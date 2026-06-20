"""Command-line interface for Config Drift."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from config_drift.detector import DriftDetector
from config_drift.models import DriftReport, DriftSeverity, Environment
from config_drift.parsers import parse_config_file
from config_drift.reporters import get_reporter

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="config-drift")
def main() -> None:
    """Config Drift - Detect configuration drift across environments."""
    pass


@main.command()
@click.argument("source_dir", type=click.Path(exists=True, path_type=Path))
@click.argument("target_dir", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--source-name",
    default="source",
    help="Name for source environment",
)
@click.option(
    "--target-name",
    default="target",
    help="Name for target environment",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["console", "json", "summary", "sarif"]),
    default="console",
    help="Output format",
)
@click.option(
    "--severity",
    type=click.Choice(["info", "warning", "error", "critical"]),
    default="info",
    help="Minimum severity to report",
)
@click.option(
    "--exclude",
    multiple=True,
    help="Glob patterns to exclude",
)
@click.option(
    "--include",
    multiple=True,
    help="Glob patterns to include",
)
@click.option(
    "--fail-on",
    type=click.Choice(["warning", "error", "critical"]),
    default=None,
    help="Exit with error code if drifts of this severity or higher are found",
)
def compare(
    source_dir: Path,
    target_dir: Path,
    source_name: str,
    target_name: str,
    output_format: str,
    severity: str,
    exclude: tuple[str, ...],
    include: tuple[str, ...],
    fail_on: Optional[str],
) -> None:
    """Compare two environment directories for configuration drift."""
    try:
        source_env = _load_environment(source_dir, source_name, exclude, include)
        target_env = _load_environment(target_dir, target_name, exclude, include)

        detector = DriftDetector()
        report = detector.compare_environments(source_env, target_env)

        min_severity = DriftSeverity(severity)
        filtered_drifts = [d for d in report.drifts if _severity_ge(d.severity, min_severity)]
        report = DriftReport(
            source_env=report.source_env,
            target_env=report.target_env,
            drifts=filtered_drifts,
            generated_at=report.generated_at,
        )

        reporter = get_reporter(output_format, verbose=True)
        output = reporter.report(report)
        if output:
            console.print(output)

        if fail_on:
            fail_severity = DriftSeverity(fail_on)
            if any(_severity_ge(d.severity, fail_severity) for d in report.drifts):
                console.print(f"\n[red]Fail-on threshold ({fail_on}) exceeded[/red]")
                sys.exit(1)

        if report.has_breaking_changes:
            sys.exit(2)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@main.command()
@click.argument("directory", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--name",
    default="environment",
    help="Environment name",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["console", "json"]),
    default="console",
    help="Output format",
)
@click.option(
    "--exclude",
    multiple=True,
    help="Glob patterns to exclude",
)
@click.option(
    "--include",
    multiple=True,
    help="Glob patterns to include",
)
def scan(
    directory: Path,
    name: str,
    output_format: str,
    exclude: tuple[str, ...],
    include: tuple[str, ...],
) -> None:
    """Scan a directory and list all discovered configuration resources."""
    try:
        env = _load_environment(directory, name, exclude, include)

        if output_format == "json":
            import json

            data = {
                "environment": name,
                "files": len(env.config_files),
                "resources": [
                    {
                        "kind": r.kind,
                        "name": r.name,
                        "namespace": r.namespace,
                        "identifier": r.identifier,
                        "file": str(r.path) if hasattr(r, "path") else "unknown",
                    }
                    for cf in env.config_files
                    for r in cf.resources
                ],
            }
            console.print(json.dumps(data, indent=2))
        else:
            console.print(f"\n[bold]Environment: {name}[/bold]")
            console.print(f"Config files: {len(env.config_files)}")
            total_resources = sum(len(cf.resources) for cf in env.config_files)
            console.print(f"Total resources: {total_resources}")

            table = Table(title="Discovered Resources")
            table.add_column("Kind")
            table.add_column("Name")
            table.add_column("Namespace")
            table.add_column("File")

            for cf in env.config_files:
                for resource in cf.resources:
                    table.add_row(
                        resource.kind,
                        resource.name,
                        resource.namespace or "-",
                        str(cf.path.relative_to(directory)),
                    )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def _load_environment(
    directory: Path,
    name: str,
    exclude_patterns: tuple[str, ...],
    include_patterns: tuple[str, ...],
) -> Environment:
    config_files = []

    for file_path in directory.rglob("*"):
        if not file_path.is_file():
            continue

        if _should_exclude(file_path, exclude_patterns, include_patterns):
            continue

        try:
            config_file = parse_config_file(file_path)
            if config_file.resources:
                config_files.append(config_file)
        except Exception:
            pass

    return Environment(name=name, config_files=config_files)


def _should_exclude(
    path: Path,
    exclude_patterns: tuple[str, ...],
    include_patterns: tuple[str, ...],
) -> bool:
    import fnmatch

    relative = str(path)

    if include_patterns and not any(fnmatch.fnmatch(relative, pat) for pat in include_patterns):
        return True

    return bool(
        exclude_patterns and any(fnmatch.fnmatch(relative, pat) for pat in exclude_patterns)
    )


def _severity_ge(a: DriftSeverity, b: DriftSeverity) -> bool:
    order = {"info": 0, "warning": 1, "error": 2, "critical": 3}
    return order[a.value] >= order[b.value]


if __name__ == "__main__":
    main()
