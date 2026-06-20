"""Reporters for drift output in various formats."""

from __future__ import annotations

import json

from rich.console import Console
from rich.table import Table
from rich.text import Text

from config_drift.models import DriftReport, DriftSeverity


class BaseReporter:
    """Base class for drift reporters."""

    def report(self, drift_report: DriftReport) -> str:
        raise NotImplementedError


class ConsoleReporter(BaseReporter):
    """Rich console reporter with colored output."""

    def __init__(self, console: Console | None = None, verbose: bool = False):
        self.console = console or Console()
        self.verbose = verbose

    def report(self, drift_report: DriftReport) -> str:
        self._print_summary(drift_report)
        if drift_report.drifts:
            self._print_drifts_table(drift_report)
        return ""

    def _print_summary(self, report: DriftReport) -> None:
        summary = report.to_dict()["summary"]
        self.console.print(
            f"\n[bold]Drift Report: {report.source_env.name} → {report.target_env.name}[/bold]"
        )
        self.console.print(f"Generated: {report.generated_at.isoformat()}")
        self.console.print(f"Total drifts: [bold]{summary['total']}[/bold]")

        if summary["critical"] > 0:
            self.console.print(f"  [red]Critical: {summary['critical']}[/red]")
        if summary["error"] > 0:
            self.console.print(f"  [red]Error: {summary['error']}[/red]")
        if summary["warning"] > 0:
            self.console.print(f"  [yellow]Warning: {summary['warning']}[/yellow]")
        if summary["info"] > 0:
            self.console.print(f"  [blue]Info: {summary['info']}[/blue]")

        if summary["has_breaking_changes"]:
            self.console.print("\n[red bold]⚠ BREAKING CHANGES DETECTED[/red bold]")

    def _print_drifts_table(self, report: DriftReport) -> None:
        table = Table(title="Configuration Drifts")
        table.add_column("Severity", style="bold")
        table.add_column("Resource")
        table.add_column("Field")
        table.add_column("Source → Target")
        table.add_column("Description")

        for drift in sorted(report.drifts, key=lambda d: self._severity_order(d.severity)):
            severity_style = self._severity_style(drift.severity)
            resource = f"{drift.resource_kind}/{drift.resource_name}"
            if drift.namespace:
                resource = f"{drift.namespace}/{resource}"

            source_str = (
                str(drift.source_value) if drift.source_value is not None else "[dim]none[/dim]"
            )
            target_str = (
                str(drift.target_value) if drift.target_value is not None else "[dim]none[/dim]"
            )

            if len(source_str) > 40:
                source_str = source_str[:37] + "..."
            if len(target_str) > 40:
                target_str = target_str[:37] + "..."

            table.add_row(
                Text(drift.severity.value.upper(), style=severity_style),
                resource,
                drift.field_path,
                f"{source_str} → {target_str}",
                drift.description,
            )

        self.console.print(table)

    def _severity_order(self, severity: DriftSeverity) -> int:
        return {"critical": 0, "error": 1, "warning": 2, "info": 3}[severity.value]

    def _severity_style(self, severity: DriftSeverity) -> str:
        return {
            DriftSeverity.CRITICAL: "bold red",
            DriftSeverity.ERROR: "red",
            DriftSeverity.WARNING: "yellow",
            DriftSeverity.INFO: "blue",
        }[severity]


class JSONReporter(BaseReporter):
    """JSON reporter for machine-readable output."""

    def __init__(self, pretty: bool = True):
        self.pretty = pretty

    def report(self, drift_report: DriftReport) -> str:
        return json.dumps(drift_report.to_dict(), indent=2 if self.pretty else None)


class SummaryReporter(BaseReporter):
    """Minimal summary reporter for CI/CD integration."""

    def report(self, drift_report: DriftReport) -> str:
        summary = drift_report.to_dict()["summary"]
        lines = [
            f"config-drift: {summary['total']} drifts detected",
            (
                f"  critical: {summary['critical']}, "
                f"error: {summary['error']}, "
                f"warning: {summary['warning']}, "
                f"info: {summary['info']}"
            ),
        ]
        if summary["has_breaking_changes"]:
            lines.append("BREAKING CHANGES: YES")
        return "\n".join(lines)


class SARIFReporter(BaseReporter):
    """SARIF reporter for integration with security tools."""

    def report(self, drift_report: DriftReport) -> str:
        results = []
        for drift in drift_report.drifts:
            level = {
                DriftSeverity.CRITICAL: "error",
                DriftSeverity.ERROR: "error",
                DriftSeverity.WARNING: "warning",
                DriftSeverity.INFO: "note",
            }[drift.severity]

            results.append({
                "ruleId": f"config-drift.{drift.severity.value}",
                "level": level,
                "message": {"text": drift.description},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": drift.resource_identifier},
                            "region": {"startLine": 1},
                        }
                    }
                ],
                "properties": {
                    "fieldPath": drift.field_path,
                    "sourceValue": str(drift.source_value),
                    "targetValue": str(drift.target_value),
                    "sourceEnv": drift.source_env,
                    "targetEnv": drift.target_env,
                },
            })

        sarif = {
            "version": "2.1.0",
            "$schema": "https://schemastore.org/schemas/json/sarif-2.1.0.json",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "config-drift",
                            "version": "0.1.0",
                            "informationUri": "https://github.com/jlaportebot/config-drift",
                        }
                    },
                    "results": results,
                }
            ],
        }
        return json.dumps(sarif, indent=2)


def get_reporter(format: str, **kwargs) -> BaseReporter:
    """Get a reporter instance by format name."""
    reporters = {
        "console": ConsoleReporter,
        "json": JSONReporter,
        "summary": SummaryReporter,
        "sarif": SARIFReporter,
    }
    if format not in reporters:
        raise ValueError(f"Unknown reporter format: {format}")

    # Only pass verbose to ConsoleReporter
    if format == "console":
        return reporters[format](**kwargs)

    # Filter out verbose for other reporters
    filtered_kwargs = {k: v for k, v in kwargs.items() if k != "verbose"}
    return reporters[format](**filtered_kwargs)
