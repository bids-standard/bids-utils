"""Self-tests for the FR-042 integration test fixture pattern.

Verifies that the fixtures + helpers in ``tests/integration/`` behave as
contracted before downstream phases (Phase 5b / SC-009 / SC-010) start
relying on them. New code under ``tests/integration/`` only — no
production-code dependencies.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.conftest import (
    BIDS_EXAMPLES_DIR,
    requires_bids_examples,
    requires_bids_validator,
    requires_git_annex,
)
from tests.integration._nonbids_inject import (
    NONBIDS_SUFFIXES,
    inject_nonbids_suffixes,
)
from tests.integration._validator import (
    assert_validator_flags,
    assert_validator_passes,
)
from tests.integration._worktree_fixture import (
    _add_worktree,
    _remove_worktree,
    bids_examples_worktree,
    bids_examples_worktree_annexed,
)

__all__ = [
    # Re-export pytest fixtures so they're injectable in this module.
    "bids_examples_worktree",
    "bids_examples_worktree_annexed",
]

# Pick a canonical small dataset for self-tests. ds001 is a basic fMRI
# dataset present in the bids-examples submodule and small enough to
# worktree quickly.
_DEFAULT_DATASET = "ds001"


def _pick_dataset_id() -> str:
    """Return a dataset name guaranteed to exist, or skip."""
    if not BIDS_EXAMPLES_DIR.is_dir():
        pytest.skip("bids-examples submodule not available")
    candidate = BIDS_EXAMPLES_DIR / _DEFAULT_DATASET
    if candidate.is_dir() and (candidate / "dataset_description.json").is_file():
        return _DEFAULT_DATASET
    for d in sorted(BIDS_EXAMPLES_DIR.iterdir()):
        if d.is_dir() and (d / "dataset_description.json").is_file():
            return d.name
    pytest.skip("no usable datasets in bids-examples")


def _snapshot(root: Path) -> list[tuple[str, int]]:
    """Sorted (relpath, size) of every regular (non-symlink) file under *root*."""
    out: list[tuple[str, int]] = []
    for f in root.rglob("*"):
        if not f.is_file() or f.is_symlink():
            continue
        out.append((str(f.relative_to(root)), f.stat().st_size))
    out.sort()
    return out


@requires_bids_examples
@pytest.mark.integration
@pytest.mark.ai_generated
def test_worktree_lifecycle_does_not_mutate_host(tmp_path: Path) -> None:
    """Add + remove of a worktree must leave the host clone untouched."""
    ds_name = _pick_dataset_id()
    host_ds = BIDS_EXAMPLES_DIR / ds_name

    before = _snapshot(host_ds)
    ds_path = _add_worktree(tmp_path, ds_name)
    try:
        assert ds_path.is_dir(), f"worktree dataset path missing: {ds_path}"
        # Mutate inside the worktree to prove it's a real, writable copy.
        marker = ds_path / "_lifecycle_marker.txt"
        marker.write_text("hello")
        assert marker.is_file()
        # Host should be unchanged while the worktree exists.
        assert _snapshot(host_ds) == before, "host mutated during worktree life"
    finally:
        _remove_worktree(ds_path)

    # And after teardown.
    assert _snapshot(host_ds) == before, "host mutated by worktree teardown"
    # The worktree path itself should be gone.
    assert not ds_path.exists(), f"worktree leaked: {ds_path}"


@requires_bids_examples
@pytest.mark.integration
@pytest.mark.ai_generated
def test_two_worktrees_are_independent(
    bids_examples_worktree: Callable[[str], Path],
) -> None:
    ds_name = _pick_dataset_id()
    a = bids_examples_worktree(ds_name)
    b = bids_examples_worktree(ds_name)
    assert a != b, "expected two distinct worktree paths"
    assert a.is_dir() and b.is_dir()

    (a / "_only_in_a.txt").write_text("a")
    assert not (b / "_only_in_a.txt").exists(), "worktrees share state"


@requires_bids_examples
@requires_git_annex
@pytest.mark.integration
@pytest.mark.ai_generated
def test_annexed_variant_produces_locked_symlinks(
    bids_examples_worktree_annexed: Callable[[str], Path],
) -> None:
    ds_name = _pick_dataset_id()
    wt = bids_examples_worktree_annexed(ds_name)
    candidates = list(wt.rglob("sub-*_*.nii.gz")) + list(wt.rglob("sub-*_*.nii"))
    if not candidates:
        pytest.skip(f"no nifti data files in {ds_name}")
    locked = [f for f in candidates if f.is_symlink()]
    assert locked, (
        f"expected at least one locked annexed symlink under {wt}, "
        f"saw {[str(f) for f in candidates[:3]]}"
    )


@requires_bids_examples
@pytest.mark.integration
@pytest.mark.ai_generated
def test_inject_creates_real_artefacts(
    bids_examples_worktree: Callable[[str], Path],
) -> None:
    ds_name = _pick_dataset_id()
    wt = bids_examples_worktree(ds_name)
    created = inject_nonbids_suffixes(
        wt, kinds=tuple(NONBIDS_SUFFIXES), seed=0, count=1
    )
    if not created:
        pytest.skip(f"no candidate data files in {ds_name}")
    # Each kind should produce at least one primary-or-sidecar file.
    assert len(created) >= len(NONBIDS_SUFFIXES)
    for p in created:
        assert p.exists() or p.is_symlink(), f"injected path missing: {p}"


@requires_bids_examples
@pytest.mark.integration
@pytest.mark.ai_generated
def test_inject_is_deterministic_under_seed(
    bids_examples_worktree: Callable[[str], Path],
) -> None:
    """Same seed + same worktree state ⇒ same selected source files."""
    ds_name = _pick_dataset_id()
    wt1 = bids_examples_worktree(ds_name)
    wt2 = bids_examples_worktree(ds_name)
    a = inject_nonbids_suffixes(wt1, kinds=("dup",), seed=42, count=2)
    b = inject_nonbids_suffixes(wt2, kinds=("dup",), seed=42, count=2)
    a_rel = sorted(str(p.relative_to(wt1)) for p in a)
    b_rel = sorted(str(p.relative_to(wt2)) for p in b)
    assert a_rel == b_rel, f"seed-42 produced different selections:\n{a_rel}\n{b_rel}"


@requires_bids_examples
@requires_bids_validator
@pytest.mark.integration
@pytest.mark.ai_generated
def test_inject_survives_validator_round_trip(
    bids_examples_worktree: Callable[[str], Path],
) -> None:
    """SC-009 pre-condition: injected files are visible to the validator."""
    ds_name = _pick_dataset_id()
    wt = bids_examples_worktree(ds_name)
    created = inject_nonbids_suffixes(wt, kinds=("dup",), seed=0, count=1)
    if not created:
        pytest.skip(f"no candidate data files in {ds_name}")
    # We only assert flagging on the primary (non-sidecar) injected files
    # since the validator's coverage of orphan sidecars is less reliable.
    primaries = [
        p for p in created
        if p.suffix not in {".json", ".bvec", ".bval", ".tsv"}
    ]
    if not primaries:
        pytest.skip("only sidecars were injected for this dataset")
    assert_validator_flags(wt, expected_files=primaries[:1])


@requires_bids_examples
@requires_bids_validator
@pytest.mark.integration
@pytest.mark.ai_generated
def test_validator_passes_helper_tolerates_pre_existing(
    bids_examples_worktree: Callable[[str], Path],
) -> None:
    """A clean worktree (no injection) should pass ``assert_validator_passes``.

    We allow the dataset's own pre-existing error codes to be ignored —
    several ``bids-examples`` datasets ship with intentional or known
    issues that we don't want to fail the helper on.
    """
    ds_name = _pick_dataset_id()
    wt = bids_examples_worktree(ds_name)
    # Compute pre-existing codes once and feed them in as ignored.
    from tests.conftest import validate_dataset

    _, errs = validate_dataset(wt)
    pre_codes = sorted({e.get("code") for e in errs if e.get("code")})
    assert_validator_passes(wt, ignore_pre_existing=pre_codes)


@pytest.mark.ai_generated
def test_inject_rejects_unknown_kind(tmp_path: Path) -> None:
    """``inject_nonbids_suffixes`` raises ``ValueError`` on unknown kinds."""
    # No bids-examples / fixture needed: a fake non-empty dataset suffices.
    fake = tmp_path / "ds"
    (fake / "sub-01" / "func").mkdir(parents=True)
    (fake / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz").write_bytes(b"")
    with pytest.raises(ValueError, match="unknown injection kind"):
        inject_nonbids_suffixes(fake, kinds=("not-a-kind",))  # type: ignore[arg-type]
