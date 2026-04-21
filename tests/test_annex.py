"""Regression tests for operations on git-annex datasets (SC-008).

These tests verify that annexed files (symlinks into .git/annex/objects)
are correctly handled by rename, session-rename, and subject-rename.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import requires_git_annex


@requires_git_annex
class TestSessionRenameAnnex:
    @pytest.mark.ai_generated
    def test_all_files_renamed(self, tmp_annex_dataset: Path) -> None:
        """Session rename must rename ALL files including annexed symlinks."""
        from bids_utils._dataset import BIDSDataset
        from bids_utils.session import rename_session

        ds = BIDSDataset.from_path(tmp_annex_dataset)
        result = rename_session(ds, "pre", "baseline")
        assert result.success, result.errors

        ses_dir = tmp_annex_dataset / "sub-01" / "ses-baseline"
        assert ses_dir.is_dir()

        # ALL files under the renamed session must have the new label
        old_label = "ses-pre"
        for f in ses_dir.rglob("*"):
            if f.is_dir():
                continue
            assert old_label not in f.name, (
                f"File still has old session label: {f.name}"
            )

    @pytest.mark.ai_generated
    def test_nii_gz_symlinks_renamed(
        self, tmp_annex_dataset: Path
    ) -> None:
        """Annexed .nii.gz files (symlinks) must be renamed."""
        from bids_utils._dataset import BIDSDataset
        from bids_utils.session import rename_session

        ds = BIDSDataset.from_path(tmp_annex_dataset)
        result = rename_session(ds, "pre", "baseline")
        assert result.success, result.errors

        func = tmp_annex_dataset / "sub-01" / "ses-baseline" / "func"
        bold = func / "sub-01_ses-baseline_task-rest_bold.nii.gz"
        # The file should exist (symlink or regular)
        assert bold.exists() or bold.is_symlink(), (
            f"Expected {bold.name} to exist after rename"
        )
        # Old name must NOT exist
        old_bold = func / "sub-01_ses-pre_task-rest_bold.nii.gz"
        assert not old_bold.exists() and not old_bold.is_symlink()

    @pytest.mark.ai_generated
    def test_json_sidecars_renamed(self, tmp_annex_dataset: Path) -> None:
        """Regular git files (.json) must also be renamed."""
        from bids_utils._dataset import BIDSDataset
        from bids_utils.session import rename_session

        ds = BIDSDataset.from_path(tmp_annex_dataset)
        result = rename_session(ds, "post", "followup")
        assert result.success, result.errors

        func = tmp_annex_dataset / "sub-01" / "ses-followup" / "func"
        bold_json = func / "sub-01_ses-followup_task-rest_bold.json"
        assert bold_json.is_file()


@requires_git_annex
class TestSubjectRenameAnnex:
    @pytest.mark.ai_generated
    def test_all_files_renamed(self, tmp_annex_dataset: Path) -> None:
        """Subject rename must rename ALL files including annexed symlinks."""
        from bids_utils._dataset import BIDSDataset
        from bids_utils.subject import rename_subject

        ds = BIDSDataset.from_path(tmp_annex_dataset)
        result = rename_subject(ds, "01", "99")
        assert result.success, result.errors

        sub_dir = tmp_annex_dataset / "sub-99"
        assert sub_dir.is_dir()

        old_label = "sub-01"
        for f in sub_dir.rglob("*"):
            if f.is_dir():
                continue
            assert old_label not in f.name, (
                f"File still has old subject label: {f.name}"
            )

    @pytest.mark.ai_generated
    def test_annexed_nii_gz_renamed(
        self, tmp_annex_dataset: Path
    ) -> None:
        """Annexed .nii.gz must be renamed during subject rename."""
        from bids_utils._dataset import BIDSDataset
        from bids_utils.subject import rename_subject

        ds = BIDSDataset.from_path(tmp_annex_dataset)
        rename_subject(ds, "01", "99")

        bold = (
            tmp_annex_dataset
            / "sub-99"
            / "ses-pre"
            / "func"
            / "sub-99_ses-pre_task-rest_bold.nii.gz"
        )
        assert bold.exists() or bold.is_symlink()


@requires_git_annex
class TestFileRenameAnnex:
    @pytest.mark.ai_generated
    def test_rename_annexed_file(self, tmp_annex_dataset: Path) -> None:
        """Renaming an annexed file itself should work."""
        from bids_utils._dataset import BIDSDataset
        from bids_utils.rename import rename_file

        ds = BIDSDataset.from_path(tmp_annex_dataset)
        bold = (
            tmp_annex_dataset
            / "sub-01"
            / "ses-pre"
            / "func"
            / "sub-01_ses-pre_task-rest_bold.nii.gz"
        )
        result = rename_file(ds, bold, set_entities={"task": "nback"})
        assert result.success, result.errors

        new_bold = bold.parent / "sub-01_ses-pre_task-nback_bold.nii.gz"
        assert new_bold.exists() or new_bold.is_symlink()
        assert not bold.exists() and not bold.is_symlink()

    @pytest.mark.ai_generated
    def test_rename_updates_scans_tsv(
        self, tmp_annex_dataset: Path
    ) -> None:
        """Renaming a file must update _scans.tsv even when it's annexed."""
        from bids_utils._dataset import BIDSDataset
        from bids_utils._scans import read_scans_tsv
        from bids_utils._types import AnnexedMode
        from bids_utils.rename import rename_file

        ds = BIDSDataset.from_path(tmp_annex_dataset)
        ds.annexed_mode = AnnexedMode.GET  # need content to read scans
        bold = (
            tmp_annex_dataset
            / "sub-01"
            / "ses-pre"
            / "func"
            / "sub-01_ses-pre_task-rest_bold.nii.gz"
        )
        result = rename_file(ds, bold, set_entities={"task": "nback"})
        assert result.success, result.errors

        # Check _scans.tsv was updated
        scans = (
            tmp_annex_dataset
            / "sub-01"
            / "ses-pre"
            / "sub-01_ses-pre_scans.tsv"
        )
        rows = read_scans_tsv(scans)
        filenames = [r.get("filename", "") for r in rows]
        assert any("task-nback" in fn for fn in filenames), (
            f"_scans.tsv not updated: {filenames}"
        )
        assert not any("task-rest_bold" in fn for fn in filenames), (
            f"Old filename still in _scans.tsv: {filenames}"
        )

        new_bold = bold.parent / "sub-01_ses-pre_task-nback_bold.nii.gz"
        assert new_bold.exists() or new_bold.is_symlink()
        assert not bold.exists() and not bold.is_symlink()
