"""Parser for local configuration files."""

import json
from pathlib import Path

import yaml

from config_drift.models.config import ConfigFormat, ConfigSource, ParsedConfig
from config_drift.parsers.base import ConfigParser, ParseResult


class FileParser(ConfigParser):
    """Parser for local configuration files (YAML, JSON)."""

    @property
    def source_type(self) -> ConfigSource:
        return ConfigSource.FILE

    @property
    def supported_formats(self) -> list[ConfigFormat]:
        return [ConfigFormat.YAML, ConfigFormat.JSON]

    def parse(self, source: str | Path, **kwargs) -> ParseResult:
        path = Path(source)
        configs = []
        errors = []

        if path.is_file():
            config = self._parse_file(path)
            if config:
                configs.append(config)
            else:
                errors.append(f"Failed to parse {path}")
        elif path.is_dir():
            for ext in ["*.yaml", "*.yml", "*.json"]:
                for file_path in path.rglob(ext):
                    config = self._parse_file(file_path)
                    if config:
                        configs.append(config)
                    else:
                        errors.append(f"Failed to parse {file_path}")
        else:
            errors.append(f"Path does not exist: {path}")

        return ParseResult(configs=configs, errors=errors)

    def _parse_file(self, file_path: Path) -> ParsedConfig | None:
        try:
            raw_content = file_path.read_text(encoding="utf-8")
            if not raw_content.strip():
                return None

            if file_path.suffix.lower() in [".yaml", ".yml"]:
                content = yaml.safe_load(raw_content)
                fmt = ConfigFormat.YAML
            elif file_path.suffix.lower() == ".json":
                content = json.loads(raw_content)
                fmt = ConfigFormat.JSON
            else:
                return None

            if not isinstance(content, dict):
                return None

            return self._create_parsed_config(
                content=content,
                file_path=file_path,
                resource_id=str(file_path.relative_to(file_path.anchor)),
                raw_content=raw_content,
                format=fmt,
            )
        except Exception:
            return None
