"""Typed comparison results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Compatibility impact assigned to a detected contract change."""

    BREAKING = "breaking"
    NON_BREAKING = "non-breaking"


@dataclass(frozen=True, slots=True)
class Change:
    """A single, addressable difference between two specifications."""

    code: str
    severity: Severity
    location: str
    message: str
    before: Any = None
    after: Any = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


@dataclass(slots=True)
class ComparisonResult:
    """Aggregate compatibility report."""

    changes: list[Change] = field(default_factory=list)

    @property
    def breaking_changes(self) -> list[Change]:
        return [change for change in self.changes if change.severity is Severity.BREAKING]

    @property
    def non_breaking_changes(self) -> list[Change]:
        return [change for change in self.changes if change.severity is Severity.NON_BREAKING]

    @property
    def has_breaking_changes(self) -> bool:
        return bool(self.breaking_changes)

    def add(
        self,
        code: str,
        severity: Severity,
        location: str,
        message: str,
        before: Any = None,
        after: Any = None,
    ) -> None:
        self.changes.append(Change(code, severity, location, message, before, after))

    def sort(self) -> None:
        order = {Severity.BREAKING: 0, Severity.NON_BREAKING: 1}
        self.changes.sort(key=lambda change: (order[change.severity], change.location, change.code))

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "breaking": len(self.breaking_changes),
                "non_breaking": len(self.non_breaking_changes),
                "total": len(self.changes),
            },
            "changes": [change.to_dict() for change in self.changes],
        }
