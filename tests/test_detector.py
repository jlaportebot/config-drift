"""Tests for config_drift detector."""

from __future__ import annotations

from pathlib import Path

import pytest

from config_drift.detector import DriftDetector
from config_drift.models import (
    ConfigFile,
    ConfigFormat,
    ConfigResource,
    DriftSeverity,
    Environment,
)


def create_test_env(name: str, resources: list[ConfigResource]) -> Environment:
    config_file = ConfigFile(
        path=Path(f"/tmp/{name}.yaml"),
        format=ConfigFormat.YAML,
        resources=resources,
    )
    return Environment(name=name, config_files=[config_file])


class TestDriftDetector:
    def test_no_drift_identical_environments(self) -> None:
        resources = [
            ConfigResource(
                kind="Deployment",
                name="app",
                namespace="prod",
                data={"spec": {"replicas": 3, "image": "nginx:1.21"}},
            )
        ]
        source = create_test_env("source", resources)
        target = create_test_env("target", resources)

        detector = DriftDetector()
        report = detector.compare_environments(source, target)

        assert report.drift_count == 0
        assert not report.has_breaking_changes

    def test_detect_added_resource(self) -> None:
        source_resources = []
        target_resources = [
            ConfigResource(
                kind="Deployment",
                name="new-app",
                namespace="prod",
                data={"spec": {"replicas": 1}},
            )
        ]
        source = create_test_env("source", source_resources)
        target = create_test_env("target", target_resources)

        detector = DriftDetector()
        report = detector.compare_environments(source, target)

        assert report.drift_count == 1
        drift = report.drifts[0]
        assert drift.field_path == "__resource__"
        assert drift.severity == DriftSeverity.WARNING
        assert "added" in drift.description.lower()

    def test_detect_removed_resource(self) -> None:
        source_resources = [
            ConfigResource(
                kind="Deployment",
                name="old-app",
                namespace="prod",
                data={"spec": {"replicas": 3}},
            )
        ]
        target_resources = []
        source = create_test_env("source", source_resources)
        target = create_test_env("target", target_resources)

        detector = DriftDetector()
        report = detector.compare_environments(source, target)

        assert report.drift_count == 1
        drift = report.drifts[0]
        assert drift.field_path == "__resource__"
        assert drift.severity == DriftSeverity.ERROR
        assert "removed" in drift.description.lower()

    def test_detect_field_change(self) -> None:
        source_resources = [
            ConfigResource(
                kind="Deployment",
                name="app",
                namespace="prod",
                data={"spec": {"replicas": 3}},
            )
        ]
        target_resources = [
            ConfigResource(
                kind="Deployment",
                name="app",
                namespace="prod",
                data={"spec": {"replicas": 5}},
            )
        ]
        source = create_test_env("source", source_resources)
        target = create_test_env("target", target_resources)

        detector = DriftDetector()
        report = detector.compare_environments(source, target)

        assert report.drift_count == 1
        drift = report.drifts[0]
        assert drift.field_path == "spec.replicas"
        assert drift.source_value == 3
        assert drift.target_value == 5
        # replicas should be ERROR severity
        assert drift.severity == DriftSeverity.ERROR

    def test_detect_image_change_critical(self) -> None:
        source_resources = [
            ConfigResource(
                kind="Deployment",
                name="app",
                namespace="prod",
                data={"spec": {"template": {"spec": {"containers": [{"image": "nginx:1.21"}]}}}},
            )
        ]
        target_resources = [
            ConfigResource(
                kind="Deployment",
                name="app",
                namespace="prod",
                data={"spec": {"template": {"spec": {"containers": [{"image": "nginx:1.22"}]}}}},
            )
        ]
        source = create_test_env("source", source_resources)
        target = create_test_env("target", target_resources)

        detector = DriftDetector()
        report = detector.compare_environments(source, target)

        # Find the image drift
        image_drifts = [d for d in report.drifts if "image" in d.field_path]
        assert len(image_drifts) >= 1
        assert image_drifts[0].severity == DriftSeverity.CRITICAL

    def test_detect_env_var_change_error(self) -> None:
        source_resources = [
            ConfigResource(
                kind="Deployment",
                name="app",
                namespace="prod",
                data={
                    "spec": {
                        "template": {
                            "spec": {"containers": [{"env": [{"name": "DEBUG", "value": "false"}]}]}
                        }
                    }
                },
            )
        ]
        target_resources = [
            ConfigResource(
                kind="Deployment",
                name="app",
                namespace="prod",
                data={
                    "spec": {
                        "template": {
                            "spec": {"containers": [{"env": [{"name": "DEBUG", "value": "true"}]}]}
                        }
                    }
                },
            )
        ]
        source = create_test_env("source", source_resources)
        target = create_test_env("target", target_resources)

        detector = DriftDetector()
        report = detector.compare_environments(source, target)

        env_drifts = [d for d in report.drifts if "env" in d.field_path]
        assert len(env_drifts) >= 1
        assert env_drifts[0].severity == DriftSeverity.ERROR

    def test_detect_annotation_change_info(self) -> None:
        source_resources = [
            ConfigResource(
                kind="Deployment",
                name="app",
                namespace="prod",
                data={"metadata": {"annotations": {"version": "1.0"}}},
            )
        ]
        target_resources = [
            ConfigResource(
                kind="Deployment",
                name="app",
                namespace="prod",
                data={"metadata": {"annotations": {"version": "1.1"}}},
            )
        ]
        source = create_test_env("source", source_resources)
        target = create_test_env("target", target_resources)

        detector = DriftDetector()
        report = detector.compare_environments(source, target)

        annotation_drifts = [d for d in report.drifts if "annotations" in d.field_path]
        assert len(annotation_drifts) >= 1
        assert annotation_drifts[0].severity == DriftSeverity.INFO

    def test_multiple_drifts_same_resource(self) -> None:
        source_resources = [
            ConfigResource(
                kind="Deployment",
                name="app",
                namespace="prod",
                data={
                    "spec": {"replicas": 3},
                    "metadata": {"annotations": {"version": "1.0"}},
                },
            )
        ]
        target_resources = [
            ConfigResource(
                kind="Deployment",
                name="app",
                namespace="prod",
                data={
                    "spec": {"replicas": 5},
                    "metadata": {"annotations": {"version": "2.0"}},
                },
            )
        ]
        source = create_test_env("source", source_resources)
        target = create_test_env("target", target_resources)

        detector = DriftDetector()
        report = detector.compare_environments(source, target)

        assert report.drift_count == 2
        severities = {d.severity for d in report.drifts}
        assert DriftSeverity.ERROR in severities  # replicas
        assert DriftSeverity.INFO in severities  # annotations

    def test_report_summary(self) -> None:
        source_resources = [
            ConfigResource(kind="Deployment", name="app1", data={"spec": {"replicas": 3}}),
            ConfigResource(
                kind="Service",
                name="svc1",
                data={"spec": {"ports": [{"port": 80, "targetPort": 8080}]}},
            ),
        ]
        target_resources = [
            ConfigResource(kind="Deployment", name="app1", data={"spec": {"replicas": 5}}),
            ConfigResource(
                kind="Service",
                name="svc1",
                data={"spec": {"ports": [{"port": 8080, "targetPort": 8080}]}},
            ),
            ConfigResource(kind="ConfigMap", name="cm1", data={"data": {"key": "value"}}),
        ]
        source = create_test_env("source", source_resources)
        target = create_test_env("target", target_resources)

        detector = DriftDetector()
        report = detector.compare_environments(source, target)

        # app1 replicas changed (ERROR), svc1 ports changed (WARNING), cm1 added (WARNING)
        assert report.drift_count == 3
        assert report.error_count == 1
        assert report.warning_count == 2
        assert report.critical_count == 0

    def test_has_breaking_changes(self) -> None:
        source_resources = [
            ConfigResource(kind="Deployment", name="app", data={"spec": {"replicas": 3}}),
        ]
        target_resources = [
            ConfigResource(kind="Deployment", name="app", data={"spec": {"replicas": 5}}),
        ]
        source = create_test_env("source", source_resources)
        target = create_test_env("target", target_resources)

        detector = DriftDetector()
        report = detector.compare_environments(source, target)

        assert report.has_breaking_changes is True


class TestSeverityRules:
    def test_custom_severity_rules(self) -> None:
        from config_drift.detector import DriftRule

        custom_rules = [
            DriftRule(
                "spec.customField", DriftSeverity.CRITICAL, description="Custom critical field"
            ),
            DriftRule("*", DriftSeverity.INFO),
        ]

        source_resources = [
            ConfigResource(kind="CustomResource", name="cr", data={"spec": {"customField": "old"}}),
        ]
        target_resources = [
            ConfigResource(kind="CustomResource", name="cr", data={"spec": {"customField": "new"}}),
        ]
        source = create_test_env("source", source_resources)
        target = create_test_env("target", target_resources)

        detector = DriftDetector(severity_rules=custom_rules)
        report = detector.compare_environments(source, target)

        custom_drifts = [d for d in report.drifts if "customField" in d.field_path]
        assert len(custom_drifts) == 1
        assert custom_drifts[0].severity == DriftSeverity.CRITICAL
