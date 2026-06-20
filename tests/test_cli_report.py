"""Tests for report CLI command."""

import json
import tempfile

from click.testing import CliRunner

from config_drift.cli.main import app


class TestReportCommand:
    """Tests for report command."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_report_help(self):
        result = self.runner.invoke(app, ["report", "--help"])
        assert result.exit_code == 0
        assert "Generate drift reports" in result.output

    def test_report_no_args(self):
        """Test report with no arguments shows baseline report."""
        result = self.runner.invoke(app, ["report"])
        assert result.exit_code == 0
        assert "baseline" in result.output.lower() or "report" in result.output.lower()

    def test_report_last_flag(self):
        """Test report with --last flag."""
        result = self.runner.invoke(app, ["report", "--last"])
        assert result.exit_code in [0, 1]

    def test_report_output_text(self, tmp_path):
        """Test report with text output format."""
        result = self.runner.invoke(app, ["report", "--format", "text"])
        assert result.exit_code == 0

    def test_report_output_json(self, tmp_path):
        """Test report with JSON output format."""
        result = self.runner.invoke(app, ["report", "--format", "json"])
        assert result.exit_code == 0

    def test_report_output_markdown(self, tmp_path):
        """Test report with markdown output format."""
        result = self.runner.invoke(app, ["report", "--format", "markdown"])
        assert result.exit_code == 0

    def test_report_output_html(self, tmp_path):
        """Test report with HTML output format."""
        result = self.runner.invoke(app, ["report", "--format", "html"])
        assert result.exit_code in [0, 1]

    def test_report_output_to_file(self, tmp_path):
        """Test report output to file."""
        output_file = tmp_path / "report.json"
        result = self.runner.invoke(
            app, ["report", "--format", "json", "--output", str(output_file)]
        )
        assert result.exit_code == 0
        assert output_file.exists()

    def test_report_output_markdown_to_file(self, tmp_path):
        """Test report markdown output to file."""
        output_file = tmp_path / "report.md"
        result = self.runner.invoke(
            app, ["report", "--format", "markdown", "--output", str(output_file)]
        )
        assert result.exit_code == 0
        assert output_file.exists()

    def test_report_with_store(self, tmp_path):
        """Test report with custom store directory."""
        store_dir = tmp_path / "baselines"
        result = self.runner.invoke(app, ["report", "--store", str(store_dir)])
        assert result.exit_code == 0

    def test_report_with_db(self, tmp_path):
        """Test report with DuckDB database."""
        db_file = tmp_path / "scans.db"
        result = self.runner.invoke(app, ["report", "--db", str(db_file), "--last"])
        assert result.exit_code in [0, 1]

    def test_report_with_scan_id(self, tmp_path):
        """Test report with specific scan ID."""
        result = self.runner.invoke(app, ["report", "--scan-id", "test-scan-123"])
        assert result.exit_code in [0, 1]

    def test_report_invalid_format(self):
        """Test report with invalid format."""
        result = self.runner.invoke(app, ["report", "--format", "invalid"])
        assert result.exit_code != 0

    def test_report_baseline_json_content(self, tmp_path):
        """Test baseline report JSON content structure."""
        result = self.runner.invoke(app, ["report", "--format", "json"])
        assert result.exit_code == 0
        # Should be valid JSON
        data = json.loads(result.output)
        assert "baselines" in data or "baselines" in str(data).lower()

    def test_report_baseline_markdown_content(self, tmp_path):
        """Test baseline report markdown content."""
        result = self.runner.invoke(app, ["report", "--format", "markdown"])
        assert result.exit_code == 0
        assert (
            "# Config Drift Baseline Report" in result.output or "baseline" in result.output.lower()
        )


class TestReportCommandEdgeCases:
    """Edge case tests for report command."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_report_with_baselines(self, tmp_path):
        """Test report when baselines exist."""
        # Create a baseline first
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")
        store_dir = tmp_path / "baselines"

        # Save baseline using baseline command
        self.runner.invoke(
            app,
            [
                "baseline",
                "save",
                "--source",
                "file",
                "--path",
                str(test_file),
                "--store",
                str(store_dir),
            ],
        )

        # Now generate report
        result = self.runner.invoke(app, ["report", "--store", str(store_dir), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "baselines" in data

    def test_report_baseline_with_resource(self, tmp_path):
        """Test report shows baseline resources."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")
        store_dir = tmp_path / "baselines"

        self.runner.invoke(
            app,
            [
                "baseline",
                "save",
                "--source",
                "file",
                "--path",
                str(test_file),
                "--store",
                str(store_dir),
            ],
        )

        result = self.runner.invoke(app, ["report", "--store", str(store_dir), "--format", "text"])
        assert result.exit_code == 0
        assert "ConfigMap" in result.output or "baselines" in result.output.lower()

    def test_report_db_no_scans(self, tmp_path):
        """Test report with DB but no scans."""
        db_file = tmp_path / "empty_scans.db"
        result = self.runner.invoke(
            app, ["report", "--db", str(db_file), "--last", "--format", "json"]
        )
        assert result.exit_code == 0


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
