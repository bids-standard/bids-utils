"""Shared CLI decorators and options."""

from __future__ import annotations

import functools
from typing import Any, Callable

import click


def common_options(f: Callable[..., Any]) -> Callable[..., Any]:
    """Add common CLI options: --dry-run, --json, -v/-q, --force, --schema-version."""

    @click.option("--dry-run", "-n", is_flag=True, help="Show what would change without modifying files.")
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
