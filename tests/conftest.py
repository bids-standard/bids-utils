"""Shared test fixtures for bids-utils."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

BIDS_EXAMPLES_DIR = Path(__file__).parent.parent / "bids-examples"


def _has_bids_examples() -> bool:
    return BIDS_EXAMPLES_DIR.is_dir() and (BIDS_EXAMPLES_DIR / "README.md").exists()


requires_bids_examples = pytest.mark.skipif(
    not _has_bids_examples(),
    reason="bids-examples submodule not available",
)


@pytest.fixture
def bids_examples_path() -> Path:
    """Return path to the bids-examples submodule."""
    if not _has_bids_examples():
        pytest.skip("bids-examples submodule not available")
    return BIDS_EXAMPLES_DIR


@pytest.fixture
def tmp_bids_dataset(tmp_path: Path) -> Path:
    """Create a minimal valid BIDS dataset in a temp directory."""
    ds = tmp_path / "dataset"
    ds.mkdir()

    # dataset_description.json
    (ds / "dataset_description.json").write_text(
        json.dumps(
            {
                "Name": "Test Dataset",
                "BIDSVersion": "1.9.0",
                "DatasetType": "raw",
            }
        )
    )

    # participants.tsv
    (ds / "participants.tsv").write_text("participant_id\tage\tsex\nsub-01\t25\tM\nsub-02\t30\tF\n")

    # sub-01 and sub-02
    _create_subject(ds, "01", sessions=None)
    _create_subject(ds, "02", sessions=None)

    return ds


@pytest.fixture
def tmp_bids_dataset_with_sessions(tmp_path: Path) -> Path:
    """Create a BIDS dataset with sessions."""
    ds = tmp_path / "dataset"
    ds.mkdir()

    (ds / "dataset_description.json").write_text(
        json.dumps(
            {
                "Name": "Test Dataset with Sessions",
                "BIDSVersion": "1.9.0",
                "DatasetType": "raw",
            }
        )
    )

    (ds / "participants.tsv").write_text("participant_id\tage\nsub-01\t25\nsub-02\t30\n")

    _create_subject(ds, "01", sessions=["pre", "post"])
    _create_subject(ds, "02", sessions=["pre", "post"])

    return ds


def _create_subject(
    ds: Path,
    sub_id: str,
    sessions: list[str] | None = None,
) -> None:
    """Create a subject with func and anat data."""
    sub_dir = ds / f"sub-{sub_id}"
    sub_dir.mkdir(exist_ok=True)

    if sessions:
        for ses in sessions:
            ses_dir = sub_dir / f"ses-{ses}"
            _create_datatype_files(ses_dir, f"sub-{sub_id}_ses-{ses}")

            # scans.tsv
            scans_path = ses_dir / f"sub-{sub_id}_ses-{ses}_scans.tsv"
            scans_path.write_text(
                "filename\tacq_time\n"
                f"func/sub-{sub_id}_ses-{ses}_task-rest_bold.nii.gz\t2020-01-01T12:00:00\n"
                f"anat/sub-{sub_id}_ses-{ses}_T1w.nii.gz\t2020-01-01T11:00:00\n"
            )
    else:
        _create_datatype_files(sub_dir, f"sub-{sub_id}")

        scans_path = sub_dir / f"sub-{sub_id}_scans.tsv"
        scans_path.write_text(
            "filename\tacq_time\n"
            f"func/sub-{sub_id}_task-rest_bold.nii.gz\t2020-01-01T12:00:00\n"
            f"anat/sub-{sub_id}_T1w.nii.gz\t2020-01-01T11:00:00\n"
        )


def _create_datatype_files(parent: Path, prefix: str) -> None:
    """Create func/ and anat/ directories with typical BIDS files."""
    func_dir = parent / "func"
    func_dir.mkdir(parents=True, exist_ok=True)

    # BOLD + sidecar
    (func_dir / f"{prefix}_task-rest_bold.nii.gz").write_bytes(b"")
    (func_dir / f"{prefix}_task-rest_bold.json").write_text(
        json.dumps({"RepetitionTime": 2.0, "TaskName": "rest"})
    )

    # events
    (func_dir / f"{prefix}_task-rest_events.tsv").write_text(
        "onset\tduration\ttrial_type\n0.0\t1.0\tgo\n"
    )

    anat_dir = parent / "anat"
    anat_dir.mkdir(parents=True, exist_ok=True)

    # T1w + sidecar
    (anat_dir / f"{prefix}_T1w.nii.gz").write_bytes(b"")
    (anat_dir / f"{prefix}_T1w.json").write_text(
        json.dumps({"MagneticFieldStrength": 3})
    )
