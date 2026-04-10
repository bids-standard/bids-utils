"""Read/write/update participants.tsv."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from bids_utils._tsv import read_tsv, write_tsv

if TYPE_CHECKING:
    from bids_utils._types import AnnexedMode
    from bids_utils._vcs import VCSBackend


def read_participants_tsv(
    path: Path,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode | None = None,
) -> list[dict[str, str]]:
    """Read participants.tsv into a list of row dicts."""
    return read_tsv(path, vcs=vcs, annexed_mode=annexed_mode)


def write_participants_tsv(
    path: Path,
    rows: list[dict[str, str]],
    vcs: VCSBackend | None = None,
) -> None:
    """Write rows to participants.tsv."""
    write_tsv(path, rows, vcs=vcs)


def rename_participant(
    participants_path: Path,
    old_id: str,
    new_id: str,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode | None = None,
) -> bool:
    """Rename a participant in participants.tsv.

    Parameters
    ----------
    old_id, new_id
        Full participant IDs including "sub-" prefix.

    Returns True if found and renamed.
    """
    rows = read_participants_tsv(
        participants_path, vcs=vcs, annexed_mode=annexed_mode
    )
    updated = False
    for row in rows:
        if row.get("participant_id") == old_id:
            row["participant_id"] = new_id
            updated = True
    if updated:
        write_participants_tsv(participants_path, rows, vcs=vcs)
    return updated


def remove_participant(
    participants_path: Path,
    participant_id: str,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode | None = None,
) -> bool:
    """Remove a participant from participants.tsv.

    Returns True if found and removed.
    """
    rows = read_participants_tsv(
        participants_path, vcs=vcs, annexed_mode=annexed_mode
    )
    new_rows = [r for r in rows if r.get("participant_id") != participant_id]
    if len(new_rows) < len(rows):
        write_participants_tsv(participants_path, new_rows, vcs=vcs)
        return True
    return False


def add_participant(
    participants_path: Path,
    participant_id: str,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode | None = None,
    **fields: str,
) -> bool:
    """Add a participant to participants.tsv.

    Returns False if the participant already exists.
    """
    rows = read_participants_tsv(
        participants_path, vcs=vcs, annexed_mode=annexed_mode
    )
    for row in rows:
        if row.get("participant_id") == participant_id:
            return False

    new_row = {"participant_id": participant_id, **fields}
    # Ensure all fieldnames are present
    if rows:
        for key in rows[0]:
            new_row.setdefault(key, "n/a")
    rows.append(new_row)
    write_participants_tsv(participants_path, rows, vcs=vcs)
    return True
