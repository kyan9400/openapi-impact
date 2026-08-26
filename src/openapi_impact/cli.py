"""Command-line entry point."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .compare import compare_specs
from .loader import SpecError, load_spec
from .report import render, render_github_annotations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openapi-impact",
        description="Detect breaking changes between two OpenAPI 3.x specifications.",
    )
    parser.add_argument("base", help="Previous OpenAPI JSON or YAML document")
    parser.add_argument("head", help="New OpenAPI JSON or YAML document")
    parser.add_argument(
        "--format",
        choices=("text", "markdown", "json"),
        default="text",
        dest="format_name",
        help="Report format (default: text)",
    )
    parser.add_argument("--output", type=Path, help="Write the report to a file")
    parser.add_argument(
        "--fail-on",
        choices=("breaking", "never"),
        default="breaking",
        help="Exit with status 1 when breaking changes exist (default: breaking)",
    )
    parser.add_argument(
        "--github-annotations",
        action="store_true",
        help="Emit GitHub Actions error and notice annotations",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def run(arguments: Sequence[str] | None = None) -> int:
    parser = build_parser()
    options = parser.parse_args(arguments)

    try:
        base = load_spec(options.base)
        head = load_spec(options.head)
    except SpecError as error:
        print(f"openapi-impact: {error}", file=sys.stderr)
        return 2

    result = compare_specs(base, head)
    report = render(result, options.format_name)

    if options.output:
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(f"{report}\n", encoding="utf-8")
    else:
        print(report)

    if options.github_annotations or os.getenv("GITHUB_ACTIONS") == "true":
        annotations = render_github_annotations(result.changes)
        if annotations:
            print(annotations, file=sys.stderr)

    if options.fail_on == "breaking" and result.has_breaking_changes:
        return 1
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
