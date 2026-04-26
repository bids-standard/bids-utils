# Phase 1 Data Model — Format-Preserving I/O

The feature introduces one primary internal entity (a per-file formatting
profile) plus two small companion structures used in the TSV path. There
is no persistent storage; profiles live in memory for the duration of a
read → modify → write cycle.

## Entities

### `FormattingProfile` (JSON)

Captured on read from a JSON file; consumed on write to reproduce style.

| Field | Type | Description | Source on read | Default (FR-006) |
|---|---|---|---|---|
| `indent` | `str` | Indent unit — e.g. `"  "`, `"    "`, `"\t"`, or `""` for compact JSON. | First indented line's leading whitespace, depth-normalized. | `"  "` |
| `separators` | `tuple[str, str]` | `(item_sep, key_sep)` passed to `json.dumps`. | Inspect bytes after first `:` and `,` outside strings. | `(",", ": ")` |
| `key_order` | implicit (via `dict` insertion order) | Order in which keys appear in the source object, recursively. | Native Python `json.loads` returns insertion-ordered dicts. | n/a |
| `line_ending` | `str` | `"\n"`, `"\r\n"`, or `"\r"`. | Predominant terminator across source lines. | `"\n"` |
| `trailing_newline` | `bool` | Whether the source ended with a line terminator. | `bytes.endswith(line_ending)`. | `True` |
| `bom` | `bool` | Whether the source began with the UTF-8 BOM. | `bytes.startswith(b"\xef\xbb\xbf")`. | `False` |
| `compact` | `bool` (derived) | True iff `indent == ""`. Convenience accessor. | derived | `False` |

**Validation rules**:
- `indent` must be `""` or a string of identical whitespace characters
  (all spaces or all tabs).
- `separators[1]` must end with the character `:` after stripping any
  trailing space.
- `line_ending` ∈ {`"\n"`, `"\r\n"`, `"\r"`}.

**State transitions**: Immutable after construction. A modified write
that needs a different style (future `--normalize` mode) constructs a new
profile rather than mutating.

**Relationships**: One per JSON file read. Not shared across files (spec
Key Entities: "One profile per file; not shared across files.").

---

### `TSVFormattingProfile`

Captured on read from a TSV file.

| Field | Type | Description | Source on read | Default |
|---|---|---|---|---|
| `fieldnames` | `list[str]` | Column order as it appears in the header row. | First row of `csv.reader`. | (operation must supply) |
| `line_ending` | `str` | `"\n"`, `"\r\n"`, or `"\r"`. | Predominant terminator. | `"\n"` |
| `trailing_newline` | `bool` | Whether the source ended with a terminator. | byte check. | `True` |
| `bom` | `bool` | Whether the source began with UTF-8 BOM. | byte check. | `False` |
| `original_lines` | `list[bytes]` | Verbatim row bytes (excluding header), keyed by row index. Used to splice unchanged rows on write (R5). | raw file split. | `[]` |
| `dialect` | `csv.Dialect` (subset) | `delimiter="\t"`, `quoting`, `quotechar`. | `csv.Sniffer` (with TSV defaults). | TSV defaults |

**Validation rules**:
- `fieldnames` must be non-empty and all unique.
- `len(original_lines)` must match the parsed row count.

**Relationships**: One per TSV file read. The pairing of parsed
`list[dict[str, str]]` rows with `original_lines` is positional
(index-aligned).

---

### `TextFormattingProfile` (plain-text BIDS files: `README`, `CHANGES`, `.bidsignore`)

Captured on read of a non-structured text file the tool may rewrite.

| Field | Type | Description | Default |
|---|---|---|---|
| `line_ending` | `str` | As above. | `"\n"` |
| `trailing_newline` | `bool` | As above. | `True` |
| `bom` | `bool` | As above. | `False` |

No indent or separator concepts — these files are opaque text from the
tool's perspective.

---

## Module entities

### `_format.py` (new module)

Pure functions, no global state:

- `detect_json_profile(source_bytes: bytes) -> FormattingProfile`
- `serialize_json(data: dict, profile: FormattingProfile) -> bytes`
- `detect_tsv_profile(source_bytes: bytes) -> TSVFormattingProfile`
- `serialize_tsv(rows: list[dict[str, str]], profile: TSVFormattingProfile) -> bytes`
- `detect_text_profile(source_bytes: bytes) -> TextFormattingProfile`
- `serialize_text(text: str, profile: TextFormattingProfile) -> bytes`
- `DEFAULT_JSON_PROFILE`, `DEFAULT_TSV_PROFILE`, `DEFAULT_TEXT_PROFILE`
  module constants (FR-006).
- `write_if_changed(path: Path, new_bytes: bytes) -> bool` — returns
  True iff a write occurred (FR-007).

### `_io.py` (modified)

Public additions/changes (backward-compatible):

- `read_json_with_profile(path, vcs, mode) -> tuple[dict | None, FormattingProfile | None]`
- `write_json(path, data, vcs, profile=None)` — `profile=None` keeps
  current behavior using `DEFAULT_JSON_PROFILE`.
- Existing `read_json`/`write_json` signatures stay; `write_json` gains
  optional `profile=` kwarg with default `None`.

### `_tsv.py` (modified)

- `read_tsv_with_profile(path, vcs, annexed_mode) -> tuple[list[dict], TSVFormattingProfile]`
- `write_tsv(path, rows, vcs, profile=None)` — optional `profile=` kwarg.

---

## Data flow (read → modify → write)

```
file bytes ──► detect_*_profile ──► profile ─────────────┐
                                                          │
file bytes ──► json.loads / csv.reader ──► data ─────────►│ caller mutates data
                                                          │ (the operation)
                                                          ▼
profile ──► serialize_*(data, profile) ──► new_bytes ──► write_if_changed
                                                          │
                                                          ▼
                                                    file on disk
                                            (or: no write, no VCS churn)
```

This realizes FR-013 (profile carried with content), FR-007 (no-op
suppression at the byte boundary), FR-005 (key-order preservation via
Python dict insertion order plus appending new keys at end), and FR-011
(single funnel for every write).
