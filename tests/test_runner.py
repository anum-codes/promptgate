import json

import pytest

from promptgate.cli import main
from promptgate.config import ConfigError, parse_suite, render
from promptgate.providers import MockProvider
from promptgate.runner import run_suite


def make_suite(cases, provider=None):
    return parse_suite({"provider": provider or {"type": "mock", "reply": "hello"},
                        "prompt": "Say {{word}}", "cases": cases})


def test_render_and_missing_var():
    assert render("a {{ x }} b", {"x": 1}) == "a 1 b"
    with pytest.raises(ConfigError):
        render("{{y}}", {})


def test_run_suite_pass_and_fail():
    suite = make_suite([
        {"name": "good", "vars": {"word": "hi"}, "assert": [{"type": "contains", "value": "hello"}]},
        {"name": "bad", "vars": {"word": "hi"}, "assert": [{"type": "contains", "value": "zzz"}]},
    ])
    results = run_suite(suite, MockProvider({"reply": "hello"}))
    assert [r.name for r in results] == ["good", "bad"]
    assert results[0].passed and not results[1].passed


def test_provider_exception_is_captured():
    class Boom:
        def complete(self, prompt):
            raise RuntimeError("down")

    results = run_suite(make_suite([{"vars": {"word": "x"}}]), Boom())
    assert results[0].error and "down" in results[0].error and not results[0].passed


def test_invalid_suites():
    with pytest.raises(ConfigError):
        parse_suite({"cases": [{}]})
    with pytest.raises(ConfigError):
        parse_suite({"provider": {"type": "mock"}, "cases": []})
    with pytest.raises(ConfigError):
        parse_suite({"provider": {"type": "mock"}, "cases": [{"name": "n"}]})


def test_cli_exit_codes_and_json(tmp_path, capsys):
    out = tmp_path / "r.json"
    assert main(["run", "examples/offline.yaml", "--json", str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["summary"]["passed"] == 1

    failing = tmp_path / "f.yaml"
    failing.write_text(
        "provider: {type: mock, reply: nope}\nprompt: p\n"
        "cases:\n  - name: c\n    assert:\n      - {type: contains, value: yes}\n")
    assert main(["run", str(failing)]) == 1
    assert main(["run", str(failing), "--fail-under", "0"]) == 0
    assert main(["run", str(tmp_path / "missing.yaml")]) == 2


def test_cli_init(tmp_path):
    p = tmp_path / "s.yaml"
    assert main(["init", str(p)]) == 0
    assert main(["init", str(p)]) == 2  # refuses to overwrite


def test_missing_api_key_exits_2_before_running(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    p = tmp_path / "s.yaml"
    p.write_text("provider: {type: anthropic, model: m}\nprompt: p\ncases:\n  - name: c\n")
    assert main(["run", str(p)]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
