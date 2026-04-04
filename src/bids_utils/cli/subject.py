"""CLI commands: bids-utils subject-rename, bids-utils remove."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from bids_utils._dataset import BIDSDataset
from bids_utils.cli import main
from bids_utils.cli._common import common_options
from bids_utils.subject import remove_subject, rename_subject


@main.command("subject-rename")
@click.argument("old")
@click.argument("new")
@click.option("--include-sourcedata", is_flag=True, help="Also rename in sourcedata/.")
@common_options
def subject_rename_cmd(
    old: str,
    new: str,
    include_sourcedata: bool,
    dry_run: bool,
    json_output: bool,
    verbose: int,
    quiet: bool,
    force: bool,
    schema_version: str | None,
) -> None:
    """Rename a subject across the entire dataset."""
    try:
        dataset = BIDSDataset.from_path(Path.cwd())
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    result = rename_subject(
        dataset, old, new, dry_run=dry_run, include_sourcedata=include_sourcedata
    )
    _output_result(result, json_output, dry_run)


@main.command("remove")
@click.argument("subject")
@common_options
def remove_cmd(
    subject: str,
    dry_run: bool,
    json_output: bool,
    verbose: int,
    quiet: bool,
    force: bool,
    schema_version: str | None,
) -> None:
    """Remove a subject from the dataset."""
    try:
        dataset = BIDSDataset.from_path(Path.cwd())
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    result = remove_subject(dataset, subject, dry_run=dry_run, force=force)
    _output_result(result, json_output, dry_run)


def _output_result(result: object, json_output: bool, dry_run: bool) -> None:
    from bids_utils._types import OperationResult

    assert isinstance(result, OperationResult)

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
        for w in result.warnings:
            click.echo(f"Warning: {w}", err=True)
        for e in result.errors:
            click.echo(f"Error: {e}", err=True)

    if not result.success:
        sys.exit(2)
