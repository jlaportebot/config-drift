"""Tests for DuckDB storage."""

from datetime import datetime

import pytest

from config_drift.models.config import ConfigFormat, ConfigSource, ParsedConfig
from config_drift.models.scan import ScanConfig, ScanResult
from config_drift.storage.duckdb_store import DuckDBStore


@pytest.fixture
def store(tmp_path):
    """Create a DuckDBStore with a temp database."""
    return DuckDBStore(str(tmp_path / "test.db"))


@pytest.fixture
def sample_config():
    """Create a sample ParsedConfig."""
    return ParsedConfig(
        source=ConfigSource.KUBERNETES,
        format=ConfigFormat.YAML,
        content={"apiVersion": "v1", "kind": "ConfigMap", "data": {"key": "value"}},
        resource_id="ConfigMap/my-config",
        namespace="default",
        labels={"app": "my-app"},
        annotations={"note": "test"},
    )


class TestDuckDBStore:
    """Tests for DuckDBStore."""

    def test_save_baseline(self, store, sample_config):
        baseline_id = store.save_baseline(sample_config)
        assert baseline_id is not None
        assert "kubernetes" in baseline_id

    def test_get_baseline(self, store, sample_config):
        store.save_baseline(sample_config)
        loaded = store.get_baseline("kubernetes", "ConfigMap/my-config", "default")
        assert loaded is not None
        assert loaded.content["kind"] == "ConfigMap"
        assert loaded.resource_id == "ConfigMap/my-config"

    def test_get_nonexistent_baseline(self, store):
        result = store.get_baseline("kubernetes", "nonexistent")
        assert result is None

    def test_list_baselines(self, store, sample_config):
        store.save_baseline(sample_config)
        baselines = store.list_baselines()
        assert len(baselines) == 1

    def test_list_baselines_by_source(self, store, sample_config):
        store.save_baseline(sample_config)
        baselines = store.list_baselines("kubernetes")
        assert len(baselines) == 1
        baselines = store.list_baselines("terraform")
        assert len(baselines) == 0

    def test_delete_baseline(self, store, sample_config):
        store.save_baseline(sample_config)
        assert store.delete_baseline("kubernetes", "ConfigMap/my-config", "default") is True
        assert store.get_baseline("kubernetes", "ConfigMap/my-config", "default") is None

    def test_save_and_get_scan(self, store):
        scan = ScanResult(
            scan_id="test-scan-1",
            started_at=datetime.utcnow(),
            scanned_sources=["kubernetes", "file"],
        )
        scan_id = store.save_scan(scan)
        assert scan_id == "test-scan-1"

        loaded = store.get_scan("test-scan-1")
        assert loaded is not None
        assert loaded.scan_id == "test-scan-1"
        assert len(loaded.scanned_sources) == 2

    def test_list_scans(self, store):
        scan = ScanResult(
            scan_id="test-scan-list",
            started_at=datetime.utcnow(),
        )
        store.save_scan(scan)
        scans = store.list_scans()
        assert len(scans) == 1

    def test_overwrite_baseline(self, store, sample_config):
        store.save_baseline(sample_config)
        sample_config.content["data"]["key"] = "new_value"
        store.save_baseline(sample_config)
        loaded = store.get_baseline("kubernetes", "ConfigMap/my-config", "default")
        assert loaded.content["data"]["key"] == "new_value"

    def test_close(self, store):
        store.close()
