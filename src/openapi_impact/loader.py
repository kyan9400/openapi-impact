"""Safe loading and basic validation for OpenAPI documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


class SpecError(ValueError):
    """Raised when an input cannot be treated as an OpenAPI document."""


def load_spec(path: str | Path) -> dict[str, Any]:
    """Load an OpenAPI JSON or YAML document from disk."""

    source = Path(path)
    if not source.is_file():
        raise SpecError(f"Specification not found: {source}")

    try:
        raw = source.read_text(encoding="utf-8")
        document = json.loads(raw) if source.suffix.lower() == ".json" else yaml.safe_load(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, yaml.YAMLError) as error:
        raise SpecError(f"Could not parse {source}: {error}") from error

    if not isinstance(document, dict):
        raise SpecError(f"Expected an object at the root of {source}.")

    version = document.get("openapi")
    if not isinstance(version, str) or not version.startswith(("3.0.", "3.1.")):
        raise SpecError(f"{source} is not an OpenAPI 3.0 or 3.1 document.")

    if not isinstance(document.get("paths", {}), dict):
        raise SpecError(f"Expected 'paths' to be an object in {source}.")

    return document


def resolve_local_ref(document: dict[str, Any], value: Any) -> Any:
    """Resolve a local JSON Pointer reference, leaving unsupported references unchanged."""

    seen: set[str] = set()
    current = value

    while isinstance(current, dict) and isinstance(current.get("$ref"), str):
        reference = current["$ref"]
        if not reference.startswith("#/") or reference in seen:
            return current
        seen.add(reference)

        resolved: Any = document
        try:
            for segment in reference[2:].split("/"):
                key = segment.replace("~1", "/").replace("~0", "~")
                resolved = resolved[key]
        except (KeyError, TypeError):
            return current
        current = resolved

    return current
