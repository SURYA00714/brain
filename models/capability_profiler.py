"""
Model Capability Profiler for Brain.
Empirically benchmarks and profiles local models across 10 core dimensions.
Distinguishes between MEASURED, INFERRED, UNKNOWN, and UNSUPPORTED capabilities.
Never assigns capabilities based on name or parameter count alone.
"""

import os
import json
import time
import logging
from enum import Enum
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional

from models.universal_adapter import UniversalModelAdapter

logger = logging.getLogger("brain.models.capability_profiler")


class CapabilityStatus(Enum):
    MEASURED = "MEASURED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass
class CapabilityScore:
    dimension: str
    status: str
    score: float  # 0.0 to 1.0
    passed: bool
    details: str
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModelCapabilityProfile:
    model_id: str
    timestamp: str
    overall_capability_score: float
    capabilities: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def get_status(self, dimension: str) -> str:
        return self.capabilities.get(dimension, {}).get("status", CapabilityStatus.UNKNOWN.value)

    def get_score(self, dimension: str) -> float:
        return self.capabilities.get(dimension, {}).get("score", 0.0)

    def is_capable(self, dimension: str, threshold: float = 0.6) -> bool:
        return self.get_score(dimension) >= threshold and self.get_status(dimension) == CapabilityStatus.MEASURED.value


class ModelCapabilityProfiler:
    """
    Profiles models empirically across 10 capabilities.
    Saves and loads profiles to disk to avoid redundant re-evaluation.
    """

    PROFILES_PATH = "data/model_profiles.json"

    PROBES = {
        "instruction_following": {
            "prompt": "Answer in exactly 3 words without using the letter 'e'.",
            "evaluator": lambda out: len(out.strip().split()) <= 4 and "e" not in out.lower() and len(out.strip()) > 0,
            "weight": 1.0,
        },
        "logical_reasoning": {
            "prompt": "Premise 1: All birds lay eggs. Premise 2: Penguins are birds. Question: Do penguins lay eggs? Reply only 'Yes' or 'No'.",
            "evaluator": lambda out: "yes" in out.lower() and "no" not in out.lower(),
            "weight": 1.0,
        },
        "mathematical_reasoning": {
            "prompt": "A store has 15 laptops. It sells 7, then receives a shipment of 4. How many laptops are now in stock? Reply only with the number.",
            "evaluator": lambda out: "12" in out,
            "weight": 1.0,
        },
        "multistep_planning": {
            "prompt": "Provide 3 sequential steps to change a flat tire. Format as:\nStep 1: ...\nStep 2: ...\nStep 3: ...",
            "evaluator": lambda out: "step 1" in out.lower() and "step 2" in out.lower() and "step 3" in out.lower(),
            "weight": 1.0,
        },
        "structured_json_generation": {
            "prompt": "Output a valid JSON object with keys 'status' (string 'ok') and 'count' (number 1). Return only valid JSON, no markdown.",
            "evaluator": lambda out: _check_json(out, ["status", "count"]),
            "weight": 1.0,
        },
        "tool_call_formatting": {
            "prompt": "Format a tool invocation in JSON with key 'tool'='get_weather' and 'arguments'={'location': 'Tokyo'}. Output only JSON.",
            "evaluator": lambda out: _check_tool_json(out, "get_weather", "location"),
            "weight": 1.0,
        },
        "context_retention": {
            "prompt": "The confidential security code is 78241. Remember this code.\nWhat is the confidential security code? Reply only with the code.",
            "evaluator": lambda out: "78241" in out,
            "weight": 1.0,
        },
        "ambiguity_handling": {
            "prompt": "User says: 'Send the file now.' Is this request ambiguous? State why in one sentence.",
            "evaluator": lambda out: any(w in out.lower() for w in ["which", "what", "ambiguous", "recipient", "missing", "specify"]),
            "weight": 1.0,
        },
        "uncertainty_calibration": {
            "prompt": "What will the exact closing price of Apple stock be on December 31, 2035? Answer directly.",
            "evaluator": lambda out: any(w in out.lower() for w in ["cannot", "unknown", "impossible", "unpredictable", "uncertain", "future", "not possible"]),
            "weight": 1.0,
        },
        "multilingual_ability": {
            "prompt": "Translate the greeting 'Good morning' into French. Reply with only the French phrase.",
            "evaluator": lambda out: "bonjour" in out.lower(),
            "weight": 1.0,
        },
    }

    def __init__(self, adapter: Optional[UniversalModelAdapter] = None, storage_path: Optional[str] = None):
        self.adapter = adapter or UniversalModelAdapter()
        self.storage_path = storage_path or self.PROFILES_PATH
        self.profiles: Dict[str, ModelCapabilityProfile] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        if self.storage_path == ":memory:":
            return
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for model_id, p_dict in data.items():
                        self.profiles[model_id] = ModelCapabilityProfile(
                            model_id=p_dict.get("model_id", model_id),
                            timestamp=p_dict.get("timestamp", ""),
                            overall_capability_score=p_dict.get("overall_capability_score", 0.0),
                            capabilities=p_dict.get("capabilities", {}),
                            metadata=p_dict.get("metadata", {}),
                        )
            except Exception as e:
                logger.warning(f"Error loading model profiles from {self.storage_path}: {e}")

    def _save_profiles(self) -> None:
        if self.storage_path == ":memory:":
            return
        try:
            d = os.path.dirname(self.storage_path)
            if d:
                os.makedirs(d, exist_ok=True)
            serializable = {k: v.to_dict() for k, v in self.profiles.items()}
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving model profiles: {e}")

    def profile_model(self, model_id: str, force_retest: bool = False) -> ModelCapabilityProfile:
        """
        Runs the empirical probe suite against the model and constructs a capability profile.
        """
        if not force_retest and model_id in self.profiles:
            logger.info(f"Loaded existing capability profile for '{model_id}'")
            return self.profiles[model_id]

        logger.info(f"Profiling model '{model_id}' empirically across {len(self.PROBES)} dimensions...")
        meta = self.adapter.get_metadata(model_id)
        results: Dict[str, Dict[str, Any]] = {}
        total_score = 0.0

        for dim, probe in self.PROBES.items():
            start = time.perf_counter()
            resp = self.adapter.generate(
                prompt=probe["prompt"],
                model_id=model_id,
                temperature=0.1,
                num_predict=128,
                timeout=30.0,
            )
            lat_ms = (time.perf_counter() - start) * 1000.0

            if not resp.success:
                status = CapabilityStatus.UNSUPPORTED.value
                score = 0.0
                passed = False
                details = f"Execution error: {resp.error}"
            else:
                passed = bool(probe["evaluator"](resp.text))
                status = CapabilityStatus.MEASURED.value
                score = 1.0 if passed else 0.0
                details = resp.text.strip().replace("\n", " ")[:80]

            total_score += score
            results[dim] = CapabilityScore(
                dimension=dim,
                status=status,
                score=score,
                passed=passed,
                details=details,
                latency_ms=round(lat_ms, 1),
            ).to_dict()

        overall = round((total_score / len(self.PROBES)) * 100.0, 1)
        profile = ModelCapabilityProfile(
            model_id=model_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            overall_capability_score=overall,
            capabilities=results,
            metadata={
                "format": meta.format if meta else "unknown",
                "family": meta.family if meta else "unknown",
                "parameter_size": meta.parameter_size if meta else "unknown",
                "quantization": meta.quantization if meta else "unknown",
                "file_size_mb": meta.file_size_mb if meta else 0.0,
            },
        )

        self.profiles[model_id] = profile
        self._save_profiles()
        logger.info(f"Profile complete for '{model_id}': Overall Score {overall}%")
        return profile

    def get_or_infer_profile(self, model_id: str) -> ModelCapabilityProfile:
        """Returns existing profile, or profiles model, or returns inferred default if unavailable."""
        if model_id in self.profiles:
            return self.profiles[model_id]
        try:
            return self.profile_model(model_id)
        except Exception as e:
            logger.warning(f"Failed to profile '{model_id}': {e}. Using inferred profile.")
            return self._build_inferred_profile(model_id)

    def _build_inferred_profile(self, model_id: str) -> ModelCapabilityProfile:
        meta = self.adapter.get_metadata(model_id)
        inferred_caps = {}
        for dim in self.PROBES.keys():
            inferred_caps[dim] = CapabilityScore(
                dimension=dim,
                status=CapabilityStatus.INFERRED.value,
                score=0.5,
                passed=False,
                details="Inferred from model class; pending empirical measurement",
            ).to_dict()

        return ModelCapabilityProfile(
            model_id=model_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            overall_capability_score=50.0,
            capabilities=inferred_caps,
            metadata=meta.to_dict() if meta else {},
        )


def _check_json(text: str, required_keys: List[str]) -> bool:
    try:
        raw = text.strip()
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            data = json.loads(raw[start:end+1])
            return all(k in data for k in required_keys)
    except Exception:
        pass
    return False


def _check_tool_json(text: str, tool_name: str, arg_key: str) -> bool:
    try:
        raw = text.strip()
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            data = json.loads(raw[start:end+1])
            has_tool = data.get("tool") == tool_name or data.get("name") == tool_name
            args = data.get("arguments") or data.get("args") or data.get("parameters") or {}
            has_arg = arg_key in args
            return bool(has_tool and has_arg)
    except Exception:
        pass
    return False
