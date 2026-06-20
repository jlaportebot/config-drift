"""Tests for config_drift models."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from config_drift.models import (
    ConfigFile,
    ConfigFormat,
    ConfigResource,
    Drift,
    DriftReport,
    DriftSeverity,
    Environment,
)


class TestConfigResource:
    def test_identifier_basic(self) -> None:
        resource = ConfigResource(kind="Deployment", name="my-app", namespace="default")
        assert resource.identifier == "Deployment/default/my-app"

    def test_identifier_no_namespace(self) -> None:
        resource = ConfigResource(kind="Namespace", name="production")
        assert resource.identifier == "Namespace/production"

    def test_equality(self) -> None:
        r1 = ConfigResource(kind="Deployment", name="app", namespace="ns")
        r2 = ConfigResource(kind="Deployment", name="app", namespace="ns")
        assert r1 == r2


class TestConfigFile:
    def test_get_resource_found(self) -> None:
        resource = ConfigResource(kind="Service", name="api", namespace="prod")
        config_file = ConfigFile(
            path=Path("/tmp/test.yaml"),
            format=ConfigFormat.YAML,
            resources=[resource],
        )
        found = config_file.get_resource("Service", "api", "prod")
        assert found is not None
        assert found.name == "api"

    def test_get_resource_not_found(self) -> None:
        config_file = ConfigFile(
            path=Path("/tmp/test.yaml"),
            format=ConfigFormat.YAML,
            resources=[],
        )
        found = config_file.get_resource("Service", "nonexistent")
        assert found is None


class TestEnvironment:
    def test_get_resource_across_files(self) -> None:
        resource1 = ConfigResource(kind="ConfigMap", name="cm1", namespace="ns1")
        resource2 = ConfigResource(kind="Secret", name="sec1", namespace="ns1")
        cf1 = ConfigFile(path=Path("/tmp/a.yaml"), format=ConfigFormat.YAML, resources=[resource1])
        cf2 = ConfigFile(path=Path("/tmp/b.yaml"), format=ConfigFormat.YAML, resources=[resource2])
        env = Environment(name="test", config_files=[cf1, cf2])

        found = env.get_resource("Secret", "sec1", "ns1")
        assert found is not None
        assert found.kind == "Secret"

    def test_get_resource_not_found(self) -> None:
        env = Environment(name="test", config_files=[])
        found = env.get_resource("Deployment", "missing")
        assert found is None


class TestDrift:
    def test_is_breaking_critical(self) -> None:
        drift = Drift(
            resource_identifier="Deployment/ns/app",
            resource_kind="Deployment",
            resource_name="app",
            namespace="ns",
            field_path="spec.replicas",
            source_value=3,
            target_value=5,
            severity=DriftSeverity.CRITICAL,
            source_env="prod",
            target_env="staging",
        )
        assert drift.is_breaking is True

    def test_is_breaking_error(self) -> None:
        drift = Drift(
            resource_identifier="Deployment/ns/app",
            resource_kind="Deployment",
            resource_name="app",
            namespace="ns",
            field_path="spec.replicas",
            source_value=3,
            target_value=5,
            severity=DriftSeverity.ERROR,
            source_env="prod",
            target_env="staging",
        )
        assert drift.is_breaking is True

    def test_is_breaking_warning(self) -> None:
        drift = Drift(
            resource_identifier="Deployment/ns/app",
            resource_kind="Deployment",
            resource_name="app",
            namespace="ns",
            field_path="metadata.annotations.version",
            source_value="1.0",
            target_value="1.1",
            severity=DriftSeverity.WARNING,
            source_env="prod",
            target_env="staging",
        )
        assert drift.is_breaking is False


class TestDriftReport:
    def test_summary_counts(self) -> None:
        drifts = [
            Drift(
                resource_identifier="r1",
                resource_kind="Deployment",
                resource_name="app",
                namespace="ns",
                field_path="a",
                source_value=1,
                target_value=2,
                severity=DriftSeverity.CRITICAL,
                source_env="s",
                target_env="t",
            ),
            Drift(
                resource_identifier="r2",
                resource_kind="Service",
                resource_name="svc",
                namespace="ns",
                field_path="b",
                source_value=1,
                target_value=2,
                severity=DriftSeverity.ERROR,
                source_env="s",
                target_env="t",
            ),
            Drift(
                resource_identifier="r3",
                resource_kind="ConfigMap",
                resource_name="cm",
                namespace="ns",
                field_path="c",
                source_value=1,
                target_value=2,
                severity=DriftSeverity.WARNING,
                source_env="s",
                target_env="t",
            ),
            Drift(
                resource_identifier="r4",
                resource_kind="Secret",
                resource_name="sec",
                namespace="ns",
                field_path="d",
                source_value=1,
                target_value=2,
                severity=DriftSeverity.INFO,
                source_env="s",
                target_env="t",
            ),
        ]

        source_env = Environment(name="source")
        target_env = Environment(name="target")
        report = DriftReport(source_env=source_env, target_env=target_env, drifts=drifts)

        assert report.drift_count == 4
        assert report.critical_count == 1
        assert report.error_count == 1
        assert report.warning_count == 1
        assert report.info_count == 1
        assert report.has_breaking_changes is True

    def test_get_drifts_by_severity(self) -> None:
        drifts = [
            Drift(
                resource_identifier="r1",
                resource_kind="Deployment",
                resource_name="app",
                namespace="ns",
                field_path="a",
                source_value=1,
                target_value=2,
                severity=DriftSeverity.CRITICAL,
                source_env="s",
                target_env="t",
            ),
            Drift(
                resource_identifier="r2",
                resource_kind="Service",
                resource_name="svc",
                namespace="ns",
                field_path="b",
                source_value=1,
                target_value=2,
                severity=DriftSeverity.INFO,
                source_env="s",
                target_env="t",
            ),
        ]

        source_env = Environment(name="source")
        target_env = Environment(name="target")
        report = DriftReport(source_env=source_env, target_env=target_env, drifts=drifts)

        critical = report.get_drifts_by_severity(DriftSeverity.CRITICAL)
        assert len(critical) == 1
        assert critical[0].resource_identifier == "r1"

    def test_to_dict(self) -> None:
        drift = Drift(
            resource_identifier="Deployment/ns/app",
            resource_kind="Deployment",
            resource_name="app",
            namespace="ns",
            field_path="spec.replicas",
            source_value=3,
            target_value=5,
            severity=DriftSeverity.ERROR,
            source_env="prod",
            target_env="staging",
            description="Replica count changed",
        )

        source_env = Environment(name="prod")
        target_env = Environment(name="staging")
        report = DriftReport(
            source_env=source_env,
            target_env=target_env,
            drifts=[drift],
            generated_at=datetime(2024, 1, 1, 12, 0, 0),
        )

        data = report.to_dict()
        assert data["source_env"] == "prod"
        assert data["target_env"] == "staging"
        assert data["summary"]["total"] == 1
        assert data["summary"]["error"] == 1
        assert data["drifts"][0]["field_path"] == "spec.replicas"
        assert data["drifts"][0]["is_breaking"] is True
