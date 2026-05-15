#!/bin/sh
# Ephemeral reproducer: does json-five's model API round-trip every strict-JSON
# sidecar in bids-examples byte-for-byte (modulo UTF-8 BOM)?
#
# Why this exists:
#   - bids-utils spec 001-consistent-inout (FR-001..FR-013) wants format-preserving
#     JSON I/O. The empirical survey (library-survey.md §6) found json-five's
#     model API to be the only library on PyPI that round-trips strict JSON
#     byte-perfect on a synthetic tricky fixture.
#   - Upstream json-five has NO live test for mutation-preservation
#     (tests/test_roundtrip.py is fully commented out; README marks the model
#     API as unstable). Before committing the spec to this dependency we need
#     evidence that load->dump preserves bytes across a real-world corpus.
#
# Pattern: STAMPED ephemeral-shell-reproducer
#   https://stamped-principles.github.io/stamped-examples/examples/ephemeral-shell-reproducer/
#
# Requirements: uv, git, network access (clones bids-examples).
# Run:   sh round_trip_repro.sh
# Output: stdout — set -x trace plus a summary table at the end. No artefacts
#         outside the ephemeral mktemp dir.

set -eux
PS4='> '

cd "$(mktemp -d "${TMPDIR:-/tmp}/json5-roundtrip-XXXXXXX")"

# --- pin every input ---------------------------------------------------------
BIDS_EXAMPLES_SHA=dd545712672537c13ac684b95699b8f11fcedc89   # from bids-utils submodule
JSON_FIVE_VERSION=1.1.2                                       # latest as of 2026-04
PYTHON_VERSION=3.12

# --- fetch corpus ------------------------------------------------------------
git clone --filter=blob:none https://github.com/bids-standard/bids-examples.git
git -C bids-examples checkout "$BIDS_EXAMPLES_SHA"

# --- venv --------------------------------------------------------------------
uv venv --python "$PYTHON_VERSION" .venv
# shellcheck disable=SC1091
. .venv/bin/activate
uv pip install "json-five==$JSON_FIVE_VERSION"

# --- run round-trip ----------------------------------------------------------
# NB: PyPI distribution name is `json-five` but the import name is `json5`
# (collides with Dirk Pranke's separate `json5` package — only safe in an
# isolated venv with json-five and not json5 installed).
python - bids-examples <<'PY'
import difflib
import pathlib
import sys
from json5.loader import ModelLoader, loads
from json5.dumper import ModelDumper, dumps

# UPSTREAM BUG (json-five 1.1.2): ModelDumper's output buffer persists across
# calls — passing the same instance to dumps() twice concatenates outputs
# (file 1 + file 2 + ...). Workaround: instantiate ModelLoader() and
# ModelDumper() fresh inside the loop. This very likely explains why
# upstream's tests/test_roundtrip.py is fully commented out.

BOM = b"\xef\xbb\xbf"
root = pathlib.Path(sys.argv[1])

identical = bom_only = differing = failed = 0
worst: list[tuple[int, str, str]] = []  # (diff_lines, rel_path, sample)

for p in sorted(root.rglob("*.json")):
    raw = p.read_bytes()
    had_bom = raw.startswith(BOM)
    pre = raw[3:] if had_bom else raw
    try:
        model = loads(pre.decode("utf-8"), loader=ModelLoader())
        out = dumps(model, dumper=ModelDumper()).encode("utf-8")
    except Exception as exc:  # noqa: BLE001 — we want every failure
        failed += 1
        worst.append(
            (10**9, str(p.relative_to(root)),
             f"PARSE/DUMP ERROR: {type(exc).__name__}: {exc}")
        )
        continue

    if out == pre:
        if had_bom:
            bom_only += 1
        else:
            identical += 1
        continue

    differing += 1
    a = pre.decode("utf-8", errors="replace").splitlines(keepends=True)
    b = out.decode("utf-8", errors="replace").splitlines(keepends=True)
    n = sum(
        1
        for ln in difflib.unified_diff(a, b, n=0)
        if ln[:1] in "+-" and not ln.startswith(("+++", "---"))
    )
    sample = "".join(
        list(difflib.unified_diff(a, b, n=1, fromfile=p.name, tofile="round-trip"))[:8]
    )
    worst.append((n, str(p.relative_to(root)), sample))

bar = "=" * 72
total = identical + bom_only + differing + failed
print(bar)
print(f"json-five {ModelLoader.__module__.split('.')[0]} round-trip on bids-examples")
print(bar)
print(f"  total scanned:                     {total}")
print(f"  byte-identical (no BOM in source): {identical}")
print(f"  byte-identical except stripped BOM:{bom_only}")
print(f"  differing:                         {differing}")
print(f"  parse/dump failed:                 {failed}")
print(bar)

worst.sort(reverse=True)
print("Top 10 offenders (by changed-line count):")
for n, path, sample in worst[:10]:
    label = "PARSE/DUMP" if n == 10**9 else f"{n} +/- lines"
    print(f"\n--- {path}  ({label}) ---")
    print(sample)
PY

# --- Phase 2 + 3: edit-one-field and insert-new-field on a controlled fixture
python - <<'PY'
"""Phase 2: mutate one string field and verify only that line changes.
   Phase 3: insert a new field and verify indent is consistent with siblings.

A small synthesized fixture is used so the expected diff shape is exact —
unlike the corpus-scale Phase 1 we can assert byte-level outcomes here.
"""
import difflib
import re
from json5.dumper import ModelDumper, dumps
from json5.loader import ModelLoader, loads
from json5.model import DoubleQuotedString, Integer

FIXTURE = (
    "{\n"
    '  "TaskName": "rest",\n'
    '  "RepetitionTime": 2.0,\n'
    '  "IntendedFor": [\n'
    '    "func/sub-01_task-rest_bold.nii.gz"\n'
    "  ]\n"
    "}\n"
)


def diff(a: str, b: str) -> tuple[int, str]:
    a_lines, b_lines = a.splitlines(keepends=True), b.splitlines(keepends=True)
    udiff = list(
        difflib.unified_diff(a_lines, b_lines, fromfile="orig", tofile="after", n=1)
    )
    n = sum(
        1 for ln in udiff
        if ln[:1] in "+-" and not ln.startswith(("+++", "---"))
    )
    return n, "".join(udiff)


bar = "=" * 72
print(bar)
print("PHASE 2: mutate TaskName 'rest' -> 'movie'")
print(bar)
print("--- fixture ---")
print(FIXTURE, end="")

m = loads(FIXTURE, loader=ModelLoader())
m.value.values[0].raw_value = '"movie"'   # values[0] is the TaskName value node
out = dumps(m, dumper=ModelDumper())

print("--- after edit ---")
print(out, end="")
n, udiff = diff(FIXTURE, out)
print("--- unified diff ---")
print(udiff)
print(f"changed lines (+/-): {n} (expected 2 — one removed, one added)")

phase2_pass = (
    n == 2
    and out.count('"movie"') == 1
    and '"rest"' not in out
    # only the TaskName line differs; everything else byte-identical
    and out.split('\n')[2:] == FIXTURE.split('\n')[2:]
    and out.split('\n')[0] == FIXTURE.split('\n')[0]
)
print(f"PHASE 2: {'PASS' if phase2_pass else 'FAIL'}")

print()
print(bar)
print("PHASE 3: insert SamplingFrequency=2400 at end of object")
print(bar)
print("--- fixture ---")
print(FIXTURE, end="")

m = loads(FIXTURE, loader=ModelLoader())
obj = m.value
last_key = obj.keys[-1]
last_val = obj.values[-1]

new_key = DoubleQuotedString(
    characters="SamplingFrequency", raw_value='"SamplingFrequency"'
)
new_key.wsc_before = list(last_key.wsc_before)   # mirror sibling indent
new_key.wsc_after = []
new_val = Integer(raw_value="2400")
new_val.wsc_before = list(last_val.wsc_before)   # ' ' between ':' and value
new_val.wsc_after = last_val.wsc_after            # transfer trailing newline-before-}
last_val.wsc_after = []

# IMPORTANT: append to obj.keys / obj.values (the canonical lists).
# obj.key_value_pairs is a read-only PROPERTY; appending to it is a silent no-op.
obj.keys.append(new_key)
obj.values.append(new_val)

out = dumps(m, dumper=ModelDumper())
print("--- after insert ---")
print(out, end="")
n, udiff = diff(FIXTURE, out)
print("--- unified diff ---")
print(udiff)
print(f"changed lines (+/-): {n}")

# Check the new field's indent matches the sibling indent (2 spaces here)
new_line = next(line for line in out.splitlines() if "SamplingFrequency" in line)
indent_match = re.match(r"^(\s+)\"SamplingFrequency\"", new_line)
new_indent = indent_match.group(1) if indent_match else ""

sibling_line = next(line for line in FIXTURE.splitlines() if "TaskName" in line)
sibling_indent = re.match(r"^(\s+)\"TaskName\"", sibling_line).group(1)

print(f"sibling indent: {sibling_indent!r}")
print(f"new-field indent: {new_indent!r}")

phase3_pass = (
    new_indent == sibling_indent
    and "\"SamplingFrequency\": 2400" in out
    and out.endswith("\n}\n")
    # original list contents preserved
    and "func/sub-01_task-rest_bold.nii.gz" in out
    # only the comma-after-prev-last and the new line should differ
    and 1 <= n <= 3
)
print(f"PHASE 3: {'PASS' if phase3_pass else 'FAIL'}")

print()
print(bar)
print(f"OVERALL: {'ALL PASS' if phase2_pass and phase3_pass else 'FAILURES PRESENT'}")
print(bar)
PY
