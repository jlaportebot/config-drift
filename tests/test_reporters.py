"""Tests for config_drift reporters."""

from __future__ import annotations

import json
from io import StringIO

import pytest
from rich.console import Console

from config_drift.models import Drift, DriftReport, DriftSeverity, Environment
from config_drift.reporters import ConsoleReporter, JSONReporter, SARIFReporter, SummaryReporter


def create_sample_report() -> DriftReport:
    drifts = [
        Drift(
            resource_identifier="Deployment/prod/app",
            resource_kind="Deployment",
            resource_name="app",
            namespace="prod",
            field_path="spec.replicas",
            source_value=3,
            target_value=5,
            severity=DriftSeverity.ERROR,
            source_env="prod",
            target_env="staging",
            description="Replica count changed",
        ),
        Drift(
            resource_identifier="Service/prod/api",
            resource_kind="Service",
            resource_name="api",
            namespace="prod",
            field_path="spec.ports[0].port",
            source_value=80,
            target_value=8080,
            severity=DriftSeverity.WARNING,
            source_env="prod",
            target_env="staging",
            description="Port changed",
        ),
        Drift(
            resource_identifier="ConfigMap/prod/config",
            resource_kind="ConfigMap",
            resource_name="config",
            namespace="prod",
            field_path="metadata.annotations.version",
            source_value="1.0",
            target_value="1.1",
            severity=DriftSeverity.INFO,
            source_env="prod",
            target_env="staging",
            description="Annotation updated",
        ),
    ]
    source = Environment(name="prod")
    target = Environment(name="staging")
    return DriftReport(source_env=source, target_env=target, drifts=drifts)


class TestJSONReporter:
    def test_report_output(self) -> None:
        report = create_sample_report()
        reporter = JSONReporter(pretty=True)
        output = reporter.report(report)

        data = json.loads(output)
        assert data["source_env"] == "prod"
        assert data["target_env"] == "staging"
        assert data["summary"]["total"] == 3
        assert data["summary"]["error"] == 1
        assert data["summary"]["warning"] == 1
        assert data["summary"]["info"] == 1
        assert len(data["drifts"]) == 3

    def test_report_compact(self) -> None:
        report = create_sample_report()
        reporter = JSONReporter(pretty=False)
        output = reporter.report(report)

        data = json.loads(output)
        assert data["summary"]["total"] == 3


class TestSummaryReporter:
    def test_report_output(self) -> None:
        report = create_sample_report()
        reporter = SummaryReporter()
        output = reporter.report(report)

        assert "3 drifts detected" in output
        assert "critical: 0" in output
        assert "error: 1" in output
        assert "warning: 1" in output
        assert "info: 1" in output

    def test_report_breaking_changes(self) -> None:
        drifts = [
            Drift(
                resource_identifier="Deployment/prod/app",
                resource_kind="Deployment",
                resource_name="app",
                namespace="prod",
                field_path="spec.replicas",
                source_value=3,
                target_value=5,
                severity=DriftSeverity.CRITICAL,
                source_env="prod",
                target_env="staging",
            ),
        ]
        report = DriftReport(
            source_env=Environment("prod"), target_env=Environment("staging"), drifts=drifts
        )
        reporter = SummaryReporter()
        output = reporter.report(report)

        assert "BREAKING CHANGES: YES" in output


class TestSARIFReporter:
    def test_report_output(self) -> None:
        report = create_sample_report()
        reporter = SARIFReporter()
        output = reporter.report(report)

        data = json.loads(output)
        assert data["version"] == "2.1.0"
        assert len(data["runs"]) == 1
        assert len(data["runs"][0]["results"]) == 3

        # Check first result
        result = data["runs"][0]["results"][0]
        assert result["ruleId"] == "config-drift.error"
        assert result["level"] == "error"
        assert "fieldPath" in result["properties"]


class TestConsoleReporter:
    def test_report_no_drifts(self) -> None:
        report = DriftReport(
            source_env=Environment("prod"), target_env=Environment("staging"), drifts=[]
        )
        output_buffer = StringIO()
        console = Console(file=output_buffer, force_terminal=False, no_color=True)
        reporter = ConsoleReporter(console=console)
        reporter.report(report)

        output = output_buffer.getvalue()
        assert "0 drifts" in output or "Total drifts: 0" in output

    def test_report_with_drifts(self) -> None:
        report = create_sample_report()
        output_buffer = StringIO()
        console = Console(file=output_buffer, force_terminal=False, no_color=True)
        reporter = ConsoleReporter(console=console)
        reporter.report(report)

        output = output_buffer.getvalue()
        assert "Drift Report" in output
        assert "prod → staging" in output
        # Description is truncated in table, check for partial
        assert "Replica count" in output
