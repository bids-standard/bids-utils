"""CLI command: bids-utils session-rename."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from bids_utils._dataset import BIDSDataset
from bids_utils.cli import main
from bids_utils.cli._common import common_options
from bids_utils.session import rename_session


@main.command("session-rename")
@click.argument("old")
@click.argument("new")
@click.option("--subject", default=None, help="Only rename for this subject.")
@common_options
def session_rename_cmd(
    old: str,
    new: str,
    subject: str | None,
    dry_run: bool,
    json_output: bool,
    verbose: int,
    quiet: bool,
    force: bool,
    schema_version: str | None,
) -> None:
    """Rename a session. Use '' for OLD to move into a new session."""
    try:
        dataset = BIDSDataset.from_path(Path.cwd())
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    result = rename_session(dataset, old, new, subject=subject, dry_run=dry_run)

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
