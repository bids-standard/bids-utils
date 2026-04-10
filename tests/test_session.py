"""Tests for session.py — session rename and move-into-session."""

from pathlib import Path

import pytest

from bids_utils._dataset import BIDSDataset
from bids_utils.session import rename_session


class TestRenameSession:
    @pytest.mark.ai_generated
    def test_rename(self, tmp_bids_dataset_with_sessions: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset_with_sessions)
        result = rename_session(ds, "pre", "baseline")

        assert result.success
        assert not (tmp_bids_dataset_with_sessions / "sub-01" / "ses-pre").exists()
        assert (tmp_bids_dataset_with_sessions / "sub-01" / "ses-baseline").is_dir()

    @pytest.mark.ai_generated
    def test_rename_files(self, tmp_bids_dataset_with_sessions: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset_with_sessions)
        rename_session(ds, "pre", "baseline")

        bold = (
            tmp_bids_dataset_with_sessions
            / "sub-01"
            / "ses-baseline"
            / "func"
            / "sub-01_ses-baseline_task-rest_bold.nii.gz"
        )
        assert bold.exists()

    @pytest.mark.ai_generated
    def test_rename_all_subjects(self, tmp_bids_dataset_with_sessions: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset_with_sessions)
        rename_session(ds, "pre", "baseline")

        # Both subjects should be affected
        assert (tmp_bids_dataset_with_sessions / "sub-01" / "ses-baseline").is_dir()
        assert (tmp_bids_dataset_with_sessions / "sub-02" / "ses-baseline").is_dir()

    @pytest.mark.ai_generated
    def test_rename_single_subject(self, tmp_bids_dataset_with_sessions: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset_with_sessions)
        rename_session(ds, "pre", "baseline", subject="01")

        assert (tmp_bids_dataset_with_sessions / "sub-01" / "ses-baseline").is_dir()
        # sub-02 should be unchanged
        assert (tmp_bids_dataset_with_sessions / "sub-02" / "ses-pre").is_dir()

    @pytest.mark.ai_generated
    def test_rename_target_exists(self, tmp_bids_dataset_with_sessions: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset_with_sessions)
        result = rename_session(ds, "pre", "post")

        assert not result.success
        assert any("already exists" in e for e in result.errors)

    @pytest.mark.ai_generated
    def test_rename_dry_run(self, tmp_bids_dataset_with_sessions: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset_with_sessions)
        result = rename_session(ds, "pre", "baseline", dry_run=True)

        assert result.dry_run
        assert (tmp_bids_dataset_with_sessions / "sub-01" / "ses-pre").exists()


class TestMoveIntoSession:
    @pytest.mark.ai_generated
    def test_move_into_session(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        result = rename_session(ds, "", "01")

        assert result.success
        # Session dir should be created
        ses_dir = tmp_bids_dataset / "sub-01" / "ses-01"
        assert ses_dir.is_dir()
        # Files should include session entity
        bold = ses_dir / "func" / "sub-01_ses-01_task-rest_bold.nii.gz"
        assert bold.exists()

    @pytest.mark.ai_generated
    def test_move_into_session_scans(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        rename_session(ds, "", "01")

        # scans.tsv should be moved and renamed
        new_scans = tmp_bids_dataset / "sub-01" / "ses-01" / "sub-01_ses-01_scans.tsv"
        assert new_scans.exists()

    @pytest.mark.ai_generated
    def test_move_into_session_dry_run(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        result = rename_session(ds, "", "01", dry_run=True)

        assert result.dry_run
        assert not (tmp_bids_dataset / "sub-01" / "ses-01").exists()
