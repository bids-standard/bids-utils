"""Tests for _scans.py — _scans.tsv operations."""

from pathlib import Path

import pytest

from bids_utils._scans import (
    find_scans_tsv,
    read_scans_tsv,
    remove_scans_entry,
    update_scans_entry,
    write_scans_tsv,
)


class TestScansReadWrite:
    @pytest.mark.ai_generated
    def test_roundtrip(self, tmp_path: Path) -> None:
        scans = tmp_path / "sub-01_scans.tsv"
        rows = [
            {"filename": "func/sub-01_task-rest_bold.nii.gz", "acq_time": "2020-01-01T12:00:00"},
            {"filename": "anat/sub-01_T1w.nii.gz", "acq_time": "2020-01-01T11:00:00"},
        ]
        write_scans_tsv(scans, rows)
        read_back = read_scans_tsv(scans)
        assert read_back == rows

    @pytest.mark.ai_generated
    def test_read_from_fixture(self, tmp_bids_dataset: Path) -> None:
        scans = tmp_bids_dataset / "sub-01" / "sub-01_scans.tsv"
        rows = read_scans_tsv(scans)
        assert len(rows) == 2
        assert rows[0]["filename"].endswith("bold.nii.gz")


class TestUpdateScansEntry:
    @pytest.mark.ai_generated
    def test_update(self, tmp_bids_dataset: Path) -> None:
        scans = tmp_bids_dataset / "sub-01" / "sub-01_scans.tsv"
        result = update_scans_entry(
            scans,
            "func/sub-01_task-rest_bold.nii.gz",
            "func/sub-01_task-nback_bold.nii.gz",
        )
        assert result is True
        rows = read_scans_tsv(scans)
        assert any("nback" in r["filename"] for r in rows)

    @pytest.mark.ai_generated
    def test_update_not_found(self, tmp_bids_dataset: Path) -> None:
        scans = tmp_bids_dataset / "sub-01" / "sub-01_scans.tsv"
        result = update_scans_entry(scans, "nonexistent.nii.gz", "new.nii.gz")
        assert result is False


class TestRemoveScansEntry:
    @pytest.mark.ai_generated
    def test_remove(self, tmp_bids_dataset: Path) -> None:
        scans = tmp_bids_dataset / "sub-01" / "sub-01_scans.tsv"
        result = remove_scans_entry(scans, "func/sub-01_task-rest_bold.nii.gz")
        assert result is True
        rows = read_scans_tsv(scans)
        assert len(rows) == 1

    @pytest.mark.ai_generated
    def test_remove_not_found(self, tmp_bids_dataset: Path) -> None:
        scans = tmp_bids_dataset / "sub-01" / "sub-01_scans.tsv"
        result = remove_scans_entry(scans, "nonexistent.nii.gz")
        assert result is False


class TestFindScansTsv:
    @pytest.mark.ai_generated
    def test_find_from_func_dir(self, tmp_bids_dataset: Path) -> None:
        bold = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz"
        scans = find_scans_tsv(bold, tmp_bids_dataset)
        assert scans is not None
        assert scans.name == "sub-01_scans.tsv"

    @pytest.mark.ai_generated
    def test_find_with_session(self, tmp_bids_dataset_with_sessions: Path) -> None:
        bold = (
            tmp_bids_dataset_with_sessions
            / "sub-01"
            / "ses-pre"
            / "func"
            / "sub-01_ses-pre_task-rest_bold.nii.gz"
        )
        scans = find_scans_tsv(bold, tmp_bids_dataset_with_sessions)
        assert scans is not None
        assert "ses-pre" in scans.name

    @pytest.mark.ai_generated
    def test_find_missing(self, tmp_path: Path) -> None:
        f = tmp_path / "sub-01" / "func" / "sub-01_bold.nii.gz"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"")
        scans = find_scans_tsv(f, tmp_path)
        assert scans is None
