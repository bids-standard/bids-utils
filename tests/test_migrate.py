"""Tests for migrate.py — schema-driven migration."""

import json
from pathlib import Path

import pytest

from bids_utils._dataset import BIDSDataset
from bids_utils.migrate import migrate_dataset


def _make_dataset(tmp_path: Path, bids_version: str = "1.4.0") -> Path:
    """Create a minimal dataset with a specific BIDSVersion."""
    ds = tmp_path / "dataset"
    ds.mkdir()
    (ds / "dataset_description.json").write_text(
        json.dumps({"Name": "Test", "BIDSVersion": bids_version, "DatasetType": "raw"})
    )
    (ds / "participants.tsv").write_text("participant_id\nsub-01\n")
    return ds


class TestFieldRename:
    @pytest.mark.ai_generated
    def test_basedon_to_sources(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        sidecar = func / "sub-01_task-rest_bold.json"
        sidecar.write_text(json.dumps({"BasedOn": ["sub-01/anat/sub-01_T1w.nii.gz"]}))

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        assert result.findings
        assert any("BasedOn" in str(f.current_value) for f in result.findings)
        # Verify the fix was applied
        data = json.loads(sidecar.read_text())
        assert "BasedOn" not in data
        assert "Sources" in data

    @pytest.mark.ai_generated
    def test_rawsources_to_sources(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        sidecar = ds_path / "sub-01_bold.json"
        sidecar.write_text(json.dumps({"RawSources": ["rawdata/sub-01.nii"]}))
        (ds_path / "sub-01").mkdir()

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        assert any("RawSources" in str(f.current_value) for f in result.findings)


class TestEnumRename:
    @pytest.mark.ai_generated
    def test_elektaneuromag(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        meg = ds_path / "sub-01" / "meg"
        meg.mkdir(parents=True)
        sidecar = meg / "sub-01_coordsystem.json"
        sidecar.write_text(json.dumps({"MEGCoordinateSystem": "ElektaNeuromag"}))

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        assert result.findings
        data = json.loads(sidecar.read_text())
        assert data["MEGCoordinateSystem"] == "NeuromagElektaMEGIN"


class TestPathFormat:
    @pytest.mark.ai_generated
    def test_intendedfor_to_bids_uri(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        fmap = ds_path / "sub-01" / "fmap"
        fmap.mkdir(parents=True)
        sidecar = fmap / "sub-01_phasediff.json"
        sidecar.write_text(json.dumps({
            "IntendedFor": "ses-01/func/sub-01_ses-01_task-rest_bold.nii.gz"
        }))

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        data = json.loads(sidecar.read_text())
        assert data["IntendedFor"].startswith("bids::")

    @pytest.mark.ai_generated
    def test_intendedfor_list(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        fmap = ds_path / "sub-01" / "fmap"
        fmap.mkdir(parents=True)
        sidecar = fmap / "sub-01_phasediff.json"
        sidecar.write_text(json.dumps({
            "IntendedFor": [
                "func/sub-01_task-rest_bold.nii.gz",
                "func/sub-01_task-motor_bold.nii.gz",
            ]
        }))

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        data = json.loads(sidecar.read_text())
        assert isinstance(data["IntendedFor"], list)
        assert all(v.startswith("bids::") for v in data["IntendedFor"])


class TestDOIFormat:
    @pytest.mark.ai_generated
    def test_bare_doi_to_uri(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        desc = ds_path / "dataset_description.json"
        data = json.loads(desc.read_text())
        data["DatasetDOI"] = "10.1234/example"
        desc.write_text(json.dumps(data))

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        data = json.loads(desc.read_text())
        assert data["DatasetDOI"] == "doi:10.1234/example"


class TestScanDateMove:
    @pytest.mark.ai_generated
    def test_scandate_to_scans_tsv(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        sub = ds_path / "sub-01" / "func"
        sub.mkdir(parents=True)
        sidecar = sub / "sub-01_task-rest_bold.json"
        sidecar.write_text(json.dumps({"ScanDate": "2020-01-15", "TaskName": "rest"}))
        nii = sub / "sub-01_task-rest_bold.nii.gz"
        nii.write_bytes(b"")

        # Create scans.tsv
        scans = ds_path / "sub-01" / "sub-01_scans.tsv"
        scans.write_text("filename\tacq_time\nfunc/sub-01_task-rest_bold.nii.gz\t\n")

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        # ScanDate should be removed from JSON
        data = json.loads(sidecar.read_text())
        assert "ScanDate" not in data

        # And moved to scans.tsv
        from bids_utils._scans import read_scans_tsv

        rows = read_scans_tsv(scans)
        assert rows[0]["acq_time"] == "2020-01-15"


class TestDryRun:
    @pytest.mark.ai_generated
    def test_dry_run_no_modifications(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        fmap = ds_path / "sub-01" / "fmap"
        fmap.mkdir(parents=True)
        sidecar = fmap / "sub-01_phasediff.json"
        original = json.dumps({"IntendedFor": "func/sub-01_bold.nii.gz"})
        sidecar.write_text(original)

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, dry_run=True)

        assert result.dry_run
        assert result.findings
        assert len(result.changes) == 0  # No changes in dry run
        # File should be unmodified
        assert sidecar.read_text() == original


class TestNothingToDo:
    @pytest.mark.ai_generated
    def test_up_to_date_dataset(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        result = migrate_dataset(ds)

        # Dataset at 1.9.0, no deprecated fields → nothing to do
        assert any("up to date" in w.lower() or "nothing" in w.lower() for w in result.warnings)
