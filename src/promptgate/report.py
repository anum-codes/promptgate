"""Terminal and JSON reporting."""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

from .runner import CaseResult


def summarize(results: List[CaseResult]) -> Dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": (passed / total) if total else 0.0,
        "avg_latency_ms": (sum(r.latency_ms for r in results) / total) if total else 0.0,
    }


def format_text(results: List[CaseResult], color: bool = False) -> str:
    g, r_, d, x = ("\033[32m", "\033[31m", "\033[2m", "\033[0m") if color else ("", "", "", "")
    lines: List[str] = []
    for res in results:
        mark = f"{g}PASS{x}" if res.passed else f"{r_}FAIL{x}"
        lines.append(f"{mark}  {res.name} {d}({res.latency_ms:.0f}ms){x}")
        if res.error:
            lines.append(f"      {r_}error:{x} {res.error}")
        for a in res.assertions:
            if not a.passed:
                lines.append(f"      {r_}x{x} {a.type}: {a.message}")
        if not res.passed and res.output:
            snippet = res.output.strip().replace("\n", " ")[:200]
            lines.append(f"      {d}output: {snippet}{x}")
    s = summarize(results)
    lines.append("")
    lines.append(f"{s['passed']}/{s['total']} passed ({s['pass_rate']:.0%}), "
                 f"avg latency {s['avg_latency_ms']:.0f}ms")
    return "\n".join(lines)


def to_json(results: List[CaseResult]) -> str:
    payload = {
        "summary": summarize(results),
        "cases": [
            {
                "name": r.name, "passed": r.passed, "error": r.error,
                "latency_ms": round(r.latency_ms, 1), "prompt": r.prompt, "output": r.output,
                "assertions": [a.__dict__ for a in r.assertions],
            }
            for r in results
        ],
    }
    return json.dumps(payload, indent=2)


def use_color() -> bool:
    return sys.stdout.isatty()
