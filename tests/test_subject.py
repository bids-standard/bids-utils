"""Tests for subject.py — subject rename and remove."""

from pathlib import Path

import pytest

from bids_utils._dataset import BIDSDataset
from bids_utils._participants import read_participants_tsv
from bids_utils.subject import remove_subject, rename_subject


class TestRenameSubject:
    @pytest.mark.ai_generated
    def test_rename(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        result = rename_subject(ds, "01", "99")

        assert result.success
        assert not (tmp_bids_dataset / "sub-01").exists()
        assert (tmp_bids_dataset / "sub-99").is_dir()

    @pytest.mark.ai_generated
    def test_rename_files(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        rename_subject(ds, "01", "99")

        # Check files are renamed
        bold = tmp_bids_dataset / "sub-99" / "func" / "sub-99_task-rest_bold.nii.gz"
        assert bold.exists()
        old_bold = tmp_bids_dataset / "sub-99" / "func" / "sub-01_task-rest_bold.nii.gz"
        assert not old_bold.exists()

    @pytest.mark.ai_generated
    def test_rename_updates_participants(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        rename_subject(ds, "01", "99")

        rows = read_participants_tsv(tmp_bids_dataset / "participants.tsv")
        ids = [r["participant_id"] for r in rows]
        assert "sub-99" in ids
        assert "sub-01" not in ids

    @pytest.mark.ai_generated
    def test_rename_target_exists(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        result = rename_subject(ds, "01", "02")

        assert not result.success
        assert any("already exists" in e for e in result.errors)

    @pytest.mark.ai_generated
    def test_rename_source_missing(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        result = rename_subject(ds, "99", "100")

        assert not result.success
        assert any("not found" in e.lower() for e in result.errors)

    @pytest.mark.ai_generated
    def test_rename_dry_run(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        result = rename_subject(ds, "01", "99", dry_run=True)

        assert result.success
        assert result.dry_run
        assert (tmp_bids_dataset / "sub-01").exists()  # unchanged
        assert not (tmp_bids_dataset / "sub-99").exists()

    @pytest.mark.ai_generated
    def test_rename_with_session(self, tmp_bids_dataset_with_sessions: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset_with_sessions)
        result = rename_subject(ds, "01", "99")

        assert result.success
        assert (tmp_bids_dataset_with_sessions / "sub-99" / "ses-pre").is_dir()
        bold = (
            tmp_bids_dataset_with_sessions
            / "sub-99"
            / "ses-pre"
            / "func"
            / "sub-99_ses-pre_task-rest_bold.nii.gz"
        )
        assert bold.exists()


class TestRemoveSubject:
    @pytest.mark.ai_generated
    def test_remove(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        result = remove_subject(ds, "01", force=True)

        assert result.success
        assert not (tmp_bids_dataset / "sub-01").exists()

    @pytest.mark.ai_generated
    def test_remove_updates_participants(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        remove_subject(ds, "01", force=True)

        rows = read_participants_tsv(tmp_bids_dataset / "participants.tsv")
        ids = [r["participant_id"] for r in rows]
        assert "sub-01" not in ids

    @pytest.mark.ai_generated
    def test_remove_missing(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        result = remove_subject(ds, "99")

        assert not result.success

    @pytest.mark.ai_generated
    def test_remove_dry_run(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        result = remove_subject(ds, "01", dry_run=True)

        assert result.dry_run
        assert (tmp_bids_dataset / "sub-01").exists()  # unchanged
