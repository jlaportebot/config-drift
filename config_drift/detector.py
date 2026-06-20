"""Drift detection logic for comparing environments."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from config_drift.models import (
    ConfigResource,
    Drift,
    DriftReport,
    DriftSeverity,
    Environment,
)


@dataclass(frozen=True)
class DriftRule:
    """A rule for determining drift severity."""

    field_path: str
    severity: DriftSeverity
    condition: Callable[[Any, Any], bool] | None = None
    description: str = ""

    def matches(self, field_path: str) -> bool:
        """Check if this rule matches the given field path."""
        return self.field_path == field_path or self.field_path == "*"


# Default severity rules for common Kubernetes fields
DEFAULT_SEVERITY_RULES: list[DriftRule] = [
    DriftRule("*.image", DriftSeverity.CRITICAL, description="Container image changed"),
    DriftRule("*.replicas", DriftSeverity.ERROR, description="Replica count changed"),
    DriftRule("*.resources.limits.*", DriftSeverity.WARNING, description="Resource limits changed"),
    DriftRule(
        "*.resources.requests.*", DriftSeverity.WARNING, description="Resource requests changed"
    ),
    DriftRule("*.env[*].*", DriftSeverity.ERROR, description="Environment variable changed"),
    DriftRule("*.command", DriftSeverity.CRITICAL, description="Container command changed"),
    DriftRule("*.args", DriftSeverity.ERROR, description="Container args changed"),
    DriftRule("*.ports[*].*", DriftSeverity.WARNING, description="Port configuration changed"),
    DriftRule("*.volumeMounts[*].*", DriftSeverity.WARNING, description="Volume mounts changed"),
    DriftRule("*.volumes[*].*", DriftSeverity.WARNING, description="Volumes changed"),
    DriftRule("*.nodeSelector", DriftSeverity.WARNING, description="Node selector changed"),
    DriftRule("*.affinity.*", DriftSeverity.WARNING, description="Affinity rules changed"),
    DriftRule("*.tolerations[*].*", DriftSeverity.WARNING, description="Tolerations changed"),
    DriftRule("*.metadata.annotations.*", DriftSeverity.INFO, description="Annotation changed"),
    DriftRule("*.metadata.labels.*", DriftSeverity.INFO, description="Label changed"),
    DriftRule("*", DriftSeverity.INFO, description="Other field changed"),
]


def _normalize_path(path: str) -> str:
    """Normalize a field path by removing array indices for pattern matching."""
    # Replace [0], [1], etc. with [*]
    return re.sub(r"\[\d+\]", "[*]", path)


def _wildcard_match(pattern: str, path: str) -> bool:
    """Simple wildcard matching for field paths."""
    # Normalize both pattern and path to handle array indices
    norm_path = _normalize_path(path)
    norm_pattern = _normalize_path(pattern)

    if norm_pattern == "*":
        return True

    # Handle patterns with wildcards using regex
    if "*" in norm_pattern or "?" in norm_pattern:
        # Escape regex special chars except * and . which we handle
        # First escape [ and ] which are special in regex
        escaped = norm_pattern.replace("[", r"\[").replace("]", r"\]")
        regex = escaped.replace(".", r"\.").replace("*", ".*")
        return bool(re.fullmatch(regex, norm_path))

    return norm_pattern == norm_path


class DriftDetector:
    """Detect configuration drift between environments."""

    def __init__(self, severity_rules: list[DriftRule] | None = None):
        self.severity_rules = severity_rules or DEFAULT_SEVERITY_RULES

    def compare_environments(self, source: Environment, target: Environment) -> DriftReport:
        """Compare two environments and generate a drift report."""
        drifts: list[Drift] = []

        source_resources = self._collect_resources(source)
        target_resources = self._collect_resources(target)

        all_identifiers = set(source_resources.keys()) | set(target_resources.keys())

        for identifier in all_identifiers:
            source_res = source_resources.get(identifier)
            target_res = target_resources.get(identifier)

            if source_res is None:
                drifts.append(
                    self._create_drift(
                        identifier=identifier,
                        source_res=source_res,
                        target_res=target_res,
                        field_path="__resource__",
                        source_value=None,
                        target_value="<present>",
                        severity=DriftSeverity.WARNING,
                        source_env=source.name,
                        target_env=target.name,
                        description=f"Resource added in {target.name}",
                    )
                )
                continue

            if target_res is None:
                drifts.append(
                    self._create_drift(
                        identifier=identifier,
                        source_res=source_res,
                        target_res=target_res,
                        field_path="__resource__",
                        source_value="<present>",
                        target_value=None,
                        severity=DriftSeverity.ERROR,
                        source_env=source.name,
                        target_env=target.name,
                        description=f"Resource removed in {target.name}",
                    )
                )
                continue

            resource_drifts = self._compare_resources(
                source_res, target_res, source.name, target.name
            )
            drifts.extend(resource_drifts)

        return DriftReport(
            source_env=source,
            target_env=target,
            drifts=drifts,
        )

    def _collect_resources(self, env: Environment) -> dict[str, ConfigResource]:
        resources = {}
        for config_file in env.config_files:
            for resource in config_file.resources:
                resources[resource.identifier] = resource
        return resources

    def _compare_resources(
        self,
        source: ConfigResource,
        target: ConfigResource,
        source_env_name: str,
        target_env_name: str,
    ) -> list[Drift]:
        drifts: list[Drift] = []

        source_data = source.data
        target_data = target.data

        source_flat = self._flatten_dict(source_data)
        target_flat = self._flatten_dict(target_data)

        all_keys = set(source_flat.keys()) | set(target_flat.keys())

        for key in all_keys:
            source_val = source_flat.get(key)
            target_val = target_flat.get(key)

            if source_val == target_val:
                continue

            if source_val is None:
                severity = self._determine_severity(key, "added")
                drifts.append(
                    self._create_drift(
                        identifier=source.identifier,
                        source_res=source,
                        target_res=target,
                        field_path=key,
                        source_value=None,
                        target_value=target_val,
                        severity=severity,
                        source_env=source_env_name,
                        target_env=target_env_name,
                        description=f"Field '{key}' added in {target_env_name}",
                    )
                )
            elif target_val is None:
                severity = self._determine_severity(key, "removed")
                drifts.append(
                    self._create_drift(
                        identifier=source.identifier,
                        source_res=source,
                        target_res=target,
                        field_path=key,
                        source_value=source_val,
                        target_value=None,
                        severity=severity,
                        source_env=source_env_name,
                        target_env=target_env_name,
                        description=f"Field '{key}' removed in {target_env_name}",
                    )
                )
            else:
                severity = self._determine_severity(key, "changed")
                drifts.append(
                    self._create_drift(
                        identifier=source.identifier,
                        source_res=source,
                        target_res=target,
                        field_path=key,
                        source_value=source_val,
                        target_value=target_val,
                        severity=severity,
                        source_env=source_env_name,
                        target_env=target_env_name,
                        description=f"Field '{key}' changed from '{source_val}' to '{target_val}'",
                    )
                )

        return drifts

    def _flatten_dict(self, data: Any, prefix: str = "") -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in data.items():
            new_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, Mapping):
                result.update(self._flatten_dict(value, new_key))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, Mapping):
                        result.update(self._flatten_dict(item, f"{new_key}[{i}]"))
                    else:
                        result[f"{new_key}[{i}]"] = item
            else:
                result[new_key] = value
        return result

    def _determine_severity(self, field_path: str, change_type: str) -> DriftSeverity:
        for rule in self.severity_rules:
            if _wildcard_match(rule.field_path, field_path) and (
                rule.condition is None or rule.condition(change_type, field_path)
            ):
                return rule.severity
        return DriftSeverity.INFO

    def _create_drift(
        self,
        identifier: str,
        source_res: ConfigResource | None,
        target_res: ConfigResource | None,
        field_path: str,
        source_value: Any,
        target_value: Any,
        severity: DriftSeverity,
        source_env: str,
        target_env: str,
        description: str,
    ) -> Drift:
        resource_kind = ""
        resource_name = ""
        namespace = None

        if source_res:
            resource_kind = source_res.kind
            resource_name = source_res.name
            namespace = source_res.namespace
        elif target_res:
            resource_kind = target_res.kind
            resource_name = target_res.name
            namespace = target_res.namespace

        return Drift(
            resource_identifier=identifier,
            resource_kind=resource_kind,
            resource_name=resource_name,
            namespace=namespace,
            field_path=field_path,
            source_value=source_value,
            target_value=target_value,
            severity=severity,
            source_env=source_env,
            target_env=target_env,
            description=description,
        )
