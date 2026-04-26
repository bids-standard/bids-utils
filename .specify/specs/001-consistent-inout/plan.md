# Implementation Plan: Format-Preserving Input/Output for BIDS Files

**Branch**: `001-consistent-inout` | **Date**: 2026-04-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-consistent-inout/spec.md`

## Summary

Make every bids-utils write of a JSON sidecar, TSV table, or plain-text BIDS
file mirror the source file's formatting style (indent, key order, line
endings, trailing-newline, BOM, separator style). Suppress writes whose
serialized bytes are byte-identical to disk so VCS history reflects only
semantic change. Implementation funnels every existing read/write site
through a single I/O layer that returns parsed content alongside a captured
**FormattingProfile**, and uses that profile on write — replacing the ~15
ad-hoc `json.dumps(data, indent=2)` and `csv.DictWriter(...lineterminator="\n")`
call sites scattered across `migrate.py`, `metadata.py`, `_io.py`, `_tsv.py`,
and `_dataset.py`. No new runtime dependencies.

## Technical Context

**Language/Version**: Python 3.10+ (CI matrix: 3.10–3.14)
**Primary Dependencies**: stdlib `json`, stdlib `csv`, `bidsschematools`, `click`, `packaging` (no new runtime deps)
**Storage**: Filesystem (BIDS dataset trees on disk; optionally git/git-annex/DataLad working trees)
**Testing**: `pytest` orchestrated by `tox` (`tox-uv`); `bids-examples` git submodule for integration sweeps; `tmp_annex_dataset` fixture for symlink/locked-file paths
**Target Platform**: Linux/macOS/Windows (line-ending detection must handle CRLF, LF, CR)
**Project Type**: Single-package Python library + thin CLI (`src/bids_utils/`)
**Performance Goals**: SC-006 — dataset-wide operations ≤20% slower than today's naive rewrite baseline; format detection is O(file size) single-pass and only on read
**Constraints**: FR-007 — no-op writes MUST be suppressed (compare final serialized bytes to disk bytes); FR-011 — uniform application across every write site (no second path); FR-013 — profile carried with parsed content (no double-read)
**Scale/Scope**: ~thousands of sidecars per realistic dataset; bids-examples corpus is the integration target; touches `_io.py`, `_tsv.py`, `metadata.py`, `migrate.py`, `_dataset.py`, plus 1 new `_format.py` (or `_io_format.py`) module

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluation of each principle from `.specify/memory/constitution.md` v1.5.0:

| Principle | Status | Notes |
|---|---|---|
| I. Do No Harm | PASS | Pure read/write refactor; no new mutating semantics. FR-012 explicitly guarantees correctness wins over preservation when they conflict. |
| II. Schema-Driven & Version-Flexible | PASS | Feature is schema-orthogonal — operates on file bytes, not BIDS entity logic. No schema-version coupling. |
| III. Library-First | PASS | New `_format.py` is library-internal. Public API (`read_json`, `write_json`, `read_tsv`, `write_tsv`) keeps current signatures, gaining an optional returned profile and a profile-on-write path. CLI gets nothing new. |
| IV. CLI Excellence | PASS | No CLI surface change. Edge case in spec (dry-run honoring preservation) is addressed by routing dry-run diff generation through the same serializer. |
| V. Test-First | PASS | Tasks phase will write tests first: profile detection unit tests, round-trip byte-identity tests, bids-examples integration sweep validating SC-001/002/003. |
| VI. Performance at Scale | PASS | Detection is single-pass O(n) on read; no-op-write check is byte compare, cheaper than the avoided write. SC-006 budgets ≤20%. |
| VII. VCS Awareness | PASS | Uses existing `ensure_writable`/`mark_modified` lifecycle. No-op suppression strictly improves VCS interaction (no spurious annex churn on locked symlinks). |
| VIII. Observability | PASS | Dry-run output unaffected in shape; the diff it shows shrinks (FR per spec edge case). No new log keys required; can add a `formatting_profile` field in JSON change manifests if useful (deferred). |
| IX. Simplicity & YAGNI | PASS | One profile dataclass + one detect/apply pair per format. No plugin system. FR-014's "extensibility contract" is satisfied by the dataclass + reader/writer pair shape, not by abstract base classes. |
| X. Versioning | PASS | Backward-compatible MINOR change: existing `read_json` returns `dict\|None` today; new return shape (`(dict, profile)`) is exposed via a sibling function or keyword opt-in to avoid breaking import sites we don't own. |
| XI. DRY | PASS — IMPROVES | Today there are ~10 hand-written `json.dumps(data, indent=2) + "\n"` lines in `migrate.py` alone (see grep evidence). This feature collapses them into one writer, eliminating duplication that pylint/jscpd would flag. |

**Result**: PASS — no Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
.specify/specs/001-consistent-inout/
├── plan.md              # This file (/speckit.plan output)
├── spec.md              # Feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── io_contract.md   # Phase 1 output — internal I/O contract
└── tasks.md             # Phase 2 output (created later by /speckit.tasks)
```

### Source Code (repository root)

```text
src/bids_utils/
├── _format.py           # NEW — FormattingProfile dataclass + detect/apply for JSON/TSV/text
├── _io.py               # MODIFIED — read_json/write_json grow profile-awareness; new read_text_with_profile/write_text_with_profile
├── _tsv.py              # MODIFIED — read_tsv/write_tsv preserve dialect, line endings, column order
├── _dataset.py          # MODIFIED — dataset_description.json read uses profile-aware reader
├── _sidecars.py         # UNCHANGED (discovery only, no I/O)
├── _participants.py     # UNCHANGED (delegates to _tsv)
├── _scans.py            # UNCHANGED (delegates to _tsv)
├── _vcs.py              # UNCHANGED
├── _types.py            # UNCHANGED
├── metadata.py          # MODIFIED — replace residual ad-hoc json.loads/dumps with profile-aware helpers
├── migrate.py           # MODIFIED — replace ~10 ad-hoc json.dumps writes with _io.write_json (profile-preserving by default)
├── merge.py / split.py / rename.py / run.py / session.py / subject.py
│                        # AUDIT — verify they go through _io/_tsv (most do already)
└── cli/                 # UNCHANGED — CLI emits machine output via json.dumps to stdout, which is not a "file write" and is out of scope

tests/
├── test_io.py           # MODIFIED — new round-trip + profile detection tests
├── test_tsv.py          # MODIFIED — CRLF, column order, no-trailing-newline cases
├── test_format.py       # NEW — unit tests for FormattingProfile detect/apply
├── integration/
│   └── test_format_preservation.py
│                        # NEW — bids-examples sweep validating SC-001/002/003
└── (other test_*.py)    # AUDIT — confirm no fixture relied on json.dumps default formatting
```

**Structure Decision**: Single-project Python library (Option 1 in template).
The feature is implemented as one new internal module (`_format.py`) plus
modifications to existing I/O entry points. No new top-level packages. The
CLI layer is untouched. Module name uses the leading-underscore convention
documented in `CLAUDE.md` for private modules.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Constitution Check passed without violations. Table omitted.
