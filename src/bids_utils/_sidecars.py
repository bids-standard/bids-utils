"""Sidecar file discovery for BIDS files."""

from __future__ import annotations

import re
from pathlib import Path

from bids_utils._schema import BIDSSchema

# Compound extensions that need special handling
_COMPOUND_EXTS = {".nii.gz", ".tsv.gz"}


def _split_extension(filename: str) -> tuple[str, str]:
    """Split a filename into stem and extension, handling compound extensions."""
    for ext in _COMPOUND_EXTS:
        if filename.endswith(ext):
            return filename[: -len(ext)], ext
    # Simple extension
    parts = filename.rsplit(".", 1)
    if len(parts) == 2:
        return parts[0], "." + parts[1]
    return filename, ""


def find_sidecars(
    file_path: Path,
    schema: BIDSSchema | None = None,
) -> list[Path]:
    """Find all sidecar files associated with a BIDS file.

    Given a primary data file (e.g., sub-01_task-rest_bold.nii.gz),
    returns all existing sidecar files in the same directory
    (e.g., sub-01_task-rest_bold.json, .bvec, .bval).

    Parameters
    ----------
    file_path
        Path to the primary BIDS file.
    schema
        Optional schema for suffix-specific extension lookup.

    Returns
    -------
    list[Path]
        Existing sidecar files (does not include the primary file itself).
    """
    file_path = Path(file_path)
    parent = file_path.parent
    stem, ext = _split_extension(file_path.name)

    # Determine which extensions to check
    if schema is not None:
        # Extract suffix from stem
        parts = stem.rsplit("_", 1)
        suffix = parts[-1] if len(parts) > 1 else stem
        check_exts = schema.sidecar_extensions(suffix)
    else:
        # Default: check common sidecar extensions
        check_exts = [".json", ".bvec", ".bval"]

    sidecars: list[Path] = []
    for sidecar_ext in check_exts:
        if sidecar_ext == ext:
            continue  # Skip the primary file's own extension
        candidate = parent / f"{stem}{sidecar_ext}"
        if candidate.is_file():
            sidecars.append(candidate)

    return sidecars
