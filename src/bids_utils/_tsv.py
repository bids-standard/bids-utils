"""Shared TSV read/write helpers."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path


def read_tsv(path: Path) -> list[dict[str, str]]:
    """Read a BIDS TSV file into a list of row dicts."""
    text = path.read_text(encoding="utf-8")
    reader = csv.DictReader(StringIO(text), delimiter="\t")
    return list(reader)


def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write rows to a BIDS TSV file."""
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    buf = StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=fieldnames, delimiter="\t", lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")
