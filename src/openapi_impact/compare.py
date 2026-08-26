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


def _content(document: dict[str, Any], container: Any) -> dict[str, Any]:
    resolved = _mapping(resolve_local_ref(document, container))
    return _mapping(resolved.get("content"))


def _compare_content(
    result: ComparisonResult,
    old_document: dict[str, Any],
    new_document: dict[str, Any],
    old_container: Any,
    new_container: Any,
    location: str,
) -> None:
    old_content = _content(old_document, old_container)
    new_content = _content(new_document, new_container)
    for media_type in sorted(old_content.keys() - new_content.keys()):
        result.add(
            "content.media_type_removed",
            Severity.BREAKING,
            f"{location}.content.{media_type}",
            f"Media type {media_type!r} is no longer supported.",
        )
    for media_type in sorted(new_content.keys() - old_content.keys()):
        result.add(
            "content.media_type_added",
            Severity.NON_BREAKING,
            f"{location}.content.{media_type}",
            f"Media type {media_type!r} is now supported.",
        )
    for media_type in sorted(old_content.keys() & new_content.keys()):
        old_schema = _mapping(old_content[media_type]).get("schema", {})
        new_schema = _mapping(new_content[media_type]).get("schema", {})
        _compare_schema(
            result,
            old_document,
            new_document,
            old_schema,
            new_schema,
            f"{location}.content.{media_type}.schema",
        )


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

    if old.get("nullable") is True and new.get("nullable") is not True:
        result.add(
            "schema.nullable_removed",
            Severity.BREAKING,
            location,
            "The schema no longer accepts null.",
            True,
            bool(new.get("nullable")),
        )

    if (
        old.get("additionalProperties", True) is not False
        and new.get("additionalProperties") is False
    ):
        result.add(
            "schema.additional_properties_forbidden",
            Severity.BREAKING,
            location,
            "Additional object properties are no longer accepted.",
        )

    old_pattern = old.get("pattern")
    new_pattern = new.get("pattern")
    if isinstance(new_pattern, str) and new_pattern != old_pattern:
        result.add(
            "schema.pattern_changed",
            Severity.BREAKING,
            location,
            "The accepted string pattern was added or changed.",
            old_pattern,
            new_pattern,
        )

    if old.get("uniqueItems") is not True and new.get("uniqueItems") is True:
        result.add(
            "schema.unique_items_required",
            Severity.BREAKING,
            location,
            "Array items must now be unique.",
            bool(old.get("uniqueItems")),
            True,
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

        default_style = "form" if parameter_location in {"query", "cookie"} else "simple"
        old_style = old_parameter.get("style", default_style)
        new_style = new_parameter.get("style", default_style)
        old_explode = old_parameter.get("explode", old_style == "form")
        new_explode = new_parameter.get("explode", new_style == "form")
        if old_style != new_style or old_explode != new_explode:
            result.add(
                "parameter.serialization_changed",
                Severity.BREAKING,
                parameter_path,
                "Parameter serialization style or explode behavior changed.",
                {"style": old_style, "explode": old_explode},
                {"style": new_style, "explode": new_explode},
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


def _security_requirements(document: dict[str, Any], operation: Any) -> list[dict[str, Any]]:
    operation_mapping = _mapping(operation)
    raw = (
        operation_mapping.get("security")
        if "security" in operation_mapping
        else document.get("security")
    )
    return [value for value in _sequence(raw) if isinstance(value, dict)]


def _canonical_security(
    requirements: list[dict[str, Any]],
) -> list[tuple[tuple[str, tuple[str, ...]], ...]]:
    return sorted(
        tuple(
            sorted(
                (scheme, tuple(sorted(str(scope) for scope in _sequence(scopes))))
                for scheme, scopes in requirement.items()
            )
        )
        for requirement in requirements
    )


def _compare_response_headers(
    result: ComparisonResult,
    old_document: dict[str, Any],
    new_document: dict[str, Any],
    old_response: Any,
    new_response: Any,
    location: str,
) -> None:
    old_headers = _mapping(_mapping(resolve_local_ref(old_document, old_response)).get("headers"))
    new_headers = _mapping(_mapping(resolve_local_ref(new_document, new_response)).get("headers"))
    for name in sorted(old_headers.keys() - new_headers.keys(), key=str.lower):
        result.add(
            "response.header_removed",
            Severity.BREAKING,
            f"{location}.headers.{name}",
            f"Response header {name!r} was removed.",
        )
    for name in sorted(new_headers.keys() - old_headers.keys(), key=str.lower):
        result.add(
            "response.header_added",
            Severity.NON_BREAKING,
            f"{location}.headers.{name}",
            f"Response header {name!r} was added.",
        )
    for name in sorted(old_headers.keys() & new_headers.keys(), key=str.lower):
        old_header = _mapping(resolve_local_ref(old_document, old_headers[name]))
        new_header = _mapping(resolve_local_ref(new_document, new_headers[name]))
        _compare_schema(
            result,
            old_document,
            new_document,
            old_header.get("schema", {}),
            new_header.get("schema", {}),
            f"{location}.headers.{name}.schema",
        )


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

    old_security = _security_requirements(old_document, old_operation)
    new_security = _security_requirements(new_document, new_operation)
    canonical_old_security = _canonical_security(old_security)
    canonical_new_security = _canonical_security(new_security)
    if not old_security and new_security:
        result.add(
            "operation.security_added",
            Severity.BREAKING,
            f"{location}.security",
            "The operation now requires authentication.",
        )
    elif old_security and not new_security:
        result.add(
            "operation.security_removed",
            Severity.NON_BREAKING,
            f"{location}.security",
            "The operation no longer requires authentication.",
        )
    elif canonical_old_security != canonical_new_security:
        result.add(
            "operation.security_changed",
            Severity.BREAKING,
            f"{location}.security",
            "Authentication schemes or required scopes changed.",
            canonical_old_security,
            canonical_new_security,
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
        _compare_content(
            result,
            old_document,
            new_document,
            old_request,
            new_request,
            f"{location}.requestBody",
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
        response_location = f"{location}.responses.{code}"
        _compare_content(
            result,
            old_document,
            new_document,
            old_responses[code],
            new_responses[code],
            response_location,
        )
        _compare_response_headers(
            result,
            old_document,
            new_document,
            old_responses[code],
            new_responses[code],
            response_location,
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
