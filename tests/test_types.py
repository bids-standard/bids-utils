"""Tests for _types.py — Entity, BIDSPath, Change, OperationResult."""

from pathlib import Path

import pytest

from bids_utils._types import BIDSPath, Change, Entity, OperationResult


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
