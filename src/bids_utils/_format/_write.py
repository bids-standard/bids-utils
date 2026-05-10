"""Byte-level no-op-write suppression (FR-007 / SC-001).

Writes are atomic: bytes are written to a sibling temp file and then
``os.replace``'d into the target path. Read errors propagate; we never
silently overwrite a file we could not verify.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_if_changed(path: Path, new_bytes: bytes) -> bool:
    """Write ``new_bytes`` to ``path`` iff different from current contents.

    Returns ``True`` iff a write occurred. The write is atomic on POSIX
    (and on Windows for same-volume targets) via tempfile + ``os.replace``.

    Behavior:

    * If ``path`` does not exist, parent directories are created and a
      write is performed.
    * If ``path`` exists and current bytes equal ``new_bytes``, no write
      occurs and ``False`` is returned. mtime is unchanged.
    * Read errors other than ``FileNotFoundError`` (e.g.,
      ``PermissionError``, ``IsADirectoryError``) propagate. We never
      overwrite a file whose current bytes we could not read.
    * On a symlink, the symlink itself is replaced atomically (the
      original target is left intact). This matches git-annex's
      "unlock-then-write" expectation.
    """
    try:
        current = path.read_bytes()
    except FileNotFoundError:
        pass
    else:
        if current == new_bytes:
            return False

    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_str = tempfile.mkstemp(
        dir=parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(new_bytes)
        os.replace(tmp_str, path)
    except BaseException:
        Path(tmp_str).unlink(missing_ok=True)
        raise
    return True
