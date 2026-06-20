"""Tests for drift detection models."""

from datetime import datetime

from config_drift.models.drift import DriftResult, DriftSeverity, DriftSummary, DriftType


class TestDriftType:
    """Tests for DriftType enum."""

    def test_values(self):
        assert DriftType.ADDED.value == "added"
        assert DriftType.REMOVED.value == "removed"
        assert DriftType.MODIFIED.value == "modified"
        assert DriftType.TYPE_CHANGED.value == "type_changed"

    def test_from_string(self):
        assert DriftType("added") == DriftType.ADDED
        assert DriftType("removed") == DriftType.REMOVED


class TestDriftSeverity:
    """Tests for DriftSeverity enum."""

    def test_values(self):
        assert DriftSeverity.LOW.value == "low"
        assert DriftSeverity.MEDIUM.value == "medium"
        assert DriftSeverity.HIGH.value == "high"
        assert DriftSeverity.CRITICAL.value == "critical"


class TestDriftResult:
    """Tests for DriftResult dataclass."""

    def test_creation(self):
        drift = DriftResult(
            path="spec.replicas",
            drift_type=DriftType.MODIFIED,
            severity=DriftSeverity.HIGH,
            expected=3,
            actual=5,
            source="kubernetes",
        )
        assert drift.path == "spec.replicas"
        assert drift.drift_type == DriftType.MODIFIED
        assert drift.severity == DriftSeverity.HIGH
        assert drift.expected == 3
        assert drift.actual == 5
        assert drift.source == "kubernetes"

    def test_to_dict(self):
        drift = DriftResult(
            path="spec.replicas",
            drift_type=DriftType.MODIFIED,
            severity=DriftSeverity.HIGH,
            expected=3,
            actual=5,
            source="kubernetes",
            message="replicas changed",
        )
        result = drift.to_dict()
        assert result["path"] == "spec.replicas"
        assert result["drift_type"] == "modified"
        assert result["severity"] == "high"
        assert result["expected"] == 3
        assert result["actual"] == 5
        assert result["source"] == "kubernetes"
        assert result["message"] == "replicas changed"
        assert "timestamp" in result


class TestDriftSummary:
    """Tests for DriftSummary dataclass."""

    def test_empty_summary(self):
        summary = DriftSummary()
        assert summary.total_drifts == 0
        assert len(summary.drifts) == 0

    def test_add_drift(self):
        summary = DriftSummary()
        drift = DriftResult(
            path="spec.replicas",
            drift_type=DriftType.MODIFIED,
            severity=DriftSeverity.HIGH,
            expected=3,
            actual=5,
            source="kubernetes",
        )
        summary.add(drift)
        assert summary.total_drifts == 1
        assert summary.by_type[DriftType.MODIFIED] == 1
        assert summary.by_severity[DriftSeverity.HIGH] == 1
        assert summary.by_source["kubernetes"] == 1
        assert len(summary.drifts) == 1

    def test_multiple_drifts(self):
        summary = DriftSummary()
        summary.add(DriftResult("a", DriftType.ADDED, DriftSeverity.LOW, None, "x", "k8s"))
        summary.add(DriftResult("b", DriftType.MODIFIED, DriftSeverity.HIGH, 1, 2, "k8s"))
        summary.add(
            DriftResult("c", DriftType.REMOVED, DriftSeverity.CRITICAL, "y", None, "docker")
        )
        assert summary.total_drifts == 3
        assert summary.by_type[DriftType.ADDED] == 1
        assert summary.by_type[DriftType.MODIFIED] == 1
        assert summary.by_type[DriftType.REMOVED] == 1
        assert summary.by_severity[DriftSeverity.LOW] == 1
        assert summary.by_severity[DriftSeverity.HIGH] == 1
        assert summary.by_severity[DriftSeverity.CRITICAL] == 1

    def test_to_dict(self):
        summary = DriftSummary()
        summary.add(DriftResult("a", DriftType.MODIFIED, DriftSeverity.HIGH, 1, 2, "k8s"))
        result = summary.to_dict()
        assert result["total_drifts"] == 1
        assert result["by_type"]["modified"] == 1
        assert result["by_severity"]["high"] == 1
        assert result["by_source"]["k8s"] == 1
        assert len(result["drifts"]) == 1
