"""Stable text, Markdown, and JSON report formats."""

from __future__ import annotations

import json

from .models import Change, ComparisonResult, Severity


def _display_value(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def render_text(result: ComparisonResult) -> str:
    lines = [
        "OpenAPI Impact",
        f"{len(result.breaking_changes)} breaking · "
        f"{len(result.non_breaking_changes)} non-breaking",
        "",
    ]
    if not result.changes:
        lines.append("No contract changes detected.")
        return "\n".join(lines)

    for change in result.changes:
        label = "BREAKING" if change.severity is Severity.BREAKING else "SAFE"
        lines.append(f"[{label}] {change.code} · {change.location}")
        lines.append(f"  {change.message}")
    return "\n".join(lines)


def _escape_cell(value: object) -> str:
    return _display_value(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(result: ComparisonResult) -> str:
    verdict = "Breaking changes found" if result.has_breaking_changes else "Compatible change set"
    lines = [
        "# OpenAPI impact report",
        "",
        f"**{verdict}.** {len(result.breaking_changes)} breaking and "
        f"{len(result.non_breaking_changes)} non-breaking changes.",
        "",
    ]
    if not result.changes:
        lines.append("No contract changes detected.")
        return "\n".join(lines)

    lines.extend(
        [
            "| Impact | Rule | Location | Change |",
            "| --- | --- | --- | --- |",
        ]
    )
    for change in result.changes:
        impact = "Breaking" if change.severity is Severity.BREAKING else "Non-breaking"
        lines.append(
            f"| {impact} | `{_escape_cell(change.code)}` | "
            f"`{_escape_cell(change.location)}` | {_escape_cell(change.message)} |"
        )
    return "\n".join(lines)


def render_json(result: ComparisonResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=False)


def render(result: ComparisonResult, format_name: str) -> str:
    renderers = {"text": render_text, "markdown": render_markdown, "json": render_json}
    return renderers[format_name](result)


def render_github_annotations(changes: list[Change]) -> str:
    """Render workflow commands without accepting untrusted line breaks."""

    lines: list[str] = []
    for change in changes:
        message = change.message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        title = change.code.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        level = "error" if change.severity is Severity.BREAKING else "notice"
        lines.append(f"::{level} title={title}::{change.location}: {message}")
    return "\n".join(lines)
