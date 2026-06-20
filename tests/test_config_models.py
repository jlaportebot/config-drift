"""Tests for configuration models."""

from datetime import datetime
from pathlib import Path

from config_drift.models.config import ConfigFormat, ConfigSource, ParsedConfig


class TestConfigSource:
    """Tests for ConfigSource enum."""

    def test_values(self):
        assert ConfigSource.KUBERNETES.value == "kubernetes"
        assert ConfigSource.DOCKER_COMPOSE.value == "docker_compose"
        assert ConfigSource.TERRAFORM.value == "terraform"
        assert ConfigSource.HELM.value == "helm"
        assert ConfigSource.FILE.value == "file"

    def test_from_string(self):
        assert ConfigSource("kubernetes") == ConfigSource.KUBERNETES


class TestConfigFormat:
    """Tests for ConfigFormat enum."""

    def test_values(self):
        assert ConfigFormat.YAML.value == "yaml"
        assert ConfigFormat.JSON.value == "json"
        assert ConfigFormat.HCL.value == "hcl"


class TestParsedConfig:
    """Tests for ParsedConfig dataclass."""

    def test_creation(self):
        config = ParsedConfig(
            source=ConfigSource.KUBERNETES,
            format=ConfigFormat.YAML,
            content={"apiVersion": "v1", "kind": "ConfigMap"},
        )
        assert config.source == ConfigSource.KUBERNETES
        assert config.format == ConfigFormat.YAML
        assert config.content == {"apiVersion": "v1", "kind": "ConfigMap"}
        assert config.resource_id is None
        assert config.namespace is None

    def test_with_metadata(self):
        config = ParsedConfig(
            source=ConfigSource.FILE,
            format=ConfigFormat.YAML,
            content={"key": "value"},
            file_path=Path("/tmp/config.yaml"),
            resource_id="config/my-app",
            namespace="default",
            labels={"app": "my-app"},
            annotations={"note": "example"},
        )
        assert config.file_path == Path("/tmp/config.yaml")
        assert config.resource_id == "config/my-app"
        assert config.namespace == "default"
        assert config.labels == {"app": "my-app"}
        assert config.annotations == {"note": "example"}

    def test_to_dict(self):
        config = ParsedConfig(
            source=ConfigSource.KUBERNETES,
            format=ConfigFormat.YAML,
            content={"key": "value"},
            resource_id="cm/my-config",
        )
        result = config.to_dict()
        assert result["source"] == "kubernetes"
        assert result["format"] == "yaml"
        assert result["content"] == {"key": "value"}
        assert result["resource_id"] == "cm/my-config"

    def test_from_dict(self):
        data = {
            "source": "kubernetes",
            "format": "yaml",
            "content": {"key": "value"},
            "file_path": "/tmp/config.yaml",
            "resource_id": "cm/my-config",
            "namespace": "default",
            "labels": {"app": "test"},
            "annotations": {},
            "parsed_at": datetime.utcnow().isoformat(),
            "raw_content": "key: value",
        }
        config = ParsedConfig.from_dict(data)
        assert config.source == ConfigSource.KUBERNETES
        assert config.format == ConfigFormat.YAML
        assert config.content == {"key": "value"}
        assert config.resource_id == "cm/my-config"
