"""Tests for the basic (structural) drift detector."""

from config_drift.detectors.basic import BasicDriftDetector
from config_drift.models.config import ConfigFormat, ConfigSource, ParsedConfig
from config_drift.models.drift import DriftSeverity, DriftType


def _make_config(content, source=ConfigSource.FILE, resource_id="test/config"):
    """Helper to create ParsedConfig for testing."""
    return ParsedConfig(
        source=source,
        format=ConfigFormat.YAML,
        content=content,
        resource_id=resource_id,
    )


class TestBasicDriftDetector:
    """Tests for BasicDriftDetector."""

    def test_no_drift(self):
        baseline = _make_config({"key": "value", "nested": {"a": 1}})
        current = _make_config({"key": "value", "nested": {"a": 1}})
        detector = BasicDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) == 0

    def test_value_changed(self):
        baseline = _make_config({"replicas": 3})
        current = _make_config({"replicas": 5})
        detector = BasicDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) == 1
        assert drifts[0].drift_type == DriftType.MODIFIED
        assert drifts[0].expected == 3
        assert drifts[0].actual == 5

    def test_key_added(self):
        baseline = _make_config({"key": "value"})
        current = _make_config({"key": "value", "new_key": "new_value"})
        detector = BasicDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) == 1
        assert drifts[0].drift_type == DriftType.ADDED
        assert drifts[0].path == "new_key"
        assert drifts[0].actual == "new_value"

    def test_key_removed(self):
        baseline = _make_config({"key": "value", "old_key": "old_value"})
        current = _make_config({"key": "value"})
        detector = BasicDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) == 1
        assert drifts[0].drift_type == DriftType.REMOVED
        assert drifts[0].path == "old_key"

    def test_type_changed(self):
        baseline = _make_config({"port": 8080})
        current = _make_config({"port": "8080"})
        detector = BasicDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) == 1
        assert drifts[0].drift_type == DriftType.TYPE_CHANGED

    def test_nested_dict_drift(self):
        baseline = _make_config({"spec": {"replicas": 3, "image": "v1"}})
        current = _make_config({"spec": {"replicas": 5, "image": "v1"}})
        detector = BasicDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) == 1
        assert drifts[0].path == "spec.replicas"
        assert drifts[0].drift_type == DriftType.MODIFIED

    def test_deeply_nested_drift(self):
        baseline = _make_config({"level1": {"level2": {"level3": {"key": "old"}}}})
        current = _make_config({"level1": {"level2": {"level3": {"key": "new"}}}})
        detector = BasicDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) == 1
        assert drifts[0].path == "level1.level2.level3.key"

    def test_list_drift_added_item(self):
        baseline = _make_config({"items": [1, 2, 3]})
        current = _make_config({"items": [1, 2, 3, 4]})
        detector = BasicDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) == 1
        assert drifts[0].drift_type == DriftType.ADDED

    def test_list_drift_removed_item(self):
        baseline = _make_config({"items": [1, 2, 3]})
        current = _make_config({"items": [1, 2]})
        detector = BasicDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) == 1
        assert drifts[0].drift_type == DriftType.REMOVED

    def test_list_drift_modified_item(self):
        baseline = _make_config({"items": [1, 2, 3]})
        current = _make_config({"items": [1, 99, 3]})
        detector = BasicDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) == 1
        assert drifts[0].drift_type == DriftType.MODIFIED
        assert drifts[0].expected == 2
        assert drifts[0].actual == 99

    def test_multiple_drifts(self):
        baseline = _make_config(
            {
                "replicas": 3,
                "image": "v1",
                "port": 8080,
            }
        )
        current = _make_config(
            {
                "replicas": 5,
                "image": "v2",
                "port": 8080,
                "new_field": "added",
            }
        )
        detector = BasicDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) == 3

    def test_ignore_paths(self):
        from config_drift.detectors.base import DetectorConfig

        config = DetectorConfig(ignore_paths=["metadata.uid", "status"])
        detector = BasicDriftDetector(config=config)
        baseline = _make_config({"metadata": {"uid": "abc"}, "status": "ready", "key": "val"})
        current = _make_config({"metadata": {"uid": "def"}, "status": "notready", "key": "val"})
        drifts = detector.detect(baseline, current)
        # metadata.uid and status should be ignored
        assert len(drifts) == 0

    def test_severity_by_type(self):
        detector = BasicDriftDetector()
        # ADDED should be LOW
        drifts = detector.detect(_make_config({}), _make_config({"new": "val"}))
        assert drifts[0].severity == DriftSeverity.LOW

        # REMOVED should be HIGH
        drifts = detector.detect(_make_config({"old": "val"}), _make_config({}))
        assert drifts[0].severity == DriftSeverity.HIGH
