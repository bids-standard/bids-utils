"""CLI command: bids-utils remove-run."""

from __future__ import annotations

import click

from bids_utils.cli import main
from bids_utils.cli._common import common_options, load_dataset, output_result
from bids_utils.run import remove_run


@main.command("remove-run")
@click.argument("subject")
@click.argument("run")
@click.option(
    "--shift/--no-shift", default=True, help="Reindex subsequent runs (default: shift)."
)
@common_options
def remove_run_cmd(
    subject: str,
    run: str,
    shift: bool,
    dry_run: str | None,
    json_output: bool,
    verbose: int,
    quiet: bool,
    force: bool,
    schema_version: str | None,
) -> None:
    """Remove a run and optionally reindex subsequent runs."""
    dataset = load_dataset()

    result = remove_run(dataset, subject, run, shift=shift, dry_run=bool(dry_run))

    output_result(result, json_output, dry_run)
