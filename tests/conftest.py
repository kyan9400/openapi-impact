from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest


@pytest.fixture
def base_spec() -> dict[str, Any]:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Orders", "version": "1.0.0"},
        "paths": {
            "/orders/{order_id}": {
                "get": {
                    "operationId": "getOrder",
                    "parameters": [
                        {
                            "name": "order_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "expand",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string", "enum": ["items", "customer"]},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Order",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Order"}
                                }
                            },
                        },
                        "404": {"description": "Missing"},
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "Order": {
                    "type": "object",
                    "required": ["id", "status"],
                    "properties": {
                        "id": {"type": "string"},
                        "status": {"type": "string", "enum": ["draft", "paid", "shipped"]},
                        "note": {"type": "string", "maxLength": 500},
                    },
                }
            }
        },
    }


@pytest.fixture
def clone_spec(base_spec: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(base_spec)
