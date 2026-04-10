"""CLI command: bids-utils split."""

from __future__ import annotations

import click

from bids_utils.cli import main
from bids_utils.cli._common import common_options, load_dataset, output_result
from bids_utils.split import split_dataset


@main.command()
@click.option("--suffix", default=None, help="Filter by suffix (e.g., bold).")
@click.option("--datatype", default=None, help="Filter by datatype (e.g., func).")
@click.option("--output", "-o", required=True, help="Output dataset path.")
@common_options
def split(
    suffix: str | None,
    datatype: str | None,
    output: str,
    dry_run: str | None,
    json_output: bool,
    verbose: int,
    quiet: bool,
    force: bool,
    schema_version: str | None,
) -> None:
    """Extract a subset of a BIDS dataset."""
    dataset = load_dataset()

    result = split_dataset(
        dataset, output, suffix=suffix, datatype=datatype, dry_run=bool(dry_run)
    )

    output_result(result, json_output, dry_run)
