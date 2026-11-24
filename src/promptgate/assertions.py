"""Assertion registry. Each check returns (passed, message)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from .providers import Provider

Result = Tuple[bool, str]


@dataclass
class Context:
    latency_ms: float = 0.0
    judge: Optional[Provider] = None


def _strip_fences(text: str) -> str:
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*\n(.*?)\n```$", t, re.DOTALL)
    return m.group(1) if m else t


def _get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            cur = cur[part]
        else:
            raise KeyError(part)
    return cur


def _contains(out: str, a: Dict[str, Any], ctx: Context) -> Result:
    v = str(a["value"])
    return v in out, f"expected output to contain {v!r}"


def _icontains(out: str, a: Dict[str, Any], ctx: Context) -> Result:
    v = str(a["value"])
    return v.lower() in out.lower(), f"expected output to contain {v!r} (case-insensitive)"


def _not_contains(out: str, a: Dict[str, Any], ctx: Context) -> Result:
    v = str(a["value"])
    return v.lower() not in out.lower(), f"expected output NOT to contain {v!r}"


def _equals(out: str, a: Dict[str, Any], ctx: Context) -> Result:
    v = str(a["value"])
    return out.strip() == v.strip(), f"expected output to equal {v!r}"


def _starts_with(out: str, a: Dict[str, Any], ctx: Context) -> Result:
    v = str(a["value"])
    return out.lstrip().startswith(v), f"expected output to start with {v!r}"


def _regex(out: str, a: Dict[str, Any], ctx: Context) -> Result:
    flags = re.IGNORECASE if a.get("ignore_case") else 0
    pat = str(a["value"])
    return re.search(pat, out, flags | re.DOTALL) is not None, f"expected output to match /{pat}/"


def _json_valid(out: str, a: Dict[str, Any], ctx: Context) -> Result:
    try:
        json.loads(_strip_fences(out))
        return True, ""
    except ValueError as e:
        return False, f"output is not valid JSON ({e})"


def _json_field(out: str, a: Dict[str, Any], ctx: Context) -> Result:
    path = str(a["path"])
    try:
        data = json.loads(_strip_fences(out))
    except ValueError as e:
        return False, f"output is not valid JSON ({e})"
    try:
        found = _get_path(data, path)
    except (KeyError, IndexError, ValueError):
        return False, f"JSON path '{path}' not found"
    if "value" in a and found != a["value"]:
        return False, f"JSON path '{path}' is {found!r}, expected {a['value']!r}"
    return True, ""


def _max_chars(out: str, a: Dict[str, Any], ctx: Context) -> Result:
    n = int(a["value"])
    return len(out) <= n, f"output is {len(out)} chars, max {n}"


def _min_chars(out: str, a: Dict[str, Any], ctx: Context) -> Result:
    n = int(a["value"])
    return len(out) >= n, f"output is {len(out)} chars, min {n}"


def _max_latency_ms(out: str, a: Dict[str, Any], ctx: Context) -> Result:
    n = float(a["value"])
    return ctx.latency_ms <= n, f"latency {ctx.latency_ms:.0f}ms exceeded {n:.0f}ms"


def _llm_judge(out: str, a: Dict[str, Any], ctx: Context) -> Result:
    if ctx.judge is None:
        return False, "llm_judge needs a provider (set 'judge:' or use a real provider)"
    criteria = str(a["value"])
    prompt = (
        "You are a strict evaluator. Decide whether the OUTPUT satisfies the CRITERIA.\n"
        f"CRITERIA: {criteria}\n\nOUTPUT:\n{out}\n\n"
        "Reply with PASS or FAIL on the first line, then a one-sentence reason."
    )
    verdict = ctx.judge.complete(prompt).strip()
    first = verdict.split(None, 1)[0].upper().strip(".:,") if verdict else ""
    return first == "PASS", f"judge said: {verdict[:160]}"


REGISTRY: Dict[str, Callable[[str, Dict[str, Any], Context], Result]] = {
    "contains": _contains,
    "icontains": _icontains,
    "not_contains": _not_contains,
    "equals": _equals,
    "starts_with": _starts_with,
    "regex": _regex,
    "json_valid": _json_valid,
    "json_field": _json_field,
    "max_chars": _max_chars,
    "min_chars": _min_chars,
    "max_latency_ms": _max_latency_ms,
    "llm_judge": _llm_judge,
}


def run_assertion(output: str, spec: Dict[str, Any], ctx: Context) -> Result:
    kind = spec["type"]
    fn = REGISTRY.get(kind)
    if fn is None:
        return False, f"unknown assertion type '{kind}'"
    try:
        return fn(output, spec, ctx)
    except KeyError as e:
        return False, f"assertion '{kind}' is missing field {e}"
    except Exception as e:  # keep one bad assertion from crashing the run
        return False, f"assertion '{kind}' errored: {e}"
