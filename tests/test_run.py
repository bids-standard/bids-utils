"""Tests for run.py — run removal with reindexing."""

import json
from pathlib import Path

import pytest

from bids_utils._dataset import BIDSDataset
from bids_utils.run import remove_run


def _make_run_dataset(tmp_path: Path) -> Path:
    """Create a dataset with multiple runs."""
    ds = tmp_path / "dataset"
    ds.mkdir()
    (ds / "dataset_description.json").write_text(
        json.dumps({"Name": "Test", "BIDSVersion": "1.9.0", "DatasetType": "raw"})
    )
    (ds / "participants.tsv").write_text("participant_id\nsub-01\n")

    func = ds / "sub-01" / "func"
    func.mkdir(parents=True)

    scans_entries = []
    for run in ["01", "02", "03"]:
        for ext in [".nii.gz", ".json"]:
            f = func / f"sub-01_task-rest_run-{run}_bold{ext}"
            if ext == ".json":
                f.write_text(json.dumps({"TaskName": "rest"}))
            else:
                f.write_bytes(b"")
        scans_entries.append(f"func/sub-01_task-rest_run-{run}_bold.nii.gz\t2020-01-01T12:00:00")

    scans = ds / "sub-01" / "sub-01_scans.tsv"
    scans.write_text("filename\tacq_time\n" + "\n".join(scans_entries) + "\n")

    return ds


class TestRemoveRun:
    @pytest.mark.ai_generated
    def test_remove_and_shift(self, tmp_path: Path) -> None:
        ds_path = _make_run_dataset(tmp_path)
        ds = BIDSDataset.from_path(ds_path)

        result = remove_run(ds, "01", "02", shift=True)

        assert result.success
        func = ds_path / "sub-01" / "func"
        # run-01 should still exist
        assert (func / "sub-01_task-rest_run-01_bold.nii.gz").exists()
        # run-03 should be shifted to run-02
        assert (func / "sub-01_task-rest_run-02_bold.nii.gz").exists()
        # run-03 should no longer exist (was shifted to run-02)
        assert not (func / "sub-01_task-rest_run-03_bold.nii.gz").exists()

    @pytest.mark.ai_generated
    def test_remove_no_shift(self, tmp_path: Path) -> None:
        ds_path = _make_run_dataset(tmp_path)
        ds = BIDSDataset.from_path(ds_path)

        result = remove_run(ds, "01", "02", shift=False)

        assert result.success
        func = ds_path / "sub-01" / "func"
        # run-02 files removed
        assert not (func / "sub-01_task-rest_run-02_bold.nii.gz").exists()
        # run-03 should stay as run-03
        assert (func / "sub-01_task-rest_run-03_bold.nii.gz").exists()

    @pytest.mark.ai_generated
    def test_remove_dry_run(self, tmp_path: Path) -> None:
        ds_path = _make_run_dataset(tmp_path)
        ds = BIDSDataset.from_path(ds_path)

        result = remove_run(ds, "01", "02", dry_run=True)

        assert result.dry_run
        func = ds_path / "sub-01" / "func"
        # Files should still exist
        assert (func / "sub-01_task-rest_run-02_bold.nii.gz").exists()

    @pytest.mark.ai_generated
    def test_remove_missing_run(self, tmp_path: Path) -> None:
        ds_path = _make_run_dataset(tmp_path)
        ds = BIDSDataset.from_path(ds_path)

        result = remove_run(ds, "01", "05")

        assert not result.success
