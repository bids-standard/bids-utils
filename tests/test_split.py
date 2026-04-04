"""Tests for split.py — dataset split by suffix/datatype."""

from pathlib import Path

import pytest

from bids_utils._dataset import BIDSDataset
from bids_utils.split import split_dataset


class TestSplit:
    @pytest.mark.ai_generated
    def test_split_by_suffix(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        output = tmp_bids_dataset.parent / "bold-only"

        result = split_dataset(ds, output, suffix="bold")

        assert result.success
        assert (output / "dataset_description.json").is_file()
        # Should have bold files
        bold_files = list(output.rglob("*bold.nii.gz"))
        assert len(bold_files) > 0
        # Should NOT have T1w files
        t1w_files = list(output.rglob("*T1w.nii.gz"))
        assert len(t1w_files) == 0

    @pytest.mark.ai_generated
    def test_split_by_datatype(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        output = tmp_bids_dataset.parent / "func-only"

        result = split_dataset(ds, output, datatype="func")

        assert result.success
        func_files = list(output.rglob("func/*"))
        assert len(func_files) > 0

    @pytest.mark.ai_generated
    def test_split_dry_run(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        output = tmp_bids_dataset.parent / "split-out"

        result = split_dataset(ds, output, suffix="bold", dry_run=True)

        assert result.dry_run
        assert len(result.changes) > 0
        assert not output.exists()

    @pytest.mark.ai_generated
    def test_split_no_filter(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        output = tmp_bids_dataset.parent / "no-filter"

        result = split_dataset(ds, output)

        assert not result.success
        assert any("Must specify" in e for e in result.errors)

    @pytest.mark.ai_generated
    def test_split_copies_sidecars(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        output = tmp_bids_dataset.parent / "bold-split"

        split_dataset(ds, output, suffix="bold")

        # JSON sidecars should be copied too
        json_files = list(output.rglob("*bold.json"))
        assert len(json_files) > 0
