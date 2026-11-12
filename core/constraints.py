"""
Instruction-Following & Constraint Validation Engine for Brain (Phase 1.6).
Provides deterministic validation and bounded correction retries for:
- Word count (exact, min, max)
- Sentence count
- Forbidden characters & forbidden words
- Required keywords
- Numbered output & exact formatting (JSON, single-line, no bullets)
- Language / ASCII restrictions
- Multiple simultaneous constraints
"""

import json
import re
from typing import Dict, Any, List, Tuple, Optional


WORD_NUMBER_MAP = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
}


def _parse_count_token(tok: str) -> Optional[int]:
    t = tok.strip().lower()
    if t.isdigit():
        return int(t)
    return WORD_NUMBER_MAP.get(t)


def extract_constraints_from_prompt(prompt: str) -> Dict[str, Any]:
    """
    Deterministically extracts explicit formatting and lexical constraints
    from natural-language instructions.
    """
    if not prompt or not isinstance(prompt, str):
        return {}

    lowered = prompt.lower()
    constraints: Dict[str, Any] = {}

    # Exact word count: "in exactly three words", "in 3 words"
    m_exact_wc = re.search(r"\bexactly\s+(\w+)\s+words?\b", lowered)
    if m_exact_wc:
        n = _parse_count_token(m_exact_wc.group(1))
        if n is not None:
            constraints["word_count"] = n

    # Max words: "at most 20 words", "under 15 words", "max 10 words", "no more than 10 words"
    m_max_wc = re.search(r"\b(?:at\s+most|under|max(?:imum)?|no\s+more\s+than)\s+(\w+)\s+words?\b", lowered)
    if m_max_wc:
        n = _parse_count_token(m_max_wc.group(1))
        if n is not None:
            constraints["max_words"] = n

    # Max sentences: "in one sentence", "in 2 sentences"
    m_sent = re.search(r"\bin\s+(?:exactly\s+)?(\w+)\s+sentences?\b", lowered)
    if m_sent:
        n = _parse_count_token(m_sent.group(1))
        if n is not None:
            constraints["max_sentences"] = n

    # Forbidden words: "without using the word 'memory'", "do not use the word X", "never use the word Y"
    for m_fw in re.finditer(r"(?:without\s+(?:using\s+)?(?:the\s+)?word|do\s+not\s+use\s+(?:the\s+)?word|never\s+use\s+(?:the\s+)?word)\s+['\"]?([a-zA-Z0-9_-]+)['\"]?", lowered):
        constraints.setdefault("forbidden_words", []).append(m_fw.group(1))

    # Forbidden characters / punctuation / numbers / bullets
    forbidden_chars: List[str] = []
    if re.search(r"\b(?:do\s+not|don't|no|without)\b[^.]*\bcommas?\b", lowered):
        forbidden_chars.append(",")
    if re.search(r"\b(?:do\s+not|don't|no|without)\b[^.]*\bnumbers?\b", lowered):
        forbidden_chars.extend(["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"])
    if re.search(r"\b(?:do\s+not|don't|no|without)\b[^.]*\bbullet\s*points?\b", lowered):
        forbidden_chars.extend(["•", "-", "*"])
    if forbidden_chars:
        # Deduplicate while preserving order
        constraints["forbidden_chars"] = list(dict.fromkeys(forbidden_chars))

    # Numbered output
    if re.search(r"\bnumbered\s+(?:list|output|steps)\b", lowered):
        constraints["numbered_output"] = True

    # JSON format
    if re.search(r"\brespond\s+only\s+(?:with|in)\s+(?:valid\s+)?json\b", lowered):
        constraints["exact_format"] = "json"

    # Single line
    if re.search(r"\bsingle[- ]line\b", lowered):
        constraints["exact_format"] = "single_line"

    # English / ASCII restriction
    if re.search(r"\b(?:only\s+in\s+english|english\s+only|ascii\s+only)\b", lowered):
        constraints["language"] = "ascii"

    return constraints


def validate_constraints(output: str, constraints: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Deterministically validates `output` against all specified constraints.
    Returns (passed: bool, violations: List[str]).
    """
    if not output or not isinstance(output, str) or not output.strip():
        return False, ["Output is empty"]

    if not constraints:
        return True, []

    text = output.strip()
    violations: List[str] = []

    # 1. Word count checks
    words = text.split()
    if "word_count" in constraints:
        target = int(constraints["word_count"])
        max_wc = int(constraints.get("max_words", target))
        if not (target <= len(words) <= max_wc):
            violations.append(f"Expected {target} words, got {len(words)}.")
    elif "max_words" in constraints:
        max_wc = int(constraints["max_words"])
        if len(words) > max_wc:
            violations.append(f"Word count {len(words)} exceeds maximum of {max_wc}.")

    if "min_words" in constraints:
        min_wc = int(constraints["min_words"])
        if len(words) < min_wc:
            violations.append(f"Word count {len(words)} is below minimum of {min_wc}.")

    # 2. Sentence count check
    if "max_sentences" in constraints:
        max_s = int(constraints["max_sentences"])
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        if len(sentences) > max_s:
            violations.append(f"Sentence count {len(sentences)} exceeds maximum of {max_s}.")

    # 3. Forbidden characters
    if "forbidden_chars" in constraints:
        for ch in constraints["forbidden_chars"]:
            if ch in text:
                violations.append(f"Contains forbidden character '{ch}'.")

    # 4. Forbidden words
    if "forbidden_words" in constraints:
        lowered = text.lower()
        for fw in constraints["forbidden_words"]:
            if re.search(r"\b" + re.escape(fw.lower()) + r"\b", lowered):
                violations.append(f"Contains forbidden word '{fw}'.")

    # 5. Required keywords
    if "required_keywords" in constraints:
        lowered = text.lower()
        for kw in constraints["required_keywords"]:
            if kw.lower() not in lowered:
                violations.append(f"Missing required keyword '{kw}'.")

    # 6. Numbered output
    if constraints.get("numbered_output"):
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        numbered = [ln for ln in lines if re.match(r"^\d+[\.\)]\s+", ln)]
        if not numbered:
            violations.append("Output must be formatted as a numbered list (e.g., '1. ...').")

    # 7. Exact formatting
    fmt = constraints.get("exact_format")
    if fmt == "json":
        try:
            json.loads(text)
        except Exception:
            violations.append("Output must be valid JSON.")
    elif fmt == "single_line":
        if "\n" in text:
            violations.append("Output must be a single line with no line breaks.")

    # 8. Language / ASCII restriction
    lang = constraints.get("language")
    if lang in ("ascii", "english"):
        non_ascii = [ch for ch in text if ord(ch) > 127 and ch not in ("•", "—", "–", "’", "‘", "“", "”")]
        if non_ascii:
            violations.append("Output contains non-ASCII/non-English characters.")

    return len(violations) == 0, violations


def generate_with_constraints(
    gateway: Any,
    prompt: str,
    constraints: Optional[Dict[str, Any]] = None,
    tier: str = "LOCAL",
    max_retries: int = 2,
    timeout: float = 30.0,
    system_prompt: Optional[str] = None
) -> Tuple[Any, bool, List[str]]:
    """
    Generates a response via `gateway` and enforces deterministic constraint validation
    with bounded correction retries when constraints fail.
    Returns: (ModelResponse, passed: bool, violations: List[str])
    """
    active_constraints = constraints if constraints is not None else extract_constraints_from_prompt(prompt)
    current_prompt = prompt
    if active_constraints.get("forbidden_chars"):
        fc = " ".join(repr(c) for c in active_constraints["forbidden_chars"])
        current_prompt = (
            f"{prompt}\n"
            f"Strict rule: Do NOT use any of these characters anywhere (including inside hyphenated words): {fc}. "
            "Be brief and avoid unnecessary prose."
        )
    last_resp = None
    last_violations: List[str] = []

    for attempt in range(max_retries + 1):
        resp = gateway.generate(
            prompt=current_prompt,
            tier=tier,
            timeout=timeout,
            system_prompt=system_prompt
        )
        last_resp = resp
        if not resp.success or not resp.text:
            return resp, False, [resp.error or "Model generation failed"]

        passed, violations = validate_constraints(resp.text.strip(), active_constraints)
        last_violations = violations
        if passed:
            return resp, True, []

        if attempt < max_retries:
            violation_str = "; ".join(violations)
            offending_tokens = []
            for ch in active_constraints.get("forbidden_chars", []):
                if ch in resp.text:
                    for tok in resp.text.split():
                        if ch in tok and tok not in offending_tokens:
                            offending_tokens.append(tok)
            offending_hint = (
                f" Replace or remove these exact offending words: {', '.join(offending_tokens[:6])}."
                if offending_tokens else ""
            )
            current_prompt = (
                f"{prompt}\n\n"
                f"Your previous draft failed these strict constraints: {violation_str}.{offending_hint}\n"
                f"Previous draft: {resp.text.strip()}\n"
                "Rewrite a minimal response now (just the requested items, no prose or hyphenated words) so ALL constraints are strictly satisfied. "
                "Output ONLY the corrected final response."
            )

    return last_resp, False, last_violations
