"""File-based storage for baselines (JSON/YAML files)."""

from pathlib import Path
from typing import Optional

import yaml

from config_drift.models.config import ParsedConfig


class FileStore:
    """File-based storage for baselines."""

    def __init__(self, base_path: str | Path = "baselines"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_baseline_path(
        self, source: str, resource_id: str, namespace: str | None = None
    ) -> Path:
        """Get the file path for a baseline."""
        safe_resource = resource_id.replace("/", "_").replace(":", "_")
        if namespace:
            safe_namespace = namespace.replace("/", "_")
            return self.base_path / source / safe_namespace / f"{safe_resource}.yaml"
        return self.base_path / source / f"{safe_resource}.yaml"

    def save_baseline(self, config: ParsedConfig) -> str:
        """Save a baseline to a YAML file."""
        file_path = self._get_baseline_path(
            config.source.value, config.resource_id, config.namespace
        )
        file_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "source": config.source.value,
            "format": config.format.value,
            "content": config.content,
            "resource_id": config.resource_id,
            "namespace": config.namespace,
            "labels": config.labels,
            "annotations": config.annotations,
            "parsed_at": config.parsed_at.isoformat(),
        }

        with file_path.open("w") as f:
            yaml.dump(data, f, sort_keys=False)

        return str(file_path)

    def get_baseline(
        self, source: str, resource_id: str, namespace: str | None = None
    ) -> Optional[ParsedConfig]:
        """Retrieve a baseline from a YAML file."""
        file_path = self._get_baseline_path(source, resource_id, namespace)
        if not file_path.exists():
            return None

        with file_path.open("r") as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        return ParsedConfig.from_dict(data)

    def list_baselines(self, source: str | None = None) -> list[dict]:
        """List all baselines."""
        results = []
        search_path = self.base_path / source if source else self.base_path

        if not search_path.exists():
            return results

        for yaml_file in search_path.rglob("*.yaml"):
            try:
                with yaml_file.open("r") as f:
                    data = yaml.safe_load(f)
                if data:
                    results.append(
                        {
                            "id": f"{data['source']}/{data['resource_id']}",
                            "source": data["source"],
                            "resource_id": data["resource_id"],
                            "namespace": data.get("namespace"),
                            "parsed_at": data.get("parsed_at"),
                        }
                    )
            except Exception:
                continue

        return sorted(results, key=lambda x: x.get("parsed_at", ""), reverse=True)

    def delete_baseline(self, source: str, resource_id: str, namespace: str | None = None) -> bool:
        """Delete a baseline file."""
        file_path = self._get_baseline_path(source, resource_id, namespace)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
