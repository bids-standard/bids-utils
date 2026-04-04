"""CLI command: bids-utils rename."""

from __future__ import annotations

from pathlib import Path

import click

from bids_utils.cli import main
from bids_utils.cli._common import common_options, load_dataset, output_result
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

    dataset = load_dataset(file_path)

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

    output_result(result, json_output, dry_run, exit_code=2 if result.errors else 1)
