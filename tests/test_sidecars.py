"""Tests for _sidecars.py — sidecar file discovery."""

from pathlib import Path

import pytest

from bids_utils._sidecars import find_sidecars


class TestFindSidecars:
    @pytest.mark.ai_generated
    def test_find_json_sidecar(self, tmp_bids_dataset: Path) -> None:
        bold = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz"
        sidecars = find_sidecars(bold)
        assert any(s.suffix == ".json" for s in sidecars)

    @pytest.mark.ai_generated
    def test_no_sidecars_for_json(self, tmp_bids_dataset: Path) -> None:
        json_file = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-rest_bold.json"
        sidecars = find_sidecars(json_file)
        # .json itself won't have sidecars (no .nii.gz check by default)
        # .bvec/.bval don't exist for bold
        assert len(sidecars) == 0

    @pytest.mark.ai_generated
    def test_find_bvec_bval(self, tmp_path: Path) -> None:
        func = tmp_path / "func"
        func.mkdir()
        nii = func / "sub-01_dwi.nii.gz"
        nii.write_bytes(b"")
        (func / "sub-01_dwi.json").write_text("{}")
        (func / "sub-01_dwi.bvec").write_text("0 0 0")
        (func / "sub-01_dwi.bval").write_text("0 0 0")

        sidecars = find_sidecars(nii)
        names = {s.name for s in sidecars}
        assert "sub-01_dwi.json" in names
        assert "sub-01_dwi.bvec" in names
        assert "sub-01_dwi.bval" in names

    @pytest.mark.ai_generated
    def test_missing_sidecars(self, tmp_path: Path) -> None:
        nii = tmp_path / "sub-01_bold.nii.gz"
        nii.write_bytes(b"")
        sidecars = find_sidecars(nii)
        assert sidecars == []
