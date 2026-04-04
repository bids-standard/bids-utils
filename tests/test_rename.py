"""Tests for rename.py — file rename with sidecars and scans."""

from pathlib import Path

import pytest

from bids_utils._dataset import BIDSDataset
from bids_utils._scans import read_scans_tsv
from bids_utils.rename import rename_file


class TestRenameFile:
    @pytest.mark.ai_generated
    def test_rename_with_entity_override(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        bold = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz"

        result = rename_file(ds, bold, set_entities={"task": "nback"})

        assert result.success
        assert not result.dry_run
        assert not bold.exists()
        new_bold = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-nback_bold.nii.gz"
        assert new_bold.exists()

    @pytest.mark.ai_generated
    def test_rename_sidecars(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        bold = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz"

        result = rename_file(ds, bold, set_entities={"task": "nback"})

        assert result.success
        # JSON sidecar should also be renamed
        new_json = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-nback_bold.json"
        assert new_json.exists()
        old_json = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-rest_bold.json"
        assert not old_json.exists()

    @pytest.mark.ai_generated
    def test_rename_updates_scans_tsv(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        bold = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz"

        rename_file(ds, bold, set_entities={"task": "nback"})

        scans = tmp_bids_dataset / "sub-01" / "sub-01_scans.tsv"
        rows = read_scans_tsv(scans)
        filenames = [r["filename"] for r in rows]
        assert "func/sub-01_task-nback_bold.nii.gz" in filenames
        assert "func/sub-01_task-rest_bold.nii.gz" not in filenames

    @pytest.mark.ai_generated
    def test_rename_dry_run(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        bold = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz"

        result = rename_file(ds, bold, set_entities={"task": "nback"}, dry_run=True)

        assert result.success
        assert result.dry_run
        assert len(result.changes) > 0
        # File should NOT be renamed
        assert bold.exists()

    @pytest.mark.ai_generated
    def test_rename_conflict(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        bold = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz"
        # Create a conflicting target
        target = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-nback_bold.nii.gz"
        target.write_bytes(b"conflict")

        result = rename_file(ds, bold, set_entities={"task": "nback"})

        assert not result.success
        assert any("already exists" in e for e in result.errors)

    @pytest.mark.ai_generated
    def test_rename_file_not_found(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)

        result = rename_file(ds, "nonexistent.nii.gz")

        assert not result.success
        assert any("not found" in e.lower() for e in result.errors)

    @pytest.mark.ai_generated
    def test_rename_noop(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        bold = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz"

        # No changes → no-op
        result = rename_file(ds, bold, set_entities={"task": "rest"})

        assert result.success
        assert any("same" in w.lower() for w in result.warnings)

    @pytest.mark.ai_generated
    def test_rename_with_suffix(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        t1w = tmp_bids_dataset / "sub-01" / "anat" / "sub-01_T1w.nii.gz"

        result = rename_file(ds, t1w, new_suffix="T2w")

        assert result.success
        new = tmp_bids_dataset / "sub-01" / "anat" / "sub-01_T2w.nii.gz"
        assert new.exists()
        assert not t1w.exists()

    @pytest.mark.ai_generated
    def test_rename_multiple_changes(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        bold = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz"

        result = rename_file(ds, bold, set_entities={"task": "nback"})

        # Should have at least 2 changes: .nii.gz + .json rename
        rename_changes = [c for c in result.changes if c.action == "rename"]
        assert len(rename_changes) >= 2

    @pytest.mark.ai_generated
    def test_rename_with_session(self, tmp_bids_dataset_with_sessions: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset_with_sessions)
        bold = (
            tmp_bids_dataset_with_sessions
            / "sub-01"
            / "ses-pre"
            / "func"
            / "sub-01_ses-pre_task-rest_bold.nii.gz"
        )

        result = rename_file(ds, bold, set_entities={"task": "nback"})

        assert result.success
        new = (
            tmp_bids_dataset_with_sessions
            / "sub-01"
            / "ses-pre"
            / "func"
            / "sub-01_ses-pre_task-nback_bold.nii.gz"
        )
        assert new.exists()
