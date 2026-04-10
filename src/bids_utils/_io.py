"""Content-aware file I/O for git-annex/DataLad datasets (FR-022).

All file reads and writes to potentially-annexed files should go through
these helpers so that the ``--annexed`` policy is enforced consistently.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bids_utils._types import AnnexedMode, ContentNotAvailableError

if TYPE_CHECKING:
    from bids_utils._vcs import VCSBackend


def ensure_content(
    path: Path,
    vcs: VCSBackend,
    mode: AnnexedMode,
) -> None:
    """Ensure file content is available for reading.

    Parameters
    ----------
    path
        File to check.
    vcs
        VCS backend (provides ``has_content`` / ``get_content``).
    mode
        The ``--annexed`` policy in effect.

    Raises
    ------
    ContentNotAvailableError
        When content is missing and *mode* is not ``GET``.
    """
    if vcs.has_content(path):
        return

    if mode is AnnexedMode.GET:
        vcs.get_content([path])
        return

    hint = (
        f"Run 'git annex get {path.name}' or use "
        "'bids-utils --annexed=get' to auto-fetch."
    )

    if mode is AnnexedMode.SKIP_WARNING:
        warnings.warn(
            f"Skipping annexed file without content: {path}",
            stacklevel=2,
        )
        raise ContentNotAvailableError(path, hint=hint)

    if mode is AnnexedMode.SKIP:
        raise ContentNotAvailableError(path, hint=hint)

    # AnnexedMode.ERROR (default)
    raise ContentNotAvailableError(path, hint=hint)


def ensure_writable(path: Path, vcs: VCSBackend) -> None:
    """Unlock an annexed file so it can be modified.

    This is always applied for git-annex/DataLad backends when the file
    is a locked symlink, regardless of the ``--annexed`` mode.  For
    NoVCS/Git backends this is a no-op.
    """
    if path.is_symlink() and path.exists():
        # Locked annexed file with content present — unlock it
        vcs.unlock([path])


def mark_modified(paths: list[Path], vcs: VCSBackend) -> None:
    """Re-annex files after modification (``git annex add``).

    Always applied for git-annex/DataLad backends to restore the file
    to its tracked state.  For NoVCS/Git backends this is a no-op
    (Git.add stages the file, NoVCS does nothing).
    """
    if paths:
        vcs.add(paths)


def read_json(
    path: Path,
    vcs: VCSBackend | None,
    mode: AnnexedMode = AnnexedMode.ERROR,
) -> dict[str, Any] | None:
    """Read a JSON sidecar with content-awareness.

    When *vcs* is ``None`` the content check is skipped (plain read).

    Returns
    -------
    dict or None
        Parsed JSON dict, or ``None`` if the file was skipped
        (skip/skip-warning modes) or is unreadable.
    """
    if vcs is not None:
        try:
            ensure_content(path, vcs, mode)
        except ContentNotAvailableError:
            return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    return data if isinstance(data, dict) else None


def write_json(
    path: Path,
    data: dict[str, Any],
    vcs: VCSBackend,
) -> None:
    """Write JSON with unlock-before / add-after lifecycle."""
    ensure_writable(path, vcs)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    mark_modified([path], vcs)
