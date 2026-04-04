"""Shared CLI decorators, options, and helpers."""

from __future__ import annotations

import functools
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

from bids_utils._dataset import BIDSDataset
from bids_utils._types import OperationResult


def common_options(f: Callable[..., Any]) -> Callable[..., Any]:
    """Add common CLI options: --dry-run, --json, -v/-q, --force, --schema-version."""

    @click.option(
        "--dry-run",
        "-n",
        is_flag=True,
        help="Show what would change without modifying files.",
    )
    @click.option("--json", "json_output", is_flag=True, help="Output results as JSON.")
    @click.option("-v", "--verbose", count=True, help="Increase verbosity.")
    @click.option("-q", "--quiet", is_flag=True, help="Suppress non-essential output.")
    @click.option("--force", is_flag=True, help="Skip confirmation prompts.")
    @click.option(
        "--schema-version",
        default=None,
        help="Override detected BIDS schema version.",
    )
    @functools.wraps(f)
    def wrapper(**kwargs: Any) -> Any:
        return f(**kwargs)

    return wrapper


def load_dataset(path: Path | None = None) -> BIDSDataset:
    """Load a BIDSDataset, exiting on error.

    Parameters
    ----------
    path
        Path to (or inside) the dataset.  Defaults to ``Path.cwd()``.
    """
    try:
        return BIDSDataset.from_path(path or Path.cwd())
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def output_result(
    result: OperationResult,
    json_output: bool,
    dry_run: bool,
    *,
    exit_code: int = 2,
) -> None:
    """Print an OperationResult as JSON or human-readable text, then exit on failure.

    Parameters
    ----------
    result
        The operation result to display.
    json_output
        If ``True``, emit a JSON document.
    dry_run
        Used for the ``[DRY RUN]`` prefix in text mode.
    exit_code
        Exit code to use when ``result.success`` is ``False``.
    """
    if json_output:
        click.echo(json.dumps(result.to_dict(), indent=2))
    else:
        prefix = "[DRY RUN] " if dry_run else ""
        for change in result.changes:
            click.echo(f"{prefix}{change.detail}")
        for w in result.warnings:
            click.echo(f"Warning: {w}", err=True)
        for err in result.errors:
            click.echo(f"Error: {err}", err=True)

    if not result.success:
        sys.exit(exit_code)
