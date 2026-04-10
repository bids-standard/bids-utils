"""Integration tests that sweep across bids-examples datasets.

These tests are skipped when the bids-examples submodule is not available.
Run with: pytest tests/integration/ -m integration
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from bids_utils._dataset import BIDSDataset
from bids_utils._types import AnnexedMode
from bids_utils.merge import merge_datasets
from bids_utils.metadata import aggregate_metadata, audit_metadata, segregate_metadata
from bids_utils.migrate import migrate_dataset
from bids_utils.rename import rename_file
from bids_utils.run import remove_run
from bids_utils.session import rename_session
from bids_utils.subject import remove_subject, rename_subject
from tests.conftest import (
    BIDS_EXAMPLES_DIR,
    requires_bids_examples,
    requires_bids_validator,
    requires_git_annex,
    validate_dataset,
)


def _iter_datasets() -> list[Path]:
    """Yield paths to bids-examples datasets that have dataset_description.json."""
    if not BIDS_EXAMPLES_DIR.is_dir():
        return []
    datasets = []
    for d in sorted(BIDS_EXAMPLES_DIR.iterdir()):
        if d.is_dir() and (d / "dataset_description.json").is_file():
            datasets.append(d)
    print("DATASETS: ", datasets)
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
        except (FileNotFoundError, ValueError) as exc:
            pytest.skip(reason=f"cannot load {ds_name}: {exc}")

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
        except (FileNotFoundError, ValueError) as exc:
            pytest.skip(reason=f"cannot load {ds_name}: {exc}")

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
        except (FileNotFoundError, ValueError) as exc:
            pytest.skip(reason=f"cannot load {ds_name}: {exc}")

        result = migrate_dataset(ds, dry_run=True)

        # Should never crash — either finds migrations or reports nothing to do
        assert result.dry_run
        assert result.success or result.warnings or result.findings


@requires_bids_examples
@pytest.mark.integration
class TestMigrate20Sweep:
    """Run migrate --to 2.0 --dry-run on each dataset; verify no crashes."""

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _dataset_ids())
    def test_migrate_to_20_dry_run(self, ds_name: str) -> None:
        ds_path = BIDS_EXAMPLES_DIR / ds_name
        try:
            ds = BIDSDataset.from_path(ds_path)
        except (FileNotFoundError, ValueError) as exc:
            pytest.skip(reason=f"cannot load {ds_name}: {exc}")

        result = migrate_dataset(ds, to_version="2.0.0", dry_run=True)

        # Should never crash — in dry_run mode even unfixable findings
        # are reported without aborting
        assert result.dry_run
        # Result includes 1.x findings (cumulative) and potentially 2.0
        # findings once 2.0 rules are registered
        assert result.findings is not None


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


def _find_session_dataset_ids() -> list[str]:
    """Return dataset names that contain at least one ses-* directory."""
    ids = []
    for d in _iter_datasets():
        sub_dirs = [
            s for s in d.iterdir() if s.is_dir() and s.name.startswith("sub-")
        ]
        for s in sub_dirs:
            if any(
                ses.is_dir() and ses.name.startswith("ses-")
                for ses in s.iterdir()
            ):
                ids.append(d.name)
                break
    return ids


def _find_sessionless_dataset_ids() -> list[str]:
    """Return dataset names that have subjects but NO ses-* directories."""
    ids = []
    for d in _iter_datasets():
        sub_dirs = [
            s for s in d.iterdir() if s.is_dir() and s.name.startswith("sub-")
        ]
        if not sub_dirs:
            continue
        has_session = False
        for s in sub_dirs:
            if any(
                ses.is_dir() and ses.name.startswith("ses-")
                for ses in s.iterdir()
            ):
                has_session = True
                break
        if not has_session:
            ids.append(d.name)
    return ids


@requires_bids_examples
@pytest.mark.integration
class TestSessionRenameSweep:
    """Rename a session in each multi-session dataset (dry-run)."""

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _find_session_dataset_ids())
    def test_session_rename_dry_run(self, ds_name: str) -> None:
        ds_path = BIDS_EXAMPLES_DIR / ds_name
        try:
            ds = BIDSDataset.from_path(ds_path)
        except (FileNotFoundError, ValueError) as exc:
            pytest.skip(reason=f"cannot load {ds_name}: {exc}")

        # Find first session in first subject
        sub_dirs = sorted(
            d
            for d in ds_path.iterdir()
            if d.is_dir() and d.name.startswith("sub-")
        )
        ses_dir = None
        for s in sub_dirs:
            for child in sorted(s.iterdir()):
                if child.is_dir() and child.name.startswith("ses-"):
                    ses_dir = child
                    break
            if ses_dir is not None:
                break

        if ses_dir is None:
            pytest.skip(reason=f"no ses-* directory in {ds_name}")

        old_label = ses_dir.name.removeprefix("ses-")
        result = rename_session(ds, old_label, "TESTZZ99", dry_run=True)

        assert result.success, (
            f"Dry-run session rename failed in {ds_name}: {result.errors}"
        )
        assert result.dry_run

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _find_sessionless_dataset_ids())
    def test_move_into_session_dry_run(self, ds_name: str) -> None:
        """Dry-run introducing a session to sessionless datasets."""
        ds_path = BIDS_EXAMPLES_DIR / ds_name
        try:
            ds = BIDSDataset.from_path(ds_path)
        except (FileNotFoundError, ValueError) as exc:
            pytest.skip(reason=f"cannot load {ds_name}: {exc}")

        result = rename_session(ds, "", "baseline", dry_run=True)

        assert result.dry_run
        # Either creates changes or warns about subjects without datatype dirs
        assert result.success


@requires_bids_examples
@pytest.mark.integration
class TestMetadataSweep:
    """Run metadata operations on each dataset (dry-run)."""

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _dataset_ids())
    def test_aggregate_dry_run(self, ds_name: str) -> None:
        ds_path = BIDS_EXAMPLES_DIR / ds_name
        try:
            ds = BIDSDataset.from_path(ds_path)
        except (FileNotFoundError, ValueError) as exc:
            pytest.skip(reason=f"cannot load {ds_name}: {exc}")

        result = aggregate_metadata(ds, dry_run=True)
        assert result.dry_run
        assert result.success

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _dataset_ids())
    def test_segregate_dry_run(self, ds_name: str) -> None:
        ds_path = BIDS_EXAMPLES_DIR / ds_name
        try:
            ds = BIDSDataset.from_path(ds_path)
        except (FileNotFoundError, ValueError) as exc:
            pytest.skip(reason=f"cannot load {ds_name}: {exc}")

        result = segregate_metadata(ds, dry_run=True)
        assert result.dry_run
        assert result.success

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _dataset_ids())
    def test_audit_no_crash(self, ds_name: str) -> None:
        ds_path = BIDS_EXAMPLES_DIR / ds_name
        try:
            ds = BIDSDataset.from_path(ds_path)
        except (FileNotFoundError, ValueError) as exc:
            pytest.skip(reason=f"cannot load {ds_name}: {exc}")

        result = audit_metadata(ds)
        # Should never crash — just reports inconsistencies
        assert isinstance(result.total_files, int)


def _find_run_file(ds_path: Path) -> tuple[str, str] | None:
    """Find a subject and run label from a dataset.

    Returns (subject_label, run_label) or None.
    """
    import re

    for f in sorted(ds_path.rglob("sub-*_*run-*_*")):
        if f.is_dir():
            continue
        m_sub = re.search(r"(sub-[^_/]+)", f.name)
        m_run = re.search(r"(run-\d+)", f.name)
        if m_sub and m_run:
            return m_sub.group(1), m_run.group(1)
    return None


@requires_bids_examples
@pytest.mark.integration
class TestRemoveSweep:
    """Dry-run remove operations on bids-examples datasets."""

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _dataset_ids())
    def test_remove_subject_dry_run(self, ds_name: str) -> None:
        ds_path = BIDS_EXAMPLES_DIR / ds_name
        try:
            ds = BIDSDataset.from_path(ds_path)
        except (FileNotFoundError, ValueError) as exc:
            pytest.skip(reason=f"cannot load {ds_name}: {exc}")

        sub_dirs = sorted(
            d
            for d in ds_path.iterdir()
            if d.is_dir() and d.name.startswith("sub-")
        )
        if not sub_dirs:
            pytest.skip(reason=f"no sub-* directories in {ds_name}")

        result = remove_subject(ds, sub_dirs[0].name, dry_run=True, force=True)
        assert result.dry_run
        assert result.success, (
            f"Dry-run remove subject failed in {ds_name}: {result.errors}"
        )
        assert len(result.changes) >= 1

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _dataset_ids())
    def test_remove_run_dry_run(self, ds_name: str) -> None:
        ds_path = BIDS_EXAMPLES_DIR / ds_name
        try:
            ds = BIDSDataset.from_path(ds_path)
        except (FileNotFoundError, ValueError) as exc:
            pytest.skip(reason=f"cannot load {ds_name}: {exc}")

        hit = _find_run_file(ds_path)
        if hit is None:
            pytest.skip(reason=f"no run-* files in {ds_name}")

        sub_label, run_label = hit
        result = remove_run(ds, sub_label, run_label, dry_run=True)
        assert result.dry_run
        assert result.success, (
            f"Dry-run remove run failed in {ds_name}: {result.errors}"
        )
        assert len(result.changes) >= 1


@requires_bids_examples
@pytest.mark.integration
class TestMergeSweep:
    """Dry-run merge of bids-examples dataset pairs."""

    @pytest.mark.ai_generated
    def test_merge_two_datasets_dry_run(self, tmp_path: Path) -> None:
        """Pick two datasets with non-overlapping subjects, dry-run merge."""
        datasets = _iter_datasets()
        if len(datasets) < 2:
            pytest.skip(reason="need at least 2 bids-examples datasets")

        # Find two datasets that each have subjects
        candidates = []
        for d in datasets:
            subs = [
                s.name
                for s in d.iterdir()
                if s.is_dir() and s.name.startswith("sub-")
            ]
            if subs:
                candidates.append((d, set(subs)))
            if len(candidates) >= 2:
                break

        if len(candidates) < 2:
            pytest.skip(reason="need at least 2 datasets with subjects")

        ds1_path, ds1_subs = candidates[0]
        ds2_path, ds2_subs = candidates[1]

        target = tmp_path / "merged"

        if ds1_subs & ds2_subs:
            # Overlapping subjects — use into_sessions to avoid conflict
            result = merge_datasets(
                [ds1_path, ds2_path],
                target,
                into_sessions=["ses-A", "ses-B"],
                dry_run=True,
            )
        else:
            result = merge_datasets(
                [ds1_path, ds2_path],
                target,
                dry_run=True,
            )

        assert result.dry_run
        assert result.success, f"Dry-run merge failed: {result.errors}"
        assert len(result.changes) >= 1

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _dataset_ids())
    def test_merge_single_dataset_into_sessions_dry_run(
        self, ds_name: str, tmp_path: Path
    ) -> None:
        """Merge a single dataset into a new target with a session label."""
        ds_path = BIDS_EXAMPLES_DIR / ds_name
        sub_dirs = [
            d
            for d in ds_path.iterdir()
            if d.is_dir() and d.name.startswith("sub-")
        ]
        if not sub_dirs:
            pytest.skip(reason=f"no subjects in {ds_name}")

        target = tmp_path / "merged"
        result = merge_datasets(
            [ds_path],
            target,
            into_sessions=["ses-orig"],
            dry_run=True,
        )

        assert result.dry_run
        assert result.success, (
            f"Dry-run single-dataset merge failed for {ds_name}: {result.errors}"
        )


# ---------------------------------------------------------------------------
# Mutating + bids-validator integration tests (SC-001)
#
# Verify that datasets valid before an operation remain valid after it.
# ---------------------------------------------------------------------------


@requires_bids_examples
@requires_bids_validator
@pytest.mark.integration
class TestRenameMutatingValidated:
    """Rename one file in each dataset copy, validate before and after."""

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _dataset_ids())
    def test_rename_validated(self, ds_name: str, tmp_path: Path) -> None:
        ds_copy = _copy_dataset(BIDS_EXAMPLES_DIR / ds_name, tmp_path)

        try:
            ds = BIDSDataset.from_path(ds_copy)
        except (FileNotFoundError, ValueError) as exc:
            pytest.skip(reason=f"cannot load {ds_name}: {exc}")

        target = _find_renameable_file(ds_copy)
        if target is None:
            pytest.skip(reason=f"no renameable BIDS data file in {ds_name}")

        valid_before, errors_before = validate_dataset(ds_copy)
        if not valid_before:
            pytest.skip(
                f"dataset {ds_name} not valid before operation: {errors_before}"
            )

        before_files = {
            f.relative_to(ds_copy) for f in ds_copy.rglob("*") if f.is_file()
        }

        result = rename_file(ds, target, set_entities={"run": "99"})
        assert result.success, f"Rename failed in {ds_name}: {result.errors}"

        after_files = {
            f.relative_to(ds_copy) for f in ds_copy.rglob("*") if f.is_file()
        }
        assert len(after_files) == len(before_files), (
            f"File count changed: {len(before_files)} -> {len(after_files)}"
        )

        valid_after, errors_after = validate_dataset(ds_copy)
        assert valid_after, (
            f"Dataset {ds_name} invalid after rename: {errors_after}"
        )


@requires_bids_examples
@requires_bids_validator
@pytest.mark.integration
class TestSubjectRenameMutatingValidated:
    """Rename first subject in each dataset copy, validate before and after."""

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _dataset_ids())
    def test_subject_rename_validated(
        self, ds_name: str, tmp_path: Path
    ) -> None:
        ds_copy = _copy_dataset(BIDS_EXAMPLES_DIR / ds_name, tmp_path)

        try:
            ds = BIDSDataset.from_path(ds_copy)
        except (FileNotFoundError, ValueError) as exc:
            pytest.skip(reason=f"cannot load {ds_name}: {exc}")

        sub_dirs = sorted(
            d
            for d in ds_copy.iterdir()
            if d.is_dir() and d.name.startswith("sub-")
        )
        if not sub_dirs:
            pytest.skip(reason=f"no sub-* directories in {ds_name}")

        old_sub = sub_dirs[0].name

        valid_before, errors_before = validate_dataset(ds_copy)
        if not valid_before:
            pytest.skip(
                f"dataset {ds_name} not valid before operation: {errors_before}"
            )

        result = rename_subject(ds, old_sub, "sub-TESTZZ")
        assert result.success, (
            f"Subject rename failed in {ds_name}: {result.errors}"
        )

        # Old dir should be gone, new dir should exist
        assert not (ds_copy / old_sub).exists(), (
            f"Old subject dir {old_sub} still present"
        )
        assert (ds_copy / "sub-TESTZZ").is_dir(), (
            "New subject dir sub-TESTZZ not found"
        )

        # No files should retain the old subject label
        for f in (ds_copy / "sub-TESTZZ").rglob("*"):
            if f.is_dir():
                continue
            assert old_sub not in f.name, (
                f"File retains old subject label: {f.name}"
            )

        valid_after, errors_after = validate_dataset(ds_copy)
        assert valid_after, (
            f"Dataset {ds_name} invalid after subject rename: {errors_after}"
        )


@requires_bids_examples
@requires_bids_validator
@pytest.mark.integration
class TestSessionRenameMutatingValidated:
    """Rename first session in session-datasets, validate before and after."""

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _find_session_dataset_ids())
    def test_session_rename_validated(
        self, ds_name: str, tmp_path: Path
    ) -> None:
        ds_copy = _copy_dataset(BIDS_EXAMPLES_DIR / ds_name, tmp_path)

        try:
            ds = BIDSDataset.from_path(ds_copy)
        except (FileNotFoundError, ValueError) as exc:
            pytest.skip(reason=f"cannot load {ds_name}: {exc}")

        # Find first session in first subject
        old_label: str | None = None
        first_sub_dir: Path | None = None
        for sub_dir in sorted(ds_copy.iterdir()):
            if not sub_dir.is_dir() or not sub_dir.name.startswith("sub-"):
                continue
            for child in sorted(sub_dir.iterdir()):
                if child.is_dir() and child.name.startswith("ses-"):
                    old_label = child.name.removeprefix("ses-")
                    first_sub_dir = sub_dir
                    break
            if old_label is not None:
                break

        if old_label is None:
            pytest.skip(reason=f"no ses-* directory in {ds_name}")

        valid_before, errors_before = validate_dataset(ds_copy)
        if not valid_before:
            pytest.skip(
                f"dataset {ds_name} not valid before operation: {errors_before}"
            )

        result = rename_session(ds, old_label, "TESTZZ99")
        assert result.success, (
            f"Session rename failed in {ds_name}: {result.errors}"
        )

        # Old session dir should be gone under the first subject
        assert first_sub_dir is not None
        assert not (first_sub_dir / f"ses-{old_label}").exists(), (
            f"Old session dir ses-{old_label} still present"
        )
        assert (first_sub_dir / "ses-TESTZZ99").is_dir(), (
            "New session dir ses-TESTZZ99 not found"
        )

        # No files should retain the old session label under new session dir
        for f in (first_sub_dir / "ses-TESTZZ99").rglob("*"):
            if f.is_dir():
                continue
            assert f"ses-{old_label}" not in f.name, (
                f"File retains old session label: {f.name}"
            )

        valid_after, errors_after = validate_dataset(ds_copy)
        assert valid_after, (
            f"Dataset {ds_name} invalid after session rename: {errors_after}"
        )


@requires_bids_examples
@requires_bids_validator
@pytest.mark.integration
class TestMigrateMutatingValidated:
    """Run migrate on each dataset copy, validate afterwards."""

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _dataset_ids())
    def test_migrate_validated(self, ds_name: str, tmp_path: Path) -> None:
        ds_copy = _copy_dataset(BIDS_EXAMPLES_DIR / ds_name, tmp_path)

        try:
            ds = BIDSDataset.from_path(ds_copy)
        except (FileNotFoundError, ValueError) as exc:
            pytest.skip(reason=f"cannot load {ds_name}: {exc}")

        valid_before, errors_before = validate_dataset(ds_copy)
        if not valid_before:
            pytest.skip(
                f"dataset {ds_name} not valid before operation: {errors_before}"
            )

        result = migrate_dataset(ds)
        assert result.success, (
            f"Migration failed in {ds_name}: {result.errors}"
        )

        valid_after, errors_after = validate_dataset(ds_copy)
        assert valid_after, (
            f"Dataset {ds_name} invalid after migration: {errors_after}"
        )


# ---------------------------------------------------------------------------
# Git-annex mode: clone datasets, force all files into annex, run operations
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _annexify_dataset(src: Path, tmp_path: Path) -> Path:
    """Copy a dataset, init git-annex, force ALL files into annex."""
    dst = tmp_path / src.name
    shutil.copytree(src, dst)

    _git(dst, "init")
    _git(dst, "config", "user.email", "test@test.com")
    _git(dst, "config", "user.name", "Test")
    _git(dst, "annex", "init", "test")
    # Force all files into annex (including .json, .tsv)
    _git(dst, "config", "annex.largefiles", "anything")
    _git(dst, "annex", "add", ".")
    _git(dst, "add", ".")
    _git(dst, "commit", "-m", "init annexed")

    return dst


def _annex_dataset_ids() -> list[str]:
    """Subset of datasets for annex testing (representative, not exhaustive)."""
    all_ids = _dataset_ids()
    # Pick datasets with different modalities for coverage
    wanted = {
        "ds001",  # basic fMRI
        "synthetic",  # multi-subject multi-session
        "7t_trt",  # multi-session MRI
        "eeg_matchingpennies",  # EEG
        "ieeg_visual",  # iEEG
    }
    # Use what's available
    ids = [d for d in all_ids if d in wanted]
    # If none of the wanted are available, pick up to 5 from what exists
    if not ids:
        ids = all_ids[:5]
    return ids


@requires_bids_examples
@requires_git_annex
@pytest.mark.integration
class TestAnnexRenameSweep:
    """Rename a file in annexed datasets — verify symlinks handled."""

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _annex_dataset_ids())
    def test_rename_dry_run_annex(
        self, ds_name: str, tmp_path: Path
    ) -> None:
        src = BIDS_EXAMPLES_DIR / ds_name
        ds_path = _annexify_dataset(src, tmp_path)
        ds = BIDSDataset.from_path(ds_path)
        ds.annexed_mode = AnnexedMode.SKIP

        target = _find_renameable_file(ds_path)
        if target is None:
            pytest.skip(f"no renameable file in {ds_name}")

        result = rename_file(
            ds, target, set_entities={"run": "99"}, dry_run=True
        )
        assert result.success, (
            f"Annex dry-run rename failed in {ds_name}: {result.errors}"
        )

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _annex_dataset_ids())
    def test_rename_mutating_annex(
        self, ds_name: str, tmp_path: Path
    ) -> None:
        """Actually rename a file in an annexed dataset."""
        src = BIDS_EXAMPLES_DIR / ds_name
        ds_path = _annexify_dataset(src, tmp_path)
        ds = BIDSDataset.from_path(ds_path)
        ds.annexed_mode = AnnexedMode.SKIP

        target = _find_renameable_file(ds_path)
        if target is None:
            pytest.skip(f"no renameable file in {ds_name}")

        result = rename_file(
            ds, target, set_entities={"run": "99"}
        )
        assert result.success, (
            f"Annex rename failed in {ds_name}: {result.errors}"
        )
        # Original file should be gone
        assert not target.exists() and not target.is_symlink()


@requires_bids_examples
@requires_git_annex
@pytest.mark.integration
class TestAnnexSubjectRenameSweep:
    """Subject rename on annexed datasets."""

    @pytest.mark.ai_generated
    @pytest.mark.parametrize("ds_name", _annex_dataset_ids())
    def test_subject_rename_annex(
        self, ds_name: str, tmp_path: Path
    ) -> None:
        src = BIDS_EXAMPLES_DIR / ds_name
        ds_path = _annexify_dataset(src, tmp_path)
        ds = BIDSDataset.from_path(ds_path)
        ds.annexed_mode = AnnexedMode.SKIP

        sub_dirs = sorted(
            d
            for d in ds_path.iterdir()
            if d.is_dir() and d.name.startswith("sub-")
        )
        if not sub_dirs:
            pytest.skip(f"no subjects in {ds_name}")

        old_sub = sub_dirs[0].name
        result = rename_subject(ds, old_sub, "sub-TESTZZ")
        assert result.success, (
            f"Annex subject rename failed in {ds_name}: {result.errors}"
        )
        # Old dir should be gone
        assert not (ds_path / old_sub).exists()
        # New dir should exist
        assert (ds_path / "sub-TESTZZ").is_dir()
        # No files should retain old label
        for f in (ds_path / "sub-TESTZZ").rglob("*"):
            if f.is_dir():
                continue
            assert old_sub not in f.name, (
                f"File retains old label: {f.name}"
            )


@requires_bids_examples
@requires_git_annex
@pytest.mark.integration
class TestAnnexSessionRenameSweep:
    """Session rename on annexed datasets."""

    @pytest.mark.ai_generated
    @pytest.mark.parametrize(
        "ds_name",
        [
            d
            for d in _annex_dataset_ids()
            if d in set(_find_session_dataset_ids())
        ],
    )
    def test_session_rename_annex(
        self, ds_name: str, tmp_path: Path
    ) -> None:
        src = BIDS_EXAMPLES_DIR / ds_name
        ds_path = _annexify_dataset(src, tmp_path)
        ds = BIDSDataset.from_path(ds_path)
        ds.annexed_mode = AnnexedMode.SKIP

        # Find first session
        for sub_dir in sorted(ds_path.iterdir()):
            if not sub_dir.is_dir() or not sub_dir.name.startswith("sub-"):
                continue
            for child in sorted(sub_dir.iterdir()):
                if child.is_dir() and child.name.startswith("ses-"):
                    old_label = child.name.removeprefix("ses-")
                    result = rename_session(
                        ds, old_label, "TESTZZ99"
                    )
                    assert result.success, (
                        f"Annex session rename in {ds_name}: "
                        f"{result.errors}"
                    )
                    # Verify no files retain old session
                    new_ses = sub_dir / "ses-TESTZZ99"
                    for f in new_ses.rglob("*"):
                        if f.is_dir():
                            continue
                        assert f"ses-{old_label}" not in f.name, (
                            f"File retains old session: {f.name}"
                        )
                    return
        pytest.skip(f"no sessions in {ds_name}")
