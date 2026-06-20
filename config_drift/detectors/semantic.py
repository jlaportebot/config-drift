"""Semantic drift detector - compares configuration meaning beyond structure."""

from typing import Any

from config_drift.detectors.base import DriftDetector
from config_drift.models.config import ParsedConfig
from config_drift.models.drift import DriftResult, DriftSeverity, DriftType


class SemanticDriftDetector(DriftDetector):
    """Detects semantic differences - meaningful changes beyond structure."""

    # Fields that are semantically significant for each source type
    SEMANTIC_FIELDS = {
        "kubernetes": {
            "critical": [
                "spec.replicas",
                "spec.template.spec.containers[*].image",
                "spec.template.spec.containers[*].resources",
                "spec.template.spec.securityContext",
                "spec.selector",
                "data",
                "stringData",
            ],
            "high": [
                "spec.template.spec.containers[*].env",
                "spec.template.spec.containers[*].ports",
                "spec.template.spec.volumes",
                "metadata.annotations",
                "metadata.labels",
            ],
            "medium": [
                "spec.template.metadata.annotations",
                "spec.template.metadata.labels",
                "spec.strategy",
            ],
        },
        "docker_compose": {
            "critical": [
                "services.*.image",
                "services.*.deploy.resources",
                "services.*.environment",
                "services.*.command",
            ],
            "high": [
                "services.*.ports",
                "services.*.volumes",
                "services.*.networks",
                "services.*.restart",
            ],
            "medium": [
                "services.*.labels",
                "services.*.depends_on",
                "services.*.healthcheck",
            ],
        },
        "terraform": {
            "critical": [
                "resource.*.*.provider",
                "resource.*.*.lifecycle",
                "module.*.source",
                "module.*.version",
            ],
            "high": [
                "resource.*.*.*.tags",
                "resource.*.*.*.environment",
                "variable.*.*.default",
                "output.*.*.value",
            ],
            "medium": [
                "locals.*",
                "data.*.*",
            ],
        },
        "helm": {
            "critical": [
                "metadata.name",
                "metadata.version",
                "values.*.image",
                "values.*.resources",
                "values.*.replicaCount",
            ],
            "high": [
                "values.*.service",
                "values.*.ingress",
                "values.*.persistence",
                "values.*.env",
            ],
            "medium": [
                "values.*.labels",
                "values.*.annotations",
                "values.*.affinity",
            ],
        },
    }

    def detect(self, baseline: ParsedConfig, current: ParsedConfig) -> list[DriftResult]:
        """Detect semantic drift by evaluating meaningful changes."""
        drifts = []

        # Get semantic field patterns for this source
        patterns = self.SEMANTIC_FIELDS.get(baseline.source.value, {})
        critical_paths = set(patterns.get("critical", []))
        high_paths = set(patterns.get("high", []))
        medium_paths = set(patterns.get("medium", []))

        # Compare with semantic awareness
        self._compare_semantic(
            baseline.content,
            current.content,
            path="",
            source=baseline.source.value,
            critical_paths=critical_paths,
            high_paths=high_paths,
            medium_paths=medium_paths,
            drifts=drifts,
        )

        return drifts

    def _compare_semantic(
        self,
        baseline: dict[str, Any],
        current: dict[str, Any],
        path: str,
        source: str,
        critical_paths: set,
        high_paths: set,
        medium_paths: set,
        drifts: list[DriftResult],
    ) -> None:
        """Recursively compare with semantic awareness."""
        all_keys = set(baseline.keys()) | set(current.keys())

        for key in sorted(all_keys):
            current_path = f"{path}.{key}" if path else key

            if self._should_ignore(current_path):
                continue

            # Determine semantic severity for this path
            semantic_severity = self._get_semantic_severity(
                current_path, critical_paths, high_paths, medium_paths
            )

            if key not in baseline:
                severity = semantic_severity or DriftSeverity.LOW
                drifts.append(
                    DriftResult(
                        path=current_path,
                        drift_type=DriftType.ADDED,
                        severity=severity,
                        expected=None,
                        actual=current[key],
                        source=source,
                        message=f"Semantically significant key '{key}' was added",
                    )
                )
            elif key not in current:
                severity = semantic_severity or DriftSeverity.HIGH
                drifts.append(
                    DriftResult(
                        path=current_path,
                        drift_type=DriftType.REMOVED,
                        severity=severity,
                        expected=baseline[key],
                        actual=None,
                        source=source,
                        message=f"Semantically significant key '{key}' was removed",
                    )
                )
            else:
                baseline_val = baseline[key]
                current_val = current[key]

                if isinstance(baseline_val, dict) and isinstance(current_val, dict):
                    self._compare_semantic(
                        baseline_val,
                        current_val,
                        current_path,
                        source,
                        critical_paths,
                        high_paths,
                        medium_paths,
                        drifts,
                    )
                elif isinstance(baseline_val, list) and isinstance(current_val, list):
                    self._compare_lists_semantic(
                        baseline_val,
                        current_val,
                        current_path,
                        source,
                        critical_paths,
                        high_paths,
                        medium_paths,
                        drifts,
                    )
                elif baseline_val != current_val:
                    severity = semantic_severity or DriftSeverity.MEDIUM
                    drifts.append(
                        DriftResult(
                            path=current_path,
                            drift_type=DriftType.MODIFIED,
                            severity=severity,
                            expected=baseline_val,
                            actual=current_val,
                            source=source,
                            message="Semantically significant value changed",
                        )
                    )

    def _compare_lists_semantic(
        self,
        baseline: list[Any],
        current: list[Any],
        path: str,
        source: str,
        critical_paths: set,
        high_paths: set,
        medium_paths: set,
        drifts: list[DriftResult],
    ) -> None:
        """Compare lists with semantic awareness."""
        # For semantic comparison of lists, we try to match by key fields
        # This is simplified - in practice you'd match by ID/name fields
        max_len = max(len(baseline), len(current))
        for i in range(max_len):
            current_path = f"{path}[{i}]"

            if self._should_ignore(current_path):
                continue

            semantic_severity = self._get_semantic_severity(
                current_path, critical_paths, high_paths, medium_paths
            )

            if i >= len(baseline):
                severity = semantic_severity or DriftSeverity.LOW
                drifts.append(
                    DriftResult(
                        path=current_path,
                        drift_type=DriftType.ADDED,
                        severity=severity,
                        expected=None,
                        actual=current[i],
                        source=source,
                        message="List item added",
                    )
                )
            elif i >= len(current):
                severity = semantic_severity or DriftSeverity.HIGH
                drifts.append(
                    DriftResult(
                        path=current_path,
                        drift_type=DriftType.REMOVED,
                        severity=severity,
                        expected=baseline[i],
                        actual=None,
                        source=source,
                        message="List item removed",
                    )
                )
            else:
                baseline_item = baseline[i]
                current_item = current[i]

                if isinstance(baseline_item, dict) and isinstance(current_item, dict):
                    self._compare_semantic(
                        baseline_item,
                        current_item,
                        current_path,
                        source,
                        critical_paths,
                        high_paths,
                        medium_paths,
                        drifts,
                    )
                elif baseline_item != current_item:
                    severity = semantic_severity or DriftSeverity.MEDIUM
                    drifts.append(
                        DriftResult(
                            path=current_path,
                            drift_type=DriftType.MODIFIED,
                            severity=severity,
                            expected=baseline_item,
                            actual=current_item,
                            source=source,
                            message="List item value changed",
                        )
                    )

    def _get_semantic_severity(
        self,
        path: str,
        critical_paths: set,
        high_paths: set,
        medium_paths: set,
    ) -> DriftSeverity | None:
        """Determine severity based on semantic path patterns."""
        for pattern in critical_paths:
            if self._match_pattern(path, pattern):
                return DriftSeverity.CRITICAL
        for pattern in high_paths:
            if self._match_pattern(path, pattern):
                return DriftSeverity.HIGH
        for pattern in medium_paths:
            if self._match_pattern(path, pattern):
                return DriftSeverity.MEDIUM
        return None
