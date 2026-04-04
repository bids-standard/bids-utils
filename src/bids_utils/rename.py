"""File rename: core operation (User Story 1).

Renames a BIDS file and all its sidecars, updates _scans.tsv,
and uses VCS when present.
"""

from __future__ import annotations

from pathlib import Path

from bids_utils._dataset import BIDSDataset
from bids_utils._scans import find_scans_tsv, update_scans_entry
from bids_utils._sidecars import find_sidecars
from bids_utils._types import BIDSPath, Change, OperationResult


def rename_file(
    dataset: BIDSDataset,
    path: str | Path,
    *,
    set_entities: dict[str, str] | None = None,
    new_suffix: str | None = None,
    dry_run: bool = False,
    include_sourcedata: bool = False,
) -> OperationResult:
    """Rename a BIDS file and all its sidecars.

    Parameters
    ----------
    dataset
        The BIDS dataset containing the file.
    path
        Path to the primary file (absolute or relative to dataset root).
    set_entities
        Entity key-value overrides (e.g., ``{"task": "nback"}``).
    new_suffix
        Optional new suffix (e.g., ``"T1w"``).
    dry_run
        If True, compute and return changes without modifying files.
    include_sourcedata
        If True, also rename matching files in sourcedata/.

    Returns
    -------
    OperationResult
        Summary of changes made (or planned if dry_run).
    """
    result = OperationResult(dry_run=dry_run)

    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = dataset.root / file_path

    if not file_path.exists():
        result.success = False
        result.errors.append(f"File not found: {file_path}")
        return result

    # Parse the source filename
    bids_path = BIDSPath.from_path(file_path)

    # Apply overrides
    if set_entities:
        bids_path = bids_path.with_entities(**set_entities)
    if new_suffix:
        bids_path = bids_path.with_suffix(new_suffix)

    new_filename = bids_path.to_filename()
    new_file_path = file_path.parent / new_filename

    # Check no-op
    if file_path == new_file_path:
        result.warnings.append("Source and target are the same; nothing to do")
        return result

    # Check for conflicts
    if new_file_path.exists():
        result.success = False
        result.errors.append(f"Target already exists: {new_file_path}")
        return result

    # Collect all files to rename: primary + sidecars
    files_to_rename: list[tuple[Path, Path]] = [(file_path, new_file_path)]

    sidecars = find_sidecars(file_path)
    for sidecar in sidecars:
        old_stem, _ = _split_stem_ext(sidecar.name)
        new_stem, _ = _split_stem_ext(new_filename)
        # Sidecar keeps its own extension but gets the new stem
        new_sidecar_name = new_stem + _get_extension(sidecar.name)
        new_sidecar_path = sidecar.parent / new_sidecar_name

        if new_sidecar_path.exists() and new_sidecar_path != sidecar:
            result.success = False
            result.errors.append(f"Sidecar target already exists: {new_sidecar_path}")
            return result

        files_to_rename.append((sidecar, new_sidecar_path))

    # Record changes
    for old, new in files_to_rename:
        result.changes.append(
            Change(
                action="rename",
                source=old,
                target=new,
                detail=f"Rename {old.name} → {new.name}",
            )
        )

    # Update _scans.tsv
    scans_path = find_scans_tsv(file_path, dataset.root)
    if scans_path is not None:
        # Compute the relative path as stored in _scans.tsv
        scans_dir = scans_path.parent
        try:
            old_rel = str(file_path.relative_to(scans_dir))
            new_rel = str(new_file_path.relative_to(scans_dir))
        except ValueError:
            old_rel = ""
            new_rel = ""

        if old_rel and new_rel:
            result.changes.append(
                Change(
                    action="modify",
                    source=scans_path,
                    detail=f"Update _scans.tsv: {old_rel} → {new_rel}",
                )
            )

    if dry_run:
        return result

    # Execute renames
    vcs = dataset.vcs
    for old, new in files_to_rename:
        vcs.move(old, new)

    # Update _scans.tsv
    if scans_path is not None and old_rel and new_rel:
        update_scans_entry(scans_path, old_rel, new_rel)

    return result


def _split_stem_ext(filename: str) -> tuple[str, str]:
    """Split filename into stem and extension, handling .nii.gz."""
    for compound in (".nii.gz", ".tsv.gz"):
        if filename.endswith(compound):
            return filename[: -len(compound)], compound
    parts = filename.rsplit(".", 1)
    if len(parts) == 2:
        return parts[0], "." + parts[1]
    return filename, ""


def _get_extension(filename: str) -> str:
    """Get the extension from a filename, handling .nii.gz."""
    _, ext = _split_stem_ext(filename)
    return ext
