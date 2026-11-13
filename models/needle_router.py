"""
Needle-Powered High-Speed Semantic Tool Router.
Uses needle.Needle's lightweight C/ONNX embedding model to filter Brain's 105 tools
down to the top-K relevant candidates in <25ms, preventing LLM token bloat and hallucination.
"""

import logging
import re
from typing import Optional, List, Dict, Any, Tuple
import numpy as np

logger = logging.getLogger("brain.models.needle_router")

# Global singleton instance of Needle model
_NEEDLE_INSTANCE = None


def get_needle():
    global _NEEDLE_INSTANCE
    if _NEEDLE_INSTANCE is None:
        try:
            import needle
            _NEEDLE_INSTANCE = needle.Needle()
            logger.info("Initialized native 27MB Needle model successfully.")
        except Exception as e:
            logger.debug(f"Could not load native Needle model ({e}). Fallback to heuristic.")
            _NEEDLE_INSTANCE = False
    return _NEEDLE_INSTANCE if _NEEDLE_INSTANCE is not False else None


class NeedleToolFilter:
    """Indexes Brain tools and uses Needle embeddings to retrieve the top-K tools for any prompt."""

    def __init__(self, top_k: int = 5):
        self.top_k = top_k
        self.needle = get_needle()
        self.tool_index: List[Dict[str, Any]] = []
        self.tool_embeddings: Optional[np.ndarray] = None
        self._build_index()

    def _build_index(self):
        try:
            from tools.registry import default_registry
            self.tool_index = default_registry.list_tools()
        except Exception as e:
            logger.error(f"Failed to load tool registry: {e}")
            self.tool_index = []

        if not self.needle or not self.tool_index:
            return

        texts = []
        for t in self.tool_index:
            name = t.get("name", "")
            desc = t.get("description", "")
            params = ", ".join(t.get("parameters", {}).keys()) if isinstance(t.get("parameters"), dict) else ""
            texts.append(f"{name}: {desc} (parameters: {params})")

        try:
            embs = [self.needle.embed(txt) for txt in texts]
            # Normalize embeddings for fast dot-product cosine similarity
            mat = np.array(embs, dtype=np.float32)
            norms = np.linalg.norm(mat, axis=1, keepdims=True)
            norms[norms == 0] = 1e-9
            self.tool_embeddings = mat / norms
            logger.info(f"Needle indexed {len(self.tool_index)} tools for vector retrieval.")
        except Exception as e:
            logger.error(f"Failed to precompute Needle embeddings: {e}")
            self.tool_embeddings = None

    def filter_tools(self, user_request: str, k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Returns the top-K most relevant tools for a user request."""
        target_k = k or self.top_k
        if not user_request or not self.tool_index:
            return []

        # High-priority keyword boosts for exact operational intents
        kw_boosts = self._keyword_intent_matches(user_request)

        if self.needle is not None and self.tool_embeddings is not None:
            try:
                q_emb = np.array(self.needle.embed(user_request), dtype=np.float32)
                q_norm = np.linalg.norm(q_emb)
                if q_norm > 0:
                    q_emb = q_emb / q_norm
                    sims = np.dot(self.tool_embeddings, q_emb)

                    # Apply keyword boosts
                    for idx, tool in enumerate(self.tool_index):
                        if tool["name"] in kw_boosts:
                            sims[idx] += 0.15

                    top_idxs = np.argsort(sims)[::-1][:target_k]
                    return [self.tool_index[i] for i in top_idxs]
            except Exception as e:
                logger.warning(f"Needle vector similarity failed ({e}), falling back to keyword heuristics.")

        # Heuristic fallback if Needle is unavailable
        matched = [t for t in self.tool_index if t["name"] in kw_boosts]
        return matched[:target_k] if matched else self.tool_index[:target_k]

    def _keyword_intent_matches(self, query: str) -> set[str]:
        q = query.lower()
        matches = set()
        if any(w in q for w in ["search", "find online", "google", "lookup", "research"]):
            matches.update(["WEB_SEARCH", "BROWSER_SEARCH", "BROWSER_NAVIGATE", "DOM_EXTRACT_CONTENT"])
        if any(w in q for w in ["whatsapp", "message", "text", "chat", "send"]):
            matches.update(["OPEN_APP", "BROWSER_NAVIGATE", "DOM_TYPE", "DOM_CLICK", "TYPE_TEXT", "PRESS_KEY"])
        if any(w in q for w in ["play", "video", "anime", "youtube", "watch", "episode"]):
            matches.update(["BROWSER_NAVIGATE", "DOM_CLICK", "BROWSER_WAIT", "VOLUME_UP"])
        if any(w in q for w in ["screenshot", "capture screen"]):
            matches.update(["SCREENSHOT", "OCR_SCREEN", "ANALYZE_SCREEN"])
        if any(w in q for w in ["volume", "audio", "sound", "mute"]):
            matches.update(["VOLUME_UP", "VOLUME_DOWN", "VOLUME_MUTE"])
        if any(w in q for w in ["file", "read", "write", "save", "log", "notes"]):
            matches.update(["WRITE_TEXT_FILE", "READ_TEXT_FILE", "CREATE_FILE", "SEARCH_FILES", "LIST_FILES"])
        if any(w in q for w in ["cpu", "ram", "memory", "disk", "hardware", "system info"]):
            matches.update(["CPU_STATUS", "MEMORY_STATUS", "DISK_STATUS", "SYSTEM_INFO"])
        return matches


# Singleton instance
default_needle_filter = NeedleToolFilter(top_k=5)
