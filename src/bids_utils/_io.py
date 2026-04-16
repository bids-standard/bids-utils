"""Content-aware file I/O for git-annex/DataLad datasets (FR-022).

All file reads and writes to potentially-annexed files should go through
these helpers so that the ``--annexed`` policy is enforced consistently.
"""

from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bids_utils._types import AnnexedMode, ContentNotAvailableError, is_bids_dir_file

if TYPE_CHECKING:
    from bids_utils._vcs import VCSBackend

logger = logging.getLogger(__name__)


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
        logger.info("Fetching annexed content: %s", path)
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
        logger.debug("Unlocking annexed file: %s", path)
        vcs.unlock([path])


def mark_modified(paths: list[Path], vcs: VCSBackend) -> None:
    """Re-annex files after modification (``git annex add``).

    Always applied for git-annex/DataLad backends to restore the file
    to its tracked state.  For NoVCS/Git backends this is a no-op
    (Git.add stages the file, NoVCS does nothing).
    """
    if paths:
        logger.debug("Re-adding modified files: %s", [str(p) for p in paths])
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


# JSON metadata fields that contain path references to other BIDS files.
_REFERENCE_FIELDS = ("IntendedFor", "AssociatedEmptyRoom", "Sources")


def _replace_in_value(
    value: str | list[str],
    old_label: str,
    new_label: str,
) -> tuple[str | list[str], bool]:
    """Replace *old_label* with *new_label* inside a string or list of strings.

    Returns ``(new_value, changed)``.
    """
    if isinstance(value, str):
        if old_label in value:
            return value.replace(old_label, new_label), True
        return value, False
    if isinstance(value, list):
        new_list: list[str] = []
        changed = False
        for item in value:
            if isinstance(item, str) and old_label in item:
                new_list.append(item.replace(old_label, new_label))
                changed = True
            else:
                new_list.append(item)
        return new_list, changed
    return value, False


def update_json_references(
    dataset_root: Path,
    old_label: str,
    new_label: str,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> list[Path]:
    """Update path references in JSON sidecars across the dataset.

    Scans all ``*.json`` files under *dataset_root* for fields like
    ``IntendedFor``, ``AssociatedEmptyRoom``, and ``Sources`` that
    contain *old_label* and replaces it with *new_label*.

    Returns a list of modified files.
    """
    modified_files: list[Path] = []
    for json_path in sorted(dataset_root.rglob("*.json")):
        # Skip dotdirs — .git, .datalad, .heudiconv, etc. are never BIDS data
        rel = json_path.relative_to(dataset_root)
        if rel.parts and rel.parts[0].startswith("."):
            continue
        # Skip files inside directory-based files
        if any(
            is_bids_dir_file(p)
            for p in json_path.parents
            if p != dataset_root
        ):
            continue

        data = read_json(json_path, vcs=vcs, mode=annexed_mode)
        if data is None:
            continue

        file_modified = False
        for field in _REFERENCE_FIELDS:
            if field not in data:
                continue
            new_val, changed = _replace_in_value(
                data[field], old_label, new_label
            )
            if changed:
                data[field] = new_val
                file_modified = True

        if file_modified:
            if vcs is not None:
                write_json(json_path, data, vcs)
            else:
                json_path.write_text(
                    json.dumps(data, indent=2) + "\n", encoding="utf-8"
                )
            modified_files.append(json_path)

    return modified_files
