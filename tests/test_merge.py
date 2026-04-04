"""Tests for merge.py — dataset merge."""

import json
from pathlib import Path

import pytest

from bids_utils.merge import merge_datasets


def _make_simple_dataset(tmp_path: Path, name: str, subjects: list[str]) -> Path:
    """Create a simple dataset with given subjects."""
    ds = tmp_path / name
    ds.mkdir()
    (ds / "dataset_description.json").write_text(
        json.dumps({"Name": name, "BIDSVersion": "1.9.0", "DatasetType": "raw"})
    )
    rows = ["participant_id"] + [f"sub-{s}" for s in subjects]
    (ds / "participants.tsv").write_text("\n".join(rows) + "\n")

    for sub in subjects:
        func = ds / f"sub-{sub}" / "func"
        func.mkdir(parents=True)
        (func / f"sub-{sub}_task-rest_bold.nii.gz").write_bytes(b"")
        (func / f"sub-{sub}_task-rest_bold.json").write_text(json.dumps({"TaskName": "rest"}))

    return ds


class TestMerge:
    @pytest.mark.ai_generated
    def test_merge_non_overlapping(self, tmp_path: Path) -> None:
        ds_a = _make_simple_dataset(tmp_path, "dsA", ["01", "02"])
        ds_b = _make_simple_dataset(tmp_path, "dsB", ["03", "04"])
        output = tmp_path / "merged"

        result = merge_datasets([ds_a, ds_b], output)

        assert result.success
        assert (output / "sub-01").is_dir()
        assert (output / "sub-03").is_dir()
        assert (output / "dataset_description.json").is_file()

    @pytest.mark.ai_generated
    def test_merge_conflict_error(self, tmp_path: Path) -> None:
        ds_a = _make_simple_dataset(tmp_path, "dsA", ["01"])
        ds_b = _make_simple_dataset(tmp_path, "dsB", ["01"])
        output = tmp_path / "merged"

        result = merge_datasets([ds_a, ds_b], output, on_conflict="error")

        assert not result.success
        assert any("Conflict" in e for e in result.errors)

    @pytest.mark.ai_generated
    def test_merge_into_sessions(self, tmp_path: Path) -> None:
        ds_a = _make_simple_dataset(tmp_path, "dsA", ["01"])
        ds_b = _make_simple_dataset(tmp_path, "dsB", ["01"])
        output = tmp_path / "merged"

        result = merge_datasets(
            [ds_a, ds_b], output, into_sessions=["ses-A", "ses-B"]
        )

        assert result.success
        assert (output / "sub-01" / "ses-A").is_dir()
        assert (output / "sub-01" / "ses-B").is_dir()

    @pytest.mark.ai_generated
    def test_merge_dry_run(self, tmp_path: Path) -> None:
        ds_a = _make_simple_dataset(tmp_path, "dsA", ["01"])
        output = tmp_path / "merged"

        result = merge_datasets([ds_a], output, dry_run=True)

        assert result.dry_run
        # Output should not be created
        assert not (output / "sub-01").exists()

    @pytest.mark.ai_generated
    def test_merge_participants(self, tmp_path: Path) -> None:
        ds_a = _make_simple_dataset(tmp_path, "dsA", ["01"])
        ds_b = _make_simple_dataset(tmp_path, "dsB", ["02"])
        output = tmp_path / "merged"

        merge_datasets([ds_a, ds_b], output)

        from bids_utils._participants import read_participants_tsv

        rows = read_participants_tsv(output / "participants.tsv")
        ids = [r["participant_id"] for r in rows]
        assert "sub-01" in ids
        assert "sub-02" in ids
