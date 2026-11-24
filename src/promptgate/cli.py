"""Command-line interface."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .config import ConfigError, load_suite
from .providers import ProviderError, build_provider
from .report import format_text, summarize, to_json, use_color
from .runner import run_suite

TEMPLATE = """\
# promptgate suite. Run with: promptgate run suite.yaml
provider:
  type: anthropic            # anthropic | openai | mock
  model: claude-sonnet-5-5
  max_tokens: 300
  # api_key_env: ANTHROPIC_API_KEY

prompt: "Reply with a JSON object with keys 'sentiment' and 'confidence' for: {{text}}"

cases:
  - name: positive review
    vars: { text: "I absolutely love this product!" }
    assert:
      - { type: json_valid }
      - { type: json_field, path: sentiment, value: positive }
      - { type: max_latency_ms, value: 10000 }
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="promptgate",
                                description="Regression tests for prompts.")
    p.add_argument("--version", action="version", version=f"promptgate {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a test suite")
    run.add_argument("suite", help="path to a YAML suite")
    run.add_argument("-w", "--workers", type=int, default=4, help="parallel requests (default 4)")
    run.add_argument("--json", metavar="FILE", help="also write a JSON report")
    run.add_argument("--model", help="override the provider model")
    run.add_argument("--fail-under", type=float, default=1.0, metavar="RATE",
                     help="minimum pass rate 0-1 for exit code 0 (default 1.0)")

    init = sub.add_parser("init", help="write a starter suite")
    init.add_argument("path", nargs="?", default="suite.yaml")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "init":
        path = Path(args.path)
        if path.exists():
            print(f"error: {path} already exists", file=sys.stderr)
            return 2
        path.write_text(TEMPLATE, encoding="utf-8")
        print(f"wrote {path}")
        return 0

    try:
        suite = load_suite(args.suite)
        if args.model:
            suite.provider["model"] = args.model
        provider = build_provider(suite.provider)
        judge = build_provider(suite.judge) if suite.judge else None
    except (ConfigError, ProviderError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    results = run_suite(suite, provider, judge=judge, workers=args.workers)
    print(format_text(results, color=use_color()))
    if args.json:
        Path(args.json).write_text(to_json(results), encoding="utf-8")
    return 0 if summarize(results)["pass_rate"] >= args.fail_under else 1


if __name__ == "__main__":
    sys.exit(main())
