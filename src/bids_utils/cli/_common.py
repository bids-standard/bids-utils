"""Shared CLI decorators, options, and helpers."""

from __future__ import annotations

import functools
import json
import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
from click.shell_completion import CompletionItem

from bids_utils._dataset import BIDSDataset
from bids_utils._types import AnnexedMode, OperationResult


def common_options(f: Callable[..., Any]) -> Callable[..., Any]:
    """Add common CLI options: --dry-run, --json, -v/-q, --force, --schema-version."""

    @click.option(
        "--dry-run",
        "-n",
        is_flag=False,
        flag_value="overview",
        default=None,
        type=click.Choice(["overview", "detailed"]),
        help=(
            "Show what would change without modifying files. "
            "Use --dry-run=detailed for per-file listing."
        ),
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
        # Configure logging from -v / -q
        # Default: INFO (shows annex get operations)
        # -v: DEBUG (shows unlock/add details)
        # -q: WARNING (suppresses info messages)
        verbose = kwargs.get("verbose", 0)
        quiet = kwargs.get("quiet", False)
        if quiet:
            level = logging.WARNING
        elif verbose:
            level = logging.DEBUG
        else:
            level = logging.INFO
        logging.basicConfig(
            level=level,
            format="%(message)s",
            force=True,
        )
        return f(**kwargs)

    return wrapper


def load_dataset(path: Path | None = None) -> BIDSDataset:
    """Load a BIDSDataset, exiting on error.

    Reads the ``--annexed`` mode from the Click context (set by the
    group-level option) and applies it to the dataset.

    Parameters
    ----------
    path
        Path to (or inside) the dataset.  Defaults to ``Path.cwd()``.
    """
    try:
        ds = BIDSDataset.from_path(path or Path.cwd())
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Apply --annexed mode from CLI group context
    ctx = click.get_current_context(silent=True)
    if ctx is not None and ctx.obj and "annexed" in ctx.obj:
        ds.annexed_mode = AnnexedMode(ctx.obj["annexed"])

    return ds


def output_result(
    result: OperationResult,
    json_output: bool,
    dry_run: str | None,
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
        ``"overview"`` for summary, ``"detailed"`` for per-file listing,
        or ``None`` / falsy when not in dry-run mode.
    exit_code
        Exit code to use when ``result.success`` is ``False``.
    """
    if json_output:
        click.echo(json.dumps(result.to_dict(), indent=2))
    else:
        prefix = "[DRY RUN] " if dry_run else ""
        detailed = dry_run == "detailed"

        for change in result.changes:
            if detailed:
                # Per-file: show action, source → target
                src = change.source
                tgt = f" → {change.target}" if change.target else ""
                click.echo(f"{prefix}{change.action}: {src}{tgt}")
            else:
                # Overview: skip indented detail lines (per-file items)
                if change.detail.startswith("  "):
                    continue
                click.echo(f"{prefix}{change.detail}")
        for w in result.warnings:
            click.echo(f"Warning: {w}", err=True)
        for err in result.errors:
            click.echo(f"Error: {err}", err=True)

    if not result.success:
        sys.exit(exit_code)


# ---------------------------------------------------------------------------
# BIDS-aware shell completion helpers (FR-019, FR-020, FR-021)
# ---------------------------------------------------------------------------


def _find_dataset_root() -> Path | None:
    """Walk up from CWD to find dataset_description.json.

    Returns the dataset root or ``None`` if not found.  This is a lightweight
    helper for completion callbacks — it must not raise.
    """
    try:
        ds = BIDSDataset.from_path(Path.cwd())
        return ds.root
    except (FileNotFoundError, ValueError, OSError):
        return None


class SubjectCompletion(click.ParamType):
    """Click type that provides ``sub-*`` directory completions."""

    name = "subject"

    def shell_complete(
        self, ctx: click.Context, param: click.Parameter, incomplete: str
    ) -> list[CompletionItem]:
        root = _find_dataset_root()
        if root is None:
            return []
        items: list[CompletionItem] = []
        for entry in sorted(root.iterdir()):
            if entry.is_dir() and entry.name.startswith("sub-"):
                label = entry.name
                if label.startswith(incomplete):
                    items.append(CompletionItem(label))
        return items


class SessionCompletion(click.ParamType):
    """Click type that provides ``ses-*`` directory completions."""

    name = "session"

    def shell_complete(
        self, ctx: click.Context, param: click.Parameter, incomplete: str
    ) -> list[CompletionItem]:
        root = _find_dataset_root()
        if root is None:
            return []
        # Collect sessions from all subject directories
        sessions: set[str] = set()
        for sub_dir in root.iterdir():
            if sub_dir.is_dir() and sub_dir.name.startswith("sub-"):
                for entry in sub_dir.iterdir():
                    if entry.is_dir() and entry.name.startswith("ses-"):
                        sessions.add(entry.name)
        items: list[CompletionItem] = []
        for ses in sorted(sessions):
            if ses.startswith(incomplete):
                items.append(CompletionItem(ses))
        return items


class EntityKeyCompletion(click.ParamType):
    """Click type that provides ``key=`` entity completions from the schema."""

    name = "entity"

    def shell_complete(
        self, ctx: click.Context, param: click.Parameter, incomplete: str
    ) -> list[CompletionItem]:
        try:
            from bids_utils._schema import BIDSSchema

            schema = BIDSSchema.load()
            keys = schema.entity_order()
        except Exception:
            keys = []
        items: list[CompletionItem] = []
        for key in keys:
            candidate = f"{key}="
            if candidate.startswith(incomplete):
                items.append(CompletionItem(candidate))
        return items


class BIDSFileCompletion(click.ParamType):
    """Click type that provides BIDS file path completions under the dataset."""

    name = "bids_file"

    def shell_complete(
        self, ctx: click.Context, param: click.Parameter, incomplete: str
    ) -> list[CompletionItem]:
        root = _find_dataset_root()
        if root is None:
            return []

        # Resolve the incomplete path relative to CWD
        cwd = Path.cwd()
        if incomplete:
            search_dir = cwd / incomplete
            if not search_dir.is_dir():
                search_dir = search_dir.parent
                prefix = os.path.dirname(incomplete)
            else:
                prefix = incomplete.rstrip("/")
        else:
            search_dir = cwd
            prefix = ""

        if not search_dir.is_dir():
            return []

        items: list[CompletionItem] = []
        basename = os.path.basename(incomplete) if incomplete else ""
        for entry in sorted(search_dir.iterdir()):
            if not entry.name.startswith(basename):
                continue
            if entry.name.startswith("."):
                continue
            rel = os.path.join(prefix, entry.name) if prefix else entry.name
            item_type = "dir" if entry.is_dir() else "file"
            items.append(
                CompletionItem(rel, type=item_type)
            )
        return items


# Singleton instances for use in CLI commands
SUBJECT_TYPE = SubjectCompletion()
SESSION_TYPE = SessionCompletion()
ENTITY_TYPE = EntityKeyCompletion()
BIDS_FILE_TYPE = BIDSFileCompletion()
