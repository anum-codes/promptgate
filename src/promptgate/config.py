"""Loading and validating test suites."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml


class ConfigError(Exception):
    """Raised when a suite file is invalid."""


@dataclass
class Case:
    name: str
    vars: Dict[str, Any] = field(default_factory=dict)
    asserts: List[Dict[str, Any]] = field(default_factory=list)
    prompt: Optional[str] = None  # overrides suite-level prompt


@dataclass
class Suite:
    provider: Dict[str, Any]
    prompt: Optional[str]
    cases: List[Case]
    judge: Optional[Dict[str, Any]] = None


_VAR = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render(template: str, variables: Dict[str, Any]) -> str:
    """Replace {{var}} placeholders. Missing variables raise ConfigError."""

    def sub(m: "re.Match[str]") -> str:
        key = m.group(1)
        if key not in variables:
            raise ConfigError(f"template uses undefined variable '{key}'")
        return str(variables[key])

    return _VAR.sub(sub, template)


def parse_suite(data: Any) -> Suite:
    if not isinstance(data, dict):
        raise ConfigError("suite must be a YAML mapping")
    provider = data.get("provider")
    if not isinstance(provider, dict) or "type" not in provider:
        raise ConfigError("'provider' with a 'type' is required")
    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ConfigError("'cases' must be a non-empty list")

    prompt = data.get("prompt")
    cases: List[Case] = []
    for i, raw in enumerate(raw_cases):
        if not isinstance(raw, dict):
            raise ConfigError(f"case #{i + 1} must be a mapping")
        case = Case(
            name=str(raw.get("name", f"case-{i + 1}")),
            vars=raw.get("vars") or {},
            asserts=raw.get("assert") or [],
            prompt=raw.get("prompt"),
        )
        if case.prompt is None and prompt is None:
            raise ConfigError(f"case '{case.name}' has no prompt and the suite defines none")
        for a in case.asserts:
            if not isinstance(a, dict) or "type" not in a:
                raise ConfigError(f"case '{case.name}': each assertion needs a 'type'")
        cases.append(case)
    return Suite(provider=provider, prompt=prompt, cases=cases, judge=data.get("judge"))


def load_suite(path: str) -> Suite:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except OSError as e:
        raise ConfigError(f"cannot read {path}: {e}") from e
    except yaml.YAMLError as e:
        raise ConfigError(f"invalid YAML in {path}: {e}") from e
    return parse_suite(data)
