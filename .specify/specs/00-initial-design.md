# Feature Specification: bids-utils — Core Library & CLI

**Feature Branch**: `00-initial-design`
**Created**: 2026-04-02
**Status**: Draft
**Input**: User description: "Build a Python application/library following what is described in docs/design/00-initial-design.md file"

## User Scenarios & Testing *(mandatory)*

<!--
  Stories are ordered by priority from the design document.
  Each story is independently implementable and testable — delivering
  an MVP that already provides value to BIDS dataset maintainers.
-->

### User Story 1 — Rename a BIDS file (Priority: P1, need: high)

A researcher has a BIDS file with an incorrect entity or a non-compliant name (e.g., a spurious `_test` suffix). They run `bids-utils rename` to fix it. The tool renames the primary file **and** all associated sidecar files (`.json`, `.bvec`, `.bval`, etc.), updates any `_scans.tsv` entries that reference the old filename, and uses `git mv` when the dataset is under version control.

**Why this priority**: Renaming a single file is the atomic building block. `subject-rename`, `session-rename`, and other higher-level operations compose on top of it. Shipping this first unblocks the most common ad-hoc fix-up need and validates the core infrastructure (sidecar discovery, `_scans.tsv` patching, VCS awareness, dry-run output).

**Independent Test**: Rename a file in any bids-examples dataset, then run the BIDS validator to confirm the dataset remains valid.

**Acceptance Scenarios**:

1. **Given** a valid BIDS dataset with `sub-01/func/sub-01_task-rest_bold.nii.gz` and its `.json` sidecar, **When** the user runs `bids-utils rename sub-01/func/sub-01_task-rest_bold.nii.gz --set task=nback`, **Then** both files are renamed to `sub-01_task-nback_bold.*`, `_scans.tsv` is updated, and the dataset passes validation.
2. **Given** a BIDS dataset under git, **When** the user runs `bids-utils rename ... --dry-run`, **Then** the tool prints the planned renames without modifying any files or git state.
3. **Given** a file with an associated `_scans.tsv` entry, **When** the file is renamed, **Then** the corresponding row in `_scans.tsv` is updated to reflect the new filename.
4. **Given** a file that is referenced nowhere else, **When** renamed, **Then** only the file and its sidecars are affected — no unrelated files change.
5. **Given** a rename that would produce a filename conflicting with an existing file, **When** the user runs the command, **Then** the tool refuses with exit code 2 and a clear error message.
6. **Given** a file which is not valid BIDS, e.g. ends with `_bold__dup-01.json`, tool operates correctly regardless that original file name is not valid BIDS.

---

### User Story 2 — Migrate a dataset within BIDS 1.x to address deprecations (Priority: P1, need: high)

A lab maintains a BIDS dataset created under an older 1.x version (e.g., 1.4 or 1.6). Over time, the BIDS specification has deprecated metadata fields, suffixes, coordinate-system values, and path formats. The dataset still validates but emits deprecation warnings. The user runs `bids-utils migrate` (defaulting to the current released 1.x version) to bring the dataset up to date, resolving all deprecations automatically where possible.

The BIDS specification has accumulated significant deprecations within the 1.x series that `migrate` must handle:

- **Metadata field replacements**: `BasedOn` → `Sources`, `RawSources` → `Sources`, `ScanDate` → `acq_time` column in `_scans.tsv` (PET, since 1.6.0), `DCOffsetCorrection` → `SoftwareFilters` (iEEG, since 1.6.0), `AcquisitionDuration` → `FrameAcquisitionDuration` (BOLD)
- **Path format → BIDS URI migration** (since 1.8.0): `IntendedFor`, `AssociatedEmptyRoom`, `Sources` fields that use relative paths must be converted to BIDS URIs (`bids::` scheme)
- **Value format changes**: `DatasetDOI` bare DOIs → URI format (since 1.8.0)
- **Suffix deprecations** (since 1.5.0): `_phase` → `_part-phase_bold`, and deprecated anatomical suffixes `T2star`, `FLASH`, `PD`
- **Coordinate system value renames**: `ElektaNeuromag` → `NeuromagElektaMEGIN`, deprecated template identifiers (`fsaverage3`–`fsaverage6` → `fsaverage`, `fsaveragesym` → `fsaverageSym`, versioned `UNCInfant*` → `UNCInfant`)

All deprecation knowledge MUST be derived from the machine-readable schema (`bidsschematools`), specifically `src/schema/objects/metadata.yaml`, `enums.yaml`, `suffixes.yaml`, and `src/schema/rules/checks/deprecations.yml` — not hardcoded.

**Why this priority**: These deprecations affect existing datasets **today**. Unlike the 2.0 migration, 1.x deprecation fixes can be applied incrementally, are lower risk, and immediately silence validator warnings. Many dataset maintainers are unaware of deprecations accumulated across 1.5→1.6→1.8→1.9 and need an automated path to modernize.

**Independent Test**: Take a BIDS 1.4-era dataset from bids-examples, run `bids-utils migrate` (targeting current 1.x), verify deprecation warnings are eliminated and the dataset passes validation.

**Acceptance Scenarios**:

1. **Given** a BIDS 1.4 dataset with `IntendedFor` using relative paths in fieldmap JSON sidecars, **When** `bids-utils migrate` is run, **Then** all `IntendedFor` values are converted to BIDS URIs and the dataset passes validation without deprecation warnings.
2. **Given** a BIDS 1.4 dataset with `_phase.nii.gz` files (deprecated suffix), **When** `bids-utils migrate` is run, **Then** files are renamed to `_part-phase_bold.nii.gz` (with sidecars), `_scans.tsv` is updated, and the dataset remains valid.
3. **Given** a PET dataset with `ScanDate` in sidecar JSON, **When** `bids-utils migrate` is run, **Then** the value is moved to the `acq_time` column in the corresponding `_scans.tsv` and removed from the JSON.
4. **Given** an MEG dataset with `MEGCoordinateSystem: "ElektaNeuromag"`, **When** `bids-utils migrate` is run, **Then** the value is updated to `"NeuromagElektaMEGIN"`.
5. **Given** a derivatives dataset with `RawSources` and `BasedOn` fields, **When** `bids-utils migrate` is run, **Then** these are consolidated into `Sources` with BIDS URI format.
6. **Given** `bids-utils migrate --dry-run`, **When** run on any dataset, **Then** the tool lists each deprecation found, the proposed fix, and the affected file — without modifying anything.
7. **Given** a dataset already conforming to the target version, **When** `bids-utils migrate` is run, **Then** the tool reports "nothing to do" and exits with code 0.
8. **Given** a deprecation that cannot be resolved automatically (e.g., ambiguous `IntendedFor` with no clear mapping), **When** migration encounters it, **Then** the tool reports it clearly and skips that item rather than guessing.
9. **Given** `bids-utils migrate --to 1.9.0` (explicit target within 1.x), **When** run, **Then** only deprecations up to and including 1.9.0 are applied — deprecations introduced in later versions are not.

---

### User Story 3 — Migrate a dataset toward BIDS 2.0 (Priority: P1, need: high)

A lab maintaining a BIDS 1.x dataset needs to prepare for BIDS 2.0. They run `bids-utils migrate --to 2.0` which reads the machine-readable schema (via `bidsschematools`) and applies the necessary transformations (entity renames, metadata key changes, structural reorganization) in a safe manner. This builds on top of the 1.x deprecation handling (User Story 2) — a dataset should first be brought up to the latest 1.x before migrating to 2.0. Changes do not need to be reversible — use of VCS should be encouraged instead to retain prior versions.

**Why this priority**: BIDS 2.0 is approaching and many datasets need a migration path. A prototype already exists (bids-specification PR #2282) validating the concept.

**Independent Test**: Take a BIDS 1.x dataset from bids-examples, run `bids-utils migrate --to 2.0`, verify the output passes the BIDS 2.0 validator schema.

**Acceptance Scenarios**:

1. **Given** a valid BIDS 1.8 dataset, **When** `bids-utils migrate --to 2.0 --dry-run` is run, **Then** the tool lists all changes needed (deprecations, renames, structural changes) without modifying any files.
2. **Given** a valid BIDS 1.8 dataset, **When** `bids-utils migrate --to 2.0` is run, **Then** the dataset is transformed and passes validation against the BIDS 2.0 schema.
3. **Given** a dataset already at the target version, **When** `bids-utils migrate` is run, **Then** the tool reports "nothing to do" and exits with code 0.
4. **Given** a dataset with ambiguities that require human judgment, **When** migration encounters them, **Then** the tool aborts with a clear explanation rather than guessing.
5. **Given** a BIDS 1.4 dataset, **When** `bids-utils migrate --to 2.0` is run, **Then** the tool first applies all 1.x deprecation fixes (Story 2) before applying 2.0-specific transformations — the migration is cumulative.

---

### User Story 4 — Rename a subject (Priority: P2, need: medium)

A data manager needs to anonymize or re-number a subject. They run `bids-utils subject-rename sub-01 sub-99`. The tool renames the `sub-` directory, every file within it (since all carry the `sub-` prefix), updates `participants.tsv`, updates all `_scans.tsv` files, and optionally processes `sourcedata/`, `.heudiconv/` and common derivatives under `derivatives/` (via recursive calls to the same method on each derivative).

**Why this priority**: Common real-world need. Composes on top of the P1 `rename` primitive. Medium priority per design doc.

**Independent Test**: Rename a subject in a bids-examples dataset, run validator, confirm validity and that no stale references remain.

**Acceptance Scenarios**:

1. **Given** a valid dataset with `sub-01`, **When** `bids-utils subject-rename sub-01 sub-99` is run, **Then** the directory is renamed, all files are renamed, `participants.tsv` is updated, and the dataset remains valid.
2. **Given** a dataset with `sourcedata/sub-01/`, **When** `--include-sourcedata` is passed, **Then** `sourcedata/sub-01/` is also renamed.
3. **Given** the target subject `sub-99` already exists, **When** the command is run, **Then** it refuses with exit code 2.
4. **Given** a dataset under git-annex, **When** subject is renamed, **Then** `git mv` / `git annex` commands are used and the operation is a single git commit.

---

### User Story 5 — Rename a session (Priority: P2, need: medium)

Similar to subject-rename but for session entities. Includes the special case of **moving into a session** — a dataset collected without sessions that now needs session identifiers.

**Why this priority**: Medium need per design doc. Uses the same infrastructure as subject-rename.

**Independent Test**: Rename a session in a multi-session bids-examples dataset, validate.

**Acceptance Scenarios**:

1. **Given** a valid dataset with `sub-01/ses-pre/`, **When** `bids-utils session-rename ses-pre ses-baseline` is run, **Then** the session directory and all its files are renamed, and the dataset remains valid.
2. **Given** a dataset without sessions, **When** `bids-utils session-rename '' ses-01` is run (move-into-session), **Then** a `ses-01` level is introduced for all subjects, files are renamed to include `ses-01`, and the dataset remains valid.
3. **Given** a target session that already exists for a subject, **When** the command is run, **Then** it refuses with exit code 2.

---

### User Story 6 — Bubble-up / condense / organize metadata (Priority: P2, need: medium)

A dataset has metadata duplicated across many sidecar JSON files at the leaf level. The user runs `bids-utils metadata aggregate` to hoist common key-value pairs up the BIDS inheritance hierarchy, reducing redundancy and making the dataset easier to overview. Both `aggregate` and `segregate` accept optional path arguments to scope their operation (e.g., per-subject only) and support `--mode copy|move` to control whether metadata is duplicated or relocated.

**Why this priority**: Medium need per design doc. Addresses a real pain point with large datasets. The `aggregate`, `segregate`, and `deduplicate` modes serve different workflows.

**Independent Test**: Run `bids-utils metadata aggregate` on a bids-examples dataset with per-subject JSON files, verify the dataset remains valid and the metadata is equivalent when resolved through the inheritance principle.

**Acceptance Scenarios**:

1. **Given** a dataset where all subjects share `RepetitionTime=2.0` in their `_bold.json`, **When** `bids-utils metadata aggregate` is run, **Then** `RepetitionTime` is moved to a higher-level `_bold.json` and removed from individual files, and the resolved metadata for every file is unchanged.
2. **Given** a subject that is missing a `_bold.json` entirely (but has `_bold.nii.gz`), **When** aggregation is attempted for `RepetitionTime`, **Then** the tool does NOT aggregate that key (since the value is unknown for that subject, not merely identical).
3. **Given** a user running `bids-utils metadata segregate`, **When** the command completes, **Then** all metadata is pushed down to leaf-level files (full self-contained sidecars per file).
4. **Given** `bids-utils metadata audit`, **When** run, **Then** the tool reports metadata keys that are neither fully unique nor fully equivalent across files — indicating potential acquisition inconsistencies.
5. **Given** a dataset with multiple subjects, **When** `bids-utils metadata aggregate sub-01/` is run, **Then** only metadata within `sub-01/` is aggregated (common keys bubble up to `sub-01/` level sidecars), while other subjects' metadata is untouched. By default (no path argument), aggregation operates across all levels of the hierarchy.
6. **Given** `bids-utils metadata aggregate --mode copy`, **When** run, **Then** common metadata is written to the higher-level sidecar but also retained in leaf-level files (normalization by duplication). **Given** `--mode move` (the default), **When** run, **Then** common metadata is removed from leaf-level files after being placed at the higher level (no duplication).

---

### User Story 7 — Remove a subject or session (Priority: P3, need: low)

A dataset maintainer needs to remove a subject (or session) entirely. The tool removes the directory tree, updates `participants.tsv`, and cleans up `_scans.tsv`.

**Why this priority**: Low need per design doc. Straightforward once the core infrastructure exists.

**Independent Test**: Remove a subject from a bids-examples dataset, validate.

**Acceptance Scenarios**:

1. **Given** a valid dataset with `sub-03`, **When** `bids-utils remove sub-03` is run with `--force`, **Then** the subject directory and all files are deleted, `participants.tsv` is updated, and the dataset remains valid.
2. **Given** a remove command without `--force`, **When** run, **Then** the tool prompts for confirmation before proceeding.

---

### User Story 8 — Remove a run (Priority: P3, need: low)

A specific run needs to be removed and subsequent run indices shifted to maintain contiguity (e.g., removing `run-02` means `run-03` becomes `run-02`).

**Why this priority**: Low need per design doc. Niche but important for data curation.

**Independent Test**: Remove a run from a multi-run dataset, verify remaining runs are re-indexed and dataset is valid.

**Acceptance Scenarios**:

1. **Given** a subject with `run-01`, `run-02`, `run-03`, **When** `bids-utils remove-run sub-01 run-02 --shift` is run, **Then** `run-02` files are removed, `run-03` is renamed to `run-02`, and `_scans.tsv` is updated.
2. **Given** `--no-shift` flag, **When** a run is removed, **Then** subsequent runs keep their indices (leaving a gap).

---

### User Story 9 — Merge datasets (Priority: P3, need: medium)

Two BIDS datasets need to be combined — either by simply combining subjects (failing on conflicts) or by placing each dataset into a separate session. A common workflow is incremental merge: BIDS conversion is done per subject/session producing many small datasets, which are then merged one-by-one into a growing target dataset. Merge must also handle intra-session file conflicts (e.g., additional runs from a split acquisition) and metadata conflicts (e.g., differing `participants.tsv` values or aggregated sidecar metadata).

**Why this priority**: Medium per Yarik. Implementation builds on session-rename and also potentially on metadata aggregate/segregate.

**Independent Test**: Merge two bids-examples datasets, validate the result.

**Acceptance Scenarios**:

1. **Given** two valid datasets with non-overlapping subjects, **When** `bids-utils merge datasetA datasetB --output merged/` is run, **Then** all subjects from both datasets appear in the output and the merged dataset is valid.
2. **Given** two datasets with overlapping subject IDs, **When** merge is run without `--into-sessions`, **Then** the tool refuses with exit code 2 listing the conflicts.
3. **Given** `--into-sessions ses-A ses-B`, **When** merge is run, **Then** each dataset's data is placed under the respective session.
4. **Given** an existing target dataset and a newly converted single-subject dataset, **When** `bids-utils merge newdata/ --into existing/` is run, **Then** the new subject is added incrementally to the existing dataset without disturbing other subjects. This supports the common workflow of converting subjects one at a time and merging each into the growing dataset.
5. **Given** a target dataset with `sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_bold.nii.gz` and a source dataset with the same subject/session containing additional BOLD runs, **When** `bids-utils merge --on-conflict add-runs` is run, **Then** the incoming files are assigned the next available `run-` indices (e.g., `run-02`) and merged into the session. **Given** `--on-conflict error` (default), **Then** the tool refuses with exit code 2 listing the conflicting filenames.
6. **Given** two datasets with differing `participants.tsv` values for the same subject (e.g., different `age` across sessions), **When** merge is run, **Then** the tool reports the conflict. **Given** top-level sidecar metadata that differs between the datasets, **When** merge is run with `--reconcile-metadata`, **Then** the tool segregates conflicting metadata down to the appropriate level and re-aggregates to produce correct inheritance.

---

### User Story 10 — Split datasets (Priority: P3, need: low)

A dataset needs to be split — for example, extracting only behavioral data or only stimuli for more efficient sharing.

**Why this priority**: Low need per design doc. Opposite of merge.

**Acceptance Scenarios**:

1. **Given** a valid dataset, **When** `bids-utils split --suffix bold --output bold-only/` is run, **Then** only BOLD-related files (and required metadata) are extracted and the result is a valid BIDS dataset.
2. **Given** a valid dataset, **When** `bids-utils split --datatype anat --output anat-only/` is run, **Then** only anatomical files are extracted, `dataset_description.json` is copied, `participants.tsv` is subset to included subjects, and the result is valid.
3. **Given** a valid dataset, **When** `bids-utils split --suffix bold --dry-run` is run, **Then** the tool lists files that would be extracted without creating any output.
4. **Given** a dataset with inherited metadata (higher-level `.json` sidecars), **When** `bids-utils split --suffix bold --output bold-only/` is run, **Then** inherited metadata that applies to extracted files is preserved in the output (either copied or segregated to leaf level) so the resolved metadata is unchanged.

---

### Edge Cases

- What happens when a rename creates a filename that exceeds OS path length limits?
  → **Resolution**: Refuse with exit code 2 and a clear error. Covered by FR-011 (refuse invalid state). No extra task needed — implement as a guard in `rename_file()`.
- How does the tool handle symlinked files (common with git-annex)?
  → **Resolution**: `_vcs.py` GitAnnex backend handles this. Locked annexed files are symlinks; `git annex` commands operate on them correctly. Covered by T017-T018.
- What happens when `_scans.tsv` references files that don't exist on disk (dangling references)?
  → **Resolution**: Warn but do not fail. Dangling references are a pre-existing dataset issue, not caused by bids-utils. Log at `-v` verbosity.
- How does the tool handle partial datasets (e.g., missing `dataset_description.json`)?
  → **Resolution**: `BIDSDataset.from_path()` raises an error if no `dataset_description.json` is found. Covered by T013-T014.
- What happens when a file is locked by git-annex and content is needed for metadata operations?
  → **Resolution**: All file reads go through a content-aware I/O layer. The behavior is controlled by the `--annexed` policy option (FR-022): `error` (default, informative message), `get` (auto-fetch), `skip-warning`, or `skip`. The VCS backend provides `has_content()` and `get_content()` methods. Covered by T086-T091.
- How does aggregation handle `.nwb` files that embed metadata internally?
  → **Resolution**: Out of scope. bids-utils operates on BIDS sidecar metadata (`.json` files), not on embedded metadata within data files. NWB internal metadata is outside BIDS's inheritance model.
- What happens when operating on a dataset on a read-only filesystem?
  → **Resolution**: Operations will fail with a standard OS permission error. No special handling needed — `--dry-run` is always available for read-only inspection.
- How does the tool handle datasets with both `participants.tsv` and `participants.json`?
  → **Resolution**: `_participants.py` updates `participants.tsv` only. `participants.json` is a sidecar describing column semantics and does not need updating when rows change. Covered by T023-T024.
- How does `migrate` handle a field like `IntendedFor` that uses relative paths but the referenced files don't exist (broken references)?
  → **Resolution**: Convert the path format to BIDS URI regardless — the migration fixes the format, not the referential integrity. Log a warning about the broken reference. Covered by acceptance scenario US2.8 (ambiguous cases skipped with clear reporting).
- How does `migrate` handle deprecated metadata fields that appear in inherited (higher-level) JSON sidecars vs. leaf-level ones?
  → **Resolution**: Migrate the field wherever it appears. The inheritance chain is not changed — if `BasedOn` appears in a root-level sidecar, it is renamed to `Sources` there. Covered by T031-T038.
- What happens when migrating `ScanDate` to `_scans.tsv` but no `_scans.tsv` exists yet for that subject/session?
  → **Resolution**: Create the `_scans.tsv` with the appropriate header and populate the `acq_time` column. Explicitly covered by T036.

## Clarifications

### Session 2026-04-06

- Q: Should `bids-utils completion` auto-detect shell from `$SHELL` or require explicit argument? → A: Auto-detect from `$SHELL`, with optional explicit override argument.
- Q: How should BIDS-aware completions resolve the dataset root? → A: Honor `--dataset` if provided; otherwise walk up from CWD until `dataset_description.json` is found.
- Q: Should `bids-utils completion` offer `--install` to modify shell rc files? → A: No; print activation script to stdout only (user handles installation).
- Q: Which argument types get custom completions initially? → A: Filesystem-derived items (`sub-*`, `ses-*` directories, BIDS file paths) plus entity keys from the schema (`task=`, `run=`, `acq=`, etc.). Entity value discovery deferred.

### Session 2026-04-09

- Q: Where should the `--annexed` option live — per-command or group-level? → A: **Group-level** (`bids-utils --annexed=MODE COMMAND ...`). Every command that reads files is affected (rename reads sidecars, migrate reads JSON, session-rename reads `_scans.tsv`, metadata reads JSON). It's a dataset-level concern, not command-specific. Putting it on the group avoids repeating the option across ~10 commands. The policy flows through `BIDSDataset.annexed_mode` so library users get the same behavior.
- Q: What modes should `--annexed` support? → A: `error` (default), `get`, `skip-warning`, `skip`. Environment variable `BIDS_UTILS_ANNEXED` for persistent preference.
- Q: Should `dataset_description.json` reads be guarded by the annex policy? → A: No. This file is essentially never annexed (small JSON tracked in git). Adding annex awareness to `BIDSDataset.from_path()` creates a chicken-and-egg problem since the dataset object doesn't exist yet.
- Q: Should content fetching be batched? → A: Initial implementation does per-file checks/fetches. Batch optimization (`ensure_content_batch`) can be added later for scan-heavy operations (migrate, metadata audit).
- Q: What about writing to annexed files? → A: Annexed files in locked mode (symlinks to `.git/annex/objects`) are read-only. Before modification, `unlock(paths)` must be called (`git annex unlock` / `datalad unlock`). After modification, `add(paths)` must be called (`git annex add`) to re-annex the file. The I/O layer provides `ensure_writable()` (unlock) and `mark_modified()` (add) to bracket writes. The full lifecycle for a modify operation on an annexed file is: get → unlock → read → modify → write → add.
- Q: Should `unlock`/`add` be implicit or require `--annexed=get`? → A: `unlock` and `add` apply whenever the VCS is git-annex/DataLad, regardless of `--annexed` mode. The `--annexed` mode only controls what happens when content is *missing*. If content is present but the file is locked, any write operation must unlock first — this is a VCS-level concern, not a policy choice.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a Python library (`bids_utils`) with a clean, importable public API. Every CLI command maps to a library function.
- **FR-002**: System MUST provide a CLI (`bids-utils`) as a thin wrapper over the library API.
- **FR-003**: Every mutating command MUST support `--dry-run` / `-n` mode showing exactly what would change without modifying any files.
- **FR-004**: System MUST detect and use VCS (git, git-annex, DataLad) when present — `git mv` instead of `os.rename`, etc. When no VCS is detected, operate directly on filesystem.
- **FR-005**: System MUST update `_scans.tsv` entries whenever referenced files are renamed or removed.
- **FR-006**: System MUST update `participants.tsv` when subjects are renamed or removed.
- **FR-007**: System MUST support `--json` output for machine-readable results alongside human-readable defaults.
- **FR-008**: System MUST use meaningful exit codes: 0=success, 1=error, 2=refused-to-act.
- **FR-009**: System MUST derive BIDS knowledge from `bidsschematools` schema, not hardcoded rules.
- **FR-010**: System MUST support explicit schema version selection (`--schema-version`) or auto-detect from `dataset_description.json` `BIDSVersion` field.
- **FR-011**: System MUST refuse to complete operations that would leave the dataset in an invalid state, with a clear error message.
- **FR-012**: System MUST support `--force` to bypass confirmation prompts on destructive operations.
- **FR-013**: System MUST support `-v` / `-q` verbosity controls.
- **FR-014**: System MUST support `--include-sourcedata` flag for operations that can extend to `sourcedata/` and `.heudiconv/`.
- **FR-015**: Sidecar discovery MUST handle all BIDS-recognized sidecar extensions (`.json`, `.bvec`, `.bval`, `.tsv` for events, etc.) based on the schema.
- **FR-016**: `migrate` MUST derive all deprecation knowledge from the `bidsschematools` machine-readable schema (deprecation rules, metadata definitions, enum definitions) — not from hardcoded migration tables. *(Specific application of FR-009 to the migration subsystem.)*
- **FR-017**: `migrate` MUST default to the current released BIDS version when no `--to` target is specified, and MUST support explicit `--to` for both 1.x and 2.0 targets.
- **FR-018**: `migrate` MUST apply migrations cumulatively — migrating from 1.4 to 1.9 applies all intermediate deprecation fixes in version order.
- **FR-019**: System MUST provide a `bids-utils completion [SHELL]` subcommand that outputs shell completion activation scripts. When `SHELL` argument is omitted, auto-detect from the `$SHELL` environment variable. Supported shells: Bash, Zsh, Fish (matching Click 8.0+ built-in completion support). Output goes to stdout only (no `--install` flag).
- **FR-020**: CLI MUST resolve the BIDS dataset root by: (1) using the `--dataset`/`-d` flag if provided, or (2) walking up the directory hierarchy from CWD until `dataset_description.json` is found. This resolution is used both by commands and by shell completion.
- **FR-021**: Shell completion MUST provide BIDS-aware completions: filesystem-derived items (`sub-*` directories, `ses-*` directories, BIDS file paths) and entity keys from the `bidsschematools` schema (e.g., `task=`, `run=`, `acq=`). Entity value completion (e.g., `task=rest`) is deferred to a later release.
- **FR-022**: System MUST provide a group-level `--annexed` option controlling behavior when git-annex/DataLad file content is not locally available. Modes: `error` (default — informative error listing missing files and suggesting `--annexed=get` or `git annex get`), `get` (automatically fetch content via `git annex get` / `datalad get` before reading), `skip-warning` (skip files without content with a per-file warning), `skip` (skip silently). The option MUST also be settable via `BIDS_UTILS_ANNEXED` environment variable (CLI flag takes precedence). The VCS backend protocol MUST expose: `has_content(path)` and `get_content(paths)` for reads; `unlock(paths)` to make locked annexed files writable before modification; `add(paths)` to re-annex modified files after writes (restoring them to their original tracked state). All file reads (TSV, JSON sidecars) MUST go through a content-aware I/O layer. All file writes to potentially-annexed files MUST go through an unlock-before/add-after lifecycle managed by the I/O layer.

### Key Entities

- **Dataset**: A BIDS-compliant directory tree rooted at `dataset_description.json`. Primary unit of operation.
- **Entity**: A BIDS key-value pair (e.g., `sub-01`, `ses-pre`, `task-rest`, `run-01`). Entities appear in filenames and directory names.
- **Sidecar**: An auxiliary file associated with a primary data file by sharing the same stem but with a different extension (`.json`, `.bvec`, `.bval`).
- **Inheritance Chain**: The ordered set of metadata files that apply to a given data file, from dataset root down to the file's directory level.
- **Scans File**: `_scans.tsv` — a per-subject (or per-session) file listing data files with acquisition metadata.
- **Operation**: A single bids-utils command invocation. Must be atomic — either fully completes or fully rolls back.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every bids-examples dataset that is valid before a `rename`/`subject-rename`/`session-rename` operation is still valid after the operation completes.
- **SC-002**: `--dry-run` output for every command matches the actual changes when run without `--dry-run` (verified by comparing dry-run output to actual filesystem diff).
- **SC-003**: All commands complete on a 1000-subject dataset in O(n) time relative to affected files (not O(n²) in total dataset size). Single-entity operations (rename, remove-run) must not scan the entire dataset. Benchmark target: `rename` on a single file in a 1000-subject dataset completes in under 5 seconds.
- **SC-004**: Library API is independently usable: all acceptance scenarios can be executed via Python imports without the CLI.
- **SC-005**: 100% of mutating commands have both `--dry-run` and `--json` modes tested in CI.
- **SC-006**: Test suite passes against at least 3 different BIDS schema versions (e.g., 1.8, 1.9, 2.0-dev).
- **SC-007**: `migrate` eliminates all deprecation warnings when run on bids-examples datasets created under older schema versions (verified by running the BIDS validator before and after).

## Assumptions

- Users have Python 3.10+ installed (aligned with current ecosystem support).
- `bidsschematools` provides stable, versioned access to the BIDS schema. If its API changes, bids-utils will adapt.
- The BIDS validator (`bids-validator-deno`) is available for integration testing but is not a runtime dependency.
- Datasets fit on local disk for direct operations. Annexed files without local content are handled via `--annexed` policy (FR-022): error by default, with auto-fetch and skip modes.
- The initial release focuses on local filesystem operations. Full DataLad integration (provenance via `datalad run`) is a subsequent enhancement.
- `bids-examples` git repository is available as a submodule or fixture for testing.
- The project uses `uv` for package management, `tox` + `tox-uv` for test orchestration, `ruff` for linting, `mypy` for type checking, `mkdocs` for documentation — as stated in the constitution.
- The CLI entry point is `bids-utils`. The `bids` name on PyPI is a placeholder pointing to pybids, and `bids-utils` is available on PyPI. Using `bids-utils` avoids confusion with the pybids ecosystem.
