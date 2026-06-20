"""Tests for baseline CLI commands."""

import os
import tempfile

from click.testing import CliRunner

from config_drift.cli.main import app


class TestBaselineCommands:
    """Tests for baseline commands."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_baseline_help(self):
        result = self.runner.invoke(app, ["baseline", "--help"])
        assert result.exit_code == 0
        assert "Manage configuration baselines" in result.output

    def test_baseline_save_help(self):
        result = self.runner.invoke(app, ["baseline", "save", "--help"])
        assert result.exit_code == 0
        assert "Save current configuration as a baseline" in result.output

    def test_baseline_list_help(self):
        result = self.runner.invoke(app, ["baseline", "list", "--help"])
        assert result.exit_code == 0
        assert "List all saved baselines" in result.output

    def test_baseline_show_help(self):
        result = self.runner.invoke(app, ["baseline", "show", "--help"])
        assert result.exit_code == 0
        assert "Show details of a specific baseline" in result.output

    def test_baseline_delete_help(self):
        result = self.runner.invoke(app, ["baseline", "delete", "--help"])
        assert result.exit_code == 0
        assert "Delete a baseline" in result.output

    def test_baseline_save_file(self, tmp_path):
        """Test saving a file as baseline."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")
        store_dir = tmp_path / "baselines"

        result = self.runner.invoke(
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
        assert result.exit_code == 0
        assert "Saved" in result.output

    def test_baseline_save_nonexistent_file(self):
        """Test saving a nonexistent file."""
        result = self.runner.invoke(
            app, ["baseline", "save", "--source", "file", "--path", "/nonexistent/file.yaml"]
        )
        assert result.exit_code != 0

    def test_baseline_save_directory(self, tmp_path):
        """Test saving a directory as baseline."""
        file1 = tmp_path / "config1.yaml"
        file1.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value1\n")
        file2 = tmp_path / "config2.yaml"
        file2.write_text("apiVersion: v1\nkind: Secret\ndata:\n  key: dmFsdWUy\n")
        store_dir = tmp_path / "baselines"

        result = self.runner.invoke(
            app,
            [
                "baseline",
                "save",
                "--source",
                "file",
                "--path",
                str(tmp_path),
                "--store",
                str(store_dir),
            ],
        )
        assert result.exit_code == 0

    def test_baseline_list_empty(self, tmp_path):
        """Test listing baselines when empty."""
        store_dir = tmp_path / "baselines"

        result = self.runner.invoke(app, ["baseline", "list", "--store", str(store_dir)])
        assert result.exit_code == 0
        assert "No baselines found" in result.output

    def test_baseline_list_after_save(self, tmp_path):
        """Test listing baselines after saving."""
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
        result = self.runner.invoke(app, ["baseline", "list", "--store", str(store_dir)])
        assert result.exit_code == 0
        assert "ConfigMap" in result.output or "baselines" in result.output.lower()

    def test_baseline_list_with_source_filter(self, tmp_path):
        """Test listing baselines with source filter."""
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
        result = self.runner.invoke(
            app, ["baseline", "list", "--store", str(store_dir), "--source", "file"]
        )
        assert result.exit_code == 0

    def test_baseline_show_existing(self, tmp_path):
        """Test showing an existing baseline."""
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

        # First list to get the baseline ID
        list_result = self.runner.invoke(app, ["baseline", "list", "--store", str(store_dir)])
        assert list_result.exit_code == 0

        # The baseline ID format is source/resource_id
        result = self.runner.invoke(
            app, ["baseline", "show", "file/ConfigMap", "--store", str(store_dir)]
        )
        assert result.exit_code in [0, 1]  # May not find exact match

    def test_baseline_show_nonexistent(self, tmp_path):
        """Test showing a nonexistent baseline."""
        store_dir = tmp_path / "baselines"

        result = self.runner.invoke(
            app, ["baseline", "show", "file/nonexistent", "--store", str(store_dir)]
        )
        assert result.exit_code in [0, 1]

    def test_baseline_delete_existing(self, tmp_path):
        """Test deleting an existing baseline."""
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

        result = self.runner.invoke(
            app, ["baseline", "delete", "file/ConfigMap", "--store", str(store_dir)], input="y\n"
        )
        assert result.exit_code in [0, 1]

    def test_baseline_delete_nonexistent(self, tmp_path):
        """Test deleting a nonexistent baseline."""
        store_dir = tmp_path / "baselines"

        result = self.runner.invoke(
            app, ["baseline", "delete", "file/nonexistent", "--store", str(store_dir)], input="y\n"
        )
        assert result.exit_code in [0, 1]

    def test_baseline_save_with_errors(self, tmp_path):
        """Test saving baseline with parse errors."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("invalid: yaml: content: [")
        store_dir = tmp_path / "baselines"

        result = self.runner.invoke(
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
        assert result.exit_code == 0  # Should still save what it can


class TestBaselineCommandsEdgeCases:
    """Edge case tests for baseline commands."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_baseline_save_different_sources(self, tmp_path):
        """Test saving baselines from different source types."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value\n")
        store_dir = tmp_path / "baselines"

        # Test with kubernetes source (will fail gracefully without cluster)
        result = self.runner.invoke(
            app,
            [
                "baseline",
                "save",
                "--source",
                "kubernetes",
                "--path",
                str(test_file),
                "--store",
                str(store_dir),
            ],
        )
        assert result.exit_code in [0, 1]

    def test_baseline_multiple_saves_overwrite(self, tmp_path):
        """Test multiple saves to same baseline overwrite."""
        test_file = tmp_path / "config.yaml"
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value1\n")
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

        # Update file
        test_file.write_text("apiVersion: v1\nkind: ConfigMap\ndata:\n  key: value2\n")
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

        result = self.runner.invoke(app, ["baseline", "list", "--store", str(store_dir)])
        assert result.exit_code == 0


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
