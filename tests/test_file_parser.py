"""Tests for the file parser."""

import json
from pathlib import Path

import pytest

from config_drift.models.config import ConfigFormat, ConfigSource
from config_drift.parsers.file import FileParser


@pytest.fixture
def tmp_dir(tmp_path):
    """Create a temporary directory with test config files."""
    # YAML file
    (tmp_path / "config.yaml").write_text("key: value\nnested:\n  a: 1\n  b: 2\n")
    # JSON file
    (tmp_path / "config.json").write_text(json.dumps({"key": "value", "port": 8080}))
    # Empty file
    (tmp_path / "empty.yaml").write_text("")
    # Invalid YAML
    (tmp_path / "invalid.yaml").write_text("key: [invalid\n")
    # Non-config file
    (tmp_path / "readme.txt").write_text("This is not a config file")
    # Nested YAML
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "nested.yaml").write_text("app: myapp\nenv: production\n")
    return tmp_path


class TestFileParser:
    """Tests for FileParser."""

    def test_source_type(self):
        parser = FileParser()
        assert parser.source_type == ConfigSource.FILE

    def test_supported_formats(self):
        parser = FileParser()
        assert ConfigFormat.YAML in parser.supported_formats
        assert ConfigFormat.JSON in parser.supported_formats

    def test_parse_yaml_file(self, tmp_dir):
        parser = FileParser()
        result = parser.parse(tmp_dir / "config.yaml")
        assert len(result.configs) == 1
        assert result.configs[0].content["key"] == "value"
        assert result.configs[0].content["nested"]["a"] == 1
        assert result.configs[0].format == ConfigFormat.YAML

    def test_parse_json_file(self, tmp_dir):
        parser = FileParser()
        result = parser.parse(tmp_dir / "config.json")
        assert len(result.configs) == 1
        assert result.configs[0].content["key"] == "value"
        assert result.configs[0].content["port"] == 8080
        assert result.configs[0].format == ConfigFormat.JSON

    def test_parse_directory(self, tmp_dir):
        parser = FileParser()
        result = parser.parse(tmp_dir)
        assert len(result.configs) >= 2  # At least config.yaml and config.json

    def test_parse_empty_file(self, tmp_dir):
        parser = FileParser()
        result = parser.parse(tmp_dir / "empty.yaml")
        assert len(result.configs) == 0

    def test_parse_invalid_file(self, tmp_dir):
        parser = FileParser()
        result = parser.parse(tmp_dir / "invalid.yaml")
        assert len(result.configs) == 0

    def test_parse_nonexistent_path(self, tmp_dir):
        parser = FileParser()
        result = parser.parse(tmp_dir / "nonexistent.yaml")
        assert len(result.configs) == 0
        assert len(result.errors) > 0

    def test_can_parse_yaml(self):
        parser = FileParser()
        assert parser.can_parse(Path("config.yaml")) is True
        assert parser.can_parse(Path("config.yml")) is True

    def test_can_parse_json(self):
        parser = FileParser()
        assert parser.can_parse(Path("config.json")) is True

    def test_cannot_parse_other(self):
        parser = FileParser()
        assert parser.can_parse(Path("config.txt")) is False
        assert parser.can_parse(Path("config.toml")) is False

    def test_parsed_config_metadata(self, tmp_dir):
        parser = FileParser()
        result = parser.parse(tmp_dir / "config.yaml")
        assert len(result.configs) == 1
        config = result.configs[0]
        assert config.source == ConfigSource.FILE
        assert config.file_path is not None
        assert config.raw_content != ""

    def test_parse_nested_directory(self, tmp_dir):
        parser = FileParser()
        result = parser.parse(tmp_dir)
        # Should find subdir/nested.yaml
        nested_configs = [c for c in result.configs if c.content.get("app") == "myapp"]
        assert len(nested_configs) == 1
