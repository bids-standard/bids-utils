"""CLI command: bids-utils remove-run."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from bids_utils._dataset import BIDSDataset
from bids_utils.cli import main
from bids_utils.cli._common import common_options
from bids_utils.run import remove_run


@main.command("remove-run")
@click.argument("subject")
@click.argument("run")
@click.option("--shift/--no-shift", default=True, help="Reindex subsequent runs (default: shift).")
@common_options
def remove_run_cmd(
    subject: str,
    run: str,
    shift: bool,
    dry_run: bool,
    json_output: bool,
    verbose: int,
    quiet: bool,
    force: bool,
    schema_version: str | None,
) -> None:
    """Remove a run and optionally reindex subsequent runs."""
    try:
        dataset = BIDSDataset.from_path(Path.cwd())
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    result = remove_run(dataset, subject, run, shift=shift, dry_run=dry_run)

    if json_output:
        output = {
            "success": result.success,
            "dry_run": result.dry_run,
            "changes": [
                {"action": c.action, "source": str(c.source), "target": str(c.target) if c.target else None, "detail": c.detail}
                for c in result.changes
            ],
            "errors": result.errors,
        }
        click.echo(json.dumps(output, indent=2))
    else:
        prefix = "[DRY RUN] " if dry_run else ""
        for change in result.changes:
            click.echo(f"{prefix}{change.detail}")
        for e in result.errors:
            click.echo(f"Error: {e}", err=True)

    if not result.success:
        sys.exit(2)
