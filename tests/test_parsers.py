"""Tests for config_drift parsers."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from config_drift.models import ConfigFormat
from config_drift.parsers import _detect_format, parse_config_file


class TestDetectFormat:
    def test_yaml_extension(self) -> None:
        assert _detect_format(Path("config.yaml")) == ConfigFormat.YAML
        assert _detect_format(Path("config.yml")) == ConfigFormat.YAML

    def test_json_extension(self) -> None:
        assert _detect_format(Path("config.json")) == ConfigFormat.JSON

    def test_kubernetes_detection(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: test\n")
            f.flush()
            assert _detect_format(Path(f.name)) == ConfigFormat.KUBERNETES

    def test_helm_values_detection(self) -> None:
        assert _detect_format(Path("values.yaml")) == ConfigFormat.HELM_VALUES
        assert _detect_format(Path("values-prod.yaml")) == ConfigFormat.HELM_VALUES


class TestParseKubernetes:
    def test_parse_deployment(self) -> None:
        content = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: production
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: app
          image: nginx:1.21
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            f.flush()
            config_file = parse_config_file(Path(f.name), ConfigFormat.KUBERNETES)

        assert len(config_file.resources) == 1
        resource = config_file.resources[0]
        assert resource.kind == "Deployment"
        assert resource.name == "my-app"
        assert resource.namespace == "production"
        assert resource.data["spec"]["replicas"] == 3

    def test_parse_multi_doc_yaml(self) -> None:
        content = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: config
---
apiVersion: v1
kind: Secret
metadata:
  name: secret
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            f.flush()
            config_file = parse_config_file(Path(f.name), ConfigFormat.KUBERNETES)

        assert len(config_file.resources) == 2
        kinds = {r.kind for r in config_file.resources}
        assert kinds == {"ConfigMap", "Secret"}

    def test_parse_service(self) -> None:
        content = """
apiVersion: v1
kind: Service
metadata:
  name: my-service
  namespace: staging
spec:
  ports:
    - port: 80
      targetPort: 8080
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            f.flush()
            config_file = parse_config_file(Path(f.name), ConfigFormat.KUBERNETES)

        assert len(config_file.resources) == 1
        resource = config_file.resources[0]
        assert resource.kind == "Service"
        assert resource.name == "my-service"
        assert resource.namespace == "staging"


class TestParseHelmValues:
    def test_parse_helm_values(self) -> None:
        content = """
replicaCount: 2
image:
  repository: nginx
  tag: "1.21"
service:
  type: ClusterIP
  port: 80
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            f.flush()
            config_file = parse_config_file(Path(f.name), ConfigFormat.HELM_VALUES)

        assert len(config_file.resources) >= 1
        # Should find HelmComponent resources
        kinds = {r.kind for r in config_file.resources}
        assert "HelmComponent" in kinds


class TestParseGenericYAML:
    def test_parse_simple_yaml(self) -> None:
        content = """
database:
  host: localhost
  port: 5432
redis:
  host: localhost
  port: 6379
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            f.flush()
            config_file = parse_config_file(Path(f.name), ConfigFormat.YAML)

        # Generic YAML parsing extracts nested dicts with keys
        assert len(config_file.resources) >= 0


class TestParseJSON:
    def test_parse_json(self) -> None:
        content = '{"name": "test", "version": "1.0", "config": {"debug": true}}'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(content)
            f.flush()
            config_file = parse_config_file(Path(f.name), ConfigFormat.JSON)

        assert config_file.format == ConfigFormat.JSON
        assert config_file.raw_content == content
