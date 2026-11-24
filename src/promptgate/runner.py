"""Execute a suite against a provider."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import List, Optional

from .assertions import Context, run_assertion
from .config import Case, ConfigError, Suite, render
from .providers import Provider


@dataclass
class AssertionResult:
    type: str
    passed: bool
    message: str


@dataclass
class CaseResult:
    name: str
    prompt: str = ""
    output: str = ""
    latency_ms: float = 0.0
    error: Optional[str] = None
    assertions: List[AssertionResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.error is None and all(a.passed for a in self.assertions)


def _run_case(case: Case, suite: Suite, provider: Provider,
              judge: Optional[Provider]) -> CaseResult:
    res = CaseResult(name=case.name)
    try:
        res.prompt = render(case.prompt or suite.prompt or "", case.vars)
    except ConfigError as e:
        res.error = str(e)
        return res
    start = time.perf_counter()
    try:
        res.output = provider.complete(res.prompt)
    except Exception as e:
        res.error = f"provider error: {e}"
        return res
    res.latency_ms = (time.perf_counter() - start) * 1000
    ctx = Context(latency_ms=res.latency_ms, judge=judge)
    for spec in case.asserts:
        ok, msg = run_assertion(res.output, spec, ctx)
        res.assertions.append(AssertionResult(spec["type"], ok, "" if ok else msg))
    return res


def run_suite(suite: Suite, provider: Provider, judge: Optional[Provider] = None,
              workers: int = 4) -> List[CaseResult]:
    judge = judge or provider
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(_run_case, c, suite, provider, judge) for c in suite.cases]
        return [f.result() for f in futures]  # preserves case order
