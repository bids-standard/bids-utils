"""Per-test git-worktree fixture pattern over the local ``bids-examples`` clone.

This is the foundation for FR-042 / SC-008 / SC-009 integration coverage:
each test gets its own throwaway working copy of a ``bids-examples`` dataset
without any in-place mutation of the shared submodule clone.

Two flavours:

* :func:`bids_examples_worktree` — `git worktree add --detach` of the
  ``bids-examples`` submodule's HEAD into a unique path under ``tmp_path``.
  On teardown calls ``git worktree remove --force``.
* :func:`bids_examples_worktree_annexed` — a standalone ``shutil.copytree``
  copy with a fresh ``git init`` + ``git annex init`` + everything forced
  into annex (so data files become locked symlinks). Implemented as a
  fully separate clone (NOT a real ``git worktree``) because
  ``git annex init`` would otherwise write to the parent clone's
  ``.git/annex/`` and break the "host clone untouched" guarantee.

Per the CLAUDE.md global rule, this module MUST NOT call
``git worktree prune`` — sandboxed worktrees can appear absent from inside
the sandbox even when they exist on the host, and ``prune`` permanently
removes their registration. Stick to ``remove --force`` on paths we
ourselves created in the current test.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from tests.conftest import (
    BIDS_EXAMPLES_DIR,
    _git,
    _has_bids_examples,
    _has_git_annex,
)

__all__ = [
    "BIDS_EXAMPLES_DIR",
    "bids_examples_worktree",
    "bids_examples_worktree_annexed",
]


def _resolve_dataset(dataset_id: str) -> Path:
    """Resolve a ``bids-examples`` dataset path or ``pytest.skip``."""
    if not _has_bids_examples():
        pytest.skip(f"bids-examples submodule not available at {BIDS_EXAMPLES_DIR}")
    src = BIDS_EXAMPLES_DIR / dataset_id
    if not src.is_dir() or not (src / "dataset_description.json").is_file():
        pytest.skip(f"bids-examples dataset {dataset_id!r} not present")
    return src


def _add_worktree(tmp_path: Path, dataset_id: str) -> Path:
    """``git worktree add --detach`` HEAD of bids-examples to a unique tmp path.

    Returns the path to the dataset within the new worktree (the worktree
    itself is the bids-examples superrepo root; ``dataset_id`` selects one
    dataset subdirectory).
    """
    _resolve_dataset(dataset_id)  # skip-if-missing
    wt_root = tmp_path / f"wt-{dataset_id}-{uuid.uuid4().hex[:8]}"
    head = _git(BIDS_EXAMPLES_DIR, "rev-parse", "HEAD").stdout.strip()
    _git(BIDS_EXAMPLES_DIR, "worktree", "add", "--detach", str(wt_root), head)
    return wt_root / dataset_id


def _remove_worktree(dataset_path: Path) -> None:
    """Tear down a worktree without ``git worktree prune`` (CLAUDE.md rule)."""
    wt_root = dataset_path.parent
    if not wt_root.exists():
        return
    try:
        _git(BIDS_EXAMPLES_DIR, "worktree", "remove", "--force", str(wt_root))
    except subprocess.CalledProcessError:
        # Last-resort cleanup: rmtree the directory only. Do NOT call
        # `git worktree prune` to clean up the now-orphaned metadata —
        # CLAUDE.md forbids it. The orphan registration in the parent's
        # `.git/worktrees/` is harmless cruft until the user prunes manually.
        _safe_rmtree(wt_root)


def _safe_rmtree(path: Path) -> None:
    """``rmtree`` that survives read-only files (e.g. git-annex objects)."""
    if not path.exists():
        return
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            with contextlib.suppress(OSError):
                os.chmod(os.path.join(root, name), 0o700)
    shutil.rmtree(path, ignore_errors=True)


def _make_annexed(tmp_path: Path, dataset_id: str) -> Path:
    """Standalone-repo copy of *dataset_id* with everything forced into annex.

    Uses ``shutil.copytree`` + a fresh ``git init`` rather than
    ``git worktree add`` so that ``git annex init`` does not write to the
    parent ``bids-examples`` clone's ``.git/annex/``.
    """
    if not _has_git_annex():
        pytest.skip("git-annex not installed")
    src = _resolve_dataset(dataset_id)
    dst = tmp_path / f"wt-{dataset_id}-annexed-{uuid.uuid4().hex[:8]}"
    shutil.copytree(src, dst, symlinks=True)

    _git(dst, "init")
    _git(dst, "config", "user.email", "test@bids-utils.invalid")
    _git(dst, "config", "user.name", "bids-utils tests")
    _git(dst, "annex", "init", "test")
    _git(dst, "config", "annex.largefiles", "anything")
    _git(dst, "annex", "add", ".")
    _git(dst, "add", ".")
    _git(dst, "commit", "--allow-empty", "-m", "init annexed")
    return dst


@pytest.fixture
def bids_examples_worktree(
    tmp_path: Path,
) -> Iterator[Callable[[str], Path]]:
    """Factory fixture: ``bids_examples_worktree("ds001")`` → dataset path.

    The returned path is the BIDS dataset root inside an ephemeral
    ``git worktree`` of the ``bids-examples`` submodule. Multiple calls in
    the same test produce independent worktrees. All worktrees created
    via this fixture are torn down with ``git worktree remove --force``
    at test exit.
    """
    created: list[Path] = []

    def _factory(dataset_id: str) -> Path:
        ds_path = _add_worktree(tmp_path, dataset_id)
        created.append(ds_path)
        return ds_path

    try:
        yield _factory
    finally:
        for ds_path in created:
            _remove_worktree(ds_path)


@pytest.fixture
def bids_examples_worktree_annexed(
    tmp_path: Path,
) -> Iterator[Callable[[str], Path]]:
    """Annexed-variant factory fixture for SC-008 coverage.

    Returns a path to a standalone copy of a single ``bids-examples``
    dataset where every file (data + sidecars) has been forced into
    git-annex, producing locked symlinks in the working tree. The copy
    is fully independent of the parent ``bids-examples`` clone: it uses
    ``shutil.copytree`` + fresh ``git init`` so that ``git annex init``
    cannot write to the parent's ``.git/annex/``.

    Skips if ``git-annex`` is not installed.
    """
    created: list[Path] = []

    def _factory(dataset_id: str) -> Path:
        path = _make_annexed(tmp_path, dataset_id)
        created.append(path)
        return path

    try:
        yield _factory
    finally:
        for path in created:
            _safe_rmtree(path)
