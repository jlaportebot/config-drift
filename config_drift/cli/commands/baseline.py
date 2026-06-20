"""Baseline command — manage configuration baselines."""

import click
from rich.console import Console
from rich.table import Table

from config_drift.parsers.file import FileParser
from config_drift.storage.file_store import FileStore


@click.group("baseline")
@click.pass_context
def baseline_cmd(ctx):
    """Manage configuration baselines.

    \b
    Subcommands:
      save     Save current configuration as baseline
      list     List all saved baselines
      show     Show a specific baseline
      delete   Delete a baseline
    """


@baseline_cmd.command("save")
@click.option(
    "--source",
    "-s",
    type=click.Choice(["kubernetes", "docker_compose", "terraform", "helm", "file"]),
    default="file",
    help="Configuration source",
)
@click.option(
    "--path", "-p", type=click.Path(exists=True), required=True, help="Path to configuration"
)
@click.option(
    "--store", "-b", type=click.Path(), default="baselines", help="Baseline storage directory"
)
@click.pass_context
def save_cmd(ctx, source, path, store):
    """Save current configuration as a baseline."""
    console = ctx.obj.get("console", Console())

    parser = FileParser()
    result = parser.parse(path)

    if not result.configs:
        console.print(f"[red]No configurations found at: {path}[/red]")
        return

    storage = FileStore(store)
    saved_count = 0
    for config in result.configs:
        storage.save_baseline(config)
        saved_count += 1

    console.print(f"[green]✓ Saved {saved_count} baseline(s) to {store}[/green]")
    if result.errors:
        for error in result.errors:
            console.print(f"[yellow]Warning: {error}[/yellow]")


@baseline_cmd.command("list")
@click.option("--source", "-s", help="Filter by source type")
@click.option(
    "--store", "-b", type=click.Path(), default="baselines", help="Baseline storage directory"
)
@click.pass_context
def list_cmd(ctx, source, store):
    """List all saved baselines."""
    console = ctx.obj.get("console", Console())

    storage = FileStore(store)
    baselines = storage.list_baselines(source)

    if not baselines:
        console.print("[yellow]No baselines found.[/yellow]")
        return

    table = Table(title="Configuration Baselines")
    table.add_column("ID", style="cyan")
    table.add_column("Source", style="magenta")
    table.add_column("Resource", style="green")
    table.add_column("Namespace", style="blue")
    table.add_column("Last Updated", style="yellow")

    for bl in baselines:
        table.add_row(
            bl["id"],
            bl["source"],
            bl["resource_id"],
            bl.get("namespace") or "-",
            bl.get("parsed_at", "unknown"),
        )

    console.print(table)


@baseline_cmd.command("show")
@click.argument("baseline_id")
@click.option(
    "--store", "-b", type=click.Path(), default="baselines", help="Baseline storage directory"
)
@click.pass_context
def show_cmd(ctx, baseline_id, store):
    """Show details of a specific baseline."""
    console = ctx.obj.get("console", Console())

    parts = baseline_id.split("/", 1)
    source = parts[0]
    resource_id = parts[1] if len(parts) > 1 else ""

    storage = FileStore(store)
    config = storage.get_baseline(source, resource_id)

    if not config:
        console.print(f"[red]Baseline not found: {baseline_id}[/red]")
        return

    import yaml

    console.print(
        Panel(
            yaml.dump(config.content, sort_keys=False),
            title=f"[bold]{baseline_id}[/bold]",
            expand=False,
        )
    )


@baseline_cmd.command("delete")
@click.argument("baseline_id")
@click.option(
    "--store", "-b", type=click.Path(), default="baselines", help="Baseline storage directory"
)
@click.confirmation_option(prompt="Delete this baseline?")
@click.pass_context
def delete_cmd(ctx, baseline_id, store):
    """Delete a baseline."""
    console = ctx.obj.get("console", Console())

    parts = baseline_id.split("/", 1)
    source = parts[0]
    resource_id = parts[1] if len(parts) > 1 else ""

    storage = FileStore(store)
    if storage.delete_baseline(source, resource_id):
        console.print(f"[green]✓ Deleted baseline: {baseline_id}[/green]")
    else:
        console.print(f"[red]Baseline not found: {baseline_id}[/red]")


from rich.panel import Panel  # noqa: E402
