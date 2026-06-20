"""Base configuration parser interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config_drift.models.config import ConfigFormat, ConfigSource, ParsedConfig


@dataclass
class ParseResult:
    """Result of parsing a configuration source."""

    configs: list[ParsedConfig]
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class ConfigParser(ABC):
    """Abstract base class for configuration parsers."""

    @property
    @abstractmethod
    def source_type(self) -> ConfigSource:
        """Return the configuration source type this parser handles."""

    @property
    @abstractmethod
    def supported_formats(self) -> list[ConfigFormat]:
        """Return supported file formats."""

    @abstractmethod
    def parse(self, source: str | Path, **kwargs) -> ParseResult:
        """Parse configuration from source.

        Args:
            source: Path to file, directory, or connection string
            **kwargs: Additional parser-specific options

        Returns:
            ParseResult with list of parsed configs and any errors
        """

    def can_parse(self, path: Path) -> bool:
        """Check if this parser can handle the given path."""
        ext = path.suffix.lower().lstrip(".")
        for fmt in self.supported_formats:
            if ext == fmt.value or (ext == "yml" and fmt.value == "yaml"):
                return True
        return False

    def _create_parsed_config(
        self,
        content: dict[str, Any],
        file_path: Path | None = None,
        resource_id: str | None = None,
        namespace: str | None = None,
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
        raw_content: str = "",
        format: ConfigFormat | None = None,
    ) -> ParsedConfig:
        """Create a ParsedConfig with common metadata."""
        return ParsedConfig(
            source=self.source_type,
            format=format or ConfigFormat.YAML,
            content=content,
            file_path=file_path,
            resource_id=resource_id,
            namespace=namespace,
            labels=labels or {},
            annotations=annotations or {},
            raw_content=raw_content,
        )
