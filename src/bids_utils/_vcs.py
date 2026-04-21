"""Version control system detection and operations."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class VCSBackend(Protocol):
    """Abstract interface for version control operations."""

    name: str

    def move(self, src: Path, dst: Path) -> None: ...
    def remove(self, path: Path) -> None: ...
    def is_dirty(self) -> bool: ...
    def commit(self, message: str, paths: list[Path]) -> None: ...

    # Content availability (FR-022)
    def has_content(self, path: Path) -> bool: ...
    def get_content(self, paths: list[Path]) -> None: ...

    # Write lifecycle for annexed files (FR-022)
    def unlock(self, paths: list[Path]) -> None: ...
    def add(self, paths: list[Path]) -> None: ...


class NoVCS:
    """Direct filesystem operations (no version control)."""

    name = "none"

    def __init__(self, root: Path) -> None:
        self.root = root

    def move(self, src: Path, dst: Path) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

    def remove(self, path: Path) -> None:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    def is_dirty(self) -> bool:
        return False  # No VCS, always "clean"

    def commit(self, message: str, paths: list[Path]) -> None:
        pass  # No-op

    def has_content(self, path: Path) -> bool:
        return True  # No annex, content always available

    def get_content(self, paths: list[Path]) -> None:
        pass  # No-op

    def unlock(self, paths: list[Path]) -> None:
        pass  # No-op

    def add(self, paths: list[Path]) -> None:
        pass  # No-op


class Git:
    """Git-based file operations."""

    name = "git"

    def __init__(self, root: Path) -> None:
        self.root = root

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        )

    def move(self, src: Path, dst: Path) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        self._run("mv", str(src), str(dst))

    def remove(self, path: Path) -> None:
        if path.is_dir():
            self._run("rm", "-rf", str(path))
        else:
            self._run("rm", str(path))

    def is_dirty(self) -> bool:
        result = self._run("status", "--porcelain")
        return bool(result.stdout.strip())

    def commit(self, message: str, paths: list[Path]) -> None:
        for p in paths:
            self._run("add", str(p))
        self._run("commit", "-m", message)

    def has_content(self, path: Path) -> bool:
        return True  # Plain git, content always available

    def get_content(self, paths: list[Path]) -> None:
        pass  # No-op

    def unlock(self, paths: list[Path]) -> None:
        pass  # No-op, plain git files are always writable

    def add(self, paths: list[Path]) -> None:
        for p in paths:
            self._run("add", str(p))


class GitAnnex:
    """Git-annex aware file operations."""

    name = "git-annex"

    def __init__(self, root: Path) -> None:
        self.root = root
        self._git = Git(root)

    def _run_annex(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "annex", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        )

    def move(self, src: Path, dst: Path) -> None:
        # git mv works for both annexed and regular files
        self._git.move(src, dst)

    def remove(self, path: Path) -> None:
        self._git.remove(path)

    def is_dirty(self) -> bool:
        return self._git.is_dirty()

    def commit(self, message: str, paths: list[Path]) -> None:
        self._git.commit(message, paths)

    def has_content(self, path: Path) -> bool:
        """Check if annexed file content is locally available.

        A file lacks content when it is a symlink whose target does not
        exist (broken symlink into .git/annex/objects).  Regular files
        (tracked in git, not annexed) always have content.
        """
        if not path.is_symlink():
            return True  # Regular file, not annexed
        # path.exists() follows the symlink — False for broken links
        return path.exists()

    def get_content(self, paths: list[Path]) -> None:
        if paths:
            self._run_annex("get", *[str(p) for p in paths])

    def unlock(self, paths: list[Path]) -> None:
        if paths:
            self._run_annex("unlock", *[str(p) for p in paths])

    def add(self, paths: list[Path]) -> None:
        if paths:
            self._run_annex("add", *[str(p) for p in paths])


class DataLad(GitAnnex):
    """DataLad-aware operations.

    Inherits move/remove/is_dirty/commit/has_content/add from :class:`GitAnnex`
    (all of which ultimately delegate to ``git`` or ``git annex``).  Only
    ``get_content`` and ``unlock`` are overridden to go through the
    ``datalad`` CLI so that subdataset/run-record bookkeeping stays
    consistent.
    """

    name = "datalad"

    def _run_datalad(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["datalad", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        )

    def get_content(self, paths: list[Path]) -> None:
        if paths:
            self._run_datalad("get", *[str(p) for p in paths])

    def unlock(self, paths: list[Path]) -> None:
        if paths:
            self._run_datalad("unlock", *[str(p) for p in paths])


def detect_vcs(root: Path) -> VCSBackend:
    """Detect the VCS backend for a directory.

    Detection order: DataLad -> GitAnnex -> Git -> NoVCS
    """
    git_dir = root / ".git"
    if not git_dir.exists():
        return NoVCS(root)

    # Check for DataLad
    datalad_dir = root / ".datalad"
    if datalad_dir.is_dir():
        return DataLad(root)

    # Check for git-annex
    try:
        result = subprocess.run(
            ["git", "config", "--get", "annex.uuid"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return GitAnnex(root)
    except FileNotFoundError:
        pass

    return Git(root)
