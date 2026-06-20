"""Scan command — detect configuration drift."""

import json
import uuid
from datetime import datetime

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config_drift.detectors import BasicDriftDetector, SemanticDriftDetector
from config_drift.models.config import ConfigSource
from config_drift.models.drift import DriftSummary
from config_drift.models.scan import ScanConfig


@click.command("scan")
@click.option(
    "--source",
    "-s",
    type=click.Choice(["kubernetes", "docker_compose", "terraform", "helm", "file"]),
    multiple=True,
    help="Configuration sources to scan",
)
@click.option("--path", "-p", type=click.Path(), multiple=True, help="Paths to scan")
@click.option("--namespace", "-n", multiple=True, help="Namespaces to scan (Kubernetes/Helm)")
@click.option("--label-selector", "-l", help="Label selector for filtering resources")
@click.option(
    "--severity",
    type=click.Choice(["low", "medium", "high", "critical"]),
    default="low",
    help="Minimum severity threshold",
)
@click.option(
    "--detector",
    type=click.Choice(["basic", "semantic", "all"]),
    default="all",
    help="Drift detection algorithm",
)
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "yaml"]),
    default="table",
    help="Output format",
)
@click.option("--baseline", "-b", type=click.Path(), help="Baseline directory for comparison")
@click.pass_context
def scan_cmd(
    ctx,
    source,
    path,
    namespace,
    label_selector,
    severity,
    detector,
    output,
    output_format,
    baseline,
):
    """Scan configuration sources for drift.

    \b
    Examples:
      $ config-drift scan --source file --path ./k8s/
      $ config-drift scan --source kubernetes --namespace default
      $ config-drift scan --source docker_compose --path docker-compose.yml
      $ config-drift scan --source terraform --path ./terraform/
      $ config-drift scan --source helm --path releases
    """
    console = ctx.obj.get("console", Console())
    verbose = ctx.obj.get("verbose", False)

    scan_id = str(uuid.uuid4())[:8]
    started_at = datetime.utcnow()

    # Determine sources
    sources = [ConfigSource(s) for s in source] if source else [ConfigSource.FILE]
    scan_config = ScanConfig(
        sources=sources,
        paths=[click.Path(p) for p in path] if path else [],
        namespaces=list(namespace),
        label_selectors={"selector": label_selector} if label_selector else {},
        severity_threshold=severity,
        output_format=output_format,
        output_file=output,
        baseline_file=baseline,
    )

    # Parse configurations
    all_configs = []
    errors = []
    for src in sources:
        for p in path or ["."]:
            parser = _get_parser_for_source(src)
            if parser:
                result = parser.parse(p, namespaces=list(namespace), label_selector=label_selector)
                all_configs.extend(result.configs)
                errors.extend(result.errors)

    if not all_configs and not errors:
        console.print("[yellow]No configurations found to scan.[/yellow]")
        return

    # Detect drift if baseline is provided
    drift_summary = None
    if baseline:
        from config_drift.storage.file_store import FileStore

        store = FileStore(baseline)
        baseline_configs = []
        for src in sources:
            for bl in store.list_baselines(src.value):
                bl_config = store.get_baseline(bl["source"], bl["resource_id"], bl.get("namespace"))
                if bl_config:
                    baseline_configs.append(bl_config)

        if baseline_configs:
            drift_summary = _detect_drift(baseline_configs, all_configs, detector)
        else:
            console.print("[yellow]No baselines found for comparison.[/yellow]")
            drift_summary = DriftSummary()

    # Display results
    if output_format == "table":
        _display_table(console, scan_id, all_configs, drift_summary, errors)
    elif output_format == "json":
        result = _to_json(scan_id, started_at, all_configs, drift_summary, errors)
        if output:
            from pathlib import Path

            Path(output).write_text(json.dumps(result, indent=2))
        else:
            console.print_json(json.dumps(result, indent=2))
    elif output_format == "yaml":
        import yaml

        result = _to_json(scan_id, started_at, all_configs, drift_summary, errors)
        if output:
            from pathlib import Path

            Path(output).write_text(yaml.dump(result, sort_keys=False))
        else:
            console.print(yaml.dump(result, sort_keys=False))

    # Save to output file
    if output and output_format == "table":
        console.print(f"[green]Results saved to {output}[/green]")


def _get_parser_for_source(source: ConfigSource):
    """Get the appropriate parser for a source type."""
    if source == ConfigSource.KUBERNETES:
        from config_drift.parsers.kubernetes import KubernetesParser

        return KubernetesParser()
    if source == ConfigSource.DOCKER_COMPOSE:
        from config_drift.parsers.docker_compose import DockerComposeParser

        return DockerComposeParser()
    if source == ConfigSource.TERRAFORM:
        from config_drift.parsers.terraform import TerraformParser

        return TerraformParser()
    if source == ConfigSource.HELM:
        from config_drift.parsers.helm import HelmParser

        return HelmParser()
    if source == ConfigSource.FILE:
        from config_drift.parsers.file import FileParser

        return FileParser()
    return None


def _detect_drift(baselines, current_configs, detector_type):
    """Run drift detection."""
    summary = DriftSummary()

    if detector_type in ["basic", "all"]:
        basic_detector = BasicDriftDetector()
        for baseline in baselines:
            for current in current_configs:
                if baseline.resource_id == current.resource_id:
                    drifts = basic_detector.detect(baseline, current)
                    for d in drifts:
                        summary.add(d)

    if detector_type in ["semantic", "all"]:
        semantic_detector = SemanticDriftDetector()
        for baseline in baselines:
            for current in current_configs:
                if baseline.resource_id == current.resource_id:
                    drifts = semantic_detector.detect(baseline, current)
                    for d in drifts:
                        summary.add(d)

    return summary


def _display_table(console, scan_id, configs, drift_summary, errors):
    """Display scan results as a rich table."""
    console.print(Panel(f"[bold]Config Drift Scan — {scan_id}[/bold]", expand=False))

    # Config summary
    table = Table(title="Parsed Configurations")
    table.add_column("Source", style="cyan")
    table.add_column("Resource", style="magenta")
    table.add_column("Namespace", style="green")
    table.add_column("Labels", style="yellow")

    for c in configs[:50]:  # Limit display
        labels_str = ", ".join(f"{k}={v}" for k, v in list(c.labels.items())[:3])
        table.add_row(c.source.value, c.resource_id or "N/A", c.namespace or "N/A", labels_str)

    console.print(table)

    # Drift summary
    if drift_summary and drift_summary.total_drifts > 0:
        drift_table = Table(title="Drift Summary")
        drift_table.add_column("Type", style="red")
        drift_table.add_column("Count", style="bold")
        drift_table.add_column("Severity", style="yellow")
        drift_table.add_column("Count", style="bold")

        for dtype, count in drift_summary.by_type.items():
            drift_table.add_row(dtype.value, str(count))

        for sev, count in drift_summary.by_severity.items():
            drift_table.add_row("", "", sev.value, str(count))

        console.print(drift_table)

        # Detail table
        detail_table = Table(title="Drift Details")
        detail_table.add_column("Path", style="cyan")
        detail_table.add_column("Type", style="red")
        detail_table.add_column("Severity", style="yellow")
        detail_table.add_column("Source", style="green")
        detail_table.add_column("Expected", style="white")
        detail_table.add_column("Actual", style="white")

        for drift in drift_summary.drifts[:50]:
            detail_table.add_row(
                drift.path,
                drift.drift_type.value,
                drift.severity.value,
                drift.source,
                str(drift.expected)[:30],
                str(drift.actual)[:30],
            )

        console.print(detail_table)
    elif drift_summary:
        console.print("[green]✓ No configuration drift detected.[/green]")

    # Errors
    if errors:
        error_table = Table(title="Errors")
        error_table.add_column("Error", style="red")
        for error in errors[:20]:
            error_table.add_row(error)
        console.print(error_table)


def _to_json(scan_id, started_at, configs, drift_summary, errors):
    """Convert scan results to JSON dict."""
    return {
        "scan_id": scan_id,
        "started_at": started_at.isoformat(),
        "config_count": len(configs),
        "configs": [c.to_dict() for c in configs],
        "drift_summary": drift_summary.to_dict() if drift_summary else None,
        "errors": errors,
    }
