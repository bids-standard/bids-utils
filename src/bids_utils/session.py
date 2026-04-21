"""Session rename operations (User Story 5)."""

from __future__ import annotations

from pathlib import Path

from bids_utils._dataset import BIDSDataset
from bids_utils._io import update_json_references
from bids_utils._scans import read_scans_tsv, write_scans_tsv
from bids_utils._types import (
    AnnexedMode,
    Change,
    OperationResult,
    _is_bids_data_entry,
)
from bids_utils._vcs import VCSBackend


def _rewrite_scans_labels(
    scans_file: Path,
    old_label: str,
    new_label: str,
    vcs: VCSBackend,
    amode: AnnexedMode,
) -> None:
    """Read a scans.tsv and rewrite any ``filename`` entry containing *old_label*.

    If no row needs to change, the file is left untouched.
    """
    rows = read_scans_tsv(scans_file, vcs=vcs, annexed_mode=amode)
    modified = False
    for row in rows:
        fn = row.get("filename", "")
        if old_label in fn:
            row["filename"] = fn.replace(old_label, new_label)
            modified = True
    if modified:
        write_scans_tsv(scans_file, rows, vcs=vcs)


def rename_session(
    dataset: BIDSDataset,
    old: str,
    new: str,
    *,
    subject: str | None = None,
    dry_run: bool = False,
) -> OperationResult:
    """Rename a session. Use old="" for move-into-session.

    Parameters
    ----------
    old, new
        Session labels WITHOUT "ses-" prefix. old="" means
        "introduce sessions where none exist".
    subject
        If specified, only rename for this subject. Otherwise all subjects.
    """
    result = OperationResult(dry_run=dry_run)
    old_id = f"ses-{old}" if old and not old.startswith("ses-") else old
    new_id = f"ses-{new}" if not new.startswith("ses-") else new

    # Find subject directories to process
    if subject:
        sub_id = f"sub-{subject}" if not subject.startswith("sub-") else subject
        sub_dirs = [dataset.root / sub_id]
    else:
        sub_dirs = sorted(
            d
            for d in dataset.root.iterdir()
            if d.is_dir() and d.name.startswith("sub-")
        )

    vcs = dataset.vcs
    amode = dataset.annexed_mode

    for sub_dir in sub_dirs:
        if not sub_dir.is_dir():
            continue

        sub_name = sub_dir.name

        if old_id:
            # Rename existing session
            old_ses_dir = sub_dir / old_id
            new_ses_dir = sub_dir / new_id

            if not old_ses_dir.is_dir():
                result.warnings.append(
                    f"{sub_name}: session {old_id} not found, skipping"
                )
                continue

            if new_ses_dir.exists():
                result.success = False
                result.errors.append(
                    f"{sub_name}: target session {new_id} already exists"
                )
                return result

            result.changes.append(
                Change(
                    action="rename",
                    source=old_ses_dir,
                    target=new_ses_dir,
                    detail=f"{sub_name}: rename {old_id} → {new_id}",
                )
            )

            # Enumerate per-file renames (for detailed dry-run)
            old_label = old_id
            new_label = new_id
            file_renames: list[tuple[str, str]] = []
            for f in sorted(old_ses_dir.rglob("*"), reverse=True):
                if _is_bids_data_entry(f) and old_label in f.name:
                    new_name = f.name.replace(old_label, new_label)
                    if f.name != new_name:
                        # Record with paths relative to old_ses_dir
                        rel = f.relative_to(old_ses_dir)
                        new_rel = rel.parent / new_name
                        result.changes.append(
                            Change(
                                action="rename",
                                source=old_ses_dir / rel,
                                target=new_ses_dir / new_rel,
                                detail=f"  {f.name} → {new_name}",
                            )
                        )
                        file_renames.append((f.name, new_name))

            # Enumerate scans.tsv edits
            for scans_file in old_ses_dir.rglob("*_scans.tsv"):
                result.changes.append(
                    Change(
                        action="modify",
                        source=scans_file,
                        detail=f"  update {scans_file.name} entries",
                    )
                )

            if dry_run:
                continue

            vcs.move(old_ses_dir, new_ses_dir)

            # Rename files within the session (reverse order: children
            # before parents so files inside .ds/.zarr get renamed first)
            for f in sorted(new_ses_dir.rglob("*"), reverse=True):
                if _is_bids_data_entry(f) and old_label in f.name:
                    new_name = f.name.replace(old_label, new_label)
                    new_path = f.parent / new_name
                    if f != new_path:
                        vcs.move(f, new_path)

            # Update scans.tsv (within session dir and at subject level)
            for scans_file in new_ses_dir.rglob("*_scans.tsv"):
                _rewrite_scans_labels(
                    scans_file, old_label, new_label, vcs, amode
                )

            # Also update subject-level scans.tsv which may reference
            # files by session-relative paths (e.g., ses-1/eeg/...)
            for scans_file in sub_dir.iterdir():
                if not scans_file.name.endswith("_scans.tsv"):
                    continue
                if not (scans_file.is_file() or scans_file.is_symlink()):
                    continue
                _rewrite_scans_labels(
                    scans_file, old_label, new_label, vcs, amode
                )

        else:
            # Move into session: no existing session, introduce new one
            # Move datatype dirs into ses-X/
            new_ses_dir = sub_dir / new_id
            if new_ses_dir.exists():
                result.success = False
                result.errors.append(
                    f"{sub_name}: target session {new_id} already exists"
                )
                return result

            # Find datatype directories (func/, anat/, fmap/, etc.)
            datatype_dirs = [
                d
                for d in sub_dir.iterdir()
                if d.is_dir() and not d.name.startswith("ses-")
            ]

            if not datatype_dirs:
                result.warnings.append(f"{sub_name}: no datatype directories to move")
                continue

            result.changes.append(
                Change(
                    action="create",
                    source=new_ses_dir,
                    detail=f"{sub_name}: create session directory {new_id}",
                )
            )

            # Enumerate per-file renames for detailed dry-run
            new_ses_label = new_id
            for dt_dir in datatype_dirs:
                for f in sorted(dt_dir.rglob("*")):
                    if not _is_bids_data_entry(f):
                        continue
                    if sub_name in f.name and new_ses_label not in f.name:
                        new_name = f.name.replace(
                            f"{sub_name}_", f"{sub_name}_{new_ses_label}_"
                        )
                        if f.name != new_name:
                            result.changes.append(
                                Change(
                                    action="rename",
                                    source=f,
                                    target=new_ses_dir / dt_dir.name / new_name,
                                    detail=f"  {f.name} → {new_name}",
                                )
                            )

            if dry_run:
                continue

            new_ses_dir.mkdir()

            # Move datatype dirs
            for dt_dir in datatype_dirs:
                target = new_ses_dir / dt_dir.name
                vcs.move(dt_dir, target)

            # Rename files to include session entity (reverse order: children
            # before parents so files inside .ds/.zarr get renamed first)
            for f in sorted(new_ses_dir.rglob("*"), reverse=True):
                if (
                    _is_bids_data_entry(f)
                    and sub_name in f.name
                    and new_ses_label not in f.name
                ):
                    new_name = f.name.replace(
                        f"{sub_name}_", f"{sub_name}_{new_ses_label}_"
                    )
                    new_path = f.parent / new_name
                    if f != new_path:
                        vcs.move(f, new_path)

            # Move scans.tsv if it exists at subject level
            sub_scans = sub_dir / f"{sub_name}_scans.tsv"
            if sub_scans.is_file():
                new_scans = new_ses_dir / f"{sub_name}_{new_ses_label}_scans.tsv"
                vcs.move(sub_scans, new_scans)
                # Update entries in scans.tsv
                rows = read_scans_tsv(
                    new_scans, vcs=vcs, annexed_mode=amode
                )
                for row in rows:
                    fn = row.get("filename", "")
                    if sub_name in fn and new_ses_label not in fn:
                        # Update filenames in scans entries
                        parts = fn.split("/", 1)
                        if len(parts) == 2:
                            datatype, fname = parts
                            new_fname = fname.replace(
                                f"{sub_name}_", f"{sub_name}_{new_ses_label}_"
                            )
                            row["filename"] = f"{datatype}/{new_fname}"
                write_scans_tsv(new_scans, rows, vcs=vcs)

    # Update IntendedFor / AssociatedEmptyRoom / Sources references
    if old_id and not dry_run:
        update_json_references(
            dataset.root, old_id, new_id, vcs=vcs, annexed_mode=amode
        )

    return result
