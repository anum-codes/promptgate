"""Model providers. Stdlib only (urllib), so there are no SDK dependencies."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Protocol


class ProviderError(Exception):
    pass


class Provider(Protocol):
    def complete(self, prompt: str) -> str: ...


def _post_json(url: str, headers: Dict[str, str], body: Dict[str, Any],
               timeout: float = 60.0, retries: int = 2) -> Dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    last: Exception = ProviderError("request failed")
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/json", **headers},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            last = ProviderError(f"HTTP {e.code}: {detail}")
            if e.code not in (429, 500, 502, 503, 529):
                break
        except (urllib.error.URLError, TimeoutError) as e:
            last = ProviderError(f"network error: {e}")
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    raise last


def _key(cfg: Dict[str, Any], default_env: str) -> str:
    env = cfg.get("api_key_env", default_env)
    key = os.environ.get(env)
    if not key:
        raise ProviderError(f"environment variable {env} is not set")
    return key


class AnthropicProvider:
    def __init__(self, cfg: Dict[str, Any]):
        self.model = cfg.get("model")
        if not self.model:
            raise ProviderError("anthropic provider requires 'model'")
        self.max_tokens = int(cfg.get("max_tokens", 512))
        self.temperature = cfg.get("temperature", 0)
        self.system = cfg.get("system")
        self.base_url = cfg.get("base_url", "https://api.anthropic.com").rstrip("/")
        self._api_key = _key(cfg, "ANTHROPIC_API_KEY")  # fail fast if missing

    def complete(self, prompt: str) -> str:
        body: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.system:
            body["system"] = self.system
        out = _post_json(
            f"{self.base_url}/v1/messages",
            {"x-api-key": self._api_key,
             "anthropic-version": "2023-06-01"},
            body,
        )
        return "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")


class OpenAICompatProvider:
    """Works with OpenAI and any server exposing /chat/completions."""

    def __init__(self, cfg: Dict[str, Any]):
        self.model = cfg.get("model")
        if not self.model:
            raise ProviderError("openai provider requires 'model'")
        self.max_tokens = int(cfg.get("max_tokens", 512))
        self.temperature = cfg.get("temperature", 0)
        self.system = cfg.get("system")
        self.base_url = cfg.get("base_url", "https://api.openai.com/v1").rstrip("/")
        self._api_key = _key(cfg, "OPENAI_API_KEY")  # fail fast if missing

    def complete(self, prompt: str) -> str:
        messages = []
        if self.system:
            messages.append({"role": "system", "content": self.system})
        messages.append({"role": "user", "content": prompt})
        out = _post_json(
            f"{self.base_url}/chat/completions",
            {"Authorization": f"Bearer {self._api_key}"},
            {"model": self.model, "messages": messages,
             "max_tokens": self.max_tokens, "temperature": self.temperature},
        )
        try:
            return out["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError) as e:
            raise ProviderError(f"unexpected response shape: {out}") from e


class MockProvider:
    """Offline provider for demos and CI. Returns `reply`, or echoes the prompt."""

    def __init__(self, cfg: Dict[str, Any]):
        self.reply = cfg.get("reply")

    def complete(self, prompt: str) -> str:
        return self.reply if self.reply is not None else prompt


def build_provider(cfg: Dict[str, Any]) -> Provider:
    kind = str(cfg.get("type", "")).lower()
    if kind == "anthropic":
        return AnthropicProvider(cfg)
    if kind in ("openai", "openai-compatible"):
        return OpenAICompatProvider(cfg)
    if kind == "mock":
        return MockProvider(cfg)
    raise ProviderError(f"unknown provider type '{kind}' (use anthropic, openai, or mock)")
