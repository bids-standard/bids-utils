"""Read/write/update participants.tsv."""

from __future__ import annotations

from pathlib import Path

from bids_utils._tsv import read_tsv, write_tsv


def read_participants_tsv(path: Path) -> list[dict[str, str]]:
    """Read participants.tsv into a list of row dicts."""
    return read_tsv(path)


def write_participants_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write rows to participants.tsv."""
    write_tsv(path, rows)


def rename_participant(
    participants_path: Path,
    old_id: str,
    new_id: str,
) -> bool:
    """Rename a participant in participants.tsv.

    Parameters
    ----------
    old_id, new_id
        Full participant IDs including "sub-" prefix.

    Returns True if found and renamed.
    """
    rows = read_participants_tsv(participants_path)
    updated = False
    for row in rows:
        if row.get("participant_id") == old_id:
            row["participant_id"] = new_id
            updated = True
    if updated:
        write_participants_tsv(participants_path, rows)
    return updated


def remove_participant(participants_path: Path, participant_id: str) -> bool:
    """Remove a participant from participants.tsv.

    Returns True if found and removed.
    """
    rows = read_participants_tsv(participants_path)
    new_rows = [r for r in rows if r.get("participant_id") != participant_id]
    if len(new_rows) < len(rows):
        write_participants_tsv(participants_path, new_rows)
        return True
    return False


def add_participant(
    participants_path: Path,
    participant_id: str,
    **fields: str,
) -> bool:
    """Add a participant to participants.tsv.

    Returns False if the participant already exists.
    """
    rows = read_participants_tsv(participants_path)
    for row in rows:
        if row.get("participant_id") == participant_id:
            return False

    new_row = {"participant_id": participant_id, **fields}
    # Ensure all fieldnames are present
    if rows:
        for key in rows[0]:
            new_row.setdefault(key, "n/a")
    rows.append(new_row)
    write_participants_tsv(participants_path, rows)
    return True
