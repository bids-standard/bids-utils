---
description: "Tasks for feature 001-consistent-inout — format-preserving I/O via json-five-backed adapter"
---

# Tasks: Format-Preserving Input/Output for BIDS Files

**Input**: Design documents at `.specify/specs/001-consistent-inout/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅ (json-five-via-adapter), data-model.md ✅, contracts/io_contract.md ✅, quickstart.md ✅

**Tests**: INCLUDED. Constitution Principle V (Test-First) and the
contract document (Test surface mapping) require tests for this feature.
Tests are written and asserted to FAIL before each story's implementation
tasks begin. The R1.1 adapter defenses each get their own test in
`tests/test_format_json_backend.py`.

**Backend**: this task list implements the **json-five-via-adapter**
plan. `json-five` is added as a runtime dependency; all imports of it
are confined to `src/bids_utils/_format/_json_backend.py`. Future
backend swaps require changes to that one file plus its tests, never
to call sites.

**Organization**: Tasks are grouped by user story per spec.md. Each
story's Independent Test criterion is reproduced from the spec at the
top of its phase.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Different files, no incomplete-task dependencies → can run in parallel.
- **[Story]**: US1 (JSON sidecars, P1), US2 (TSVs, P2), US3 (plain-text, P3).
- All paths are repo-relative.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create the `src/bids_utils/_format/` package skeleton: empty `__init__.py`, `_profile.py`, `_write.py`, `_json.py`, `_json_backend.py`, `_tsv.py`, `_text.py`. Each file gets a one-line module docstring referencing `.specify/specs/001-consistent-inout/contracts/io_contract.md`. Empty for now — populated per phase below.
- [X] T002 Add `json-five>=1.1.2,<2` to `[project] dependencies` in `pyproject.toml` (alongside `bidsschematools`, `click`, `packaging`). The PyPI distribution name is `json-five`; the import name is `json5`. Document in the `[project]` section comment that this dep is isolated to `bids_utils._format._json_backend`.
- [X] T003 [P] Add a `bids_examples_copy` pytest fixture to `tests/conftest.py` that yields a temp-copy `Path` of one configurable bids-examples dataset, so integration tests can mutate without dirtying the submodule. Honors `BIDS_EXAMPLES_DATASET` env var (default `ds001`).
- [X] T004 [P] Register the `pytest.mark.integration` marker in `pyproject.toml` `[tool.pytest.ini_options].markers` if not already present, so the integration sweep can be selected via `-m integration`. Also confirm `pytest.mark.ai_generated` is registered (per `~/.claude/CLAUDE.md`). (Markers were already registered; verified.)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Dataclasses, defaults, the byte-level write helper, and the
package re-exports. These are imported by every story.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 [P] Define `FormattingProfile` (frozen dataclass: `indent: str`, `separators: tuple[str, str]`, `line_ending: str`, `trailing_newline: bool`, `bom: bool`) in `src/bids_utils/_format/_profile.py` per contract Part A
- [X] T006 [P] Define `TSVFormattingProfile` (frozen dataclass: `fieldnames: tuple[str, ...]`, `line_ending`, `trailing_newline`, `bom`, `original_lines: tuple[bytes, ...]`, `quoting: int`) in `src/bids_utils/_format/_profile.py` per contract Part A
- [X] T007 [P] Define `TextFormattingProfile` (frozen dataclass: `line_ending`, `trailing_newline`, `bom`) in `src/bids_utils/_format/_profile.py` per contract Part A
- [X] T008 Define module constants `DEFAULT_JSON_PROFILE`, `DEFAULT_TSV_PROFILE`, `DEFAULT_TEXT_PROFILE` in `src/bids_utils/_format/_profile.py` per research R9 / FR-006 (2-space indent for JSON, LF, trailing newline, no BOM, `(",", ": ")` separators). Depends on T005–T007.
- [X] T009 Implement `write_if_changed(path: Path, new_bytes: bytes) -> bool` in `src/bids_utils/_format/_write.py` per contract A and research R6 (single byte read + compare; create parent dirs only on first write; idempotent on identical bytes). Depends on T005.
- [X] T010 Populate `src/bids_utils/_format/__init__.py` to re-export the public-internal surface: `FormattingProfile`, `TSVFormattingProfile`, `TextFormattingProfile`, the three `DEFAULT_*_PROFILE` constants, `write_if_changed` (more added per phase). Depends on T005–T009.
- [X] T011 [P] Create `tests/test_format.py` with `test_signatures_present` asserting all dataclass fields, default constants, and module-level re-exports exist as documented in contract Part A. Currently fails (modules empty); becomes the contract pin.
- [X] T012 [P] In `tests/test_format.py` add `test_default_profile_for_new_file` asserting `DEFAULT_JSON_PROFILE.indent == "  "`, `line_ending == "\n"`, `trailing_newline is True`, `bom is False`, `separators == (",", ": ")` (FR-006 / B.4).
- [X] T013 [P] In `tests/test_format.py` add `test_write_if_changed_skips_identical_bytes` (write→write same bytes → second call returns False, mtime unchanged) and `test_write_if_changed_writes_when_different` (FR-007 / SC-001 unit-level).

**Checkpoint**: Foundation ready — package laid out, dataclasses + defaults + `write_if_changed` work; user-story phases can begin.

---

## Phase 3: User Story 1 — JSON sidecar edits without unrelated churn (Priority: P1) 🎯 MVP

**Goal**: Every JSON sidecar bids-utils writes preserves indent, key
order, separators, line endings, BOM, trailing newline; new keys
appended at end; no-op writes suppressed. Backed by `json-five` via
the `JSONBackend` adapter.

**Independent Test (spec §US1)**: take a bids-examples dataset whose
sidecars use mixed indent widths and key orders, run a bids-utils
command that should change one field, compare modified file against
original byte-for-byte — every byte outside the changed field's
line(s) is identical.

### 3.A Backend tests (FAIL first, write before T028+)

These tests pin the R1.1 defenses — without them, the json-five
upstream footguns silently corrupt output. Each test corresponds to a
defense in research.md R1.1.

- [ ] T014 [P] [US1] In `tests/test_format_json_backend.py` add `test_default_backend_conforms_to_protocol` — instantiate `Json5Backend()`, verify `isinstance` against `JSONBackend` Protocol with `runtime_checkable`, and call every method with a tiny fixture; covers contract Part A (Protocol)
- [ ] T015 [P] [US1] In `tests/test_format_json_backend.py` add `test_serialize_is_stateless_across_calls` — parse two distinct sources, serialize each with the same backend instance, assert the second output does NOT contain bytes from the first. Reproduces `json_five_modeldumper_state_bug.py`. R1.1.1 defense.
- [ ] T016 [P] [US1] In `tests/test_format_json_backend.py` add `test_set_value_routes_through_canonical_lists` — after `backend.set_value(model, "k", "new")`, the model's `obj.values[i].raw_value` reflects the new value; `obj.key_value_pairs[i]` (the read-only property) is NOT relied on. R1.1.2 defense.
- [ ] T017 [P] [US1] In `tests/test_format_json_backend.py` add `test_serialize_asserts_keys_values_length` — manually break the model (`del obj.keys[0]` without touching `values`), call `backend.serialize(model, profile)`, assert it raises a clear error rather than emitting corrupt bytes. Reference: `json_five_keys_manipulation_bug.py` case 04. R1.1.3 defense.
- [ ] T018 [P] [US1] In `tests/test_format_json_backend.py` add `test_append_key_mirrors_whitespace` — start from a 2-space-indented sidecar, call `backend.append_key(model, "NewField", 42)`, serialize, assert the new key's leading whitespace matches the prior keys' indent and the closing `}` retains its newline. Reference: `round_trip_repro.sh` Phase 3. R1.1.5 defense.
- [ ] T019 [P] [US1] In `tests/test_format_json_backend.py` add `test_parse_falls_back_to_stdlib_on_json5_failure` — pass bytes that `json-five` rejects but stdlib `json` accepts (or zero bytes triggering empty-file path), assert `backend.parse(bytes)` returns a `FallbackModel` and that subsequent `serialize` uses stdlib. R1.1.6 defense.
- [ ] T020 [P] [US1] In `tests/test_format_json_backend.py` add `test_detect_profile_bom_present` and `test_detect_profile_trailing_newline_states` — backend detects the two load-bearing profile fields. (Indent/separators come from the model, not the profile, in this path.)
- [ ] T021 [P] [US1] In `tests/test_format_json_backend.py` add `test_round_trip_byte_identity` — for a parametrized set of fixture sidecar bytes (covering 2-space, 4-space, tab indent; LF/CRLF; BOM/no-BOM; trailing/no-trailing newline), assert `backend.serialize(backend.parse(b), backend.detect_profile(b)) == b`. Pulls a handful of fixtures from `tests/fixtures/sidecars/` (create dir).

### 3.B `JSONDocument` & polymorphic `serialize_json` tests (FAIL first)

- [ ] T022 [P] [US1] In `tests/test_format.py` add `test_jsondocument_dict_protocol` — `__getitem__`/`__setitem__`/`__delitem__`/`__iter__`/`__len__`/`__contains__` round-trip behaviors on a fresh document
- [ ] T023 [P] [US1] In `tests/test_format.py` add `test_jsondocument_new_key_appended_at_end` — `doc["NewKey"] = v` places the new key as the last KV in the serialized output; pre-existing key order untouched (FR-005 / B.3)
- [ ] T024 [P] [US1] In `tests/test_format.py` add `test_jsondocument_nested_object_returns_plain_dict` — `doc["Nested"]` returns a `dict` (not a `JSONDocument`); local mutation of that dict is NOT visible until reassigned via `doc["Nested"] = nested` (R13 semantics)
- [ ] T025 [P] [US1] In `tests/test_format.py` add `test_jsondocument_to_dict` — `doc.to_dict()` materializes a fully-Python plain dict matching `json.loads(source)` semantically
- [ ] T026 [P] [US1] In `tests/test_format.py` add `test_serialize_json_with_jsondocument_round_trip` — `serialize_json(doc, doc.profile)` returns bytes equal to source for the byte-identical round-trip case
- [ ] T027 [P] [US1] In `tests/test_format.py` add `test_serialize_json_with_plain_dict_uses_stdlib_path` — `serialize_json({"k": "v"}, DEFAULT_JSON_PROFILE)` returns bytes equal to `b'{\n  "k": "v"\n}\n'` (FR-006 stdlib new-file path)

### 3.C `_io.py` integration tests (FAIL first)

- [ ] T028 [P] [US1] In `tests/test_io.py` add `test_read_json_with_profile_returns_document` — return type is `(JSONDocument | None, FormattingProfile | None)`; both None for a missing file in `AnnexedMode.SKIP`
- [ ] T029 [P] [US1] In `tests/test_io.py` add `test_write_json_uses_jsondocument_profile` — read → mutate one field → write; assert resulting bytes equal what `serialize_json(doc, doc.profile)` would produce
- [ ] T030 [P] [US1] In `tests/test_io.py` add `test_write_json_no_op_returns_false` — read → write back unchanged; assert return value `False`, file mtime unchanged (FR-007)
- [ ] T031 [P] [US1] In `tests/test_io.py` add `test_legacy_read_json_still_returns_dict` — the un-profiled `read_json(path, vcs, mode)` returns a plain `dict`, not a `JSONDocument` (Principle X back-compat)
- [ ] T032 [P] [US1] In `tests/test_io.py` add `test_legacy_write_json_dict_uses_default_profile` — calling `write_json(path, {"k": "v"}, vcs)` with no profile produces bytes matching `serialize_json({"k": "v"}, DEFAULT_JSON_PROFILE)`

### 3.D Implementation

- [ ] T033 [US1] Define `JSONBackend` Protocol (with `@runtime_checkable`) in `src/bids_utils/_format/_json_backend.py` per contract Part A. Eight methods: `parse`, `serialize`, `detect_profile`, `get_keys`, `get_value`, `set_value`, `append_key`, `delete_key`. Makes T014 importable.
- [ ] T034 [US1] Implement `Json5Backend.parse(source) -> JSONText | FallbackModel` and `Json5Backend.detect_profile(source) -> FormattingProfile` in `src/bids_utils/_format/_json_backend.py`. Strip BOM before passing to `json5.loader.loads`; on `json5` parse error, retry via `json.loads` and wrap in a `FallbackModel(plain_dict)`. Detect `bom` (BOM bytes prefix) and `trailing_newline` (terminator suffix); fill `indent`/`separators`/`line_ending` from the model where possible, else from a quick byte scan. Always use a fresh `ModelLoader()`. Makes T019, T020, T021 (parse half) pass. Depends on T033.
- [ ] T035 [US1] Implement `Json5Backend.serialize(model, profile) -> bytes` in `src/bids_utils/_format/_json_backend.py`. **Always** instantiate a fresh `ModelDumper()` (R1.1.1). Walk the root `JSONObject` and assert `len(obj.keys) == len(obj.values)` (R1.1.3). Call `json5.dumper.dumps(model, dumper=fresh_dumper)`. Post-process: replace line endings to match `profile.line_ending` (no-op for the dominant case); add/strip trailing terminator per `profile.trailing_newline`; prepend `b"\xef\xbb\xbf"` iff `profile.bom`. For a `FallbackModel`, route through `json.dumps(plain_dict, indent=profile.indent, separators=profile.separators, ensure_ascii=False)` then the same post-processing. Makes T015, T017, T021 (serialize half), T019 (fallback half) pass. Depends on T034.
- [ ] T036 [US1] Implement `Json5Backend.get_keys` / `get_value` / `set_value` / `append_key` / `delete_key` in `src/bids_utils/_format/_json_backend.py`. Mutations route through `obj.keys` / `obj.values` only (R1.1.2); `append_key` mirrors `wsc_before` of the prior last KV pair and transfers the prior `wsc_after` (R1.1.5); `delete_key` deletes from BOTH lists symmetrically. Re-use the helper logic from `round_trip_repro.sh` Phase 3. Makes T016, T018 pass. Depends on T033.
- [ ] T037 [US1] Implement `JSONDocument(MutableMapping[str, Any])` in `src/bids_utils/_format/_json.py`. Hold `_model`, `_backend`, `profile`. Implement the six abstract methods routing through the backend. Implement `to_dict()` via `json.loads(serialize_json(self, self.profile))` (or a direct walk). Makes T022–T025 pass. Depends on T036.
- [ ] T038 [US1] Implement `parse_json(source) -> tuple[JSONDocument, FormattingProfile]` and `serialize_json(data: JSONDocument | dict, profile) -> bytes` (polymorphic) in `src/bids_utils/_format/_json.py`. Use a module-level `_default_backend = Json5Backend()`. For dict input, route to stdlib `json.dumps(data, indent=profile.indent, separators=profile.separators, ensure_ascii=False)` + post-processing matching `Json5Backend.serialize`'s post-processing (factor that into a shared helper). Makes T026, T027 pass. Depends on T037.
- [ ] T039 [US1] Add `read_json_with_profile(path, vcs, mode) -> tuple[JSONDocument | None, FormattingProfile | None]` to `src/bids_utils/_io.py`. Reads bytes once, calls `parse_json`, returns `(doc, profile)`. Returns `(None, None)` on existing AnnexedMode skip paths. Makes T028 pass. Depends on T038.
- [ ] T040 [US1] Extend `write_json` in `src/bids_utils/_io.py` signature to `(path, data: JSONDocument | dict, vcs, profile=None) -> bool`. If `data` is a `JSONDocument` and `profile is None`, use `data.profile`. If `data` is a dict and `profile is None`, use `DEFAULT_JSON_PROFILE`. Route through `serialize_json` + `write_if_changed`. Honor existing VCS unlock/lock lifecycle. Makes T029, T030, T032 pass. Depends on T038.
- [ ] T041 [US1] Update legacy `read_json` in `src/bids_utils/_io.py` to internally call `read_json_with_profile` and return `doc.to_dict()` (or `None`). Preserves Principle X back-compat. Makes T031 pass. Depends on T039.
- [ ] T042 [US1] Re-export `JSONDocument`, `JSONBackend`, `parse_json`, `serialize_json` from `src/bids_utils/_format/__init__.py`. Depends on T038.

### 3.E Migration of existing call sites

- [ ] T043 [P] [US1] Migrate every direct `json.dumps(data, indent=2)` write in `src/bids_utils/migrate.py` to the `read_json_with_profile` + `write_json(doc, profile=)` recipe. Preserve all existing dry-run plumbing. Use grep `json\.dumps\|\.write_text` to find sites.
- [ ] T044 [P] [US1] Migrate every direct `json.dumps`/`Path.write_text` JSON write in `src/bids_utils/metadata.py` to the profile-aware path
- [ ] T045 [P] [US1] Update `src/bids_utils/_dataset.py` `dataset_description.json` reader to use `read_json_with_profile`; pass the profile to any downstream writes
- [ ] T046 [P] [US1] Audit `src/bids_utils/{merge,split,rename,run,session,subject}.py` for direct JSON writes that bypass `_io.write_json`. Convert each found case (most are expected to delegate already).
- [ ] T047 [P] [US1] Audit `src/bids_utils/cli/migrate.py` and `src/bids_utils/cli/metadata.py` for JSON writes that target on-disk files (vs stdout). Convert disk writes; document any stdout writes as out-of-scope per FR-011.

### 3.F Integration tests (after implementation)

- [ ] T048 [US1] Add `tests/integration/test_format_preservation.py::test_no_op_byte_identity` (marked `@pytest.mark.integration` and `@pytest.mark.ai_generated`). Sweep `bids-examples` datasets via the `bids_examples_copy` fixture, run a no-op `bids-utils migrate` operation per dataset, assert every JSON sidecar's bytes unchanged. Covers SC-001 / B.1 (JSON).
- [ ] T049 [US1] Add `tests/integration/test_format_preservation.py::test_one_field_edit_diff_size` — for a sample of bids-examples sidecars, mutate one existing field via `JSONDocument`, write, compute `difflib.unified_diff` line count vs source, assert ≤5 changed lines in ≥95% of sidecars. Covers SC-002 / B.2 (JSON).

**Checkpoint**: User Story 1 fully functional. JSON sidecar edits ship a localized diff. **MVP-shippable here** if US2/US3 are deferred.

---

## Phase 4: User Story 2 — TSV row edits without rewriting every row (Priority: P2)

**Goal**: TSV writes preserve column order, line endings, BOM, trailing
newline, and per-row quoting (untouched rows are spliced verbatim).

**Independent Test (spec §US2)**: take a `participants.tsv` with CRLF
line endings and non-alphabetical column order, run a command that
edits one row, confirm line endings + column order unchanged and the
diff is limited to the edited row.

### 4.A Tests (FAIL first)

- [ ] T050 [P] [US2] In `tests/test_format.py` add `test_detect_tsv_profile_lf`, `test_detect_tsv_profile_crlf`, `test_detect_tsv_profile_bom`, `test_detect_tsv_profile_no_trailing_newline`, `test_detect_tsv_profile_preserves_column_order` (FR-004, FR-008, FR-009, R5)
- [ ] T051 [P] [US2] In `tests/test_format.py` add `test_serialize_tsv_round_trip_no_changes_returns_source_bytes` (with `changed_indices=set()`)
- [ ] T052 [P] [US2] In `tests/test_format.py` add `test_serialize_tsv_one_row_change_splices_rest` — only the changed row is re-serialized; untouched rows kept verbatim from `profile.original_lines` (R5)
- [ ] T053 [P] [US2] In `tests/test_format.py` add `test_correctness_wins_over_preservation_tsv` — TSV cell containing a tab triggers proper quoting + `UserWarning` (B.6 / FR-012)
- [ ] T054 [P] [US2] In `tests/test_tsv.py` add `test_read_tsv_with_profile_returns_pair` and `test_write_tsv_no_op_returns_false`
- [ ] T055 [P] [US2] In `tests/test_tsv.py` add `test_write_tsv_with_changed_indices_only_touches_those_rows` — assert untouched row bytes appear verbatim in output

### 4.B Implementation

- [ ] T056 [US2] Implement `detect_tsv_profile(source: bytes) -> TSVFormattingProfile` in `src/bids_utils/_format/_tsv.py` (capture header verbatim; build `original_lines` tuple of post-header byte slices; line ending + BOM + trailing-newline as in JSON path; quoting via `csv.Sniffer` defaults). Makes T050 pass.
- [ ] T057 [US2] Implement `serialize_tsv(rows, profile, changed_indices=None) -> bytes` in `src/bids_utils/_format/_tsv.py`. Header re-emitted via `csv.writer` with profile lineterminator + quoting. For each row: if index in `changed_indices` → re-serialize via `csv.writer`, else splice from `profile.original_lines`. Emit BOM + trailing terminator per profile. If a splice would produce ambiguous bytes (B.6), fall back to re-serialize that row and `warnings.warn(UserWarning)`. Makes T051–T053 pass. Depends on T056.
- [ ] T058 [US2] Re-export TSV symbols from `src/bids_utils/_format/__init__.py`
- [ ] T059 [US2] Implement `read_tsv_with_profile(path, vcs, annexed_mode) -> tuple[list[dict[str, str]], TSVFormattingProfile]` in `src/bids_utils/_tsv.py` (single `read_bytes`; call `detect_tsv_profile`; parse rows positionally with `csv.reader`). Makes T054 (read half) pass.
- [ ] T060 [US2] Extend `write_tsv` in `src/bids_utils/_tsv.py` with `profile=None`, `changed_indices=None` kwargs; route through `serialize_tsv` + `write_if_changed`; return `bool`. Update legacy callers to drop the new return value. Makes T054 (write half), T055 pass.
- [ ] T061 [P] [US2] Audit `src/bids_utils/_participants.py` and `src/bids_utils/_scans.py` for any TSV-write or `csv.DictWriter` that bypasses `_tsv.write_tsv`; route through profile-aware path

### 4.C Integration

- [ ] T062 [US2] Add `tests/integration/test_format_preservation.py::test_one_row_edit_diff_size` — for bids-examples TSVs, mutate one cell, write via `write_tsv(profile=, changed_indices={i})`, assert diff has ≤3 changed lines in 100% of cases regardless of LF/CRLF source. Covers SC-003 / B.2 (TSV).
- [ ] T063 [US2] Extend `tests/integration/test_format_preservation.py::test_no_op_byte_identity` to also assert TSV bytes unchanged on no-op operations (B.1 for TSV)

**Checkpoint**: TSV row edits diff localized. US1 + US2 both functional.

---

## Phase 5: User Story 3 — Plain-text BIDS files (Priority: P3)

**Goal**: `README`, `CHANGES`, `.bidsignore` writes preserve line
endings, trailing-newline state, and BOM.

**Independent Test (spec §US3)**: modify a single character inside
`README` or `CHANGES` via a bids-utils operation, confirm line endings,
indent, and trailing-newline state are preserved.

### 5.A Tests (FAIL first)

- [ ] T064 [P] [US3] In `tests/test_format.py` add `test_detect_text_profile_lf`, `test_detect_text_profile_crlf`, `test_detect_text_profile_cr`, `test_detect_text_profile_bom`, `test_detect_text_profile_trailing_newline_states`
- [ ] T065 [P] [US3] In `tests/test_format.py` add `test_serialize_text_round_trip` parametrized over the cases above

### 5.B Implementation

- [ ] T066 [US3] Implement `detect_text_profile(source: bytes) -> TextFormattingProfile` in `src/bids_utils/_format/_text.py` (subset of JSON detector — only line ending, BOM, trailing newline)
- [ ] T067 [US3] Implement `serialize_text(text: str, profile: TextFormattingProfile) -> bytes` in `src/bids_utils/_format/_text.py`
- [ ] T068 [US3] Re-export text symbols from `src/bids_utils/_format/__init__.py`
- [ ] T069 [US3] Add `read_text_with_profile(path, vcs, mode) -> tuple[str | None, TextFormattingProfile | None]` and `write_text(path, text, vcs, profile=None) -> bool` to `src/bids_utils/_io.py` per contract Part A
- [ ] T070 [P] [US3] Grep `src/bids_utils/` for any plain-text file writes targeting `README`/`CHANGES`/`.bidsignore`. Likely zero hits today — task is the audit + a comment in `_io.py` documenting the entry point exists for future use.

### 5.C Integration

- [ ] T071 [US3] Add `tests/integration/test_format_preservation.py::test_plain_text_round_trip` — pick a bids-examples dataset with `README`, read with `read_text_with_profile`, write back unchanged content via `write_text`, assert bytes identical on disk

**Checkpoint**: All three stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T072 [P] Add `tests/test_format.py::test_no_bypass_writers_in_repo` (B.5 meta-test): grep `src/bids_utils/` for `json.dumps(`, `csv.DictWriter(`, `csv.writer(`, and any `Path.write_text` whose target is a sidecar/TSV/plain-text file outside `src/bids_utils/_format/` and `src/bids_utils/_io.py` and `src/bids_utils/_tsv.py`. Allow-list `cli/` (CLI stdout) and `_format/_json_backend.py` (which uses `json.dumps` for the fallback path). Assert no remaining hits. Covers FR-011.
- [ ] T073 [P] Add `tests/test_format.py::test_only_json_backend_imports_json5` (adapter-isolation meta-test): grep `src/bids_utils/` for `import json5` and `from json5` patterns; assert the only hit is `src/bids_utils/_format/_json_backend.py`. This locks in the swap-ability invariant from plan.md.
- [ ] T074 [P] Extend `tests/test_dry_run.py::test_dry_run_diff_matches_real_run` — render a dry-run diff and a real-run diff for the same operation against bids-examples sample; assert text equality (B.7)
- [ ] T075 [P] Add `tests/integration/test_format_preservation.py::test_perf_within_budget` (informational, not gating): time the full sweep, assert ≤1.20× a baseline value stored in `tests/integration/perf_baseline.json` (or skip with TODO if baseline is missing — record it on first green run). Covers SC-006 / B.8.
- [ ] T076 [P] Document in `src/bids_utils/_format/__init__.py` module docstring the FR-014 extensibility shape: "to add a new format, define `<Fmt>FormattingProfile` dataclass + `detect_<fmt>_profile(bytes)` + `serialize_<fmt>(data, profile)` + `DEFAULT_<FMT>_PROFILE`. To swap the JSON backend, write a class implementing `JSONBackend` Protocol and replace `_default_backend` in `_json.py`."
- [ ] T077 [P] Add a brief `library-survey.md` reference comment in `src/bids_utils/_format/_json_backend.py` listing the upstream bug numbers / sections (R1.1.1–R1.1.6) so future maintainers know why each defense exists
- [ ] T078 [P] Update `.specify/specs/001-consistent-inout/quickstart.md` if API names diverged from the contract during implementation (no-op if not)
- [ ] T079 Run full `tox` (py-matrix + lint + type + duplication). Fix every failure. **Do NOT commit until every env passes per `CLAUDE.md` pre-commit gate.**
- [ ] T080 Add a CHANGELOG / changelog.d fragment if this project uses scriv (otherwise skip — `ls changelog.d/` to verify before noting in PR body)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no deps — start immediately
- **Phase 2 (Foundational)**: depends on Phase 1 — BLOCKS all stories
- **Phase 3 (US1, P1)**: depends on Phase 2 — story-internal deps in §3.D
- **Phase 4 (US2, P2)**: depends on Phase 2 — independent of US1; US2 may start in parallel with US3 once Phase 2 is done
- **Phase 5 (US3, P3)**: depends on Phase 2 — independent of US1/US2
- **Phase 6 (Polish)**: T072–T077 depend on the user stories they reference; T079 depends on everything before it

### Within Phase 3 (US1) — implementation chain

```
T033 (Protocol)
   ├──► T034 (parse + detect_profile)
   │      └──► T035 (serialize)
   │             └──► T038 (parse_json + serialize_json polymorphism)
   │                    ├──► T039 (read_json_with_profile)
   │                    │      └──► T041 (legacy read_json wrapper)
   │                    └──► T040 (write_json extension)
   │                           └──► T043, T044, T045, T046, T047 (migrations, parallel)
   ├──► T036 (mutation methods)
   │      └──► T037 (JSONDocument)
   │             └──► T038 (above)
   └──► T042 (re-export)

T048, T049 (integration) depend on T040 + at least one migration site
```

### Within Phase 4 (US2)

```
T056 (detect_tsv_profile) ──► T057 (serialize_tsv) ──► T058 (re-export)
T056 ──► T059 (read_tsv_with_profile)
T057 ──► T060 (write_tsv extension)
T060 ──► T061 (audit) ──► T062, T063 (integration)
```

### Tests-first discipline

- All tests in §3.A (T014–T021), §3.B (T022–T027), §3.C (T028–T032) MUST be written and failing before any task in §3.D (T033+) is started.
- All tests in §4.A (T050–T055) MUST be written and failing before any task in §4.B (T056+).
- All tests in §5.A (T064–T065) MUST be written and failing before any task in §5.B (T066+).
- The Phase 6 meta-tests (T072, T073) lock in FR-011 and the adapter-isolation invariant for the long term.

---

## Parallel Execution Examples

### Phase 2 (Foundational)

```text
# Run concurrently — different dataclasses in the same file but separate edits, plus tests in a separate file:
Task: T005 — FormattingProfile in _format/_profile.py
Task: T006 — TSVFormattingProfile in _format/_profile.py
Task: T007 — TextFormattingProfile in _format/_profile.py
Task: T011 — test_signatures_present in tests/test_format.py
Task: T012 — test_default_profile_for_new_file in tests/test_format.py
Task: T013 — write_if_changed tests in tests/test_format.py
```

### Phase 3.A (Backend defenses) + 3.B (JSONDocument tests) + 3.C (I/O tests)

All eight backend-defense tests (T014–T021) plus the JSONDocument
tests (T022–T027) plus the I/O tests (T028–T032) live in three
distinct files — all 19 can be authored concurrently before any
implementation:

```text
Task: T014, T015, T016, T017, T018, T019, T020, T021  (tests/test_format_json_backend.py)
Task: T022, T023, T024, T025, T026, T027              (tests/test_format.py)
Task: T028, T029, T030, T031, T032                    (tests/test_io.py)
```

### Phase 3.E (migrations after T040 lands)

```text
# Independent files — fully parallel:
Task: T043 — migrate.py
Task: T044 — metadata.py
Task: T045 — _dataset.py
Task: T046 — audit merge/split/rename/run/session/subject
Task: T047 — audit cli/migrate.py + cli/metadata.py
```

### Phases 4 + 5 in parallel

After Phase 2 + Phase 3 are merged, US2 (TSV) and US3 (plain-text)
can be implemented in parallel by separate developers — they touch
disjoint sub-modules within `_format/` and disjoint test functions.

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 → Phase 2 → Phase 3 (US1 only)
2. Run the integration sweep — confirm SC-001 + SC-002 thresholds met
3. **Ship**: localized JSON sidecar diffs are the bulk of observed churn
4. Defer US2/US3 to the next increment

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. + US1 → ship MVP (JSON localized diffs via json-five backend)
3. + US2 → ship TSV preservation
4. + US3 → ship plain-text preservation
5. + Polish (T072 meta-test, T073 adapter-isolation, T074 dry-run, T075 perf) → close the spec

### Backend-swap readiness

The R1.1 defense tests (T014–T021) and the adapter-isolation meta-test
(T073) together encode the contract any future backend must meet. To
swap from `Json5Backend` to a hypothetical alternative:

1. Write a new class implementing `JSONBackend` Protocol in a sibling
   file `_format/_json_backend_<name>.py`.
2. Update `_default_backend` in `_format/_json.py`.
3. Re-run the suite. T014–T021 verify the new backend honors all
   contract clauses; the integration sweep verifies SC-001/002 still
   hold.

No call site changes required — that is the point of this design.

---

## Notes

- All paths are repo-relative; the worktree absolute path is
  `/home/yoh/proj/bids/bids-utils/.git-meta/worktrees/001-consistent-inout/`.
- AI-generated tests must be marked `@pytest.mark.ai_generated` per
  user's global Python conventions.
- Pre-commit gate (`CLAUDE.md`): `tox` MUST pass (py-matrix + lint +
  type + duplication) before any commit. T079 enforces this for the
  feature.
- Reference scripts already in `.specify/specs/001-consistent-inout/`:
  `round_trip_repro.sh` (Phase 1+2+3 reproducer for round-trip,
  mutation, insertion), `json_five_modeldumper_state_bug.py` (R1.1.1
  demonstrator), `json_five_keys_manipulation_bug.py` (R1.1.2/.3
  demonstrator), `json_five_manipulation_probe.py` (full 13-case probe
  matrix). Implementation can copy/adapt patterns from these.
- `library-survey.md` §7.1 documents the corpus-scale evidence that
  motivates the json-five choice (99.91% byte-identity); §7.4
  documents the manipulation-API findings that motivate the adapter.
- Open questions (NOT blocking): deep `JSONDocument` views for nested
  objects (R13 parking lot), surgical splice fast path (R1 parking
  lot), `--normalize` mode (spec Assumptions), YAML support
  (FR-014 — same adapter pattern would apply).
