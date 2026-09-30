"""Tests for _io.py — content-aware I/O layer (FR-022)."""

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bids_utils._io import (
    ensure_content,
    ensure_writable,
    mark_modified,
    read_json,
    update_json_references,
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
    @pytest.mark.parametrize(
        ("mode", "expected_warnings"),
        [
            (AnnexedMode.SKIP_WARNING, 1),
            (AnnexedMode.SKIP, 0),
        ],
        ids=["skip_warning_emits_warning", "skip_mode_is_silent"],
    )
    def test_skip_modes_raise(
        self,
        tmp_path: Path,
        mode: AnnexedMode,
        expected_warnings: int,
    ) -> None:
        vcs = _mock_vcs(has_content=False)
        f = tmp_path / "test.json"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with pytest.raises(ContentNotAvailableError):
                ensure_content(f, vcs, mode)
        assert len(w) == expected_warnings
        if expected_warnings:
            assert "Skipping" in str(w[0].message)


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


@pytest.mark.ai_generated
def test_update_json_references_skips_vanishing_git_objects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Background ``git gc`` removing ``.git/objects/NN`` must not break it."""
    (tmp_path / ".git" / "objects" / "03").mkdir(parents=True)
    fmap = tmp_path / "sub-01" / "fmap"
    fmap.mkdir(parents=True)
    sidecar = fmap / "sub-01_phasediff.json"
    sidecar.write_text(json.dumps({"IntendedFor": ["func/sub-01_run-1_bold.nii.gz"]}))

    scanned_git: list[Path] = []
    real_scandir = os.scandir

    def gc_race(path):  # type: ignore[no-untyped-def]
        if ".git" in Path(path).parts:
            scanned_git.append(Path(path))
            raise FileNotFoundError(path)
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", gc_race)
    modified = update_json_references(
        tmp_path, "sub-01_run-1_bold", "sub-01_run-99_bold"
    )
    assert scanned_git == []
    assert modified == [sidecar]
    assert json.loads(sidecar.read_text())["IntendedFor"] == [
        "func/sub-01_run-99_bold.nii.gz"
    ]
