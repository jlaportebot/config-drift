"""Report command — generate drift reports."""

import json
from pathlib import Path

import click
from rich.console import Console

from config_drift.storage.duckdb_store import DuckDBStore
from config_drift.storage.file_store import FileStore


@click.command("report")
@click.option("--scan-id", help="Specific scan ID to report on")
@click.option(
    "--store", "-b", type=click.Path(), default="baselines", help="Baseline storage directory"
)
@click.option("--db", type=click.Path(), help="DuckDB database path for scan history")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["text", "json", "html", "markdown"]),
    default="text",
    help="Report output format",
)
@click.option("--last", is_flag=True, help="Report on most recent scan")
@click.pass_context
def report_cmd(ctx, scan_id, store, db, output, output_format, last):
    """Generate drift reports.

    \b
    Examples:
      $ config-drift report --last
      $ config-drift report --scan-id abc123
      $ config-drift report --db scans.db --last --format html --output report.html
    """
    console = ctx.obj.get("console", Console())

    if not db and not scan_id:
        # Generate report from baselines
        storage = FileStore(store)
        baselines = storage.list_baselines()

        if output_format == "text":
            console.print("[bold]Config Drift Baseline Report[/bold]")
            console.print(f"Total baselines: {len(baselines)}")
            for bl in baselines:
                console.print(f"  • {bl['source']}/{bl['resource_id']}")
        elif output_format == "json":
            data = {"baselines": baselines}
            if output:
                Path(output).write_text(json.dumps(data, indent=2))
            else:
                console.print_json(json.dumps(data, indent=2))
        elif output_format == "markdown":
            lines = [
                "# Config Drift Baseline Report",
                "",
                f"**Total baselines:** {len(baselines)}",
                "",
            ]
            lines.append("| Source | Resource | Namespace | Last Updated |")
            lines.append("|--------|----------|-----------|-------------|")
            for bl in baselines:
                lines.append(
                    f"| {bl['source']} | {bl['resource_id']} | {bl.get('namespace') or '-'} | {bl.get('parsed_at', 'unknown')} |"
                )
            md_content = "\n".join(lines)
            if output:
                Path(output).write_text(md_content)
            else:
                console.print(md_content)
        return

    if db:
        db_store = DuckDBStore(db)

        if last and not scan_id:
            scans = db_store.list_scans(limit=1)
            if scans:
                scan_id = scans[0]["scan_id"]

        if scan_id:
            scan = db_store.get_scan(scan_id)
            if scan:
                if output_format == "text":
                    console.print(f"[bold]Scan Report: {scan.scan_id}[/bold]")
                    console.print(f"Started: {scan.started_at}")
                    console.print(f"Completed: {scan.completed_at}")
                    if scan.summary:
                        console.print(f"Total drifts: {scan.summary.total_drifts}")
                elif output_format == "json":
                    data = scan.to_dict()
                    if output:
                        Path(output).write_text(json.dumps(data, indent=2))
                    else:
                        console.print_json(json.dumps(data, indent=2))
            else:
                console.print(f"[red]Scan not found: {scan_id}[/red]")
        else:
            console.print("[yellow]No scans found.[/yellow]")

        db_store.close()
