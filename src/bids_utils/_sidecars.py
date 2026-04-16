"""Sidecar file discovery for BIDS files."""

from __future__ import annotations

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
    """Find all **same-directory** sidecar files associated with a BIDS file.

    Given a primary data file (e.g., ``sub-01_task-rest_bold.nii.gz``),
    returns all existing files in the **same directory** that share the
    same stem (e.g., ``.json``, ``.bvec``, ``.bval``, ``.tsv`` label
    tables, BrainVision companions ``.eeg``/``.vhdr``/``.vmrk``).

    .. note::

       This function does **not** walk the BIDS inheritance hierarchy.
       Higher-level sidecars (e.g., a ``task-rest_bold.json`` at the
       dataset root) are not returned.  For inheritance-aware metadata
       resolution, see ``metadata.py``.

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

    # Start with schema-known sidecar extensions
    sidecars: list[Path] = []
    seen_exts: set[str] = {ext}  # skip the primary file's own extension
    for sidecar_ext in check_exts:
        if sidecar_ext in seen_exts:
            continue
        seen_exts.add(sidecar_ext)
        candidate = parent / f"{stem}{sidecar_ext}"
        if candidate.exists() or candidate.is_symlink():
            sidecars.append(candidate)

    # For data files (not sidecars themselves), also discover all same-stem
    # companions.  This catches multi-file formats like BrainVision
    # (.eeg + .vhdr + .vmrk), companion label tables (.tsv for dseg),
    # and any other same-stem companions the schema doesn't list.
    sidecar_only_exts = {".json", ".bvec", ".bval"}
    if ext not in sidecar_only_exts:
        for sibling in parent.iterdir():
            if sibling.is_dir():
                continue
            sib_stem, sib_ext = _split_extension(sibling.name)
            if sib_stem == stem and sib_ext not in seen_exts:
                seen_exts.add(sib_ext)
                sidecars.append(sibling)

    return sidecars
