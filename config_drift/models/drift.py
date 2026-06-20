"""Drift detection models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class DriftType(str, Enum):
    """Types of configuration drift."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    TYPE_CHANGED = "type_changed"


class DriftSeverity(str, Enum):
    """Severity levels for drift."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DriftResult:
    """A single drift detection result."""

    path: str
    drift_type: DriftType
    severity: DriftSeverity
    expected: Any
    actual: Any
    source: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "drift_type": self.drift_type.value,
            "severity": self.severity.value,
            "expected": self.expected,
            "actual": self.actual,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
        }


@dataclass
class DriftSummary:
    """Summary of drift detection results."""

    total_drifts: int = 0
    by_type: dict[DriftType, int] = field(default_factory=dict)
    by_severity: dict[DriftSeverity, int] = field(default_factory=dict)
    by_source: dict[str, int] = field(default_factory=dict)
    drifts: list[DriftResult] = field(default_factory=list)

    def add(self, drift: DriftResult) -> None:
        self.total_drifts += 1
        self.by_type[drift.drift_type] = self.by_type.get(drift.drift_type, 0) + 1
        self.by_severity[drift.severity] = self.by_severity.get(drift.severity, 0) + 1
        self.by_source[drift.source] = self.by_source.get(drift.source, 0) + 1
        self.drifts.append(drift)

    def to_dict(self) -> dict:
        return {
            "total_drifts": self.total_drifts,
            "by_type": {k.value: v for k, v in self.by_type.items()},
            "by_severity": {k.value: v for k, v in self.by_severity.items()},
            "by_source": self.by_source,
            "drifts": [d.to_dict() for d in self.drifts],
        }
