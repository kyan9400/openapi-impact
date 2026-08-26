from __future__ import annotations

from copy import deepcopy
from typing import Any

from openapi_impact import Severity, compare_specs


def codes(result: Any) -> set[str]:
    return {change.code for change in result.changes}


def test_identical_specs_are_compatible(base_spec: dict[str, Any]) -> None:
    result = compare_specs(base_spec, deepcopy(base_spec))

    assert result.changes == []
    assert result.has_breaking_changes is False


def test_removed_path_is_breaking(base_spec: dict[str, Any], clone_spec: dict[str, Any]) -> None:
    clone_spec["paths"] = {}

    result = compare_specs(base_spec, clone_spec)

    assert codes(result) == {"path.removed"}
    assert result.breaking_changes[0].location == "paths./orders/{order_id}"


def test_added_operation_is_non_breaking(
    base_spec: dict[str, Any], clone_spec: dict[str, Any]
) -> None:
    clone_spec["paths"]["/orders/{order_id}"]["delete"] = {
        "responses": {"204": {"description": "Deleted"}}
    }

    result = compare_specs(base_spec, clone_spec)

    assert codes(result) == {"operation.added"}
    assert result.changes[0].severity is Severity.NON_BREAKING


def test_required_parameter_addition_is_breaking(
    base_spec: dict[str, Any], clone_spec: dict[str, Any]
) -> None:
    clone_spec["paths"]["/orders/{order_id}"]["get"]["parameters"].append(
        {
            "name": "tenant",
            "in": "header",
            "required": True,
            "schema": {"type": "string"},
        }
    )

    result = compare_specs(base_spec, clone_spec)

    assert "parameter.required_added" in codes(result)
    assert result.has_breaking_changes


def test_optional_parameter_addition_is_safe(
    base_spec: dict[str, Any], clone_spec: dict[str, Any]
) -> None:
    clone_spec["paths"]["/orders/{order_id}"]["get"]["parameters"].append(
        {
            "name": "locale",
            "in": "query",
            "required": False,
            "schema": {"type": "string"},
        }
    )

    result = compare_specs(base_spec, clone_spec)

    assert codes(result) == {"parameter.optional_added"}
    assert not result.has_breaking_changes


def test_operation_id_and_security_changes_are_breaking(
    base_spec: dict[str, Any], clone_spec: dict[str, Any]
) -> None:
    operation = clone_spec["paths"]["/orders/{order_id}"]["get"]
    operation["operationId"] = "findOrder"
    operation["security"] = [{"bearerAuth": []}]

    result = compare_specs(base_spec, clone_spec)

    assert {"operation.id_changed", "operation.security_added"} <= codes(result)


def test_component_schema_detects_contract_narrowing(
    base_spec: dict[str, Any], clone_spec: dict[str, Any]
) -> None:
    order = clone_spec["components"]["schemas"]["Order"]
    order["required"].append("currency")
    order["properties"]["currency"] = {"type": "string"}
    order["properties"]["status"]["enum"].remove("draft")
    order["properties"]["note"]["maxLength"] = 120

    result = compare_specs(base_spec, clone_spec)

    assert {
        "schema.required_property_added",
        "schema.enum_value_removed",
        "schema.constraint_tightened",
    } <= codes(result)
    assert len(result.breaking_changes) == 3
    assert len(result.non_breaking_changes) == 0


def test_removed_response_is_breaking(
    base_spec: dict[str, Any], clone_spec: dict[str, Any]
) -> None:
    del clone_spec["paths"]["/orders/{order_id}"]["get"]["responses"]["404"]

    result = compare_specs(base_spec, clone_spec)

    assert codes(result) == {"response.removed"}


def test_removed_media_type_and_response_header_are_breaking(
    base_spec: dict[str, Any], clone_spec: dict[str, Any]
) -> None:
    old_response = base_spec["paths"]["/orders/{order_id}"]["get"]["responses"]["200"]
    new_response = clone_spec["paths"]["/orders/{order_id}"]["get"]["responses"]["200"]
    old_response["content"]["application/xml"] = {"schema": {"type": "string"}}
    old_response["headers"] = {"X-Request-Id": {"schema": {"type": "string"}}}
    new_response["headers"] = {}

    result = compare_specs(base_spec, clone_spec)

    assert {"content.media_type_removed", "response.header_removed"} <= codes(result)
    assert len(result.breaking_changes) == 2


def test_parameter_serialization_and_security_scope_changes_are_breaking(
    base_spec: dict[str, Any], clone_spec: dict[str, Any]
) -> None:
    base_operation = base_spec["paths"]["/orders/{order_id}"]["get"]
    new_operation = clone_spec["paths"]["/orders/{order_id}"]["get"]
    base_operation["security"] = [{"oauth": ["orders:read"]}]
    new_operation["security"] = [{"oauth": ["orders:read", "orders:admin"]}]
    new_operation["parameters"][1]["style"] = "spaceDelimited"

    result = compare_specs(base_spec, clone_spec)

    assert {"operation.security_changed", "parameter.serialization_changed"} <= codes(result)


def test_schema_restrictions_are_breaking(
    base_spec: dict[str, Any], clone_spec: dict[str, Any]
) -> None:
    old_order = base_spec["components"]["schemas"]["Order"]
    new_order = clone_spec["components"]["schemas"]["Order"]
    old_order["additionalProperties"] = True
    new_order["additionalProperties"] = False
    old_order["properties"]["note"]["nullable"] = True
    new_order["properties"]["note"]["nullable"] = False
    new_order["properties"]["note"]["pattern"] = "^[A-Z]"
    old_order["properties"]["tags"] = {"type": "array", "items": {"type": "string"}}
    new_order["properties"]["tags"] = {
        "type": "array",
        "items": {"type": "string"},
        "uniqueItems": True,
    }

    result = compare_specs(base_spec, clone_spec)

    assert {
        "schema.additional_properties_forbidden",
        "schema.nullable_removed",
        "schema.pattern_changed",
        "schema.unique_items_required",
    } <= codes(result)


def test_changes_sort_breaking_items_first(
    base_spec: dict[str, Any], clone_spec: dict[str, Any]
) -> None:
    clone_spec["paths"]["/health"] = {"get": {"responses": {"200": {"description": "OK"}}}}
    del clone_spec["paths"]["/orders/{order_id}"]["get"]["responses"]["404"]

    result = compare_specs(base_spec, clone_spec)

    assert result.changes[0].severity is Severity.BREAKING
    assert result.changes[-1].severity is Severity.NON_BREAKING
