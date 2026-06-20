"""Tests for Helm parser."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from config_drift.models.config import ConfigFormat, ConfigSource
from config_drift.parsers.helm import HelmParser


class TestHelmParser:
    """Tests for HelmParser."""

    def test_source_type(self):
        parser = HelmParser()
        assert parser.source_type == ConfigSource.HELM

    def test_supported_formats(self):
        parser = HelmParser()
        assert parser.supported_formats == [ConfigFormat.YAML]

    def test_can_parse_chart_yaml(self, tmp_path):
        parser = HelmParser()
        chart_file = tmp_path / "Chart.yaml"
        chart_file.write_text("name: my-chart\nversion: 1.0.0\n")
        # The parser checks directory, not file
        assert parser.can_parse(tmp_path) is False  # directories not checked by can_parse

    def test_parse_nonexistent_path(self):
        parser = HelmParser()
        result = parser.parse("/nonexistent/path")
        assert len(result.errors) > 0

    def test_parse_chart_directory(self, tmp_path):
        parser = HelmParser()
        chart_dir = tmp_path / "my-chart"
        chart_dir.mkdir()
        (chart_dir / "Chart.yaml").write_text(
            "name: my-chart\nversion: 1.0.0\nappVersion: 1.0.0\ndescription: Test chart\n"
        )
        (chart_dir / "values.yaml").write_text("replicaCount: 3\nimage: nginx\n")

        with patch("config_drift.parsers.helm.Chart") as mock_chart_class:
            mock_chart = Mock()
            mock_chart.metadata = Mock()
            mock_chart.metadata.name = "my-chart"
            mock_chart.metadata.version = "1.0.0"
            mock_chart.metadata.app_version = "1.0.0"
            mock_chart.metadata.description = "Test chart"
            mock_chart.values = {"replicaCount": 3, "image": "nginx"}
            mock_chart_class.from_path.return_value = mock_chart

            result = parser.parse(str(chart_dir))
            assert len(result.configs) == 1
            assert result.configs[0].resource_id == "chart/my-chart"
            assert result.configs[0].content["metadata"]["name"] == "my-chart"

    def test_parse_chart_directory_no_chart_yaml(self, tmp_path):
        parser = HelmParser()
        chart_dir = tmp_path / "my-chart"
        chart_dir.mkdir()
        # No Chart.yaml
        result = parser.parse(str(chart_dir))
        assert len(result.configs) == 0
        assert len(result.errors) > 0

    @patch("config_drift.parsers.helm.Client")
    def test_parse_releases(self, mock_client_class):
        parser = HelmParser()
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_release = Mock()
        mock_release.name = "my-release"
        mock_release.revision = 5
        mock_release.chart = "my-chart-1.0.0"

        mock_loop = Mock()
        mock_loop.is_running.return_value = False
        mock_loop.run_until_complete.return_value = [mock_release]

        with (
            patch("asyncio.get_event_loop", return_value=mock_loop),
            patch("config_drift.parsers.helm.Client", return_value=mock_client),
        ):
            result = parser.parse("releases", namespace="default")
            assert len(result.configs) == 1
            assert result.configs[0].resource_id == "release/my-release"

    @patch("config_drift.parsers.helm.Client")
    def test_parse_specific_releases(self, mock_client_class):
        parser = HelmParser()
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_release = Mock()
        mock_release.name = "specific-release"
        mock_release.revision = 2
        mock_release.chart = "chart-1.0.0"

        mock_loop = Mock()
        mock_loop.is_running.return_value = False

        async def mock_get_release(release_name, namespace):
            return mock_release

        mock_loop.run_until_complete.side_effect = [
            ["specific-release"],  # list_releases
            mock_release,  # get_release
        ]

        with patch("asyncio.get_event_loop", return_value=mock_loop):
            result = parser.parse("releases", namespace="default", releases=["specific-release"])
            assert len(result.configs) == 1
            assert result.configs[0].resource_id == "release/specific-release"

    def test_parse_chart_with_exception(self, tmp_path):
        parser = HelmParser()
        chart_dir = tmp_path / "my-chart"
        chart_dir.mkdir()
        (chart_dir / "Chart.yaml").write_text("name: my-chart\nversion: 1.0.0\n")

        with patch("config_drift.parsers.helm.Chart") as mock_chart_class:
            mock_chart_class.from_path.side_effect = Exception("Chart parse error")
            result = parser.parse(str(chart_dir))
            assert len(result.configs) == 0
            assert len(result.errors) > 0

    def test_list_releases_empty(self):
        parser = HelmParser()
        mock_client = Mock()
        mock_loop = Mock()
        mock_loop.is_running.return_value = True  # Running loop, can't run

        with (
            patch("config_drift.parsers.helm.Client", return_value=mock_client),
            patch("asyncio.get_event_loop", return_value=mock_loop),
        ):
            releases = parser._list_releases(mock_client, "default")  # noqa: SLF001
            assert releases == []

    def test_parse_release_with_exception(self):
        parser = HelmParser()
        mock_client = Mock()
        mock_loop = Mock()
        mock_loop.is_running.return_value = False
        mock_loop.run_until_complete.side_effect = Exception("Release not found")

        with (
            patch("config_drift.parsers.helm.Client", return_value=mock_client),
            patch("asyncio.get_event_loop", return_value=mock_loop),
        ):
            result = parser._parse_release(mock_client, "bad-release", "default")  # noqa: SLF001
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
