"""Tests for _types.py — Entity, BIDSPath, Change, OperationResult."""

from pathlib import Path

import pytest

from bids_utils._types import (
    BIDSPath,
    Change,
    Entity,
    OperationResult,
    _is_bids_data_entry,
)


class TestEntity:
    @pytest.mark.ai_generated
    def test_str(self) -> None:
        e = Entity(key="sub", value="01")
        assert str(e) == "sub-01"

    @pytest.mark.ai_generated
    def test_frozen(self) -> None:
        e = Entity(key="sub", value="01")
        with pytest.raises(AttributeError):
            e.key = "ses"  # type: ignore[misc]


class TestBIDSPath:
    @pytest.mark.ai_generated
    def test_from_path_basic(self) -> None:
        bp = BIDSPath.from_path("sub-01_task-rest_bold.nii.gz")
        assert bp.entities == {"sub": "01", "task": "rest"}
        assert bp.suffix == "bold"
        assert bp.extension == ".nii.gz"

    @pytest.mark.ai_generated
    def test_from_path_with_session(self) -> None:
        bp = BIDSPath.from_path("sub-01_ses-pre_task-rest_run-02_bold.nii.gz")
        assert bp.entities == {"sub": "01", "ses": "pre", "task": "rest", "run": "02"}
        assert bp.suffix == "bold"

    @pytest.mark.ai_generated
    def test_from_path_full_path(self) -> None:
        bp = BIDSPath.from_path("sub-01/func/sub-01_task-rest_bold.nii.gz")
        assert bp.datatype == "func"
        assert bp.entities["sub"] == "01"

    @pytest.mark.ai_generated
    def test_from_path_json_sidecar(self) -> None:
        bp = BIDSPath.from_path("sub-01_task-rest_bold.json")
        assert bp.extension == ".json"
        assert bp.suffix == "bold"

    @pytest.mark.ai_generated
    def test_from_path_events_tsv(self) -> None:
        bp = BIDSPath.from_path("sub-01_task-rest_events.tsv")
        assert bp.extension == ".tsv"
        assert bp.suffix == "events"

    @pytest.mark.ai_generated
    def test_to_filename_roundtrip(self) -> None:
        original = "sub-01_ses-pre_task-rest_bold.nii.gz"
        bp = BIDSPath.from_path(original)
        assert bp.to_filename() == original

    @pytest.mark.ai_generated
    def test_to_relative_path(self) -> None:
        bp = BIDSPath(
            entities={"sub": "01", "ses": "pre", "task": "rest"},
            suffix="bold",
            extension=".nii.gz",
            datatype="func",
        )
        rel = bp.to_relative_path()
        assert rel == Path("sub-01/ses-pre/func/sub-01_ses-pre_task-rest_bold.nii.gz")

    @pytest.mark.ai_generated
    def test_with_entities(self) -> None:
        bp = BIDSPath.from_path("sub-01_task-rest_bold.nii.gz")
        bp2 = bp.with_entities(task="nback")
        assert bp2.entities["task"] == "nback"
        assert bp.entities["task"] == "rest"  # original unchanged

    @pytest.mark.ai_generated
    def test_with_suffix(self) -> None:
        bp = BIDSPath.from_path("sub-01_task-rest_bold.nii.gz")
        bp2 = bp.with_suffix("T1w")
        assert bp2.suffix == "T1w"
        assert bp.suffix == "bold"

    @pytest.mark.ai_generated
    def test_with_extension(self) -> None:
        bp = BIDSPath.from_path("sub-01_task-rest_bold.nii.gz")
        bp2 = bp.with_extension(".json")
        assert bp2.extension == ".json"

    @pytest.mark.ai_generated
    def test_from_path_anat(self) -> None:
        bp = BIDSPath.from_path("sub-01_T1w.nii.gz")
        assert bp.entities == {"sub": "01"}
        assert bp.suffix == "T1w"

    @pytest.mark.ai_generated
    def test_from_path_dwi(self) -> None:
        bp = BIDSPath.from_path("sub-01_dwi.bvec")
        assert bp.suffix == "dwi"
        assert bp.extension == ".bvec"

    @pytest.mark.ai_generated
    def test_to_filename_schema_order(self) -> None:
        """to_filename(schema=...) reorders entities into schema order."""
        from bids_utils._schema import BIDSSchema

        bp = BIDSPath(
            entities={
                "sub": "01",
                "task": "rest",
                "run": "99",
                "recording": "bipolar",
            },
            suffix="emg",
            extension=".edf",
        )
        # Insertion order would put run before recording already, but the
        # schema places `run` *after* `recording` (recording is between run
        # and task).  Construct entities in a wrong order to prove the
        # schema reorders them.
        bp_insertion = BIDSPath(
            entities={
                "recording": "bipolar",
                "run": "99",
                "task": "rest",
                "sub": "01",
            },
            suffix="emg",
            extension=".edf",
        )
        # Insertion-order filename reflects the bad ordering
        assert bp_insertion.to_filename().startswith("recording-bipolar")

        schema = BIDSSchema.load()
        ordered = bp.to_filename(schema=schema)
        # sub must come first and suffix/extension stay intact
        assert ordered.startswith("sub-01_")
        assert ordered.endswith("_emg.edf")
        # Apply schema's ordering to the badly-constructed instance and
        # verify that the resulting filename matches the well-ordered one.
        ordered_reordered = bp_insertion.to_filename(schema=schema)
        assert ordered_reordered == ordered

    @pytest.mark.ai_generated
    def test_to_filename_no_schema_preserves_insertion_order(self) -> None:
        """Without schema, insertion order is preserved."""
        bp = BIDSPath(
            entities={
                "recording": "bipolar",
                "sub": "01",
            },
            suffix="emg",
            extension=".edf",
        )
        # First key inserted appears first
        assert bp.to_filename().startswith("recording-bipolar_sub-01_")


class TestIsBidsDataEntry:
    """FR-036 — directory-as-file patterns are data entries."""

    @pytest.mark.ai_generated
    def test_regular_file_is_data_entry(self, tmp_path: Path) -> None:
        f = tmp_path / "sub-01_bold.nii.gz"
        f.write_bytes(b"")
        assert _is_bids_data_entry(f)

    @pytest.mark.ai_generated
    def test_plain_directory_is_not_data_entry(self, tmp_path: Path) -> None:
        d = tmp_path / "func"
        d.mkdir()
        assert not _is_bids_data_entry(d)

    @pytest.mark.ai_generated
    def test_ds_directory_is_data_entry(self, tmp_path: Path) -> None:
        """CTF MEG .ds directories are treated as atomic data entries."""
        meg = tmp_path / "sub-01_task-rest_meg.ds"
        meg.mkdir()
        (meg / "inside.bin").write_bytes(b"")
        assert _is_bids_data_entry(meg)

    @pytest.mark.ai_generated
    def test_zarr_directory_is_data_entry(self, tmp_path: Path) -> None:
        z = tmp_path / "sub-01.ome.zarr"
        z.mkdir()
        assert _is_bids_data_entry(z)

    @pytest.mark.ai_generated
    def test_rename_subject_includes_ds_directory(
        self, tmp_path: Path
    ) -> None:
        """Subject rename renames a .ds directory alongside regular files."""
        from bids_utils._dataset import BIDSDataset
        from bids_utils.subject import rename_subject

        ds_root = tmp_path / "ds"
        ds_root.mkdir()
        (ds_root / "dataset_description.json").write_text(
            '{"Name":"X","BIDSVersion":"1.9.0","DatasetType":"raw"}'
        )
        sub = ds_root / "sub-01" / "meg"
        sub.mkdir(parents=True)
        # CTF MEG .ds directory — a BIDS "dir-as-file"
        ds_file = sub / "sub-01_task-rest_meg.ds"
        ds_file.mkdir()
        (ds_file / "inner.bin").write_bytes(b"")

        ds = BIDSDataset.from_path(ds_root)
        result = rename_subject(ds, "01", "02")
        assert result.success

        # .ds directory must have been renamed under sub-02
        renamed = ds_root / "sub-02" / "meg" / "sub-02_task-rest_meg.ds"
        assert renamed.is_dir()
        assert (renamed / "inner.bin").exists()


class TestOperationResult:
    @pytest.mark.ai_generated
    def test_default(self) -> None:
        r = OperationResult()
        assert r.success is True
        assert r.dry_run is False
        assert r.changes == []
        assert r.warnings == []
        assert r.errors == []

    @pytest.mark.ai_generated
    def test_with_changes(self) -> None:
        c = Change(action="rename", source=Path("a"), target=Path("b"), detail="test")
        r = OperationResult(changes=[c])
        assert len(r.changes) == 1
        assert r.changes[0].action == "rename"
