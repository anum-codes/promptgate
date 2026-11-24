"""End-to-end provider tests against a local fake HTTP server (no real API calls)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from promptgate.cli import main
from promptgate.providers import ProviderError, build_provider

CALLS = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        CALLS.append((self.path, {k.lower(): v for k, v in self.headers.items()}, body))
        if self.path.startswith("/nope"):
            self.send_response(404); self.end_headers(); return
        if self.path.endswith("/v1/messages"):
            payload = {"content": [{"type": "text", "text": "anthropic says hi"}]}
        elif self.path.endswith("/chat/completions"):
            payload = {"choices": [{"message": {"content": "openai says hi"}}]}
        else:
            self.send_response(404); self.end_headers(); return
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture(scope="module")
def server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_anthropic_request_shape(server, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k-test")
    CALLS.clear()
    p = build_provider({"type": "anthropic", "model": "m", "base_url": server, "system": "sys"})
    assert p.complete("hello") == "anthropic says hi"
    path, headers, body = CALLS[0]
    assert path == "/v1/messages"
    assert headers["x-api-key"] == "k-test"
    assert headers["anthropic-version"] == "2023-06-01"
    assert body["messages"] == [{"role": "user", "content": "hello"}]
    assert body["system"] == "sys" and body["model"] == "m"


def test_openai_request_shape(server, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "o-test")
    CALLS.clear()
    p = build_provider({"type": "openai", "model": "m", "base_url": server + "/v1", "system": "s"})
    assert p.complete("hello") == "openai says hi"
    path, headers, body = CALLS[0]
    assert path == "/v1/chat/completions"
    assert headers["authorization"] == "Bearer o-test"
    assert body["messages"][0] == {"role": "system", "content": "s"}


def test_missing_key_and_bad_config(server, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
        build_provider({"type": "anthropic", "model": "m", "base_url": server})
    with pytest.raises(ProviderError):
        build_provider({"type": "anthropic"})
    with pytest.raises(ProviderError):
        build_provider({"type": "bogus"})


def test_http_error_is_reported(server, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    p = build_provider({"type": "anthropic", "model": "m", "base_url": server + "/nope"})
    with pytest.raises(ProviderError, match="404"):
        p.complete("x")


def test_full_cli_run_with_judge(server, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    suite = tmp_path / "s.yaml"
    suite.write_text(f"""
provider: {{type: anthropic, model: m, base_url: "{server}"}}
judge: {{type: mock, reply: "PASS looks right"}}
prompt: "Say {{{{w}}}}"
cases:
  - name: e2e
    vars: {{w: hi}}
    assert:
      - {{type: contains, value: anthropic}}
      - {{type: llm_judge, value: anything}}
""")
    assert main(["run", str(suite)]) == 0
    assert "1/1 passed" in capsys.readouterr().out
