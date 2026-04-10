"""Subject rename and remove operations (User Stories 4, 7)."""

from __future__ import annotations

from pathlib import Path

from bids_utils._dataset import BIDSDataset
from bids_utils._participants import remove_participant, rename_participant
from bids_utils._scans import read_scans_tsv, write_scans_tsv
from bids_utils._types import (
    Change,
    OperationResult,
    normalize_subject_id,
    rename_change,
    require_subject_dir,
)


def rename_subject(
    dataset: BIDSDataset,
    old: str,
    new: str,
    *,
    dry_run: bool = False,
    include_sourcedata: bool = False,
) -> OperationResult:
    """Rename a subject across the entire dataset.

    Parameters
    ----------
    old, new
        Subject labels WITHOUT "sub-" prefix (e.g., "01", "99").
    """
    result = OperationResult(dry_run=dry_run)
    old_id = normalize_subject_id(old)
    new_id = normalize_subject_id(new)

    old_dir = require_subject_dir(dataset.root, old_id, result)
    if old_dir is None:
        return result
    new_dir = dataset.root / new_id

    if new_dir.exists():
        result.success = False
        result.errors.append(f"Target subject already exists: {new_dir}")
        return result

    # Collect all files that need renaming
    files_to_rename: list[Path] = []
    for f in sorted(old_dir.rglob("*")):
        if f.is_file() and old_id in f.name:
            files_to_rename.append(f)

    # Record directory rename
    result.changes.append(
        rename_change(old_dir, new_dir, f"Rename directory {old_id} \u2192 {new_id}")
    )

    # Record file renames
    for f in files_to_rename:
        new_name = f.name.replace(old_id, new_id)
        # Compute target path (under new_dir)
        rel = f.relative_to(old_dir)
        new_path = new_dir / rel.parent / new_name
        result.changes.append(
            rename_change(f, new_path, f"Rename {f.name} \u2192 {new_name}")
        )

    # participants.tsv update
    participants = dataset.root / "participants.tsv"
    if participants.is_file():
        result.changes.append(
            Change(
                action="modify",
                source=participants,
                detail=f"Update participants.tsv: {old_id} → {new_id}",
            )
        )

    # scans.tsv updates
    for scans_file in old_dir.rglob("*_scans.tsv"):
        new_scans_name = scans_file.name.replace(old_id, new_id)
        result.changes.append(
            Change(
                action="modify",
                source=scans_file,
                detail=f"Update scans.tsv entries and rename to {new_scans_name}",
            )
        )

    if dry_run:
        return result

    # Execute: rename the directory first
    vcs = dataset.vcs
    vcs.move(old_dir, new_dir)

    # Rename files within the new directory
    for f in sorted(new_dir.rglob("*"), reverse=True):
        if f.is_file() and old_id in f.name:
            new_name = f.name.replace(old_id, new_id)
            new_path = f.parent / new_name
            if f != new_path:
                vcs.move(f, new_path)

    # Update scans.tsv files (they're now under new_dir)
    amode = dataset.annexed_mode
    for scans_file in sorted(new_dir.rglob("*_scans.tsv")):
        rows = read_scans_tsv(scans_file, vcs=vcs, annexed_mode=amode)
        modified = False
        for row in rows:
            fn = row.get("filename", "")
            if old_id in fn:
                row["filename"] = fn.replace(old_id, new_id)
                modified = True
        if modified:
            write_scans_tsv(scans_file, rows, vcs=vcs)

    # Update participants.tsv
    if participants.is_file():
        rename_participant(
            participants, old_id, new_id, vcs=vcs, annexed_mode=amode
        )

    # Handle sourcedata if requested
    if include_sourcedata:
        for extra_dir_name in ["sourcedata", ".heudiconv"]:
            extra = dataset.root / extra_dir_name / old_id
            new_extra = dataset.root / extra_dir_name / new_id
            if extra.is_dir() and not new_extra.exists():
                vcs.move(extra, new_extra)

    return result


def remove_subject(
    dataset: BIDSDataset,
    subject: str,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> OperationResult:
    """Remove a subject from the dataset."""
    result = OperationResult(dry_run=dry_run)
    sub_id = normalize_subject_id(subject)

    sub_dir = require_subject_dir(dataset.root, sub_id, result)
    if sub_dir is None:
        return result

    result.changes.append(
        Change(action="delete", source=sub_dir, detail=f"Remove {sub_id} directory")
    )

    participants = dataset.root / "participants.tsv"
    if participants.is_file():
        result.changes.append(
            Change(
                action="modify",
                source=participants,
                detail=f"Remove {sub_id} from participants.tsv",
            )
        )

    if dry_run:
        return result

    vcs = dataset.vcs
    vcs.remove(sub_dir)

    if participants.is_file():
        remove_participant(
            participants, sub_id, vcs=vcs, annexed_mode=dataset.annexed_mode
        )

    return result
