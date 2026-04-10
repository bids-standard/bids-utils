"""Tests for _vcs.py — VCS detection and operations."""

import subprocess
from pathlib import Path

import pytest

from bids_utils._vcs import DataLad, Git, GitAnnex, NoVCS, detect_vcs


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


class TestNoVCSContentMethods:
    @pytest.mark.ai_generated
    def test_has_content_always_true(self, tmp_path: Path) -> None:
        vcs = NoVCS(tmp_path)
        f = tmp_path / "test.txt"
        f.write_text("x")
        assert vcs.has_content(f) is True

    @pytest.mark.ai_generated
    def test_get_content_noop(self, tmp_path: Path) -> None:
        vcs = NoVCS(tmp_path)
        vcs.get_content([tmp_path / "x"])  # should not raise

    @pytest.mark.ai_generated
    def test_unlock_noop(self, tmp_path: Path) -> None:
        vcs = NoVCS(tmp_path)
        vcs.unlock([tmp_path / "x"])  # should not raise

    @pytest.mark.ai_generated
    def test_add_noop(self, tmp_path: Path) -> None:
        vcs = NoVCS(tmp_path)
        vcs.add([tmp_path / "x"])  # should not raise


class TestGitContentMethods:
    @pytest.mark.ai_generated
    def test_has_content_always_true(self, tmp_path: Path) -> None:
        git = Git(tmp_path)
        f = tmp_path / "test.txt"
        f.write_text("x")
        assert git.has_content(f) is True

    @pytest.mark.ai_generated
    def test_get_content_noop(self, tmp_path: Path) -> None:
        git = Git(tmp_path)
        git.get_content([tmp_path / "x"])  # should not raise

    @pytest.mark.ai_generated
    def test_unlock_noop(self, tmp_path: Path) -> None:
        git = Git(tmp_path)
        git.unlock([tmp_path / "x"])  # should not raise

    @pytest.mark.ai_generated
    def test_add_stages_file(self, tmp_path: Path) -> None:
        subprocess.run(
            ["git", "init"], cwd=tmp_path, capture_output=True, check=True
        )
        f = tmp_path / "new.txt"
        f.write_text("hello")
        git = Git(tmp_path)
        git.add([f])
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert "new.txt" in result.stdout


class TestGitAnnexHasContent:
    @pytest.mark.ai_generated
    def test_regular_file_has_content(self, tmp_path: Path) -> None:
        annex = GitAnnex(tmp_path)
        f = tmp_path / "regular.txt"
        f.write_text("data")
        assert annex.has_content(f) is True

    @pytest.mark.ai_generated
    def test_symlink_with_target_has_content(self, tmp_path: Path) -> None:
        annex = GitAnnex(tmp_path)
        target = tmp_path / "real_file"
        target.write_text("data")
        link = tmp_path / "linked"
        link.symlink_to(target)
        assert annex.has_content(link) is True

    @pytest.mark.ai_generated
    def test_broken_symlink_no_content(self, tmp_path: Path) -> None:
        annex = GitAnnex(tmp_path)
        link = tmp_path / "broken"
        link.symlink_to(tmp_path / "nonexistent")
        assert annex.has_content(link) is False


class TestDataLadHasContent:
    @pytest.mark.ai_generated
    def test_delegates_to_annex(self, tmp_path: Path) -> None:
        subprocess.run(
            ["git", "init"], cwd=tmp_path, capture_output=True, check=True
        )
        (tmp_path / ".datalad").mkdir()
        dl = DataLad(tmp_path)
        f = tmp_path / "regular.txt"
        f.write_text("data")
        assert dl.has_content(f) is True

    @pytest.mark.ai_generated
    def test_broken_symlink_no_content(self, tmp_path: Path) -> None:
        subprocess.run(
            ["git", "init"], cwd=tmp_path, capture_output=True, check=True
        )
        (tmp_path / ".datalad").mkdir()
        dl = DataLad(tmp_path)
        link = tmp_path / "broken"
        link.symlink_to(tmp_path / "nonexistent")
        assert dl.has_content(link) is False
