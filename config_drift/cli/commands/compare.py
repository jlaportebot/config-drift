"""Compare command — compare two configuration sets."""

import click
from rich.console import Console
from rich.table import Table

from config_drift.detectors import BasicDriftDetector, SemanticDriftDetector
from config_drift.models.drift import DriftSummary
from config_drift.parsers.file import FileParser


@click.command("compare")
@click.option(
    "--baseline",
    "-b",
    type=click.Path(exists=True),
    required=True,
    help="Path to baseline configuration directory/file",
)
@click.option(
    "--current",
    "-c",
    type=click.Path(exists=True),
    required=True,
    help="Path to current configuration directory/file",
)
@click.option(
    "--detector",
    type=click.Choice(["basic", "semantic", "all"]),
    default="all",
    help="Drift detection algorithm",
)
@click.option(
    "--severity",
    type=click.Choice(["low", "medium", "high", "critical"]),
    default="low",
    help="Minimum severity threshold",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
@click.pass_context
def compare_cmd(ctx, baseline, current, detector, severity, output_format):
    """Compare two configuration sets for drift.

    \b
    Examples:
      $ config-drift compare --baseline ./baselines/ --current ./k8s/
      $ config-drift compare --baseline old-compose.yml --current new-compose.yml
      $ config-drift compare -b ./tf/baseline/ -c ./tf/current/ --detector semantic
    """
    console = ctx.obj.get("console", Console())

    # Parse both configurations
    parser = FileParser()
    baseline_result = parser.parse(baseline)
    current_result = parser.parse(current)

    if not baseline_result.configs:
        console.print(f"[red]No configurations found in baseline: {baseline}[/red]")
        return

    if not current_result.configs:
        console.print(f"[red]No configurations found in current: {current}[/red]")
        return

    # Detect drift
    summary = DriftSummary()

    for bl_config in baseline_result.configs:
        for cur_config in current_result.configs:
            # Match by resource_id if available
            if bl_config.resource_id and bl_config.resource_id == cur_config.resource_id:
                if detector in ["basic", "all"]:
                    detector_inst = BasicDriftDetector()
                    drifts = detector_inst.detect(bl_config, cur_config)
                    for d in drifts:
                        summary.add(d)

                if detector in ["semantic", "all"]:
                    detector_inst = SemanticDriftDetector()
                    drifts = detector_inst.detect(bl_config, cur_config)
                    for d in drifts:
                        summary.add(d)
            elif not bl_config.resource_id:
                # If no resource_id, compare all pairs (simplified)
                if detector in ["basic", "all"]:
                    detector_inst = BasicDriftDetector()
                    drifts = detector_inst.detect(bl_config, cur_config)
                    for d in drifts:
                        summary.add(d)

    # Filter by severity
    min_severity = {"low": 0, "medium": 1, "high": 2, "critical": 3}[severity]
    summary.drifts = [
        d
        for d in summary.drifts
        if {"low": 0, "medium": 1, "high": 2, "critical": 3}[d.severity.value] >= min_severity
    ]

    # Display results
    if output_format == "table":
        _display_comparison(console, baseline_result, current_result, summary)
    elif output_format == "json":
        import json

        console.print_json(json.dumps(summary.to_dict(), indent=2))


def _display_comparison(console, baseline_result, current_result, summary):
    """Display comparison results as a rich table."""
    console.print(f"[bold]Baseline:[/bold] {len(baseline_result.configs)} configurations")
    console.print(f"[bold]Current:[/bold]  {len(current_result.configs)} configurations")

    if summary.total_drifts == 0:
        console.print(
            "[green]✓ No configuration drift detected between baseline and current.[/green]"
        )
        return

    # Summary table
    table = Table(title="Drift Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="bold")

    table.add_row("Total Drifts", str(summary.total_drifts))
    for dtype, count in summary.by_type.items():
        table.add_row(f"  {dtype.value}", str(count))
    for sev, count in summary.by_severity.items():
        table.add_row(f"  {sev.value}", str(count))

    console.print(table)

    # Detail table
    detail = Table(title="Drift Details")
    detail.add_column("Path", style="cyan", max_width=40)
    detail.add_column("Type", style="red")
    detail.add_column("Severity", style="yellow")
    detail.add_column("Expected", max_width=25)
    detail.add_column("Actual", max_width=25)

    for drift in summary.drifts[:100]:
        detail.add_row(
            drift.path,
            drift.drift_type.value,
            drift.severity.value,
            str(drift.expected)[:25],
            str(drift.actual)[:25],
        )

    console.print(detail)
