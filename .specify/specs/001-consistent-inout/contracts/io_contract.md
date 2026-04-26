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

### `bids_utils._format`

```python
from dataclasses import dataclass
from pathlib import Path

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

def detect_json_profile(source: bytes) -> FormattingProfile: ...
def serialize_json(data: dict, profile: FormattingProfile) -> bytes: ...
def detect_tsv_profile(source: bytes) -> TSVFormattingProfile: ...
def serialize_tsv(rows: list[dict[str, str]],
                  profile: TSVFormattingProfile,
                  changed_indices: set[int] | None = None) -> bytes: ...
def detect_text_profile(source: bytes) -> TextFormattingProfile: ...
def serialize_text(text: str, profile: TextFormattingProfile) -> bytes: ...

def write_if_changed(path: Path, new_bytes: bytes) -> bool: ...
```

### `bids_utils._io` (additions)

```python
from bids_utils._format import FormattingProfile

def read_json_with_profile(
    path: Path,
    vcs: VCSBackend | None,
    mode: AnnexedMode = AnnexedMode.ERROR,
) -> tuple[dict | None, FormattingProfile | None]:
    """Read JSON and return (parsed_data, profile_for_round_trip).
    profile is None iff parsed_data is None."""

def write_json(
    path: Path,
    data: dict,
    vcs: VCSBackend,
    profile: FormattingProfile | None = None,
) -> bool:
    """Serialize *data* using *profile* (default if None) and write iff
    bytes differ from disk. Returns True iff a write occurred."""
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
importable and behaviorally equivalent (with `write_json` returning
`None` to preserve type), per Principle X. They internally call the
profile-aware path with `profile=DEFAULT_*_PROFILE` and discard the
returned bool.

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
| B.1 | `tests/integration/test_format_preservation.py::test_no_op_byte_identity` |
| B.2 (JSON) | `tests/integration/test_format_preservation.py::test_one_field_edit_diff_size` |
| B.2 (TSV) | `tests/integration/test_format_preservation.py::test_one_row_edit_diff_size` |
| B.3 | `tests/test_format.py::test_new_key_appended_at_end` |
| B.4 | `tests/test_format.py::test_default_profile_for_new_file` |
| B.5 | `tests/test_format.py::test_no_bypass_writers_in_repo` (meta-test) |
| B.6 | `tests/test_format.py::test_correctness_wins_over_preservation` |
| B.7 | `tests/test_dry_run.py::test_dry_run_diff_matches_real_run` (extension) |
| B.8 | `tests/integration/test_format_preservation.py::test_perf_within_budget` |
