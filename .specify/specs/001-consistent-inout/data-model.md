# Phase 1 Data Model — Format-Preserving I/O

The feature introduces one primary internal entity (a per-file formatting
profile) plus two small companion structures used in the TSV path. There
is no persistent storage; profiles live in memory for the duration of a
read → modify → write cycle.

## Entities

### `FormattingProfile` (JSON)

Captured on read from a JSON file; consumed on write to reproduce style.

> **Adapter note (2026-05-02)**: in the **json-five-backed** path
> (parse + mutate + serialize through `Json5Backend`), the *indent*,
> *separators*, *key_order*, and *line_ending* fields are *advisory* —
> the model itself preserves them byte-for-byte. The fields are still
> populated for diagnostics and for the **stdlib fallback path** used
> on (a) new-file writes (FR-006) and (b) parse failures, where the
> profile fully drives serialization. `bom` and `trailing_newline`
> are *load-bearing in both paths*: json-five does not preserve BOM,
> and json-five's trailing-newline behavior is normalized inside the
> adapter so the profile carries this state explicitly.

| Field | Type | Description | Source on read | Default (FR-006) | Path (json5 / stdlib) |
|---|---|---|---|---|---|
| `indent` | `str` | Indent unit — e.g. `"  "`, `"    "`, `"\t"`, or `""` for compact JSON. | json-five model (advisory) / hand-written byte scan (stdlib path) | `"  "` | model / driver |
| `separators` | `tuple[str, str]` | `(item_sep, key_sep)` passed to stdlib `json.dumps`. | model (advisory) / byte scan | `(",", ": ")` | model / driver |
| `line_ending` | `str` | `"\n"`, `"\r\n"`, or `"\r"`. | Predominant terminator across source lines. | `"\n"` | both (post-process) |
| `trailing_newline` | `bool` | Whether the source ended with a line terminator. | `bytes.endswith(line_ending)`. | `True` | both (post-process) |
| `bom` | `bool` | Whether the source began with the UTF-8 BOM. | `bytes.startswith(b"\xef\xbb\xbf")`. | `False` | both (post-process) |
| `compact` | `bool` (derived) | True iff `indent == ""`. | derived | `False` | both |

**Validation rules** (unchanged):
- `indent` must be `""` or a string of identical whitespace characters
  (all spaces or all tabs).
- `separators[1]` must end with the character `:` after stripping any
  trailing space.
- `line_ending` ∈ {`"\n"`, `"\r\n"`, `"\r"`}.

**State transitions**: Immutable (frozen dataclass). A modified write
that needs a different style (future `--normalize` mode) constructs a
new profile.

**Relationships**: One per JSON file read. Not shared across files
(spec Key Entities: "One profile per file; not shared across files.").
Stored on the `JSONDocument` that the profile-aware reader returns,
and accepted as an explicit kwarg on `write_json` for the new-file
path.

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
| `quoting` | `int` | One of `csv.QUOTE_*` constants. | `csv.Sniffer` with TSV defaults; falls back to `csv.QUOTE_MINIMAL`. | `csv.QUOTE_MINIMAL` (`0`) |

> **Note (2026-05-08)**: an earlier draft of this row described a richer
> ``dialect: csv.Dialect (subset)`` field. ``csv.Dialect`` is a class
> object, not a value-type that fits cleanly into a frozen dataclass,
> and TSV's delimiter is always ``\t``, so the field collapsed to just
> ``quoting: int``. The contract document and the implementation
> already use this shape; this row is the doc catching up.

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

### `JSONDocument` (new, 2026-05-02)

The format-preserving JSON document type returned by
`read_json_with_profile` and accepted by `write_json`. Implements
`collections.abc.MutableMapping[str, Any]` so call sites use it like a
plain dict.

| Slot | Type | Description |
|---|---|---|
| `_model` | `Any` (opaque, backend-defined) | The parsed model (a json-five `JSONText` for `Json5Backend`). Private; do not access from outside `_format/`. |
| `_backend` | `JSONBackend` | The backend instance whose methods drive every read/mutation. |
| `profile` | `FormattingProfile` | Public — formatting context carried alongside the model. |

**Methods (`MutableMapping` interface)**:
- `__getitem__(key) -> Any` — return Python value (dict for nested
  objects, list for arrays, etc.).
- `__setitem__(key, value)` — append-if-new (FR-005), replace-if-exists.
  Routes through `backend.set_value` / `backend.append_key`.
- `__delitem__(key)` — routes through `backend.delete_key`.
- `__iter__() -> Iterator[str]` — yields keys in source order.
- `__len__() -> int` — number of top-level keys.
- `__contains__(key) -> bool` — fast key presence check.

**Convenience methods**:
- `to_dict() -> dict` — fully-materialized plain-Python view (useful
  for legacy code paths that need a real dict).
- `keys() / values() / items()` — inherited from `MutableMapping`.

**Nested-object semantics**:
- `__getitem__` for an object-typed value returns a plain `dict`, not a
  nested `JSONDocument`. Local mutation of that dict does not
  propagate back. To write a nested change:
  ```python
  nested = doc["Nested"]
  nested["NewKey"] = "value"
  doc["Nested"] = nested            # MUST assign back
  ```
- This is documented as the explicit semantics in `quickstart.md`.
  Rationale: research.md R13.

**State transitions**: mutable. Mutations route through the backend
synchronously; no buffering.

**Relationships**: One per JSON file read. The `JSONDocument` and the
`FormattingProfile` it holds are paired 1:1. Independent of any other
file's `JSONDocument`.

---

### `JSONBackend` Protocol (new, 2026-05-02)

The contract any JSON backend must satisfy. Lives in
`bids_utils._format._json_backend`.

```python
from typing import Any, Protocol

class JSONBackend(Protocol):
    def parse(self, source: bytes) -> Any: ...
    def serialize(self, model: Any, profile: FormattingProfile) -> bytes: ...
    def detect_profile(self, source: bytes) -> FormattingProfile: ...
    def get_keys(self, model: Any) -> list[str]: ...
    def get_value(self, model: Any, key: str) -> Any: ...
    def set_value(self, model: Any, key: str, value: Any) -> None: ...
    def append_key(self, model: Any, key: str, value: Any) -> None: ...
    def delete_key(self, model: Any, key: str) -> None: ...
```

**Concrete implementation**: `Json5Backend` (the only one shipped).
Defenses against upstream footguns are listed in research.md R1.1 and
tested in `tests/test_format_json_backend.py`.

**Relationships**: A `JSONDocument` holds a reference to one
`JSONBackend` instance. Within one process, all `JSONDocument`s share
a module-level `_default_backend = Json5Backend()` instance — the
backend is stateless across calls (the `ModelDumper` state bug is
contained inside `serialize`, which constructs a fresh dumper per
invocation).

---

## Module entities

### `_format/` package (replaces previously-planned single `_format.py`)

#### `_format/_profile.py`
- `FormattingProfile`, `TSVFormattingProfile`, `TextFormattingProfile`
  (frozen dataclasses).
- `DEFAULT_JSON_PROFILE`, `DEFAULT_TSV_PROFILE`, `DEFAULT_TEXT_PROFILE`
  constants (FR-006).

#### `_format/_write.py`
- `write_if_changed(path: Path, new_bytes: bytes) -> bool` — returns
  True iff a write occurred (FR-007).

#### `_format/_json.py`
Public-internal surface for JSON I/O. **Does NOT import `json5`** —
that import is confined to `_format/_json_backend.py`.
- `JSONDocument` class (above).
- `parse_json(source: bytes) -> tuple[JSONDocument, FormattingProfile]`
- `serialize_json(data: JSONDocument | dict, profile: FormattingProfile) -> bytes`
  — polymorphic on input type (see plan.md "serialize_json
  polymorphism").

#### `_format/_json_backend.py`
The **only** module that imports from `json5.*`.
- `JSONBackend` Protocol.
- `Json5Backend` concrete implementation with all R1.1 defenses.
- Module-level `_default_backend = Json5Backend()` instance.

#### `_format/_tsv.py` (logic, not the existing `bids_utils._tsv`)
- `detect_tsv_profile(source: bytes) -> TSVFormattingProfile`
- `serialize_tsv(rows, profile, changed_indices=None) -> bytes`

#### `_format/_text.py`
- `detect_text_profile(source: bytes) -> TextFormattingProfile`
- `serialize_text(text: str, profile: TextFormattingProfile) -> bytes`

#### `_format/__init__.py`
Re-exports the public-internal surface so call sites can write
`from bids_utils._format import JSONDocument, FormattingProfile,
write_if_changed, …` without reaching into private module files.

### `bids_utils._io` (modified)

Public additions/changes (backward-compatible):

- `read_json_with_profile(path, vcs, mode) -> tuple[JSONDocument | None, FormattingProfile | None]`
  — returns a `JSONDocument` (NOT a plain dict) when parse succeeds.
- `write_json(path, data, vcs, profile=None) -> bool` — `data` may be
  either a `JSONDocument` (preferred — preservation path) or a plain
  `dict` (stdlib path, used for new files / migrations from
  legacy callers). Returns True iff a write occurred.
- Existing legacy `read_json(path, vcs, mode) -> dict | None` keeps
  its plain-dict return type for callers that only read; internally
  it constructs a `JSONDocument` and returns `doc.to_dict()`.
- New: `read_text_with_profile(path, vcs, mode) -> tuple[str | None, TextFormattingProfile | None]`
  and `write_text(path, text, vcs, profile=None) -> bool`.

### `bids_utils._tsv` (modified)

- `read_tsv_with_profile(path, vcs, annexed_mode) -> tuple[list[dict], TSVFormattingProfile]`
- `write_tsv(path, rows, vcs, profile=None, changed_indices=None) -> bool`
  — optional `profile=`, optional `changed_indices=` for row-splice
  semantics (research R5).

---

## Data flow (read → modify → write)

### JSON (json-five-backed adapter path)

```
file bytes ──► Json5Backend.parse        ──► model ───────────────────┐
              + Json5Backend.detect_profile ─► profile (bom, trailing) ┐│
                                                                      ││
                                              ──► JSONDocument(model, ││
                                                                profile)
                                                                       │
                                            ◄ caller mutates as a dict ◄┘
                                              doc["X"] = "y"
                                              del doc["Z"]
                                              (routes through backend)
                                                                       │
                                                                       ▼
                                              Json5Backend.serialize  ──► bytes
                                              (fresh ModelDumper, BOM
                                              prepend, trailing-newline
                                              normalization)
                                                                       │
                                                                       ▼
                                                              write_if_changed
                                                                       │
                                                                       ▼
                                                                file on disk
                                                          (or: no write, clean VCS)
```

### JSON (stdlib fallback / new-file path)

```
plain dict ───────────────────────────────────► json.dumps(data, indent=…,
                                                  separators=…, ensure_ascii=False)
                                                       │
profile ─────────────────────────────────────────────► │ (post-process: BOM,
                                                       │  line-ending substitution,
                                                       │  trailing newline)
                                                       ▼
                                                     bytes
                                                       │
                                                       ▼
                                              write_if_changed
                                                       │
                                                       ▼
                                                file on disk
```

### TSV / text

(Unchanged: stdlib `csv` for TSV; raw bytes manipulation for text;
both use the profile to drive line-ending / BOM / trailing-newline.)

This realizes FR-013 (profile carried with content), FR-007 (no-op
suppression at the byte boundary), FR-005 (key-order preservation via
the json-five model + `append_key` at end), and FR-011 (single funnel
for every write — the polymorphic `serialize_json` handles both
adapter and stdlib paths).
