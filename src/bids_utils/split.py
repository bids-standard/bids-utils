"""Dataset split operations (User Story 10)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from bids_utils._dataset import BIDSDataset
from bids_utils._types import Change, OperationResult


def split_dataset(
    dataset: BIDSDataset,
    output: str | Path,
    *,
    suffix: str | None = None,
    datatype: str | None = None,
    dry_run: bool = False,
) -> OperationResult:
    """Extract a subset of a BIDS dataset by suffix or datatype.

    Parameters
    ----------
    output
        Path for the output dataset.
    suffix
        Filter by suffix (e.g., "bold").
    datatype
        Filter by datatype directory (e.g., "func").
    """
    result = OperationResult(dry_run=dry_run)
    output_path = Path(output)

    if not suffix and not datatype:
        result.success = False
        result.errors.append("Must specify --suffix or --datatype")
        return result

    # Create output directory
    if not dry_run:
        output_path.mkdir(parents=True, exist_ok=True)

    # Copy dataset_description.json
    desc = dataset.root / "dataset_description.json"
    if desc.exists():
        result.changes.append(
            Change(action="create", source=output_path / "dataset_description.json", detail="Copy dataset_description.json")
        )
        if not dry_run:
            shutil.copy2(desc, output_path / "dataset_description.json")

    # Walk through all files
    for f in sorted(dataset.root.rglob("*")):
        if not f.is_file():
            continue
        if f.name == "dataset_description.json":
            continue

        rel = f.relative_to(dataset.root)

        # Apply filters
        match = True
        if datatype:
            # Check if file is under a matching datatype directory
            match = datatype in rel.parts

        if suffix and match:
            # Check if filename contains the suffix
            stem = f.stem
            if f.name.endswith(".nii.gz"):
                stem = f.name[:-7]  # Remove .nii.gz
            parts = stem.rsplit("_", 1)
            file_suffix = parts[-1] if len(parts) > 1 else stem
            match = file_suffix == suffix

        if not match:
            continue

        target = output_path / rel
        result.changes.append(
            Change(action="create", source=target, detail=f"Copy {rel}")
        )

        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)

        # Also copy associated JSON sidecar
        if not f.name.endswith(".json"):
            json_name = f.name
            for ext in (".nii.gz", ".nii"):
                if json_name.endswith(ext):
                    json_name = json_name[: -len(ext)] + ".json"
                    break
            json_src = f.parent / json_name
            if json_src.exists():
                json_target = output_path / json_src.relative_to(dataset.root)
                if not any(c.source == json_target for c in result.changes):
                    result.changes.append(
                        Change(action="create", source=json_target, detail=f"Copy sidecar {json_name}")
                    )
                    if not dry_run:
                        json_target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(json_src, json_target)

    # Copy participants.tsv
    participants = dataset.root / "participants.tsv"
    if participants.exists() and not dry_run:
        shutil.copy2(participants, output_path / "participants.tsv")

    return result
