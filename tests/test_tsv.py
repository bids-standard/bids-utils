"""Tests for the shared _tsv module."""

from __future__ import annotations

from pathlib import Path

import pytest

from bids_utils._tsv import read_tsv, write_tsv


@pytest.mark.ai_generated
def test_read_write_roundtrip(tmp_path: Path) -> None:
    """read_tsv and write_tsv preserve data through a roundtrip."""
    tsv = tmp_path / "test.tsv"
    rows = [
        {"col_a": "1", "col_b": "hello"},
        {"col_a": "2", "col_b": "world"},
    ]
    write_tsv(tsv, rows)
    result = read_tsv(tsv)
    assert result == rows


@pytest.mark.ai_generated
def test_write_tsv_empty_rows(tmp_path: Path) -> None:
    """write_tsv is a no-op when given an empty list."""
    tsv = tmp_path / "empty.tsv"
    write_tsv(tsv, [])
    assert not tsv.exists()


@pytest.mark.ai_generated
def test_read_tsv_preserves_field_order(tmp_path: Path) -> None:
    """Column order is preserved through write/read."""
    tsv = tmp_path / "ordered.tsv"
    rows = [{"z_col": "1", "a_col": "2", "m_col": "3"}]
    write_tsv(tsv, rows)
    result = read_tsv(tsv)
    assert list(result[0].keys()) == ["z_col", "a_col", "m_col"]
