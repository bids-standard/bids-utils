"""CLI command: bids-utils merge."""

from __future__ import annotations

import click

from bids_utils.cli import main
from bids_utils.cli._common import common_options, output_result
from bids_utils.merge import merge_datasets


@main.command()
@click.argument("sources", nargs=-1, required=True)
@click.option("--output", "-o", required=True, help="Output dataset path.")
@click.option(
    "--into-sessions", multiple=True, help="Place each source into a session."
)
@click.option(
    "--on-conflict", type=click.Choice(["error", "add-runs"]), default="error"
)
@common_options
def merge(
    sources: tuple[str, ...],
    output: str,
    into_sessions: tuple[str, ...],
    on_conflict: str,
    dry_run: bool,
    json_output: bool,
    verbose: int,
    quiet: bool,
    force: bool,
    schema_version: str | None,
) -> None:
    """Merge multiple BIDS datasets."""
    sessions = list(into_sessions) if into_sessions else None

    result = merge_datasets(
        list(sources),
        output,
        into_sessions=sessions,
        on_conflict=on_conflict,  # type: ignore[arg-type]
        dry_run=dry_run,
    )

    output_result(result, json_output, dry_run)
