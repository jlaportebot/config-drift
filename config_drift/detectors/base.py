"""Base drift detector interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from config_drift.models.config import ParsedConfig
from config_drift.models.drift import DriftResult, DriftSeverity, DriftType


@dataclass
class DetectorConfig:
    """Configuration for drift detectors."""

    ignore_paths: list[str] = None
    severity_rules: dict[str, DriftSeverity] = None
    compare_values: bool = True
    compare_types: bool = True

    def __post_init__(self):
        if self.ignore_paths is None:
            self.ignore_paths = []
        if self.severity_rules is None:
            self.severity_rules = {}


class DriftDetector(ABC):
    """Abstract base class for drift detectors."""

    def __init__(self, config: DetectorConfig | None = None):
        self.config = config or DetectorConfig()

    @abstractmethod
    def detect(self, baseline: ParsedConfig, current: ParsedConfig) -> list[DriftResult]:
        """Detect drift between baseline and current configuration.

        Args:
            baseline: Expected/baseline configuration
            current: Current/actual configuration

        Returns:
            List of drift results
        """

    def _should_ignore(self, path: str) -> bool:
        """Check if a path should be ignored."""
        for pattern in self.config.ignore_paths:
            if self._match_pattern(path, pattern):
                return True
        return False

    def _match_pattern(self, path: str, pattern: str) -> bool:
        """Simple pattern matching (supports * wildcards)."""
        if "*" not in pattern:
            return path == pattern
        parts = pattern.split("*")
        if not path.startswith(parts[0]):
            return False
        if not path.endswith(parts[-1]):
            return False
        return True

    def _determine_severity(self, path: str, drift_type: DriftType) -> DriftSeverity:
        """Determine severity based on path and drift type."""
        # Check custom rules first
        for pattern, severity in self.config.severity_rules.items():
            if self._match_pattern(path, pattern):
                return severity

        # Default severity by drift type
        severity_map = {
            DriftType.ADDED: DriftSeverity.LOW,
            DriftType.REMOVED: DriftSeverity.HIGH,
            DriftType.MODIFIED: DriftSeverity.MEDIUM,
            DriftType.TYPE_CHANGED: DriftSeverity.HIGH,
        }
        return severity_map.get(drift_type, DriftSeverity.MEDIUM)

    def _create_drift(
        self,
        path: str,
        drift_type: DriftType,
        expected: Any,
        actual: Any,
        source: str,
        message: str = "",
    ) -> DriftResult:
        """Create a drift result with computed severity."""
        severity = self._determine_severity(path, drift_type)
        return DriftResult(
            path=path,
            drift_type=drift_type,
            severity=severity,
            expected=expected,
            actual=actual,
            source=source,
            message=message,
        )
