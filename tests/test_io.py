"""Tests for _io.py — content-aware I/O layer (FR-022)."""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bids_utils._io import (
    ensure_content,
    ensure_writable,
    mark_modified,
    read_json,
    write_json,
)
from bids_utils._types import AnnexedMode, ContentNotAvailableError


def _mock_vcs(has_content: bool = True) -> MagicMock:
    """Create a mock VCS backend."""
    vcs = MagicMock()
    vcs.has_content.return_value = has_content
    return vcs


class TestEnsureContent:
    @pytest.mark.ai_generated
    def test_content_present_does_nothing(self, tmp_path: Path) -> None:
        vcs = _mock_vcs(has_content=True)
        f = tmp_path / "test.json"
        f.write_text("{}")
        ensure_content(f, vcs, AnnexedMode.ERROR)
        vcs.get_content.assert_not_called()

    @pytest.mark.ai_generated
    def test_error_mode_raises(self, tmp_path: Path) -> None:
        vcs = _mock_vcs(has_content=False)
        f = tmp_path / "test.json"
        with pytest.raises(ContentNotAvailableError) as exc_info:
            ensure_content(f, vcs, AnnexedMode.ERROR)
        assert "annexed" in str(exc_info.value).lower()
        assert "--annexed=get" in str(exc_info.value)

    @pytest.mark.ai_generated
    def test_get_mode_fetches(self, tmp_path: Path) -> None:
        vcs = _mock_vcs(has_content=False)
        f = tmp_path / "test.json"
        ensure_content(f, vcs, AnnexedMode.GET)
        vcs.get_content.assert_called_once_with([f])

    @pytest.mark.ai_generated
    def test_skip_warning_raises_with_warning(
        self, tmp_path: Path
    ) -> None:
        vcs = _mock_vcs(has_content=False)
        f = tmp_path / "test.json"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with pytest.raises(ContentNotAvailableError):
                ensure_content(f, vcs, AnnexedMode.SKIP_WARNING)
        assert len(w) == 1
        assert "Skipping" in str(w[0].message)

    @pytest.mark.ai_generated
    def test_skip_mode_raises_silently(self, tmp_path: Path) -> None:
        vcs = _mock_vcs(has_content=False)
        f = tmp_path / "test.json"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with pytest.raises(ContentNotAvailableError):
                ensure_content(f, vcs, AnnexedMode.SKIP)
        assert len(w) == 0


class TestEnsureWritable:
    @pytest.mark.ai_generated
    def test_regular_file_noop(self, tmp_path: Path) -> None:
        vcs = _mock_vcs()
        f = tmp_path / "test.tsv"
        f.write_text("x")
        ensure_writable(f, vcs)
        vcs.unlock.assert_not_called()

    @pytest.mark.ai_generated
    def test_symlink_with_content_unlocks(self, tmp_path: Path) -> None:
        vcs = _mock_vcs()
        target = tmp_path / "real_file"
        target.write_text("data")
        link = tmp_path / "linked_file"
        link.symlink_to(target)
        ensure_writable(link, vcs)
        vcs.unlock.assert_called_once_with([link])

    @pytest.mark.ai_generated
    def test_broken_symlink_no_unlock(self, tmp_path: Path) -> None:
        vcs = _mock_vcs()
        link = tmp_path / "broken_link"
        link.symlink_to(tmp_path / "nonexistent")
        ensure_writable(link, vcs)
        vcs.unlock.assert_not_called()


class TestMarkModified:
    @pytest.mark.ai_generated
    def test_calls_add(self, tmp_path: Path) -> None:
        vcs = _mock_vcs()
        f = tmp_path / "test.tsv"
        mark_modified([f], vcs)
        vcs.add.assert_called_once_with([f])

    @pytest.mark.ai_generated
    def test_empty_list_noop(self) -> None:
        vcs = _mock_vcs()
        mark_modified([], vcs)
        vcs.add.assert_not_called()


class TestReadJson:
    @pytest.mark.ai_generated
    def test_reads_json(self, tmp_path: Path) -> None:
        vcs = _mock_vcs(has_content=True)
        f = tmp_path / "test.json"
        f.write_text(json.dumps({"key": "value"}))
        result = read_json(f, vcs, AnnexedMode.ERROR)
        assert result == {"key": "value"}

    @pytest.mark.ai_generated
    def test_returns_none_on_skip(self, tmp_path: Path) -> None:
        vcs = _mock_vcs(has_content=False)
        f = tmp_path / "test.json"
        result = read_json(f, vcs, AnnexedMode.SKIP)
        assert result is None

    @pytest.mark.ai_generated
    def test_returns_none_on_bad_json(self, tmp_path: Path) -> None:
        vcs = _mock_vcs(has_content=True)
        f = tmp_path / "test.json"
        f.write_text("not json")
        result = read_json(f, vcs, AnnexedMode.ERROR)
        assert result is None

    @pytest.mark.ai_generated
    def test_returns_none_on_non_dict(self, tmp_path: Path) -> None:
        vcs = _mock_vcs(has_content=True)
        f = tmp_path / "test.json"
        f.write_text(json.dumps([1, 2, 3]))
        result = read_json(f, vcs, AnnexedMode.ERROR)
        assert result is None


class TestWriteJson:
    @pytest.mark.ai_generated
    def test_writes_json(self, tmp_path: Path) -> None:
        vcs = _mock_vcs()
        f = tmp_path / "test.json"
        f.write_text("{}")
        write_json(f, {"key": "value"}, vcs)
        data = json.loads(f.read_text())
        assert data == {"key": "value"}
        vcs.add.assert_called_once()

    @pytest.mark.ai_generated
    def test_unlocks_symlink_before_write(self, tmp_path: Path) -> None:
        vcs = _mock_vcs()
        target = tmp_path / "real_file"
        target.write_text("{}")
        link = tmp_path / "linked.json"
        link.symlink_to(target)
        write_json(link, {"new": "data"}, vcs)
        vcs.unlock.assert_called_once_with([link])
        vcs.add.assert_called_once()
