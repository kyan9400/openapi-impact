from __future__ import annotations

import json

from openapi_impact.models import ComparisonResult, Severity
from openapi_impact.report import (
    render_github_annotations,
    render_json,
    render_markdown,
    render_sarif,
    render_text,
)


def sample_result() -> ComparisonResult:
    result = ComparisonResult()
    result.add("path.removed", Severity.BREAKING, "paths./users", "Path '/users' was removed.")
    result.add("path.added", Severity.NON_BREAKING, "paths./teams", "Path '/teams' was added.")
    result.sort()
    return result


def test_text_report_has_summary_and_labels() -> None:
    report = render_text(sample_result())

    assert "1 breaking · 1 non-breaking" in report
    assert "[BREAKING] path.removed" in report
    assert "[SAFE] path.added" in report


def test_markdown_report_is_table_based() -> None:
    report = render_markdown(sample_result())

    assert "**Breaking changes found.**" in report
    assert "| Impact | Rule | Location | Change |" in report


def test_json_report_is_machine_readable() -> None:
    report = json.loads(render_json(sample_result()))

    assert report["summary"] == {"breaking": 1, "non_breaking": 1, "total": 2}
    assert report["changes"][0]["severity"] == "breaking"


def test_github_annotations_escape_workflow_commands() -> None:
    result = ComparisonResult()
    result.add("unsafe%title", Severity.BREAKING, "paths./users", "line one\nline two")

    annotation = render_github_annotations(result.changes)

    assert annotation == "::error title=unsafe%25title::paths./users: line one%0Aline two"


def test_sarif_report_contains_rules_and_logical_locations() -> None:
    report = json.loads(render_sarif(sample_result()))

    assert report["version"] == "2.1.0"
    run = report["runs"][0]
    assert {rule["id"] for rule in run["tool"]["driver"]["rules"]} == {
        "path.added",
        "path.removed",
    }
    assert run["results"][0]["level"] == "error"
    assert (
        run["results"][0]["locations"][0]["logicalLocations"][0]["fullyQualifiedName"]
        == "paths./users"
    )
