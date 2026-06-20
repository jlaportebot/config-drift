"""Parsers for various configuration file formats."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from config_drift.models import ConfigFile, ConfigFormat, ConfigResource


def parse_config_file(path: Path, format: ConfigFormat | None = None) -> ConfigFile:
    """Parse a configuration file and extract resources."""
    if format is None:
        format = _detect_format(path)

    raw_content = path.read_text(encoding="utf-8")

    if format == ConfigFormat.YAML:
        return _parse_yaml(path, raw_content)
    elif format == ConfigFormat.JSON:
        return _parse_json(path, raw_content)
    elif format == ConfigFormat.HELM_VALUES:
        return _parse_helm_values(path, raw_content)
    elif format == ConfigFormat.KUBERNETES:
        return _parse_kubernetes(path, raw_content)
    else:
        # Generic parsing for other formats
        return ConfigFile(
            path=path,
            format=format,
            raw_content=raw_content,
        )


def _detect_format(path: Path) -> ConfigFormat:
    """Detect configuration format from file extension and content."""
    suffix = path.suffix.lower()

    if suffix in {".yaml", ".yml"}:
        # Check if it's a Helm values file
        if "values" in path.name.lower() or path.parent.name == "values":
            return ConfigFormat.HELM_VALUES
        # Check if it's Kubernetes by looking for apiVersion
        try:
            content = path.read_text(encoding="utf-8")[:500]
            if "apiVersion:" in content and "kind:" in content:
                return ConfigFormat.KUBERNETES
        except Exception:
            pass
        return ConfigFormat.YAML
    elif suffix == ".json":
        return ConfigFormat.JSON
    elif suffix in {".tf", ".tfvars", ".hcl"}:
        return ConfigFormat.HCL
    elif suffix in {".toml"}:
        return ConfigFormat.TOML
    elif suffix in {".env", ".envrc"} or path.name.startswith(".env"):
        return ConfigFormat.ENV
    elif path.name == "Dockerfile" or path.name.startswith("Dockerfile"):
        return ConfigFormat.DOCKERFILE
    else:
        return ConfigFormat.YAML  # Default


def _parse_yaml(path: Path, content: str) -> ConfigFile:
    """Parse YAML file, handling multi-document files."""
    resources = []
    try:
        docs = list(yaml.safe_load_all(content))
        for doc in docs:
            if doc is None:
                continue
            if isinstance(doc, dict):
                _extract_resources(doc, "", resources)
    except yaml.YAMLError:
        pass

    return ConfigFile(
        path=path,
        format=ConfigFormat.YAML,
        resources=resources,
        raw_content=content,
    )


def _parse_json(path: Path, content: str) -> ConfigFile:
    """Parse JSON file."""
    resources = []
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            _extract_resources(data, "", resources)
    except json.JSONDecodeError:
        pass

    return ConfigFile(
        path=path,
        format=ConfigFormat.JSON,
        resources=resources,
        raw_content=content,
    )


def _parse_helm_values(path: Path, content: str) -> ConfigFile:
    """Parse Helm values.yaml file."""
    resources = []
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict):
            _extract_helm_resources(data, "", resources)
    except yaml.YAMLError:
        pass

    return ConfigFile(
        path=path,
        format=ConfigFormat.HELM_VALUES,
        resources=resources,
        raw_content=content,
    )


def _parse_kubernetes(path: Path, content: str) -> ConfigFile:
    """Parse Kubernetes manifest file."""
    resources = []
    try:
        docs = list(yaml.safe_load_all(content))
        for doc in docs:
            if doc is None:
                continue
            if isinstance(doc, dict) and "apiVersion" in doc and "kind" in doc:
                metadata = doc.get("metadata", {})
                resource = ConfigResource(
                    kind=doc["kind"],
                    name=metadata.get("name", ""),
                    namespace=metadata.get("namespace"),
                    data=doc,
                    path="",
                )
                resources.append(resource)
    except yaml.YAMLError:
        pass

    return ConfigFile(
        path=path,
        format=ConfigFormat.KUBERNETES,
        resources=resources,
        raw_content=content,
    )


def _extract_resources(data: Any, prefix: str, resources: list[ConfigResource]) -> None:
    """Recursively extract resources from a nested dictionary."""
    if "kind" in data and "metadata" in data:
        metadata = data["metadata"]
        if isinstance(metadata, Mapping):
            resource = ConfigResource(
                kind=data["kind"],
                name=metadata.get("name", ""),
                namespace=metadata.get("namespace"),
                data=dict(data),  # Convert to dict for storage
                path=prefix,
            )
            resources.append(resource)
            return

    for key, value in data.items():
        new_prefix = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            _extract_resources(value, new_prefix, resources)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, Mapping):
                    _extract_resources(item, f"{new_prefix}[{i}]", resources)


def _extract_helm_resources(
    data: Any, prefix: str, resources: list[ConfigResource]
) -> None:
    """Extract resources from Helm values structure."""
    for key, value in data.items():
        new_prefix = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            # In Helm values, any top-level dict is a component configuration
            resource = ConfigResource(
                kind="HelmComponent",
                name=key,
                namespace=None,
                data=dict(value),  # Convert to dict for storage
                path=new_prefix,
            )
            resources.append(resource)
            _extract_helm_resources(value, new_prefix, resources)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, Mapping):
                    _extract_helm_resources(item, f"{new_prefix}[{i}]", resources)
