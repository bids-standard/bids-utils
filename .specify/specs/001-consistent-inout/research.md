# Phase 0 Research — Format-Preserving I/O

This document resolves the open technical questions raised by the Technical
Context section of `plan.md`. Each entry follows: **Decision / Rationale /
Alternatives considered**.

## R1 — JSON: how to preserve indent, key order, and separators on write

**Decision**: Use stdlib `json` with insertion-ordered `dict` for parsing,
and a custom `json.dumps` invocation parameterized by the detected
formatting profile (`indent=<width or "\t">`, `separators=(item_sep,
key_sep)`, `ensure_ascii=False`). Detect the indent and separator style
from the first whitespace pattern observed after parsing the source bytes
with a small hand-written tokenizer that records (a) the first leading
whitespace of a nested element to derive indent character/width and (b)
the bytes between a `:` and the value, and between a `,` and the next
element, to derive separators.

**Rationale**:
- stdlib `json` already preserves key order via `dict` (Python 3.7+).
- Adding new keys at end-of-object is automatic when the new key is
  assigned to an existing dict (FR-005).
- The two style parameters that matter for SC-002 (≤5 changed lines for a
  one-field edit) are *indent* and *separators*. Both are first-class
  arguments of `json.dumps`. Reproducing them, plus key order and trailing
  newline, is sufficient to make the unified diff localized to the edited
  field.
- No new runtime dependency; aligns with constitution Principle IX
  (Simplicity).

**Alternatives considered**:
- `python-json-source-map` / `jsonpreserve` / `cson`-style libraries that
  preserve full source-map fidelity for byte-exact rewrites: rejected as
  overkill — the spec's measurable outcomes are line-diff based, not
  byte-exact for changed regions, and adding a runtime dep for an internal
  refactor violates Principle IX.
- Surgical patching (locate the single changed key in the original byte
  stream and splice in a replacement value): rejected as Phase 1 scope.
  Would deliver SC-002 with margin to spare but adds complexity not
  warranted by the success criteria. Document as a future option in
  `_format.py` docstring.
- `ruamel.yaml`-style round-tripping for JSON: no mature library exists
  for JSON specifically; would mean writing one. Out of scope.

## R2 — JSON: detecting the source indent (spaces vs tabs, width)

**Decision**: After parsing, scan the source bytes for the first newline
followed by a non-newline whitespace run preceding a structural character
(`"`, `{`, `[`, digit, `t`, `f`, `n`). The indent character is the first
byte of that run; the indent width is the run length divided by the
nesting depth of that token (computed by re-parsing or, more simply, by
treating the *first* indented line as depth=1 and using its raw width).
Empty arrays/objects on a single line yield no observation → fall back to
default indent.

**Rationale**: One-pass and dependency-free. Handles the common cases
called out in the spec (2-space, 4-space, tab). Mixed-indent files (edge
case in spec) get the predominant style by majority vote across the first
N (e.g. 50) observed lines.

**Alternatives considered**:
- Use a tokenizer like `tokenize.generate_tokens`: not designed for JSON,
  doesn't help.
- Always re-emit with project default and rely on no-op suppression
  (FR-007): fails SC-002 on every non-default file because every line
  changes when the operation does change one field.

## R3 — JSON: separator style detection

**Decision**: Compact JSON (`json.dumps(data, separators=(",",":"))`)
versus pretty JSON (`(", ", ": ")`) is detected by looking for the first
occurrence of `":"` in the source after a structural `"key"` token. If
followed by a space, separators are `(", ", ": ")` (the stdlib default for
`indent=N`); otherwise compact. This is a binary classification and is
sufficient because real-world sidecars overwhelmingly use one or the
other; intermediate styles (e.g. `" : "`) are rare and acceptable to
normalize.

**Rationale**: Two cases cover essentially 100% of bids-examples; binary
classification is simpler than reproducing arbitrary whitespace.

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
Existing `read_json`/`read_tsv` keep their current return type
(backward-compatible MINOR per Principle X) and gain a sibling
`read_json_with_profile` / `read_tsv_with_profile` (or a keyword
`return_profile=True`). Internal call sites migrate to the
profile-aware variant; external callers (none in our tree) stay on the
original. Writers accept an optional `profile` parameter; when absent,
the documented default profile (FR-006) is used.

**Rationale**: Honors FR-013 (no double-read), Principle X (no break),
and Principle IX (no abstract base class — just two functions per
format).

**Alternatives considered**:
- Always return the tuple and update every caller: works but is a wider
  blast radius for the same outcome.
- Stash the profile in a module-level cache keyed by path: rejected —
  introduces hidden state, breaks for callers that read then write a
  modified copy to a different path.

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

**Decision**: Detection is single-pass O(n) over source bytes; profile is
a small dataclass; no-op-write check reads the file once. Net overhead
per write is one extra file read + a small in-memory comparison. For the
no-op-write case (which the spec identifies as the dominant churn
source), we *save* a write. Microbenchmark target: detection + serialization
of a 100-key sidecar in ≤0.5 ms; full bids-examples sweep ≤20% slower
end-to-end than baseline (validated by a benchmark in
`tests/integration/test_format_preservation.py`).

**Rationale**: All operations are constant-factor on top of work the tool
already does. The 20% budget includes the profile-detection cost and
gains back time from skipped no-op writes.

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

## Open question parking lot (NOT blocking implementation)

- Surgical single-key splice for sub-1-line diffs: deferred (R1).
- `--normalize` opt-in canonicalizing mode: explicitly deferred (spec
  Assumptions).
- YAML support: FR-014 only requires the contract supports adding it
  later; no YAML implementation is in this feature.
