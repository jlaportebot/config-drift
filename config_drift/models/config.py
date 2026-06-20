"""Configuration source and parsed config models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class ConfigSource(str, Enum):
    """Source types for configurations."""

    KUBERNETES = "kubernetes"
    DOCKER_COMPOSE = "docker_compose"
    TERRAFORM = "terraform"
    HELM = "helm"
    FILE = "file"


class ConfigFormat(str, Enum):
    """Configuration file formats."""

    YAML = "yaml"
    JSON = "json"
    HCL = "hcl"
    TEXT = "text"


@dataclass
class ParsedConfig:
    """A parsed configuration with metadata."""

    source: ConfigSource
    format: ConfigFormat
    content: dict[str, Any]
    file_path: Optional[Path] = None
    resource_id: Optional[str] = None
    namespace: Optional[str] = None
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    parsed_at: datetime = field(default_factory=datetime.utcnow)
    raw_content: str = ""

    def to_dict(self) -> dict:
        return {
            "source": self.source.value,
            "format": self.format.value,
            "content": self.content,
            "file_path": str(self.file_path) if self.file_path else None,
            "resource_id": self.resource_id,
            "namespace": self.namespace,
            "labels": self.labels,
            "annotations": self.annotations,
            "parsed_at": self.parsed_at.isoformat(),
            "raw_content": self.raw_content,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ParsedConfig":
        from pathlib import Path

        return cls(
            source=ConfigSource(data["source"]),
            format=ConfigFormat(data["format"]),
            content=data["content"],
            file_path=Path(data["file_path"]) if data.get("file_path") else None,
            resource_id=data.get("resource_id"),
            namespace=data.get("namespace"),
            labels=data.get("labels", {}),
            annotations=data.get("annotations", {}),
            parsed_at=datetime.fromisoformat(data["parsed_at"])
            if data.get("parsed_at")
            else datetime.utcnow(),
            raw_content=data.get("raw_content", ""),
        )
