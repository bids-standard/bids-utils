"""
Title: JSONObject manipulation API silently no-ops or corrupts the model

Severity: high (silent data corruption / silent edit loss)
Affects:  json-five 1.1.2 (PyPI), json5.model.JSONObject

Summary
-------

When using the model API (`json5.loader.ModelLoader` + `json5.dumper.ModelDumper`)
to round-trip JSON5 with structural edits, three closely related dict-mutation
patterns fail in surprising ways:

  1. `del obj.key_value_pairs[i]`           -> SILENT NO-OP
  2. `obj.key_value_pairs[i] = new_kv`      -> SILENT NO-OP
  3. `obj.key_value_pairs[:] = [...]`       -> SILENT NO-OP

Root cause: `JSONObject.key_value_pairs` is a read-only `@property` that
synthesises a fresh `list` on every access from the canonical `obj.keys` and
`obj.values` lists. Mutating that list mutates a throw-away object, never the
model. There is no setter or deleter on the property. The natural dict-like
syntax compiles, runs, returns `None`, and lies.

Adjacent footgun: the canonical `obj.keys` / `obj.values` lists ARE mutable,
but the dumper does not validate that they remain length-aligned. Deleting from
one without the other produces malformed output:

  4. `del obj.keys[i]` (without `del obj.values[i]`) -> CORRUPT OUTPUT
     keys mis-pair with stale values, trailing newlines/whitespace can be lost.

Adjacent absence: the dict / collection protocols are not implemented on
`JSONObject` at all, so users who reach for the natural syntax get loud
TypeErrors:

  5. `obj['k']`        -> TypeError: 'JSONObject' object is not subscriptable
  6. `obj['k'] = ...`  -> TypeError: ... does not support item assignment
  7. `del obj['k']`    -> TypeError: ... does not support item deletion
  8. `len(obj)`        -> TypeError: object of type 'JSONObject' has no len()
  9. `'k' in obj`      -> TypeError: argument of type 'JSONObject' is not iterable
  10. `list(obj)`      -> TypeError: 'JSONObject' object is not iterable

Adjacent: `KeyValuePair` is a `NamedTuple`, so `kv.value = new_node` raises
`AttributeError: can't set attribute`. (This one is loud, so it is fine,
but it makes the only path a user can find -- `obj.key_value_pairs[i].value
= ...` -- a dead end on top of the silent no-op above.)

Repro
-----

Save this file and run:

    pip install json-five==1.1.2
    python json_five_keys_manipulation_bug.py

Expected (if the bug is fixed): exit 0 and a `b`-removed object.
Actual today: exit 1, the second print shows the unchanged input.

Suggested fix (sketch)
----------------------

Either:

(a) Make `key_value_pairs` a real mutable view that proxies through to
    `obj.keys` / `obj.values` (implement `__delitem__`, `__setitem__`,
    `__setslice__` / slice `__setitem__` on the proxy).

(b) Drop the `key_value_pairs` property and expose only the canonical
    `keys` / `values` lists, documented as the only correct mutation path,
    and make the dumper raise on length mismatch instead of silently
    emitting malformed JSON.

(c) Implement `MutableMapping` on `JSONObject` so the natural dict-like
    syntax works and stays consistent. This subsumes (a) and (b) for the
    common case and is what users reach for first.

Whichever route, the dumper should detect `len(obj.keys) != len(obj.values)`
and raise rather than emit corrupt output.
"""

from __future__ import annotations

import sys

from json5.dumper import ModelDumper, dumps
from json5.loader import ModelLoader, loads

FIXTURE = '{\n  "a": 1,\n  "b": 2,\n  "c": 3\n}\n'


def main() -> int:
    text = loads(FIXTURE, loader=ModelLoader())
    obj = text.value

    # The natural dict-like syntax. Returns None. Does nothing.
    del obj.key_value_pairs[1]

    out = dumps(text, dumper=ModelDumper())

    print(f"input  : {FIXTURE!r}")
    print(f"output : {out!r}")

    if '"b"' in out:
        print("BUG PRESENT: del on key_value_pairs was a silent no-op", file=sys.stderr)
        return 1
    print("Bug fixed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
