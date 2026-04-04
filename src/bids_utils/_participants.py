"""Read/write/update participants.tsv."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path


def read_participants_tsv(path: Path) -> list[dict[str, str]]:
    """Read participants.tsv into a list of row dicts."""
    text = path.read_text(encoding="utf-8")
    reader = csv.DictReader(StringIO(text), delimiter="\t")
    return list(reader)


def write_participants_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write rows to participants.tsv."""
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


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
