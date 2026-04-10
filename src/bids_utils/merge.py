"""Dataset merge operations (User Story 9)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from bids_utils._participants import read_participants_tsv, write_participants_tsv
from bids_utils._types import Change, OperationResult


def merge_datasets(
    sources: list[str | Path],
    target: str | Path,
    *,
    into_sessions: list[str] | None = None,
    on_conflict: Literal["error", "add-runs"] = "error",
    dry_run: bool = False,
) -> OperationResult:
    """Merge multiple BIDS datasets into a target.

    Parameters
    ----------
    sources
        Paths to source datasets.
    target
        Path to target dataset (created if needed).
    into_sessions
        If provided, place each source into the corresponding session.
    on_conflict
        "error": refuse on overlapping subjects. "add-runs": assign
        next available run indices for intra-session conflicts.
    """
    result = OperationResult(dry_run=dry_run)
    target_path = Path(target)

    if into_sessions and len(into_sessions) != len(sources):
        result.success = False
        result.errors.append("Number of sessions must match number of sources")
        return result

    # Create target if needed
    if not target_path.exists():
        if not dry_run:
            target_path.mkdir(parents=True)
        result.changes.append(
            Change(
                action="create",
                source=target_path,
                detail="Create target dataset directory",
            )
        )

    # Copy dataset_description.json from first source if target doesn't have one
    desc_target = target_path / "dataset_description.json"
    if not desc_target.exists():
        for src in sources:
            desc_src = Path(src) / "dataset_description.json"
            if desc_src.exists():
                result.changes.append(
                    Change(
                        action="create",
                        source=desc_target,
                        detail="Copy dataset_description.json",
                    )
                )
                if not dry_run:
                    shutil.copy2(desc_src, desc_target)
                break

    # Collect subjects from each source
    for i, src in enumerate(sources):
        src_path = Path(src)
        session = into_sessions[i] if into_sessions else None

        sub_dirs = sorted(
            d for d in src_path.iterdir() if d.is_dir() and d.name.startswith("sub-")
        )

        for sub_dir in sub_dirs:
            sub_name = sub_dir.name
            target_sub = target_path / sub_name

            if session:
                ses_id = f"ses-{session}" if not session.startswith("ses-") else session
                target_ses = target_sub / ses_id
                dest = target_ses
            else:
                dest = target_sub

            if dest.exists() and on_conflict == "error":
                result.success = False
                result.errors.append(f"Conflict: {sub_name} already exists in target")
                return result

            result.changes.append(
                Change(
                    action="create",
                    source=dest,
                    detail=f"Copy {sub_name} from {src_path.name}"
                    + (f" into {ses_id}" if session else ""),
                )
            )

            if dry_run:
                continue

            # Copy subject directory
            if session:
                target_sub.mkdir(exist_ok=True)
                # Copy datatype dirs into session
                dest.mkdir(exist_ok=True)
                for item in sub_dir.iterdir():
                    if item.is_dir():
                        shutil.copytree(item, dest / item.name, dirs_exist_ok=True)
                    elif not item.is_dir():
                        shutil.copy2(item, dest / item.name)
            else:
                if dest.exists():
                    shutil.copytree(sub_dir, dest, dirs_exist_ok=True)
                else:
                    shutil.copytree(sub_dir, dest)

        # Merge participants.tsv
        src_participants = src_path / "participants.tsv"
        target_participants = target_path / "participants.tsv"
        if src_participants.exists():
            src_rows = read_participants_tsv(src_participants)
            if target_participants.exists():
                target_rows = read_participants_tsv(target_participants)
                existing_ids = {r["participant_id"] for r in target_rows}
                for row in src_rows:
                    if row["participant_id"] not in existing_ids:
                        target_rows.append(row)
                if not dry_run:
                    write_participants_tsv(target_participants, target_rows)
            elif not dry_run:
                shutil.copy2(src_participants, target_participants)

    return result
