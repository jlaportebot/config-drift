"""Main CLI entry point for config-drift."""

import click
from rich.console import Console

from config_drift.cli.commands.baseline import baseline_cmd
from config_drift.cli.commands.compare import compare_cmd
from config_drift.cli.commands.report import report_cmd
from config_drift.cli.commands.scan import scan_cmd

console = Console()


@click.group()
@click.version_option(version="0.1.0")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--config", "-c", type=click.Path(), help="Path to config file")
@click.pass_context
def app(ctx, verbose, config):
    """🔍 Config Drift — Detect configuration drift across environments.

    Compare Kubernetes, Docker Compose, Terraform, and Helm configurations
    to detect unauthorized or unexpected changes.

    \b
    Supported sources:
      • Kubernetes (cluster resources)
      • Docker Compose (files and running containers)
      • Terraform (HCL files, state, plans)
      • Helm (charts and releases)

    \b
    Quick start:
      $ config-drift scan --source kubernetes --path ./k8s/
      $ config-drift baseline save --source kubernetes --path ./k8s/
      $ config-drift compare --baseline ./baselines/ --current ./k8s/
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["config"] = config
    ctx.obj["console"] = console


app.add_command(scan_cmd, "scan")
app.add_command(compare_cmd, "compare")
app.add_command(baseline_cmd, "baseline")
app.add_command(report_cmd, "report")


if __name__ == "__main__":
    app()
