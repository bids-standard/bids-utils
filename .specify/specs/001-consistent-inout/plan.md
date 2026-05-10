# Implementation Plan: Format-Preserving Input/Output for BIDS Files

**Branch**: `001-consistent-inout` | **Date**: 2026-05-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `.specify/specs/001-consistent-inout/spec.md`

## Summary

Make every bids-utils write of a JSON sidecar, TSV table, or plain-text BIDS
file mirror the source file's formatting style (indent, key order, line
endings, trailing-newline, BOM, separator style). Suppress writes whose
serialized bytes are byte-identical to disk so VCS history reflects only
semantic change.

**Approach**: Funnel every read/write site through a new internal package
`src/bids_utils/_format/`. The JSON path is implemented behind a small
**adapter layer**: a `JSONBackend` Protocol with one default implementation
backed by **`json-five`** (chosen empirically — `library-survey.md` §7
records 99.91% byte-identical round-trip across the entire bids-examples
corpus). The adapter pattern means a future backend swap (back to stdlib +
hand-rolled splicing, or to `json-source-map`, or to a vendored fork)
touches one file, not the call sites. TSV and plain-text paths use stdlib
(no equivalent library exists; their preservation requirements are simpler
and per-row splicing is straightforward).

The empirical research that produced this decision — including reproducer
scripts, the `ModelDumper` state bug, and the `key_value_pairs` read-only
property footgun in `json-five` — is documented in `library-survey.md`
§7.1–§7.4 and the bug demonstrators alongside this plan.

## Technical Context

**Language/Version**: Python 3.10+ (CI matrix: 3.10–3.14)
**Primary Dependencies**:
- **`json-five>=1.1.2,<2`** — NEW runtime dependency (PyPI distribution
  name `json-five`, import name `json5`). Pure-Python, ~1k LOC, MIT
  license, no transitive deps beyond `regex` + `sly`. Justified by §7.3
  empirical evidence; isolated behind the adapter so it can be removed.
- stdlib `json` (still used for: new-file writes, plain-dict input to
  `serialize_json`, fallback when `json-five` parse fails)
- stdlib `csv` (TSV path)
- `bidsschematools`, `click`, `packaging` (unchanged)
**Storage**: Filesystem (BIDS dataset trees on disk; optionally git/git-annex/DataLad working trees)
**Testing**: `pytest` orchestrated by `tox` (`tox-uv`); `bids-examples` git submodule for integration sweeps; `tmp_annex_dataset` fixture for symlink/locked-file paths
**Target Platform**: Linux/macOS/Windows (line-ending detection must handle CRLF, LF, CR)
**Project Type**: Single-package Python library + thin CLI (`src/bids_utils/`)
**Performance Goals**: SC-006 — dataset-wide operations ≤20% slower than today's naive rewrite baseline. `json-five` is pure-Python and slower than stdlib `json` per byte; the §7 corpus run completed within seconds for ~2,151 files, so the headroom on SC-006 is comfortable. Detection is O(file size) single-pass, on read only.
**Constraints**:
- FR-007 — no-op writes MUST be suppressed (compare final serialized bytes to disk bytes)
- FR-011 — uniform application across every write site (no second path)
- FR-013 — profile carried with parsed content (no double-read)
- **Adapter constraint**: `bids_utils._format._json_backend` is the only module that imports from `json5.*`. Every other module (call sites, tests, even `_format._json` itself) sees only the adapter's exported types.
**Scale/Scope**: ~thousands of sidecars per realistic dataset; bids-examples corpus is the integration target; touches `_io.py`, `_tsv.py`, `metadata.py`, `migrate.py`, `_dataset.py`, plus a new `_format/` package replacing the previously-planned single `_format.py` module

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluation of each principle from `.specify/memory/constitution.md` v1.5.0:

| Principle | Status | Notes |
|---|---|---|
| I. Do No Harm | PASS | Pure read/write refactor; no new mutating semantics. FR-012 still applies: correctness wins over preservation. The `json-five` adapter explicitly defends against the upstream `ModelDumper` state bug (fresh instance per call) and the `key_value_pairs` read-only property footgun (mutations route through the canonical `keys`/`values` lists with a length-mismatch assert before serialize). Both behaviors are tested at the adapter boundary. |
| II. Schema-Driven & Version-Flexible | PASS | Schema-orthogonal — operates on file bytes, not BIDS entity logic. |
| III. Library-First | PASS | `_format/` is library-internal. Public API (`read_json`, `write_json`, `read_tsv`, `write_tsv`) keeps current call signatures plus a profile-aware sibling. CLI is unchanged. The adapter Protocol IS the library-first contract for the JSON backend. |
| IV. CLI Excellence | PASS | No CLI surface change. Dry-run preservation handled by routing dry-run diff generation through `serialize_json`. |
| V. Test-First | PASS | Tasks phase will write tests first: profile detection unit tests, round-trip byte-identity tests, bids-examples integration sweep validating SC-001/002/003. The adapter's contract (Protocol shape + the two `json-five`-specific defenses) is also covered with explicit tests so a future backend swap is verifiable. |
| VI. Performance at Scale | PASS | §7 corpus benchmark completed comfortably; SC-006 budget (≤20%) has margin. If performance ever becomes an issue, the adapter pattern allows swapping in a faster backend without changing call sites. |
| VII. VCS Awareness | PASS | Uses existing `ensure_writable`/`mark_modified` lifecycle. No-op suppression strictly improves VCS interaction. |
| VIII. Observability | PASS | Dry-run output unaffected in shape; the diff it shows shrinks (FR per spec edge case). The adapter layer logs (debug-level) when it falls back from `json-five` to stdlib for a file `json-five` could not parse, so failures are visible. |
| IX. Simplicity & YAGNI | PASS — with one explicit choice | The adapter Protocol adds **one** indirection (a `JSONBackend` ABC/Protocol with one implementation). Per "YAGNI" we ship ONE backend (`json-five`-based); per the user's brief we keep the indirection so a swap is a one-file change. We do **not** ship a stdlib backend in parallel (would violate YAGNI) — the stdlib fallback for parse-failures is *inside* the json-five backend, not a parallel implementation. |
| X. Versioning | PASS | Backward-compatible MINOR change. Existing `read_json` / `write_json` keep their signatures. New profile-aware functions are siblings. Adding `json-five` as a runtime dep is a MINOR version bump per semver. |
| XI. DRY | PASS — IMPROVES | Today there are ~10 hand-written `json.dumps(data, indent=2) + "\n"` lines in `migrate.py` alone. This feature collapses them into one writer. |

**Result**: PASS — no Complexity Tracking entries needed. The single
"explicit choice" under Principle IX is the adapter Protocol; it is
justified by the brief and by `library-survey.md` §7.4 evidence that
`json-five`'s upstream API has known footguns, making isolation
prudent.

## Project Structure

### Documentation (this feature)

```text
.specify/specs/001-consistent-inout/
├── plan.md              # This file (/speckit.plan output)
├── spec.md              # Feature spec
├── research.md          # Phase 0 output (updated for json-five-via-adapter)
├── data-model.md        # Phase 1 output (updated)
├── quickstart.md        # Phase 1 output (updated minimally)
├── contracts/
│   └── io_contract.md   # Phase 1 output (updated)
├── library-survey.md    # Empirical evidence: §7 corpus run + manipulation findings
├── round_trip_repro.sh  # Reproducer used to discover the upstream bugs
├── json_five_modeldumper_state_bug*.py     # Bug demonstrators
├── json_five_keys_manipulation_bug.py
├── json_five_manipulation_probe.py
└── tasks.md             # Phase 2 output (regenerated by /speckit.tasks)
```

### Source Code (repository root)

```text
src/bids_utils/
├── _format/                       # NEW package (replaces previously-planned _format.py module)
│   ├── __init__.py                # Re-exports the public-internal surface
│   ├── _profile.py                # FormattingProfile, TSVFormattingProfile, TextFormattingProfile + DEFAULTS
│   ├── _write.py                  # write_if_changed
│   ├── _json.py                   # JSONDocument (MutableMapping wrapper) + parse_json + serialize_json (calls backend)
│   ├── _json_backend.py           # JSONBackend Protocol + Json5Backend (json-five adapter); ONLY module that imports json5
│   ├── _tsv.py                    # detect_tsv_profile + serialize_tsv (stdlib csv)
│   └── _text.py                   # detect_text_profile + serialize_text
├── _io.py                         # MODIFIED — read_json_with_profile / write_json grow profile-awareness; read_text_with_profile / write_text added
├── _tsv.py                        # MODIFIED — read_tsv_with_profile / write_tsv preserve dialect, line endings, column order
├── _dataset.py                    # MODIFIED — dataset_description.json read uses profile-aware reader
├── _sidecars.py                   # UNCHANGED (discovery only)
├── _participants.py               # UNCHANGED (delegates to _tsv)
├── _scans.py                      # UNCHANGED (delegates to _tsv)
├── _vcs.py                        # UNCHANGED
├── _types.py                      # UNCHANGED
├── metadata.py                    # MODIFIED — replace residual ad-hoc json.loads/dumps with profile-aware helpers
├── migrate.py                     # MODIFIED — replace ~10 ad-hoc json.dumps writes with _io.write_json (profile-preserving by default)
├── merge.py / split.py / rename.py / run.py / session.py / subject.py
│                                  # AUDIT — verify they go through _io/_tsv (most do already)
└── cli/                           # UNCHANGED — CLI emits machine output via json.dumps to stdout (out of scope)

tests/
├── test_io.py                     # MODIFIED — new round-trip + profile detection tests
├── test_tsv.py                    # MODIFIED — CRLF, column order, no-trailing-newline cases
├── test_format.py                 # NEW — unit tests for FormattingProfile detect/apply + JSONDocument MutableMapping behavior
├── test_format_json_backend.py    # NEW — adapter-boundary tests: Protocol conformance, ModelDumper-state defense, key-list-symmetry assert
├── integration/
│   └── test_format_preservation.py
│                                  # NEW — bids-examples sweep validating SC-001/002/003
└── (other test_*.py)              # AUDIT — confirm no fixture relied on json.dumps default formatting
```

**Structure Decision**: Single-project Python library (Option 1). The
feature is implemented as one new internal **package** `_format/` (not a
single file — the adapter layer earns its own module) plus modifications
to existing I/O entry points. The CLI layer is untouched. Module names
use the leading-underscore convention documented in `CLAUDE.md` for
private modules.

### Why a package, not one module

The original plan put everything in `_format.py`. The adapter shift makes
that file too crowded:
- Three dataclasses + 3 default constants
- One MutableMapping wrapper class (`JSONDocument`)
- Two free functions per format (detect + serialize) × 3 formats
- One Protocol + one backend implementation isolating `json-five`

Splitting into `_format/` keeps each file focused (≤200 LoC), keeps the
`json5` import surface to one file (the `_json_backend.py` invariant
above), and makes the "swap backend" operation a pure file-replacement.

## Adapter Layer Design

This section is the load-bearing addition to the previous plan. Full
shape lives in `data-model.md` and `contracts/io_contract.md`; the
summary here is what makes the rest of the documents interpretable.

### Three layers

```
┌──────────────────────────────────────────────────────────────┐
│  Call sites:  migrate.py, metadata.py, _dataset.py, ...      │
│  Use:         doc["X"] = "y"  (dict-like)                    │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 2:     _format._json.JSONDocument (MutableMapping)    │
│  Imports:     _format._json_backend                          │
│  Knows:       FormattingProfile, the backend Protocol        │
│  Does NOT:    import json5 directly                          │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 3:     _format._json_backend.JSONBackend (Protocol)   │
│               _format._json_backend.Json5Backend (impl)      │
│  Imports:     json5.*  ←  the ONLY module to do so           │
│  Defends:     against ModelDumper state bug                  │
│  Defends:     against key_value_pairs read-only footgun      │
│  Defends:     against keys/values length-mismatch corruption │
└──────────────────────────────────────────────────────────────┘
```

### `JSONDocument` — public-internal surface

`JSONDocument` is a `collections.abc.MutableMapping[str, Any]`. Call
sites use it like a dict:

```python
doc, profile = read_json_with_profile(path, vcs, mode)
doc["IntendedFor"] = ["new/path.nii.gz"]
del doc["DeprecatedField"]
write_json(path, doc, vcs, profile=profile)
```

Internally `JSONDocument` holds an opaque `model` (the json-five
`JSONText`) and routes every mutation through the backend Protocol.
Reads return Python values (lists, dicts, strings, numbers) materialized
on demand from the model nodes. Nested objects come back as plain
`dict` subtree views (no nested `JSONDocument`); modifying a nested
dict does *not* propagate back — to write a nested change, assign the
whole subtree: `doc["Subobj"] = {**doc["Subobj"], "k": "v"}`. This
trade-off keeps the API simple at the cost of one assignment for
nested edits; data-model.md §JSONDocument records the rationale.

### Backend Protocol

```python
class JSONBackend(Protocol):
    def parse(self, source: bytes) -> Any: ...                    # opaque "model"
    def serialize(self, model: Any, profile: FormattingProfile) -> bytes: ...
    def detect_profile(self, source: bytes) -> FormattingProfile: ...
    def get_keys(self, model: Any) -> list[str]: ...
    def get_value(self, model: Any, key: str) -> Any: ...
    def set_value(self, model: Any, key: str, value: Any) -> None: ...
    def append_key(self, model: Any, key: str, value: Any) -> None: ...
    def delete_key(self, model: Any, key: str) -> None: ...
```

Default implementation: `Json5Backend`. Every method is prepared for
the upstream footguns documented in `library-survey.md` §7.4 (read-only
`key_value_pairs` property, `ModelDumper` state bug, asymmetric
`keys`/`values` corruption, `KeyValuePair` NamedTuple immutability).

### `serialize_json` polymorphism

`_format._json.serialize_json` accepts either a `JSONDocument` (use
backend's `serialize`, byte-perfect round-trip) **or** a plain `dict`
(stdlib fallback path: `json.dumps(data, indent=profile.indent,
separators=profile.separators)` then BOM/line-ending/trailing-newline
post-processing). The plain-dict path is used for FR-006 new-file
writes where there is no source model to preserve from.

This polymorphism gives us "one writer" (FR-011) without forcing every
new-file caller to construct a fake `JSONDocument`.

### Swap criteria

The adapter layer makes a backend swap a one-file change. Triggers
that would justify a swap:

1. `json-five` becomes unmaintained (no commits / no release in 18
   months) — switch to a vendored fork or to a stdlib + json-source-map
   approach.
2. Performance regression beyond SC-006 — switch to a stdlib +
   surgical-splice backend (the R1 parking-lot option in `research.md`).
3. A second tricky bug surfaces in `json-five` that cannot be defended
   against in the adapter — switch backends.

The integration sweep in `tests/integration/test_format_preservation.py`
is the contract that any replacement backend must pass.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Constitution Check passed. The one judgment call (Principle IX, the
adapter indirection) is justified inline in the table above and by the
brief; it does not constitute a violation.
