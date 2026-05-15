# Library Survey — Format-Preserving JSON I/O

Research date: 2026-04-26. Scope: actively-maintained Python libraries that
could replace or supplement stdlib `json` for the use case in
`spec.md` (FR-001..FR-014, SC-001..SC-006) and the API shape in
`contracts/io_contract.md`.

## 1. Executive Summary

**No library on PyPI today clearly beats "stdlib `json` + a small hand-rolled
`FormattingProfile` detector" for our use case.** The closest contender is
**`json-source-map`** (Apache-2.0, pure-Python, no runtime deps): it would
let us achieve FR-002/B.2's strongest form — a *single-line* diff for a
single-field edit (vs. our planned 95% / ≤5 lines) — by giving us byte
offsets for keys and values, which we could splice in place. But it is
read-only positional metadata and was last released 2022-12 / last
committed 2023-10, so adopting it means owning the splice layer and
betting on a lightly-maintained dep. Every other library we evaluated
either fails our license bar (jsonyx GPL-3.0, demjson3 LGPL-3.0),
solves a different problem (json-five preserves JSON5 *comments*, not
strict-JSON *indent style*), or normalizes formatting on emit (ruamel.yaml
explicitly normalizes indent on round-trip). Recommendation: **stick
with stdlib + FormattingProfile**, and consider `json-source-map` as a
*future* surgical-edit upgrade if SC-002's 95% target proves
insufficient in practice.

## 2. Comparison Table

| Name | License | Last release | Last commit | Deps | Pure-Py | Preserves | Verdict |
|---|---|---|---|---|---|---|---|
| stdlib `json` (baseline) | PSF | n/a | n/a | none | yes | key order only (3.7+); needs hand-rolled detection for indent/EOL/BOM/trailing-newline | baseline |
| [json-source-map](https://pypi.org/project/json-source-map/) | Apache-2.0 | 1.0.5, 2022-12-20 | 2023-10-09 | none | yes | source positions (line/col/char start+end for every key & value) — enables byte-splicing surgical edits | **consider** for surgical-edit upgrade; lightly maintained |
| [python-json-source-map](https://pypi.org/project/python-json-source-map/) | — | could not load PyPI page | — | — | — | — | could not verify; likely the same or earlier alias of `json-source-map` |
| [json-five](https://pypi.org/project/json-five/) (spyoungtech) | Apache-2.0 | 1.1.2, 2024-06-11; last commit 2025-05-07 | 2025-05-07 | `sly`, `regex` | yes | **empirically verified 2026-04-26**: model API round-trips strict-JSON byte-for-byte (CRLF, 4-space indent, mixed colon spacing, no-trailing-newline state) for all but the BOM | **reconsider** — model API is the only library tested that actually preserves all formatting except BOM (which is trivially handled at the byte layer); see §6 |
| [jsonyx](https://pypi.org/project/jsonyx/) | **LGPL-3.0** (verified from `LICENSE` in repo on 2026-04-26 — the survey's earlier "GPL-3.0-or-later" claim was incorrect) | 2.3.0 (active) | active | none | yes (optional C ext) | extended JSON dialect | **reject** — does not aim at format preservation (verified: README and docs make no such claim); LGPL is permissive enough for library use but not the right tool |
| [demjson3](https://pypi.org/project/demjson3/) | **LGPL-v3** | 3.0.6, 2022-10-22 | dormant | none | yes | reformat (no preservation) | **reject** — copyleft + dormant + only declares Py 3.5–3.9 |
| [ruamel.yaml](https://pypi.org/project/ruamel.yaml/) | MIT | 0.19.1, 2026-01-02 | active | none (libyaml optional) | yes | YAML round-trip; **explicitly normalizes indent on round-trip** ("individual indentation is not preserved"); risky for strict JSON (booleans, nulls, numeric formats) | **reject** — wrong tool, would change semantics |
| [json-five](https://github.com/spyoungtech/json-five) — see above | | | | | | | |
| [jsonpatch](https://pypi.org/project/jsonpatch/) | BSD-3-Clause | 1.33, 2023-06-16; last commit 2024-08-05 | 2024-08 | none | yes | semantic RFC 6902 patches; **not byte-preserving** | **reject** for preservation; orthogonal tool |
| commentjson, hjson-py, json5 (dpranke), json2ast, json-tricks | various | — | — | — | — | none preserve indent/EOL/BOM | **reject** — none target byte-level preservation |
| orjson, simplejson, rapidjson, ujson | various | active | active | mostly native | C ext | speed only; orjson does not even support custom indent | **reject** — speed variants, no preservation |
| canonicaljson, rfc8785 | Apache-2.0 / MIT | active | active | small | yes | the **opposite** (canonicalize) | **reject** — opposite direction (useful only as contrast) |
| LibCST | MIT | active | active | medium | yes | preserves Python source — not JSON | **N/A** — Python language only |
| tree-sitter + tree-sitter-json | MIT | active | active | C native binding | no | concrete syntax tree of JSON with byte ranges | **reject** — heavy native dep, JSON grammar gives positions but no edit/serializer; we'd build the same splice layer as with json-source-map and pay a C dep instead of zero deps |
| PyYAML | MIT | active | active | optional C | yes | does **not** round-trip preserve | mentioned as anti-pattern; reject |

For TSV: `tablib`, `python-tabulate`, `csvkit` all rewrite and pretty-print
columns; none preserve quoting/EOL of unchanged rows. **stdlib `csv` plus
the line-splice approach already in `TSVFormattingProfile.original_lines`
is the right choice** — confirmed.

## 3. Detailed Evaluations

### 3.1 `json-source-map` — Apache-2.0, pure-Python, no deps

```python
from json_source_map import calculate
src = b'{"A": 1,\n  "B": 2}'
m = calculate(src.decode())
# m["/B"].value_start.line == 1, .column == 7, .position == 12
```

**License**: Apache-2.0 (declared in pyproject.toml on
`open-alchemy/json-source-map`). Permissive — passes.
**Deps**: zero runtime deps; pyproject declares only test-time deps.
**Python versions**: declared `^3.8` — works for our 3.10–3.14 target
(though no explicit 3.13/3.14 classifier, the lib is pure Python and
trivially compatible).
**Maintenance**: latest release 1.0.5 on 2022-12-20; latest commit
2023-10-09 (Python 3.12 test additions and dependabot bumps). Single
maintainer (David Andersson / open-alchemy). **Lightly maintained** —
~2.5 years since last commit. Functionally feature-complete for what it
does; risk is bug-fix latency.

**What it preserves**: nothing on its own — it returns a dict mapping
JSON-Pointer paths to `(line, column, position)` tuples for both the key
and value of every node. By itself it does **not** write JSON.

**Why it matters here**: it is the only credible primitive on PyPI for
implementing **surgical edits** — load the source bytes, find the byte
range of the value at JSON-Pointer `/IntendedFor`, splice in the new
serialized scalar, write back. That gives single-line diffs in 100% of
cases for value-swap edits, surpassing SC-002's 95%/≤5-line target.
Nested-object insertions (FR-005) still need careful "where does the
trailing comma go" logic, which the library does not provide — we would
write that ourselves.

**Integration cost**: medium. We would rewrite `serialize_json()` to
take both `data` and (optionally) the original source bytes; on
single-key edits that don't change structure, splice; otherwise fall
back to stdlib re-emit with `FormattingProfile`. The
`FormattingProfile` contract in `_format.py` would still exist (for
new-file defaults FR-006 and the structural-edit fallback), so this is
*additive*, not a replacement.

**Verdict**: not recommended for v1, but recommended as a **named
follow-up** for v2 if SC-002 measurements on bids-examples reveal the
≤5-line/95% target is missed too often. Lock to a version pin and
vendor if upstream goes dormant.

### 3.2 `json-five` (spyoungtech) — Apache-2.0, JSON5 with model API

```python
import json5
# basic load/dump preserves identifier quoting on round-trip:
assert json5.dumps(json5.loads(text)) == text  # only for JSON5 idents
```

**License**: Apache-2.0 (PyPI classifiers + setup.cfg). Passes.
**Deps**: `sly` (parser generator) + `regex`. Two non-stdlib deps.
**Python**: 3.8+; supported through 3.11 in setup.cfg, possibly works
on 3.12+ but not declared.
**Maintenance**: 1.1.2 released 2024-06; last commit 2025-05-07. Single
maintainer. Active but slow.
**What it preserves**: JSON5 *comments* and JSON5 *identifier* quoting,
via a separate ModelLoader/ModelDumper API. The README and docs
explicitly call out "round-trip preservation of comments" — not indent
style, not key separators, not line endings. The model API is **marked
explicitly unstable** ("subject to breaking changes, even in minor
releases").

**Empirical 2026-04-26 update**: the model API turned out to also
preserve indent, line endings, mixed colon spacing, and no-trailing-newline
state byte-for-byte for strict-JSON input. This was not advertised. See
§6.4 for the experiment. The only thing it does not preserve is the UTF-8
BOM (which it strips and does not re-emit). This makes it a viable
candidate for our use case if we are willing to accept the unstable model
API and the `sly` runtime cost.

**Integration cost (revised)**: medium. We would parse with the model
loader, mutate `raw_value` on the model node we want to change, dump
with the model dumper, and re-prefix the BOM at the byte layer if the
source had one. The `FormattingProfile` work in `_format.py` is mostly
unnecessary in this path (the model carries the formatting). We do
still need it for the *new file* / *full-rewrite* paths because the
model dumper is only useful for byte-preserving round-trips, not for
emitting freshly-constructed objects with a chosen formatting. The
`sly` parser dependency adds ~1 ms per kB to load (rough order); for
sub-MB BIDS sidecars this is comfortably within SC-006's 1.20× budget,
but for the few-MB `participants.tsv`-adjacent JSON cases it should be
measured.

**Verdict (revised)**: reconsider for v1. The empirical preservation is
exactly what we want; the costs are (a) an unstable model-API surface,
(b) a non-trivial third-party parser (`sly` + `regex`), and (c) needing
to keep stdlib-`json`+`FormattingProfile` for the new-file path
anyway. Decision deferred to §6.X bottom line.

### 3.3 `jsonpatch` (RFC 6902) — BSD-3-Clause, semantic patches

```python
import jsonpatch
patch = jsonpatch.make_patch(old_dict, new_dict)
# [{"op": "replace", "path": "/IntendedFor", "value": "..."}]
```

**License**: BSD-3-Clause. Pure-Python. Last release 1.33, 2023-06-16;
latest commit 2024-08-05. Multiple contributors over time.
**What it preserves**: nothing in terms of bytes. RFC 6902 is a
*semantic* diff format. Useful for representing what changed, not for
how to write it.
**Verdict**: orthogonal to FR-001..FR-013. Could be a nice-to-have for
the dry-run diff display layer (B.7), but not for serialization. Not
recommended now.

### 3.4 `ruamel.yaml` — MIT, the canonical YAML round-tripper

**License**: MIT, very active (0.19.1, 2026-01-02). Pure Python (libyaml
optional). Multi-decade maintenance by Anthon van der Neut.
**What it preserves**: YAML comments, key order, flow vs block style.
**What it normalizes**: indentation ("individual indentation is not
preserved" — confirmed by upstream documentation philosophy and
[cpython issue 90948](https://github.com/python/cpython/issues/90948)),
boolean/null spellings, numeric formats. Strict JSON is technically a
YAML 1.2 subset but YAML 1.1 booleans (`yes`/`no`/`on`/`off`) are
landmines, and forcing JSON-style emission still defeats indent
preservation.
**Verdict**: reject. Would add a heavyweight semantic-conversion layer
to fix a small formatting problem, with measurable risk of changing
field values.

### 3.5 `jsonyx` — LGPL-3.0, extended JSON dialect, no preservation goal

**License (corrected)**: **LGPL-3.0**, not GPL-3.0-or-later as stated in
the original survey. Verified 2026-04-26 by reading
[`LICENSE`](https://raw.githubusercontent.com/nineteendo/jsonyx/main/LICENSE)
in the upstream repo: the file is the GNU **Lesser** General Public
License, Version 3, 29 June 2007. LGPL is permissive enough for
*library use* under most readings of the FSF guidance (we link
dynamically and do not modify the library), so the original
license-policy "reject" was based on a wrong reading of the file.

**Format-preservation goal**: **none stated**. Verified 2026-04-26 by
reading the upstream README and stable docs index. The "Key Features"
list is: "JSON encoding, decoding and patching", "Pretty printing",
"Optional JSON deviations support", "Detailed error messages". None of
those mention round-trip preservation, indent preservation, byte
preservation, or comment preservation. The class `jsonyx.Manipulator`
is a stateless query/patch helper that operates on the parsed Python
data structure, not on bytes — confirmed by reading its `__init__`
signature (`*, allow=frozenset(), use_decimal=False`). The patch
operation set (`set`, `del`, `append`, `move`, `copy`, `update`,
`extend`, `insert`, `clear`, `assert`, `reverse`, `sort`) is RFC
6902-shaped semantic patching; it has no positional metadata.

**Empirical 2026-04-26**: see §6.5. `jsonyx.dumps(jsonyx.loads(text))`
normalizes everything (default flow style, no BOM, no CRLF). With
`indent=4` it preserves the indent width and the key order but nothing
else. It is squarely a stdlib-`json`-replacement library focused on
features and error reporting, not on byte preservation.

**Verdict (revised)**: reject. The license is OK (LGPL, dynamic-link is
fine for our distribution), but the library does not target our
problem at all. Adopting it would buy us better error messages and
JSON-Patch — neither of which is on our requirements list — at the cost
of a non-stdlib dep that does not actually solve the byte-preservation
problem.

### 3.6 Performance variants (orjson / simplejson / rapidjson / ujson)

All four are speed-focused. None offer indent/EOL/BOM/key-separator
preservation. orjson does not even support arbitrary indent strings
(only `INDENT_2`). They would only help SC-006 (perf), and stdlib `json`
is already C-backed and fast enough — perf is not the bottleneck. Reject.

### 3.7 tree-sitter + tree-sitter-json

Provides positions like `json-source-map` but with a C native binding
plus a separate language grammar. Heavier dep footprint than
`json-source-map` for the same outcome (positions only; no serializer).
Reject — no upside over `json-source-map`, downside is C dep.

## 4. Final Recommendation

**(c) Stick with stdlib `json` + a hand-rolled `FormattingProfile` in
`_format.py`** as planned in the existing spec/contract. Concrete
reasons each candidate falls short:

- `json-source-map` would let us exceed SC-002 (single-line diff for
  any single-field edit), but it is lightly maintained (last commit
  2023-10), provides no serializer, and the splice layer we would still
  write covers most of the work. The "stdlib + FormattingProfile" plan
  already meets SC-002's 95%/≤5-line target by re-emitting with the
  detected indent/EOL/BOM/trailing-newline. Adopt only if measurements
  show we miss the target.
- `json-five` solves JSON5 comments, which BIDS forbids.
- `ruamel.yaml` normalizes indent and risks YAML semantics on JSON
  payloads.
- `jsonyx` (**LGPL-3.0**, not GPL-3.0 — license claim corrected
  2026-04-26) does not target byte-level preservation per its own
  README/docs (verified). `demjson3` is LGPL-3.0 and dormant. Neither
  is a fit even setting license aside.
- `jsonpatch` is orthogonal (semantic, not byte-level).
- All speed variants ignore preservation entirely.

**Strongest contenders (named with PyPI URLs) if a library path is
revisited later:**

1. [json-source-map](https://pypi.org/project/json-source-map/) — for
   surgical-edit byte splicing if/when SC-002 needs to go from 95% to
   100%.
2. [jsonpatch](https://pypi.org/project/jsonpatch/) — for the dry-run
   diff layer (B.7) if a structured semantic-diff display is wanted.

For TSV (FR-009/FR-010), continue with stdlib `csv` plus `original_lines`
in `TSVFormattingProfile`. No survey candidate beats this for
quote/EOL/column-order preservation of unchanged rows.

## 5. Risks / Open Questions

- **`json-source-map` maintenance ambiguity**: the project shows ~2.5
  years of inactivity but is also feature-complete for what it does.
  Whether to depend on a stale-but-working Apache-2.0 single-maintainer
  library is a judgment call. If we ever adopt it, vendor a copy in
  `src/bids_utils/_vendor/` to insulate against upstream rot.
- **`python-json-source-map`** (the other PyPI name): could not load
  PyPI metadata page directly during this survey (page rendering
  failed); could not confirm whether it is the same project under a
  different name, an older alias, or a different lib. If pursued,
  verify on PyPI manually before depending. Best evidence is that
  `json-source-map` is the live name and `python-json-source-map`
  is either a typo squat or an earlier rename.
- **`json-five` model API stability**: explicitly marked unstable by
  upstream — even if BIDS started allowing comments, depending on the
  model layer is a continuous-breakage risk.
- **No survey of internal/private libraries**: I only searched PyPI,
  GitHub, and recent (2024–2026) blog posts. There may be a niche lib
  (e.g., from JSON Schema tooling like `jsonschema`'s authors, or a
  config-management toolkit) that does byte-preserving JSON edits and
  isn't discoverable by the search terms tried. The terms searched
  included "lossless JSON round-trip", "JSON CST python", "JSON edit in
  place byte preserving", "JSON source positions", "format preserving
  JSON pypi". Nothing else surfaced.
- **Pre-existing `json-asty` (rse/json-asty)**: this is a JavaScript
  library, no Python port found. Mentioned for completeness.
- **Performance contention**: stdlib `json` is C-backed (`_json`
  module). Replacing it with any pure-Python alternative (json-five,
  jsonyx) would directly threaten SC-006's 1.20× perf budget. This is
  another structural reason to prefer stdlib for the hot path.

## 6. Empirical experiments (2026-04-26)

To turn the desk-research recommendation into a measured one, I built a
deliberately tricky strict-JSON sidecar fixture and ran identity
round-trip and single-field-edit experiments against each candidate
library in an isolated `uv` venv on Python 3.12.13. All test artefacts
live under `/tmp/json-lib-eval/` and are reproducible (`make_fixture.py`
+ `run_experiments.py` in that directory).

### 6.1 The fixture

`tricky.json` is 306 bytes constructed from raw byte literals so every
quirk is intentional. Verified via `hexdump -C tricky.json | head`:

- **UTF-8 BOM** (`ef bb bf`) at offset 0.
- **CRLF** (`0d 0a`) line endings throughout — 13 line breaks, all CRLF.
- **4-space indent** at the top level, 8-space at the nested level.
- **No trailing newline** — last byte is `}` (`7d`).
- **Mixed colon spacing**, all four variants in one file:
  - `"Manufacturer": "Siemens"` (standard `key": "val`)
  - `"MagneticFieldStrength" : 3` (extra space *before* `:`)
  - `"RepetitionTime":2.0` (compact, no space)
  - `"EchoTime" :  0.03` (extra space after `:`)
- **Non-alphabetical key order**: `Manufacturer`, `MagneticFieldStrength`,
  `RepetitionTime`, `EchoTime`, `IntendedFor`, `Acquisition` (nested
  `Coil`, `Bandwidth`), `Notes`.
- **List value** for `IntendedFor`.

A second fixture `tricky_yes.json` carries the string `"yes"` to test
the YAML-1.1 boolean landmine.

### 6.2 stdlib `json` — Python 3.12, baseline

- License: PSF.
- Format-preservation goal: none (out of scope by design).

**Experiment 1 (round-trip).** Read with `json.loads`, emit with
`json.dumps(data, indent=2)` (the most generous setting available out
of the box). Survives: key order only. Lost: BOM, CRLF, 4-space indent
(stdlib forces 2-space), all four colon-spacing variants, and the
no-trailing-newline state (`json.dumps` does not add a trailing newline,
which happens to match here, so that one is a coincidence).

**Experiment 2 (single edit).** Set `EchoTime` to `0.04`. **30 diff
lines** — every single line of the file is rewritten:

```diff
--- tricky.json
+++ stdlib-edit
@@ -1,14 +1,14 @@
-﻿{
-    "Manufacturer": "Siemens",
-    "MagneticFieldStrength" : 3,
-    "RepetitionTime":2.0,
-    "EchoTime" :  0.03,
-    "IntendedFor": [
+{
+  "Manufacturer": "Siemens",
+  "MagneticFieldStrength": 3,
+  "RepetitionTime": 2.0,
+  "EchoTime": 0.04,
+  "IntendedFor": [
…
```

**Verdict**: every formatting aspect except key order is normalized; this
is the gap that motivated the survey in the first place.

### 6.3 `json-source-map` 1.0.5 — Apache-2.0

- License: Apache-2.0 (verified).
- Format-preservation goal: not stated; the library returns positions,
  no serializer.

**Experiment 1**: not applicable — no writer.

**Experiment 2b (manual splice)**. Position info comes back as char
indices in the BOM-stripped decoded string. With a small char-to-byte
mapping (since the fixture has only ASCII content, this is a no-op for
our payload, but the implementation handles multi-byte UTF-8) we
spliced `0.04` into the byte range `[117, 121]` reported for
`/EchoTime`'s value. The result is **byte-identical to the source
except for the 4 bytes of the value**:

```diff
--- tricky.json
+++ json-source-map-splice
@@ -4,3 +4,3 @@
     "RepetitionTime":2.0,
-    "EchoTime" :  0.03,
+    "EchoTime" :  0.04,
     "IntendedFor": [
```

7 unified-diff lines (4 header + 1 context above + 1 changed pair + 1
context below = the canonical "single semantic line changed" shape).

**Verdict**: works exactly as advertised; preservation is *complete*
(BOM, CRLF, indent, colon spacing, key order, trailing-newline state)
because we never re-emit anything we don't change. The splice
itself is ~10 lines of careful Python that we own. Insertion of new
keys (FR-005) needs comma-handling logic the library does not provide.

### 6.4 `ruamel.yaml` 0.19.1 (`typ="rt"`) — MIT

- License: MIT.
- Format-preservation goal for *YAML*: yes; for *JSON* output: no.
  ruamel.yaml's documentation explicitly says individual indentation
  is not preserved.

**Experiment 1**. Loaded the BOM+CRLF source via `YAML(typ="rt")` and
dumped to a fresh buffer. The result loses BOM, CRLF, 4-space indent,
all colon spacing, the trailing-newline state — and crucially is **not
even valid JSON**: ruamel adds soft line wraps that break JSON syntax:

```diff
--- tricky.json
+++ ruamel-rt-emit
@@ -1,14 +1,3 @@
-﻿{
-    "Manufacturer": "Siemens",
…
-    "Notes": "tricky"
-}+{"Manufacturer": "Siemens", "MagneticFieldStrength": 3, "RepetitionTime": 2.0, "EchoTime": 0.03,
+"IntendedFor": ["func/sub-01_task-rest_bold.nii.gz"], "Acquisition": {"Coil": "32ch",
+"Bandwidth": 2056}, "Notes": "tricky"}
```

I confirmed this output fails `json.loads` with `Expecting property name
enclosed in double quotes: line 1 column 2`. The implicit object
placement at top level is YAML, not JSON. (To get valid JSON out, one
would need to compose `yaml.dump` differently, defeating the purpose.)

**`typ="safe"` Experiment 1**: also normalizes everything (and now
loses key order too).

**YAML 1.1 boolean landmine**. The fixture
`tricky_yes.json = {"ConsentGiven": "yes", "ParticipantsAge": 30}`
parsed under `typ="rt"` keeps `ConsentGiven` as the string `"yes"`
(class `DoubleQuotedScalarString`) and re-emits it quoted, so for
strict-JSON inputs `typ="rt"` happens to be safe on this point. **But
under `typ="safe"`** the value parses to the *string* `"yes"` (good)
and emits as `b'{ConsentGiven: yes, ParticipantsAge: 30}\n'` —
unquoted, which on round-trip through any YAML 1.1 reader becomes
boolean `True`. So `typ="safe"` is unsafe for our use case.

**Verdict**: confirmed reject. ruamel.yaml is the wrong tool, and its
JSON-shaped output is broken twice over (not valid JSON; risks turning
strings into booleans on later YAML reads).

### 6.5 `json-five` 1.1.2 — Apache-2.0 — the unexpected winner

- License: Apache-2.0 (verified).
- Format-preservation goal: stated for JSON5 *comments*; **not stated
  for indent / EOL / colon spacing**.

**Experiment 1 (basic `json5.loads`/`json5.dumps`)**: normalizes
everything, similar to stdlib but flow-style by default.

**Experiment 1 (model API: `ModelLoader` + `ModelDumper`)**:
`ModelDumper().dumps(ModelLoader().loads(text))` produced output that,
compared to the BOM-stripped source, was **byte-identical** — every
CRLF, every 4-space indent, every space before / after / inside the
colon, the trailing-newline state, and key order all survived. Compared
to the *raw* source the only difference is the missing BOM (the model
dumper does not emit one):

```diff
--- tricky.json
+++ json5-model-emit
@@ -1,2 +1,2 @@
-﻿{
+{
     "Manufacturer": "Siemens",
```

That is 6 unified-diff lines, all attributable to the BOM. The internal
`Notes` field with trailing-quote-only-no-newline came through
unchanged.

**Experiment 2 (single edit)**. Mutate the model node in place:
`kv.value.raw_value = "0.04"` for the `EchoTime` `Float` node — note
that `KeyValuePair` is a NamedTuple and its `value` slot is immutable,
but the `Float` node carries a writable `raw_value`. Re-emit, then
re-prefix the BOM at the byte layer. Result: a clean **single
semantic-line diff**, indistinguishable in shape from the
`json-source-map` splice:

```diff
--- tricky.json
+++ json5-model-edit-with-BOM
@@ -4,3 +4,3 @@
     "RepetitionTime":2.0,
-    "EchoTime" :  0.03,
+    "EchoTime" :  0.04,
     "IntendedFor": [
```

7 unified-diff lines, byte-identical outside the changed line. The
model API also passed the YAML "yes" landmine trivially because it is
a JSON parser, not a YAML parser: `'{"ConsentGiven": "yes"}'` round-trips
byte-identical.

**Verdict**: `json-five`'s model API is the only library tested that
*emits* a byte-preserving round-trip of strict JSON, and the only one
besides `json-source-map` that produces a single-line diff for a
single-field edit — *and unlike `json-source-map` it has a real
serializer with insert/remove semantics*, so it could plausibly handle
FR-005 (key insertion) without us writing comma-placement logic by
hand. The catch: the model API is upstream-marked unstable, and
`json-five` carries `sly` and `regex` as parser dependencies. Pinning
to a specific 1.1.x and vendoring would mitigate.

### 6.6 `jsonyx` 2.3.0 — LGPL-3.0

- License: **LGPL-3.0** (verified by reading
  https://raw.githubusercontent.com/nineteendo/jsonyx/main/LICENSE
  which begins "GNU LESSER GENERAL PUBLIC LICENSE / Version 3, 29 June
  2007"). The earlier survey claim of "GPL-3.0-or-later" was wrong.
- Format-preservation goal: **not stated**. Verified by reading
  https://github.com/nineteendo/jsonyx and
  https://jsonyx.readthedocs.io/en/stable/. The Key Features list is
  "JSON encoding, decoding and patching", "Pretty printing", "Optional
  JSON deviations support", "Detailed error messages". None mention
  preservation of any kind. The `Manipulator` class operates on parsed
  Python data, not on bytes.

**Experiment 1 (default `dumps`)**: emits flow style, no BOM, no CRLF,
key order preserved (Python dict insertion order). Loses everything
else.

**Experiment 1 (`dumps(indent=4)`)**: 4-space indent comes through;
everything else still normalized.

**Experiment 2 (single edit, `indent=4`)**. Same picture as stdlib —
**31 diff lines** because every line in the original was already
"wrong" relative to jsonyx's normalized output:

```diff
--- tricky.json
+++ jsonyx-edit
@@ -1,14 +1,14 @@
-﻿{
…
-}+{
+    "Manufacturer": "Siemens",
+    "MagneticFieldStrength": 3,
+    "RepetitionTime": 2.0,
+    "EchoTime": 0.04,
…
```

`apply_patch(data, [{"op": "set", "path": "$.EchoTime", "value": 0.04}])`
is a *semantic* patch — it mutates the parsed Python value — and is
followed by a normal `dumps`, so the result is identical to the
hand-written edit above.

**Verdict**: confirmed reject for our use case. License is fine (LGPL
with dynamic linking is OK for our distribution model), but the
library does not target byte preservation in any form. Original
survey's "GPL-3.0 reject" reasoning was wrong; the right reason to
reject is "wrong tool".

### 6.X Updated bottom line

The empirical sweep changes the recommendation. There is now exactly
**one library on PyPI that preserves all the BIDS-relevant formatting
quirks of a real-world strict-JSON sidecar byte-for-byte**: the
`json-five` model API. Specifically:

| Aspect | stdlib | json-source-map (splice) | ruamel rt | json-five model | jsonyx |
|---|---|---|---|---|---|
| BOM | lost | preserved (we keep source bytes) | lost | lost (need manual re-prefix) | lost |
| CRLF | lost | preserved | lost (LF + soft wraps, invalid JSON) | preserved | lost |
| 4-space indent | lost (forces 2) | preserved | lost | preserved | preserved (only with `indent=4`) |
| Mixed colon spacing | lost | preserved | lost | preserved | lost |
| Key order | preserved | preserved | preserved | preserved | preserved |
| No-trailing-newline | preserved (coincidence) | preserved | lost (adds `\n`) | preserved | lost |
| Single-edit diff lines | 30 | 7 | 20 (and invalid JSON) | 7 (with BOM re-prefix) | 31 |

`json-source-map` is still the right pick if we already plan to write
our own splice/insert logic — it is tinier, has no parser
dependencies, and gives explicit byte ranges. But for **single-field
edits in real BIDS sidecars** the `json-five` model API delivers the
same single-line diff *without* the splice-layer engineering, and
crucially it has an actual serializer that should generalize to key
insertion (FR-005) without us hand-coding comma placement.

**Revised recommendation:**

1. **Keep stdlib `json` + `FormattingProfile` as the new-file / freshly-
   constructed default path** (FR-006). All four candidates agree this
   is uncontroversial.
2. **Promote `json-five` (model API) from "reject" to "evaluate as the
   primary preservation backend for the read-modify-write path"** in a
   dedicated v2 spike. Drivers:
   - Empirical byte preservation of every formatting aspect except BOM
     (handled at the byte layer outside the library).
   - Single-line semantic diff for single-field edits — meets and
     exceeds SC-002.
   - Real serializer (unlike `json-source-map`), with insert/delete on
     the model graph, so FR-005 doesn't require us to write a
     comma-placement layer.
   - Apache-2.0, pure Python, last commit 2025-05-07 (more recently
     maintained than `json-source-map`).
   - The model API is upstream-marked unstable; mitigation is pinning
     to a specific 1.1.x and vendoring under
     `src/bids_utils/_vendor/json5/` if upstream churn manifests.
3. **Fall back to `json-source-map` only if the spike reveals model-API
   instability or the `sly` parser fails on edge cases** (unicode key
   variants, surrogate pairs, etc.). The splice path is then plan B
   with a smaller dep footprint.
4. **Drop `ruamel.yaml` from consideration entirely** — confirmed
   broken for JSON output (emits invalid JSON in `typ="rt"` and
   unquoted YAML 1.1 booleans in `typ="safe"`).
5. **Drop `jsonyx` from consideration on goal mismatch** (not on
   license — the license is LGPL-3.0, not GPL, and is acceptable; the
   library simply does not target byte preservation).

This revision is contingent on the model-API spike confirming that:
(a) load-mutate-dump preserves bytes for *all* of bids-examples'
sidecars, not just our synthetic tricky.json; (b) key insertion via the
model API yields a similarly minimal diff; (c) the `sly` parser does
not regress on Python 3.13/3.14. If any of those fail, fall back to
the original §4 recommendation (stdlib + FormattingProfile + maybe
json-source-map for surgical edits).

## 7. Corpus-scale empirical run (2026-04-27)

Reproducer at `round_trip_repro.sh` (this directory). Pinned inputs:
bids-examples SHA `dd54571267…` (matches the bids-utils submodule),
`json-five==1.1.2`, Python 3.12.13. Run on 2026-04-27.

### 7.1 Result

```
========================================================================
json-five 1.1.2 round-trip on bids-examples (FRESH ModelDumper per file)
========================================================================
  total scanned:                     2151
  byte-identical (no BOM in source): 2149
  byte-identical except stripped BOM:0
  differing:                         0
  parse/dump failed:                 2
========================================================================
```

**2,149 of 2,151 sidecars (99.91%) round-trip byte-identical** through
`json-five`'s model API. The 2 failures are **zero-byte empty files**
(`ieeg_epilepsy{NWB,}/derivatives/brainvisa/dataset_description.json`)
on which stdlib `json` would also error — not a preservation regression.
Zero files differed in non-trivial ways. None of the bids-examples
corpus uses a UTF-8 BOM (the BOM-only bucket is empty).

This decisively answers concern (a) in the §6.X contingency: `json-five`
preserves bytes across the *entire* real-world corpus we have, not just
the synthetic tricky fixture.

### 7.2 Critical upstream bug discovered

**`ModelDumper`'s output buffer persists across calls.** Reusing the
same `ModelDumper()` instance across multiple `dumps()` invocations
returns *the concatenation of all prior outputs plus the current one*.
First test pass with a single shared dumper produced 80,000-line diffs
on tiny 1–2 line input files because each output contained every
previously-dumped sidecar.

Workaround: instantiate `ModelLoader()` and `ModelDumper()` **fresh on
every call** (the script does this). This very likely explains why
upstream's `tests/test_roundtrip.py` is entirely commented out — the
disabled tests would have hit this bug.

This bug is a **strong reason to vendor `json-five` under
`src/bids_utils/_vendor/json5/`** if we adopt it: fixing it upstream
is straightforward (reset the buffer in `dumps`), but until that lands
we own the workaround and need it permanently in our wrapper.

### 7.3 Final recommendation (now decisive)

Adopt `json-five`'s model API as the **primary** preservation backend
for the read-modify-write path. Specifics for the implementation phase:

1. Wrap every `loads`/`dumps` call in our own thin helper that always
   constructs a fresh `ModelLoader`/`ModelDumper` (defensive against the
   stateful-dumper bug; documented internally).
2. Keep stdlib `json` for new-file writes and as the fallback for the 2
   pathological corpus files (empty content).
3. Pre-prepend the BOM at the byte layer when the source had one (the
   model API does not preserve BOM; trivial 3-byte prefix).
4. Pin to `json-five==1.1.2` initially. If upstream churn manifests
   (model API marked unstable), vendor under `src/bids_utils/_vendor/`.
5. File an upstream issue documenting the `ModelDumper` state bug and
   the commented-out `test_roundtrip.py` so we are not the only ones
   carrying the workaround.

The §6.X "contingent on a spike" recommendation now has its evidence:
99.91% byte-identity on the full corpus + a single, well-understood
upstream bug with a one-line workaround. `json-source-map` remains the
plan-B if upstream `json-five` becomes unmaintained.

### 7.4 Manipulation-API findings (2026-05-02)

A second category of upstream issues surfaced when probing whether the
model can be **edited** (not just round-tripped). Probe script:
`/tmp/json5-probe/probe.py`. Demonstrator:
`json_five_keys_manipulation_bug.py`. Results on `json-five 1.1.2`,
fixture `'{\n  "a": 1,\n  "b": 2,\n  "c": 3\n}\n'`:

| # | Operation | Result | Severity |
|---|-----------|--------|----------|
| 1 | `del obj.key_value_pairs[i]` | **silent NO-OP** | high (silent edit loss) |
| 2 | `obj.key_value_pairs[i] = kv` | **silent NO-OP** | high (silent edit loss) |
| 3 | `obj.key_value_pairs[:] = [...]` | **silent NO-OP** | high (silent edit loss) |
| 4 | `del obj.keys[i]` alone (forget values) | **CORRUPT output** — `c` mis-paired with stale value `2`, trailing newline stripped | high (silent corruption) |
| 5 | `del obj.keys[i]; del obj.values[i]` | PASS | — |
| 6 | `obj.keys.pop(i); obj.values.pop(i)` | PASS | — |
| 7 | `obj.values[i] = node` | PASS | — |
| 8 | `obj['k']`, `obj['k'] = …`, `del obj['k']` | TypeError | medium (loud absence) |
| 9 | `len(obj)`, `'k' in obj`, `list(obj)` | TypeError | medium (loud absence) |
| 10 | `kv.value = node` | AttributeError (NamedTuple) | medium (loud immutability) |

Root cause for 1–3: `JSONObject.key_value_pairs` is a read-only
`@property` (verified via descriptor inspection: `fset=None`, `fdel=None`)
that synthesises a fresh list on every access. Mutating that list mutates
a throw-away. The dumper later reads the canonical `keys`/`values`
lists, so all such mutations are invisible to it.

Root cause for 4: dumper does not assert
`len(obj.keys) == len(obj.values)` before serialising.

Implications for our adoption plan:

- **Mutation API contract.** Our wrapper must expose **only** the
  canonical-list path (`obj.keys` + `obj.values`, kept length-aligned)
  and forbid `obj.key_value_pairs` mutation in our internal code. A
  helper like `replace_value`, `delete_pair`, `append_pair`, `set_value`
  in `_format.py` will hide both footguns.
- **Defensive assert before dump.** The wrapper should
  `assert len(obj.keys) == len(obj.values)` immediately before each
  `dumps()` so an asymmetric edit fails loudly rather than silently
  corrupting output.
- **Single upstream issue covering all of the above.** Filed under
  `json_five_keys_manipulation_bug.py` (same dir). The issue suggests
  three remediations (mutable proxy / drop the property / implement
  `MutableMapping`) and asks the dumper to detect length mismatch.
- **No vendoring required for these footguns** — they are entirely
  surmountable in our wrapper. The `ModelDumper` state bug remains the
  reason vendoring is on the table; the manipulation footguns just add
  weight to the wrapper-must-exist conclusion.

---

Sources cross-referenced during this survey:

- [PyPI: json-source-map](https://pypi.org/project/json-source-map/)
- [GitHub: open-alchemy/json-source-map](https://github.com/open-alchemy/json-source-map)
- [PyPI: json-five](https://pypi.org/project/json-five/)
- [GitHub: spyoungtech/json-five](https://github.com/spyoungtech/json-five)
- [PyPI: ruamel.yaml](https://pypi.org/project/ruamel.yaml/)
- [PyPI: demjson3](https://pypi.org/project/demjson3/)
- [PyPI: jsonpatch](https://pypi.org/project/jsonpatch/)
- [GitHub: stefankoegl/python-json-patch](https://github.com/stefankoegl/python-json-patch)
- [GitHub: nineteendo/jsonyx](https://github.com/nineteendo/jsonyx) — license: **LGPL-3.0** per [`LICENSE`](https://raw.githubusercontent.com/nineteendo/jsonyx/main/LICENSE) (the survey's original "GPL-3.0-or-later" claim was wrong; corrected 2026-04-26). README/docs index do not list format preservation as a goal.
- [cpython issue 90948 — ruamel.yaml does not preserve indentation](https://github.com/python/cpython/issues/90948)
