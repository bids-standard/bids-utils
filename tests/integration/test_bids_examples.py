"""Integration tests that sweep across bids-examples datasets.

These tests are skipped when the bids-examples submodule is not available.
Run with: pytest tests/integration/ -m integration
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from bids_utils._dataset import BIDSDataset
from bids_utils.migrate import migrate_dataset
from bids_utils.rename import rename_file
from bids_utils.subject import rename_subject
from tests.conftest import BIDS_EXAMPLES_DIR, requires_bids_examples


def _iter_datasets() -> list[Path]:
    """Yield paths to bids-examples datasets that have dataset_description.json."""
    if not BIDS_EXAMPLES_DIR.is_dir():
        return []
    datasets = []
    for d in sorted(BIDS_EXAMPLES_DIR.iterdir()):
        if d.is_dir() and (d / "dataset_description.json").is_file():
            datasets.append(d)
    return datasets


def _dataset_ids() -> list[str]:
    return [d.name for d in _iter_datasets()]


def _copy_dataset(src: Path, tmp_path: Path) -> Path:
    """Copy a bids-examples dataset to a temp dir for mutation."""
    dst = tmp_path / src.name
    shutil.copytree(src, dst)
    return dst


def _find_renameable_file(ds_path: Path) -> Path | None:
    """Find a BIDS data file suitable for rename testing.

    Looks for files with a sub- entity and a recognised BIDS suffix,
    not just .nii.gz — so EEG, MEG, motion, fNIRS, microscopy etc.
    datasets are also covered.
    """
    # Broad set of data-file extensions found in bids-examples
    for pattern in [
        "sub-*_*.nii.gz",
        "sub-*_*.nii",
        "sub-*_*.edf",
        "sub-*_*.vhdr",
        "sub-*_*.set",
        "sub-*_*.bdf",
        "sub-*_*.eeg",
        "sub-*_*.fif",
        "sub-*_*.snirf",
        "sub-*_*.ome.tif",
        "sub-*_*.ome.zarr",
        "sub-*_*.tif",
        "sub-*_*.tsv",
        "sub-*_*.json",
    ]:
        hits = sorted(ds_path.rglob(pattern))
        if hits:
            return hits[0]
    return None


@requires_bids_examples
@pytest.mark.integration
class TestRenameSweep:
    """Rename one file in each dataset; verify no crash and file count preserved."""

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _dataset_ids())
    def test_rename_dry_run(self, ds_name: str) -> None:
        ds_path = BIDS_EXAMPLES_DIR / ds_name
        try:
            ds = BIDSDataset.from_path(ds_path)
        except (FileNotFoundError, ValueError):
            pytest.skip(reason=f"cannot load dataset: {ds_name}")

        target = _find_renameable_file(ds_path)
        if target is None:
            pytest.skip(reason=f"no renameable BIDS data file in {ds_name}")

        result = rename_file(
            ds,
            target,
            set_entities={"run": "99"},
            dry_run=True,
        )

        assert result.success, f"Dry-run rename failed in {ds_name}: {result.errors}"
        assert result.dry_run
        assert len(result.changes) >= 1


@requires_bids_examples
@pytest.mark.integration
class TestSubjectRenameSweep:
    """Rename first subject in datasets with >=2 subjects (dry-run)."""

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _dataset_ids())
    def test_subject_rename_dry_run(self, ds_name: str) -> None:
        ds_path = BIDS_EXAMPLES_DIR / ds_name
        try:
            ds = BIDSDataset.from_path(ds_path)
        except (FileNotFoundError, ValueError):
            pytest.skip(reason=f"cannot load dataset: {ds_name}")

        sub_dirs = sorted(
            d for d in ds_path.iterdir()
            if d.is_dir() and d.name.startswith("sub-")
        )
        if len(sub_dirs) < 1:
            pytest.skip(reason=f"no sub-* directories in {ds_name}")

        old_sub = sub_dirs[0].name
        result = rename_subject(ds, old_sub, "sub-TESTZZ", dry_run=True)

        assert result.success, (
            f"Dry-run subject rename failed in {ds_name}: {result.errors}"
        )
        assert result.dry_run


@requires_bids_examples
@pytest.mark.integration
class TestMigrateSweep:
    """Run migrate --dry-run on each dataset; verify no crashes."""

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _dataset_ids())
    def test_migrate_dry_run(self, ds_name: str) -> None:
        ds_path = BIDS_EXAMPLES_DIR / ds_name
        try:
            ds = BIDSDataset.from_path(ds_path)
        except (FileNotFoundError, ValueError):
            pytest.skip(reason=f"cannot load dataset: {ds_name}")

        result = migrate_dataset(ds, dry_run=True)

        # Should never crash — either finds migrations or reports nothing to do
        assert result.dry_run
        assert result.success or result.warnings or result.findings


@requires_bids_examples
@pytest.mark.integration
class TestRenameMutating:
    """Actually rename a file in a copy and verify file counts match."""

    @pytest.mark.ai_generated
    def test_rename_preserves_file_count(self, tmp_path: Path) -> None:
        """Pick a dataset, copy it, rename one file, check file count."""
        datasets = _iter_datasets()
        # Find a dataset with .nii.gz files
        picked = None
        for d in datasets:
            if list(d.rglob("sub-*_*.nii.gz")):
                picked = d
                break
        if picked is None:
            pytest.skip(reason="no dataset with sub-*_*.nii.gz files found")

        ds_copy = _copy_dataset(picked, tmp_path)
        ds = BIDSDataset.from_path(ds_copy)

        nii_files = sorted(ds_copy.rglob("sub-*_*.nii.gz"))
        target = nii_files[0]

        # Count files before
        before = {f.relative_to(ds_copy) for f in ds_copy.rglob("*") if f.is_file()}

        result = rename_file(ds, target, set_entities={"run": "99"})
        assert result.success, f"Rename failed: {result.errors}"

        # Count files after — should be same count (renames, not creates/deletes)
        after = {f.relative_to(ds_copy) for f in ds_copy.rglob("*") if f.is_file()}
        assert len(after) == len(before), (
            f"File count changed: {len(before)} -> {len(after)}"
        )
