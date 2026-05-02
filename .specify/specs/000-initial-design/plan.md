# Implementation Plan: bids-utils — Core Library & CLI

**Branch**: `000-initial-design` | **Date**: 2026-04-03 (last revised 2026-05-02) | **Spec**: [000-initial-design.md](../000-initial-design.md)
**Input**: Feature specification from `.specify/specs/000-initial-design.md`

> **Plan revision log (2026-05-02)** — incorporates Session 2026-04-27 clarifications addressing GH issue #14:
> - **CLI surface change (BREAKING for unreleased API)**: `rename` becomes mv-like `rename SRC [SRC ...] DST` (FR-039). The `--set`/`--delete` entity-mutation semantics move to a new sibling command `edit-filename` (FR-040). The chosen name is `edit-filename` (not `edit-entities`) because it covers `--set-suffix` in addition to entity edits.
> - **New requirements**: FR-037 (deferred future `normalize` command — TODO), FR-038 (full-literal-stem sidecar discovery for non-BIDS source files), FR-039, FR-040, FR-041 (non-BIDS-source robustness across 5 commands), FR-042 (per-test git-worktree fixture pattern + adversarial-suffix injection helper), FR-043 (batch / glob input for `rename` and `edit-filename`, atomic at the batch level — applies the same edit across many files / subjects / sessions in one invocation), SC-009 (validator pre+post coverage), SC-010 (batch-edit coverage).
> - **Reshaped phases**: Phase 2 split into 2a (`rename SRC DST`) + 2b (`edit-filename`); new Phase 1d (test fixture pattern); Phase 5 gains a non-BIDS-source sweep step; Phase 2a gains cross-container detection logic; Phase 2b includes batch / glob support out-of-the-box.

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
| I. Do No Harm | PASS | Every operation validates affected entities; `--dry-run` mandatory; atomic operations. FR-041 + SC-009 strengthen this for non-BIDS-named source files (no silent skipping). |
| II. Schema-Driven | PASS | All BIDS knowledge from `bidsschematools`; multi-version support; FR-033 audit ensures schema/rule sync across all 6 deprecation levels |
| III. Library-First | PASS | Every CLI command maps to a public library function. New `edit-filename` (FR-040) follows the same pattern (`bids_utils.edit_filename.edit_filename()`). |
| IV. CLI Excellence | PASS | `--dry-run`, `--json`, `-v`/`-q`, meaningful exit codes for every command. The new `rename SRC DST` shape is more idiomatic (mv-like) and removes the overloaded `--set` from `rename`. |
| V. Test-First | PASS | TDD enforced; `bids-examples` sweep testing; randomized testing for coverage. FR-042 introduces a generic per-test `git worktree` fixture pattern + adversarial-suffix injection helper; SC-009 mandates per-command non-BIDS-source coverage. |
| VI. Performance | PASS | Lazy evaluation; no full-dataset loading for single-entity operations |
| VII. VCS Awareness | PASS | Auto-detect git/git-annex/DataLad; use VCS primitives when present. The worktree-based test fixture also exercises VCS plumbing more naturally than `shutil.copytree`. |
| VIII. Observability | PASS | Structured logging; JSON change manifests; dry-run parity. Cross-container `rename` clearly reports both move + entity rewrite. |
| IX. Simplicity | PASS | Flat module structure; composition over monoliths; YAGNI. `rename` and `edit-filename` are deliberately split single-purpose verbs; cross-container `rename` delegates to `edit-filename` semantics rather than duplicating logic. |
| X. Versioning | PASS | SemVer; automated releases via intuit/auto. The `rename --set` removal is a breaking pre-1.0 API change — release notes MUST call this out. |
| XI. DRY | PASS | Duplication detection in CI (pylint + jscpd). Filename-rewrite logic lives in one place (`edit_filename` core), invoked by both `rename` (cross-container case) and `edit-filename`. |

## Project Structure

### Documentation (this feature)

```text
.specify/specs/000-initial-design/
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
├── _io.py               # Content-aware file I/O (annexed content policy enforcement)
├── _tsv.py              # Shared TSV read/write utilities (used by _scans.py, _participants.py)
├── _scans.py            # _scans.tsv read/write/update operations
├── _participants.py     # participants.tsv read/write/update operations
├── _sidecars.py         # Sidecar discovery (find all associated files for a BIDS file)
├── _dataset.py          # Dataset-level operations (find root, read dataset_description)
├── rename.py            # File rename: pure mv-like SRC→DST (Story 1, FR-039)
├── edit_filename.py     # In-place entity-level edits (FR-040, new sibling to rename)
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
    ├── rename.py         # bids-utils rename SRC DST (mv-like, FR-039)
    ├── edit_filename.py  # bids-utils edit-filename (FR-040)
    ├── migrate.py        # bids-utils migrate
    ├── metadata.py       # bids-utils metadata {aggregate,segregate,audit}
    ├── subject.py        # bids-utils subject-rename, bids-utils remove
    ├── session.py        # bids-utils session-rename
    ├── merge.py          # bids-utils merge
    ├── split.py          # bids-utils split
    └── run.py            # bids-utils remove-run

tests/
├── conftest.py          # Shared fixtures (tmp BIDS datasets, bids-examples access)
├── test_rename.py       # Unit + integration tests for rename SRC DST
├── test_edit_filename.py  # Tests for edit-filename (FR-040) — entity set/delete + order
├── test_migrate.py      # Migration tests (multi-version)
├── test_metadata.py     # Metadata manipulation tests
├── test_subject.py      # Subject operations tests
├── test_session.py      # Session operations tests
├── test_merge.py        # Merge tests
├── test_split.py        # Split tests
├── test_run.py          # Run removal tests
├── test_io.py           # Content-aware I/O tests (annexed modes)
├── test_vcs.py          # VCS integration tests
├── test_cli.py          # CLI smoke tests
├── test_cli_common.py   # Tests for shared CLI options/decorators
├── test_tsv.py          # Tests for shared TSV utilities
└── integration/
    ├── test_bids_examples.py     # Sweep tests against bids-examples
    ├── _worktree_fixture.py      # FR-042: per-test git worktree of bids-examples
    ├── _nonbids_inject.py        # FR-042: injection helper (__dup-NN, +mine, --crap, _test)
    └── test_nonbids_sources.py   # SC-009: 5 commands × non-BIDS-source fixtures
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

### Phase 1b: Annexed Content Handling (FR-022)

**Goal**: All file reads work correctly on git-annex/DataLad datasets via a `--annexed` policy option.

**Steps**:
1. **Foundation types**: Add `AnnexedMode` enum and `ContentNotAvailableError` to `_types.py`. Add `annexed_mode` field to `BIDSDataset`.
2. **VCS protocol extension**: Extend `VCSBackend` protocol with four new methods:
   - `has_content(path) -> bool` / `get_content(paths)` — for reads
   - `unlock(paths)` / `add(paths)` — for writes (unlock locked annexed files before modification, re-annex after)
   - Implementations: `NoVCS`/`Git` → trivial (always True, no-op for unlock, `git add` for add); `GitAnnex` → check symlink target, `git annex get/unlock/add`; `DataLad` → `datalad get/unlock`, `git annex add`.
3. **Content-aware I/O** (`_io.py`):
   - `ensure_content(path, vcs, mode)` — enforces `--annexed` policy for reads
   - `ensure_writable(path, vcs)` — unlocks locked annexed files before writes (always, regardless of `--annexed` mode)
   - `mark_modified(paths, vcs)` — calls `vcs.add()` after writes to re-annex files
   - `read_json(path, vcs, mode)` / `write_json(path, data, vcs)` — content-aware JSON I/O
4. **Wire through existing code**: Update `_tsv.read_tsv`/`write_tsv` with optional VCS/mode params. Update all callers. Replace inline JSON reads/writes in `metadata.py` (~6 read + ~3 write sites) and `migrate.py` (~11 read + ~6 write sites) with `_io` helpers.
5. **CLI wiring**: Add `--annexed` to Click group with `envvar="BIDS_UTILS_ANNEXED"`. `load_dataset()` sets `annexed_mode` on the returned `BIDSDataset`.
6. **Tests**: Mock VCS tests for all four modes. Unlock/add lifecycle tests. Integration test with real git-annex repo (locked files, content present/absent).

**Dependencies**: Phase 1 complete. Can be done at any point after Phase 1, but should be done before real-world usage on annexed datasets.

### Phase 1c: Symlink Safety & Dry-Run Detail (FR-003, FR-023, FR-024)

**Goal**: Fix the `is_file()` symlink bug that silently skips annexed data files during rename operations. Enhance `--dry-run` to show per-file detail. Add annex operation logging.

**Steps**:
1. **Symlink bug fix (T092)**: Audit all `is_file()` calls used for file iteration. Replace with `not path.is_dir()` in `session.py`, `subject.py`, `run.py`, `split.py`, `merge.py`, `_sidecars.py`, `migrate.py`. Keep `is_file()` where checking for file existence (not iteration).
2. **Annex test fixture (T093)**: `tmp_annex_dataset` in conftest.py — git-annex repo with locked symlinks alongside regular files.
3. **Regression tests (T094)**: Session/subject/file rename on annexed dataset — verify all files including symlinks are renamed.
4. **Dry-run detail (T095-T096)**: `--dry-run=overview|detailed`. Update `common_options`, ensure all library functions populate per-file `Change` entries. `output_result` renders overview vs detailed.
5. **Annex logging (T097)**: INFO-level logging for get/unlock/add operations in `_io.py`.
6. **Tests (T098)**: Verify `--dry-run=detailed` output.

**Dependencies**: Phase 1b complete. BLOCKS real-world usage on annexed datasets.

### Phase 1d: Integration Test Fixture Pattern (FR-042)

**Goal**: Establish a generic, reusable per-test fixture pattern based on `git worktree` over the local `bids-examples` clone, plus an injection helper for adversarial non-BIDS source filenames. Replaces (for new tests) the existing `_copy_dataset` + `git reset --hard` pattern from the 2026-04-10 testing clarifications.

**Steps**:
1. **Worktree fixture** (`tests/integration/_worktree_fixture.py`):
   - Pytest fixture `bids_examples_worktree(dataset_id)` that:
     - Resolves the local `bids-examples` clone (already a submodule, per Phase 0).
     - Generates a unique throwaway path under the test's `tmp_path`.
     - Runs `git worktree add --detach <unique_path> <ref>` to materialise the dataset.
     - Yields the worktree path.
     - On teardown: `git worktree remove --force <unique_path>` (and `git worktree prune` is **avoided** — see CLAUDE.md global rule).
   - Variant: `bids_examples_worktree_annexed(dataset_id)` — additionally enables annex (force annex of all data files) for git-annex coverage (SC-008).
2. **Non-BIDS injection helper** (`tests/integration/_nonbids_inject.py`):
   - `inject_nonbids_suffixes(worktree_root, *, kinds=("dup",), seed=0, count=2) -> list[Path]`:
     - Deterministically (seeded) selects `count` data files (and their sidecars) per `kind`.
     - For each selected file with stem `S` and ext `E`, creates an additional file `S<suffix><E>` (and sidecars sharing the new full literal stem) where suffix comes from the `kinds` set:
       - `"dup"` → `__dup-01` (heudiconv-style)
       - `"plus_mine"` → `+mine`
       - `"crap"` → `--crap`
       - `"test"` → `_test`
     - Returns the list of created (non-BIDS) primary file paths so tests can target them.
   - Helper is content-aware: copies bytes of the original file (or symlinks under git-annex) so the injected files are real, not zero-byte placeholders.
3. **Validator wrapper**:
   - `assert_validator_flags(worktree_root, *, expected_files: list[Path])` — runs `bids-validator-deno` on the worktree and asserts every file in `expected_files` is named in the output. Skips gracefully if validator absent.
   - `assert_validator_passes(worktree_root, *, ignore_pre_existing: list[str] | None = None)` — runs the validator after the operation and asserts it passes (modulo any pre-existing warnings captured before injection).
4. Tests for the fixture itself: `test_worktree_fixture.py` exercises both variants (creation, isolation between tests, teardown leaves the host clone untouched).

**Dependencies**: Phase 1 complete (or in parallel — the fixture has no app-code dependency).
**Used by**: All Phase 2/2b/5 integration tests, plus the SC-009 sweep in Phase 5b.

### Phase 2a: File Rename (Story 1 — P1, FR-038, FR-039)

**Goal**: `bids-utils rename SRC DST` (mv-like) working end-to-end with full test coverage, including non-BIDS source files (heudiconv `__dup-NN`) and cross-container moves.

**Steps**:
1. Implement `rename.py` library function (`rename_file`):
   - Accept `(dataset, src_path, dst_path)` — pure mv semantics (NO `--set`/`--delete`).
   - Discover all sidecars for `src_path` via FR-038 **full-literal-stem** matching (so `..._bold__dup-01.nii.gz` finds `..._bold__dup-01.json`, etc.). The stem-matching rule must NOT canonicalize/strip non-BIDS trailing segments before comparison.
   - **Cross-container detection**: parse `src_path` and `dst_path`'s subject/session containers (the leading `sub-XX/[ses-YY]/` directory components). If they differ AND `dst_path` is a directory or its filename does not already encode the destination's `sub-`/`ses-`, delegate to `edit_filename` (Phase 2b) to rewrite the `sub-`/`ses-` (and any other container-implied) entity labels in the destination filename. The result MUST satisfy entity-order normalization (FR-035).
   - If `dst_path` is an existing directory, the destination filename is derived from `src_path`'s filename plus the cross-container rewrite.
   - Check for conflicts (target file already exists) → exit code 2 (FR-011).
   - Execute renames (filesystem or VCS via `_vcs`); update `_scans.tsv` rows referencing the old filename; invoke FR-025 BIDS URI fixup helper.
2. Implement `cli/rename.py`:
   - `bids-utils rename SRC DST` — positional arguments only; reject `--set`/`--delete` (deferred to `edit-filename`).
   - Wire up `--dry-run`, `--json`, `-v`/`-q`.
3. Tests:
   - Unit tests: cross-container detection, sidecar discovery on non-BIDS stems (FR-038), conflict detection.
   - Integration tests using the FR-042 worktree fixture: bare rename within a directory; rename into a different `sub-`/`ses-` directory (verify entity rewrite); rename of a heudiconv-style `__dup-NN` file.
   - `bids-examples` sweep using worktree fixture: rename a random file, validate dataset.
4. **Migration note**: existing `tests/test_rename.py` uses the old `--set entity=value` API. Those tests must be either rewritten to use `edit-filename` (Phase 2b) or — where they exercised pure path-rename — converted to `rename SRC DST` form. Old `--set` tests are NOT preserved as backward-compat shims.

**Dependencies**: Phase 1 + Phase 1d complete. Phase 2b is co-required because cross-container rename delegates to it.

### Phase 2b: Entity-level Edits — `edit-filename` (FR-040)

**Goal**: New sibling command `bids-utils edit-filename SRC --set/--delete ...` that performs in-place entity-level edits (no directory change). Canonical home for the `--set`/`--delete` semantics formerly attached to `rename`.

**Steps**:
1. Implement `edit_filename.py` library function (`edit_filename`):
   - Parse `src_path` into `BIDSPath`; FR-038 full-literal-stem sidecar discovery (must accept non-BIDS source filenames and preserve unrecognized trailing segments verbatim).
   - Apply `--set KEY=VALUE` (overwrite/insert) and `--delete KEY` (remove) operations against the `BIDSPath.entities` dict.
   - Reorder entities to schema order (FR-035) before reconstructing the filename.
   - File operation is an in-place rename within the same directory (no cross-container logic). Conflicts → exit code 2.
   - Update `_scans.tsv` rows; invoke FR-025 BIDS URI fixup.
2. Implement `cli/edit_filename.py`:
   - `bids-utils edit-filename SRC --set KEY=VALUE [--set ...] [--delete KEY ...]` — repeatable flags.
   - `--dry-run`, `--json`, `-v`/`-q`.
3. Tests:
   - Unit tests: set/delete combinations, entity-order reordering (FR-035 regression), preservation of non-BIDS trailing segments (`__dup-NN` → preserved).
   - Integration tests using the FR-042 worktree fixture and injection helper.
4. `rename`'s cross-container code path imports `edit_filename`'s entity-rewrite core — single source of truth (Principle XI / DRY).

**Dependencies**: Phase 1 + Phase 1d complete. Phase 2a depends on this for cross-container delegation.

### Phase 3: Migration — 1.x Deprecations (Story 2 — P1)

**Goal**: `bids-utils migrate` handles all known 1.x deprecations with tiered migration levels.

**Prior art**: PR #2282's decorator-based migration registry pattern is directly reusable. It implements `@registry.register(name="...", version="1.10.0", description="...")` with dry-run support and JSON-safe operations. Currently handles 3 migrations; bids-utils must extend to cover all 1.x deprecations.

**Steps**:
1. **Extend MigrationRule schema** (FR-029):
   - Add `level` field to `MigrationRule`: `safe` | `advisory` | `non-auto-fixable`
   - Add `condition` field for contextual rules (e.g., `AcquisitionDuration` requires `VolumeTiming`)
   - This formalizes the migration record schema (analogous to validator schemas, cf. dandi-cli)
2. **Implement CLI filtering** (FR-030):
   - `--level=safe` (default), `--level=advisory`, `--level=all`
   - `--rule-id=ID` / `--exclude-rule=ID` for per-rule control
   - `--mode=auto` (default: currently non-interactive; PTY-aware interactive prompting deferred to T103/post-MVP), `--mode=non-interactive`, `--mode=interactive` (planned)
   - Library API: `level`, `mode`, `rule_ids`, `exclude_rules` parameters on `migrate_dataset()`
3. Implement migration rule engine in `migrate.py`:
   - Scan deprecation markers from ALL schema levels (not just `rules/checks`):
     - `rules/sidecars` — field-level `deprecated` annotations
     - `rules/checks` — validator check rules
     - `objects/metadata` — description-text deprecation markers
     - `objects/enums` — deprecated enum values
     - `objects/columns` — column-level deprecations
     - `objects/suffixes` — deprecated suffixes
   - Determine dataset's current version (from `dataset_description.json`)
   - Determine target version (default: current released 1.x; or `--to`)
   - Compute applicable rules (between source and target versions), filtered by level/id
4. Implement transformation handlers — **safe level** (auto-applied by default):
   - **Metadata field rename**: `BasedOn` → `Sources`, `RawSources` → `Sources`
   - **Value format changes**: relative paths → BIDS URIs in `IntendedFor`, `AssociatedEmptyRoom`, `Sources`
   - **DOI format**: bare DOIs → URI format in `DatasetDOI`
   - **Suffix deprecations**: `_phase` → `_part-phase_bold` (delegates to `rename`)
   - **Enum value renames**: `ElektaNeuromag` → `NeuromagElektaMEGIN`, `KitYokogawa` → `YokogawaKIT`
   - **Cross-file moves**: `ScanDate` → `acq_time` in `_scans.tsv`
   - **Conditional field rename**: `AcquisitionDuration` → `FrameAcquisitionDuration` (only when `VolumeTiming` present) (FR-026)
   - **TSV column value**: `"89+"` string → numeric `89` in `participants.tsv` `age` column, unit-aware (FR-027)
5. Implement transformation handlers — **advisory level** (opt-in via `--level=advisory`):
   - **Field removal**: `DCOffsetCorrection` deprecated in iEEG (FR-031)
   - **Field removal**: `HardcopyDeviceSoftwareVersion` deprecated in MRI (FR-032)
   - **HIPAA age cap**: numeric values > 89 → `89` in `age` column (rule id: `age_cap_89`)
   - **Conditional field rename (ambiguous)**: `AcquisitionDuration` without `VolumeTiming` — prompt user
6. Implement transformation handlers — **non-auto-fixable** (report only):
   - **Ambiguous suffixes**: `T2star`, `FLASH`, `PD` — flag with replacement options
   - **Deprecated templates**: `fsaverage3-6`, `fsaveragesym`, `UNCInfant*V2x` — flag, no clear auto-replacement
7. **Age migration unit-awareness** (FR-027):
   - Check `participants.json` sidecar for `"Units"` on the `age` column definition
   - If units are non-year (months, days, etc.), skip the 89-year threshold rules and warn
   - TODO: upstream resolution needed on column unit override mechanism (bids-standard/bids-specification#1633)
8. Implement `cli/migrate.py`:
   - `--to VERSION`, `--level LEVEL`, `--mode MODE`, `--rule-id ID`, `--exclude-rule ID`
   - `--dry-run`, `--json`
   - Report: per-file changes with rule references, grouped by level
9. Tests:
   - Unit tests for each transformation type
   - Integration tests with crafted datasets containing known deprecations
   - `bids-examples` sweep: find datasets with older `BIDSVersion`, migrate, validate
   - Test `--level` and `--mode` filtering

**Dependencies**: Phase 2 complete (uses rename for suffix changes)

### Phase 3b: Schema Deprecation Audit (FR-033, FR-034)

**Goal**: Automated coverage tracking to ensure all schema-declared deprecations have corresponding migration rules.

**Steps**:
1. **Audit function** in `migrate.py`:
   - Scan all deprecation markers in the loaded `bidsschematools` schema across all levels
   - Compare against registered `MigrationRule` entries
   - Return list of unimplemented deprecations with schema location
   - Recommend: upgrade `bidsschematools` if not latest, or file an issue
2. **CLI subcommand**: `bids-utils migrate --audit`
   - Report: implemented vs missing migration rules, schema version
3. **Test**: `test_migration_coverage_vs_schema` — fails when new schema deprecations appear without corresponding rules
4. **GitHub issue template** (FR-034): `.github/ISSUE_TEMPLATE/missing-migration-rule.yml`
   - Fields: schema version, deprecation location, affected field/suffix/enum, expected behavior
   - Labels: `migration`, `schema-gap`

**Dependencies**: Phase 3 complete (needs the migration registry to audit against)

### Phase 3c: BIDS URI Fixup Helper (FR-025)

**Goal**: Generic helper that updates `bids:` URIs when files are renamed, reusable across all operations.

**Steps**:
1. **Library function** in new `_bids_uri.py`:
   - `update_bids_uris(dataset, old_to_new: dict[Path, Path], dry_run) -> list[Change]`
   - Scan JSON metadata fields known to contain BIDS URIs: `IntendedFor`, `AssociatedEmptyRoom`, `Sources`, `DerivedFrom`
   - Match `bids::` scheme URIs against the old→new mapping
   - Update matched URIs
2. **Wire into rename/migrate/subject-rename/session-rename**: call after file renames
3. **Deferred**: cross-dataset URIs (`bids:ds001::...`), partial path matches
4. Tests: unit tests with crafted JSON sidecars containing BIDS URIs

**Dependencies**: Phase 1 complete (needs `_io.py` for JSON read/write)

### Phase 4: Migration — BIDS 2.0 (Story 3 — P1)

**Goal**: `bids-utils migrate --to 2.0` handles 2.0 breaking changes.

**Steps**:
1. **Concrete 2.0 rule** (FR-028, bids-standard/bids-2-devel#14):
   - Rename `participants.tsv` → `subjects.tsv` (file rename via VCS)
   - Rename `participants.json` → `subjects.json` (file rename via VCS)
   - Rename `participant_id` column → `subject_id` in the renamed file
   - Update `BIDSVersion` in `dataset_description.json`
   - Update BIDS URIs referencing the old file via FR-025 helper
2. Extend migration rule engine for additional 2.0-specific transformations:
   - Entity renames (TBD from schema)
   - Structural reorganization (TBD from schema)
   - Metadata key changes (TBD from schema)
3. Ensure cumulative application: 1.x deprecations applied first, then 2.0 changes
4. Handle ambiguities: flag items requiring human judgment, skip with clear reporting
5. Tests:
   - Unit tests for participants→subjects rename
   - Integration tests against 2.0-dev schema
   - Validate migrated datasets against 2.0 validator schema

**Dependencies**: Phase 3 + 3c complete
**Note**: Additional 2.0 transformations depend on BIDS 2.0 schema stabilization. This phase will iterate as the schema evolves.

### Phase 5: Subject & Session Operations (Stories 4, 5 — P2)

**Goal**: `bids-utils subject-rename` and `bids-utils session-rename` working.

**Steps**:
1. **Subject rename** (`subject.py`):
   - Rename subject directory
   - Rename all files within (compose on `edit_filename` for in-directory entity rewrite, NOT `rename` — `rename` is for cross-path mv)
   - Update `participants.tsv`
   - Update all `_scans.tsv` files
   - Optionally process `sourcedata/`, `.heudiconv/`, `derivatives/`
2. **Session rename** (`session.py`):
   - Similar to subject rename but for session entity
   - Special case: move-into-session (`'' → ses-01`)
3. CLI wrappers with standard options
4. Tests:
   - bids-examples sweep for both operations (using FR-042 worktree fixture)
   - Edge cases: sourcedata, derivatives, git-annex

**Dependencies**: Phase 2a + Phase 2b complete

### Phase 5b: Non-BIDS Source Robustness Sweep (FR-041, SC-009)

**Goal**: Each of the five file-touching commands (`rename`, `edit-filename`, `remove`, `subject-rename`, `session-rename`) is verified to operate correctly on non-BIDS-named source files.

**Steps**:
1. Audit each of the five commands for the FR-041 checklist:
   - (a) Sidecar discovery uses FR-038 full-literal-stem matching.
   - (b) File iteration uses `not path.is_dir()` AND matches BIDS directory-data files (FR-023, FR-036).
   - (c) `_scans.tsv` updates handle non-BIDS filenames (the row's filename is matched literally).
   - (d) Non-BIDS trailing segments are preserved verbatim (no implicit canonicalization until FR-037 lands).
2. Implement `tests/integration/test_nonbids_sources.py`:
   - Parameterised over the five commands × `kinds=("dup", "plus_mine", "crap", "test")` from FR-042's injection helper.
   - For each parameter combination:
     - Materialise a `bids-examples` worktree; record validator state pre-injection (warnings only).
     - Inject adversarial suffixes; **pre-validate** and assert validator now flags the injected files (per SC-009).
     - Run the command under test (with appropriate args) on the injected files.
     - **Post-validate** and assert: no new validator findings beyond the recorded pre-injection warnings; injected files were renamed/removed cleanly (not silently skipped).
   - Validator-dependent assertions skip gracefully when `bids-validator-deno` is absent.
3. `migrate` is **explicitly out of scope** for FR-041 in this release (decision recorded in Session 2026-04-27 Q3).

**Dependencies**: Phase 5 complete (all five commands implemented). Phase 1d (worktree fixture + injection helper).

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
| BIDS 2.0 schema not finalized | High | Medium | Phase 4 is designed to iterate; 1.x migration is independently useful. participants→subjects (issue #14) is concrete and implementable now. |
| git-annex edge cases | Medium | Medium | Test with locked/unlocked files; handle gracefully when content unavailable |
| Large dataset performance | Low | Medium | Profile early; use lazy evaluation; batch file operations |
| Cross-platform path handling | Medium | Low | Use `pathlib` throughout; test on Windows CI |
| Schema deprecation drift | Medium | Medium | FR-033 audit test fails on new deprecations; CI catches gaps automatically |
| Age column units ambiguity | Medium | Low | Unit-aware migration; skip non-year units with warning; upstream issue bids-specification#1633 tracks resolution |
| Advisory migration data loss | Low | High | Advisory rules require opt-in (`--level=advisory`); interactive mode prompts per-finding |
| `rename --set` removal breaks downstream | Low | Medium | Pre-1.0 API; release notes call out the split; existing tests rewritten to `edit-filename` (Phase 2b). |
| `git worktree` fixture cleanup races | Low | Low | Per-test unique paths; never call `git worktree prune` (CLAUDE.md global rule); explicit `worktree remove --force` in teardown only for paths the fixture created. |
| Non-BIDS injection helper masks real BIDS regressions | Low | Medium | SC-009 requires both pre-validation (assert injected files are flagged) and post-validation (assert validator passes); pre-existing warnings captured separately so non-BIDS sweep doesn't paper over genuine regressions. |

## Complexity Tracking

No constitution violations identified. The plan follows all 11 principles:
- Single project structure (Principle IX)
- All BIDS knowledge from schema (Principle II)
- Library functions before CLI (Principle III)
- TDD with bids-examples (Principle V)
- Filename-rewrite logic centralised in `edit_filename` and reused by cross-container `rename` (Principle XI / DRY)

## Pending Consistency Updates (post-2026-04-27 clarifications)

The following dependent design artifacts MUST be updated separately (per project rule that `/speckit.*` commands are bounded operations and dependent docs are *reported*, not auto-cascaded):

1. **`contracts/library-api.md`**:
   - `rename_file()` signature: drop `set_entities` and `new_suffix` parameters; replace with positional `dst_path: str | Path`. Add note about cross-container detection (delegates to `edit_filename`).
   - Add new `bids_utils.edit_filename` API section: `edit_filename(dataset, path, *, set_entities, delete_entities, dry_run, ...)`.
   - CLI Contract: update rename flags (positional `SRC DST`); add `edit-filename` command flags (`--set KEY=VALUE`, `--delete KEY`).
2. **`data-model.md`**:
   - `BIDSPath.from_path()` must explicitly preserve unrecognized non-BIDS trailing segments verbatim (no canonicalization). Document the FR-038 full-literal-stem rule alongside Sidecar Discovery.
3. **`quickstart.md`**:
   - Replace `bids-utils rename ... --set task=nback` examples with `bids-utils rename SRC DST` form, plus a parallel `bids-utils edit-filename SRC --set task=nback` example.
4. **`tasks.md`**:
   - Add new task block for Phase 1d (worktree fixture + injection helper + validator wrapper).
   - Split existing rename tasks into 2a (`rename SRC DST`) + 2b (`edit-filename`).
   - Add Phase 5b non-BIDS-source sweep tasks (parameterised across 5 commands × 4 suffix kinds).
   - Mark old `--set`-based tasks/tests for rewrite, not deletion.
5. **`spec.md` (000-initial-design.md)** — already updated in Session 2026-04-27.
6. **`docs/`** (mkdocs site, if any rename docs exist) — once `quickstart.md` is updated, propagate.
7. **`CHANGELOG`** / release notes — flag the breaking pre-1.0 CLI change for `rename`.

These updates SHOULD be requested explicitly (e.g., re-run `/speckit.tasks` for tasks.md, or address the others manually) before proceeding to `/speckit.implement` for the new phases.
