"""Unit tests for bids_utils._format — Phase 2 foundational coverage.

Covers contract Part A signatures, FR-006 default profile values, and
FR-007 / SC-001 byte-level no-op-write suppression.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from bids_utils._format import (
    DEFAULT_JSON_PROFILE,
    DEFAULT_TEXT_PROFILE,
    DEFAULT_TSV_PROFILE,
    FormattingProfile,
    TextFormattingProfile,
    TSVFormattingProfile,
    write_if_changed,
)


@pytest.mark.ai_generated
def test_signatures_present() -> None:
    """Contract Part A — dataclass fields and module re-exports."""
    # FormattingProfile fields
    p = FormattingProfile(
        indent="  ",
        separators=(",", ": "),
        line_ending="\n",
        trailing_newline=True,
        bom=False,
    )
    assert p.indent == "  "
    assert p.separators == (",", ": ")
    assert p.line_ending == "\n"
    assert p.trailing_newline is True
    assert p.bom is False
    assert p.compact is False  # derived

    # Frozen
    with pytest.raises((AttributeError, TypeError)):
        p.indent = "    "  # type: ignore[misc]

    # TSVFormattingProfile fields
    t = TSVFormattingProfile(
        fieldnames=("a", "b"),
        line_ending="\n",
        trailing_newline=True,
        bom=False,
        original_lines=(),
        quoting=0,
    )
    assert t.fieldnames == ("a", "b")
    assert t.original_lines == ()
    assert t.quoting == 0

    # TextFormattingProfile fields
    tx = TextFormattingProfile(line_ending="\n", trailing_newline=True, bom=False)
    assert tx.line_ending == "\n"


@pytest.mark.ai_generated
def test_default_profile_for_new_file() -> None:
    """B.4 / FR-006 — default profile for new JSON files."""
    assert DEFAULT_JSON_PROFILE.indent == "  "
    assert DEFAULT_JSON_PROFILE.separators == (",", ": ")
    assert DEFAULT_JSON_PROFILE.line_ending == "\n"
    assert DEFAULT_JSON_PROFILE.trailing_newline is True
    assert DEFAULT_JSON_PROFILE.bom is False
    assert DEFAULT_JSON_PROFILE.compact is False

    assert DEFAULT_TSV_PROFILE.line_ending == "\n"
    assert DEFAULT_TSV_PROFILE.trailing_newline is True
    assert DEFAULT_TSV_PROFILE.bom is False

    assert DEFAULT_TEXT_PROFILE.line_ending == "\n"
    assert DEFAULT_TEXT_PROFILE.trailing_newline is True
    assert DEFAULT_TEXT_PROFILE.bom is False


@pytest.mark.ai_generated
def test_write_if_changed_writes_when_different(tmp_path: Path) -> None:
    """FR-007 — first write to a missing path always happens."""
    p = tmp_path / "sub" / "f.txt"
    assert write_if_changed(p, b"hello") is True
    assert p.read_bytes() == b"hello"

    assert write_if_changed(p, b"different") is True
    assert p.read_bytes() == b"different"


@pytest.mark.ai_generated
def test_write_if_changed_skips_identical_bytes(tmp_path: Path) -> None:
    """FR-007 / SC-001 — identical bytes ⇒ no write, mtime unchanged."""
    p = tmp_path / "f.txt"
    p.write_bytes(b"hello")
    mtime_before = p.stat().st_mtime_ns

    assert write_if_changed(p, b"hello") is False
    assert p.stat().st_mtime_ns == mtime_before
    assert p.read_bytes() == b"hello"


@pytest.mark.ai_generated
def test_write_if_changed_propagates_read_errors(tmp_path: Path) -> None:
    """Read errors (other than FileNotFoundError) must NOT be swallowed.

    A previous version returned ``current = None`` on any ``OSError``
    and then unconditionally wrote, which silently violated FR-007 for
    unreadable-but-writable files. Lock that defense in.
    """
    # IsADirectoryError on read of a directory path
    d = tmp_path / "subdir"
    d.mkdir()
    with pytest.raises(IsADirectoryError):
        write_if_changed(d, b"hello")
    # Directory is unchanged
    assert d.is_dir()


@pytest.mark.ai_generated
def test_write_if_changed_is_atomic_under_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the write step fails, the original file is intact and no
    temp turd is left in the parent directory."""
    p = tmp_path / "f.txt"
    p.write_bytes(b"original")

    real_replace = os.replace

    def boom(*args: object, **kwargs: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr("bids_utils._format._write.os.replace", boom)

    with pytest.raises(OSError, match="simulated"):
        write_if_changed(p, b"new bytes")

    # Original survived
    assert p.read_bytes() == b"original"
    # No temp files left behind
    leftovers = [c for c in tmp_path.iterdir() if c.name.startswith(".f.txt.")]
    assert leftovers == [], f"temp turd(s) left: {leftovers}"

    # Restore to confirm the test patched the right thing
    monkeypatch.setattr("bids_utils._format._write.os.replace", real_replace)
