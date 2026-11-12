"""
Universal Model Adapter for Brain.
Provides a model-independent abstraction layer for local and remote LLMs.
Discovers local models, normalizes request/response formats, inspects metadata,
handles safe loading/unloading, and manages hardware-constrained execution bounds.
"""

import os
import time
import json
import logging
import threading
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List, Union
import requests

from models.gateway import ModelResponse, ProvenanceSource

logger = logging.getLogger("brain.models.universal_adapter")


@dataclass
class ModelMetadata:
    model_id: str
    name: str
    provider: str
    format: str = "gguf"
    family: str = "unknown"
    parameter_size: str = "unknown"
    quantization: str = "unknown"
    file_size_mb: float = 0.0
    context_window: int = 2048
    capabilities: List[str] = field(default_factory=list)
    custom_parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class UniversalModelAdapter:
    """
    Universal Model Adapter managing local model discovery, metadata inspection,
    safe loading/unloading, parameter normalization, and provider abstraction.
    """

    def __init__(self, default_provider: str = "ollama", base_url: str = "http://localhost:11434"):
        self.default_provider = default_provider
        self.base_url = base_url.rstrip("/")
        self._active_model_id: Optional[str] = None
        self._lock = threading.Lock()
        self._discovered_models: Dict[str, ModelMetadata] = {}
        self.refresh_models()

    def refresh_models(self) -> Dict[str, ModelMetadata]:
        """Discovers all locally installed models via Ollama API."""
        discovered: Dict[str, ModelMetadata] = {}
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("models", []):
                    name = item.get("name", "")
                    details = item.get("details", {}) or {}
                    size_bytes = item.get("size", 0) or 0
                    caps = item.get("capabilities", []) or []

                    meta = ModelMetadata(
                        model_id=name,
                        name=name,
                        provider="ollama",
                        format=details.get("format", "gguf"),
                        family=details.get("family", "unknown"),
                        parameter_size=details.get("parameter_size", "unknown"),
                        quantization=details.get("quantization_level", "unknown"),
                        file_size_mb=round(size_bytes / (1024 * 1024), 1),
                        context_window=details.get("context_length", 2048),
                        capabilities=caps,
                    )
                    discovered[name] = meta
        except Exception as e:
            logger.warning(f"Failed to query Ollama model tags: {e}")

        with self._lock:
            self._discovered_models = discovered
            if not self._active_model_id and discovered:
                # Default preference: qwen3.5:2b-q4_K_M or first available
                if "qwen3.5:2b-q4_K_M" in discovered:
                    self._active_model_id = "qwen3.5:2b-q4_K_M"
                else:
                    self._active_model_id = next(iter(discovered.keys()))

        return discovered

    def list_models(self) -> List[ModelMetadata]:
        """Returns metadata for all discovered models."""
        with self._lock:
            return list(self._discovered_models.values())

    def get_metadata(self, model_id: Optional[str] = None) -> Optional[ModelMetadata]:
        """Gets metadata for specified or active model."""
        target = model_id or self._active_model_id
        with self._lock:
            return self._discovered_models.get(target) if target else None

    @property
    def active_model(self) -> str:
        with self._lock:
            return self._active_model_id or "qwen3.5:2b-q4_K_M"

    def set_active_model(self, model_id: str, unload_previous: bool = True) -> bool:
        """Safely switches the active model and optionally unloads the previous model from memory."""
        with self._lock:
            if model_id not in self._discovered_models:
                # Try refresh
                self.refresh_models()
                if model_id not in self._discovered_models:
                    logger.error(f"Cannot switch to unknown model '{model_id}'")
                    return False

            prev = self._active_model_id
            if unload_previous and prev and prev != model_id:
                self._safe_unload_model(prev)

            self._active_model_id = model_id
            logger.info(f"Active model switched to: {model_id}")
            return True

    def unload_model(self, model_id: Optional[str] = None) -> None:
        """Public method to safely unload a model from local VRAM/RAM."""
        target = model_id or self._active_model
        if target:
            self._safe_unload_model(target)

    def _safe_unload_model(self, model_id: str) -> None:
        """Requests Ollama to unload model from VRAM/RAM by setting keep_alive: 0."""
        try:
            url = f"{self.base_url}/api/generate"
            payload = {"model": model_id, "keep_alive": 0}
            requests.post(url, json=payload, timeout=2.0)
            logger.info(f"Unload signal sent for model '{model_id}'")
        except Exception as e:
            logger.warning(f"Error unloading model '{model_id}': {e}")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model_id: Optional[str] = None,
        temperature: float = 0.2,
        num_ctx: Optional[int] = None,
        num_predict: Optional[int] = None,
        timeout: float = 30.0,
        keep_alive: str = "5m",
        think: bool = False,
    ) -> ModelResponse:
        """
        Normalized generation request across any local model.
        Normalizes inputs, limits, and outputs.
        """
        target_model = model_id or self.active_model
        meta = self.get_metadata(target_model)

        # Context limit normalization
        ctx_limit = num_ctx or 2048
        if meta and meta.context_window:
            ctx_limit = min(ctx_limit, meta.context_window)

        pred_limit = num_predict or 384

        start = time.perf_counter()
        url = f"{self.base_url}/api/chat"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        options: Dict[str, Any] = {
            "num_ctx": ctx_limit,
            "num_predict": pred_limit,
            "temperature": temperature,
        }

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "think": think,
            "keep_alive": keep_alive,
            "options": options,
        }

        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            duration_ms = (time.perf_counter() - start) * 1000.0

            if resp.status_code == 404:
                return ModelResponse(
                    success=False,
                    error=f"Model '{target_model}' not found in local provider (404).",
                    provider="ollama",
                    model=target_model,
                    duration_ms=duration_ms,
                )
            resp.raise_for_status()
            data = resp.json()
            out_text = data.get("message", {}).get("content", "")
            eval_count = data.get("eval_count", 0) or 0
            eval_ns = data.get("eval_duration", 0) or 0
            prompt_eval_ns = data.get("prompt_eval_duration", 0) or 0
            done_reason = data.get("done_reason", "stop")

            tok_per_s = round(eval_count / (eval_ns / 1e9), 2) if eval_ns > 0 else 0.0
            ttft_ms = round(prompt_eval_ns / 1e6, 2) if prompt_eval_ns > 0 else 0.0

            return ModelResponse(
                text=out_text,
                model=target_model,
                provider="ollama",
                duration_ms=duration_ms,
                success=True,
                cloud_attempted=False,
                metadata={
                    "eval_count": eval_count,
                    "ttft_ms": ttft_ms,
                    "tokens_per_sec": tok_per_s,
                    "num_ctx": ctx_limit,
                    "num_predict": pred_limit,
                    "done_reason": done_reason,
                    "truncated": done_reason == "length",
                    "format": meta.format if meta else "gguf",
                    "family": meta.family if meta else "unknown",
                },
                provenance=ProvenanceSource.LOCAL_MODEL.value,
            )
        except requests.exceptions.ConnectionError:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return ModelResponse(
                success=False,
                error="Local model provider is not reachable on localhost:11434.",
                provider="ollama",
                model=target_model,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return ModelResponse(
                success=False,
                error=f"Generation error: {str(e)}",
                provider="ollama",
                model=target_model,
                duration_ms=duration_ms,
            )
