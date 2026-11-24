# promptgate

[![CI](https://github.com/anum-codes/promptgate/actions/workflows/ci.yml/badge.svg)](https://github.com/anum-codes/promptgate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Regression tests for prompts.** Define test cases in YAML, run them against any LLM, and fail your CI when a prompt change breaks behavior.

Changing a prompt without tests is how quality quietly drops. `promptgate` gives you a tiny, dependency-light harness (just PyYAML) so prompt changes get the same review as code changes.

## Features

- **YAML test suites** with `{{variable}}` templating
- **12 built-in assertions**: `contains`, `icontains`, `not_contains`, `equals`, `starts_with`, `regex`, `json_valid`, `json_field`, `max_chars`, `min_chars`, `max_latency_ms`, `llm_judge`
- **Providers**: Anthropic, any OpenAI-compatible endpoint (OpenAI, vLLM, Ollama, LiteLLM...), and an offline `mock` for CI
- **Parallel execution**, retries on 429/5xx, JSON reports
- **CI-friendly exit codes** with a configurable `--fail-under` pass rate
- No SDKs: providers use plain HTTPS via the standard library

## Install

```bash
pip install git+https://github.com/anum-codes/promptgate.git
# or, from a clone:
pip install -e ".[dev]"
```

## Quick start

```bash
promptgate init suite.yaml          # write a starter suite
export ANTHROPIC_API_KEY=...
promptgate run suite.yaml
```

No API key? Try the offline example:

```bash
promptgate run examples/offline.yaml
```

## Suite format

```yaml
provider:
  type: anthropic              # anthropic | openai | mock
  model: claude-sonnet-5-5
  max_tokens: 300
  temperature: 0
  # system: "You are a helpful assistant."
  # api_key_env: MY_KEY_VAR    # default: ANTHROPIC_API_KEY / OPENAI_API_KEY
  # base_url: http://localhost:8000/v1   # for OpenAI-compatible servers

judge:                          # optional; defaults to the main provider
  type: anthropic
  model: claude-sonnet-5-5

prompt: "Summarize in one sentence: {{text}}"

cases:
  - name: summary is short and on-topic
    vars:
      text: "Retrieval-augmented generation grounds answers in fetched documents."
    assert:
      - { type: icontains, value: retrieval }
      - { type: max_chars, value: 300 }
      - { type: llm_judge, value: "A single, accurate one-sentence summary." }
```

A case can override the suite-level `prompt` with its own.

### Assertions

| type | fields | passes when |
|---|---|---|
| `contains` / `icontains` | `value` | output contains the string (exact / case-insensitive) |
| `not_contains` | `value` | output lacks the string (case-insensitive) |
| `equals` | `value` | trimmed output equals the value |
| `starts_with` | `value` | output starts with the value |
| `regex` | `value`, `ignore_case?` | regex matches anywhere |
| `json_valid` | | output parses as JSON (code fences are stripped) |
| `json_field` | `path`, `value?` | dotted path exists (and equals `value` if given) |
| `max_chars` / `min_chars` | `value` | length bound |
| `max_latency_ms` | `value` | request took at most N ms |
| `llm_judge` | `value` (criteria) | judge model replies `PASS` |

## CLI

```
promptgate run SUITE [-w WORKERS] [--json FILE] [--model NAME] [--fail-under RATE]
promptgate init [PATH]
```

Exit codes: `0` pass rate met, `1` below `--fail-under`, `2` config/usage error.

## Use in CI

```yaml
- run: pip install git+https://github.com/anum-codes/promptgate.git
- run: promptgate run prompts/suite.yaml --fail-under 0.9 --json results.json
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

Use `--fail-under` below 1.0 to tolerate flakiness on non-deterministic prompts.

## Extending

Add an assertion by writing a function in `src/promptgate/assertions.py` and registering it in `REGISTRY`. Add a provider by implementing `complete(prompt) -> str` and adding it to `build_provider` in `providers.py`.

## Roadmap ideas

- Multi-turn conversations and tool-call assertions
- Prompt A/B comparison across models with a diff report
- JUnit XML output
- Response caching to cut cost on unchanged cases

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Author

Built by [Anum Mughal](https://github.com/anum-codes). Issues and PRs welcome.

## License

MIT, see [LICENSE](LICENSE).
