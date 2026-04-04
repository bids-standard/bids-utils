"""CLI command: bids-utils rename."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from bids_utils._dataset import BIDSDataset
from bids_utils.cli import main
from bids_utils.cli._common import common_options
from bids_utils.rename import rename_file


def _parse_set_option(values: tuple[str, ...]) -> dict[str, str]:
    """Parse --set key=value pairs into a dict."""
    result: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise click.BadParameter(f"Expected key=value format, got: {item}")
        key, value = item.split("=", 1)
        result[key] = value
    return result


@main.command()
@click.argument("file", type=click.Path(exists=False))
@click.option(
    "--set",
    "set_entities",
    multiple=True,
    help="Set entity value (e.g., --set task=nback). Can be repeated.",
)
@click.option("--suffix", default=None, help="Set a new suffix.")
@click.option("--include-sourcedata", is_flag=True, help="Also rename in sourcedata/.")
@common_options
def rename(
    file: str,
    set_entities: tuple[str, ...],
    suffix: str | None,
    include_sourcedata: bool,
    dry_run: bool,
    json_output: bool,
    verbose: int,
    quiet: bool,
    force: bool,
    schema_version: str | None,
) -> None:
    """Rename a BIDS file and all its sidecars."""
    file_path = Path(file).resolve()

    try:
        dataset = BIDSDataset.from_path(file_path)
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if schema_version:
        dataset.schema_version = schema_version

    entities = _parse_set_option(set_entities) if set_entities else None

    result = rename_file(
        dataset,
        file_path,
        set_entities=entities,
        new_suffix=suffix,
        dry_run=dry_run,
        include_sourcedata=include_sourcedata,
    )

    if json_output:
        output = {
            "success": result.success,
            "dry_run": result.dry_run,
            "changes": [
                {
                    "action": c.action,
                    "source": str(c.source),
                    "target": str(c.target) if c.target else None,
                    "detail": c.detail,
                }
                for c in result.changes
            ],
            "warnings": result.warnings,
            "errors": result.errors,
        }
        click.echo(json.dumps(output, indent=2))
    else:
        prefix = "[DRY RUN] " if dry_run else ""
        for change in result.changes:
            click.echo(f"{prefix}{change.detail}")
        for warning in result.warnings:
            click.echo(f"Warning: {warning}", err=True)
        for error in result.errors:
            click.echo(f"Error: {error}", err=True)

    if not result.success:
        sys.exit(2 if result.errors else 1)
