"""Core data models for Config Drift."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class DriftSeverity(StrEnum):
    """Severity levels for configuration drift."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ConfigFormat(StrEnum):
    """Supported configuration file formats."""

    YAML = "yaml"
    JSON = "json"
    TOML = "toml"
    HCL = "hcl"
    ENV = "env"
    DOCKERFILE = "dockerfile"
    HELM_VALUES = "helm-values"
    KUBERNETES = "kubernetes"


@dataclass(frozen=True)
class ConfigResource:
    """A single configuration resource within a file."""

    kind: str
    name: str
    namespace: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    path: str = ""  # JSONPath or similar within the file

    @property
    def identifier(self) -> str:
        """Unique identifier for this resource."""
        parts = [self.kind]
        if self.namespace:
            parts.append(self.namespace)
        parts.append(self.name)
        return "/".join(parts)


@dataclass(frozen=True)
class ConfigFile:
    """A parsed configuration file."""

    path: Path
    format: ConfigFormat
    resources: list[ConfigResource] = field(default_factory=list)
    raw_content: str = ""
    parsed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get_resource(
        self, kind: str, name: str, namespace: str | None = None
    ) -> ConfigResource | None:
        """Find a resource by kind, name, and optional namespace."""
        for resource in self.resources:
            if resource.kind == kind and resource.name == name and resource.namespace == namespace:
                return resource
        return None


@dataclass(frozen=True)
class Environment:
    """An environment (e.g., dev, staging, prod) with its config files."""

    name: str
    config_files: list[ConfigFile] = field(default_factory=list)

    def get_resource(
        self, kind: str, name: str, namespace: str | None = None
    ) -> ConfigResource | None:
        """Find a resource across all config files in this environment."""
        for config_file in self.config_files:
            resource = config_file.get_resource(kind, name, namespace)
            if resource:
                return resource
        return None


@dataclass(frozen=True)
class Drift:
    """A single drift detection between environments."""

    resource_identifier: str
    resource_kind: str
    resource_name: str
    namespace: str | None
    field_path: str
    source_value: Any
    target_value: Any
    severity: DriftSeverity
    source_env: str
    target_env: str
    description: str = ""

    @property
    def is_breaking(self) -> bool:
        """Whether this drift is a breaking change."""
        return self.severity in (DriftSeverity.ERROR, DriftSeverity.CRITICAL)


@dataclass(frozen=True)
class DriftReport:
    """Complete drift report between two environments."""

    source_env: Environment
    target_env: Environment
    drifts: list[Drift] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def drift_count(self) -> int:
        return len(self.drifts)

    @property
    def critical_count(self) -> int:
        return sum(1 for d in self.drifts if d.severity == DriftSeverity.CRITICAL)

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.drifts if d.severity == DriftSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.drifts if d.severity == DriftSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for d in self.drifts if d.severity == DriftSeverity.INFO)

    @property
    def has_breaking_changes(self) -> bool:
        return any(d.is_breaking for d in self.drifts)

    def get_drifts_by_severity(self, severity: DriftSeverity) -> list[Drift]:
        return [d for d in self.drifts if d.severity == severity]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_env": self.source_env.name,
            "target_env": self.target_env.name,
            "generated_at": self.generated_at.isoformat(),
            "summary": {
                "total": self.drift_count,
                "critical": self.critical_count,
                "error": self.error_count,
                "warning": self.warning_count,
                "info": self.info_count,
                "has_breaking_changes": self.has_breaking_changes,
            },
            "drifts": [
                {
                    "resource_identifier": d.resource_identifier,
                    "resource_kind": d.resource_kind,
                    "resource_name": d.resource_name,
                    "namespace": d.namespace,
                    "field_path": d.field_path,
                    "source_value": d.source_value,
                    "target_value": d.target_value,
                    "severity": d.severity.value,
                    "source_env": d.source_env,
                    "target_env": d.target_env,
                    "description": d.description,
                    "is_breaking": d.is_breaking,
                }
                for d in self.drifts
            ],
        }
