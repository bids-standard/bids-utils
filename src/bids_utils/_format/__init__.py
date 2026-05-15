"""Format-preserving I/O package — internal API surface.

This package implements feature 001-consistent-inout (format-preserving
input/output for BIDS files). It is library-internal; the public
``bids_utils`` surface re-exports only what callers actually need.

Extensibility (FR-014): to add a new file type, define
``<Fmt>FormattingProfile`` (frozen dataclass), ``detect_<fmt>_profile``,
``serialize_<fmt>``, and a ``DEFAULT_<FMT>_PROFILE`` constant, then
re-export them here. To swap the JSON backend, write a class
implementing ``JSONBackend`` Protocol in a sibling
``_json_backend_<name>.py`` and update ``_default_backend`` in
``_json.py``. No call site changes are required.

See ``.specify/specs/001-consistent-inout/`` for the contract,
data-model, and research artifacts that define these shapes.
"""

from __future__ import annotations

from bids_utils._format._profile import (
    DEFAULT_JSON_PROFILE,
    DEFAULT_TEXT_PROFILE,
    DEFAULT_TSV_PROFILE,
    FormattingProfile,
    TextFormattingProfile,
    TSVFormattingProfile,
)
from bids_utils._format._write import write_if_changed

__all__ = [
    "DEFAULT_JSON_PROFILE",
    "DEFAULT_TEXT_PROFILE",
    "DEFAULT_TSV_PROFILE",
    "FormattingProfile",
    "TSVFormattingProfile",
    "TextFormattingProfile",
    "write_if_changed",
]
