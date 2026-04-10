"""Shared TSV read/write helpers."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bids_utils._types import AnnexedMode
    from bids_utils._vcs import VCSBackend


def read_tsv(
    path: Path,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode | None = None,
) -> list[dict[str, str]]:
    """Read a BIDS TSV file into a list of row dicts.

    When *vcs* and *annexed_mode* are provided, content availability is
    checked before reading (FR-022).
    """
    if vcs is not None and annexed_mode is not None:
        from bids_utils._io import ensure_content

        ensure_content(path, vcs, annexed_mode)

    text = path.read_text(encoding="utf-8")
    reader = csv.DictReader(StringIO(text), delimiter="\t")
    return list(reader)


def write_tsv(
    path: Path,
    rows: list[dict[str, str]],
    vcs: VCSBackend | None = None,
) -> None:
    """Write rows to a BIDS TSV file.

    When *vcs* is provided, the file is unlocked before writing and
    re-added after (FR-022).
    """
    if not rows:
        return

    if vcs is not None:
        from bids_utils._io import ensure_writable, mark_modified

        ensure_writable(path, vcs)

    fieldnames = list(rows[0].keys())
    buf = StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=fieldnames, delimiter="\t", lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")

    if vcs is not None:
        mark_modified([path], vcs)
