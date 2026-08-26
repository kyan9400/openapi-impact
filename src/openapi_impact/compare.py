"""Semantic OpenAPI compatibility checks."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .loader import resolve_local_ref
from .models import ComparisonResult, Severity

HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _sequence(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _schema_from_content(document: dict[str, Any], container: Any) -> dict[str, Any]:
    content = _mapping(_mapping(resolve_local_ref(document, container)).get("content"))
    preferred = content.get("application/json")
    media_type = preferred if preferred is not None else next(iter(content.values()), {})
    schema = _mapping(media_type).get("schema", {})
    return _mapping(schema)


def _parameters(
    document: dict[str, Any], path_item: Any, operation: Any
) -> dict[tuple[str, str], dict[str, Any]]:
    parameters: dict[tuple[str, str], dict[str, Any]] = {}
    values = [
        *_sequence(_mapping(path_item).get("parameters")),
        *_sequence(_mapping(operation).get("parameters")),
    ]
    for raw_parameter in values:
        parameter = _mapping(resolve_local_ref(document, raw_parameter))
        name = parameter.get("name")
        location = parameter.get("in")
        if isinstance(name, str) and isinstance(location, str):
            parameters[(location, name)] = parameter
    return parameters


def _compare_schema(
    result: ComparisonResult,
    old_document: dict[str, Any],
    new_document: dict[str, Any],
    old_raw: Any,
    new_raw: Any,
    location: str,
) -> None:
    if (
        isinstance(old_raw, dict)
        and isinstance(new_raw, dict)
        and isinstance(old_raw.get("$ref"), str)
        and old_raw.get("$ref") == new_raw.get("$ref")
    ):
        return

    old = _mapping(resolve_local_ref(old_document, old_raw))
    new = _mapping(resolve_local_ref(new_document, new_raw))
    if not old and not new:
        return

    old_type = old.get("type")
    new_type = new.get("type")
    if old_type is not None and new_type is not None and old_type != new_type:
        result.add(
            "schema.type_changed",
            Severity.BREAKING,
            location,
            f"Schema type changed from {old_type!r} to {new_type!r}.",
            old_type,
            new_type,
        )

    old_format = old.get("format")
    new_format = new.get("format")
    if old_format and new_format and old_format != new_format:
        result.add(
            "schema.format_changed",
            Severity.BREAKING,
            location,
            f"Schema format changed from {old_format!r} to {new_format!r}.",
            old_format,
            new_format,
        )

    old_enum = set(_sequence(old.get("enum")))
    new_enum = set(_sequence(new.get("enum")))
    for removed in sorted(old_enum - new_enum, key=str):
        result.add(
            "schema.enum_value_removed",
            Severity.BREAKING,
            location,
            f"Allowed enum value {removed!r} was removed.",
            removed,
            None,
        )
    for added in sorted(new_enum - old_enum, key=str):
        result.add(
            "schema.enum_value_added",
            Severity.NON_BREAKING,
            location,
            f"Allowed enum value {added!r} was added.",
            None,
            added,
        )

    tightening_rules = (
        ("minimum", lambda before, after: after > before, "minimum increased"),
        ("minLength", lambda before, after: after > before, "minimum length increased"),
        ("minItems", lambda before, after: after > before, "minimum item count increased"),
        ("maximum", lambda before, after: after < before, "maximum decreased"),
        ("maxLength", lambda before, after: after < before, "maximum length decreased"),
        ("maxItems", lambda before, after: after < before, "maximum item count decreased"),
    )
    for keyword, is_tighter, message in tightening_rules:
        before = old.get(keyword)
        after = new.get(keyword)
        if (
            isinstance(before, (int, float))
            and isinstance(after, (int, float))
            and is_tighter(before, after)
        ):
            result.add(
                "schema.constraint_tightened",
                Severity.BREAKING,
                location,
                f"Schema {message} from {before} to {after}.",
                before,
                after,
            )

    old_required = {str(item) for item in _sequence(old.get("required"))}
    new_required = {str(item) for item in _sequence(new.get("required"))}
    for name in sorted(new_required - old_required):
        result.add(
            "schema.required_property_added",
            Severity.BREAKING,
            f"{location}.{name}",
            f"Property {name!r} is now required.",
            False,
            True,
        )
    for name in sorted(old_required - new_required):
        result.add(
            "schema.required_property_removed",
            Severity.NON_BREAKING,
            f"{location}.{name}",
            f"Property {name!r} is no longer required.",
            True,
            False,
        )

    old_properties = _mapping(old.get("properties"))
    new_properties = _mapping(new.get("properties"))
    for name in sorted(old_properties.keys() - new_properties.keys()):
        result.add(
            "schema.property_removed",
            Severity.BREAKING,
            f"{location}.{name}",
            f"Property {name!r} was removed.",
        )
    for name in sorted(new_properties.keys() - old_properties.keys()):
        if name in new_required:
            continue
        result.add(
            "schema.property_added",
            Severity.NON_BREAKING,
            f"{location}.{name}",
            f"Optional property {name!r} was added.",
        )
    for name in sorted(old_properties.keys() & new_properties.keys()):
        _compare_schema(
            result,
            old_document,
            new_document,
            old_properties[name],
            new_properties[name],
            f"{location}.{name}",
        )

    old_items = old.get("items")
    new_items = new.get("items")
    if isinstance(old_items, dict) and isinstance(new_items, dict):
        _compare_schema(result, old_document, new_document, old_items, new_items, f"{location}[]")


def _compare_parameters(
    result: ComparisonResult,
    old_document: dict[str, Any],
    new_document: dict[str, Any],
    old_path_item: Any,
    new_path_item: Any,
    old_operation: Any,
    new_operation: Any,
    location: str,
) -> None:
    old_parameters = _parameters(old_document, old_path_item, old_operation)
    new_parameters = _parameters(new_document, new_path_item, new_operation)

    for key in sorted(old_parameters.keys() - new_parameters.keys()):
        parameter_location, name = key
        result.add(
            "parameter.removed",
            Severity.BREAKING,
            f"{location}.parameters.{parameter_location}.{name}",
            f"{parameter_location} parameter {name!r} was removed.",
        )

    for key in sorted(new_parameters.keys() - old_parameters.keys()):
        parameter_location, name = key
        parameter = new_parameters[key]
        required = bool(parameter.get("required")) or parameter_location == "path"
        result.add(
            "parameter.required_added" if required else "parameter.optional_added",
            Severity.BREAKING if required else Severity.NON_BREAKING,
            f"{location}.parameters.{parameter_location}.{name}",
            (
                f"{'Required' if required else 'Optional'} {parameter_location} "
                f"parameter {name!r} was added."
            ),
        )

    for key in sorted(old_parameters.keys() & new_parameters.keys()):
        parameter_location, name = key
        old_parameter = old_parameters[key]
        new_parameter = new_parameters[key]
        old_required = bool(old_parameter.get("required")) or parameter_location == "path"
        new_required = bool(new_parameter.get("required")) or parameter_location == "path"
        parameter_path = f"{location}.parameters.{parameter_location}.{name}"
        if not old_required and new_required:
            result.add(
                "parameter.became_required",
                Severity.BREAKING,
                parameter_path,
                f"Parameter {name!r} is now required.",
                False,
                True,
            )
        elif old_required and not new_required:
            result.add(
                "parameter.became_optional",
                Severity.NON_BREAKING,
                parameter_path,
                f"Parameter {name!r} is now optional.",
                True,
                False,
            )

        _compare_schema(
            result,
            old_document,
            new_document,
            old_parameter.get("schema", {}),
            new_parameter.get("schema", {}),
            f"{parameter_path}.schema",
        )


def _response_codes(operation: Any) -> set[str]:
    return {str(code) for code in _mapping(_mapping(operation).get("responses"))}


def _compare_operation(
    result: ComparisonResult,
    old_document: dict[str, Any],
    new_document: dict[str, Any],
    old_path_item: Any,
    new_path_item: Any,
    method: str,
    path: str,
) -> None:
    old_operation = _mapping(old_path_item).get(method, {})
    new_operation = _mapping(new_path_item).get(method, {})
    location = f"paths.{path}.{method}"

    old_operation_id = _mapping(old_operation).get("operationId")
    new_operation_id = _mapping(new_operation).get("operationId")
    if old_operation_id and new_operation_id and old_operation_id != new_operation_id:
        result.add(
            "operation.id_changed",
            Severity.BREAKING,
            location,
            f"operationId changed from {old_operation_id!r} to {new_operation_id!r}.",
            old_operation_id,
            new_operation_id,
        )

    if not _sequence(_mapping(old_operation).get("security")) and _sequence(
        _mapping(new_operation).get("security")
    ):
        result.add(
            "operation.security_added",
            Severity.BREAKING,
            f"{location}.security",
            "The operation now requires authentication.",
        )

    _compare_parameters(
        result,
        old_document,
        new_document,
        old_path_item,
        new_path_item,
        old_operation,
        new_operation,
        location,
    )

    old_request = _mapping(
        resolve_local_ref(old_document, _mapping(old_operation).get("requestBody", {}))
    )
    new_request = _mapping(
        resolve_local_ref(new_document, _mapping(new_operation).get("requestBody", {}))
    )
    if not old_request and new_request and new_request.get("required"):
        result.add(
            "request_body.required_added",
            Severity.BREAKING,
            f"{location}.requestBody",
            "A required request body was added.",
        )
    elif old_request and not new_request:
        result.add(
            "request_body.removed",
            Severity.BREAKING,
            f"{location}.requestBody",
            "The request body was removed.",
        )
    elif old_request and new_request:
        if not old_request.get("required") and new_request.get("required"):
            result.add(
                "request_body.became_required",
                Severity.BREAKING,
                f"{location}.requestBody",
                "The request body is now required.",
            )
        _compare_schema(
            result,
            old_document,
            new_document,
            _schema_from_content(old_document, old_request),
            _schema_from_content(new_document, new_request),
            f"{location}.requestBody.schema",
        )

    old_responses = _mapping(_mapping(old_operation).get("responses"))
    new_responses = _mapping(_mapping(new_operation).get("responses"))
    for code in sorted(_response_codes(old_operation) - _response_codes(new_operation)):
        result.add(
            "response.removed",
            Severity.BREAKING,
            f"{location}.responses.{code}",
            f"Response {code!r} was removed.",
        )
    for code in sorted(_response_codes(new_operation) - _response_codes(old_operation)):
        result.add(
            "response.added",
            Severity.NON_BREAKING,
            f"{location}.responses.{code}",
            f"Response {code!r} was added.",
        )
    for code in sorted(_response_codes(old_operation) & _response_codes(new_operation)):
        _compare_schema(
            result,
            old_document,
            new_document,
            _schema_from_content(old_document, old_responses[code]),
            _schema_from_content(new_document, new_responses[code]),
            f"{location}.responses.{code}.schema",
        )


def _schema_names(document: dict[str, Any]) -> set[str]:
    return set(_mapping(_mapping(document.get("components")).get("schemas")))


def compare_specs(old_document: dict[str, Any], new_document: dict[str, Any]) -> ComparisonResult:
    """Compare two OpenAPI documents from the perspective of existing consumers."""

    result = ComparisonResult()
    old_paths = _mapping(old_document.get("paths"))
    new_paths = _mapping(new_document.get("paths"))

    for path in sorted(old_paths.keys() - new_paths.keys()):
        result.add(
            "path.removed", Severity.BREAKING, f"paths.{path}", f"Path {path!r} was removed."
        )
    for path in sorted(new_paths.keys() - old_paths.keys()):
        result.add(
            "path.added", Severity.NON_BREAKING, f"paths.{path}", f"Path {path!r} was added."
        )

    for path in sorted(old_paths.keys() & new_paths.keys()):
        old_path_item = _mapping(resolve_local_ref(old_document, old_paths[path]))
        new_path_item = _mapping(resolve_local_ref(new_document, new_paths[path]))
        old_methods = set(old_path_item) & HTTP_METHODS
        new_methods = set(new_path_item) & HTTP_METHODS

        for method in sorted(old_methods - new_methods):
            result.add(
                "operation.removed",
                Severity.BREAKING,
                f"paths.{path}.{method}",
                f"{method.upper()} {path} was removed.",
            )
        for method in sorted(new_methods - old_methods):
            result.add(
                "operation.added",
                Severity.NON_BREAKING,
                f"paths.{path}.{method}",
                f"{method.upper()} {path} was added.",
            )
        for method in sorted(old_methods & new_methods):
            _compare_operation(
                result,
                old_document,
                new_document,
                old_path_item,
                new_path_item,
                method,
                path,
            )

    old_schemas = _mapping(_mapping(old_document.get("components")).get("schemas"))
    new_schemas = _mapping(_mapping(new_document.get("components")).get("schemas"))
    for name in sorted(_schema_names(old_document) - _schema_names(new_document)):
        result.add(
            "component.schema_removed",
            Severity.BREAKING,
            f"components.schemas.{name}",
            f"Reusable schema {name!r} was removed.",
        )
    for name in sorted(_schema_names(new_document) - _schema_names(old_document)):
        result.add(
            "component.schema_added",
            Severity.NON_BREAKING,
            f"components.schemas.{name}",
            f"Reusable schema {name!r} was added.",
        )
    for name in sorted(_schema_names(old_document) & _schema_names(new_document)):
        _compare_schema(
            result,
            old_document,
            new_document,
            old_schemas[name],
            new_schemas[name],
            f"components.schemas.{name}",
        )

    result.sort()
    return result


def summarize_codes(changes: Iterable[str]) -> dict[str, int]:
    """Count change codes for integrations that need coarse-grained metrics."""

    counts: dict[str, int] = {}
    for code in changes:
        counts[code] = counts.get(code, 0) + 1
    return counts
