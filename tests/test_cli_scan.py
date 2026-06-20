"""Tests for scan CLI command."""

from click.testing import CliRunner

from config_drift.cli.main import app


class TestScanCommand:
    """Tests for scan command."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_scan_help(self):
        result = self.runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        assert "Scan configuration sources for drift" in result.output

    def test_scan_no_source_defaults_to_file(self):
        """Test scan defaults to file source when no source specified."""
        result = self.runner.invoke(app, ["scan", "--path", "nonexistent"])
        # Should not crash, may show "No configurations found"
        assert result.exit_code in [0, 1]

    def test_scan_file_source_yaml(self, tmp_path):
        """Test scanning a YAML file."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")

        result = self.runner.invoke(app, ["scan", "--source", "file", "--path", str(test_file)])
        assert result.exit_code == 0
        assert "ConfigMap" in result.output or "config" in result.output.lower()

    def test_scan_file_source_json(self, tmp_path):
        """Test scanning a JSON file."""
        test_file = tmp_path / "config.json"
        test_file.write_text('{"apiVersion": "v1", "kind": "Secret", "data": {"key": "dmFsdWU="}}')

        result = self.runner.invoke(app, ["scan", "--source", "file", "--path", str(test_file)])
        assert result.exit_code == 0

    def test_scan_multiple_paths(self, tmp_path):
        """Test scanning multiple paths."""
        file1 = tmp_path / "config1.yaml"
        file1.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value1\n")
        file2 = tmp_path / "config2.yaml"
        file2.write_text("apiVersion: v1\nkind: Secret\ndata:\n  key: dmFsdWUy\n")

        result = self.runner.invoke(
            app, ["scan", "--source", "file", "--path", str(file1), "--path", str(file2)]
        )
        assert result.exit_code == 0

    def test_scan_output_json(self, tmp_path):
        """Test JSON output format."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")

        result = self.runner.invoke(
            app, ["scan", "--source", "file", "--path", str(test_file), "--format", "json"]
        )
        assert result.exit_code == 0
        assert "scan_id" in result.output
        assert "config_count" in result.output

    def test_scan_output_yaml(self, tmp_path):
        """Test YAML output format."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")

        result = self.runner.invoke(
            app, ["scan", "--source", "file", "--path", str(test_file), "--format", "yaml"]
        )
        assert result.exit_code == 0

    def test_scan_output_to_file(self, tmp_path):
        """Test output to file."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")
        output_file = tmp_path / "output.json"

        result = self.runner.invoke(
            app,
            [
                "scan",
                "--source",
                "file",
                "--path",
                str(test_file),
                "--format",
                "json",
                "--output",
                str(output_file),
            ],
        )
        assert result.exit_code == 0
        assert output_file.exists()

    def test_scan_with_severity_filter(self, tmp_path):
        """Test scan with severity threshold."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")

        result = self.runner.invoke(
            app, ["scan", "--source", "file", "--path", str(test_file), "--severity", "high"]
        )
        assert result.exit_code == 0

    def test_scan_with_detector_basic(self, tmp_path):
        """Test scan with basic detector."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")

        result = self.runner.invoke(
            app, ["scan", "--source", "file", "--path", str(test_file), "--detector", "basic"]
        )
        assert result.exit_code == 0

    def test_scan_with_detector_semantic(self, tmp_path):
        """Test scan with semantic detector."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")

        result = self.runner.invoke(
            app, ["scan", "--source", "file", "--path", str(test_file), "--detector", "semantic"]
        )
        assert result.exit_code == 0

    def test_scan_with_baseline(self, tmp_path):
        """Test scan with baseline comparison."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")
        baseline_dir = tmp_path / "baselines"
        baseline_dir.mkdir()

        result = self.runner.invoke(
            app,
            ["scan", "--source", "file", "--path", str(test_file), "--baseline", str(baseline_dir)],
        )
        assert result.exit_code == 0

    def test_scan_nonexistent_path(self):
        """Test scan with nonexistent path."""
        result = self.runner.invoke(
            app, ["scan", "--source", "file", "--path", "/nonexistent/path"]
        )
        assert result.exit_code in [0, 1]

    def test_scan_empty_directory(self, tmp_path):
        """Test scan with empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = self.runner.invoke(app, ["scan", "--source", "file", "--path", str(empty_dir)])
        assert result.exit_code in [0, 1]

    def test_scan_invalid_source(self):
        """Test scan with invalid source type."""
        result = self.runner.invoke(app, ["scan", "--source", "invalid_source", "--path", "."])
        assert result.exit_code != 0


class TestScanCommandEdgeCases:
    """Edge case tests for scan command."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_scan_with_namespace_option(self, tmp_path):
        """Test scan with namespace option."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")

        result = self.runner.invoke(
            app, ["scan", "--source", "file", "--path", str(test_file), "--namespace", "default"]
        )
        assert result.exit_code == 0

    def test_scan_with_label_selector(self, tmp_path):
        """Test scan with label selector."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")

        result = self.runner.invoke(
            app,
            ["scan", "--source", "file", "--path", str(test_file), "--label-selector", "app=myapp"],
        )
        assert result.exit_code == 0

    def test_scan_verbose_flag(self, tmp_path):
        """Test scan with verbose flag."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")

        result = self.runner.invoke(
            app, ["-v", "scan", "--source", "file", "--path", str(test_file)]
        )
        assert result.exit_code == 0


class TestScanCommandMultipleSources:
    """Tests for scan with multiple sources."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_scan_multiple_sources(self, tmp_path):
        """Test scan with multiple sources specified."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")

        result = self.runner.invoke(
            app, ["scan", "--source", "file", "--source", "file", "--path", str(test_file)]
        )
        assert result.exit_code == 0

    def test_scan_kubernetes_source_no_cluster(self):
        """Test scan with kubernetes source (no cluster available)."""
        result = self.runner.invoke(app, ["scan", "--source", "kubernetes"])
        # Should handle gracefully
        assert result.exit_code in [0, 1]


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
