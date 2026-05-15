"""Formatting profile dataclasses + module-level defaults.

The profile is captured on read from a file and consumed on write to
reproduce the file's style. See
``.specify/specs/001-consistent-inout/contracts/io_contract.md`` Part A
for the load-bearing contract, and ``data-model.md`` for the entity
shape.

In the json-five-backed JSON path, ``indent`` / ``separators`` /
``line_ending`` are *advisory* — the model preserves them byte-for-byte.
``bom`` and ``trailing_newline`` are load-bearing in both the
json-five-backed and stdlib-fallback paths because json-five does not
preserve them on its own.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormattingProfile:
    """Per-JSON-file formatting profile (FR-001..FR-004, FR-008)."""

    indent: str
    separators: tuple[str, str]
    line_ending: str
    trailing_newline: bool
    bom: bool

    @property
    def compact(self) -> bool:
        return self.indent == ""


@dataclass(frozen=True)
class TSVFormattingProfile:
    """Per-TSV-file formatting profile (FR-003, FR-004, FR-008, FR-009)."""

    fieldnames: tuple[str, ...]
    line_ending: str
    trailing_newline: bool
    bom: bool
    original_lines: tuple[bytes, ...]
    quoting: int


@dataclass(frozen=True)
class TextFormattingProfile:
    """Per-plain-text-file formatting profile."""

    line_ending: str
    trailing_newline: bool
    bom: bool


# FR-006 — defaults for new files; defined in exactly one place.

DEFAULT_JSON_PROFILE = FormattingProfile(
    indent="  ",
    separators=(",", ": "),
    line_ending="\n",
    trailing_newline=True,
    bom=False,
)

DEFAULT_TSV_PROFILE = TSVFormattingProfile(
    fieldnames=(),
    line_ending="\n",
    trailing_newline=True,
    bom=False,
    original_lines=(),
    quoting=0,  # csv.QUOTE_MINIMAL
)

DEFAULT_TEXT_PROFILE = TextFormattingProfile(
    line_ending="\n",
    trailing_newline=True,
    bom=False,
)
