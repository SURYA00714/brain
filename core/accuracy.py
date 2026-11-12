"""
Accuracy & Evidence Grounding Engine for Brain (Phase 1.6).
Provides:
- Intent & external-information-need assessment
- Ambiguity & missing-information detection
- Evidence relevance filtering & conflict detection
- Claim verification against retrieved evidence
- Observable-signal confidence scoring (never model-invented)
"""

import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple


STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "when", "where",
    "what", "which", "who", "whom", "whose", "why", "how", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can", "of", "in", "on",
    "at", "to", "for", "with", "by", "from", "about", "as", "into", "like",
    "through", "after", "over", "between", "out", "against", "during", "without",
    "before", "under", "around", "among", "today", "now", "latest", "recent",
    "recently", "current", "happened", "news", "please", "tell", "me", "give",
    "find", "search", "look", "up", "this", "that", "these", "those", "it"
}

AMBIGUOUS_PHRASES = {
    "fix this", "do this", "handle it", "fix it", "what about it",
    "help with this", "check this", "check it", "update this", "update it",
    "explain this", "solve this", "run this", "run it"
}

FRESHNESS_TRIGGERS = {
    "latest", "recent", "recently", "today", "news", "current version",
    "new features in", "what happened", "what changed in", "this week",
    "just happened", "who won", "price of", "weather in", "score of"
}


@dataclass
class ObservableConfidence:
    """Confidence computed strictly from observable verification signals."""
    score: float
    level: str  # HIGH | MEDIUM | LOW | UNVERIFIED
    evidence_coverage: float
    source_agreement: float
    validation_passed: bool
    task_completeness: float
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AccuracyEngine:
    """
    Factual grounding, evidence verification, and observable confidence engine.
    Never invents confidence scores or fabricates citations.
    """

    @staticmethod
    def extract_keywords(text: str) -> List[str]:
        """Extracts meaningful domain keywords from a query or text."""
        if not text:
            return []
        tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
        return [t for t in tokens if len(t) >= 3 and t not in STOPWORDS]

    @classmethod
    def classify_external_info_need(cls, user_request: str) -> str:
        """
        Determines whether a request requires external information:
        - WEB: requires live/fresh external web data
        - SYSTEM: requires live local OS/hardware inspection
        - MEMORY: requires stored user/episodic memory
        - NONE: self-contained reasoning/math/static definition
        """
        lowered = (user_request or "").lower().strip()
        if any(trig in lowered for trig in FRESHNESS_TRIGGERS):
            return "WEB"
        if any(kw in lowered for kw in ("search the web", "look up", "search for")):
            return "WEB"
        if any(kw in lowered for kw in ("cpu", "ram", "memory usage", "disk space", "running process", "battery")):
            return "SYSTEM"
        if any(kw in lowered for kw in ("my preferred", "do i live", "my name", "remember ", "last time")):
            return "MEMORY"
        return "NONE"

    @classmethod
    def detect_ambiguity(
        cls,
        user_request: str,
        recent_turns: Optional[List[Any]] = None
    ) -> Optional[str]:
        """
        Detects underspecified or ambiguous requests when no conversational referent exists.
        Returns a clarification question string if ambiguous, else None.
        """
        if not user_request or not isinstance(user_request, str):
            return "Could you please provide a request or question?"

        lowered = user_request.strip().lower().strip(".?!")
        if lowered in AMBIGUOUS_PHRASES:
            has_referent = False
            if recent_turns:
                for turn in reversed(recent_turns):
                    if getattr(turn, "referenced_app", None) or getattr(turn, "referenced_query", None):
                        has_referent = True
                        break
            if not has_referent:
                return (
                    "Could you clarify what you would like me to address? "
                    "Please specify the target application, file, or problem."
                )
        return None

    @staticmethod
    def is_generic_portal_snippet(snippet: str) -> bool:
        """
        Distinguishes generic news-portal/tracker/index descriptions from specific event evidence.
        """
        lowered = (snippet or "").lower()
        portal_markers = (
            "get the latest news",
            "news & features",
            "news and features",
            "read astronomy articles",
            "brings you the latest",
            "stay up to date",
            "all the latest breaking",
            "latest news, features",
            "browse all articles",
            "subscribe to",
            "mission tracker",
            "live updates",
            "news, missions",
            "breaking news",
            "headlines and today",
        )
        if any(m in lowered for m in portal_markers):
            return True
        if re.search(r"\blive\s+[a-z]+\s+news\b", lowered):
            return True
        return False

    @staticmethod
    def extract_dates(text: str) -> List[str]:
        """Extracts explicit year or month-day-year date mentions from evidence text."""
        if not text:
            return []
        dates = re.findall(
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b|\b20\d{2}-\d{2}-\d{2}\b|\b20\d{2}\b",
            text,
            flags=re.IGNORECASE
        )
        return list(dict.fromkeys(dates))

    @classmethod
    def evaluate_evidence_relevance(
        cls,
        query: str,
        findings: List[str],
        sources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Filters retrieved findings by semantic & domain-keyword relevance to the query.
        Distinguishes generic portal pages from specific event evidence for 'today'/live queries.
        Never falls back to off-topic or portal-only snippets when specific evidence is missing.
        """
        if not findings:
            return {
                "relevant_findings": [],
                "relevant_sources": [],
                "evidence_coverage": 0.0,
                "source_agreement": 0.0,
                "conflicts": [],
                "is_ambiguous": False,
                "dates_found": [],
                "portal_only": False,
            }

        q_lower = (query or "").lower()
        requires_today_event = any(t in q_lower for t in ("today", "just happened", "what happened"))
        q_keywords = cls.extract_keywords(query)
        relevant_findings: List[str] = []
        relevant_sources: List[str] = []
        matched_keywords = set()
        portal_filtered_count = 0

        for idx, finding in enumerate(findings):
            f_lower = (finding or "").lower()
            if not f_lower.strip():
                continue

            if requires_today_event and cls.is_generic_portal_snippet(finding):
                portal_filtered_count += 1
                continue

            if not q_keywords:
                relevant_findings.append(finding)
                if sources and idx < len(sources):
                    relevant_sources.append(sources[idx])
                continue

            hits = [kw for kw in q_keywords if re.search(r"\b" + re.escape(kw) + r"\b", f_lower)]
            if hits:
                matched_keywords.update(hits)
                relevant_findings.append(finding)
                if sources and idx < len(sources):
                    relevant_sources.append(sources[idx])

        coverage = (len(matched_keywords) / len(q_keywords)) if (q_keywords and relevant_findings) else (1.0 if relevant_findings else 0.0)
        conflicts = cls.detect_conflicts(relevant_findings)
        agreement = 1.0 if not conflicts else max(0.2, 1.0 - 0.4 * len(conflicts))
        is_ambiguous = (0.0 < coverage < 0.5) or bool(conflicts)
        dates_found = cls.extract_dates(" ".join(relevant_findings))

        return {
            "relevant_findings": relevant_findings,
            "relevant_sources": relevant_sources,
            "evidence_coverage": round(coverage, 3),
            "source_agreement": round(agreement, 3),
            "conflicts": conflicts,
            "is_ambiguous": is_ambiguous,
            "dates_found": dates_found,
            "portal_only": (portal_filtered_count > 0 and len(relevant_findings) == 0),
        }

    @staticmethod
    def detect_conflicts(findings: List[str]) -> List[str]:
        """
        Detects explicit contradictions across multiple evidence snippets:
        - Opposing polarity on the same topic (e.g. 'is supported' vs 'is not supported')
        - Conflicting numerical values with identical units (e.g. '8 GB' vs '16 GB')
        """
        if len(findings) < 2:
            return []

        conflicts: List[str] = []
        neg_markers = (" not ", " no ", " never ", " cannot ", " unsupported ", " false", " disabled")
        pos_markers = (" is ", " yes ", " supported", " true", " enabled", " confirmed")

        has_pos = any(any(m in f.lower() for m in pos_markers) and not any(n in f.lower() for n in neg_markers) for f in findings)
        has_neg = any(any(n in f.lower() for n in neg_markers) for f in findings)
        if has_pos and has_neg:
            conflicts.append("Sources contain opposing affirmative and negative statements.")

        # Check conflicting numbers with same unit
        unit_values: Dict[str, set] = {}
        for f in findings:
            for val, unit in re.findall(r"\b(\d+(?:\.\d+)?)\s*(gb|mb|tb|ghz|mhz|%|ms|seconds?|minutes?|hours?)\b", f.lower()):
                norm_unit = unit.rstrip("s")
                unit_values.setdefault(norm_unit, set()).add(val)
        for unit, vals in unit_values.items():
            if len(vals) > 1:
                sorted_vals = sorted(vals)
                conflicts.append(f"Conflicting values for '{unit}': {', '.join(sorted_vals)}.")

        return conflicts

    @classmethod
    def verify_claims(cls, answer: str, evidence: List[str]) -> Dict[str, Any]:
        """
        Verifies whether concrete factual tokens (numbers, URLs) in an answer
        are grounded in the provided evidence.
        """
        if not answer:
            return {"grounded": False, "unverified_claims": ["Empty answer"], "coverage": 0.0}

        if not evidence:
            return {"grounded": False, "unverified_claims": ["No supporting evidence provided"], "coverage": 0.0}

        evidence_blob = " ".join(evidence).lower()
        unverified: List[str] = []

        # Check URLs in answer aren't fabricated
        urls = re.findall(r"https?://[^\s\)\]]+", answer)
        for u in urls:
            if u.lower() not in evidence_blob:
                unverified.append(f"Unverified URL: {u}")

        # Check numeric claims in answer against evidence
        ans_nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", answer))
        ev_nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", evidence_blob))
        for n in sorted(ans_nums - ev_nums):
            unverified.append(f"Number '{n}' not found in retrieved evidence")

        ans_kw = cls.extract_keywords(answer)
        if ans_kw:
            matched = sum(1 for kw in ans_kw if kw in evidence_blob)
            coverage = matched / len(ans_kw)
        else:
            coverage = 1.0

        return {
            "grounded": len(unverified) == 0 and coverage >= 0.3,
            "unverified_claims": unverified,
            "coverage": round(coverage, 3)
        }

    @staticmethod
    def compute_observable_confidence(
        evidence_coverage: float,
        source_agreement: float = 1.0,
        validation_passed: bool = True,
        task_completeness: float = 1.0
    ) -> ObservableConfidence:
        """
        Computes confidence strictly from observable signals.
        Never asks the model to invent a confidence number.
        """
        cov = max(0.0, min(1.0, float(evidence_coverage)))
        agr = max(0.0, min(1.0, float(source_agreement)))
        comp = max(0.0, min(1.0, float(task_completeness)))
        val_factor = 1.0 if validation_passed else 0.3

        score = round((0.40 * cov + 0.25 * agr + 0.20 * comp + 0.15 * val_factor), 3)
        reasons: List[str] = []
        if cov == 0.0:
            reasons.append("No relevant supporting evidence found")
        elif cov < 0.5:
            reasons.append(f"Partial evidence coverage ({cov:.0%})")
        if agr < 1.0:
            reasons.append(f"Source disagreement detected ({agr:.0%})")
        if not validation_passed:
            reasons.append("Deterministic validation failed")
        if comp < 1.0:
            reasons.append(f"Incomplete task coverage ({comp:.0%})")

        if not validation_passed or cov == 0.0:
            level = "UNVERIFIED"
        elif score >= 0.8:
            level = "HIGH"
        elif score >= 0.55:
            level = "MEDIUM"
        else:
            level = "LOW"

        return ObservableConfidence(
            score=score,
            level=level,
            evidence_coverage=cov,
            source_agreement=agr,
            validation_passed=validation_passed,
            task_completeness=comp,
            reasons=reasons
        )
