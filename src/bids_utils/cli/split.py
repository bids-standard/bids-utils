"""CLI command: bids-utils split."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from bids_utils._dataset import BIDSDataset
from bids_utils.cli import main
from bids_utils.cli._common import common_options
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
    dry_run: bool,
    json_output: bool,
    verbose: int,
    quiet: bool,
    force: bool,
    schema_version: str | None,
) -> None:
    """Extract a subset of a BIDS dataset."""
    try:
        dataset = BIDSDataset.from_path(Path.cwd())
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    result = split_dataset(dataset, output, suffix=suffix, datatype=datatype, dry_run=dry_run)

    if json_output:
        click.echo(json.dumps({
            "success": result.success,
            "changes": [{"detail": c.detail} for c in result.changes],
            "errors": result.errors,
        }, indent=2))
    else:
        prefix = "[DRY RUN] " if dry_run else ""
        for change in result.changes:
            click.echo(f"{prefix}{change.detail}")
        for e in result.errors:
            click.echo(f"Error: {e}", err=True)

    if not result.success:
        sys.exit(2)
