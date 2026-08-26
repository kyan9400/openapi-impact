from __future__ import annotations

import json
from pathlib import Path

from openapi_impact.cli import run


def write_spec(path: Path, paths: dict[str, object]) -> None:
    path.write_text(
        json.dumps({"openapi": "3.1.0", "info": {"title": "Test", "version": "1"}, "paths": paths})
    )


def test_cli_returns_one_for_breaking_changes(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    head = tmp_path / "head.json"
    write_spec(base, {"/users": {"get": {"responses": {"200": {"description": "OK"}}}}})
    write_spec(head, {})

    assert run([str(base), str(head)]) == 1
    assert run([str(base), str(head), "--fail-on", "never"]) == 0


def test_cli_writes_json_report(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    head = tmp_path / "head.json"
    report = tmp_path / "reports" / "impact.json"
    write_spec(base, {})
    write_spec(head, {"/health": {"get": {"responses": {"200": {"description": "OK"}}}}})

    exit_code = run([str(base), str(head), "--format", "json", "--output", str(report)])

    assert exit_code == 0
    assert json.loads(report.read_text())["summary"]["non_breaking"] == 1


def test_cli_writes_sarif_report(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    head = tmp_path / "head.json"
    report = tmp_path / "impact.sarif"
    write_spec(base, {"/users": {"get": {"responses": {"200": {"description": "OK"}}}}})
    write_spec(head, {})

    exit_code = run(
        [str(base), str(head), "--format", "sarif", "--output", str(report), "--fail-on", "never"]
    )

    assert exit_code == 0
    assert json.loads(report.read_text())["runs"][0]["results"][0]["ruleId"] == "path.removed"


def test_cli_returns_two_for_invalid_input(tmp_path: Path, capsys: object) -> None:
    exit_code = run([str(tmp_path / "missing.yaml"), str(tmp_path / "also-missing.yaml")])

    assert exit_code == 2
