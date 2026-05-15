# Feature Specification: Format-Preserving Input/Output for BIDS Files

**Feature Branch**: `001-consistent-inout`
**Created**: 2026-04-21
**Status**: Draft
**Input**: User description: "Formatting preserving input/output of json (and potentially other) file formats"

## User Scenarios & Testing *(mandatory)*

<!--
  Stories are prioritized by how visible the pain is to dataset
  maintainers today. P1 addresses JSON sidecars (the most common write
  target); P2 addresses tabular files; P3 covers the long tail of plain
  text files in a BIDS tree.
-->

### User Story 1 — Edit a JSON sidecar without churning unrelated lines (Priority: P1)

A researcher maintains a BIDS dataset under version control. The dataset's sidecar JSONs were authored by various tools over several years: some use 4-space indent, some 2-space, some tab indent; some have sorted keys, some have a hand-curated key order that groups scanner settings together; many end in a trailing newline, a few do not. The researcher runs a bids-utils command that needs to change a single field in one sidecar (e.g., `subject-rename` updating an `IntendedFor` entry, or `migrate` replacing `BasedOn` with `Sources`). They commit the result.

In the version-control diff, they expect to see only the lines that semantically changed. Today, they instead see the entire file rewritten in 2-space indent with alphabetized keys and a trailing newline forced on — a change that makes code review harder, obscures the real edit, and inflates history.

**Why this priority**: JSON sidecars are the most frequent write target in bids-utils (every `migrate`, every rename with reference updates, every `metadata` operation). A noisy diff on every sidecar edit undermines trust in the tool and makes the output of `--dry-run` misleadingly large. Fixing this for JSON alone already removes the majority of observed churn.

**Independent Test**: Take a BIDS dataset whose sidecars use a mix of indent widths and key orders (bids-examples provides several). Run a bids-utils command that should change one field in one sidecar. Compare the modified file against the original byte-for-byte: every byte outside the changed field's line(s) must be identical.

**Acceptance Scenarios**:

1. **Given** a sidecar JSON formatted with 4-space indent and a custom key order, **When** bids-utils updates one field's value, **Then** the rewritten file uses the same 4-space indent, retains the same key order, and the only changed line(s) in the diff are those for the updated field.
2. **Given** a sidecar JSON without a trailing newline, **When** bids-utils rewrites it, **Then** the rewritten file also has no trailing newline.
3. **Given** a sidecar JSON with a trailing newline, **When** bids-utils rewrites it, **Then** the trailing newline is preserved (not duplicated, not stripped).
4. **Given** a sidecar JSON whose content is semantically unchanged by the operation (e.g., a migration rule matched but no field actually changed), **When** the operation completes, **Then** the file's bytes are unchanged on disk and the VCS reports the file as clean.
5. **Given** a sidecar JSON indented with tab characters, **When** bids-utils rewrites it, **Then** the rewritten file also uses tab indent.
6. **Given** a bids-utils operation that adds a **new field** to an existing sidecar, **When** the sidecar is written, **Then** the field is appended at a deterministic location (end of the enclosing object) and the pre-existing keys retain their original order and indentation.

---

### User Story 2 — Edit a tabular file without rewriting every row (Priority: P2)

A researcher runs `bids-utils subject-rename` or `bids-utils remove-run` on a dataset whose `participants.tsv` and `_scans.tsv` files were exported from spreadsheet software on Windows (CRLF line endings), or written by a custom pipeline that omits a trailing newline, or that uses a non-standard column order preserved for lab convention. The operation updates one or two rows.

In the diff, the researcher expects to see only the updated rows. Today, switching line endings from CRLF to LF, forcing a trailing newline, or normalizing column order silently rewrites every row of the file.

**Why this priority**: TSV files are rewritten less often than JSON sidecars, but when they are touched (subject rename, run removal, participants update) the full-file churn is especially painful because these are the files most likely to have been hand-curated. This story matters less for raw correctness than for trust, which is why it is P2 behind JSON.

**Independent Test**: Take a `participants.tsv` with CRLF line endings and a non-alphabetical column order. Run a command that edits one row. Confirm line endings and column order are unchanged, and the diff is limited to the edited row.

**Acceptance Scenarios**:

1. **Given** a TSV file with CRLF line endings, **When** bids-utils rewrites it after editing one row, **Then** CRLF line endings are preserved for all lines including the edited one.
2. **Given** a TSV file without a trailing newline, **When** bids-utils rewrites it, **Then** no trailing newline is added.
3. **Given** a TSV file whose columns are in a specific (non-default) order, **When** bids-utils edits a cell, **Then** the column order is preserved.
4. **Given** a TSV file whose content is semantically unchanged by the operation, **When** the operation completes, **Then** the file's bytes are unchanged on disk.

---

### User Story 3 — Touch plain-text BIDS files without reformatting them (Priority: P3)

Some bids-utils operations may need to read or write non-structured text files at or near the dataset root: `README`, `CHANGES`, `.bidsignore`, and similar. A researcher edits `CHANGES` manually in their editor of choice (tab indent, no trailing newline); later, a bids-utils command that happens to touch that file re-writes it with a normalized style.

**Why this priority**: These files are rarely written by bids-utils today, but the principle should be consistent across the whole tool — if we are careful with sidecars, users will trust the tool with their hand-curated `README` too. This is P3 because the blast radius is small and the stories above deliver most of the value.

**Independent Test**: Modify a single character inside `README` or `CHANGES` via a bids-utils operation (or simulate one). Confirm the file's line endings, indent, and trailing-newline state are preserved.

**Acceptance Scenarios**:

1. **Given** a plain-text BIDS file with specific line endings and trailing-newline state, **When** bids-utils rewrites it, **Then** both are preserved.
2. **Given** a plain-text BIDS file whose content is semantically unchanged, **When** the operation completes, **Then** the file bytes are unchanged on disk.

---

### Edge Cases

- **Brand-new file created by bids-utils** (e.g., `split` producing a new `dataset_description.json`, `metadata` segregating out a new sidecar): no source file exists to mirror, so a documented default formatting style is used. See FR-006.
- **File with content the tool cannot parse as expected** (e.g., malformed JSON, JSON-with-comments, BOM-prefixed TSV where content is otherwise correct): the tool reads the file where possible; if a write is required, formatting aspects that cannot be recovered fall back to defaults. This must not silently drop content.
- **Mixed indentation in a single file** (e.g., a JSON sidecar hand-edited inconsistently): the tool picks the predominant indent and uses it uniformly; it does not attempt to preserve per-level idiosyncrasies.
- **UTF-8 BOM**: if the source file begins with a byte-order mark, the rewritten file preserves it. BIDS discourages BOM but does not forbid it, and removing one would be a silent, unexpected semantic change to some downstream tooling.
- **Very large sidecars** (thousands of fields): format-preserving rewrites must not degrade performance such that typical dataset-wide operations become noticeably slower than today's naive rewrite.
- **Directory-based files** and binary formats (e.g., NIfTI): out of scope — treated as opaque blobs, never read or written as text by this feature.
- **File that bids-utils reads but never writes**: format preservation is a write-side concern only; reads must tolerate all in-the-wild text styles without erroring.
- **Dry-run mode**: `--dry-run` must also honor the preservation contract — the diff it displays must reflect only the semantic change, not a full-file normalization that current behavior would show.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST detect and preserve the indent style (width and character — 2 spaces, 4 spaces, tabs, etc.) of each JSON sidecar it rewrites.
- **FR-002**: System MUST preserve the key order of each JSON object it rewrites. Keys that existed in the source MUST appear in the same order in the output; keys that the operation removes MUST leave no trailing blank line beyond what normal structural rewriting implies.
- **FR-003**: System MUST preserve the presence or absence of a trailing newline in every text file it rewrites.
- **FR-004**: System MUST preserve the line-ending style (LF, CRLF, or CR) of every text file it rewrites. Mixed line endings within a single file are normalized to the predominant style, not silently unified to LF.
- **FR-005**: When an operation adds a **new key** to an existing JSON object, the system MUST insert it at the end of that object so that the relative order of pre-existing keys is untouched.
- **FR-006**: When the system creates a **new file from scratch** (no source file to mirror), it MUST use a documented default style: 2-space indent for JSON, LF line endings, trailing newline, no BOM. This default MUST be defined in one place and not duplicated per command.
- **FR-007**: System MUST NOT write a file whose serialized content is byte-identical to what is already on disk. No-op writes are the primary source of VCS churn and MUST be suppressed. This applies equally in normal and dry-run modes.
- **FR-008**: System MUST preserve a UTF-8 byte-order mark if the source file had one. It MUST NOT add a BOM to a file that did not have one.
- **FR-009**: System MUST preserve the column order of TSV files it edits. It MUST NOT alphabetize or otherwise re-order columns even if a BIDS-canonical order exists.
- **FR-010**: System MUST preserve TSV quoting and escaping decisions for rows and cells that the operation did not change. For cells the operation rewrites, standard TSV quoting rules apply.
- **FR-011**: Format preservation MUST apply uniformly to every bids-utils code path that writes a sidecar or tabular file, including all subcommands and the library API. There MUST NOT be a second write path that bypasses preservation for "simple" cases.
- **FR-012**: Format preservation MUST NOT alter the semantic content of any file. If a preservation heuristic conflicts with correctness (e.g., a TSV quoting style would produce an ambiguous cell), correctness wins and the formatting aspect is dropped with a warning.
- **FR-013**: Detection of the source formatting (indent, line endings, trailing newline, BOM) MUST be a read-side operation whose result is carried alongside the parsed content, so that the later write can reproduce it without re-reading the file from disk.
- **FR-014**: The system MUST expose, for future extensibility, a minimal internal contract for adding format-preserving support for additional file types (e.g., YAML, if BIDS-adjacent tooling begins to emit it). This contract is internal; no public API guarantee is implied.

### Key Entities *(include if feature involves data)*

- **Formatting profile**: The bundle of style choices (indent width, indent character, key order, line-ending style, trailing-newline presence, BOM presence) captured when a file is read and used to reproduce that file on write. One profile per file; not shared across files.
- **File formats in scope**: JSON sidecars; BIDS TSV tables (`participants.tsv`, `_scans.tsv`, `_sessions.tsv`, `_events.tsv`, `_channels.tsv`, `_electrodes.tsv`, etc.); plain-text dataset files (`README`, `CHANGES`, `.bidsignore`). NIfTI and other binary formats are out of scope.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A bids-utils operation that performs no semantic change to a file MUST leave that file's bytes unchanged on disk in 100% of cases across the full bids-examples corpus.
- **SC-002**: For operations that change exactly one field in a JSON sidecar, the resulting unified-diff (default 3 lines of context) MUST contain at most 5 changed lines in at least 95% of the sidecars present in bids-examples. Measured across all sidecar-touching migration rules.
- **SC-003**: For operations that change exactly one row in a TSV file, the resulting unified-diff MUST contain at most 3 changed lines in 100% of cases, regardless of whether the source file used LF or CRLF line endings.
- **SC-004**: Across bids-examples, running any bids-utils command end-to-end and comparing the resulting file set against the minimum diff set required by the semantic change, the total number of lines altered MUST be within 10% of that minimum.
- **SC-005**: Dataset maintainers reviewing a bids-utils-produced commit on a version-controlled dataset report that the diff reflects only the intended change (qualitative; measured via user feedback after rollout).
- **SC-006**: Dataset-wide operations (e.g., `subject-rename` across hundreds of sidecars) MUST not take more than 20% longer than the pre-feature baseline. Format preservation MUST NOT make the tool meaningfully slower.

## Assumptions

- Sidecar JSON files in BIDS datasets are plain UTF-8 text using strict JSON (no comments, no trailing commas). Format preservation is defined for strict JSON; non-strict dialects are not supported and will fall through to read-error behavior already present in bids-utils.
- "Key order" refers to the insertion order of JSON object members as observed when parsing. Nested objects are preserved recursively.
- For TSV files, column order is authoritative per file. bids-utils does not attempt to reconcile column order across files of the same kind (e.g., `_scans.tsv` in different subject directories may legitimately differ in column order, and this feature does not change that).
- The default formatting for newly created files (FR-006) matches what bids-utils emits today, so existing test fixtures and downstream tooling remain compatible.
- No-op write detection (FR-007) is performed by comparing the final serialized byte sequence to the on-disk bytes — not by hashing the parsed content — so that formatting-only differences are also treated as write-worthy when intentional (e.g., a future `--normalize` command).
- Producing a byte-identical output when nothing semantic changed is considered more important than producing a canonically formatted output. There is no current need for a canonicalizing mode; if one is added later, it is an explicit opt-in.
- Integration testing uses the bids-examples submodule as the corpus for measuring success criteria, since it contains datasets authored by many different tools and exercises a broad range of real-world formatting styles.
