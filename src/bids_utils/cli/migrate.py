"""CLI command: bids-utils migrate."""

from __future__ import annotations

import json
import sys

import click

from bids_utils.cli import main
from bids_utils.cli._common import common_options, load_dataset
from bids_utils.migrate import migrate_dataset


@main.command()
@click.option(
    "--to",
    "to_version",
    default=None,
    help="Target BIDS version (default: current released).",
)
@click.option(
    "--level",
    type=click.Choice(["safe", "advisory", "all"]),
    default="safe",
    help="Migration rule tier to include (default: safe).",
)
@click.option(
    "--mode",
    type=click.Choice(["auto", "non-interactive", "interactive"]),
    default="auto",
    help="Interaction mode (default: auto).",
)
@click.option(
    "--rule-id",
    "rule_ids",
    multiple=True,
    type=str,
    help="Only run specific rule(s) by id (repeatable).",
)
@click.option(
    "--exclude-rule",
    "exclude_rules",
    multiple=True,
    type=str,
    help="Exclude specific rule(s) by id (repeatable).",
)
@common_options
def migrate(
    to_version: str | None,
    level: str,
    mode: str,
    rule_ids: tuple[str, ...],
    exclude_rules: tuple[str, ...],
    dry_run: str | None,
    json_output: bool,
    verbose: int,
    quiet: bool,
    force: bool,
    schema_version: str | None,
) -> None:
    """Apply schema-driven migrations to resolve deprecations."""
    dataset = load_dataset()

    if schema_version:
        dataset.schema_version = schema_version

    result = migrate_dataset(
        dataset,
        to_version=to_version,
        dry_run=bool(dry_run),
        level=level,
        mode=mode,
        rule_ids=list(rule_ids) or None,
        exclude_rules=list(exclude_rules) or None,
    )

    if json_output:
        output: dict[str, object] = {
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
        }
        output["warnings"] = result.warnings
        output["errors"] = result.errors
        click.echo(json.dumps(output, indent=2))
    else:
        prefix = "[DRY RUN] " if dry_run else ""
        if result.findings:
            click.echo(f"{prefix}Found {len(result.findings)} migration(s):")
            for f in result.findings:
                click.echo(f"  {f.file.name}: {f.rule.description}")
                click.echo(f"    {f.current_value} \u2192 {f.proposed_value}")
        for change in result.changes:
            click.echo(f"{prefix}{change.detail}")
        for warning in result.warnings:
            click.echo(f"Info: {warning}")
        for error in result.errors:
            click.echo(f"Error: {error}", err=True)

    if not result.success:
        sys.exit(1)
