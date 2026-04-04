"""Tests for _vcs.py — VCS detection and operations."""

import subprocess
from pathlib import Path

import pytest

from bids_utils._vcs import Git, NoVCS, detect_vcs


class TestNoVCS:
    @pytest.mark.ai_generated
    def test_move(self, tmp_path: Path) -> None:
        src = tmp_path / "a.txt"
        dst = tmp_path / "b.txt"
        src.write_text("hello")
        vcs = NoVCS(tmp_path)
        vcs.move(src, dst)
        assert not src.exists()
        assert dst.read_text() == "hello"

    @pytest.mark.ai_generated
    def test_move_creates_parent(self, tmp_path: Path) -> None:
        src = tmp_path / "a.txt"
        dst = tmp_path / "sub" / "b.txt"
        src.write_text("hello")
        vcs = NoVCS(tmp_path)
        vcs.move(src, dst)
        assert dst.read_text() == "hello"

    @pytest.mark.ai_generated
    def test_remove_file(self, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_text("bye")
        vcs = NoVCS(tmp_path)
        vcs.remove(f)
        assert not f.exists()

    @pytest.mark.ai_generated
    def test_remove_dir(self, tmp_path: Path) -> None:
        d = tmp_path / "mydir"
        d.mkdir()
        (d / "file.txt").write_text("x")
        vcs = NoVCS(tmp_path)
        vcs.remove(d)
        assert not d.exists()

    @pytest.mark.ai_generated
    def test_is_dirty(self, tmp_path: Path) -> None:
        vcs = NoVCS(tmp_path)
        assert vcs.is_dirty() is False

    @pytest.mark.ai_generated
    def test_commit_noop(self, tmp_path: Path) -> None:
        vcs = NoVCS(tmp_path)
        vcs.commit("test", [])  # should not raise


class TestGit:
    @pytest.mark.ai_generated
    def test_move(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        src = tmp_path / "a.txt"
        src.write_text("hello")
        subprocess.run(
            ["git", "add", "a.txt"], cwd=tmp_path, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        dst = tmp_path / "b.txt"
        git = Git(tmp_path)
        git.move(src, dst)
        assert not src.exists()
        assert dst.read_text() == "hello"

    @pytest.mark.ai_generated
    def test_is_dirty(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        (tmp_path / "a.txt").write_text("x")
        subprocess.run(
            ["git", "add", "."], cwd=tmp_path, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        git = Git(tmp_path)
        assert git.is_dirty() is False

        (tmp_path / "b.txt").write_text("new")
        assert git.is_dirty() is True


class TestDetectVCS:
    @pytest.mark.ai_generated
    def test_no_vcs(self, tmp_path: Path) -> None:
        vcs = detect_vcs(tmp_path)
        assert vcs.name == "none"

    @pytest.mark.ai_generated
    def test_git(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        vcs = detect_vcs(tmp_path)
        assert vcs.name == "git"

    @pytest.mark.ai_generated
    def test_datalad(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        (tmp_path / ".datalad").mkdir()
        vcs = detect_vcs(tmp_path)
        assert vcs.name == "datalad"
