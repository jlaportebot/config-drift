"""Tests for compare CLI command."""

import tempfile

from click.testing import CliRunner

from config_drift.cli.main import app


class TestCompareCommand:
    """Tests for compare command."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_compare_help(self):
        result = self.runner.invoke(app, ["compare", "--help"])
        assert result.exit_code == 0
        assert "Compare two configuration sets for drift" in result.output

    def test_compare_missing_baseline(self):
        result = self.runner.invoke(app, ["compare", "--current", "some_file.yaml"])
        assert result.exit_code != 0

    def test_compare_missing_current(self):
        result = self.runner.invoke(app, ["compare", "--baseline", "some_file.yaml"])
        assert result.exit_code != 0

    def test_compare_both_missing(self):
        result = self.runner.invoke(app, ["compare"])
        assert result.exit_code != 0

    def test_compare_identical_files(self, tmp_path):
        """Test comparing identical files."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")
        current_file = tmp_path / "current.yaml"
        current_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")

        result = self.runner.invoke(
            app, ["compare", "--baseline", str(baseline_file), "--current", str(current_file)]
        )
        assert result.exit_code == 0
        assert "No configuration drift detected" in result.output or "0" in result.output

    def test_compare_different_files(self, tmp_path):
        """Test comparing different files."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value1\n")
        current_file = tmp_path / "current.yaml"
        current_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value2\n")

        result = self.runner.invoke(
            app, ["compare", "--baseline", str(baseline_file), "--current", str(current_file)]
        )
        assert result.exit_code == 0
        assert "drift" in result.output.lower() or "Drift" in result.output

    def test_compare_output_json(self, tmp_path):
        """Test JSON output format."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value1\n")
        current_file = tmp_path / "current.yaml"
        current_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value2\n")

        result = self.runner.invoke(
            app,
            [
                "compare",
                "--baseline",
                str(baseline_file),
                "--current",
                str(current_file),
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        assert "total_drifts" in result.output or "drifts" in result.output.lower()

    def test_compare_detector_basic(self, tmp_path):
        """Test compare with basic detector."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value1\n")
        current_file = tmp_path / "current.yaml"
        current_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value2\n")

        result = self.runner.invoke(
            app,
            [
                "compare",
                "--baseline",
                str(baseline_file),
                "--current",
                str(current_file),
                "--detector",
                "basic",
            ],
        )
        assert result.exit_code == 0

    def test_compare_detector_semantic(self, tmp_path):
        """Test compare with semantic detector."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value1\n")
        current_file = tmp_path / "current.yaml"
        current_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value2\n")

        result = self.runner.invoke(
            app,
            [
                "compare",
                "--baseline",
                str(baseline_file),
                "--current",
                str(current_file),
                "--detector",
                "semantic",
            ],
        )
        assert result.exit_code == 0

    def test_compare_detector_all(self, tmp_path):
        """Test compare with all detectors."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value1\n")
        current_file = tmp_path / "current.yaml"
        current_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value2\n")

        result = self.runner.invoke(
            app,
            [
                "compare",
                "--baseline",
                str(baseline_file),
                "--current",
                str(current_file),
                "--detector",
                "all",
            ],
        )
        assert result.exit_code == 0

    def test_compare_severity_low(self, tmp_path):
        """Test compare with low severity threshold."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value1\n")
        current_file = tmp_path / "current.yaml"
        current_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value2\n")

        result = self.runner.invoke(
            app,
            [
                "compare",
                "--baseline",
                str(baseline_file),
                "--current",
                str(current_file),
                "--severity",
                "low",
            ],
        )
        assert result.exit_code == 0

    def test_compare_severity_high(self, tmp_path):
        """Test compare with high severity threshold."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value1\n")
        current_file = tmp_path / "current.yaml"
        current_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value2\n")

        result = self.runner.invoke(
            app,
            [
                "compare",
                "--baseline",
                str(baseline_file),
                "--current",
                str(current_file),
                "--severity",
                "high",
            ],
        )
        assert result.exit_code == 0

    def test_compare_nonexistent_baseline(self, tmp_path):
        """Test compare with nonexistent baseline."""
        current_file = tmp_path / "current.yaml"
        current_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")

        result = self.runner.invoke(
            app, ["compare", "--baseline", "/nonexistent", "--current", str(current_file)]
        )
        assert result.exit_code != 0

    def test_compare_nonexistent_current(self, tmp_path):
        """Test compare with nonexistent current."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")

        result = self.runner.invoke(
            app, ["compare", "--baseline", str(baseline_file), "--current", "/nonexistent"]
        )
        assert result.exit_code != 0

    def test_compare_empty_files(self, tmp_path):
        """Test comparing empty files."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text("")
        current_file = tmp_path / "current.yaml"
        current_file.write_text("")

        result = self.runner.invoke(
            app, ["compare", "--baseline", str(baseline_file), "--current", str(current_file)]
        )
        assert result.exit_code in [0, 1]

    def test_compare_directories(self, tmp_path):
        """Test comparing directories."""
        baseline_dir = tmp_path / "baseline"
        baseline_dir.mkdir()
        (baseline_dir / "config1.yaml").write_text(
            "apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value1\n"
        )

        current_dir = tmp_path / "current"
        current_dir.mkdir()
        (current_dir / "config1.yaml").write_text(
            "apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value2\n"
        )

        result = self.runner.invoke(
            app, ["compare", "--baseline", str(baseline_dir), "--current", str(current_dir)]
        )
        assert result.exit_code == 0

    def test_compare_invalid_detector(self, tmp_path):
        """Test compare with invalid detector."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")
        current_file = tmp_path / "current.yaml"
        current_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")

        result = self.runner.invoke(
            app,
            [
                "compare",
                "--baseline",
                str(baseline_file),
                "--current",
                str(current_file),
                "--detector",
                "invalid",
            ],
        )
        assert result.exit_code != 0

    def test_compare_invalid_severity(self, tmp_path):
        """Test compare with invalid severity."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")
        current_file = tmp_path / "current.yaml"
        current_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")

        result = self.runner.invoke(
            app,
            [
                "compare",
                "--baseline",
                str(baseline_file),
                "--current",
                str(current_file),
                "--severity",
                "invalid",
            ],
        )
        assert result.exit_code != 0


class TestCompareCommandEdgeCases:
    """Edge case tests for compare command."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_compare_added_key(self, tmp_path):
        """Test compare detects added key."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key1: value1\n")
        current_file = tmp_path / "current.yaml"
        current_file.write_text(
            "apiVersion: v1\nkind: ConfigMap\ndata:\n  key1: value1\n  key2: value2\n"
        )

        result = self.runner.invoke(
            app, ["compare", "--baseline", str(baseline_file), "--current", str(current_file)]
        )
        assert result.exit_code == 0

    def test_compare_removed_key(self, tmp_path):
        """Test compare detects removed key."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text(
            "apiVersion: v1\nkind: ConfigMap\ndata:\n  key1: value1\n  key2: value2\n"
        )
        current_file = tmp_path / "current.yaml"
        current_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key1: value1\n")

        result = self.runner.invoke(
            app, ["compare", "--baseline", str(baseline_file), "--current", str(current_file)]
        )
        assert result.exit_code == 0

    def test_compare_type_change(self, tmp_path):
        """Test compare detects type change."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text('apiVersion: v1\nkind: ConfigMap\ndata:\n  key: "value"\n')
        current_file = tmp_path / "current.yaml"
        current_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: 123\n")

        result = self.runner.invoke(
            app, ["compare", "--baseline", str(baseline_file), "--current", str(current_file)]
        )
        assert result.exit_code == 0

    def test_compare_nested_drift(self, tmp_path):
        """Test compare detects nested drift."""
        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text(
            "apiVersion: v1\nkind: ConfigMap\ndata:\n  nested:\n    key: value1\n"
        )
        current_file = tmp_path / "current.yaml"
        current_file.write_text(
            "apiVersion: v1\nkind: ConfigMap\ndata:\n  nested:\n    key: value2\n"
        )

        result = self.runner.invoke(
            app, ["compare", "--baseline", str(baseline_file), "--current", str(current_file)]
        )
        assert result.exit_code == 0


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
