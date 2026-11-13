"""
Model Gateway & Provider Abstraction Layer for Brain.
Implements tiered routing across Cloud (Groq primary, Gemini secondary) and Local (Ollama Qwen 2B).
Supports strict fallback rules, non-streaming /api/chat invocation, and telemetry metadata.
"""

import os
import re
import time
import json
import logging
import threading
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
import requests

logger = logging.getLogger("brain.models.gateway")


class ProvenanceSource(Enum):
    LOCAL_MODEL = "LOCAL_MODEL"
    CLOUD_MODEL = "CLOUD_MODEL"
    WEB = "WEB"
    OBSERVED = "OBSERVED"
    WEB_AND_MODEL = "WEB_AND_MODEL"
    DETERMINISTIC = "DETERMINISTIC"


@dataclass
class ModelResponse:
    text: str = ""
    model: str = ""
    provider: str = ""
    duration_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    fallback_used: bool = False
    cloud_attempted: bool = False
    cloud_failure_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    provenance: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GroqProvider:
    """Primary Cloud reasoning provider via Groq OpenAI-compatible API."""
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.1-8b-instant"):
        self.api_key = api_key if api_key is not None else os.environ.get("GROQ_API_KEY", "")
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self._auth_failed = False

    def is_available(self) -> bool:
        if self._auth_failed:
            return False
        key = self.api_key if self.api_key is not None else os.environ.get("GROQ_API_KEY", "")
        return bool(key and key.strip())

    def generate(self, prompt: str, timeout: float = 30.0, system_prompt: Optional[str] = None) -> ModelResponse:
        key = self.api_key if self.api_key is not None else os.environ.get("GROQ_API_KEY", "")
        if not key:
            return ModelResponse(
                success=False,
                error="GROQ_API_KEY missing or not set in environment.",
                provider="groq",
                model=self.model,
                cloud_attempted=True
            )

        start = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2
        }

        try:
            resp = requests.post(self.base_url, headers=headers, json=payload, timeout=timeout)
            duration_ms = (time.perf_counter() - start) * 1000.0

            if resp.status_code in (401, 403):
                self._auth_failed = True
                return ModelResponse(
                    success=False,
                    error=f"Groq authentication failed ({resp.status_code}): {resp.text}",
                    provider="groq",
                    model=self.model,
                    duration_ms=duration_ms,
                    cloud_attempted=True
                )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            out_text = choices[0]["message"]["content"] if choices else ""
            return ModelResponse(
                text=out_text,
                model=self.model,
                provider="groq",
                duration_ms=duration_ms,
                success=True,
                cloud_attempted=True,
                provenance=ProvenanceSource.CLOUD_MODEL.value
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return ModelResponse(
                success=False,
                error=f"Groq request error: {str(e)}",
                provider="groq",
                model=self.model,
                duration_ms=duration_ms,
                cloud_attempted=True
            )


class GeminiProvider:
    """Secondary Cloud reasoning provider via Google Gemini API."""
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash"):
        self.api_key = api_key if api_key is not None else (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", ""))
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self._auth_failed = False

    def is_available(self) -> bool:
        if self._auth_failed:
            return False
        key = self.api_key if self.api_key is not None else (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", ""))
        return bool(key and key.strip())

    def generate(self, prompt: str, timeout: float = 30.0, system_prompt: Optional[str] = None, image_path: Optional[str] = None) -> ModelResponse:
        key = self.api_key if self.api_key is not None else (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", ""))
        if not key:
            return ModelResponse(
                success=False,
                error="GEMINI_API_KEY missing or not set in environment.",
                provider="gemini",
                model=self.model,
                cloud_attempted=True
            )

        start = time.perf_counter()
        url = f"{self.base_url}/{self.model}:generateContent?key={key}"
        headers = {"Content-Type": "application/json"}
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instructions: {system_prompt}"}]})

        user_parts = [{"text": prompt}]
        if image_path:
            import base64
            from pathlib import Path
            img_p = Path(image_path)
            if img_p.exists():
                img_bytes = img_p.read_bytes()
                mime = "image/png"
                if img_p.suffix.lower() in (".jpg", ".jpeg"):
                    mime = "image/jpeg"
                b64 = base64.b64encode(img_bytes).decode("utf-8")
                user_parts.append({
                    "inlineData": {
                        "mimeType": mime,
                        "data": b64
                    }
                })
        contents.append({"role": "user", "parts": user_parts})

        payload = {"contents": contents}

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            duration_ms = (time.perf_counter() - start) * 1000.0
            if resp.status_code in (401, 403):
                self._auth_failed = True
                return ModelResponse(
                    success=False,
                    error=f"Gemini authentication failed ({resp.status_code}): {resp.text}",
                    provider="gemini",
                    model=self.model,
                    duration_ms=duration_ms,
                    cloud_attempted=True
                )
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            out_text = ""
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                out_text = parts[0].get("text", "") if parts else ""
            return ModelResponse(
                text=out_text,
                model=self.model,
                provider="gemini",
                duration_ms=duration_ms,
                success=True,
                cloud_attempted=True,
                provenance=ProvenanceSource.CLOUD_MODEL.value
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return ModelResponse(
                success=False,
                error=f"Gemini request error: {str(e)}",
                provider="gemini",
                model=self.model,
                duration_ms=duration_ms,
                cloud_attempted=True
            )


class OllamaProvider:
    """
    Local Offline Reasoning Provider via Ollama HTTP Chat API (/api/chat).
    Configured specifically for Qwen3.5 2B Q4_K_M on resource-constrained hardware.
    """
    def __init__(self, model: Optional[str] = None, base_url: str = "http://localhost:11434"):
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen3.5-brain:v2")
        self.base_url = base_url.rstrip("/")
        self._inference_lock = threading.Lock()

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=1.0)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        """Queries local Ollama tags endpoint to list installed models and architectures."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=2.0)
            if r.status_code == 200:
                data = r.json()
                return data.get("models", [])
            return []
        except Exception:
            return []

    def generate(
        self,
        prompt: str,
        timeout: float = 30.0,
        system_prompt: Optional[str] = None,
        think: bool = False,
        num_ctx: int = 2048,
        num_predict: int = 384,
        num_thread: Optional[int] = None
    ) -> ModelResponse:
        start = time.perf_counter()
        url = f"{self.base_url}/api/chat"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        options: Dict[str, Any] = {
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "temperature": 0.2
        }
        if num_thread is not None:
            options["num_thread"] = int(num_thread)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": think,
            "keep_alive": "5m",
            "options": options
        }

        try:
            with self._inference_lock:
                resp = requests.post(url, json=payload, timeout=timeout)
            duration_ms = (time.perf_counter() - start) * 1000.0

            if resp.status_code == 404:
                return ModelResponse(
                    success=False,
                    error=f"Ollama model '{self.model}' not found on host (404).",
                    provider="ollama",
                    model=self.model,
                    duration_ms=duration_ms,
                    cloud_attempted=False
                )
            resp.raise_for_status()
            data = resp.json()
            out_text = data.get("message", {}).get("content", "")
            eval_count = data.get("eval_count", 0) or 0
            eval_ns = data.get("eval_duration", 0) or 0
            prompt_eval_count = data.get("prompt_eval_count", 0) or 0
            prompt_eval_ns = data.get("prompt_eval_duration", 0) or 0
            done_reason = data.get("done_reason", "stop")
            tok_per_s = round(eval_count / (eval_ns / 1e9), 2) if eval_ns > 0 else 0.0
            ttft_ms = round(prompt_eval_ns / 1e6, 2) if prompt_eval_ns > 0 else 0.0
            return ModelResponse(
                text=out_text,
                model=self.model,
                provider="ollama",
                duration_ms=duration_ms,
                success=True,
                cloud_attempted=False,
                metadata={
                    "eval_count": eval_count,
                    "prompt_eval_count": prompt_eval_count,
                    "ttft_ms": ttft_ms,
                    "tokens_per_sec": tok_per_s,
                    "num_ctx": num_ctx,
                    "num_predict": num_predict,
                    "done_reason": done_reason,
                    "truncated": done_reason == "length",
                },
                provenance=ProvenanceSource.LOCAL_MODEL.value
            )
        except requests.exceptions.ConnectionError:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return ModelResponse(
                success=False,
                error="Ollama service is not reachable on localhost:11434.",
                provider="ollama",
                model=self.model,
                duration_ms=duration_ms,
                cloud_attempted=False
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return ModelResponse(
                success=False,
                error=f"Ollama generation error: {str(e)}",
                provider="ollama",
                model=self.model,
                duration_ms=duration_ms,
                cloud_attempted=False
            )


class ModelGateway:
    """
    Tiered Cognitive Model Gateway for Brain.
    Manages Cloud execution (Groq primary, Gemini secondary) and Local Ollama fallback.
    """
    def __init__(self):
        self.providers: Dict[str, Any] = {
            "groq": GroqProvider(),
            "gemini": GeminiProvider(),
            "ollama": OllamaProvider()
        }

    def get_provider(self, name: str) -> Any:
        return self.providers.get(name.lower())

    def discover_local_models(self) -> List[Dict[str, Any]]:
        """
        Discovers all available local offline models via the Ollama provider.
        Returns list of model dictionaries with name, size, and quantization info.
        """
        ollama = self.providers.get("ollama")
        if ollama and hasattr(ollama, "list_models"):
            return ollama.list_models()
        return []

    def get_cloud_status(self) -> Dict[str, Any]:
        groq_avail = self.providers["groq"].is_available()
        gemini_avail = self.providers["gemini"].is_available()
        groq_str = "Configured" if groq_avail else "Not configured (set GROQ_API_KEY)"
        gemini_str = "Configured" if gemini_avail else "Not configured (set GEMINI_API_KEY)"
        report = (
            "Brain Cloud Intelligence Status:\n"
            f"- Groq: {groq_str}\n"
            f"- Gemini: {gemini_str}"
        )
        return {
            "groq": groq_avail,
            "gemini": gemini_avail,
            "report": report
        }

    LOCAL_FIRST_TASKS = {
        "conversation", "basic_reasoning", "summarization", "local_task", "tool_planning"
    }
    CLOUD_ELIGIBLE_TASKS = {
        "complex_reasoning", "difficult_planning", "complex_instruction"
    }

    @staticmethod
    def contains_sensitive_data(text: str) -> bool:
        """Detects credentials or sensitive personal data that must stay local."""
        if not text:
            return False
        patterns = [
            r"\bgsk_[a-zA-Z0-9_-]{20,}\b",
            r"\bAIza[0-9A-Za-z-_]{35}\b",
            r"\bsk-[a-zA-Z0-9_-]{20,}\b",
            r"\bghp_[a-zA-Z0-9]{36}\b",
            r"\b(password|passwd|pwd|secret|api_key|apikey|ssn|credit\s*card)\s*[:=]\s*\S+",
            r"-----BEGIN (RSA|OPENSSH|PGP|PRIVATE) KEY-----",
        ]
        return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)

    def route_task(
        self,
        task_type: str,
        prompt: str,
        timeout: float = 30.0,
        system_prompt: Optional[str] = None,
        think: bool = False
    ) -> ModelResponse:
        """
        Task-based hybrid routing:
        - Sensitive data always stays LOCAL.
        - Local-first tasks route directly to local Ollama.
        - Complex tasks try cloud if available/authenticated, else fall back to local Ollama.
        """
        combined = f"{system_prompt or ''} {prompt}"
        if self.contains_sensitive_data(combined):
            return self.generate(prompt=prompt, tier="LOCAL", timeout=timeout, system_prompt=system_prompt, think=think)

        t_lower = (task_type or "").lower().strip()
        if t_lower in self.LOCAL_FIRST_TASKS or t_lower not in self.CLOUD_ELIGIBLE_TASKS:
            return self.generate(prompt=prompt, tier="LOCAL", timeout=timeout, system_prompt=system_prompt, think=think)

        # Complex task: use cloud (AUTO) only if a cloud provider is configured, else LOCAL
        if self.providers["groq"].is_available() or self.providers["gemini"].is_available():
            resp = self.generate(prompt=prompt, tier="AUTO", timeout=timeout, system_prompt=system_prompt, think=think)
            if resp.success:
                return resp

        local_resp = self.generate(prompt=prompt, tier="LOCAL", timeout=timeout, system_prompt=system_prompt, think=think)
        if local_resp.success:
            local_resp.fallback_used = True
        return local_resp

    def generate(
        self,
        prompt: str,
        tier: str = "AUTO",
        timeout: float = 30.0,
        system_prompt: Optional[str] = None,
        think: bool = False,
        num_predict: int = 384,
        image_path: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> ModelResponse:
        if image_path:
            if not self.providers["gemini"].is_available():
                return ModelResponse(
                    success=False,
                    error="Vision model unavailable offline. Requires Gemini API key or online vision endpoint.",
                    provider="gemini",
                    fallback_used=False
                )
            return self.providers["gemini"].generate(
                prompt=prompt,
                timeout=timeout,
                system_prompt=system_prompt,
                image_path=image_path
            )

        tier_upper = tier.upper()

        if tier_upper == "LOCAL":
            return self.providers["ollama"].generate(
                prompt=prompt,
                timeout=timeout,
                system_prompt=system_prompt,
                think=think,
                num_predict=num_predict
            )

        # Privacy guard: never send sensitive data to cloud in AUTO mode
        if tier_upper == "AUTO" and self.contains_sensitive_data(f"{system_prompt or ''} {prompt}"):
            return self.providers["ollama"].generate(
                prompt=prompt,
                timeout=timeout,
                system_prompt=system_prompt,
                think=think,
                num_predict=num_predict
            )

        # Handle DEEP tier (routes preferentially to Gemini if available)
        if tier_upper == "DEEP" and self.providers["gemini"].is_available():
            resp = self.providers["gemini"].generate(
                prompt=prompt,
                timeout=timeout,
                system_prompt=system_prompt
            )
            resp.cloud_attempted = True
            if resp.success:
                return resp

        # Check cloud keys availability
        groq_avail = self.providers["groq"].is_available()
        gemini_avail = self.providers["gemini"].is_available()

        if not groq_avail and not gemini_avail:
            return ModelResponse(
                success=False,
                error="No cloud models configured (set GROQ_API_KEY or GEMINI_API_KEY).",
                provider="none",
                model="none",
                cloud_attempted=False
            )

        # 1. Try Groq (Primary Cloud)
        groq_resp = self.providers["groq"].generate(
            prompt=prompt,
            timeout=timeout,
            system_prompt=system_prompt
        )
        groq_resp.cloud_attempted = True
        if groq_resp.success:
            return groq_resp

        # 2. Try Gemini (Secondary Cloud)
        gemini_resp = self.providers["gemini"].generate(
            prompt=prompt,
            timeout=timeout,
            system_prompt=system_prompt
        )
        gemini_resp.cloud_attempted = True
        if gemini_resp.success:
            return gemini_resp

        # If CLOUD tier requested, strictly return cloud failure (NO local fallback)
        if tier_upper in ("CLOUD", "DEEP"):
            combined_err = f"Cloud providers failed. Groq: {groq_resp.error}; Gemini: {gemini_resp.error}"
            return ModelResponse(
                success=False,
                error=combined_err,
                provider=gemini_resp.provider or "cloud",
                model=self.providers["groq"].model,
                fallback_used=False,
                cloud_attempted=True,
                cloud_failure_reason=combined_err
            )

        # 3. AUTO tier: Fall back to Local Ollama
        ollama_resp = self.providers["ollama"].generate(
            prompt=prompt,
            timeout=timeout,
            system_prompt=system_prompt,
            think=think
        )
        if ollama_resp.success:
            ollama_resp.fallback_used = True
            ollama_resp.cloud_attempted = True
            return ollama_resp

        return ModelResponse(
            success=False,
            error=f"All providers exhausted. Groq: {groq_resp.error}; Gemini: {gemini_resp.error}; Ollama: {ollama_resp.error}",
            provider="none",
            model="none",
            fallback_used=False,
            cloud_attempted=True
        )


class ModelRuntimeStatus:
    """Truthful model runtime identity reporter."""
    @classmethod
    def get_runtime_identity_summary(cls) -> str:
        groq_key = os.environ.get("GROQ_API_KEY", "")
        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        cloud_active = "Groq (llama-3.1-8b-instant)" if groq_key else ("Gemini" if gemini_key else "None (cloud key not set)")
        return (
            f"Brain Cognitive Reasoning Runtime: Primary cloud provider is Groq ({cloud_active}), "
            "with secondary Gemini, and local offline fallback via Ollama qwen3.5:2b-q4_K_M."
        )

    @classmethod
    def get_active_provider(cls) -> str:
        if os.environ.get("GROQ_API_KEY"):
            return "groq"
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return "gemini"
        return "ollama"


default_gateway = ModelGateway()
