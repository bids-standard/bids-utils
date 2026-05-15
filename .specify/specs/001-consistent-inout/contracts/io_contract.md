# Internal I/O Contract — `bids_utils._format` and friends

bids-utils is a CLI/library, not a network service. The "interfaces" this
feature exposes are (a) the internal Python API used by every other
module that touches a file, and (b) the **observable behavioral contract**
on the resulting on-disk bytes. Both are specified below as the
acceptance surface for tests.

> **Status (FR-014)**: This contract is **internal**. No public API
> guarantee is implied; semver covers only the documented public surface
> in `bids_utils.__init__`. The contract here is the load-bearing
> agreement between modules in this repo.

---

## Part A — Python API contract

### `bids_utils._format` (package — re-exports from sub-modules)

```python
from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

# ── Dataclasses (from _format/_profile.py) ────────────────────────────

@dataclass(frozen=True)
class FormattingProfile:
    indent: str                      # "" | "  " | "    " | "\t" | ...
    separators: tuple[str, str]      # (item_sep, key_sep)
    line_ending: str                 # "\n" | "\r\n" | "\r"
    trailing_newline: bool
    bom: bool

@dataclass(frozen=True)
class TSVFormattingProfile:
    fieldnames: tuple[str, ...]
    line_ending: str
    trailing_newline: bool
    bom: bool
    original_lines: tuple[bytes, ...]   # row bytes, header excluded
    quoting: int                         # csv.QUOTE_*

@dataclass(frozen=True)
class TextFormattingProfile:
    line_ending: str
    trailing_newline: bool
    bom: bool

DEFAULT_JSON_PROFILE: FormattingProfile  # FR-006
DEFAULT_TSV_PROFILE: TSVFormattingProfile
DEFAULT_TEXT_PROFILE: TextFormattingProfile

# ── Backend Protocol (from _format/_json_backend.py) ──────────────────

class JSONBackend(Protocol):
    def parse(self, source: bytes) -> Any: ...
    def serialize(self, model: Any, profile: FormattingProfile) -> bytes: ...
    def detect_profile(self, source: bytes) -> FormattingProfile: ...
    def get_keys(self, model: Any) -> list[str]: ...
    def get_value(self, model: Any, key: str) -> Any: ...
    def set_value(self, model: Any, key: str, value: Any) -> None: ...
    def append_key(self, model: Any, key: str, value: Any) -> None: ...
    def delete_key(self, model: Any, key: str) -> None: ...

# ── Format-preserving JSON document (from _format/_json.py) ───────────

class JSONDocument(MutableMapping[str, Any]):
    """Format-preserving JSON document. Use like a dict.

    - __getitem__ returns Python values (lists, plain dicts for nested
      objects, strings, numbers, bools, None).
    - __setitem__ append-if-new, replace-if-exists.
    - __delitem__ removes the key.
    - Nested object views are plain dicts; mutate-and-assign-back to
      propagate (see quickstart.md).
    """
    profile: FormattingProfile

    def to_dict(self) -> dict: ...

def parse_json(source: bytes) -> tuple[JSONDocument, FormattingProfile]: ...
def serialize_json(
    data: JSONDocument | dict,
    profile: FormattingProfile,
) -> bytes:
    """Polymorphic on input type:
    - JSONDocument: byte-perfect round-trip via the backend.
    - dict: stdlib json.dumps parameterized by profile (FR-006 path).
    """

# ── TSV (from _format/_tsv.py) ────────────────────────────────────────

def detect_tsv_profile(source: bytes) -> TSVFormattingProfile: ...
def serialize_tsv(
    rows: list[dict[str, str]],
    profile: TSVFormattingProfile,
    changed_indices: set[int] | None = None,
) -> bytes: ...

# ── Text (from _format/_text.py) ──────────────────────────────────────

def detect_text_profile(source: bytes) -> TextFormattingProfile: ...
def serialize_text(text: str, profile: TextFormattingProfile) -> bytes: ...

# ── Write helper (from _format/_write.py) ─────────────────────────────

def write_if_changed(path: Path, new_bytes: bytes) -> bool: ...
```

### `bids_utils._io` (additions)

```python
from bids_utils._format import (
    FormattingProfile,
    JSONDocument,
    TextFormattingProfile,
)

def read_json_with_profile(
    path: Path,
    vcs: VCSBackend | None,
    mode: AnnexedMode = AnnexedMode.ERROR,
) -> tuple[JSONDocument | None, FormattingProfile | None]:
    """Read JSON and return (document, profile).
    profile is None iff document is None.
    The returned JSONDocument carries `profile` on `.profile`; the
    tuple shape is symmetric with `read_tsv_with_profile`."""

def write_json(
    path: Path,
    data: JSONDocument | dict,
    vcs: VCSBackend,
    profile: FormattingProfile | None = None,
) -> bool:
    """Serialize *data* using *profile* (default if None) and write iff
    bytes differ from disk. Returns True iff a write occurred.

    - If *data* is a JSONDocument: profile defaults to data.profile
      (the json-five-backed path). An explicit profile= overrides.
    - If *data* is a dict: profile defaults to DEFAULT_JSON_PROFILE
      (the stdlib path; FR-006 new-file behavior)."""

def read_text_with_profile(
    path: Path,
    vcs: VCSBackend | None,
    mode: AnnexedMode = AnnexedMode.ERROR,
) -> tuple[str | None, TextFormattingProfile | None]: ...

def write_text(
    path: Path,
    text: str,
    vcs: VCSBackend,
    profile: TextFormattingProfile | None = None,
) -> bool: ...
```

### `bids_utils._tsv` (additions)

```python
from bids_utils._format import TSVFormattingProfile

def read_tsv_with_profile(
    path: Path,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode | None = None,
) -> tuple[list[dict[str, str]], TSVFormattingProfile]: ...

def write_tsv(
    path: Path,
    rows: list[dict[str, str]],
    vcs: VCSBackend | None = None,
    profile: TSVFormattingProfile | None = None,
    changed_indices: set[int] | None = None,
) -> bool: ...
```

### Backward compatibility

The pre-existing signatures `read_json(path, vcs, mode) -> dict | None`
and `write_json(path, data, vcs) -> None`, `read_tsv(path, vcs,
annexed_mode) -> list[dict]`, `write_tsv(path, rows, vcs)` remain
importable and behaviorally equivalent. Per Principle X:

- Legacy `read_json` internally calls `read_json_with_profile` and
  returns `doc.to_dict()` (dropping the profile). Callers that only
  read continue to work without changes.
- Legacy `write_json(path, dict, vcs)` is the stdlib new-file path;
  it internally calls the profile-aware path with
  `profile=DEFAULT_JSON_PROFILE` and discards the returned bool.
- TSV legacy signatures are analogous.

### Adapter contract (new)

The `JSONBackend` Protocol IS a load-bearing interface contract. Any
future implementation must conform to its signatures AND pass
`tests/test_format_json_backend.py`, which encodes:
- the six R1.1 defenses (state-bug, mutation symmetry, etc.) as
  positive tests on the backend;
- the round-trip identity expectation on the bids-examples corpus
  (delegated test, optionally skipped in fast CI).

A new backend module shipping alongside `_json_backend.py` (e.g.,
`_json_backend_stdlib.py`) plus a one-line change to
`_format/_json.py` that selects between them is the supported swap
mechanism. No call site changes are required for a swap.

---

## Part B — Behavioral contract on output bytes

For every JSON, TSV, or plain-text file written by bids-utils, the
following MUST hold. These are the test assertions for
`tests/integration/test_format_preservation.py`.

### B.1 — Round-trip identity (FR-007 / SC-001)

For any file `f` read by bids-utils and written back without any
operation modifying `data`:
```
read_bytes_before == read_bytes_after
```
i.e., the file's bytes on disk are unchanged. No write happens; VCS
reports the file as clean.

### B.2 — Format preservation under semantic edit (FR-001..FR-004, FR-008..FR-010)

For any JSON file `f` with profile `P` whose data dict is modified by
changing exactly one existing key's value:
- `detect_json_profile(new_bytes) == P` (style preserved)
- The unified diff against the source has ≤ 5 changed lines in 95%+ of
  bids-examples sidecars (SC-002).

For any TSV file `f` with profile `T` whose rows are modified by
changing exactly one existing row's value:
- `detect_tsv_profile(new_bytes).line_ending == T.line_ending`
- `detect_tsv_profile(new_bytes).fieldnames == T.fieldnames`
- The unified diff against the source has ≤ 3 changed lines in 100% of
  cases (SC-003), regardless of LF vs CRLF.

### B.3 — Adding a new key (FR-005)

For any JSON file with a top-level (or nested) object `O = {k1, k2, ..., kn}`,
after `O[k_new] = v`:
- `list(O.keys()) == [k1, k2, ..., kn, k_new]` in serialized output.
- The diff is bounded to lines around the insertion point only; pre-existing
  keys are not reordered.

### B.4 — New file from scratch (FR-006)

For any file path that did not exist on disk before the write, the bytes
match `serialize_*(data, DEFAULT_*_PROFILE)`. The default is defined in
exactly one place (`_format.DEFAULT_*_PROFILE`).

### B.5 — Uniformity (FR-011)

There exists no code path in `src/bids_utils/` that writes a JSON sidecar
or TSV file by means other than `_io.write_json` / `_tsv.write_tsv` (or
equivalents that route through `_format`). Enforced by a meta-test that
greps `src/bids_utils/` for `json.dumps(...)` and `csv.DictWriter(...)`
calls outside `_format.py` / `_io.py` / `_tsv.py` and asserts none target
on-disk files. (CLI stdout writes are exempt and explicitly out of
scope.)

### B.6 — Correctness wins over preservation (FR-012)

If a preservation choice would alter semantic content (e.g., a TSV
quoting style would render a cell ambiguous), the writer drops the
preservation aspect and emits a `warnings.warn` with category
`UserWarning`. The output is then valid even if non-byte-identical to
what naive preservation would have produced.

### B.7 — Dry-run consistency (spec edge case)

For any operation invoked with `--dry-run`, the diff text rendered to the
user is identical (line-for-line) to the diff a real run would have
produced against disk. Implementation: dry-run synthesizes the would-be
new bytes with the same `serialize_*` call and diffs against the read
bytes.

### B.8 — Performance (SC-006)

The full `bids-examples` integration sweep runs in ≤ 1.20× the wall-clock
time of a baseline measured on `main` immediately before this feature
lands. Recorded as a benchmark in CI logs (informational, not a hard
gate).

---

## Test surface mapping

| Contract clause | Test |
|---|---|
| A (signatures) | `tests/test_format.py::test_signatures_present` |
| A (Protocol) | `tests/test_format_json_backend.py::test_default_backend_conforms_to_protocol` |
| A (adapter defenses R1.1.1) | `tests/test_format_json_backend.py::test_serialize_is_stateless_across_calls` |
| A (adapter defenses R1.1.2) | `tests/test_format_json_backend.py::test_set_value_routes_through_canonical_lists` |
| A (adapter defenses R1.1.3) | `tests/test_format_json_backend.py::test_serialize_asserts_keys_values_length` |
| A (adapter defenses R1.1.5) | `tests/test_format_json_backend.py::test_append_key_mirrors_whitespace` |
| A (adapter defenses R1.1.6) | `tests/test_format_json_backend.py::test_parse_falls_back_to_stdlib_on_json5_failure` |
| B.1 | `tests/integration/test_format_preservation.py::test_no_op_byte_identity` |
| B.2 (JSON) | `tests/integration/test_format_preservation.py::test_one_field_edit_diff_size` |
| B.2 (TSV) | `tests/integration/test_format_preservation.py::test_one_row_edit_diff_size` |
| B.3 | `tests/test_format.py::test_new_key_appended_at_end` |
| B.4 | `tests/test_format.py::test_default_profile_for_new_file` |
| B.5 | `tests/test_format.py::test_no_bypass_writers_in_repo` (meta-test; also asserts only `_json_backend.py` imports `json5`) |
| B.6 | `tests/test_format.py::test_correctness_wins_over_preservation` |
| B.7 | `tests/test_dry_run.py::test_dry_run_diff_matches_real_run` (extension) |
| B.8 | `tests/integration/test_format_preservation.py::test_perf_within_budget` |
