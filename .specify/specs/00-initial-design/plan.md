# Implementation Plan: bids-utils — Core Library & CLI

**Branch**: `00-initial-design` | **Date**: 2026-04-03 | **Spec**: [00-initial-design.md](../00-initial-design.md)
**Input**: Feature specification from `.specify/specs/00-initial-design.md`

## Summary

Build `bids-utils`, a Python library and CLI for manipulating BIDS datasets. Core operations: file renaming (with sidecar/scans tracking), schema-driven migration (1.x deprecations + 2.0), metadata aggregation/segregation, subject/session renaming, and dataset merge/split. All operations are schema-driven via `bidsschematools`, VCS-aware, and validated against `bids-examples`.

## Technical Context

**Language/Version**: Python 3.10+ (per spec assumptions)
**Primary Dependencies**: `bidsschematools` (schema access), `click` (CLI framework)
**Optional Dependencies**: `bids-validator-deno` (testing), `bids2table` (dataset querying, if needed)
**Storage**: Filesystem (BIDS datasets are directory trees)
**Testing**: `pytest` orchestrated by `tox` (with `tox-uv`)
**Target Platform**: Linux, macOS, Windows (cross-platform filesystem operations)
**Project Type**: Library + CLI
**Performance Goals**: O(n) in affected files, not O(n²) in total dataset size. Usable on 1000-subject datasets.
**Constraints**: Must not corrupt valid BIDS datasets. Must support git/git-annex/DataLad workflows.
**Scale/Scope**: Single-developer start, community contributions expected. ~10 CLI commands at maturity.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Do No Harm | PASS | Every operation validates affected entities; `--dry-run` mandatory; atomic operations |
| II. Schema-Driven | PASS | All BIDS knowledge from `bidsschematools`; multi-version support designed in |
| III. Library-First | PASS | Every CLI command maps to a public library function |
| IV. CLI Excellence | PASS | `--dry-run`, `--json`, `-v`/`-q`, meaningful exit codes for every command |
| V. Test-First | PASS | TDD enforced; `bids-examples` sweep testing; randomized testing for coverage |
| VI. Performance | PASS | Lazy evaluation; no full-dataset loading for single-entity operations |
| VII. VCS Awareness | PASS | Auto-detect git/git-annex/DataLad; use VCS primitives when present |
| VIII. Observability | PASS | Structured logging; JSON change manifests; dry-run parity |
| IX. Simplicity | PASS | Flat module structure; composition over monoliths; YAGNI |
| X. Versioning | PASS | SemVer; automated releases via intuit/auto |
| XI. DRY | PASS | Duplication detection in CI (pylint + jscpd) |

## Project Structure

### Documentation (this feature)

```text
.specify/specs/00-initial-design/
├── plan.md              # This file
├── research.md          # Prior art & ecosystem analysis
├── data-model.md        # Core data model design
├── quickstart.md        # Getting started guide
├── contracts/           # Interface contracts
└── tasks.md             # Implementation tasks (via /speckit.tasks)
```

### Source Code (repository root)

```text
pyproject.toml           # Single source of truth for deps, metadata, build
tox.ini                  # Test orchestration (pytest, lint, type, duplication)
mkdocs.yml               # Documentation site config

src/bids_utils/
├── __init__.py          # Package root, version
├── _types.py            # Shared type definitions (PathLike, Entity, etc.)
├── _vcs.py              # VCS detection and operations (git mv, git annex, datalad)
├── _schema.py           # Schema loading and querying helpers (wraps bidsschematools)
├── _tsv.py              # Shared TSV read/write utilities (used by _scans.py, _participants.py)
├── _scans.py            # _scans.tsv read/write/update operations
├── _participants.py     # participants.tsv read/write/update operations
├── _sidecars.py         # Sidecar discovery (find all associated files for a BIDS file)
├── _dataset.py          # Dataset-level operations (find root, read dataset_description)
├── rename.py            # File rename: core operation (Story 1)
├── migrate.py           # Schema-driven migration (Stories 2, 3)
├── metadata.py          # Metadata aggregate/segregate/audit (Story 6)
├── subject.py           # Subject rename/remove (Stories 4, 7)
├── session.py           # Session rename/move-into-session (Story 5)
├── merge.py             # Dataset merge (Story 9)
├── split.py             # Dataset split (Story 10)
├── run.py               # Run remove with reindexing (Story 8)
└── cli/
    ├── __init__.py      # CLI entry point (click group)
    ├── _common.py       # Shared CLI options (--dry-run, --json, -v/-q, --force)
    ├── rename.py         # bids-utils rename
    ├── migrate.py        # bids-utils migrate
    ├── metadata.py       # bids-utils metadata {aggregate,segregate,audit}
    ├── subject.py        # bids-utils subject-rename, bids-utils remove
    ├── session.py        # bids-utils session-rename
    ├── merge.py          # bids-utils merge
    ├── split.py          # bids-utils split
    └── run.py            # bids-utils remove-run

tests/
├── conftest.py          # Shared fixtures (tmp BIDS datasets, bids-examples access)
├── test_rename.py       # Unit + integration tests for rename
├── test_migrate.py      # Migration tests (multi-version)
├── test_metadata.py     # Metadata manipulation tests
├── test_subject.py      # Subject operations tests
├── test_session.py      # Session operations tests
├── test_merge.py        # Merge tests
├── test_split.py        # Split tests
├── test_run.py          # Run removal tests
├── test_vcs.py          # VCS integration tests
├── test_cli.py          # CLI smoke tests
├── test_cli_common.py   # Tests for shared CLI options/decorators
├── test_tsv.py          # Tests for shared TSV utilities
└── integration/
    └── test_bids_examples.py  # Sweep tests against bids-examples
```

**Structure Decision**: Single-project layout with `src/` layout (PEP 517/518 compliant). Library modules at `src/bids_utils/`, CLI as a subpackage. Private modules prefixed with `_` for internal utilities. This is the simplest structure that supports the library-first + CLI wrapper architecture.

## Implementation Phases

### Phase 0: Project Scaffolding (Foundation)

**Goal**: Working project skeleton with CI, linting, type checking, and an empty CLI.

**Steps**:
1. Initialize project using copier-astral template (or manual setup with uv)
2. Configure `pyproject.toml` with dependency layers (test/devel/ci)
3. Configure `tox.ini` with envs: py310-py314, lint, type, duplication
4. Set up GitHub Actions workflow (invoke tox via tox-gh-actions)
5. Configure mkdocs with basic structure
6. Create `src/bids_utils/__init__.py` with version
7. Create `src/bids_utils/cli/__init__.py` with click group entry point
8. Set up intuit/auto for automated releases
9. Add `bids-examples` as a git submodule for testing
10. Verify: `tox` passes, `bids-utils --help` works, CI green

**Dependencies**: None (first phase)

### Phase 1: Core Infrastructure (Private Modules)

**Goal**: Build the shared utilities that all commands depend on.

**Steps** (implement in this order, each with tests first):

1. **`_types.py`**: Type definitions — `BIDSPath`, `Entity` (key-value pair), `EntitySet`, path-like protocols
2. **`_dataset.py`**: Find dataset root (walk up to `dataset_description.json`), read `BIDSVersion`, detect BIDS validity basics
3. **`_schema.py`**: Wrap `bidsschematools.schema.load_schema()` — load by version, query entities, query suffixes, query sidecar extensions, query deprecation rules
4. **`_vcs.py`**: Detect VCS type (none, git, git-annex, datalad). Provide `move()`, `remove()`, `commit()` that dispatch to the right backend. Handle dirty-tree detection.
5. **`_sidecars.py`**: Given a BIDS file path, find all associated sidecars by replacing extension with each known sidecar extension (from schema). Handle the case where sidecar might be at a higher level (inheritance).
6. **`_scans.py`**: Read/write `_scans.tsv`. Find the scans file for a given file. Update/remove entries by filename.
7. **`_participants.py`**: Read/write `participants.tsv`. Add/remove/rename subject entries.

**Dependencies**: Phase 0 complete

### Phase 2: File Rename (Story 1 — P1)

**Goal**: `bids-utils rename` working end-to-end with full test coverage.

**Steps**:
1. Implement `rename.py` library function:
   - Parse source file path into entities
   - Accept entity overrides (e.g., `--set task=nback`)
   - Compute new filename from modified entities
   - Discover all sidecars for the source file
   - Check for conflicts (target already exists)
   - Execute renames (filesystem or VCS)
   - Update `_scans.tsv` if applicable
2. Implement `cli/rename.py`:
   - Wire up arguments, `--dry-run`, `--json`, `-v`/`-q`
   - Human-readable and JSON output modes
3. Tests:
   - Unit tests for entity parsing, filename construction
   - Integration tests with tmp BIDS datasets
   - `bids-examples` sweep: rename a random file, validate dataset

**Dependencies**: Phase 1 complete

### Phase 3: Migration — 1.x Deprecations (Story 2 — P1)

**Goal**: `bids-utils migrate` handles all known 1.x deprecations.

**Prior art**: PR #2282's decorator-based migration registry pattern is directly reusable. It implements `@registry.register(name="...", version="1.10.0", description="...")` with dry-run support and JSON-safe operations. Currently handles 3 migrations; bids-utils must extend to cover all 1.x deprecations.

**Steps**:
1. Implement migration rule engine in `migrate.py`:
   - Adopt/adapt the migration registry pattern from PR #2282
   - Load deprecation rules from schema (`rules/checks/deprecations.yml`)
   - Load metadata definitions (for field renames) from `objects/metadata.yaml`
   - Load enum definitions (for value renames) from `objects/enums.yaml`
   - Determine dataset's current version (from `dataset_description.json`)
   - Determine target version (default: current released 1.x; or `--to`)
   - Compute applicable rules (between source and target versions)
2. Implement transformation handlers:
   - **Metadata field rename**: `BasedOn` → `Sources`, etc.
   - **Value format changes**: relative paths → BIDS URIs in `IntendedFor`, `Sources`, etc.
   - **Suffix deprecations**: `_phase` → `_part-phase_bold` (delegates to `rename`)
   - **Enum value renames**: `ElektaNeuromag` → `NeuromagElektaMEGIN`
   - **Cross-file moves**: `ScanDate` → `acq_time` in `_scans.tsv`
3. Implement `cli/migrate.py`:
   - `--to VERSION`, `--dry-run`, `--json`
   - Report: per-file changes with deprecation rule references
4. Tests:
   - Unit tests for each transformation type
   - Integration tests with crafted datasets containing known deprecations
   - `bids-examples` sweep: find datasets with older `BIDSVersion`, migrate, validate

**Dependencies**: Phase 2 complete (uses rename for suffix changes)

### Phase 4: Migration — BIDS 2.0 (Story 3 — P1)

**Goal**: `bids-utils migrate --to 2.0` handles 2.0 breaking changes.

**Steps**:
1. Extend migration rule engine for 2.0-specific transformations:
   - Entity renames (TBD from schema)
   - Structural reorganization (TBD from schema)
   - Metadata key changes (TBD from schema)
2. Ensure cumulative application: 1.x deprecations applied first, then 2.0 changes
3. Handle ambiguities: flag items requiring human judgment, skip with clear reporting
4. Tests:
   - Integration tests against 2.0-dev schema
   - Validate migrated datasets against 2.0 validator schema

**Dependencies**: Phase 3 complete
**Note**: Exact 2.0 transformations depend on BIDS 2.0 schema stabilization. This phase may need iteration as the schema evolves.

### Phase 5: Subject & Session Operations (Stories 4, 5 — P2)

**Goal**: `bids-utils subject-rename` and `bids-utils session-rename` working.

**Steps**:
1. **Subject rename** (`subject.py`):
   - Rename subject directory
   - Rename all files within (compose on `rename`)
   - Update `participants.tsv`
   - Update all `_scans.tsv` files
   - Optionally process `sourcedata/`, `.heudiconv/`, `derivatives/`
2. **Session rename** (`session.py`):
   - Similar to subject rename but for session entity
   - Special case: move-into-session (`'' → ses-01`)
3. CLI wrappers with standard options
4. Tests:
   - bids-examples sweep for both operations
   - Edge cases: sourcedata, derivatives, git-annex

**Dependencies**: Phase 2 complete

### Phase 6: Metadata Operations (Story 6 — P2)

**Goal**: `bids-utils metadata {aggregate,segregate,audit}` working.

**Prior art**: IP-freely (@Lestropie) implements a graph-based relational model with bidirectional m4d/d4m mappings and ruleset-based inheritance behaviors. Key learnings: three inheritance behaviors (merge for `.json`, nearest for `.bval`/`.bvec`, forbidden for `.tsv`), parameterized rulesets, applicability rules (ancestor directory + entity subset matching + suffix matching). bids-utils should adopt the m4d/d4m pattern and add schema integration.

**Steps**:
1. **Aggregate** (`metadata.py`):
   - Walk the inheritance hierarchy bottom-up
   - Identify common key-value pairs across all files at a level
   - Hoist common pairs to parent-level sidecar
   - Handle missing files correctly (do NOT aggregate if any file is absent)
   - Support scoped operation (per-subject, per-session)
   - Support `--mode copy|move`
2. **Segregate**: Push metadata down to leaf level (inverse of aggregate)
3. **Audit**: Report metadata values that are neither fully unique nor fully equivalent
4. CLI wrappers
5. Tests:
   - Verify resolved metadata is unchanged after aggregate + segregate round-trip
   - bids-examples sweep

**Dependencies**: Phase 1 complete (independent of rename/migrate)

### Phase 7: Remove & Merge/Split (Stories 7, 8, 9, 10 — P3)

**Goal**: Lower-priority operations.

**Steps**:
1. **Remove subject/session** (`subject.py`): Delete directory tree, update participants/scans
2. **Remove run** (`run.py`): Delete run files, optionally reindex subsequent runs
3. **Merge** (`merge.py`): Combine datasets, handle conflicts, session placement
4. **Split** (`split.py`): Extract subset by suffix/datatype
5. CLI wrappers and tests

**Dependencies**: Phases 2, 5 complete

## Key Design Decisions

### 1. CLI Framework: Click

**Decision**: Use `click` for CLI.
**Why**: Mature, well-documented, supports subcommands naturally, good testing support via `CliRunner`. The alternative (`argparse`) requires more boilerplate for subcommand groups.

### 2. No PyBIDS Dependency

**Decision**: Core operations use `bidsschematools` directly, not PyBIDS.
**Why**: Per constitution — PyBIDS brings considerable transitive complexity. Core operations (rename, migrate, metadata) can be implemented with just `bidsschematools` + filesystem ops.

### 3. Entity Parsing: Custom, Schema-Driven

**Decision**: Parse BIDS filenames using entity definitions from the schema.
**Why**: Hardcoded entity lists would violate Principle II. The schema defines entity ordering and allowed values per datatype.

### 4. Atomic Operations via VCS

**Decision**: When VCS is present, each command is a single atomic operation (single commit).
**Why**: Makes operations reversible via `git revert`. When no VCS, operations are best-effort with clear reporting.

### 5. `_scans.tsv` and `participants.tsv` Updates Are Automatic

**Decision**: Every operation that renames/removes files automatically updates these files.
**Why**: Leaving stale references breaks dataset validity (Principle I).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `bidsschematools` API changes | Medium | High | Pin to compatible version range; abstract behind `_schema.py` |
| BIDS 2.0 schema not finalized | High | Medium | Phase 4 is designed to iterate; 1.x migration is independently useful |
| git-annex edge cases | Medium | Medium | Test with locked/unlocked files; handle gracefully when content unavailable |
| Large dataset performance | Low | Medium | Profile early; use lazy evaluation; batch file operations |
| Cross-platform path handling | Medium | Low | Use `pathlib` throughout; test on Windows CI |

## Complexity Tracking

No constitution violations identified. The plan follows all 11 principles:
- Single project structure (Principle IX)
- All BIDS knowledge from schema (Principle II)
- Library functions before CLI (Principle III)
- TDD with bids-examples (Principle V)
