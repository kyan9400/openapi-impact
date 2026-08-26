from __future__ import annotations

import json
from pathlib import Path

import pytest

from openapi_impact.loader import SpecError, load_spec, resolve_local_ref


def test_loads_yaml_and_json(tmp_path: Path) -> None:
    document = {"openapi": "3.0.3", "info": {"title": "Test", "version": "1"}, "paths": {}}
    yaml_path = tmp_path / "openapi.yaml"
    json_path = tmp_path / "openapi.json"
    yaml_path.write_text("openapi: 3.0.3\ninfo:\n  title: Test\n  version: '1'\npaths: {}\n")
    json_path.write_text(json.dumps(document))

    assert load_spec(yaml_path) == document
    assert load_spec(json_path) == document


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("missing-version.yaml", "paths: {}\n"),
        ("swagger.yaml", "swagger: '2.0'\npaths: {}\n"),
        ("array.yaml", "- not\n- an\n- object\n"),
    ],
)
def test_rejects_invalid_documents(tmp_path: Path, filename: str, content: str) -> None:
    path = tmp_path / filename
    path.write_text(content)

    with pytest.raises(SpecError):
        load_spec(path)


def test_resolves_escaped_local_json_pointer() -> None:
    document = {"components": {"schemas": {"a/b": {"type": "string"}}}}

    resolved = resolve_local_ref(document, {"$ref": "#/components/schemas/a~1b"})

    assert resolved == {"type": "string"}


def test_unresolved_reference_is_left_intact() -> None:
    reference = {"$ref": "https://example.com/schema.yaml"}
    assert resolve_local_ref({}, reference) == reference
