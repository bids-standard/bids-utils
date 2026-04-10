"""Tests for _dataset.py — BIDSDataset discovery and loading."""

import json
from pathlib import Path

import pytest

from bids_utils._dataset import BIDSDataset


class TestBIDSDataset:
    @pytest.mark.ai_generated
    def test_from_path_root(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        assert ds.root == tmp_bids_dataset
        assert ds.bids_version == "1.9.0"

    @pytest.mark.ai_generated
    def test_from_path_nested(self, tmp_bids_dataset: Path) -> None:
        nested = tmp_bids_dataset / "sub-01" / "func"
        ds = BIDSDataset.from_path(nested)
        assert ds.root == tmp_bids_dataset

    @pytest.mark.ai_generated
    def test_from_path_file(self, tmp_bids_dataset: Path) -> None:
        f = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz"
        ds = BIDSDataset.from_path(f)
        assert ds.root == tmp_bids_dataset

    @pytest.mark.ai_generated
    def test_from_path_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="No dataset_description.json"):
            BIDSDataset.from_path(tmp_path)

    @pytest.mark.ai_generated
    def test_from_path_malformed(self, tmp_path: Path) -> None:
        (tmp_path / "dataset_description.json").write_text("not json")
        with pytest.raises(ValueError, match="Malformed"):
            BIDSDataset.from_path(tmp_path)

    @pytest.mark.ai_generated
    def test_from_path_missing_version(self, tmp_path: Path) -> None:
        (tmp_path / "dataset_description.json").write_text(json.dumps({"Name": "test"}))
        with pytest.raises(ValueError, match="Missing BIDSVersion"):
            BIDSDataset.from_path(tmp_path)

    @pytest.mark.ai_generated
    def test_vcs_detection(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        # No .git dir → NoVCS
        assert ds.vcs.name == "none"
