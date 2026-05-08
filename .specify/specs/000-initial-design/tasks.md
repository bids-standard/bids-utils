# Tasks: bids-utils — Core Library & CLI

**Input**: Design documents from `/specs/000-initial-design/`
**Prerequisites**: plan.md, spec (000-initial-design.md), research.md, data-model.md, contracts/library-api.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 0: Project Scaffolding

**Purpose**: Working project skeleton with CI, linting, type checking, and an empty CLI.

- [X] T001 Initialize project with `uv`: create `pyproject.toml` with dependency layers (`test`/`devel`/`ci`), package metadata, `[project.scripts]` entry point for `bids-utils` CLI
- [X] T002 Create `tox.ini` with envs: `py310`–`py314`, `lint`, `type`, `duplication`; configure `tox-gh-actions` mapping
- [X] T003 [P] Set up GitHub Actions CI workflow (`.github/workflows/ci.yml`) — install `.[ci]`, run `tox`
- [X] T004 [P] Create `src/bids_utils/__init__.py` with `__version__`
- [X] T005 [P] Create `src/bids_utils/cli/__init__.py` with `click` group entry point (`bids-utils --help` works)
- [X] T006 [P] Add `bids-examples` as a git submodule for testing
- [X] T007 [P] Configure `mkdocs.yml` with basic documentation structure
- [X] T008 [P] Set up intuit/auto for automated releases (`.autorc`, labels)
- [X] T009 [P] Create `tests/conftest.py` with shared fixtures (tmp BIDS dataset factory, `bids-examples` path helper)
- [X] T010 Verify: `tox` passes, `bids-utils --help` works, CI green

**Checkpoint**: Project skeleton is functional, CI is green, CLI prints help.

---

## Phase 1: Core Infrastructure (Private Modules)

**Purpose**: Shared utilities that ALL commands depend on. BLOCKS all user story work.

- [X] T011 Implement `src/bids_utils/_types.py`: `Entity` (frozen dataclass: key+value), `BIDSPath` (entities dict, suffix, extension, datatype; `from_path()`, `to_filename()`, `to_relative_path()`, `with_entities()`, `with_suffix()`, `with_extension()`), `OperationResult`, `Change` dataclasses per data-model.md
- [X] T012 [P] Write tests for `_types.py` in `tests/test_types.py` — entity parsing, filename round-tripping, `BIDSPath.from_path()` with various BIDS filenames
- [X] T123 [US1] Fix `BIDSPath.to_filename()` in `src/bids_utils/_types.py` to emit entities in schema-defined order (FR-035). When a `BIDSSchema` is available, `to_filename()` MUST reorder entities according to `BIDSSchema.entity_order()` before assembling the filename. Without a schema, preserve insertion order (best-effort). Add test in `tests/test_types.py`: `BIDSPath(entities={"sub":"01","task":"rest","run":"99","recording":"bipolar"}).to_filename(schema=...)` produces entities in schema order, not insertion order.
- [X] T013 Implement `src/bids_utils/_dataset.py`: `BIDSDataset` dataclass (`root`, `bids_version`, `schema_version`, `vcs`), `BIDSDataset.from_path()` (walk up to find `dataset_description.json`), read `BIDSVersion`
- [X] T014 [P] Write tests for `_dataset.py` in `tests/test_dataset.py` — discovery from nested paths, missing `dataset_description.json`, version extraction
- [X] T015 Implement `src/bids_utils/_schema.py`: `BIDSSchema` class wrapping `bidsschematools.schema.load_schema()` — load by version, `entity_order()`, `sidecar_extensions(suffix)`, `is_valid_entity()`, `deprecation_rules(from_ver, to_ver)`, `metadata_field_info()`
- [X] T016 [P] Write tests for `_schema.py` in `tests/test_schema.py` — schema loading, entity queries, sidecar extension queries, deprecation rule extraction
- [X] T017 Implement `src/bids_utils/_vcs.py`: `VCSBackend` protocol, `NoVCS`, `Git`, `GitAnnex`, `DataLad` implementations with `move()`, `remove()`, `is_dirty()`, `commit()`. Detection order: DataLad → GitAnnex → Git → NoVCS
- [X] T018 [P] Write tests for `_vcs.py` in `tests/test_vcs.py` — detection logic, `git mv` integration, fallback to filesystem ops
- [X] T019 Implement `src/bids_utils/_sidecars.py`: given a BIDS file path + schema, find all associated sidecars by replacing extension with each known sidecar extension
- [X] T020 [P] Write tests for `_sidecars.py` in `tests/test_sidecars.py` — sidecar discovery for `.nii.gz` with `.json`, `.bvec`, `.bval`; missing sidecars; inheritance-level sidecars
- [X] T021 Implement `src/bids_utils/_scans.py`: read/write `_scans.tsv`, find scans file for a given file, update/remove entries by filename
- [X] T022 [P] Write tests for `_scans.py` in `tests/test_scans.py` — read/write round-trip, entry update, entry removal, missing `_scans.tsv`
- [X] T023 Implement `src/bids_utils/_participants.py`: read/write `participants.tsv`, add/remove/rename subject entries
- [X] T024 [P] Write tests for `_participants.py` in `tests/test_participants.py` — CRUD operations, duplicate detection

**Checkpoint**: All private infrastructure modules pass tests. No user-facing features yet.

---

## Phase 1b: Annexed Content Handling (FR-022)

**Purpose**: Content-aware I/O layer so all commands work correctly on git-annex/DataLad datasets where file content may not be locally available. Retroactively completes the VCS integration promise from Phase 1.

**Independent Test**: Run `bids-utils --annexed=get session-rename` on a DataLad dataset with annexed `_scans.tsv` — content is auto-fetched, rename succeeds.

### Foundation

- [X] T086 Add `AnnexedMode` enum (`error`, `get`, `skip-warning`, `skip`) and `ContentNotAvailableError` exception to `src/bids_utils/_types.py`. Add `annexed_mode: AnnexedMode` field to `BIDSDataset` in `src/bids_utils/_dataset.py` (default: `AnnexedMode.ERROR`).
- [X] T087 Extend `VCSBackend` protocol in `src/bids_utils/_vcs.py` with four new methods: `has_content(path: Path) -> bool`, `get_content(paths: list[Path]) -> None` for reads; `unlock(paths: list[Path]) -> None`, `add(paths: list[Path]) -> None` for writes. Implement for all backends: `NoVCS` all no-op/True; `Git` has_content=True, unlock=no-op, add=`git add`; `GitAnnex` checks symlink target, runs `git annex get/unlock/add`; `DataLad` uses `datalad get/unlock`, `git annex add`.

### Content-aware I/O layer

- [X] T088 Create `src/bids_utils/_io.py` with: `ensure_content(path, vcs, annexed_mode)` enforcing `--annexed` policy for reads; `ensure_writable(path, vcs)` calling `vcs.unlock()` for locked annexed files before writes (always, independent of `--annexed` mode); `mark_modified(paths, vcs)` calling `vcs.add()` after writes to re-annex; `read_json(path, vcs, mode) -> dict | None` and `write_json(path, data, vcs)` helpers.
- [X] T089 Wire content-aware I/O through existing code: update `_tsv.read_tsv`/`write_tsv` to accept optional `vcs`/`annexed_mode` params; update callers in `_scans.py`, `_participants.py`, `session.py`, `subject.py`, `rename.py` to pass `dataset.vcs`/`dataset.annexed_mode`. Replace inline `json.loads(f.read_text())` in `metadata.py` and `migrate.py` with `_io.read_json()`. Replace inline `f.write_text(json.dumps(...))` with `_io.write_json()` (which brackets with ensure_writable/mark_modified).

### CLI wiring

- [X] T090 Add `--annexed` option to CLI group in `src/bids_utils/cli/__init__.py` (with `envvar="BIDS_UTILS_ANNEXED"`). Update `load_dataset()` in `_common.py` to set `annexed_mode` on the returned `BIDSDataset` from Click context. All existing subcommands inherit automatically.

### Tests

- [X] T091 Write tests: `tests/test_io.py` for `ensure_content`/`ensure_writable`/`mark_modified`/`read_json`/`write_json` with all four annexed modes using mock VCS; `tests/test_vcs.py` additions for `has_content`/`get_content`/`unlock`/`add` on all backends; `tests/test_cli_common.py` additions for `--annexed` group option flow and env var; integration test with actual git-annex repo (locked files: read requires get+unlock, write unlocks then re-adds).

**Checkpoint**: `bids-utils --annexed=get session-rename` works on a git-annex dataset — content is fetched, locked files are unlocked for modification, and re-annexed after writes. All existing tests still pass. `--annexed=error` gives an informative error pointing to `--annexed=get`.

---

## Phase 2: User Story 1 — Rename a BIDS File (Priority: P1)

**Goal**: `bids-utils rename` working end-to-end — rename a file and all its sidecars, update `_scans.tsv`, use VCS when present.

**Independent Test**: Rename a file in any `bids-examples` dataset, run BIDS validator, confirm validity.

### Implementation for User Story 1

- [X] T025 [US1] Implement `src/bids_utils/rename.py`: `rename_file()` per library-api.md contract — parse source into `BIDSPath`, apply entity overrides, compute new filename, discover sidecars, check for conflicts, execute renames (filesystem or VCS), update `_scans.tsv`
- [X] T026 [US1] Write tests for `rename.py` in `tests/test_rename.py`:
  - Rename with entity override (`--set task=nback`) renames file + sidecars
  - `_scans.tsv` entry updated after rename
  - Conflict detection (target already exists → error)
  - Non-BIDS filenames (e.g., `_bold__dup-01.json`) handled gracefully
  - Dry-run returns changes without modifying files
  - VCS (`git mv`) used when in git repo
- [X] T027 [US1] Implement `src/bids_utils/cli/rename.py`: click command wiring `--set`, `--dry-run`, `--json`, `-v`/`-q`
- [X] T028 [US1] Implement `src/bids_utils/cli/_common.py`: shared CLI decorators/options (`--dry-run`, `--json`, `-v`/`-q`, `--force`, `--include-sourcedata`, `--schema-version`)
- [X] T029 [US1] Write CLI smoke tests in `tests/test_cli.py` — `bids-utils rename --help`, `bids-utils rename --dry-run` on a fixture dataset
- [X] T030 [US1] Write `bids-examples` sweep test in `tests/integration/test_bids_examples.py` — rename a random file in each dataset, validate

**Checkpoint**: `bids-utils rename` is functional. Single-file rename with sidecars, scans, VCS all working.

---

## Phase 3: User Story 2 — Migrate Dataset within BIDS 1.x (Priority: P1)

**Goal**: `bids-utils migrate` resolves all 1.x deprecations using schema-derived rules.

**Independent Test**: Take a BIDS 1.4-era dataset, run `bids-utils migrate`, verify deprecation warnings eliminated.

### Implementation for User Story 2

- [X] T031 [US2] Implement migration rule engine in `src/bids_utils/migrate.py`: `MigrationRule`, `MigrationPlan`, `MigrationFinding` dataclasses per data-model.md; migration registry (decorator-based, adapted from PR #2282 pattern); load deprecation rules from schema (`rules/checks/deprecations.yml`, `objects/metadata.yaml`, `objects/enums.yaml`)
- [X] T032 [US2] Implement metadata field rename handler: `BasedOn` → `Sources`, `RawSources` → `Sources`. Merge logic MUST handle: (a) existing `Sources` as string + incoming value as array (normalize to array first), (b) both `BasedOn` AND `RawSources` present alongside existing `Sources` (3-way merge). Add tests for mixed-type merge and 3-way merge scenarios. (Note: `ScanDate` handled by T036; `DCOffsetCorrection` by T105; `AcquisitionDuration` by T104.) *(Reimplementation needed: current merge logic broken for mixed string/array types.)*
- [X] T033 [US2] Implement value format change handler: relative paths → BIDS URIs in `IntendedFor`, `AssociatedEmptyRoom`, `Sources`; `DatasetDOI` bare DOIs → URI format
- [X] T034 [US2] Implement suffix deprecation handler: `_phase` → `_part-phase_bold`; deprecated anat suffixes `T2star`, `FLASH`, `PD` (delegates to `rename_file()`)
- [X] T035 [US2] Implement enum value rename handler: `ElektaNeuromag` → `NeuromagElektaMEGIN`, deprecated template identifiers (`fsaverage3`–`fsaverage6`, `fsaveragesym`, versioned `UNCInfant*`)
- [X] T036 [US2] Implement cross-file move handler: `ScanDate` from JSON sidecar → `acq_time` column in `_scans.tsv`. MUST create `_scans.tsv` with appropriate headers if it does not exist — current implementation silently skips the TSV write when the file is missing, causing data loss (`ScanDate` removed from JSON but never written to TSV). Add test for missing-`_scans.tsv` scenario. *(Reimplementation needed: data loss bug.)*
- [X] T037 [US2] Implement `migrate_dataset()` orchestrator: determine dataset version, determine target version (default: current released 1.x), compute applicable rules between versions, scan dataset for findings, apply auto-fixable findings, report unfixable ones
- [X] T038 [US2] Write tests for `migrate.py` in `tests/test_migrate.py`:
  - Metadata field renames applied correctly
  - Relative paths converted to BIDS URIs
  - Suffix deprecations trigger file renames
  - Enum values updated
  - `ScanDate` moved to `_scans.tsv`
  - `--dry-run` lists findings without modifying
  - Already-compliant dataset → "nothing to do"
  - Ambiguous cases skipped with clear reporting
  - `--to 1.9.0` applies only up-to-1.9.0 deprecations
- [X] T039 [US2] Implement `src/bids_utils/cli/migrate.py`: click command with `--to VERSION`, `--dry-run`, `--json`
- [X] T040 [US2] Write `bids-examples` integration test: find datasets with older `BIDSVersion`, migrate, validate
- [X] T125 [US2] Document migration rule test matrix in `tests/test_migrate.py` header comment: which rules have bids-examples test data (`IntendedFor`, `AssociatedEmptyRoom`, `ElektaNeuromag`, `SoftwareFilters`, `RawSources`, `DatasetDOI`, `AcquisitionDuration`) vs. which need synthetic fixtures (`DCOffsetCorrection`, `BasedOn`, `ScanDate`, `HardcopyDeviceSoftwareVersion`, `_phase` suffix, `"89+"` age, `fsaverage3-6`/`fsaveragesym`/`UNCInfant` templates). Ensure T038 tests cover both categories.

**Checkpoint**: `bids-utils migrate` handles all 1.x deprecations schema-driven.

---

## Phase 3a: Migration Rule Schema & Tiered Levels (FR-029, FR-030)

**Purpose**: Formalize the migration rule schema (analogous to validator schemas) and expose tiered migration levels and interaction modes via CLI. Prerequisite for new migration rules in Phase 3b.

### Migration rule schema (FR-029)

- [X] T099 [US2] Add `level` field (`safe` | `advisory` | `non-auto-fixable`) to `MigrationRule` dataclass in `src/bids_utils/migrate.py`. Add `MigrationLevel` enum to `src/bids_utils/_types.py`. Assign `level` to all existing registered rules: field renames → `safe`, enum renames → `safe`, path format → `safe`, DOI → `safe`, ScanDate cross-file move → `safe`, suffix _phase → `safe`, ambiguous suffixes (T2star, FLASH, PD) → `non-auto-fixable`, deprecated templates → `non-auto-fixable`.
- [X] T100 [P] [US2] Add `condition` field (optional `Callable[..., bool]`) to `MigrationRule` for contextual guards. Not wired to any rule yet — infrastructure only. Update `_scan_*` functions to call `rule.condition(context)` if present and skip the rule if it returns `False`.

### CLI filtering (FR-030)

- [X] T101 [US2] Add `MigrationMode` enum (`auto`, `non-interactive`, `interactive`) to `src/bids_utils/_types.py`. Add `level`, `mode`, `rule_ids`, `exclude_rules` parameters to `migrate_dataset()` in `src/bids_utils/migrate.py`. Filter registered rules by level (cumulative: `advisory` includes `safe`; `all` includes everything). Filter by `rule_ids`/`exclude_rules` if provided.
- [X] T102 [US2] Update `src/bids_utils/cli/migrate.py`: add `--level` (choice: safe/advisory/all, default: safe), `--mode` (choice: auto/non-interactive/interactive, default: auto), `--rule-id` (multiple, str), `--exclude-rule` (multiple, str) click options. Wire to `migrate_dataset()` parameters.
- [ ] T103 [US2] *(post-MVP)* Implement interactive mode in `migrate_dataset()`: when `mode=interactive` or `mode=auto` with PTY detected, prompt user for each `advisory` or `non-auto-fixable` finding. Accept/skip/abort. When `mode=non-interactive`, apply only auto-fixable rules at the selected level, skip others silently.

### New 1.x migration rules

- [X] T104 [US2] Register `AcquisitionDuration` → `FrameAcquisitionDuration` migration rule in `src/bids_utils/migrate.py` (FR-026). Level: `safe`. Condition: `VolumeTiming` must be present in the same sidecar JSON. Implement handler: scan BOLD/ASL sidecars, check condition, rename field. When `AcquisitionDuration` exists without `VolumeTiming`, register a separate finding as `non-auto-fixable` with clear reason.
- [X] T105 [P] [US2] Register `DCOffsetCorrection` → `SoftwareFilters` structural migration rule in `src/bids_utils/migrate.py` (FR-031). Level: `safe`. Scope: iEEG sidecars. Handler: move `DCOffsetCorrection` value into `"SoftwareFilters": {"DCOffsetCorrection": {"description": VALUE}}`; merge into existing `SoftwareFilters` dict if present; remove original `DCOffsetCorrection` field. Add tests for: standalone DCOffsetCorrection, DCOffsetCorrection with pre-existing SoftwareFilters dict. *(Reimplementation needed: current code removes field instead of migrating to SoftwareFilters.)*
- [X] T106 [P] [US2] Register `HardcopyDeviceSoftwareVersion` field removal rule in `src/bids_utils/migrate.py` (FR-032). Level: `advisory`. Scope: MRI sidecars. Handler: remove the field. Warn about data loss.
- [X] T107 [US2] Register age `"89+"` string → numeric `89` rule in `src/bids_utils/migrate.py` (FR-027). Level: `safe`. Handler: scan `participants.tsv` `age` column for `"89+"` string values. **Unit-aware**: read `participants.json` sidecar, check if `"Units"` is defined for `age`; if non-year units, skip with warning. Convert matched strings to numeric `89`.
- [X] T108 [P] [US2] Register HIPAA age cap rule (id: `age_cap_89`) in `src/bids_utils/migrate.py` (FR-027). Level: `advisory`. Handler: scan `participants.tsv` `age` column for numeric values > 89, cap to `89`. Same unit-awareness as T107.

### Tests

- [X] T109 [US2] Write tests for tiered migration in `tests/test_migrate.py`:
  - `--level=safe` applies only safe rules (default behavior unchanged)
  - `--level=advisory` applies safe + advisory rules
  - `--level=all` includes non-auto-fixable findings in report
  - `--rule-id=age_cap_89` applies only that specific rule
  - `--exclude-rule=field_rename_BasedOn_to_Sources` excludes that rule
  - `--mode=non-interactive` skips advisory prompts
- [X] T110 [US2] Write tests for new migration rules in `tests/test_migrate.py`:
  - `AcquisitionDuration` renamed to `FrameAcquisitionDuration` when `VolumeTiming` present
  - `AcquisitionDuration` flagged non-auto-fixable when `VolumeTiming` absent
  - `DCOffsetCorrection` removed from iEEG sidecar at advisory level
  - `HardcopyDeviceSoftwareVersion` removed at advisory level
  - `"89+"` string converted to numeric `89` in `participants.tsv`
  - Age with non-year units (`"Units": "months"` in `participants.json`) → rule skipped with warning
  - HIPAA cap: numeric `92` → `89` at advisory level

**Checkpoint**: `bids-utils migrate --level=advisory` applies all 1.x deprecations including field removals and HIPAA age capping. `--mode=interactive` prompts for each advisory item.

---

## Phase 3b: Schema Deprecation Audit (FR-033, FR-034)

**Purpose**: Automated coverage tracking — ensures all schema-declared deprecations have corresponding migration rules. Catches drift as bidsschematools is updated.

- [ ] T111 [US2] Implement schema deprecation scanner in `src/bids_utils/migrate.py`: function `_scan_schema_deprecations(schema)` that extracts all deprecation markers from all 6 schema levels: `rules/sidecars` field annotations, `rules/checks` validator rules, `objects/metadata` descriptions, `objects/enums` values, `objects/columns` definitions, `objects/suffixes` definitions. Returns list of `dict` with keys: `location` (schema path), `field` (affected field/suffix/enum), `description`.
- [ ] T112 [US2] Implement `audit_schema_coverage()` library function in `src/bids_utils/migrate.py` (FR-033): compare output of `_scan_schema_deprecations()` against registered `_RULES`. Return `AuditResult` (add dataclass to `src/bids_utils/_types.py`) with `implemented`, `missing`, `schema_version`, `schema_locations_scanned`. If bidsschematools version is not latest, include recommendation to upgrade.
- [ ] T113 [US2] Add `--audit` flag to `src/bids_utils/cli/migrate.py`: when passed, run `audit_schema_coverage()` and output report (human-readable default, `--json` for machine-readable). Exit 0 if fully covered, exit 1 if gaps found.
- [ ] T114 [US2] Write `test_migration_coverage_vs_schema` in `tests/test_migrate.py`: loads current schema, runs audit, asserts no unimplemented deprecations. This test will fail when bidsschematools is upgraded and new deprecations appear — forcing us to add rules.
- [ ] T115 [P] Create GitHub issue template `.github/ISSUE_TEMPLATE/missing-migration-rule.yml` (FR-034): form fields for schema version, deprecation location, affected field/suffix/enum, expected behavior. Labels: `migration`, `schema-gap`.

**Checkpoint**: `bids-utils migrate --audit` reports full coverage. `test_migration_coverage_vs_schema` passes. Upgrading bidsschematools with new deprecations will fail the test until rules are added.

---

## Phase 3c: BIDS URI Fixup Helper (FR-025)

**Purpose**: Generic helper that updates `bids:` URIs when files are renamed. Reusable across rename, migrate, subject-rename, session-rename.

- [ ] T116 [P] [US2] Create `src/bids_utils/_bids_uri.py` with `update_bids_uris(dataset: BIDSDataset, old_to_new: dict[Path, Path], dry_run: bool) -> list[Change]`. Scan JSON metadata fields: `IntendedFor`, `AssociatedEmptyRoom`, `Sources`, `DerivedFrom`. Match `bids::` scheme URIs against old→new path mapping. Update matched URIs. Respect content-aware I/O (`_io.py`).
- [ ] T117 [P] [US2] Write tests for `_bids_uri.py` in `tests/test_bids_uri.py`: single URI updated, list of URIs updated, cross-dataset URIs (`bids:ds001::...`) left unchanged, no false matches, dry-run returns changes without modifying
- [ ] T118 [US2] Wire `update_bids_uris()` into `src/bids_utils/rename.py` after file renames — call with old→new path mapping. Wire into `subject.py`, `session.py`, `migrate.py` similarly.

**Checkpoint**: Renaming a file that is referenced by `IntendedFor` in a fieldmap sidecar automatically updates the BIDS URI.

---

## Phase 4: User Story 3 — Migrate toward BIDS 2.0 (Priority: P1)

**Goal**: `bids-utils migrate --to 2.0` applies 2.0 breaking changes after resolving 1.x deprecations.

**Independent Test**: Take a BIDS 1.x dataset, run `bids-utils migrate --to 2.0`, validate against 2.0 schema.

### Implementation for User Story 3

- [X] T041 [US3] Extend migration rule engine for 2.0-specific transformations: entity renames, structural reorganization, metadata key changes (from 2.0 schema)
- [X] T042 [US3] Ensure cumulative migration: `migrate --to 2.0` on a 1.4 dataset applies all 1.x deprecation fixes first, then 2.0 changes
- [X] T043 [US3] Handle ambiguities requiring human judgment: abort with clear explanation, list items requiring manual intervention
- [X] T044 [US3] Write tests for 2.0 migration in `tests/test_migrate.py`:
  - 2.0-specific transformations applied
  - Cumulative application (1.x → 2.0)
  - Already-at-target → "nothing to do"
  - Ambiguities flagged, not guessed
- [X] T045 [US3] Write `bids-examples` integration test: migrate 1.x datasets to 2.0, validate against 2.0 schema

**⚠ PROVISIONAL**: Tasks T041-T045 are marked complete but their implementations are necessarily preliminary — they target the current 2.0-dev schema which is not yet finalized.

### Concrete 2.0 rules (bids-standard/bids-2-devel#14)

- [ ] T119 [US3] Register `participants.tsv` → `subjects.tsv` migration rule in `src/bids_utils/migrate.py` (FR-028). Level: `safe`. Category: `file_rename`. Handler: rename `participants.tsv` → `subjects.tsv` via VCS, rename `participants.json` → `subjects.json` via VCS, rename `participant_id` column → `subject_id` in the TSV, update `BIDSVersion` in `dataset_description.json`.
- [ ] T120 [US3] Wire BIDS URI fixup (FR-025/T118) into the participants→subjects migration: after file rename, call `update_bids_uris()` with `{participants.tsv: subjects.tsv}` mapping to update any `bids:` URIs referencing the old file.
- [ ] T121 [US3] Write tests for participants→subjects migration in `tests/test_migrate.py`:
  - `participants.tsv` renamed to `subjects.tsv`
  - `participants.json` renamed to `subjects.json`
  - `participant_id` column renamed to `subject_id`
  - `BIDSVersion` updated in `dataset_description.json`
  - BIDS URIs referencing `participants.tsv` updated to `subjects.tsv`
  - Dry-run lists all changes without modifying
  - Already at 2.0 → "nothing to do"
- [ ] T122 [US3] Update `src/bids_utils/_participants.py` to support both `participants.tsv` and `subjects.tsv` filenames — detect which exists and operate accordingly. This ensures post-migration commands (subject-rename, remove) work on 2.0 datasets.

**Checkpoint**: Full migration path from any 1.x version to 2.0 including participants→subjects rename.

---

## Phase 5: User Story 4 — Rename a Subject (Priority: P2)

**Goal**: `bids-utils subject-rename` renames a subject across the entire dataset.

**Independent Test**: Rename a subject in a `bids-examples` dataset, validate, confirm no stale references.

### Implementation for User Story 4

- [X] T046 [US4] Implement `src/bids_utils/subject.py`: `rename_subject()` — rename `sub-` directory, rename all files within (compose on `rename_file()`), update `participants.tsv`, update all `_scans.tsv` files
- [X] T047 [P] [US4] Add `--include-sourcedata` support: process `sourcedata/`, `.heudiconv/`, `derivatives/` recursively
- [X] T048 [US4] Write tests for `subject.py` in `tests/test_subject.py`:
  - Directory renamed, all files renamed, `participants.tsv` updated
  - `--include-sourcedata` processes sourcedata
  - Target subject already exists → refuse with exit code 2
  - VCS used when present (single commit)
- [X] T049 [US4] Implement `src/bids_utils/cli/subject.py`: `bids-utils subject-rename` click command
- [X] T050 [US4] Write `bids-examples` sweep test for subject rename

**Checkpoint**: Subject rename fully functional.

---

## Phase 6: User Story 5 — Rename a Session (Priority: P2)

**Goal**: `bids-utils session-rename` renames a session, including move-into-session.

**Independent Test**: Rename a session in a multi-session `bids-examples` dataset, validate.

### Implementation for User Story 5

- [X] T051 [US5] Implement `src/bids_utils/session.py`: `rename_session()` — rename `ses-` directory, rename all files within, update `_scans.tsv` files. Special case: `old=""` for move-into-session (introduce `ses-` level)
- [X] T052 [US5] Write tests for `session.py` in `tests/test_session.py`:
  - Session directory and files renamed
  - Move-into-session (`'' → ses-01`) introduces session level for all subjects
  - Target session already exists → refuse with exit code 2
- [X] T053 [US5] Implement `src/bids_utils/cli/session.py`: `bids-utils session-rename` click command
- [X] T054 [US5] Write `bids-examples` sweep test for session rename

**Checkpoint**: Session rename including move-into-session fully functional.

---

## Phase 7: User Story 6 — Metadata Aggregate/Segregate/Audit (Priority: P2)

**Goal**: `bids-utils metadata {aggregate,segregate,audit}` manipulates metadata inheritance.

**Independent Test**: Run `aggregate` on a `bids-examples` dataset, verify metadata equivalence.

### Implementation for User Story 6

- [X] T055 [US6] Implement inheritance chain resolution in `src/bids_utils/metadata.py`: build m4d/d4m bidirectional mappings (adapted from IP-freely pattern), walk hierarchy to resolve effective metadata per file
- [X] T056 [US6] Implement `aggregate_metadata()`: walk hierarchy bottom-up, identify common key-value pairs, hoist to parent-level sidecar, handle missing files correctly (do NOT aggregate if any file absent), support `--mode copy|move`, support scoped operation (per-subject path argument)
- [X] T057 [US6] Implement `segregate_metadata()`: push all metadata down to leaf-level files (inverse of aggregate)
- [X] T058 [US6] Implement `audit_metadata()`: report keys neither fully unique nor fully equivalent across files
- [X] T059 [US6] Write tests for `metadata.py` in `tests/test_metadata.py`:
  - Aggregate hoists common keys, resolved metadata unchanged
  - Missing file prevents aggregation of that key
  - Segregate produces self-contained leaf sidecars
  - `--mode copy` retains metadata at both levels
  - Scoped aggregation (`sub-01/`) only affects that subject
  - Audit reports inconsistent values
  - Round-trip: aggregate then segregate preserves equivalence
- [X] T060 [US6] Implement `src/bids_utils/cli/metadata.py`: `bids-utils metadata {aggregate,segregate,audit}` click subcommands
- [X] T061 [US6] Write `bids-examples` sweep test for metadata operations

**Checkpoint**: Metadata manipulation fully functional.

---

## Phase 8: User Stories 7, 8 — Remove Subject/Session/Run (Priority: P3)

**Goal**: `bids-utils remove` and `bids-utils remove-run` for data curation.

### Implementation

- [X] T062 [US7] Implement `remove_subject()` in `src/bids_utils/subject.py`: delete directory tree, update `participants.tsv`, clean up `_scans.tsv`; require `--force` or prompt for confirmation
- [X] T063 [P] [US8] Implement `src/bids_utils/run.py`: `remove_run()` — delete run files + sidecars, optionally reindex subsequent runs (`--shift` / `--no-shift`), update `_scans.tsv`
- [X] T064 [US7] Write tests for `remove_subject()` in `tests/test_subject.py`: subject removed, `participants.tsv` updated, `--force` bypasses prompt
- [X] T065 [P] [US8] Write tests for `remove_run()` in `tests/test_run.py`: run removed, `--shift` reindexes, `--no-shift` leaves gap, `_scans.tsv` updated
- [X] T066 [US7] Add `bids-utils remove` to `src/bids_utils/cli/subject.py`
- [X] T067 [P] [US8] Implement `src/bids_utils/cli/run.py`: `bids-utils remove-run` click command
- [X] T068 Write `bids-examples` integration tests for remove operations

**Checkpoint**: Remove subject/session/run functional.

---

## Phase 9: User Story 9 — Merge Datasets (Priority: P3)

**Goal**: `bids-utils merge` combines BIDS datasets with conflict handling.

### Implementation

- [X] T069 [US9] Implement `src/bids_utils/merge.py`: `merge_datasets()` per library-api.md — combine subjects (fail on conflicts), `--into-sessions` for overlapping subjects, incremental merge into existing dataset, `--on-conflict add-runs` for intra-session conflicts, `--reconcile-metadata` for metadata conflicts
- [X] T070 [US9] Write tests for `merge.py` in `tests/test_merge.py`:
  - Non-overlapping subjects merged successfully
  - Overlapping subjects → error (default) or placed into sessions
  - Incremental merge adds new subject to existing dataset
  - `--on-conflict add-runs` assigns next available run indices
  - `participants.tsv` conflicts reported
  - Metadata conflicts handled with segregate/re-aggregate
- [X] T071 [US9] Implement `src/bids_utils/cli/merge.py`: `bids-utils merge` click command
- [X] T072 [US9] Write `bids-examples` integration test: merge two datasets, validate

**Checkpoint**: Dataset merge functional.

---

## Phase 10: User Story 10 — Split Datasets (Priority: P3)

**Goal**: `bids-utils split` extracts subset of a dataset by suffix/datatype.

### Implementation

- [X] T073 [US10] Implement `src/bids_utils/split.py`: `split_dataset()` — extract files matching suffix/datatype filter, include required metadata, produce valid BIDS dataset
- [X] T074 [US10] Write tests for `split.py` in `tests/test_split.py`: split by suffix produces valid dataset with required metadata
- [X] T075 [US10] Implement `src/bids_utils/cli/split.py`: `bids-utils split` click command

**Checkpoint**: Dataset split functional.

---

## Phase 11: Shell Completion (FR-019, FR-020, FR-021)

**Purpose**: `bids-utils completion` subcommand with BIDS-aware completions.

**Independent Test**: Run `bids-utils completion bash | source /dev/stdin`, verify tab-completion offers `sub-*`, `ses-*` directories and entity keys.

### Implementation

- [X] T083 [P] Implement `src/bids_utils/cli/completion.py`: `bids-utils completion [SHELL]` click command — auto-detect shell from `$SHELL`, output activation script to stdout. Supported: Bash, Zsh, Fish (Click 8.0+ built-in).
- [X] T084 Implement BIDS-aware custom completions: filesystem-derived items (`sub-*` directories, `ses-*` directories, BIDS file paths) and entity keys from schema (`task=`, `run=`, `acq=`). Uses `_dataset.py` for dataset root resolution (FR-020: honor `--dataset` or walk up from CWD to `dataset_description.json`).
- [X] T085 Write tests for completion in `tests/test_cli.py` or `tests/test_completion.py`: `bids-utils completion --help`, shell detection, activation script output for each shell, BIDS-aware completion produces expected items

**Checkpoint**: `bids-utils completion` outputs working activation scripts with BIDS-aware completions.

---

## Phase 1c: Symlink Safety & Dry-Run Detail (FR-003, FR-023, FR-024)

**Purpose**: Fix critical git-annex symlink handling bug and enhance `--dry-run` to show per-file detail. These are blocking issues for real-world usage on annexed datasets.

### Bug fix: `is_file()` skips annexed symlinks (FR-023)

- [X] T092 Replace all bare `path.is_file()` calls used for file iteration with `not path.is_dir()` (or `path.is_file() or path.is_symlink()`) in: `session.py` (2 sites), `subject.py` (2 sites), `run.py` (2 sites), `split.py` (1 site), `merge.py` (1 site), `_sidecars.py` (1 site), `migrate.py` (1 site). Preserve `is_file()` where semantically correct (e.g., `_dataset.py` checking `dataset_description.json` existence, `_scans.py` checking `_scans.tsv` existence — these are never annexed).
- [X] T093 Add `tmp_annex_dataset` pytest fixture in `tests/conftest.py`: creates a git-annex repo with locked (symlinked) data files (`.nii.gz`) alongside regular git files (`.json`, `.tsv`). Requires `git annex` to be installed (mark tests `skipif` otherwise).
- [X] T094 Write regression tests using `tmp_annex_dataset` for session-rename, subject-rename, and rename — verify that ALL files (including annexed symlinks) are renamed correctly (SC-008). Test both with content present and content absent.
- [X] T124 [US4,US5] Implement `_is_bids_data_entry(path: Path) -> bool` helper in `src/bids_utils/_types.py` (FR-036). Returns `True` for: (a) regular files, (b) symlinks (annexed files per FR-023), (c) directories matching BIDS data directory patterns (`.ds`, `.zarr`, `.ome.zarr`). Replace all `not path.is_dir()` file iteration filters (introduced by T092) with `_is_bids_data_entry()` in: `session.py`, `subject.py`, `run.py`, `split.py`, `merge.py`, `_sidecars.py`, `migrate.py`. Add test with mock `.ds` directory — verify it is included in rename operations.

### Enhanced dry-run (FR-003 update)

- [X] T095 Change `--dry-run` / `-n` from a boolean flag to an optional-value option: `--dry-run` (or `--dry-run=overview`) for current summary behavior, `--dry-run=detailed` for per-file listing. Update `common_options` in `cli/_common.py`, `OperationResult`, and `output_result()`. Library functions already populate `result.changes` with per-file detail — the change is in how `output_result` renders them.
- [X] T096 Ensure all library functions populate `result.changes` with per-file detail (not just one summary `Change` per subject/session). Audit `session.py`, `subject.py`, `rename.py` — the rename function already does this; session/subject need to add per-file `Change` entries for individual file renames within the session/subject operation.

### Annex operation logging (FR-024)

- [X] T097 Add logging to `_io.py` for annex operations: log at INFO level when `ensure_content` fetches a file (`--annexed=get`), when `ensure_writable` unlocks, when `mark_modified` re-adds. In `--dry-run` mode, report which files would need content fetched. Wire through to CLI verbosity (`-v` enables DEBUG, default shows INFO, `-q` suppresses).

### Tests

- [X] T098 Write tests for `--dry-run=detailed` output: verify per-file change listing for session-rename, subject-rename, rename. Verify `--dry-run=overview` retains current behavior. Verify `--dry-run` without value defaults to overview.

**Checkpoint**: `bids-utils --annexed=get session-rename --dry-run=detailed` shows every file that would be renamed/edited/fetched. Running without `--dry-run` on an annexed dataset correctly renames all files including symlinks.

---

## Phase 1d: Integration Test Fixture Pattern (FR-042)

**Purpose**: Establish a generic, reusable per-test fixture pattern based on `git worktree` over the local `bids-examples` clone, plus an injection helper for adversarial non-BIDS source filenames. This unblocks Phase 2a/2b non-BIDS coverage and Phase 5b sweep.

**Independent Test**: A throwaway worktree fixture creates and tears down a per-test copy of a `bids-examples` dataset without mutating the host clone. The injection helper produces files like `..._bold__dup-01.nii.gz` whose presence is independently verifiable by the BIDS validator.

- [X] T126 [P] Implement per-test git-worktree fixture in `tests/integration/_worktree_fixture.py`: pytest fixture `bids_examples_worktree(dataset_id)` that runs `git worktree add --detach <unique_path> <ref>` from the local `bids-examples` clone into a unique path under `tmp_path`, yields the worktree path, and on teardown calls `git worktree remove --force <unique_path>`. MUST NOT call `git worktree prune` (per CLAUDE.md global rule). Add variant `bids_examples_worktree_annexed(dataset_id)` that additionally enables `git annex init` + force-annex of all data files for SC-008 coverage.
- [X] T127 [P] Implement non-BIDS suffix injection helper in `tests/integration/_nonbids_inject.py`: `inject_nonbids_suffixes(worktree_root, *, kinds=("dup",), seed=0, count=2) -> list[Path]` that deterministically (seeded RNG) selects `count` data files per `kind` and creates additional files with full-literal stems including the chosen non-BIDS suffix (`__dup-01` for "dup", `+mine` for "plus_mine", `--crap` for "crap", `_test` for "test") plus their full-literal-stem sidecars. Must copy bytes (or symlinks for git-annex) so injected files are real artefacts.
- [X] T128 [P] Implement validator wrapper helpers in `tests/integration/_validator.py`: `assert_validator_flags(worktree_root, *, expected_files: list[Path])` (asserts injected files appear in validator output), `assert_validator_passes(worktree_root, *, ignore_pre_existing: list[str] | None = None)` (asserts validator passes modulo pre-existing warnings). Both helpers skip gracefully via `pytest.skip` when `bids-validator-deno` is absent.
- [X] T129 Write fixture self-tests in `tests/integration/test_worktree_fixture.py`: verify worktree creation/teardown leaves the host `bids-examples` clone untouched, two parallel test cases get isolated worktrees, the annexed variant produces locked symlinks, and the injection helper produces files that survive a validator round-trip.
- [X] T130 [P] Add a brief `tests/integration/README.md` documenting the worktree fixture pattern and the injection helper kinds, including the rule against `git worktree prune` and the deterministic seed contract.
- [X] T146 Refactor `tests/integration/test_bids_examples.py` to use the FR-042 worktree fixture pattern: replace every `_copy_dataset(BIDS_EXAMPLES_DIR / ds_name, tmp_path)` call with `bids_examples_worktree(ds_name)` and every `_load_annexified_dataset(ds_name, tmp_path)` call with `bids_examples_worktree_annexed(ds_name)` (plus a small wrapper that builds the `BIDSDataset` and sets `annexed_mode=SKIP`). Delete the now-unused `_copy_dataset`, `_annexify_dataset`, `_load_annexified_dataset` helpers. Dry-run sweeps that operate on the host clone via `_load_example_dataset` are intentionally left unchanged (no mutation, no copy). Verify with `pytest tests/integration/test_bids_examples.py` and full `tox`.

**Checkpoint**: `pytest tests/integration/test_worktree_fixture.py` passes; new tests can `bids_examples_worktree("ds000001")` and get a clean throwaway worktree.

---

## Phase 2a/2b: Split Existing `rename --set` into `edit-filename` + mv-like `rename` (FR-038, FR-039, FR-040)

**Framing**: This phase is a **move/rename, not a rewrite**. The existing `src/bids_utils/rename.py` (T025, ~199 lines) and `src/bids_utils/cli/rename.py` (T027, ~74 lines) already implement the full entity-mutation logic via `set_entities`/`new_suffix`/`--set`/`--suffix`. We treat that working code as the seed for the new `edit-filename` command, then trim what's left of `rename.py` down to a much smaller mv-like core. Phase 2a (the trimmed `rename`) and Phase 2b (the relocated `edit-filename`) are co-required and easiest to land in a single PR — listed as separate phases only for traceability against FR-039 vs FR-040.

**Independent Test**:
- `bids-utils edit-filename sub-01/func/sub-01_task-rest_bold.nii.gz --set task=nback` performs exactly what `rename --set task=nback` did before — same files moved, same `_scans.tsv` row update, same validator outcome (regression-equivalent).
- `bids-utils rename sub-01/func/sub-01_task-rest_bold.nii.gz sub-02/ses-post/func/` (cross-container) moves the file and rewrites `sub-`/`ses-` labels; dataset still validates. The new `rename` rejects `--set`/`--delete` flags with a hint pointing to `edit-filename`.

### Phase 2b: Move existing entity-mutation logic into `edit-filename` (FR-040)

- [ ] T135 [US1] **Move (not rewrite)** the existing `rename_file()` body from `src/bids_utils/rename.py` into a new `src/bids_utils/edit_filename.py` as `edit_filename(dataset, path, *, set_entities=None, delete_entities=None, dry_run=False, include_sourcedata=False) -> OperationResult`. Concrete steps: (i) `git mv src/bids_utils/rename.py src/bids_utils/edit_filename.py` then re-add a fresh stub `rename.py` for T131; (ii) rename the function to `edit_filename`; (iii) replace `set_entities` semantics as-is; (iv) add a `delete_entities: list[str] | None` parameter that calls a new `BIDSPath.without_entities(*keys)` helper (or inlines a `dict.pop` loop); (v) keep `with_suffix` support but rename the kwarg from `new_suffix` to `set_suffix` for naming symmetry; (vi) preserve the existing `_scans.tsv` update, conflict detection, and `_vcs.move` calls verbatim. The body of the function should be **substantively unchanged** from the old `rename_file()`.
- [ ] T136 [P] [US1] **Move (not rewrite)** the existing `cli/rename.py` into `src/bids_utils/cli/edit_filename.py`: `git mv src/bids_utils/cli/rename.py src/bids_utils/cli/edit_filename.py`, rename the click command from `rename` to `edit-filename`, keep `--set` (multiple, parsed by existing `_parse_set_option`), rename `--suffix` → `--set-suffix` for symmetry with `--set`, and add a new repeatable `--delete KEY` option that populates a `delete_entities` list. Re-add a fresh stub `cli/rename.py` for T133. The body of the click command should be **substantively unchanged**, just routing to `edit_filename()` instead of `rename_file()`.
- [ ] T137 [US1] Re-register both commands in the click CLI group in `src/bids_utils/cli/__init__.py`: keep `rename` (now backed by T133's stub) and add `edit-filename` (backed by T136). Update `bids-utils --help` so the two appear with distinct one-line descriptions making the split obvious.
- [ ] T138 [US1] **Rename (not rewrite) tests**: `git mv tests/test_rename.py tests/test_edit_filename.py` and update imports from `bids_utils.rename` to `bids_utils.edit_filename` and CLI invocations from `bids-utils rename --set ...` to `bids-utils edit-filename --set ...`. The test bodies should be substantively unchanged — they were already testing the entity-mutation behaviour. Add only the new tests required by the change: FR-035 entity-order regression (run before recording), FR-038 non-BIDS preservation (`__dup-NN` segment retained verbatim), and the new `--delete KEY` cases. A fresh `tests/test_rename.py` will be created in T134 for the trimmed mv-like API.

### Phase 2a: Trim `rename` down to mv-like SRC→DST (FR-039)

- [ ] T131 [US1] **Trim, don't rewrite**. After T135 has moved the entity-mutation logic out, populate the new (post-`git mv`) `src/bids_utils/rename.py` with a small `rename_file(dataset, src_path, dst_path, *, dry_run=False, include_sourcedata=False) -> OperationResult` that performs only the mv-like core: discover sidecars for `src_path` via FR-038 full-literal-stem matching (T139), check conflicts on `dst_path`, call `_vcs.move(src, dst)` for each (primary + sidecars), update `_scans.tsv` rows referencing the old filename, invoke the FR-025 BIDS URI fixup helper. Drop the `set_entities`/`new_suffix` parameters entirely (their behaviour now lives in `edit_filename`). Mark the breaking pre-1.0 API change in the docstring.
- [ ] T132 [US1] Add cross-container detection to the trimmed `rename_file()` in `src/bids_utils/rename.py`: extract `(sub, ses)` containers from `src_path` and `dst_path`. When they differ (or `dst_path` is a directory under a different container), import `_rewrite_entities_for_target_filename(...)` from `edit_filename` (T135) and use it to rewrite the destination filename's `sub-`/`ses-` labels to match the destination path. Result MUST satisfy entity-order normalization (FR-035). Add unit tests covering the four combinations: (same sub, same ses), (different sub), (different ses), (different sub+ses).
- [ ] T133 [US1] Populate the new (post-`git mv`) `src/bids_utils/cli/rename.py` as a small click command taking positional `SRC` and `DST` only. Reject `--set`/`--delete`/`--suffix` with a clear error message pointing the user to `bids-utils edit-filename` (these were the old flags — users will reflexively try them). Preserve `--dry-run`, `--json`, `-v`/`-q`, `--include-sourcedata`. Smoke-test in `tests/test_cli.py`: `bids-utils rename --help` lists no `--set`/`--delete`; passing them yields a non-zero exit and a hint.
- [ ] T134 [US1] Create a fresh `tests/test_rename.py` (the old file was moved to `test_edit_filename.py` in T138) covering only the trimmed mv-like behaviour: (a) bare same-directory rename (using FR-042 `bids_examples_worktree`), (b) cross-container rename moves a file into a new `sub-XX/ses-YY/` and rewrites the entity labels, (c) heudiconv-style `..._bold__dup-01.nii.gz` → clean BIDS target via `rename SRC DST` with sidecars matched by full literal stem, (d) conflict detection (existing target → exit 2), (e) VCS path (`git mv`).
- [ ] T139 [US1] Update `src/bids_utils/_sidecars.py` `find_sidecars()` to honor FR-038: when the source filename is non-BIDS (does not parse as a valid `BIDSPath`), use the **full literal stem** (basename minus final extension; preserving `__dup-NN`, `+mine`, etc.) for sibling matching — do NOT canonicalize or strip non-BIDS trailing segments. When the source IS valid BIDS, retain the existing schema-driven sidecar-extension lookup. Add tests in `tests/test_sidecars.py` covering both branches and a mixed directory.
- [ ] T144 [US1] Implement batch / glob input for both commands (FR-043). (a) In `src/bids_utils/edit_filename.py`, change the function signature from `path: str | Path` to `paths: PathArg` (single path or sequence) and apply set/delete/set-suffix to each path, coalescing `_scans.tsv` updates per `(subject, session)` container. Pre-compute every target path and refuse the entire batch with exit code 2 if ANY conflict (target exists, schema validation fails, etc.) is detected — atomic-at-batch-level. (b) In `src/bids_utils/cli/edit_filename.py`, change the `SRC` click argument to `nargs=-1` and accept multiple positional paths so shell globs (`sub-*/func/...`) flow through naturally. (c) In `src/bids_utils/rename.py`, accept multi-source input where the final argument is the destination directory (mirrors Unix `mv`); single-source `rename SRC DST` keeps current semantics. Update `cli/rename.py` similarly. (d) Add unit tests in `tests/test_edit_filename.py` and `tests/test_rename.py` covering: single path (regression), multi-path same-directory, glob across subjects, partial-failure (one conflict aborts the whole batch with no filesystem mutation), and `_scans.tsv` coalescing. (e) Add an integration test using FR-042's worktree fixture: glob across two subjects, apply `--set task=nback`, verify the dataset still validates.
- [ ] T145 [US1] Add atomic-batch tests in `tests/test_edit_filename.py` and `tests/test_rename.py` (SC-010): set up a worktree with two source files where the second's target collides with an existing file; assert the command exits with code 2, stderr names the conflicting file, and the first source is **not** renamed (filesystem unchanged). Repeat for the same scenario in `--dry-run` mode (no mutation either way, but the conflict is still reported).

**Checkpoint**: `bids-utils rename SRC DST` works for same-directory, cross-directory-same-container, and cross-container moves. Heudiconv `__dup-NN` source files are renamed cleanly. The CLI no longer accepts `--set`/`--delete`. `bids-utils edit-filename --set task=nback FILE` is regression-equivalent to the old `bids-utils rename FILE --set task=nback`.

---

## Phase 5b: Non-BIDS Source Robustness Sweep (FR-041, SC-009)

**Purpose**: Confirm and (where needed) repair that the five file-touching commands (`rename`, `edit-filename`, `remove`, `subject-rename`, `session-rename`) operate correctly on non-BIDS-named source files (`__dup-NN`, `+mine`, `--crap`, `_test`). `migrate` is explicitly out of scope per Session 2026-04-27 Q3.

**Independent Test**: For each of the five commands, an integration test (a) injects adversarial-suffix files into a `bids-examples` worktree, (b) asserts the validator flags those files (pre-state contract), (c) runs the command, and (d) asserts the validator passes (modulo pre-existing warnings) — proving the injected files were renamed/removed cleanly, not silently skipped.

- [ ] T140 [P] Audit each command for FR-041 compliance and patch as needed: walk through `src/bids_utils/rename.py`, `src/bids_utils/edit_filename.py`, `src/bids_utils/subject.py`, `src/bids_utils/session.py`, `src/bids_utils/run.py` and verify (a) sidecar discovery uses FR-038 full-literal-stem matching, (b) file iteration uses `_is_bids_data_entry()` (FR-023, FR-036), (c) `_scans.tsv` row updates match filenames literally, (d) non-BIDS trailing segments are preserved verbatim. File any deltas as follow-up tasks if real bugs are found.
- [ ] T141 [US1,US4,US5,US7] Write `tests/integration/test_nonbids_sources.py` parameterised over `command in {rename, edit-filename, remove, subject-rename, session-rename}` × `kind in {"dup", "plus_mine", "crap", "test"}`. For each combination: materialise a `bids_examples_worktree`, capture pre-existing validator warnings, call `inject_nonbids_suffixes(kinds=(kind,))`, run `assert_validator_flags(...)` (SC-009 pre-condition), run the command on the injected file (with appropriate args — for `subject-rename`/`session-rename` rename the containing subject/session), then run `assert_validator_passes(ignore_pre_existing=...)` (SC-009 post-condition).
- [ ] T142 [P] Add `nonbids_robustness` pytest marker registration in `pyproject.toml` (`[tool.pytest.ini_options] markers`) so the new sweep can be selected/excluded with `pytest -m nonbids_robustness` / `-m "not nonbids_robustness"`. Apply the marker to all tests in `test_nonbids_sources.py`.
- [ ] T143 [P] Update Phase 12 / CI: ensure the `nonbids_robustness` marker runs in CI alongside the existing `bids-examples` sweep (extend `tox.ini`'s default test command or add a dedicated env), and document in `tests/integration/README.md` how to run only this sweep locally.

**Checkpoint**: `pytest -m nonbids_robustness` passes against an installed `bids-validator-deno` (and skips gracefully without it). Each of the five commands handles `__dup-NN`/`+mine`/`--crap`/`_test` source files cleanly.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories.

- [ ] T076 [P] Documentation: populate `mkdocs` site with quickstart, API reference, CLI reference
- [ ] T077 [P] Add `--json` output mode tests for all commands (SC-005)
- [X] T078 Run full `bids-examples` sweep across all operations (SC-001, SC-008). **Two modes**: (a) plain git (current bids-examples), (b) git-annex mode — clone bids-examples, `git annex init`, force all files into annex (`git annex add .`), then run all operations. Both modes must produce equivalent results. Operations to test per dataset: rename (random file), session-rename (if multi-session), subject-rename, migrate --dry-run. Validate dataset remains valid after each operation.
- [ ] T079 [P] Test suite against multiple BIDS schema versions (1.8, 1.9, 2.0-dev) (SC-006)
- [ ] T080 [P] Performance profiling on a 1000-subject synthetic dataset (SC-003)
- [X] T081 Code cleanup: check for duplication (`tox -e duplication`), refactor
- [X] T082 Run `quickstart.md` validation — verify all documented commands work

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0 (Scaffolding)**: No dependencies — start immediately
- **Phase 1 (Infrastructure)**: Depends on Phase 0 — BLOCKS all user stories
- **Phase 1b (Annexed Content / FR-022)**: Depends on Phase 1. Can be done at any point but SHOULD be done before real-world usage on git-annex/DataLad datasets. Retroactively completes VCS integration from Phase 1.
- **Phase 1c (Symlink Safety & Dry-Run Detail / FR-003, FR-023, FR-024)**: Depends on Phase 1b. BLOCKS real-world usage on annexed datasets — the symlink bug causes silent data loss (files not renamed). Should be done immediately after Phase 1b.
- **Phase 1d (Test Fixture Pattern / FR-042)**: Depends on Phase 1. Independent of app code. BLOCKS Phase 5b. Strongly recommended before Phase 2a/2b for non-BIDS coverage.
- **Phase 2 (Rename / US1)**: Depends on Phase 1
- **Phase 2a (rename SRC DST refactor / FR-038, FR-039)**: Depends on Phase 2 (refactors existing T025–T030). Co-required with Phase 2b — cross-container `rename` delegates filename rewriting to `edit_filename`.
- **Phase 2b (edit-filename / FR-040)**: Depends on Phase 1 + Phase 2 (replaces the entity-mutation behaviour of the original T025/T027). Co-required with Phase 2a.
- **Phase 5b (Non-BIDS Source Sweep / FR-041, SC-009)**: Depends on Phases 2a, 2b, 5, 8 (all five commands implemented), and Phase 1d (worktree fixture + injection helper).
- **Phase 3 (Migrate 1.x / US2)**: Depends on Phase 2 (uses rename for suffix changes)
- **Phase 3a (Migration Rule Schema / FR-029, FR-030)**: Depends on Phase 3 (extends existing migrate.py)
- **Phase 3b (Schema Audit / FR-033, FR-034)**: Depends on Phase 3a (needs level field and rule registry)
- **Phase 3c (BIDS URI Fixup / FR-025)**: Depends on Phase 1 (independent of migrate, but blocks Phase 4 concrete rules)
- **Phase 4 (Migrate 2.0 / US3)**: Depends on Phase 3a + Phase 3c (needs tiered levels and URI fixup for participants→subjects)
- **Phase 5 (Subject rename / US4)**: Depends on Phase 2
- **Phase 6 (Session rename / US5)**: Depends on Phase 2
- **Phase 7 (Metadata / US6)**: Depends on Phase 1 (independent of rename/migrate)
- **Phase 8 (Remove / US7-8)**: Depends on Phase 2
- **Phase 9 (Merge / US9)**: Depends on Phases 5, 6 (uses subject/session rename)
- **Phase 10 (Split / US10)**: Depends on Phase 1
- **Phase 11 (Completion / FR-019-021)**: Depends on Phase 1 (uses `_dataset.py`, `_schema.py`)
- **Phase 12 (Polish)**: Depends on all desired phases being complete

### Parallel Opportunities After Phase 3

```
Phase 3 (Migrate 1.x)  ─→  Phase 3a (Rule Schema)  ─→  Phase 3b (Audit)
                                                     ─→  Phase 4 (Migrate 2.0)
Phase 3c (URI Fixup) can start after Phase 1 (parallel with Phase 2/3)
Phase 3c BLOCKS Phase 4 concrete rules (participants→subjects needs URI fixup)
```

Earlier parallel opportunities (after Phase 1) remain:

```
Phase 2 (Rename)  ─→  Phase 3 (Migrate 1.x)  ─→  Phase 3a ─→ Phase 3b, Phase 4
                  ─→  Phase 5 (Subject)       ─→  Phase 9 (Merge)
                  ─→  Phase 6 (Session)       ─→
                  ─→  Phase 8 (Remove)
Phase 3c (URI Fixup) can start after Phase 1 (parallel with everything)
Phase 7 (Metadata) can start immediately after Phase 1
Phase 10 (Split) can start immediately after Phase 1
Phase 11 (Completion) can start immediately after Phase 1
```

### Within Each Phase

- Tests MUST be written and FAIL before implementation (TDD per constitution)
- Models/types before services
- Library before CLI
- Commit after each task or logical group

## Implementation Strategy

### MVP First (Stories 1-2)

1. Complete Phase 0: Scaffolding
2. Complete Phase 1: Infrastructure (CRITICAL — blocks everything)
3. Complete Phase 2: Rename (US1) → **validate independently**
4. Complete Phase 3: Migrate 1.x (US2) → **validate independently**
5. Ship: `bids-utils rename` + `bids-utils migrate` cover the highest-priority needs

### Incremental Delivery

Each subsequent phase adds value without breaking prior phases:
- Phase 1d adds the worktree-based test fixture pattern (foundation for FR-041/SC-009 coverage)
- Phase 2a/2b is a **breaking pre-1.0 CLI refactor** of `rename` (mv-like) plus the new `edit-filename` command — release notes MUST flag the split.
- Phase 5b verifies the five file-touching commands handle non-BIDS source files (heudiconv `__dup-NN`, plus adversarial `+mine`/`--crap`/`_test`) — closes bids-standard/bids-utils#14.
- Phase 3a adds tiered migration levels (safe/advisory/non-auto-fixable)
- Phase 3b adds schema audit (catches drift when bidsschematools updates)
- Phase 3c adds BIDS URI fixup (reusable across all rename operations)
- Phase 4 adds concrete 2.0 migration (participants→subjects)
- Phases 5-6 add subject/session rename
- Phase 7 adds metadata management
- Phases 8-10 add remove/merge/split

---

## Notes

- [P] tasks = different files, no dependencies — can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Verify tests fail before implementing (TDD — constitution Principle V)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
