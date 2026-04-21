"""Shared test fixtures for bids-utils."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

BIDS_EXAMPLES_DIR = Path(__file__).parent.parent / "bids-examples"


def _has_bids_examples() -> bool:
    return BIDS_EXAMPLES_DIR.is_dir() and (BIDS_EXAMPLES_DIR / "README.md").exists()


def _has_bids_validator() -> bool:
    return shutil.which("bids-validator-deno") is not None


requires_bids_validator = pytest.mark.skipif(
    not _has_bids_validator(),
    reason="bids-validator-deno not installed",
)


def validate_dataset(ds_path: Path) -> tuple[bool, list[dict]]:
    """Run bids-validator-deno on a dataset.

    Returns ``(valid, errors)`` where *errors* is the list of error-severity
    issues.  Uses ``--ignoreNiftiHeaders`` because bids-examples ships stub
    NIfTI files.

    Raises ``FileNotFoundError`` if ``bids-validator-deno`` is not installed.
    """
    if not _has_bids_validator():
        raise FileNotFoundError("bids-validator-deno not installed")

    result = subprocess.run(
        [
            "bids-validator-deno",
            str(ds_path),
            "--format",
            "json",
            "--ignoreNiftiHeaders",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, [
            {
                "code": "VALIDATOR_PARSE_ERROR",
                "severity": "error",
                "message": result.stderr[:500],
            }
        ]

    # v2 validator: issues.issues is a flat list with "severity" field
    all_issues = data.get("issues", {}).get("issues", [])
    # Filter: errors only, ignore EMPTY_FILE and NIFTI issues (bids-examples
    # ships stub/zero-byte data files that are expected to fail these checks)
    ignorable = {
        "EMPTY_FILE",
        "NIFTI_HEADER_UNREADABLE",
        "NIFTI_UNIT",
        # bids-examples ships files with intentionally invalid suffixes
        # (e.g., ds000248/sub-01/anat/sub-01_THISSUFFIXISNOTVALID.json)
        "NOT_INCLUDED",
        "SIDECAR_WITHOUT_DATAFILE",
    }
    errors = [
        i
        for i in all_issues
        if i.get("severity") == "error" and i.get("code") not in ignorable
    ]
    return len(errors) == 0, errors


requires_bids_examples = pytest.mark.skipif(
    not _has_bids_examples(),
    reason="bids-examples submodule not available",
)


# Cache of dataset names that pass bids-validator (computed once per session).
_VALID_DATASETS: list[str] | None = None


def validated_dataset_ids() -> list[str]:
    """Return bids-examples dataset names that pass bids-validator.

    Results are cached across the entire test session.  Datasets that
    fail validation (or have no ``dataset_description.json``) are
    excluded — they would cause every mutating test to skip anyway.
    """
    global _VALID_DATASETS  # noqa: PLW0603
    if _VALID_DATASETS is not None:
        return _VALID_DATASETS

    if not _has_bids_examples() or not _has_bids_validator():
        _VALID_DATASETS = []
        return _VALID_DATASETS

    valid: list[str] = []
    for d in sorted(BIDS_EXAMPLES_DIR.iterdir()):
        if not d.is_dir() or not (d / "dataset_description.json").is_file():
            continue
        ok, _ = validate_dataset(d)
        if ok:
            valid.append(d.name)
    _VALID_DATASETS = valid
    return _VALID_DATASETS


def validated_session_dataset_ids() -> list[str]:
    """Subset of ``validated_dataset_ids`` that contain ``ses-*`` dirs."""
    ids: list[str] = []
    for name in validated_dataset_ids():
        ds = BIDS_EXAMPLES_DIR / name
        for sub in ds.iterdir():
            if not sub.is_dir() or not sub.name.startswith("sub-"):
                continue
            if any(
                c.is_dir() and c.name.startswith("ses-")
                for c in sub.iterdir()
            ):
                ids.append(name)
                break
    return ids


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
    (ds / "participants.tsv").write_text(
        "participant_id\tage\tsex\nsub-01\t25\tM\nsub-02\t30\tF\n"
    )

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

    (ds / "participants.tsv").write_text(
        "participant_id\tage\nsub-01\t25\nsub-02\t30\n"
    )

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


def _has_git_annex() -> bool:
    return shutil.which("git-annex") is not None


requires_git_annex = pytest.mark.skipif(
    not _has_git_annex(),
    reason="git-annex not installed",
)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture
def tmp_annex_dataset(tmp_path: Path) -> Path:
    """Create a BIDS dataset inside a git-annex repo with locked files.

    Data files (``.nii.gz``) are annexed (locked symlinks into
    ``.git/annex/objects``).  Sidecar files (``.json``, ``.tsv``) are
    tracked in regular git.  This reproduces the layout that DataLad and
    ``git annex add`` produce for real neuroimaging datasets.

    Skips if ``git-annex`` is not installed.
    """
    if not _has_git_annex():
        pytest.skip("git-annex not installed")

    ds = tmp_path / "annex_dataset"
    ds.mkdir()

    # Init git + annex
    _git(ds, "init")
    _git(ds, "config", "user.email", "test@test.com")
    _git(ds, "config", "user.name", "Test")
    _git(ds, "annex", "init", "test-annex")

    # Configure: annex large files only (simulates DataLad default)
    _git(
        ds,
        "config",
        "annex.largefiles",
        "largerthan=0 and not (include=*.json or include=*.tsv)",
    )

    # dataset_description.json (regular git)
    (ds / "dataset_description.json").write_text(
        json.dumps(
            {
                "Name": "Annex Test Dataset",
                "BIDSVersion": "1.9.0",
                "DatasetType": "raw",
            }
        )
    )

    # participants.tsv (regular git)
    (ds / "participants.tsv").write_text(
        "participant_id\tage\tsex\nsub-01\t25\tM\n"
    )

    # Create subject with func + anat
    _create_annex_subject(ds, "01")

    # Add and commit everything
    _git(ds, "annex", "add", ".")
    _git(ds, "add", ".")
    _git(ds, "commit", "-m", "initial dataset")

    # Verify: .nii.gz files should be symlinks, .json should be regular
    func = ds / "sub-01" / "ses-pre" / "func"
    bold = func / "sub-01_ses-pre_task-rest_bold.nii.gz"
    bold_json = func / "sub-01_ses-pre_task-rest_bold.json"
    assert bold.is_symlink(), f"Expected {bold} to be a symlink"
    assert not bold_json.is_symlink(), f"Expected {bold_json} to not be a symlink"

    return ds


def _create_annex_subject(ds: Path, sub_id: str) -> None:
    """Create a subject with sessions for the annex fixture."""
    for ses in ["pre", "post"]:
        prefix = f"sub-{sub_id}_ses-{ses}"
        ses_dir = ds / f"sub-{sub_id}" / f"ses-{ses}"

        func_dir = ses_dir / "func"
        func_dir.mkdir(parents=True, exist_ok=True)
        (func_dir / f"{prefix}_task-rest_bold.nii.gz").write_bytes(
            b"\x00" * 100
        )
        (func_dir / f"{prefix}_task-rest_bold.json").write_text(
            json.dumps({"RepetitionTime": 2.0, "TaskName": "rest"})
        )

        anat_dir = ses_dir / "anat"
        anat_dir.mkdir(parents=True, exist_ok=True)
        (anat_dir / f"{prefix}_T1w.nii.gz").write_bytes(b"\x00" * 100)
        (anat_dir / f"{prefix}_T1w.json").write_text(
            json.dumps({"MagneticFieldStrength": 3})
        )

        # scans.tsv
        scans = ses_dir / f"{prefix}_scans.tsv"
        scans.write_text(
            "filename\tacq_time\n"
            f"func/{prefix}_task-rest_bold.nii.gz\t2020-01-01T12:00:00\n"
            f"anat/{prefix}_T1w.nii.gz\t2020-01-01T11:00:00\n"
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
