"""Metadata aggregate/segregate/audit operations (User Story 6).

Uses BIDS inheritance hierarchy to manage metadata distribution.
"""

from __future__ import annotations

import contextlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from bids_utils._dataset import BIDSDataset
from bids_utils._types import Change, OperationResult


@dataclass
class AuditResult:
    """Result of a metadata audit."""

    inconsistent_keys: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    total_files: int = 0


def _find_json_sidecars(root: Path, scope: Path | None = None) -> list[Path]:
    """Find all JSON sidecar files (not dataset_description.json)."""
    search = scope or root
    return sorted(
        f
        for f in search.rglob("*.json")
        if f.name != "dataset_description.json"
        and not any(p.startswith(".") for p in f.relative_to(root).parts)
    )


def _group_by_stem_suffix(files: list[Path]) -> dict[str, list[Path]]:
    """Group JSON files by their suffix (e.g., _bold.json, _T1w.json)."""
    groups: dict[str, list[Path]] = defaultdict(list)
    for f in files:
        # Extract suffix: last underscore-separated part before .json
        stem = f.stem  # e.g., sub-01_task-rest_bold
        parts = stem.rsplit("_", 1)
        suffix = parts[-1] if len(parts) > 1 else stem
        groups[suffix].append(f)
    return dict(groups)


def _find_common_keys(json_files: list[Path]) -> dict[str, Any]:
    """Find key-value pairs common to ALL files."""
    if not json_files:
        return {}

    # Load all files
    all_data: list[dict[str, Any]] = []
    for f in json_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                all_data.append(data)
        except (json.JSONDecodeError, OSError):
            return {}  # Can't determine common keys if a file is unreadable

    if len(all_data) != len(json_files):
        return {}  # Some files missing or unreadable

    if not all_data:
        return {}

    # Keys present in ALL files with identical values
    common: dict[str, Any] = {}
    candidate_keys = set(all_data[0].keys())
    for data in all_data[1:]:
        candidate_keys &= set(data.keys())

    for key in candidate_keys:
        values = [data[key] for data in all_data]
        if all(v == values[0] for v in values):
            common[key] = values[0]

    return common


def aggregate_metadata(
    dataset: BIDSDataset,
    *,
    scope: str | Path | None = None,
    mode: Literal["copy", "move"] = "move",
    dry_run: bool = False,
) -> OperationResult:
    """Hoist common metadata up the inheritance hierarchy.

    Parameters
    ----------
    scope
        Restrict to a subdirectory (e.g., "sub-01/").
    mode
        "move" removes keys from leaf files; "copy" keeps them.
    """
    result = OperationResult(dry_run=dry_run)

    scope_path = Path(scope) if scope else None
    if scope_path and not scope_path.is_absolute():
        scope_path = dataset.root / scope_path

    json_files = _find_json_sidecars(dataset.root, scope_path)
    groups = _group_by_stem_suffix(json_files)

    for suffix, files in groups.items():
        if len(files) < 2:
            continue

        common = _find_common_keys(files)
        if not common:
            continue

        # Determine the parent directory for the aggregated sidecar
        # Use the longest common parent directory
        parents = [f.parent for f in files]
        common_parent = parents[0]
        for p in parents[1:]:
            while not str(p).startswith(str(common_parent)):
                common_parent = common_parent.parent
                if common_parent == dataset.root.parent:
                    break

        # Target: parent_dir/suffix.json (e.g., bold.json)
        target = common_parent / f"{suffix}.json"

        result.changes.append(
            Change(
                action="create" if not target.exists() else "modify",
                source=target,
                detail=(
                    f"Aggregate {len(common)} key(s) to "
                    f"{target.relative_to(dataset.root)}: {list(common.keys())}"
                ),
            )
        )

        if dry_run:
            continue

        # Write/update the parent-level sidecar
        existing: dict[str, Any] = {}
        if target.exists():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                existing = json.loads(target.read_text(encoding="utf-8"))
        existing.update(common)
        target.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

        # Remove keys from leaf files (if mode="move")
        if mode == "move":
            for f in files:
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                modified = False
                for key in common:
                    if key in data:
                        del data[key]
                        modified = True
                if modified:
                    f.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    return result


def segregate_metadata(
    dataset: BIDSDataset,
    *,
    scope: str | Path | None = None,
    dry_run: bool = False,
) -> OperationResult:
    """Push all metadata down to leaf-level sidecars.

    This is the inverse of aggregate: for each data file, resolve
    the full inheritance chain and write a self-contained sidecar.
    """
    result = OperationResult(dry_run=dry_run)

    scope_path = Path(scope) if scope else None
    if scope_path and not scope_path.is_absolute():
        scope_path = dataset.root / scope_path

    search = scope_path or dataset.root

    # Find all data files (non-JSON, non-TSV)
    data_files = sorted(
        f
        for f in search.rglob("*")
        if f.is_file()
        and f.suffix in (".gz", "")
        and not f.name.endswith(".json")
        and not f.name.endswith(".tsv")
        and "sub-" in f.name
    )

    for data_file in data_files:
        # Find the JSON sidecar for this data file
        stem = data_file.name
        for ext in (".nii.gz", ".nii"):
            if stem.endswith(ext):
                stem = stem[: -len(ext)]
                break

        leaf_json = data_file.parent / f"{stem}.json"

        # Resolve metadata through inheritance chain
        resolved = _resolve_inheritance(data_file, dataset.root)

        if not resolved:
            continue

        result.changes.append(
            Change(
                action="modify" if leaf_json.exists() else "create",
                source=leaf_json,
                detail=f"Segregate metadata to {leaf_json.name}",
            )
        )

        if dry_run:
            continue

        leaf_json.write_text(json.dumps(resolved, indent=2) + "\n", encoding="utf-8")

    return result


def _resolve_inheritance(data_file: Path, dataset_root: Path) -> dict[str, Any]:
    """Resolve metadata through the BIDS inheritance chain."""
    # Extract suffix from filename
    stem = data_file.name
    for ext in (".nii.gz", ".nii", ".tsv.gz"):
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
            break
    else:
        stem = data_file.stem

    parts = stem.rsplit("_", 1)
    suffix = parts[-1] if len(parts) > 1 else stem

    # Walk from dataset root down to the file's directory
    resolved: dict[str, Any] = {}
    current = dataset_root
    file_dir = data_file.parent

    # Collect directories from root to file
    dirs = [dataset_root]
    rel = file_dir.relative_to(dataset_root)
    for part in rel.parts:
        current = current / part
        dirs.append(current)

    for d in dirs:
        # Check for suffix.json at each level
        sidecar = d / f"{suffix}.json"
        if sidecar.is_file():
            try:
                data = json.loads(sidecar.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    resolved.update(data)
            except (json.JSONDecodeError, OSError):
                pass

    # Finally, the leaf-level sidecar (file-specific)
    leaf = data_file.parent / f"{stem}.json"
    if leaf.is_file():
        try:
            data = json.loads(leaf.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                resolved.update(data)
        except (json.JSONDecodeError, OSError):
            pass

    return resolved


def audit_metadata(dataset: BIDSDataset) -> AuditResult:
    """Report metadata keys that are neither fully unique nor fully equivalent.

    These indicate potential acquisition inconsistencies.
    """
    result = AuditResult()

    json_files = _find_json_sidecars(dataset.root)
    result.total_files = len(json_files)

    groups = _group_by_stem_suffix(json_files)

    for suffix, files in groups.items():
        if len(files) < 2:
            continue

        # Collect all key-value pairs
        all_data: list[dict[str, Any]] = []
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    all_data.append(data)
            except (json.JSONDecodeError, OSError):
                continue

        if len(all_data) < 2:
            continue

        # Check each key
        all_keys: set[str] = set()
        for data in all_data:
            all_keys.update(data.keys())

        for key in all_keys:
            values = [data.get(key) for data in all_data if key in data]
            if not values:
                continue

            # Skip if all same (fully equivalent) or all different (fully unique)
            unique_values = {json.dumps(v, sort_keys=True) for v in values}
            if len(unique_values) == 1 or len(unique_values) == len(values):
                continue

            # This key has inconsistent values
            result.inconsistent_keys[f"{suffix}/{key}"] = [
                {"file": str(f), "value": data.get(key)}
                for f, data in zip(files, all_data, strict=False)
                if key in data
            ]

    return result
