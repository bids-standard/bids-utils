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

---

### User Story 2 — Migrate a dataset toward BIDS 2.0 (Priority: P1, need: high)

A lab maintaining a BIDS 1.x dataset needs to address deprecations and prepare for BIDS 2.0. They run `bids-utils migrate` which reads the machine-readable schema (via `bidsschematools`) and applies the necessary transformations (entity renames, metadata key changes, structural reorganization) in a safe, reversible manner.

**Why this priority**: BIDS 2.0 is approaching and many datasets need a migration path. A prototype already exists (bids-specification PR #2282) validating the concept.

**Independent Test**: Take a BIDS 1.x dataset from bids-examples, run `bids-utils migrate --target 2.0`, verify the output passes the BIDS 2.0 validator schema.

**Acceptance Scenarios**:

1. **Given** a valid BIDS 1.8 dataset, **When** `bids-utils migrate --target 2.0 --dry-run` is run, **Then** the tool lists all changes needed (deprecations, renames) without modifying any files.
2. **Given** a valid BIDS 1.8 dataset, **When** `bids-utils migrate --target 2.0` is run, **Then** the dataset is transformed and passes validation against the BIDS 2.0 schema.
3. **Given** a dataset already at the target version, **When** `bids-utils migrate` is run, **Then** the tool reports "nothing to do" and exits with code 0.
4. **Given** a dataset with ambiguities that require human judgment, **When** migration encounters them, **Then** the tool aborts with a clear explanation rather than guessing.

---

### User Story 3 — Rename a subject (Priority: P2, need: medium)

A data manager needs to anonymize or re-number a subject. They run `bids-utils subject-rename sub-01 sub-99`. The tool renames the `sub-` directory, every file within it (since all carry the `sub-` prefix), updates `participants.tsv`, updates all `_scans.tsv` files, and optionally processes `sourcedata/` and `.heudiconv/`.

**Why this priority**: Common real-world need. Composes on top of the P1 `rename` primitive. Medium priority per design doc.

**Independent Test**: Rename a subject in a bids-examples dataset, run validator, confirm validity and that no stale references remain.

**Acceptance Scenarios**:

1. **Given** a valid dataset with `sub-01`, **When** `bids-utils subject-rename sub-01 sub-99` is run, **Then** the directory is renamed, all files are renamed, `participants.tsv` is updated, and the dataset remains valid.
2. **Given** a dataset with `sourcedata/sub-01/`, **When** `--include-sourcedata` is passed, **Then** `sourcedata/sub-01/` is also renamed.
3. **Given** the target subject `sub-99` already exists, **When** the command is run, **Then** it refuses with exit code 2.
4. **Given** a dataset under git-annex, **When** subject is renamed, **Then** `git mv` / `git annex` commands are used and the operation is a single git commit.

---

### User Story 4 — Rename a session (Priority: P2, need: medium)

Similar to subject-rename but for session entities. Includes the special case of **moving into a session** — a dataset collected without sessions that now needs session identifiers.

**Why this priority**: Medium need per design doc. Uses the same infrastructure as subject-rename.

**Independent Test**: Rename a session in a multi-session bids-examples dataset, validate.

**Acceptance Scenarios**:

1. **Given** a valid dataset with `sub-01/ses-pre/`, **When** `bids-utils session-rename ses-pre ses-baseline` is run, **Then** the session directory and all its files are renamed, and the dataset remains valid.
2. **Given** a dataset without sessions, **When** `bids-utils session-rename '' ses-01` is run (move-into-session), **Then** a `ses-01` level is introduced for all subjects, files are renamed to include `ses-01`, and the dataset remains valid.
3. **Given** a target session that already exists for a subject, **When** the command is run, **Then** it refuses with exit code 2.

---

### User Story 5 — Bubble-up / condense / organize metadata (Priority: P2, need: medium)

A dataset has metadata duplicated across many sidecar JSON files at the leaf level. The user runs `bids-utils metadata aggregate` to hoist common key-value pairs up the BIDS inheritance hierarchy, reducing redundancy and making the dataset easier to overview.

**Why this priority**: Medium need per design doc. Addresses a real pain point with large datasets. The `aggregate`, `segregate`, and `deduplicate` modes serve different workflows.

**Independent Test**: Run `bids-utils metadata aggregate` on a bids-examples dataset with per-subject JSON files, verify the dataset remains valid and the metadata is equivalent when resolved through the inheritance principle.

**Acceptance Scenarios**:

1. **Given** a dataset where all subjects share `RepetitionTime=2.0` in their `_bold.json`, **When** `bids-utils metadata aggregate` is run, **Then** `RepetitionTime` is moved to a higher-level `_bold.json` and removed from individual files, and the resolved metadata for every file is unchanged.
2. **Given** a subject that is missing a `_bold.json` entirely (but has `_bold.nii.gz`), **When** aggregation is attempted for `RepetitionTime`, **Then** the tool does NOT aggregate that key (since the value is unknown for that subject, not merely identical).
3. **Given** a user running `bids-utils metadata segregate`, **When** the command completes, **Then** all metadata is pushed down to leaf-level files (full self-contained sidecars per file).
4. **Given** `bids-utils metadata audit`, **When** run, **Then** the tool reports metadata keys that are neither fully unique nor fully equivalent across files — indicating potential acquisition inconsistencies.

---

### User Story 6 — Remove a subject or session (Priority: P3, need: low)

A dataset maintainer needs to remove a subject (or session) entirely. The tool removes the directory tree, updates `participants.tsv`, and cleans up `_scans.tsv`.

**Why this priority**: Low need per design doc. Straightforward once the core infrastructure exists.

**Independent Test**: Remove a subject from a bids-examples dataset, validate.

**Acceptance Scenarios**:

1. **Given** a valid dataset with `sub-03`, **When** `bids-utils remove sub-03` is run with `--force`, **Then** the subject directory and all files are deleted, `participants.tsv` is updated, and the dataset remains valid.
2. **Given** a remove command without `--force`, **When** run, **Then** the tool prompts for confirmation before proceeding.

---

### User Story 7 — Remove a run (Priority: P3, need: low)

A specific run needs to be removed and subsequent run indices shifted to maintain contiguity (e.g., removing `run-02` means `run-03` becomes `run-02`).

**Why this priority**: Low need per design doc. Niche but important for data curation.

**Independent Test**: Remove a run from a multi-run dataset, verify remaining runs are re-indexed and dataset is valid.

**Acceptance Scenarios**:

1. **Given** a subject with `run-01`, `run-02`, `run-03`, **When** `bids-utils remove-run sub-01 run-02 --shift` is run, **Then** `run-02` files are removed, `run-03` is renamed to `run-02`, and `_scans.tsv` is updated.
2. **Given** `--no-shift` flag, **When** a run is removed, **Then** subsequent runs keep their indices (leaving a gap).

---

### User Story 8 — Merge datasets (Priority: P3, need: low)

Two BIDS datasets need to be combined — either by simply combining subjects (failing on conflicts) or by placing each dataset into a separate session.

**Why this priority**: Low need per design doc. Implementation builds on session-rename.

**Independent Test**: Merge two bids-examples datasets, validate the result.

**Acceptance Scenarios**:

1. **Given** two valid datasets with non-overlapping subjects, **When** `bids-utils merge datasetA datasetB --output merged/` is run, **Then** all subjects from both datasets appear in the output and the merged dataset is valid.
2. **Given** two datasets with overlapping subject IDs, **When** merge is run without `--into-sessions`, **Then** the tool refuses with exit code 2 listing the conflicts.
3. **Given** `--into-sessions ses-A ses-B`, **When** merge is run, **Then** each dataset's data is placed under the respective session.

---

### User Story 9 — Split datasets (Priority: P3, need: low)

A dataset needs to be split — for example, extracting only behavioral data or only stimuli for more efficient sharing.

**Why this priority**: Low need per design doc. Opposite of merge.

**Acceptance Scenarios**:

1. **Given** a valid dataset, **When** `bids-utils split --suffix bold --output bold-only/` is run, **Then** only BOLD-related files (and required metadata) are extracted and the result is a valid BIDS dataset.

---

### Edge Cases

- What happens when a rename creates a filename that exceeds OS path length limits?
- How does the tool handle symlinked files (common with git-annex)?
- What happens when `_scans.tsv` references files that don't exist on disk (dangling references)?
- How does the tool handle partial datasets (e.g., missing `dataset_description.json`)?
- What happens when a file is locked by git-annex and content is needed for metadata operations?
- How does aggregation handle `.nwb` files that embed metadata internally?
- What happens when operating on a dataset on a read-only filesystem?
- How does the tool handle datasets with both `participants.tsv` and `participants.json`?

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
- **SC-003**: All commands complete on a 1000-subject dataset within reasonable time (no pathological performance cliffs — O(n) in number of affected files, not O(n²) in total dataset size).
- **SC-004**: Library API is independently usable: all acceptance scenarios can be executed via Python imports without the CLI.
- **SC-005**: 100% of mutating commands have both `--dry-run` and `--json` modes tested in CI.
- **SC-006**: Test suite passes against at least 3 different BIDS schema versions (e.g., 1.8, 1.9, 2.0-dev).

## Assumptions

- Users have Python 3.10+ installed (aligned with current ecosystem support).
- `bidsschematools` provides stable, versioned access to the BIDS schema. If its API changes, bids-utils will adapt.
- The BIDS validator (`bids-validator-deno`) is available for integration testing but is not a runtime dependency.
- Datasets fit on local disk for direct operations. Remote/annexed access is a separate concern handled via fsspec/git-annex passthrough.
- The initial release focuses on local filesystem operations. Full DataLad integration (provenance via `datalad run`) is a subsequent enhancement.
- `bids-examples` git repository is available as a submodule or fixture for testing.
- The project uses `uv` for package management, `tox` + `tox-uv` for test orchestration, `ruff` for linting, `mypy` for type checking, `mkdocs` for documentation — as stated in the constitution.
- The CLI entry point is `bids-utils`. The `bids` name on PyPI is a placeholder pointing to pybids, and `bids-utils` is available on PyPI. Using `bids-utils` avoids confusion with the pybids ecosystem.
