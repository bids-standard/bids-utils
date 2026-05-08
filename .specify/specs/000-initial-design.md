# Feature Specification: bids-utils — Core Library & CLI

**Feature Branch**: `000-initial-design`
**Created**: 2026-04-02
**Status**: Draft
**Input**: User description: "Build a Python application/library following what is described in docs/design/000-initial-design.md file"

## User Scenarios & Testing *(mandatory)*

<!--
  Stories are ordered by priority from the design document.
  Each story is independently implementable and testable — delivering
  an MVP that already provides value to BIDS dataset maintainers.
-->

### User Story 1 — Rename a BIDS file (Priority: P1, need: high)

A researcher needs to rename a BIDS file (e.g., to fix a typo, drop a heudiconv `__dup-NN` duplicate, or move a file under a different subject/session container). They run `bids-utils rename SRC DST` (mv-like semantics). The tool renames the primary file **and** all associated sidecar files (`.json`, `.bvec`, `.bval`, etc.), updates any `_scans.tsv` entries that reference the old filename, and uses `git mv` when the dataset is under version control. Per the 2026-04-27 clarifications, in-place **entity-level edits** (set/delete entity key-value pairs in a filename) live in a sibling `edit-filename` command rather than in `rename --set`.

**Why this priority**: Renaming a single file is the atomic building block. `subject-rename`, `session-rename`, and other higher-level operations compose on top of it. Shipping this first unblocks the most common ad-hoc fix-up need and validates the core infrastructure (sidecar discovery, `_scans.tsv` patching, VCS awareness, dry-run output).

**Independent Test**: Rename a file in any bids-examples dataset (and a heudiconv-style `__dup-NN` fixture), then run the BIDS validator to confirm the dataset remains valid.

**Acceptance Scenarios**:

1. **Given** a valid BIDS dataset with `sub-01/func/sub-01_task-rest_bold.nii.gz` and its `.json` sidecar, **When** the user runs `bids-utils rename sub-01/func/sub-01_task-rest_bold.nii.gz sub-01/func/sub-01_task-nback_bold.nii.gz`, **Then** both files are renamed to `sub-01_task-nback_bold.*`, `_scans.tsv` is updated, and the dataset passes validation.
2. **Given** a BIDS dataset under git, **When** the user runs `bids-utils rename SRC DST --dry-run`, **Then** the tool prints the planned renames without modifying any files or git state.
3. **Given** a file with an associated `_scans.tsv` entry, **When** the file is renamed, **Then** the corresponding row in `_scans.tsv` is updated to reflect the new filename.
4. **Given** a file that is referenced nowhere else, **When** renamed, **Then** only the file and its sidecars are affected — no unrelated files change.
5. **Given** a rename that would produce a filename conflicting with an existing file, **When** the user runs the command, **Then** the tool refuses with exit code 2 and a clear error message.
6. **Given** a heudiconv-style file `sub-qa64/ses-20220217/func/sub-qa64_ses-20220217_task-rest_acq-p2_bold__dup-01.nii.gz` (non-BIDS due to `__dup-01` segment), **When** the user runs `bids-utils rename SRC sub-qa64/ses-20220217/func/sub-qa64_ses-20220217_task-rest_acq-p2_run-02_bold.nii.gz`, **Then** the primary file and its full-literal-stem sidecars (e.g., `..._bold__dup-01.json`) are renamed to the BIDS-clean target, `_scans.tsv` is updated, and the dataset passes validation.
7. **Given** `DST` is a directory under a **different subject/session container** (e.g., `bids-utils rename sub-01/ses-pre/func/sub-01_ses-pre_task-rest_bold.nii.gz sub-02/ses-post/func/`), **When** the command runs, **Then** the file (and its sidecars) is moved into the destination directory **and** the `sub-`/`ses-` entity labels in the filename are rewritten to match the destination (`sub-02_ses-post_task-rest_bold.nii.gz`) by delegating to `edit-filename` semantics. Conflicts and `_scans.tsv` updates are handled the same way as a same-directory rename.
8. **Given** a shell glob spanning multiple files / subjects / sessions (e.g., `bids-utils edit-filename sub-*/func/sub-*_task-rest_bold.nii.gz --set task=nback`), **When** the command runs, **Then** the same edit is applied to every matched file (and each file's sidecars, per FR-038), `_scans.tsv` updates are coalesced per `(subject, session)` container, and the dataset remains valid. **Given** any one of the resulting target paths conflicts with an existing file, **When** the command runs, **Then** the entire batch is refused with exit code 2 *before any filesystem mutation* — none of the matched files are renamed (atomic-at-batch-level, FR-043).
9. **Given** `bids-utils rename SRC1 SRC2 SRC3 DSTDIR/` (multi-source mv semantics, `DSTDIR` is an existing directory), **When** the command runs, **Then** all three sources (with their sidecars and `_scans.tsv` rows) are moved into `DSTDIR/`, with cross-container entity-label rewriting applied where applicable; if any single target conflicts the whole batch is refused with exit code 2 and the filesystem is unchanged.

---

### User Story 2 — Migrate a dataset within BIDS 1.x to address deprecations (Priority: P1, need: high)

A lab maintains a BIDS dataset created under an older 1.x version (e.g., 1.4 or 1.6). Over time, the BIDS specification has deprecated metadata fields, suffixes, coordinate-system values, and path formats. The dataset still validates but emits deprecation warnings. The user runs `bids-utils migrate` (defaulting to the current released 1.x version) to bring the dataset up to date, resolving all deprecations automatically where possible.

The BIDS specification has accumulated significant deprecations within the 1.x series that `migrate` must handle:

- **Metadata field replacements**: `BasedOn` → `Sources`, `RawSources` → `Sources`, `ScanDate` → `acq_time` column in `_scans.tsv` (PET, since 1.6.0), `DCOffsetCorrection` → deprecated (iEEG, `rules/sidecars/ieeg`), `AcquisitionDuration` → `FrameAcquisitionDuration` (BOLD/ASL, `rules/sidecars/func` + `rules/checks/func`), `HardcopyDeviceSoftwareVersion` → deprecated (MRI, `rules/sidecars/mri`)
- **Path format → BIDS URI migration** (since 1.8.0): `IntendedFor`, `AssociatedEmptyRoom`, `Sources` fields that use relative paths must be converted to BIDS URIs (`bids::` scheme)
- **Value format changes**: `DatasetDOI` bare DOIs → URI format (since 1.8.0)
- **Suffix deprecations** (since 1.5.0): `_phase` → `_part-phase_bold`, and deprecated anatomical suffixes `T2star`, `FLASH`, `PD`
- **Coordinate system value renames**: `ElektaNeuromag` → `NeuromagElektaMEGIN`, deprecated template identifiers (`fsaverage3`–`fsaverage6` → `fsaverage`, `fsaveragesym` → `fsaverageSym`, versioned `UNCInfant*` → `UNCInfant`)
- **TSV column value deprecation**: `age` column string `"89+"` → numeric `89` (schema `columns.age` says "89+" is DEPRECATED). Only the string format is auto-fixed; numeric values > 89 are a separate optional HIPAA-compliance migration. Migration MUST be unit-aware — the 89-year threshold only applies when age units are years (see bids-standard/bids-specification#1633).

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
10. **Given** a dataset with `participants.tsv` containing `age` column with value `"89+"`, **When** `bids-utils migrate` is run, **Then** the string `"89+"` is replaced with numeric `89` and the dataset passes validation without the `AGE_89` warning.
11. **Given** a dataset with `participants.tsv` containing `age` column with numeric value `92`, **When** `bids-utils migrate` is run (default `--level=safe`), **Then** the value is **not** modified (only the deprecated string format is auto-fixed). **Given** `bids-utils migrate --level=advisory` (or `--rule-id=age_cap_89`), **Then** the value is capped to `89`.
12. **Given** a dataset with `participants.tsv` where `participants.json` defines `"Units": "months"` for the `age` column, **When** `bids-utils migrate` is run, **Then** the `"89+"` string deprecation fix is **skipped** because the 89-year threshold does not apply to non-year units, and a warning is emitted explaining the unit mismatch.
13. **Given** a BOLD dataset with `AcquisitionDuration` in sidecar JSON (with `VolumeTiming` present), **When** `bids-utils migrate` is run, **Then** the field is renamed to `FrameAcquisitionDuration`.

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
6. **Given** a valid BIDS 1.x dataset with `participants.tsv` and `participants.json`, **When** `bids-utils migrate --to 2.0` is run, **Then** `participants.tsv` is renamed to `subjects.tsv`, `participants.json` is renamed to `subjects.json`, the `participant_id` column is renamed to `subject_id`, and `BIDSVersion` in `dataset_description.json` is updated (bids-standard/bids-2-devel#14).
7. **Given** a dataset where JSON sidecar `Sources` fields contain BIDS URIs referencing `participants.tsv`, **When** `bids-utils migrate --to 2.0` is run, **Then** those URIs are updated to reference `subjects.tsv`. *(Depends on a generic BIDS URI fixup helper — see FR-025.)*

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
  → **Resolution**: All file iteration code MUST treat symlinks as files (FR-023). `Path.is_file()` follows symlinks and returns `False` for annexed files without content — use `not path.is_dir()` instead. VCS operations (`git mv`, `git annex unlock/add`) handle symlinks correctly. Covered by T092.
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
- **BUG (2026-04-16, integration tests)**: When `rename_file()` adds or modifies entities (e.g., `--set run=99`), the resulting filename preserves Python dict insertion order, NOT the schema-defined entity order. BIDS requires entities in a specific order (e.g., `run` before `recording`, `run` before `chunk`). Validator reports `FILENAME_MISMATCH`. **Resolution**: `BIDSPath.to_filename()` MUST reorder entities according to the schema's entity order (`BIDSSchema.entity_order()`). Requires FR-035.
- **BUG (2026-04-16, integration tests)**: Directory-based BIDS data files (CTF MEG `.ds/` directories, Zarr `.ome.zarr/` directories) are skipped by session-rename and subject-rename because the file iteration code uses `not path.is_dir()` to find files. These directories are BIDS data "files" that contain the entity labels in their directory name and MUST be renamed. Validator reports `INVALID_LOCATION`. **Resolution**: File iteration must also match BIDS directory patterns (`.ds`, `.zarr`, `.ome.zarr`). FR-036.
- **BUG (2026-04-16, integration tests)**: After subject-rename and session-rename, `IntendedFor` fields in fieldmap sidecars still reference old paths (old subject/session labels). Validator reports `INTENDED_FOR`. **Resolution**: `update_json_references()` in `_io.py` scans JSON sidecars for reference fields and updates old labels. This is the simplified version of FR-025; the full generic BIDS URI fixup helper remains planned.
- **RULE**: All file-scanning functions (`_scan_json_files`, `_scan_bids_files`, `update_json_references`) MUST skip **all dotdirs** (directories starting with `.`) — not just `.git` and `.datalad`. BIDS never stores data in dotdirs, and the bids-validator similarly ignores them.
- `find_sidecars()` in `_sidecars.py` discovers **same-directory** companion files only. It does NOT walk the BIDS inheritance hierarchy (`task-rest_bold.json` at dataset root is not returned). For inheritance-aware metadata resolution, see `metadata.py`. For data files (not `.json`/`.bvec`/`.bval`), all same-stem files are discovered (catches BrainVision `.eeg`/`.vhdr`/`.vmrk` and segmentation `.tsv` label tables).
- **BUG (2026-04-16, integration tests)**: `_scans.tsv` entries not fully updated after some rename operations — entries still reference old filenames. Validator reports `SCANS_FILENAME_NOT_MATCH_DATASET`. **Resolution**: Audit `_scans.py` update logic for completeness, especially when renaming across session/subject boundaries.
- **BUG (2026-04-16, integration tests)**: `participants.tsv` `participant_id` column not properly updated in some subject-rename scenarios (e.g., `ds000248` where subjects have unusual naming). Validator reports `PARTICIPANT_ID_MISMATCH`. **Resolution**: Audit `_participants.py` rename logic.
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

### Session 2026-04-10

- Q: Should `--dry-run` show every file operation or just a summary? → A: Both. `--dry-run` (no value or `--dry-run=overview`) shows the current summary view (one line per subject/session). `--dry-run=detailed` lists every individual file rename, file edit, and `_scans.tsv` update. The detailed mode is what users need to verify correctness before committing. The overview mode remains the default for quick checks.
- Q: How should annexed content operations be logged? → A: When `--annexed=get` fetches content, log each file fetched at normal verbosity. In `--dry-run` mode, report which files *would* need content fetched. At `-v`, also log `unlock` and `add` operations.
- **BUG (fixed T092)**: `session.py` and `subject.py` use `Path.is_file()` to filter files for renaming, but `is_file()` follows symlinks — returning `False` for annexed files without local content (broken symlinks into `.git/annex/objects`). This means **annexed data files (`.nii.gz`, etc.) are silently skipped during rename**. The fix: use `not path.is_dir()` or `path.is_file() or path.is_symlink()` everywhere that iterates over files for processing. This affects `session.py`, `subject.py`, `run.py`, `split.py`, `merge.py`, `_sidecars.py`, and `migrate.py`. All existing tests missed this because they use `tmp_path` fixtures with real files, never symlinks.
- **BUG (fixed)**: `cli/rename.py` uses `Path.resolve()` which follows symlinks, resolving annexed files to `.git/annex/objects/...` paths. Then `git mv` fails because it's trying to move the annex object, not the symlink. Fix: use `Path.absolute()` instead. Similarly, `rename.py` uses `path.exists()` to check file existence, which returns `False` for broken symlinks. Fix: `path.exists() or path.is_symlink()`.
- **RULE**: In git-annex codepaths, NEVER use `Path.resolve()` on files that may be symlinks. Use `Path.absolute()` instead. NEVER use bare `Path.exists()` when the file might be an annexed symlink — use `path.exists() or path.is_symlink()`.
- Q: Why didn't the `bids-examples` integration tests catch the symlink bug? → A: `bids-examples` datasets contain regular files, not annexed symlinks. Integration tests need a fixture that creates a git-annex repo with locked (symlinked) files to exercise this path. Add a `tmp_annex_dataset` fixture.

### Session 2026-04-10 (testing)

- **PROBLEM**: Most bids-examples integration tests run in dry-run mode only. Dry-run tests verify the code doesn't crash but do NOT verify the operation produces correct results (SC-001 requires datasets remain valid after operations). Dry-run testing is necessary but insufficient.
- Q: What should the integration test pattern be? → A: Copy dataset to tmp_path, run mutating operation, validate result. For validation: (1) structural checks (file counts, no stale references), (2) `bids-validator-deno` before+after (skip if validator not installed). The existing `_copy_dataset` helper + `git reset --hard; git clean -dfx` for annexed clones.
- Q: Should `bids-validator-deno` be a test dependency? → A: Yes, add to `[project.optional-dependencies] test`. Skip validator tests if not installed (graceful degradation). The validator is the authoritative check for SC-001.
- Q: How to reset bids-examples after mutation? → A: Don't mutate bids-examples in-place. Always `shutil.copytree` to `tmp_path` first, then mutate the copy. For git-annex mode, copy + `git annex init` + force annex.

### Session 2026-04-15

- Q: For the age 89+ migration (`columns.age` schema says "89+" is DEPRECATED): should migrate handle both string `"89+"` and numeric values > 89? → A: **B — only convert the deprecated string format `"89+"` → `89` (numeric).** Capping numeric values > 89 is a separate, optional migration (HIPAA compliance) that should be offered when such values are observed but not auto-applied by default. **Critical constraint**: the age migration MUST be unit-aware — if `participants.json` sidecar defines `"Units"` for the `age` column (e.g., months, days), the 89-year threshold does not apply to non-year values. See bids-standard/bids-specification#1633 for the ongoing discussion about formalizing age units. **TODO**: clarify how column units are determined — the sidecar `"definition"` mechanism and `"Units"` override pattern need resolution upstream before the HIPAA-compliance optional migration can correctly handle non-year units.
- Q: Should `DCOffsetCorrection` migration be implemented given it wasn't found in schema checks? → A: **It IS in the schema** — at `rules/sidecars/ieeg/iEEGRecommended/fields/DCOffsetCorrection: deprecated`, which was missed by only searching `rules/checks` and `objects/metadata`. The schema declares deprecations at multiple levels: `rules/sidecars` (field level annotations), `rules/checks` (validator check rules), `objects/metadata` (description text), `objects/enums` (description text), `objects/columns` (description text), `objects/suffixes` (description text). **All levels must be scanned** when building the migration rule inventory. Additionally found: `HardcopyDeviceSoftwareVersion` deprecated at `rules/sidecars/mri/MRIHardware` — not previously in the spec. **Action items**: (1) Implement a **schema deprecation audit** function that compares the migration rule registry against all deprecation markers in the loaded schema and reports any unimplemented deprecations. This should run as a test (`test_migration_coverage_vs_schema`) and also be exposed as `bids-utils migrate --audit`. (2) Create a **GitHub issue template** for reporting missing migration rules, so users can easily file issues when they discover a schema deprecation without a corresponding migration. (3) The audit should recommend upgrading `bidsschematools` if the installed version is not the latest, or filing an issue if a deprecation is present but unhandled.
- Q: How should tiered migration levels be exposed in the CLI? → A: **Migration rules should have a formalized schema** (similar to how validators have schemas for validation checks, harmonized e.g. in dandi-cli). The existing `MigrationRule` dataclass already has `id`, `category`, `description` — extend it with a `level` field (`safe`, `advisory`, `non-auto-fixable`). CLI exposes **filtering by rule attributes**: `--level=safe` (default — only auto-fixes), `--level=advisory` (includes safe + opt-in), `--level=all`. Individual rules can also be selected/excluded by `--rule-id`. Separately, a `--mode` flag controls interaction behavior: `auto` (default — currently non-interactive; PTY-aware interactive prompting is planned as a post-MVP enhancement, see FR-030 and T103), `non-interactive` (only applies auto-fixable rules, skips prompts), `interactive` (planned: walks through each finding, prompting for decisions on advisory/ambiguous items). This replaces per-migration flags like `--hipaa-deidentify` with a composable `--level=advisory --rule-id=age_cap_89` pattern.
- Q: Should `AcquisitionDuration` → `FrameAcquisitionDuration` rename apply unconditionally or only when `VolumeTiming` is present? → A: **Only when `VolumeTiming` is also present** (matching schema check `func.DeprecatedAcquisitionDuration` semantics). Without `VolumeTiming`, `AcquisitionDuration` may have different semantics (total scan duration) and renaming it unconditionally could introduce incorrect metadata. Cases without `VolumeTiming` should be flagged as non-auto-fixable. **Design note**: this is another case for an optional/advisory migration tier — where the tool could offer to rename the field *and* prompt for the additional metadata context needed, but not auto-apply. This tiered migration pattern (safe auto-fix vs. optional advisory) is emerging as a recurring need (age HIPAA capping, AcquisitionDuration without VolumeTiming) and should be designed as a first-class concept in the migration framework.
- Q: For `participants.tsv` → `subjects.tsv` (bids-2-devel#14), what is the migration scope? → A: **Strict scope**: rename `participants.tsv` → `subjects.tsv`, rename `participants.json` → `subjects.json`, rename `participant_id` column → `subject_id` column, update `BIDSVersion` in `dataset_description.json`. BIDS URIs referencing the renamed file should also be updated, but this should be handled by a **generic BIDS URI fixup helper** (FR-025) — not migration-specific logic. This helper scans JSON/TSV files for `bids:` URIs referencing renamed files and updates them. The helper is reusable by any operation that renames files (rename, subject-rename, migrate, etc.) and may not yet be fully scoped.

### Session 2026-04-27

Scope: ensuring `bids-utils rename` (and related file-level commands) operate correctly on non-BIDS-named source files such as heudiconv duplicate-run output (`..._bold__dup-01.nii.gz`). Closes/addresses bids-standard/bids-utils#14. A separate future `normalize` command (FR-037) will handle deeper canonicalization (entity-label sanitization, key lowercasing, optional `__dup-NN` stripping) and is out of scope here.

- Q: For a non-BIDS source filename `X__dup-NN.<ext>`, what stem-matching rule should `find_sidecars()` use? → A: **A — full literal stem match**. Only files sharing the exact stem `X__dup-NN` (e.g., `X__dup-NN.json`, `X__dup-NN.bvec`) are treated as sidecars. Rationale: heudiconv emits a paired `.json` per duplicate (each `__dup-NN` carries its own acquisition metadata); merging them would be semantically wrong. This is also the only safe default for unrecognized non-BIDS suffixes from other tools.
- Q: How should the user express "rename non-BIDS source → clean BIDS target" in the CLI? → A: **Split the current `rename --set ...` into two commands** ("explicit better than implicit"):
   - `rename SRC DST` — pure path-rename (mv-like). Renames the primary file plus its sidecars (per FR-038 stem rules), updates `_scans.tsv`, and uses `git mv` when applicable. **Super-power**: if `DST` is a directory (or a path under a different subject/session container), the rename understands that the move crosses BIDS hierarchy boundaries and rewrites entity labels accordingly (e.g., moving a file from `sub-01/ses-pre/...` into `sub-02/ses-post/` rewrites the `sub-`/`ses-` entities in the filename to match the destination). Internally this delegates to `edit-filename` semantics to perform the label rewrite.
   - `edit-filename SRC --set/--delete/...` — new sibling command that performs in-place entity-level edits on a file's name (and its sidecars / `_scans.tsv` references) without changing the file's directory. This is where `--set`/`--delete` lives going forward. Entity-order normalization (FR-035) applies here.
   - This decision replaces the original `rename ... --set entity=value` interface in US1.1 and folds entity-mutation use cases into the new `edit-filename` command.
- Q: Which file-touching commands MUST be tested/required to operate correctly on non-BIDS source filenames (heudiconv `__dup-NN`, stray `_test` suffixes, etc.) in this initial release? → A: **D — `rename`, `edit-filename`, `remove`, `subject-rename`, `session-rename`.** Rationale: these are the structural file-level commands a user is likely to wield on a freshly-converted (heudiconv) tree where invalid filenames are most common. `migrate` is deferred — its deprecation logic generally assumes valid BIDS input and the extension cost outweighs the value in this round; non-BIDS robustness for `migrate` can be added later. The shared underpinning is FR-038 (full-literal-stem sidecar discovery) plus FR-036 (directory-data-file iteration), exercised by all five commands.
- Q: What pre/post validator contract should the non-BIDS-source integration tests enforce? → A: **A — pre-validate AND post-validate.** Each non-BIDS-source integration test MUST run the BIDS validator on the worktree **before** the operation under test and assert that the validator flags the injected non-BIDS files (proves the synthetic fixture actually produced an invalid dataset, so a regression in the fixture itself is observable). It MUST then run the operation, run the validator **after**, and assert the validator passes (or only emits pre-existing unrelated warnings unchanged from before injection). This satisfies the spirit of SC-001 — *valid-before → valid-after* — while making fixture-construction bugs detectable rather than silent. As before, validator-dependent assertions degrade gracefully when `bids-validator-deno` is not installed.
- Q: How should non-BIDS source filenames be produced for testing? → A: **B (refined) — synthesize at test time** by injecting non-BIDS suffixes into selected files within an ephemeral, **per-test git worktree** of the local `bids-examples` clone (no `shutil.copytree`). Pattern (intended to be generic for *all* `bids-examples`-based tests, not just non-BIDS-source ones):
   - From the local `bids-examples` clone, create a throwaway `git worktree add` at a unique path under `tmp_path`.
   - Run the operation under test inside that worktree.
   - On teardown, `git worktree remove` (and prune if needed) — no in-place mutation of the shared clone.
   - This replaces the existing `_copy_dataset` helper and `git reset --hard` reset pattern from the 2026-04-10 testing clarifications for new tests; the old helper can stay for backward compatibility but new fixtures SHOULD use the worktree approach.
   - For non-BIDS-source coverage specifically, a fixture helper injects synthetic suffixes (`__dup-NN` à la heudiconv, plus additional adversarial cases like `+mine`, `--crap`, stray `_test`) on a handful of randomly selected (deterministic seed) files within the worktree before invoking the command.
   - Real heudiconv runs on DICOM fixtures are **not** required (too heavyweight for CI); synthesis is sufficient because the goal is to exercise our filename-handling code, not heudiconv itself.

### Session 2026-05-02

Refinement of Session 2026-04-27 after initial implementation review. Two follow-ups:

- Q: The new entity-mutation command also handles `--set-suffix`, not just entity values. Should it still be called `edit-entities`? → A: **No — rename it to `edit-filename`** (CLI), `edit_filename` (library / module). Rationale: it edits the *filename* in place, which includes both the entity portion and the suffix; calling it `edit-entities` would mislead users about scope. All five design docs (spec, plan, tasks, contracts/library-api, data-model, quickstart) updated to use the new name.
- Q: Should the new commands accept batch / glob input — applying the same edit across many files / subjects / sessions in one invocation? → A: **Yes (FR-043).** Both `rename` and `edit-filename` accept multiple `SRC` positional arguments; for `rename`, the destination must be a directory when there are multiple sources (Unix `mv` semantics). The whole batch is **atomic** — every target path is precomputed and validated up front; any conflict refuses the entire batch with exit code 2 before any filesystem mutation. `_scans.tsv` updates are coalesced per `(subject, session)`. The library API mirrors the CLI via `PathArg = PathLike | Sequence[PathLike]`. The motivating use cases (from quickstart): `bids-utils edit-filename sub-01/func/sub-01_task-rest_*bold.* --set task=nback` (across multiple runs and the matching `.json` sidecars when shells glob through them) and `bids-utils edit-filename sub-*/func/sub-*-rest_bold.nii.gz --set run=99 --set acq=p2` (across subjects).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a Python library (`bids_utils`) with a clean, importable public API. Every CLI command maps to a library function.
- **FR-002**: System MUST provide a CLI (`bids-utils`) as a thin wrapper over the library API.
- **FR-003**: Every mutating command MUST support `--dry-run` / `-n` mode showing exactly what would change without modifying any files. `--dry-run` (or `--dry-run=overview`) shows a summary view; `--dry-run=detailed` lists every individual file operation (rename, edit, content fetch). SC-002 applies to the detailed mode.
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
- **FR-023**: All code that iterates over files MUST treat symlinks as files (not skip them). Use `not path.is_dir()` or `path.is_file() or path.is_symlink()` instead of bare `path.is_file()`. This is critical for git-annex datasets where data files are symlinks to `.git/annex/objects`.
- **FR-024**: Annexed content operations (get, unlock, add) MUST be logged. At normal verbosity, log each file fetched by `--annexed=get`. In `--dry-run` mode, report files that would need content fetched. At `-v`, also log unlock/add operations. This gives users visibility into what the annex layer is doing.
- **FR-025**: System SHOULD provide a generic **BIDS URI fixup helper** that, given a mapping of old→new file paths, scans JSON and TSV files for `bids:` URIs referencing the old paths and updates them to the new paths. This helper is reusable across operations that rename files (`rename`, `subject-rename`, `session-rename`, `migrate`). Initial scope: update `bids::` scheme URIs in metadata fields known to contain them (`IntendedFor`, `AssociatedEmptyRoom`, `Sources`, `DerivedFrom`). Full scoping deferred — design must handle cross-dataset URIs (`bids:ds001::...`) and partial path matches.
- **FR-026**: `migrate` MUST handle the `AcquisitionDuration` → `FrameAcquisitionDuration` metadata field rename for BOLD/ASL sidecars, but ONLY when `VolumeTiming` is also present in the same sidecar (matching schema check `func.DeprecatedAcquisitionDuration` semantics). When `AcquisitionDuration` exists without `VolumeTiming`, the finding MUST be flagged as non-auto-fixable. An optional/advisory migration tier MAY offer to rename the field with user confirmation in ambiguous cases.
- **FR-027**: `migrate` MUST handle the deprecated `"89+"` string format in `participants.tsv` `age` column, converting it to numeric `89` (level: `safe`). This migration MUST be unit-aware: skip if the sidecar defines non-year units for the `age` column. A separate `advisory`-level rule (`age_cap_89`) SHOULD cap numeric values > 89 to `89` (HIPAA compliance), activated via `--level=advisory` or `--rule-id=age_cap_89`.
- **FR-029**: Each `MigrationRule` MUST have a formalized schema with at minimum: `id` (unique string identifier, e.g., `"age_89plus_string"`), `level` (`safe` | `advisory` | `non-auto-fixable`), `category`, `from_version`, `description`. This schema serves the same role as validator schemas (cf. dandi-cli harmonization across validators). Rules MUST be filterable by these attributes from both the library API and CLI.
- **FR-030**: `migrate` CLI MUST support `--level=safe` (default), `--level=advisory`, `--level=all` for selecting which tiers of migration rules to apply. Individual rules can be included/excluded via `--rule-id=ID` and `--exclude-rule=ID`. Additionally, `--mode=auto` (default — non-interactive; interactive prompting is a future enhancement), `--mode=non-interactive` (only applies auto-fixable rules, skips prompts). A `--mode=interactive` option (walks through each finding, prompting for decisions on advisory/ambiguous items) SHOULD be added in a subsequent release. The library API MUST expose equivalent filtering parameters.
- **FR-028**: `migrate --to 2.0` MUST rename `participants.tsv` → `subjects.tsv`, `participants.json` → `subjects.json`, rename the `participant_id` column → `subject_id`, and update `BIDSVersion` in `dataset_description.json` (bids-standard/bids-2-devel#14). BIDS URI references to the renamed file SHOULD be updated via FR-025.
- **FR-031**: `migrate` MUST handle `DCOffsetCorrection` → `SoftwareFilters` (iEEG, schema `rules/sidecars/ieeg/iEEGRecommended`, bids-specification PR #799). The migration MUST move the `DCOffsetCorrection` value into a nested entry within the `SoftwareFilters` dict: `"SoftwareFilters": {"DCOffsetCorrection": {"description": VALUE}}`. When `SoftwareFilters` already exists, the new entry MUST be merged (appended) into the existing dict, not replace it. The original `DCOffsetCorrection` field MUST be removed after migration. Level: `safe` (lossless structural migration — value is preserved, not deleted).
- **FR-032**: `migrate` MUST handle `HardcopyDeviceSoftwareVersion` → deprecated (MRI, schema `rules/sidecars/mri/MRIHardware`). No replacement field is specified in the schema. The migration MUST remove the field with a warning. Level: `advisory` (removing a field is data-lossy — user should confirm or use `--level=advisory`). If a replacement is later identified in the schema, this should be updated to a structural migration like FR-031.
- **FR-033**: System MUST provide a **schema deprecation audit** that compares the registered migration rules against all deprecation markers in the loaded `bidsschematools` schema (scanning `rules/sidecars` field annotations, `rules/checks`, `objects/metadata` descriptions, `objects/enums`, `objects/columns`, `objects/suffixes`). Unimplemented deprecations MUST be reported. This audit MUST be: (a) a test (`test_migration_coverage_vs_schema`) that fails when new schema deprecations appear without corresponding rules, (b) exposed via `bids-utils migrate --audit` CLI subcommand, (c) able to recommend upgrading `bidsschematools` if not the latest version or filing an issue if a deprecation is unhandled.
- **FR-034**: The project MUST provide a **GitHub issue template** for reporting missing migration rules. The template should pre-fill fields for: schema version, deprecation location in schema, affected metadata field/suffix/enum, and expected migration behavior. This enables users and the audit tool to create actionable issues that are easily filterable among other project issues.
- **FR-035**: `BIDSPath.to_filename()` MUST emit entities in the order defined by the BIDS schema (`BIDSSchema.entity_order()`), not in Python dict insertion order. When a `BIDSSchema` is available (e.g., via `BIDSDataset`), any operation that mutates entity values in a filename (the new `edit-filename` command, the implicit entity-rewrite path of `rename SRC DST` when `DST` crosses subject/session containers, `subject-rename`, `session-rename`, `migrate`) MUST reorder entities before writing the new filename. This ensures `edit-filename ... --set run=99` produces `sub-01_task-rest_run-99_recording-bipolar_emg.edf` (correct order) not `sub-01_task-rest_recording-bipolar_run-99_emg.edf`.
- **FR-036**: File iteration in rename, subject-rename, session-rename, and all operations that enumerate BIDS files MUST also match BIDS **directory-based data files** — specifically `.ds` directories (CTF MEG) and `.zarr`/`.ome.zarr` directories (microscopy/Zarr). These directories carry entity labels in their name and MUST be renamed alongside regular files. The current `not path.is_dir()` filter incorrectly skips them.
- **FR-038**: `find_sidecars()` MUST be robust to non-BIDS-named source files (e.g., heudiconv duplicate-run output `..._bold__dup-01.nii.gz`). For such files, sidecar discovery MUST use the **full literal stem** of the source — only files sharing that exact stem (e.g., `..._bold__dup-01.json`, `..._bold__dup-01.bvec`) are treated as sidecars. The function MUST NOT attempt to canonicalize or strip non-BIDS trailing segments before stem comparison. (Closes part of bids-standard/bids-utils#14.)
- **FR-039**: `bids-utils rename SRC [SRC ...] DST` MUST implement mv-like rename semantics over BIDS files. Single-source form (`rename SRC DST`) renames the primary file, its sidecars (using FR-038 stem rules so that non-BIDS source filenames like heudiconv `__dup-NN` are handled), updates `_scans.tsv` rows referencing the old filename, and uses `git mv` (or annex-equivalent) when the dataset is under VCS. Multi-source form (`rename SRC SRC ... DST`) is permitted when `DST` is an existing directory and is governed by the batch contract in FR-043. `rename` MUST NOT support entity-mutation flags `--set` / `--delete` / `--suffix` / `--set-suffix` — those live in `edit-filename` (FR-040); passing them MUST yield a non-zero exit and a hint pointing to `edit-filename`. When `DST` (or a multi-source destination directory) lives under a different `sub-XX/[ses-YY]/` container than the source(s), `rename` MUST detect the cross-container move and rewrite the `sub-`/`ses-` (and any other container-implied) entity labels in the destination filename(s) to match the destination path, delegating to `edit-filename`'s entity-rewrite core. The result MUST satisfy entity-order normalization (FR-035). Conflicts are refused with exit code 2 (FR-011) per the atomic-batch rules of FR-043.
- **FR-040**: System MUST provide a `bids-utils edit-filename SRC [SRC ...] --set KEY=VALUE [--delete KEY ...] [--set-suffix SUFFIX]` command that performs in-place edits to one or many BIDS files' filenames — both the entity portion AND the suffix — and to their sidecars / `_scans.tsv` references, **without** changing each file's directory. `edit-filename` is the canonical home for the `--set` / `--delete` / `--set-suffix` semantics formerly attached to `rename`. (The command is named `edit-filename`, not `edit-entities`, because it covers the suffix in addition to entities.) Output filenames MUST satisfy entity-order normalization (FR-035). `edit-filename` MUST be robust to non-BIDS source filenames (FR-038), preserving any unrecognized non-BIDS trailing segments (e.g., `__dup-NN`) verbatim unless the user explicitly asks for normalization (deferred to FR-037). Batch / glob input (multiple `SRC` paths spanning multiple files / subjects / sessions) MUST be supported per FR-043. Conflicts are refused with exit code 2 (FR-011).
- **FR-041**: The following file-touching commands MUST operate correctly on non-BIDS-named source files (e.g., heudiconv `..._bold__dup-01.nii.gz`, files with stray `_test` suffixes): `rename`, `edit-filename`, `remove`, `subject-rename`, `session-rename`. Each MUST: (a) discover sidecars via FR-038 full-literal-stem matching, (b) include such files in iteration (FR-023, FR-036), (c) update `_scans.tsv` rows that reference them, and (d) preserve any unrecognized non-BIDS trailing segments verbatim except where the user explicitly opts in to normalization (FR-037). `migrate` is **out of scope** for this requirement in the initial release. Each of the five listed commands MUST have integration tests exercising at least one heudiconv-style `__dup-NN` fixture and at least one stray-non-BIDS-suffix fixture (see FR-042 / SC-009).
- **FR-042**: The integration test suite MUST provide a generic `bids-examples`-based fixture pattern using **per-test git worktrees**: from the local `bids-examples` clone, `git worktree add` a unique throwaway worktree under `tmp_path`, run the operation under test inside it, then `git worktree remove` it on teardown (no in-place mutation of the shared clone). This SHOULD replace the existing `_copy_dataset` / `git reset --hard` pattern for new tests. Additionally, a fixture helper MUST be available to inject synthetic non-BIDS filename suffixes — heudiconv-style `__dup-NN`, plus adversarial cases such as `+mine`, `--crap`, and stray `_test` — into a deterministic (seeded) selection of files within the worktree, so the FR-041 commands can be exercised against realistic non-BIDS source filenames without requiring a real heudiconv/DICOM toolchain in CI.
- **FR-043**: Both `rename` and `edit-filename` MUST accept **batch / glob input** — multiple `SRC` positional arguments (typically supplied via shell-glob expansion) that may span multiple files, subjects, and sessions in a single invocation. (a) For `edit-filename`, the same edit (`--set`, `--delete`, `--set-suffix`) is applied to every matched source. (b) For `rename`, multi-source input is permitted when the destination is an existing directory (mirrors Unix `mv SRC ... DST/`). (c) Every batch operation MUST be **atomic at the batch level**: every target path is computed and validated up front; if ANY target conflicts (existing file, schema violation, etc.) the entire batch is refused with exit code 2 *before any filesystem mutation occurs* — no partial completion. (d) `_scans.tsv` updates MUST be coalesced per `(subject, session)` container so a batch produces one update per scans file, not one per source. (e) The library API MUST mirror the CLI: `rename_file()` and `edit_filename()` accept a single path or a sequence of paths (`PathArg = PathLike | Sequence[PathLike]`). (f) Per Constitution Principle VIII (Observability), each per-source change MUST appear as its own `Change` entry in `OperationResult.changes`, and `--dry-run=detailed` MUST list every per-source change individually — batch input does not coalesce the user-facing change log even though it does coalesce `_scans.tsv` writes.
- **FR-037** *(deferred / future work — TODO)*: System SHOULD provide a dedicated `bids-utils normalize` (or similarly named) command that performs **canonicalization / sanitization** of BIDS dataset filenames and metadata. Anticipated scope (to be designed in a follow-up clarification round):
   - Reordering entity key-value pairs to `BIDSSchema.entity_order()` (currently auto-handled per FR-035 inside `BIDSPath.to_filename()`).
   - Sanitizing entity-label values (e.g., replacing forbidden characters in label values such as `-` with `+`, per the approach used in the `nwb2bids` project; ensuring labels are alphanumeric).
   - Lowercasing / canonicalizing entity keys (e.g., `Sub-` → `sub-`).
   - Optional/triaged dropping of non-BIDS suffix segments such as heudiconv's `__dup-NN` (must remain explicit / opt-in due to data-loss risk).
   - Once designed, normalization semantics MAY be invoked from `rename`, `subject-rename`, `session-rename`, and `migrate` via a shared option (e.g., `--normalize` / `--no-normalize`).
   - Until this command is designed, `rename` and related commands MUST simply operate correctly on non-BIDS-named source files (US1.6) without performing additional normalization beyond schema entity-order in the rename pipeline (FR-035). See GitHub issue bids-standard/bids-utils#14 for the broader context.
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
- **SC-002**: `--dry-run=detailed` output for every command matches the actual changes when run without `--dry-run` (verified by comparing dry-run output to actual filesystem diff). `--dry-run=overview` provides a human-friendly summary.
- **SC-008**: All file-renaming operations (session-rename, subject-rename, rename) correctly handle git-annex symlinks — verified by tests using a `tmp_annex_dataset` fixture with locked annexed files.
- **SC-003**: All commands complete on a 1000-subject dataset in O(n) time relative to affected files (not O(n²) in total dataset size). Single-entity operations (rename, remove-run) must not scan the entire dataset. Benchmark target: `rename` on a single file in a 1000-subject dataset completes in under 5 seconds.
- **SC-004**: Library API is independently usable: all acceptance scenarios can be executed via Python imports without the CLI.
- **SC-005**: 100% of mutating commands have both `--dry-run` and `--json` modes tested in CI.
- **SC-006**: Test suite passes against at least 3 different BIDS schema versions (e.g., 1.8, 1.9, 2.0-dev).
- **SC-007**: `migrate` eliminates all deprecation warnings when run on bids-examples datasets created under older schema versions (verified by running the BIDS validator before and after).
- **SC-009**: For each of `rename`, `edit-filename`, `remove`, `subject-rename`, `session-rename`, the integration test suite (using the worktree fixture pattern from FR-042) MUST exercise at least one heudiconv-style `__dup-NN` source file and at least one adversarial non-BIDS-suffix source file (`+mine`, `--crap`, or stray `_test`), and each test MUST: (i) **pre-validate** the worktree post-injection and assert the validator flags the injected non-BIDS file(s) — guaranteeing the fixture genuinely produced an invalid dataset; (ii) run the operation under test; (iii) **post-validate** and assert the validator passes (or only emits pre-existing unrelated warnings unchanged from before injection), so the synthetic non-BIDS files are renamed/removed cleanly rather than silently skipped. Validator-dependent assertions skip gracefully when `bids-validator-deno` is not installed.
- **SC-010**: Both `rename` and `edit-filename` MUST be tested under **batch / glob input** spanning multiple subjects in a single invocation: at minimum (a) a `bids-utils edit-filename sub-*/func/sub-*_task-rest_bold.nii.gz --set task=nback` over a worktree fixture with ≥2 subjects yields a still-valid dataset; (b) a deliberate batch with one conflicting target is refused with exit code 2 and the filesystem is **byte-for-byte unchanged** before and after the failed call (atomic-batch verification, FR-043).

## Assumptions

- Users have Python 3.10+ installed (aligned with current ecosystem support).
- `bidsschematools` provides stable, versioned access to the BIDS schema. If its API changes, bids-utils will adapt.
- The BIDS validator (`bids-validator-deno`) is available for integration testing but is not a runtime dependency.
- Datasets fit on local disk for direct operations. Annexed files without local content are handled via `--annexed` policy (FR-022): error by default, with auto-fetch and skip modes.
- The initial release focuses on local filesystem operations. Full DataLad integration (provenance via `datalad run`) is a subsequent enhancement.
- `bids-examples` git repository is available as a submodule or fixture for testing.
- The project uses `uv` for package management, `tox` + `tox-uv` for test orchestration, `ruff` for linting, `mypy` for type checking, `mkdocs` for documentation — as stated in the constitution.
- The CLI entry point is `bids-utils`. The `bids` name on PyPI is a placeholder pointing to pybids, and `bids-utils` is available on PyPI. Using `bids-utils` avoids confusion with the pybids ecosystem.
