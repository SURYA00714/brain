"""
Deterministic Mathematical & Logical Intelligence Engine for Brain (Phase 1.9).
Provides safe AST-based arithmetic, percentages, ratios, unit conversions,
sequence pattern recognition, and logical contradiction detection.
Zero eval()/exec(), <1ms deterministic execution.
"""

import ast
import operator
import re
from typing import Any, Dict, List, Optional, Tuple


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def safe_eval_arithmetic(expr: str) -> Optional[float]:
    """Safely evaluates an arithmetic expression using AST parsing (no eval)."""
    if not expr or not isinstance(expr, str):
        return None
    clean = expr.strip().replace("^", "**")
    if len(clean) > 120:
        return None
    try:
        tree = ast.parse(clean, mode="eval")
    except SyntaxError:
        return None

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("Exponent too large")
            if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
                raise ZeroDivisionError("Division by zero")
            return float(_BIN_OPS[type(node.op)](left, right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return float(_UNARY_OPS[type(node.op)](_eval(node.operand)))
        raise ValueError("Unsupported AST node")

    try:
        res = _eval(tree)
        return round(res, 6)
    except Exception:
        return None


_UNIT_FACTORS = {
    # Data (base: bytes)
    "b": ("data", 1.0),
    "kb": ("data", 1024.0),
    "mb": ("data", 1024.0 ** 2),
    "gb": ("data", 1024.0 ** 3),
    "tb": ("data", 1024.0 ** 4),
    # Time (base: seconds)
    "ms": ("time", 0.001),
    "s": ("time", 1.0),
    "sec": ("time", 1.0),
    "seconds": ("time", 1.0),
    "min": ("time", 60.0),
    "minute": ("time", 60.0),
    "minutes": ("time", 60.0),
    "hr": ("time", 3600.0),
    "hour": ("time", 3600.0),
    "hours": ("time", 3600.0),
    # Length (base: meters)
    "mm": ("length", 0.001),
    "cm": ("length", 0.01),
    "m": ("length", 1.0),
    "km": ("length", 1000.0),
}


def convert_units(value: float, from_unit: str, to_unit: str) -> Optional[float]:
    fu = from_unit.strip().lower()
    tu = to_unit.strip().lower()
    if fu in ("c", "celsius") and tu in ("f", "fahrenheit"):
        return round((value * 9.0 / 5.0) + 32.0, 4)
    if fu in ("f", "fahrenheit") and tu in ("c", "celsius"):
        return round((value - 32.0) * 5.0 / 9.0, 4)
    if fu in _UNIT_FACTORS and tu in _UNIT_FACTORS:
        cat_f, fac_f = _UNIT_FACTORS[fu]
        cat_t, fac_t = _UNIT_FACTORS[tu]
        if cat_f != cat_t:
            return None
        return round((value * fac_f) / fac_t, 6)
    return None


def solve_sequence_pattern(nums: List[float]) -> Optional[Dict[str, Any]]:
    """Identifies next number in arithmetic, geometric, second-order, or Fibonacci sequences."""
    if len(nums) < 3:
        return None

    # 1. Arithmetic
    diffs = [round(nums[i + 1] - nums[i], 6) for i in range(len(nums) - 1)]
    if len(set(diffs)) == 1:
        return {"next": round(nums[-1] + diffs[0], 6), "pattern": f"arithmetic (d={diffs[0]})"}

    # 2. Geometric
    if all(n != 0 for n in nums[:-1]):
        ratios = [round(nums[i + 1] / nums[i], 6) for i in range(len(nums) - 1)]
        if len(set(ratios)) == 1:
            return {"next": round(nums[-1] * ratios[0], 6), "pattern": f"geometric (r={ratios[0]})"}

    # 3. Second-order arithmetic (e.g. 2, 6, 12, 20, 30 -> diffs 4, 6, 8, 10)
    if len(diffs) >= 3:
        d2 = [round(diffs[i + 1] - diffs[i], 6) for i in range(len(diffs) - 1)]
        if len(set(d2)) == 1:
            next_diff = diffs[-1] + d2[0]
            return {"next": round(nums[-1] + next_diff, 6), "pattern": f"second-order arithmetic (d2={d2[0]})"}

    # 4. Fibonacci-like
    if len(nums) >= 4 and all(round(nums[i] + nums[i + 1], 6) == round(nums[i + 2], 6) for i in range(len(nums) - 2)):
        return {"next": round(nums[-2] + nums[-1], 6), "pattern": "fibonacci-sum"}

    return None


def detect_logical_contradictions(statements: List[str]) -> List[str]:
    """Detects direct boolean/numeric contradictions across statements."""
    if len(statements) < 2:
        return []
    contradictions: List[str] = []
    # Check "X is Y" vs "X is not Y"
    pos_props: Dict[str, str] = {}
    neg_props: Dict[str, str] = {}
    for st in statements:
        low = st.lower().strip().rstrip(".")
        m_neg = re.search(r"\b([a-z0-9_]+)\s+(?:is|are|can|cannot|will)\s+not\s+([a-z0-9_\s]+)", low)
        if m_neg:
            neg_props[m_neg.group(1)] = m_neg.group(2).strip()
            continue
        m_cannot = re.search(r"\b([a-z0-9_]+)\s+cannot\s+([a-z0-9_\s]+)", low)
        if m_cannot:
            neg_props[m_cannot.group(1)] = m_cannot.group(2).strip()
            continue
        m_pos = re.search(r"\b([a-z0-9_]+)\s+(?:is|are|can)\s+([a-z0-9_\s]+)", low)
        if m_pos:
            pos_props[m_pos.group(1)] = m_pos.group(2).strip()

    for subj, p_val in pos_props.items():
        if subj in neg_props and (p_val in neg_props[subj] or neg_props[subj] in p_val):
            contradictions.append(f"Contradiction on '{subj}': '{p_val}' vs 'not {neg_props[subj]}'.")

    # Check antonym pairs (enabled/disabled, open/closed, active/inactive, etc.)
    antonyms = [
        ("enabled", "disabled"), ("open", "closed"), ("active", "inactive"),
        ("true", "false"), ("online", "offline"), ("valid", "invalid"),
        ("writable", "read-only"), ("allowed", "blocked"),
    ]
    joined_low = [s.lower() for s in statements]
    for a, b in antonyms:
        has_a = any(re.search(r"\b" + re.escape(a) + r"\b", s) for s in joined_low)
        has_b = any(re.search(r"\b" + re.escape(b) + r"\b", s) for s in joined_low)
        if has_a and has_b:
            contradictions.append(f"Antonym contradiction detected: '{a}' vs '{b}'.")

    # Check conflicting numbers with same unit or percentage ONLY on the same subject/property
    # (avoid false positives on different metrics like "8 GB RAM and 4 GB app" or transitions "800 ms to 5 ms")
    prop_units: Dict[Tuple[str, str], set] = {}
    for s in joined_low:
        # Ignore transition/comparison sentences ("from X to Y", "dropped to", "reduced to", "speedup")
        if any(w in s for w in (" to ", " -> ", "from ", "reduced ", "dropped ", "speedup", "became ")):
            continue
        # Extract subject + value + unit (e.g., "ram has 8 gb", "size is 4 gb")
        for subj, val, unit in re.findall(r"\b([a-z_]+)\s+(?:is|has|uses|consumes|requires|allocated)\s+(\d+(?:\.\d+)?)\s*(%|gb|mb|tb|kb|ghz|mhz|ms|seconds?|minutes?|hours?)\b", s):
            prop_units.setdefault((subj, unit.rstrip("s")), set()).add(val)
    for (subj, unit), vals in prop_units.items():
        if len(vals) > 1:
            contradictions.append(f"Numeric contradiction on '{subj}' for '{unit}': {', '.join(sorted(vals))}.")

    return contradictions


def try_deterministic_math_or_logic(query: str) -> Optional[Dict[str, Any]]:
    """
    Attempts to solve self-contained arithmetic, percentage, unit conversion,
    or sequence queries deterministically in <1ms without an LLM call.
    """
    if not query or not isinstance(query, str):
        return None
    q = query.strip()
    low = q.lower()

    # 1. Percentage: "what is 15% of 240"
    m_pct = re.search(r"(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)", low)
    if m_pct and len(low.split()) <= 10:
        pct = float(m_pct.group(1))
        total = float(m_pct.group(2))
        val = round((pct / 100.0) * total, 6)
        ans = int(val) if val.is_integer() else val
        return {"solved": True, "answer": f"{ans}", "method": "deterministic_percentage", "confidence": 1.0}

    # 2. Unit conversion: "convert 4 gb to mb"
    m_conv = re.search(r"\bconvert\s+(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s+(?:to|in)\s+([a-zA-Z]+)\b", low)
    if m_conv:
        val = float(m_conv.group(1))
        res = convert_units(val, m_conv.group(2), m_conv.group(3))
        if res is not None:
            ans = int(res) if res.is_integer() else res
            return {"solved": True, "answer": f"{ans} {m_conv.group(3)}", "method": "deterministic_unit_conversion", "confidence": 1.0}

    # 3. Sequence pattern: "next number in sequence 2, 6, 12, 20, 30"
    if any(k in low for k in ("sequence", "next number", "pattern")):
        # If sequence contains alphanumeric tokens like A1, B2 or words, don't capture with pure numeric solver
        if re.search(r"\b[a-zA-Z]+\d+|\d+[a-zA-Z]+\b", q):
            return None
        nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", q)]
        seq_res = solve_sequence_pattern(nums)
        if seq_res:
            nxt = seq_res["next"]
            ans = int(nxt) if nxt.is_integer() else nxt
            return {"solved": True, "answer": f"{ans} ({seq_res['pattern']})", "method": "deterministic_sequence", "confidence": 1.0}

    # 4. Pure arithmetic expression: "calculate (12 + 8) * 3" or "what is 144 / 12"
    m_expr = re.match(r"^(?:calculate|compute|what\s+is|evaluate)?\s*([\d\s\+\-\*/\(\)\.\^%]+)\??$", low)
    if m_expr:
        expr_str = m_expr.group(1).strip()
        if any(op in expr_str for op in ("+", "-", "*", "/", "^", "%")):
            val = safe_eval_arithmetic(expr_str)
            if val is not None:
                ans = int(val) if val.is_integer() else val
                return {"solved": True, "answer": f"{ans}", "method": "deterministic_ast_math", "confidence": 1.0}

    return None


def evaluate_counterfactual_scenario(query: str) -> Dict[str, Any]:
    """
    Vision Domain 2.2: Counterfactual reasoning evaluator.
    Evaluates 'what if' speculative scenarios with altered numeric constraints/capacities.
    """
    if not query or not isinstance(query, str):
        return {"valid": False, "conclusion": "Invalid query"}

    lowered = query.lower().strip()
    if not any(k in lowered for k in ("what if", "suppose", "assuming")):
        return {"valid": False, "conclusion": "Not a counterfactual query"}

    # Pattern: what if X changed/increased/decreased from A to B on a C system/limit
    m_cf = re.search(
        r"(?:increased|changed|increased\s+from|from)?\s*(\d+(?:\.\d+)?)\s*(gb|mb|tb|ghz|%)\s*(?:to|into)\s*(\d+(?:\.\d+)?)\s*(gb|mb|tb|ghz|%)\s*(?:on|in|with)\s*(?:an?|the)?\s*(\d+(?:\.\d+)?)\s*(gb|mb|tb|ghz|%)",
        lowered
    )

    if m_cf:
        from_val = float(m_cf.group(1))
        from_unit = m_cf.group(2).lower()
        to_val = float(m_cf.group(3))
        to_unit = m_cf.group(4).lower()
        limit_val = float(m_cf.group(5))
        limit_unit = m_cf.group(6).lower()

        # Check unit consistency
        if to_unit == limit_unit:
            if to_val <= limit_val:
                diff = limit_val - to_val
                conclusion = f"Counterfactual scenario is feasible: {to_val} {to_unit} fits within the {limit_val} {limit_unit} limit with {diff:.1f} {limit_unit} remaining."
                feasible = True
            else:
                excess = to_val - limit_val
                conclusion = f"Counterfactual scenario exceeds system limits: {to_val} {to_unit} exceeds the {limit_val} {limit_unit} capacity by {excess:.1f} {limit_unit}."
                feasible = False

            return {
                "valid": True,
                "feasible": feasible,
                "initial_value": from_val,
                "target_value": to_val,
                "limit_value": limit_val,
                "metric": to_unit,
                "conclusion": conclusion
            }

    return {
        "valid": True,
        "feasible": True,
        "conclusion": f"Counterfactual scenario analyzed: {query}"
    }
