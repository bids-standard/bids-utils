"""Run removal with reindexing (User Story 8)."""

from __future__ import annotations

import re
from pathlib import Path

from bids_utils._dataset import BIDSDataset
from bids_utils._scans import find_scans_tsv, remove_scans_entry, update_scans_entry
from bids_utils._sidecars import find_sidecars
from bids_utils._types import Change, OperationResult


def remove_run(
    dataset: BIDSDataset,
    subject: str,
    run: str,
    *,
    shift: bool = True,
    dry_run: bool = False,
) -> OperationResult:
    """Remove a run and optionally reindex subsequent runs.

    Parameters
    ----------
    subject
        Subject label (e.g., "sub-01" or "01").
    run
        Run label to remove (e.g., "run-02" or "02").
    shift
        If True, renumber subsequent runs to fill the gap.
    """
    result = OperationResult(dry_run=dry_run)

    sub_id = f"sub-{subject}" if not subject.startswith("sub-") else subject
    run_id = f"run-{run}" if not run.startswith("run-") else run
    run_num = int(run_id.removeprefix("run-"))

    sub_dir = dataset.root / sub_id
    if not sub_dir.is_dir():
        result.success = False
        result.errors.append(f"Subject directory not found: {sub_dir}")
        return result

    # Find all files matching this run
    run_files: list[Path] = []
    for f in sorted(sub_dir.rglob("*")):
        if f.is_file() and run_id in f.name:
            run_files.append(f)

    if not run_files:
        result.success = False
        result.errors.append(f"No files found for {run_id} in {sub_id}")
        return result

    # Record deletions
    for f in run_files:
        result.changes.append(
            Change(action="delete", source=f, detail=f"Remove {f.name}")
        )

    # Find subsequent runs to shift
    shifts: list[tuple[Path, Path]] = []
    if shift:
        for f in sorted(sub_dir.rglob("*")):
            if not f.is_file():
                continue
            m = re.search(r"run-(\d+)", f.name)
            if not m:
                continue
            file_run = int(m.group(1))
            if file_run > run_num:
                new_run = f"run-{file_run - 1:02d}"
                old_run = f"run-{file_run:02d}"
                new_name = f.name.replace(old_run, new_run)
                new_path = f.parent / new_name
                shifts.append((f, new_path))
                result.changes.append(
                    Change(
                        action="rename",
                        source=f,
                        target=new_path,
                        detail=f"Shift {f.name} → {new_name}",
                    )
                )

    if dry_run:
        return result

    vcs = dataset.vcs

    # Delete the target run files
    for f in run_files:
        # Update scans.tsv
        scans = find_scans_tsv(f, dataset.root)
        if scans:
            scans_dir = scans.parent
            try:
                rel = str(f.relative_to(scans_dir))
                remove_scans_entry(scans, rel)
            except ValueError:
                pass
        vcs.remove(f)

    # Shift subsequent runs
    for old, new in shifts:
        if old.exists():
            # Update scans.tsv
            scans = find_scans_tsv(old, dataset.root)
            if scans:
                scans_dir = scans.parent
                try:
                    old_rel = str(old.relative_to(scans_dir))
                    new_rel = str(new.relative_to(scans_dir))
                    update_scans_entry(scans, old_rel, new_rel)
                except ValueError:
                    pass
            vcs.move(old, new)

    return result
