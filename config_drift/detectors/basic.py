"""Structural drift detector - compares configuration structure and values."""

from typing import Any

from config_drift.detectors.base import DriftDetector
from config_drift.models.config import ParsedConfig
from config_drift.models.drift import DriftResult, DriftType


class BasicDriftDetector(DriftDetector):
    """Detects structural differences between configurations."""

    def detect(self, baseline: ParsedConfig, current: ParsedConfig) -> list[DriftResult]:
        """Detect structural drift by comparing config trees."""
        drifts = []
        self._compare_dicts(
            baseline.content,
            current.content,
            path="",
            source=baseline.source.value,
            drifts=drifts,
        )
        return drifts

    def _compare_dicts(
        self,
        baseline: dict[str, Any],
        current: dict[str, Any],
        path: str,
        source: str,
        drifts: list[DriftResult],
    ) -> None:
        """Recursively compare two dictionaries."""
        all_keys = set(baseline.keys()) | set(current.keys())

        for key in sorted(all_keys):
            current_path = f"{path}.{key}" if path else key

            if self._should_ignore(current_path):
                continue

            if key not in baseline:
                # Key added
                drifts.append(
                    self._create_drift(
                        path=current_path,
                        drift_type=DriftType.ADDED,
                        expected=None,
                        actual=current[key],
                        source=source,
                        message=f"Key '{key}' was added",
                    )
                )
            elif key not in current:
                # Key removed
                drifts.append(
                    self._create_drift(
                        path=current_path,
                        drift_type=DriftType.REMOVED,
                        expected=baseline[key],
                        actual=None,
                        source=source,
                        message=f"Key '{key}' was removed",
                    )
                )
            else:
                # Key exists in both - compare values
                baseline_val = baseline[key]
                current_val = current[key]

                if isinstance(baseline_val, dict) and isinstance(current_val, dict):
                    # Recurse into nested dicts
                    self._compare_dicts(baseline_val, current_val, current_path, source, drifts)
                elif isinstance(baseline_val, list) and isinstance(current_val, list):
                    # Compare lists
                    self._compare_lists(baseline_val, current_val, current_path, source, drifts)
                elif self.config.compare_types and type(baseline_val) != type(current_val):
                    # Type changed
                    drifts.append(
                        self._create_drift(
                            path=current_path,
                            drift_type=DriftType.TYPE_CHANGED,
                            expected=baseline_val,
                            actual=current_val,
                            source=source,
                            message=f"Type changed from {type(baseline_val).__name__} to {type(current_val).__name__}",
                        )
                    )
                elif self.config.compare_values and baseline_val != current_val:
                    # Value changed
                    drifts.append(
                        self._create_drift(
                            path=current_path,
                            drift_type=DriftType.MODIFIED,
                            expected=baseline_val,
                            actual=current_val,
                            source=source,
                            message="Value changed",
                        )
                    )

    def _compare_lists(
        self,
        baseline: list[Any],
        current: list[Any],
        path: str,
        source: str,
        drifts: list[DriftResult],
    ) -> None:
        """Compare two lists."""
        # For lists, we compare by index (structural comparison)
        max_len = max(len(baseline), len(current))
        for i in range(max_len):
            current_path = f"{path}[{i}]"

            if self._should_ignore(current_path):
                continue

            if i >= len(baseline):
                # Item added
                drifts.append(
                    self._create_drift(
                        path=current_path,
                        drift_type=DriftType.ADDED,
                        expected=None,
                        actual=current[i],
                        source=source,
                        message=f"List item added at index {i}",
                    )
                )
            elif i >= len(current):
                # Item removed
                drifts.append(
                    self._create_drift(
                        path=current_path,
                        drift_type=DriftType.REMOVED,
                        expected=baseline[i],
                        actual=None,
                        source=source,
                        message=f"List item removed at index {i}",
                    )
                )
            else:
                # Compare items
                baseline_item = baseline[i]
                current_item = current[i]

                if isinstance(baseline_item, dict) and isinstance(current_item, dict):
                    self._compare_dicts(baseline_item, current_item, current_path, source, drifts)
                elif isinstance(baseline_item, list) and isinstance(current_item, list):
                    self._compare_lists(baseline_item, current_item, current_path, source, drifts)
                elif self.config.compare_types and type(baseline_item) != type(current_item):
                    drifts.append(
                        self._create_drift(
                            path=current_path,
                            drift_type=DriftType.TYPE_CHANGED,
                            expected=baseline_item,
                            actual=current_item,
                            source=source,
                            message="List item type changed",
                        )
                    )
                elif self.config.compare_values and baseline_item != current_item:
                    drifts.append(
                        self._create_drift(
                            path=current_path,
                            drift_type=DriftType.MODIFIED,
                            expected=baseline_item,
                            actual=current_item,
                            source=source,
                            message="List item value changed",
                        )
                    )
