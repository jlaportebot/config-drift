"""Parser for Helm charts and releases."""

from pathlib import Path

import yaml
from pyhelm3 import Chart, Client

from config_drift.models.config import ConfigFormat, ConfigSource, ParsedConfig
from config_drift.parsers.base import ConfigParser, ParseResult


class HelmParser(ConfigParser):
    """Parser for Helm charts and releases."""

    @property
    def source_type(self) -> ConfigSource:
        return ConfigSource.HELM

    @property
    def supported_formats(self) -> list[ConfigFormat]:
        return [ConfigFormat.YAML]

    def __init__(self, kubeconfig: str | None = None):
        self.kubeconfig = kubeconfig
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = Client(kubeconfig=self.kubeconfig)
        return self._client

    def parse(self, source: str | Path, **kwargs) -> ParseResult:
        """Parse Helm chart or release.

        Args:
            source: Path to chart directory, or release name
            **kwargs:
                namespace: Kubernetes namespace (default: default)
                include_values: Include computed values
                releases: List of release names to fetch (if source is "releases")
        """
        configs = []
        errors = []

        try:
            client = self._get_client()
            namespace = kwargs.get("namespace", "default")

            if str(source) == "releases":
                releases = kwargs.get("releases")
                if not releases:
                    releases = self._list_releases(client, namespace)
                for release_name in releases:
                    config = self._parse_release(client, release_name, namespace)
                    if config:
                        configs.append(config)
                    else:
                        errors.append(f"Failed to parse release {release_name}")
            else:
                path = Path(source)
                if path.is_dir():
                    config = self._parse_chart(path, **kwargs)
                    if config:
                        configs.append(config)
                    else:
                        errors.append(f"Failed to parse chart at {path}")
                else:
                    errors.append(f"Path does not exist: {path}")

        except Exception as e:
            errors.append(f"Helm parse error: {e}")

        return ParseResult(configs=configs, errors=errors)

    def _list_releases(self, client: Client, namespace: str) -> list[str]:
        """List all Helm releases in a namespace."""
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                return []
            releases = loop.run_until_complete(client.list_releases(namespace=namespace))
            return [r.name for r in releases]
        except Exception:
            return []

    def _parse_release(
        self, client: Client, release_name: str, namespace: str
    ) -> ParsedConfig | None:
        """Parse a Helm release."""
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                return None

            async def _get_release():
                release = await client.get_release(release_name, namespace=namespace)
                return release

            release = loop.run_until_complete(_get_release())
            if not release:
                return None

            # Get release info
            release_data = {
                "name": release_name,
                "namespace": namespace,
                "revision": release.revision if hasattr(release, "revision") else None,
                "chart": release.chart if hasattr(release, "chart") else None,
            }

            raw_yaml = yaml.dump(release_data, sort_keys=False)

            return self._create_parsed_config(
                content=release_data,
                resource_id=f"release/{release_name}",
                namespace=namespace,
                raw_content=raw_yaml,
            )
        except Exception:
            return None

    def _parse_chart(self, chart_path: Path, **kwargs) -> ParsedConfig | None:
        """Parse a Helm chart directory."""
        try:
            chart = Chart.from_path(str(chart_path))
            if not chart:
                return None

            # Get chart metadata
            metadata = chart.metadata

            content = {
                "metadata": {
                    "name": metadata.name,
                    "version": metadata.version,
                    "appVersion": metadata.app_version,
                    "description": metadata.description,
                },
                "values": chart.values if hasattr(chart, "values") else {},
            }

            raw_yaml = yaml.dump(content, sort_keys=False)

            return self._create_parsed_config(
                content=content,
                file_path=chart_path,
                resource_id=f"chart/{metadata.name}",
                raw_content=raw_yaml,
            )
        except Exception:
            return None
