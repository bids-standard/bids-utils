"""Read/write/update _scans.tsv files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from bids_utils._tsv import read_tsv, write_tsv

if TYPE_CHECKING:
    from bids_utils._types import AnnexedMode
    from bids_utils._vcs import VCSBackend


def read_scans_tsv(
    path: Path,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode | None = None,
) -> list[dict[str, str]]:
    """Read a _scans.tsv file into a list of row dicts."""
    return read_tsv(path, vcs=vcs, annexed_mode=annexed_mode)


def write_scans_tsv(
    path: Path,
    rows: list[dict[str, str]],
    vcs: VCSBackend | None = None,
) -> None:
    """Write rows back to a _scans.tsv file."""
    write_tsv(path, rows, vcs=vcs)


def find_scans_tsv(file_path: Path, dataset_root: Path) -> Path | None:
    """Find the _scans.tsv that should contain an entry for *file_path*.

    Scans files live at the subject or session level:
      sub-01/sub-01_scans.tsv
      sub-01/ses-pre/sub-01_ses-pre_scans.tsv
    """
    # Walk from the file's directory upward looking for _scans.tsv
    search_dir = file_path.parent
    while search_dir != dataset_root.parent:
        for f in search_dir.iterdir():
            if f.name.endswith("_scans.tsv") and f.is_file():
                return f
        # Stop at dataset root
        if search_dir == dataset_root:
            break
        search_dir = search_dir.parent

    return None


def update_scans_entry(
    scans_path: Path,
    old_filename: str,
    new_filename: str,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode | None = None,
) -> bool:
    """Update a filename reference in a _scans.tsv file.

    Returns True if an entry was updated, False if not found.
    """
    rows = read_scans_tsv(scans_path, vcs=vcs, annexed_mode=annexed_mode)
    updated = False
    for row in rows:
        if row.get("filename") == old_filename:
            row["filename"] = new_filename
            updated = True
    if updated:
        write_scans_tsv(scans_path, rows, vcs=vcs)
    return updated


def remove_scans_entry(
    scans_path: Path,
    filename: str,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode | None = None,
) -> bool:
    """Remove a filename entry from a _scans.tsv file.

    Returns True if an entry was removed, False if not found.
    """
    rows = read_scans_tsv(scans_path, vcs=vcs, annexed_mode=annexed_mode)
    new_rows = [r for r in rows if r.get("filename") != filename]
    if len(new_rows) < len(rows):
        write_scans_tsv(scans_path, new_rows, vcs=vcs)
        return True
    return False
