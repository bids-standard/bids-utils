"""Inject adversarial non-BIDS filename suffixes into a BIDS dataset worktree.

This is the FR-041 / FR-042 / SC-009 fixture helper. It synthesizes
heudiconv-style ``__dup-NN`` and other adversarial trailing segments
into a deterministic, seeded selection of data files (and their sidecars)
within a per-test worktree, so the file-touching commands (``rename``,
``edit-filename``, ``remove``, ``subject-rename``, ``session-rename``)
can be exercised against realistic non-BIDS source filenames without
requiring a real heudiconv/DICOM toolchain in CI.

Deterministic seed contract
---------------------------

For a fixed ``(seed, kinds, count)`` and a fixed worktree state (i.e. a
specific ``bids-examples`` HEAD), the set of selected source files is
stable across runs. Test authors can rely on the same ``seed`` choosing
the same files.
"""

from __future__ import annotations

import os
import random
import shutil
from pathlib import Path

__all__ = [
    "NONBIDS_SUFFIXES",
    "inject_nonbids_suffixes",
]


#: Mapping from injection-kind name → the literal trailing segment that
#: gets glued onto the BIDS stem before the extension. Each segment is
#: deliberately non-BIDS so the validator flags it.
NONBIDS_SUFFIXES: dict[str, str] = {
    "dup": "__dup-01",
    "plus_mine": "+mine",
    "crap": "--crap",
    "test": "_test",
}

# Data-file extensions we'll target across modalities. We intentionally
# exclude ``_scans.tsv`` and ``_events.tsv`` (auxiliary) by name later.
_DATA_FILE_PATTERNS: tuple[str, ...] = (
    "**/sub-*_*.nii.gz",
    "**/sub-*_*.nii",
    "**/sub-*_*.edf",
    "**/sub-*_*.vhdr",
    "**/sub-*_*.set",
    "**/sub-*_*.bdf",
    "**/sub-*_*.eeg",
    "**/sub-*_*.fif",
    "**/sub-*_*.snirf",
)

# Two-part extensions that a naive ``Path.suffix`` would mishandle.
_COMPOUND_EXTS: tuple[str, ...] = (".nii.gz", ".ome.tif", ".ome.zarr")


def _split_bids_ext(name: str) -> tuple[str, str]:
    """Split *name* into ``(stem, ext)`` honoring two-part BIDS extensions."""
    for ext in _COMPOUND_EXTS:
        if name.endswith(ext):
            return name[: -len(ext)], ext
    if "." in name:
        idx = name.rfind(".")
        return name[:idx], name[idx:]
    return name, ""


def _list_data_files(root: Path) -> list[Path]:
    """Return a stably-ordered list of candidate primary data files."""
    seen: set[Path] = set()
    out: list[Path] = []
    for pat in _DATA_FILE_PATTERNS:
        for p in sorted(root.glob(pat)):
            if p.name.endswith(("_scans.tsv", "_events.tsv")):
                continue
            if p in seen or not (p.is_file() or p.is_symlink()):
                continue
            seen.add(p)
            out.append(p)
    return out


def _materialize(src: Path, dst: Path) -> None:
    """Create *dst* as a real artefact mirroring *src*.

    For symlinks (annex-locked content), copy the link itself so *dst*
    points at the same annex object. For regular files, copy bytes.
    """
    if dst.exists() or dst.is_symlink():
        return
    if src.is_symlink():
        os.symlink(os.readlink(src), dst)
    else:
        shutil.copy2(src, dst)


def _inject_one(
    src: Path,
    suffix_segment: str,
) -> list[Path]:
    """Inject *suffix_segment* into *src*'s stem and into all its sidecars.

    Returns the list of newly-created paths (primary + each sidecar).
    """
    stem, ext = _split_bids_ext(src.name)
    new_stem = f"{stem}{suffix_segment}"
    out: list[Path] = []

    # Primary
    primary = src.parent / f"{new_stem}{ext}"
    if not primary.exists() and not primary.is_symlink():
        _materialize(src, primary)
        out.append(primary)

    # Sidecars: any sibling whose stem matches *src*'s stem exactly.
    # Compare stems (not basenames) so that compound extensions are
    # peeled correctly.
    for sib in sorted(src.parent.iterdir()):
        if sib == src:
            continue
        sib_stem, sib_ext = _split_bids_ext(sib.name)
        if sib_stem != stem:
            continue
        new_sib = src.parent / f"{new_stem}{sib_ext}"
        if new_sib.exists() or new_sib.is_symlink():
            continue
        _materialize(sib, new_sib)
        out.append(new_sib)
    return out


def inject_nonbids_suffixes(
    worktree_root: Path,
    *,
    kinds: tuple[str, ...] = ("dup",),
    seed: int = 0,
    count: int = 2,
) -> list[Path]:
    """Inject non-BIDS trailing segments into a deterministic file selection.

    Parameters
    ----------
    worktree_root
        BIDS dataset root within an ephemeral worktree (e.g. as returned
        by :func:`bids_examples_worktree`).
    kinds
        Which adversarial segments to inject. Each kind in
        :data:`NONBIDS_SUFFIXES` is sampled independently from the same
        candidate pool; a single source file may end up with multiple
        injected siblings if multiple kinds are requested.
    seed
        RNG seed for file selection. Same seed + same worktree state →
        same selection.
    count
        How many primary files per kind to inject suffixes into. Capped
        at the number of available candidates.

    Returns
    -------
    list[Path]
        All newly-created files (primaries + sidecars).
    """
    candidates = _list_data_files(worktree_root)
    if not candidates:
        return []

    created: list[Path] = []
    for kind in kinds:
        if kind not in NONBIDS_SUFFIXES:
            raise ValueError(
                f"unknown injection kind {kind!r}; "
                f"expected one of {sorted(NONBIDS_SUFFIXES)}"
            )
        # Independent RNG per kind so kinds are reproducible regardless
        # of their position in the *kinds* tuple.
        rng = random.Random(f"{seed}|{kind}")
        k = min(count, len(candidates))
        for src in rng.sample(candidates, k=k):
            created.extend(_inject_one(src, NONBIDS_SUFFIXES[kind]))
    return created
