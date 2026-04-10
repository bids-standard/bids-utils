"""CLI command: bids-utils session-rename."""

from __future__ import annotations

import click

from bids_utils.cli import main
from bids_utils.cli._common import (
    SESSION_TYPE,
    common_options,
    load_dataset,
    output_result,
)
from bids_utils.session import rename_session


@main.command("session-rename")
@click.argument("old", type=SESSION_TYPE)
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
    dataset = load_dataset()

    result = rename_session(dataset, old, new, subject=subject, dry_run=dry_run)

    output_result(result, json_output, dry_run)
