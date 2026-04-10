"""CLI commands: bids-utils subject-rename, bids-utils remove."""

from __future__ import annotations

import click

from bids_utils.cli import main
from bids_utils.cli._common import (
    SUBJECT_TYPE,
    common_options,
    load_dataset,
    output_result,
)
from bids_utils.subject import remove_subject, rename_subject


@main.command("subject-rename")
@click.argument("old", type=SUBJECT_TYPE)
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
    dataset = load_dataset()

    result = rename_subject(
        dataset, old, new, dry_run=dry_run, include_sourcedata=include_sourcedata
    )
    output_result(result, json_output, dry_run)


@main.command("remove")
@click.argument("subject", type=SUBJECT_TYPE)
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
    if not force and not dry_run:
        click.confirm(
            f"Remove {subject} and all its data? This cannot be undone",
            abort=True,
        )

    dataset = load_dataset()

    result = remove_subject(dataset, subject, dry_run=dry_run, force=force)
    output_result(result, json_output, dry_run)
