"""Validator wrapper helpers for non-BIDS-source integration tests.

Two thin assertions on top of :func:`tests.conftest.validate_dataset`:

* :func:`assert_validator_flags` — asserts that the listed files appear
  in the validator's output (used as the *pre*-condition in SC-009 to
  prove the synthetic injection actually produced an invalid dataset).
* :func:`assert_validator_passes` — asserts the dataset has no error-
  severity issues, modulo a caller-supplied set of pre-existing codes
  (used as the *post*-condition in SC-009).

Both helpers ``pytest.skip`` gracefully when ``bids-validator-deno`` is
not installed so the suite remains portable across CI environments.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import _has_bids_validator, validate_dataset

__all__ = [
    "assert_validator_flags",
    "assert_validator_passes",
]


# Shared baseline of issue codes that ``bids-examples`` legitimately
# trips because it ships stub/zero-byte data files.  Mirrors the
# ignorable set used in tests/conftest.py:validate_dataset.
_BIDS_EXAMPLES_NOISE_CODES: frozenset[str] = frozenset(
    {
        "EMPTY_FILE",
        "NIFTI_HEADER_UNREADABLE",
        "NIFTI_UNIT",
        "NOT_INCLUDED",
        "SIDECAR_WITHOUT_DATAFILE",
    }
)


def _require_validator() -> None:
    if not _has_bids_validator():
        pytest.skip("bids-validator-deno not installed")


def assert_validator_flags(
    worktree_root: Path,
    *,
    expected_files: list[Path],
) -> None:
    """Assert that *expected_files* appear in the validator's raw output.

    Uses substring matching against the raw validator stdout/stderr
    rather than parsing the JSON ``files`` field, because the exact
    schema of issue-attached file references has shifted between
    validator versions and we want this helper to be resilient.
    """
    _require_validator()
    if not expected_files:
        raise ValueError("expected_files must be non-empty")

    proc = subprocess.run(
        [
            "bids-validator-deno",
            str(worktree_root),
            "--format",
            "json",
            "--ignoreNiftiHeaders",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    blob = proc.stdout + "\n" + proc.stderr
    missing = [p for p in expected_files if p.name not in blob]
    if missing:
        # Try parsing JSON for a more useful error message.
        try:
            data = json.loads(proc.stdout)
            issues = data.get("issues", {}).get("issues", [])
            issue_codes = sorted({i.get("code") for i in issues if i.get("code")})
        except json.JSONDecodeError:
            issue_codes = ["<unparseable validator output>"]
        raise AssertionError(
            f"Validator did not flag expected non-BIDS files: "
            f"{[str(p) for p in missing]}\n"
            f"Issue codes seen: {issue_codes}"
        )


def assert_validator_passes(
    worktree_root: Path,
    *,
    ignore_pre_existing: list[str] | None = None,
) -> None:
    """Assert no error-severity issues, modulo *ignore_pre_existing* codes."""
    _require_validator()

    ignored = set(ignore_pre_existing or ())
    ignored.update(_BIDS_EXAMPLES_NOISE_CODES)

    valid, errors = validate_dataset(worktree_root)
    remaining = [e for e in errors if e.get("code") not in ignored]
    if remaining:
        raise AssertionError(
            f"Validator reported {len(remaining)} error(s) at {worktree_root} "
            f"after operation:\n"
            + "\n".join(
                f"  - {e.get('code')}: {e.get('message', '')[:200]}"
                for e in remaining[:10]
            )
            + (f"\n  ... and {len(remaining) - 10} more" if len(remaining) > 10 else "")
        )
    # `valid` may be False even when *remaining* is empty if the only
    # errors fell into ``validate_dataset``'s built-in ignore list.
    # That's the contract — pre-existing noise is not a regression.
    _ = valid


# Re-export so callers can probe availability without importing from
# tests.conftest themselves.
def has_validator() -> bool:
    """Return ``True`` iff ``bids-validator-deno`` is on PATH."""
    return shutil.which("bids-validator-deno") is not None
