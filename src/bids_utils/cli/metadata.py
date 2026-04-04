"""CLI commands: bids-utils metadata {aggregate,segregate,audit}."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from bids_utils._dataset import BIDSDataset
from bids_utils.cli import main
from bids_utils.cli._common import common_options
from bids_utils.metadata import aggregate_metadata, audit_metadata, segregate_metadata


@main.group()
def metadata() -> None:
    """Metadata manipulation commands."""


@metadata.command()
@click.argument("scope", required=False, default=None)
@click.option("--mode", type=click.Choice(["copy", "move"]), default="move", help="Copy or move metadata up.")
@common_options
def aggregate(
    scope: str | None,
    mode: str,
    dry_run: bool,
    json_output: bool,
    verbose: int,
    quiet: bool,
    force: bool,
    schema_version: str | None,
) -> None:
    """Hoist common metadata up the inheritance hierarchy."""
    try:
        dataset = BIDSDataset.from_path(Path.cwd())
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    result = aggregate_metadata(dataset, scope=scope, mode=mode, dry_run=dry_run)  # type: ignore[arg-type]

    prefix = "[DRY RUN] " if dry_run else ""
    for change in result.changes:
        click.echo(f"{prefix}{change.detail}")


@metadata.command()
@click.argument("scope", required=False, default=None)
@common_options
def segregate(
    scope: str | None,
    dry_run: bool,
    json_output: bool,
    verbose: int,
    quiet: bool,
    force: bool,
    schema_version: str | None,
) -> None:
    """Push all metadata down to leaf-level sidecars."""
    try:
        dataset = BIDSDataset.from_path(Path.cwd())
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    result = segregate_metadata(dataset, scope=scope, dry_run=dry_run)

    prefix = "[DRY RUN] " if dry_run else ""
    for change in result.changes:
        click.echo(f"{prefix}{change.detail}")


@metadata.command()
@common_options
def audit(
    dry_run: bool,
    json_output: bool,
    verbose: int,
    quiet: bool,
    force: bool,
    schema_version: str | None,
) -> None:
    """Report metadata inconsistencies."""
    try:
        dataset = BIDSDataset.from_path(Path.cwd())
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    result = audit_metadata(dataset)

    if json_output:
        click.echo(json.dumps({"inconsistent_keys": result.inconsistent_keys, "total_files": result.total_files}, indent=2))
    else:
        if not result.inconsistent_keys:
            click.echo("No inconsistencies found.")
        else:
            click.echo(f"Found {len(result.inconsistent_keys)} inconsistent key(s):")
            for key, entries in result.inconsistent_keys.items():
                click.echo(f"  {key}: {len(entries)} files with different values")
