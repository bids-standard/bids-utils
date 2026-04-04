"""CLI command: bids-utils migrate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from bids_utils._dataset import BIDSDataset
from bids_utils.cli import main
from bids_utils.cli._common import common_options
from bids_utils.migrate import migrate_dataset


@main.command()
@click.option("--to", "to_version", default=None, help="Target BIDS version (default: current released).")
@common_options
def migrate(
    to_version: str | None,
    dry_run: bool,
    json_output: bool,
    verbose: int,
    quiet: bool,
    force: bool,
    schema_version: str | None,
) -> None:
    """Apply schema-driven migrations to resolve deprecations."""
    try:
        dataset = BIDSDataset.from_path(Path.cwd())
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if schema_version:
        dataset.schema_version = schema_version

    result = migrate_dataset(dataset, to_version=to_version, dry_run=dry_run)

    if json_output:
        output = {
            "success": result.success,
            "dry_run": result.dry_run,
            "from_version": result.from_version,
            "to_version": result.to_version,
            "findings": [
                {
                    "rule": f.rule.id,
                    "file": str(f.file),
                    "current_value": str(f.current_value),
                    "proposed_value": str(f.proposed_value),
                    "can_auto_fix": f.can_auto_fix,
                }
                for f in result.findings
            ],
            "changes": [
                {"action": c.action, "source": str(c.source), "detail": c.detail}
                for c in result.changes
            ],
            "warnings": result.warnings,
            "errors": result.errors,
        }
        click.echo(json.dumps(output, indent=2))
    else:
        prefix = "[DRY RUN] " if dry_run else ""
        if result.findings:
            click.echo(f"{prefix}Found {len(result.findings)} migration(s):")
            for f in result.findings:
                click.echo(f"  {f.file.name}: {f.rule.description}")
                click.echo(f"    {f.current_value} ��� {f.proposed_value}")
        for change in result.changes:
            click.echo(f"{prefix}{change.detail}")
        for warning in result.warnings:
            click.echo(f"Info: {warning}")
        for error in result.errors:
            click.echo(f"Error: {error}", err=True)

    if not result.success:
        sys.exit(1)
