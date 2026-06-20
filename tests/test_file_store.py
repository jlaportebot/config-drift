"""Tests for the file-based storage."""

from pathlib import Path

import pytest

from config_drift.models.config import ConfigFormat, ConfigSource, ParsedConfig
from config_drift.storage.file_store import FileStore


@pytest.fixture
def store(tmp_path):
    """Create a FileStore with a temp directory."""
    return FileStore(str(tmp_path / "baselines"))


@pytest.fixture
def sample_config():
    """Create a sample ParsedConfig."""
    return ParsedConfig(
        source=ConfigSource.FILE,
        format=ConfigFormat.YAML,
        content={"key": "value", "nested": {"a": 1}},
        resource_id="config/my-app",
        namespace="default",
        labels={"app": "my-app", "env": "prod"},
        annotations={"note": "test"},
    )


class TestFileStore:
    """Tests for FileStore."""

    def test_save_baseline(self, store, sample_config):
        path = store.save_baseline(sample_config)
        assert Path(path).exists()

    def test_get_baseline(self, store, sample_config):
        store.save_baseline(sample_config)
        loaded = store.get_baseline("file", "config/my-app", "default")
        assert loaded is not None
        assert loaded.content["key"] == "value"
        assert loaded.resource_id == "config/my-app"
        assert loaded.namespace == "default"

    def test_get_nonexistent_baseline(self, store):
        result = store.get_baseline("file", "nonexistent")
        assert result is None

    def test_list_baselines(self, store, sample_config):
        store.save_baseline(sample_config)
        baselines = store.list_baselines()
        assert len(baselines) == 1
        assert baselines[0]["source"] == "file"

    def test_list_baselines_by_source(self, store, sample_config):
        store.save_baseline(sample_config)
        baselines = store.list_baselines("file")
        assert len(baselines) == 1
        baselines = store.list_baselines("kubernetes")
        assert len(baselines) == 0

    def test_delete_baseline(self, store, sample_config):
        store.save_baseline(sample_config)
        assert store.delete_baseline("file", "config/my-app", "default") is True
        assert store.get_baseline("file", "config/my-app", "default") is None

    def test_delete_nonexistent_baseline(self, store):
        assert store.delete_baseline("file", "nonexistent") is False

    def test_overwrite_baseline(self, store, sample_config):
        store.save_baseline(sample_config)
        # Modify and save again
        sample_config.content["key"] = "new_value"
        store.save_baseline(sample_config)
        loaded = store.get_baseline("file", "config/my-app", "default")
        assert loaded.content["key"] == "new_value"
