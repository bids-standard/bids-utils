# Phase 0 Research — Format-Preserving I/O

This document resolves the open technical questions raised by the Technical
Context section of `plan.md`. Each entry follows: **Decision / Rationale /
Alternatives considered**.

## R1 — JSON: how to preserve indent, key order, and separators on write

> **Revised 2026-05-02**: replaces the original "stdlib + hand-rolled
> tokenizer" decision after the empirical work in `library-survey.md`
> §6–§7. The original text is preserved as `R1-rejected` below for
> traceability.

**Decision**: Adopt **`json-five`** as the JSON parsing/serialization
backend for round-trip preservation, accessed exclusively through an
internal adapter Protocol (`bids_utils._format._json_backend.JSONBackend`).
Indent, separators, key order, in-line trailing whitespace, and per-line
formatting all ride along on the parsed model — there is no separate
detection pass for these. Only orthogonal byte-level concerns
(BOM presence, trailing-newline state) are captured into the
`FormattingProfile` dataclass.

**Rationale**:
- **Empirical evidence**: `library-survey.md` §7.1 records the corpus
  run on `json-five==1.1.2` against the bids-examples submodule pinned
  at SHA `dd54571267…`. **2,149 of 2,151 files round-trip
  byte-identical (99.91%)**. The 2 failures are zero-byte empty files
  which stdlib `json` would also fail on. This is a direct measurement
  of SC-001 / B.1 against the same corpus that defines our acceptance
  criteria.
- **Diff size**: a stdlib + `json.dumps(indent=N)` rewrite changes
  *every line* of any file whose source style does not match exactly
  what `json.dumps` emits (it never matches `,\n` line splitting,
  trailing whitespace inside arrays, etc., on hand-written files).
  `json-five`'s model preserves these. SC-002 (≤5 changed lines on a
  one-field edit, 95% of sidecars) is achievable with `json-five` and
  practically unachievable with stdlib for hand-curated sidecars.
- **Adapter isolation**: `library-survey.md` §7.4 documents real
  upstream footguns (read-only `key_value_pairs` property; stateful
  `ModelDumper` buffer; `KeyValuePair` NamedTuple immutability;
  asymmetric `keys`/`values` corruption). The adapter is the
  containment for these — none of them leak to call sites. A future
  swap (back to stdlib + splicing, or to a different library) is a
  one-file change.
- **YAGNI compliance**: we ship one backend. The Protocol exists to
  *constrain* the contract, not to enable shipping multiple backends.
- **Cost**: one new runtime dep (`json-five`, MIT, pure-Python, no
  heavy transitive deps). Justified by the measurement above.

**Alternatives considered**:
- *(R1-rejected, 2026-04-26)*: stdlib `json` + hand-written tokenizer
  for indent/separators detection. Rejected because (a) it cannot
  preserve in-line whitespace styles common in hand-curated sidecars,
  failing SC-002 on much of the corpus; (b) the §7 measurement showed
  json-five achieves byte-identity at 99.91% — orders-of-magnitude
  better than the diff-size metric the original plan targeted; (c) the
  added cost is one well-isolated runtime dep, not a structural
  complexity increase, since the adapter contains it.
- `python-json-source-map` / `jsonpreserve`: rejected after §3 review —
  source-map libraries solve a different problem (locate-by-source-position),
  not round-trip preservation.
- Surgical patching (locate the single changed key in the original byte
  stream and splice in a replacement value): parking-lot for a future
  performance optimization. The adapter Protocol allows this swap
  later without changing call sites.
- `ruamel.yaml`-style round-tripping for JSON: no mature library exists
  specifically for JSON; would mean writing one. `json-five` is exactly
  that library, just not yet widely known.

## R1.1 — Defense against `json-five` upstream footguns

**Decision**: The `Json5Backend` adapter implementation in
`_format/_json_backend.py` MUST encode the following defenses, each
with a dedicated unit test in `tests/test_format_json_backend.py`:

1. **Fresh `ModelDumper` per `serialize` call.** The upstream
   `ModelDumper` retains its output buffer across calls; reusing one
   instance returns the concatenation of every prior dump. Reference
   bug: `json_five_modeldumper_state_bug.py`. Defense: never store a
   `ModelDumper` on the backend; instantiate inside `serialize`.
2. **Mutations route through `obj.keys` / `obj.values` only.** The
   `obj.key_value_pairs` attribute is a read-only `@property` returning
   a fresh list — `del obj.key_value_pairs[i]`, slice assignment, and
   index replacement all silently no-op. Reference bug:
   `json_five_keys_manipulation_bug.py`. Defense: `set_value`,
   `delete_key`, `append_key` use the canonical lists.
3. **Length-symmetry assert before every `serialize`.** Asymmetric
   deletion (`del obj.keys[i]` without matching `del obj.values[i]`)
   silently corrupts output. Defense: `serialize` calls
   `assert len(obj.keys) == len(obj.values)` for each `JSONObject`
   reachable from the root, raising a clear error on mismatch. (The
   adapter's own mutation methods never produce asymmetry; the assert
   exists as a defense against hypothetical direct-model access by a
   future contributor.)
4. **`KeyValuePair` is a NamedTuple — never mutate via `kv.value =`.**
   Defense: documented in module docstring; mutation API is exposed at
   the `JSONDocument` level, never at the per-pair level.
5. **Whitespace mirroring on append.** New keys appended via
   `append_key` mirror the `wsc_before` of the prior last KV pair and
   transfer the `wsc_after` (which may contain the trailing newline
   before the closing `}`) so indentation stays consistent. Reference:
   `round_trip_repro.sh` Phase 3.
6. **Parse-fail fallback.** If `json-five` raises during `parse`, the
   backend re-tries with stdlib `json.loads` and returns a
   `FallbackModel` wrapping the resulting dict. Subsequent `serialize`
   calls on a `FallbackModel` use stdlib `json.dumps` parameterized by
   the profile. This handles the 2 zero-byte files in the §7.1 corpus
   run and any future malformed-but-stdlib-tolerable file.

**Rationale**: Each defense corresponds to a specific bug or footgun
discovered empirically during the `library-survey.md` §6–§7 work. Each
test prevents regression if the upstream library ever changes shape.

## R2 — JSON: detecting the source indent

**Decision**: NOT NEEDED in the json-five-backed path. Indent rides on
the model. For the stdlib fallback path (parse-fail or new-file write),
default `DEFAULT_JSON_PROFILE.indent = "  "` per FR-006.

The previously-planned indent detector is dropped. If a future backend
swap to stdlib-with-splicing is taken, this research item must be
restored — its content is preserved in the section "R2-future" below
for that contingency.

### R2-future (parking lot, only if backend swap forces it)

If/when the adapter is swapped back to a stdlib-based backend that
needs to detect indent/separators from source bytes: scan the source
for the first newline followed by a non-newline whitespace run preceding
a structural character (`"`, `{`, `[`, digit, `t`, `f`, `n`). The indent
character is the first byte of that run; the width is run-length /
nesting-depth. Mixed-indent files: predominant style across the first 50
observed lines.

## R3 — JSON: separator style detection

**Decision**: NOT NEEDED in the json-five-backed path (separators ride
on the model). Default for new files is `(",", ": ")` per FR-006.

The previously-planned binary-classification detector is dropped from
the implementation, preserved as parking-lot below in case of backend
swap.

### R3-future (parking lot)

If/when needed: look for the first `":"` after a structural key token;
if followed by a space, separators are `(", ", ": ")` (pretty), else
compact `(",", ":")`.

## R4 — Trailing newline, line endings, and BOM

**Decision**:
- **Trailing newline**: `source_bytes.endswith(b"\n")` (or `b"\r\n"`,
  `b"\r"`) → record boolean. On write, append the matching terminator iff
  the source had one. (FR-003)
- **Line endings**: count occurrences of `b"\r\n"`, `b"\n"` (excluding
  those already counted as part of CRLF), and lone `b"\r"`; predominant
  style wins, ties broken in order CRLF > LF > CR. Apply uniformly on
  write. (FR-004)
- **BOM**: `source_bytes.startswith(b"\xef\xbb\xbf")` → record. On write,
  prepend if recorded; never add otherwise. (FR-008)

**Rationale**: All three are simple byte-level inspections, single-pass,
no library needed. The line-endings predominant-style rule matches
spec FR-004 (mixed → unified to predominant, not silently to LF).

**Alternatives considered**: Preserving per-line ending exactly: rejected
as out of scope per FR-004's explicit normalize-to-predominant rule.

## R5 — TSV: column order and dialect preservation

**Decision**: Read TSV with `csv.reader` (not `DictReader`) to capture the
header row verbatim, then build a `list[dict]` keyed by that order.
Detect line endings and BOM as in R4. On write, use `csv.writer` with the
captured fieldnames, the source's `lineterminator`, and pass-through
quoting (`csv.QUOTE_MINIMAL` is the stdlib default and matches BIDS
expectations). Per-row quoting state is preserved by *not rewriting rows
that the operation did not change*: keep a parallel list of original raw
line bytes; for rows the operation touched, re-serialize via `csv.writer`;
for untouched rows, splice the original byte slice back. (FR-009, FR-010)

**Rationale**: This directly satisfies SC-003 (one-row edit → ≤3 changed
lines) without trying to reproduce arbitrary per-cell quoting decisions
made by the original writer. It also gives FR-007 (no-op write
suppression) for free at the row level.

**Alternatives considered**:
- Full byte-exact rewrite of TSV: would need a TSV-aware tokenizer that
  records each cell's quote style. Out of scope; unnecessary.
- `pandas.read_csv` round-trip: heavyweight new dep, normalizes
  whitespace, fails CRLF preservation. Rejected.

## R6 — No-op write suppression (FR-007 / SC-001)

**Decision**: Wrap every write in a helper `write_if_changed(path, new_bytes)`
that compares `new_bytes` to `path.read_bytes()` (when the file exists) and
short-circuits when equal. Applies to JSON, TSV, and plain-text writers.
For VCS-managed files, the unlock-before / re-add-after lifecycle in
`_io.py` also short-circuits when no write happened (avoids spurious
`git annex unlock`).

**Rationale**: Bytewise comparison is the only correct check (spec
Assumptions explicitly excludes hashing parsed content). Cost is one
file read, dwarfed by the avoided write + VCS bookkeeping.

**Alternatives considered**: Hashing parsed content (rejected by spec
assumptions). Comparing pre-parse vs post-parse data structure (misses
formatting-only churn; doesn't address the symmetric "intentional
formatting change" case for a future `--normalize` mode).

## R7 — Dry-run integration (spec edge case)

**Decision**: Dry-run already constructs the same in-memory data
structures as a real run; route its diff generation through the same
profile-aware serializer. Concretely, in code paths that today produce a
preview by calling `json.dumps(new_data, indent=2)`, swap to
`_format.serialize_json(new_data, profile)` where `profile` came from the
read. The resulting preview text matches what a real write would have
produced byte-for-byte, so the displayed diff matches the on-disk diff a
real run would create.

**Rationale**: Constitution VIII requires dry-run output identical in
format to actual-run output; this satisfies it for the edge case spec
flags.

## R8 — Where the profile lives in the data flow (FR-013)

**Decision**: Each profile-aware reader returns `(content, profile)`.
For JSON, *content* is a `JSONDocument` (MutableMapping wrapping the
json-five model + the profile). The `JSONDocument` itself stores the
profile, so `write_json(doc, ...)` does not strictly need the profile
argument — but the API still accepts an explicit `profile=` for
symmetry with TSV/text and for the case where a caller wants to
override (e.g., normalize-mode in a future opt-in). Existing
`read_json`/`read_tsv` keep their plain-dict return type for
backward compatibility (Principle X) and gain a sibling
`read_json_with_profile` / `read_tsv_with_profile`. Writers accept
optional `profile=`; when absent and the input is a plain dict
(new-file path), the documented default profile (FR-006) is used.

**Rationale**: Honors FR-013 (no double-read), Principle X (no break),
and Principle IX (one Protocol, one implementation; no inheritance
tree). Carrying the profile alongside `JSONDocument` also lets us
keep BOM/trailing-newline state out of the user's mental model when
they just want to "edit a field and write it back".

**Alternatives considered**:
- Always return the tuple and update every caller: works but is a wider
  blast radius for the same outcome.
- Stash the profile in a module-level cache keyed by path: rejected —
  introduces hidden state, breaks for callers that read then write a
  modified copy to a different path.
- Make `JSONDocument` mandatorily carry the profile and drop the
  `(doc, profile)` tuple: rejected for symmetry with TSV/text, where
  we keep the tuple shape because TSV `original_lines` is conceptually
  separate from the row data.

## R9 — Default profile for newly created files (FR-006)

**Decision**: Single module-level constant
`DEFAULT_JSON_PROFILE = FormattingProfile(indent="  ", separators=(",", ": "),
line_ending="\n", trailing_newline=True, bom=False)`,
matching today's `json.dumps(data, indent=2) + "\n"` output. Same module
holds `DEFAULT_TSV_PROFILE` and `DEFAULT_TEXT_PROFILE`. All writers
default to these constants when no profile is provided. (FR-006: "defined
in one place and not duplicated per command".)

**Rationale**: Trivially satisfies the FR. Migration is a search-and-replace
of `json.dumps(..., indent=2) + "\n"` → `_io.write_json(path, data, vcs)`.

## R10 — Performance budget (SC-006)

**Decision**: `json-five` is pure-Python (vs stdlib `json`'s C
implementation), so the per-file parse + serialize cost is higher than
stdlib. Empirically (see `library-survey.md` §7.1), the full
bids-examples corpus (~2,151 files) round-trips through json-five in a
few seconds. The dominant cost in real bids-utils workflows is *I/O*
(read file → mutate → write file → optional VCS bookkeeping), not the
parse step. The profile-aware path also gains back time from skipped
no-op writes (FR-007). Empirical sweep target: full
bids-examples integration suite ≤1.20× pre-feature baseline
(SC-006). Microbenchmark target: parse + serialize of a 100-key
sidecar in ≤5 ms (10× the original stdlib budget — the §7 corpus run
is well under this in aggregate).

**Rationale**: We accept a higher constant factor for parse to gain
much-better diff quality. Constitution Principle VI (Performance at
Scale) is satisfied by the SC-006 ≤20% budget, which the §7
measurement shows is well within reach.

**Alternatives considered**:
- Skip json-five for "small" files and use stdlib for everything else:
  unnecessary complexity; the corpus run was fast in aggregate.
- Run parse / serialize concurrently across files via
  `concurrent.futures`: parking-lot for if/when SC-006 needs more
  headroom. Not in MVP scope.

## R11 — Tests against bids-examples for SC-001/002/003

**Decision**: Add `tests/integration/test_format_preservation.py` that:
1. Sweeps `bids-examples` datasets, captures pre-image bytes for each
   text file, runs a representative bids-utils operation (e.g., a
   `migrate` or a `subject-rename` no-op with `--dry-run` then a real
   no-op pass), and asserts SC-001 (no semantic change → bytes
   unchanged) holds across the corpus.
2. For SC-002/003, runs a one-field/one-row edit on a representative
   sample and computes `difflib.unified_diff` line counts; asserts the
   percentage thresholds.
3. Exercised in both regular-git and tmp_annex_dataset modes per
   constitution Principle V/VII.

**Rationale**: Spec's Measurable Outcomes are the acceptance gate;
expressing them as tests on the canonical corpus keeps them honest.

## R12 — Adapter Protocol shape (new, 2026-05-02)

**Decision**: Define `JSONBackend` as a `typing.Protocol` (not an
`abc.ABC`) in `_format/_json_backend.py`. One implementation:
`Json5Backend`. The Protocol fixes the contract; the implementation
fulfills it. A future swap requires writing a new class that conforms
to the same Protocol — verified by the `tests/test_format_json_backend.py`
suite which is **backend-agnostic** (it imports the abstract Protocol
methods and tests an instance, not the concrete class).

```python
class JSONBackend(Protocol):
    def parse(self, source: bytes) -> Any: ...
    def serialize(self, model: Any, profile: FormattingProfile) -> bytes: ...
    def detect_profile(self, source: bytes) -> FormattingProfile: ...
    def get_keys(self, model: Any) -> list[str]: ...
    def get_value(self, model: Any, key: str) -> Any: ...
    def set_value(self, model: Any, key: str, value: Any) -> None: ...
    def append_key(self, model: Any, key: str, value: Any) -> None: ...
    def delete_key(self, model: Any, key: str) -> None: ...
```

**Rationale**:
- `Protocol` is structural; a future replacement just needs the same
  methods, without inheriting from anything. Aligns with Principle IX
  (Simplicity — no inheritance hierarchy).
- mypy can verify Protocol conformance on each implementation.
- The tests pin the contract in code, not just in a docstring.

**Alternatives considered**:
- `abc.ABC`: heavier; nominal subtyping forces inheritance from a
  shared base. Protocol is enough.
- A plain module with module-level functions (no class): rejected —
  swapping a module is harder than swapping a class instance, and
  testing two backends side-by-side would mean importing two modules.

## R13 — `JSONDocument` semantics (new, 2026-05-02)

**Decision**: `JSONDocument` is a `collections.abc.MutableMapping[str,
Any]`. It wraps the backend's opaque `model` plus a `FormattingProfile`.
Read operations (`__getitem__`, `__iter__`, `__len__`, `__contains__`)
return Python values materialized from the model (lists, plain dicts
for nested objects, strings, numbers, bools, None). Write operations
(`__setitem__`, `__delitem__`) route through the backend and may
short-circuit on no-change-detected for `__setitem__` (compare new
value to old before mutating).

**Nested objects**: `doc["nested_obj"]` returns a plain Python `dict`
view, NOT another `JSONDocument`. Mutating that returned dict does
**not** propagate back into the model. To write a nested change, the
caller assigns the whole subtree:
```python
nested = doc["Nested"]                # plain dict view
nested["NewKey"] = "value"            # local mutation only
doc["Nested"] = nested                # writes the whole subtree back
```

**Rationale**:
- Most BIDS sidecars are flat or shallow; the assign-whole-subtree
  pattern is acceptable and explicit.
- Returning a deep `JSONDocument` view for nested objects would 4× the
  surface (every nested write needs propagation tracking) for a small
  win.
- Whole-subtree assignment is also what `migrate.py` already does for
  most rule applications, so the migration cost is small.

**Alternatives considered**:
- Deep views (recursive `JSONDocument`): rejected for the surface
  cost above. May revisit if a real call site needs it.
- Return a `MappingProxyType` for nested objects (read-only): rejected
  because callers legitimately mutate locally, then assign back.
- Make `JSONDocument` itself only support get/set/del/iter/len/contains
  and document via type hints that nested writes don't propagate:
  *taken*. Plus a runtime check in tests via the meta-test (B.5) that
  no call site stores a return-value-of-`__getitem__`-and-mutates
  pattern that doesn't end with an assign-back.

## Open question parking lot (NOT blocking implementation)

- Deep `JSONDocument` views for nested objects: deferred (R13).
- Surgical single-key splice for sub-1-line diffs: not needed —
  json-five already achieves the diff target. Parking lot for if/when
  json-five is replaced.
- `--normalize` opt-in canonicalizing mode: explicitly deferred (spec
  Assumptions).
- YAML support: FR-014 only requires the contract supports adding it
  later; no YAML implementation is in this feature. The same adapter
  pattern applies — a `YamlBackend` would slot in.
- Concurrency for large datasets: deferred (R10).
