"""Systematic probe of JSONObject manipulation operations in json-five 1.1.2.

For each operation we report:
  PASS    -- the operation behaved as a dict/list user would expect
  NO-OP   -- the operation silently did nothing (output unchanged)
  CORRUPT -- the operation produced malformed output (e.g. unbalanced keys/values)
  RAISE   -- the operation raised an exception (this is OK if the message is clear)
"""

from __future__ import annotations

import sys
import traceback

from json5.dumper import ModelDumper, dumps
from json5.loader import ModelLoader, loads
from json5.model import (
    DoubleQuotedString,
    Integer,
    KeyValuePair,
)

FIXTURE = '{\n  "a": 1,\n  "b": 2,\n  "c": 3\n}\n'


def fresh():
    """Return a freshly parsed model (avoids ModelDumper state bug)."""
    return loads(FIXTURE, loader=ModelLoader())


def render(model) -> str:
    return dumps(model, dumper=ModelDumper())


def banner(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def show(label: str, value) -> None:
    print(f"  {label}: {value!r}")


def run(name: str, fn) -> None:
    banner(name)
    try:
        fn()
    except Exception:
        print("  ! exception:")
        traceback.print_exc()


def case_01_del_key_value_pairs():
    """del obj.key_value_pairs[1] -- the natural dict-like syntax."""
    text = fresh()
    obj = text.value
    show("before", render(text))
    del obj.key_value_pairs[1]
    out = render(text)
    show("after ", out)
    show("verdict", "NO-OP" if "b" in out else "PASS")


def case_02_replace_key_value_pairs_index():
    """obj.key_value_pairs[1] = KeyValuePair(...) -- replace by index."""
    text = fresh()
    obj = text.value
    new_kv = KeyValuePair(
        key=DoubleQuotedString(characters="B", raw_value='"B"'),
        value=Integer(raw_value="22"),
    )
    show("before", render(text))
    try:
        obj.key_value_pairs[1] = new_kv
    except Exception as e:
        show("raised", repr(e))
        return
    out = render(text)
    show("after ", out)
    show("verdict", "PASS" if '"B"' in out and '"b"' not in out else "NO-OP")


def case_03_del_keys_and_values():
    """del obj.keys[1]; del obj.values[1] -- coordinated removal via canonical lists."""
    text = fresh()
    obj = text.value
    show("before", render(text))
    del obj.keys[1]
    del obj.values[1]
    out = render(text)
    show("after ", out)
    show("verdict", "PASS" if '"b"' not in out and '"a"' in out and '"c"' in out else "FAIL")


def case_04_asymmetric_del_keys_only():
    """del obj.keys[1] WITHOUT touching obj.values[1] -- corruption check."""
    text = fresh()
    obj = text.value
    show("before", render(text))
    del obj.keys[1]
    print(f"  keys length:   {len(obj.keys)}")
    print(f"  values length: {len(obj.values)}")
    try:
        out = render(text)
        show("after ", out)
        show("verdict", "CORRUPT (silent mismatch)")
    except Exception as e:
        show("raise on render", repr(e))
        show("verdict", "RAISE-on-render (asymmetric is a footgun but at least loud)")


def case_05_replace_value_via_values_index():
    """obj.values[1] = Integer(raw_value='99') -- replace value, keep key."""
    text = fresh()
    obj = text.value
    show("before", render(text))
    new_val = Integer(raw_value="99")
    new_val.wsc_before = list(obj.values[1].wsc_before)
    new_val.wsc_after = list(obj.values[1].wsc_after)
    obj.values[1] = new_val
    out = render(text)
    show("after ", out)
    show("verdict", "PASS" if "99" in out and '"b"' in out else "FAIL")


def case_06_dict_get_item():
    """obj['a'] -- dict-style lookup."""
    text = fresh()
    obj = text.value
    try:
        v = obj["a"]
        show("obj['a']", v)
        show("verdict", "PASS (dict-protocol implemented)")
    except Exception as e:
        show("raised", repr(e))
        show("verdict", "ABSENT (no __getitem__)")


def case_07_dict_set_item():
    """obj['d'] = Integer(...) -- dict-style assignment of a NEW key."""
    text = fresh()
    obj = text.value
    show("before", render(text))
    try:
        obj["d"] = Integer(raw_value="4")
    except Exception as e:
        show("raised", repr(e))
        show("verdict", "ABSENT (no __setitem__)")
        return
    out = render(text)
    show("after ", out)
    show("verdict", "PASS" if '"d"' in out and '4' in out else "NO-OP/CORRUPT")


def case_08_dict_del_item():
    """del obj['b'] -- dict-style deletion."""
    text = fresh()
    obj = text.value
    show("before", render(text))
    try:
        del obj["b"]
    except Exception as e:
        show("raised", repr(e))
        show("verdict", "ABSENT (no __delitem__)")
        return
    out = render(text)
    show("after ", out)
    show("verdict", "PASS" if '"b"' not in out else "NO-OP")


def case_09_len_contains_iter():
    """len(obj), 'a' in obj, list(obj) -- collection protocols."""
    text = fresh()
    obj = text.value
    for op_name, fn in [
        ("len(obj)", lambda: len(obj)),
        ("'a' in obj", lambda: "a" in obj),
        ("list(obj)", lambda: list(obj)),
    ]:
        try:
            show(op_name, fn())
        except Exception as e:
            show(op_name + " raised", repr(e))


def case_10_kv_value_assignment():
    """kv.value = Integer(...) -- KeyValuePair is a NamedTuple, so this MUST fail."""
    text = fresh()
    obj = text.value
    kv = obj.key_value_pairs[0]
    print(f"  type(kv): {type(kv).__name__}")
    print(f"  is NamedTuple: {hasattr(kv, '_fields')}")
    show("before", render(text))
    try:
        kv.value = Integer(raw_value="999")
    except Exception as e:
        show("raised", repr(e))
        show("verdict", "RAISE (NamedTuple immutable -- cannot mutate via kv)")
        return
    out = render(text)
    show("after ", out)
    show("verdict", "?? mutation appeared to succeed")


def case_11_slice_key_value_pairs():
    """obj.key_value_pairs[:] = [...] -- slice assignment."""
    text = fresh()
    obj = text.value
    show("before", render(text))
    try:
        obj.key_value_pairs[:] = [obj.key_value_pairs[0]]
    except Exception as e:
        show("raised", repr(e))
        show("verdict", "RAISE")
        return
    out = render(text)
    show("after ", out)
    show("verdict", "PASS" if '"b"' not in out and '"c"' not in out else "NO-OP")


def case_12_property_check():
    """Confirm key_value_pairs is a read-only @property -- the root cause."""
    cls = type(fresh().value)
    descriptor = cls.__dict__.get("key_value_pairs")
    print(f"  type(descriptor): {type(descriptor).__name__}")
    print(f"  fget: {descriptor.fget}")
    print(f"  fset: {descriptor.fset}")
    print(f"  fdel: {descriptor.fdel}")
    show("verdict", "read-only property" if descriptor.fset is None else "settable property")


def case_13_keys_values_canonical_pop():
    """Compare obj.keys.pop / obj.values.pop -- list.pop should work on canonical lists."""
    text = fresh()
    obj = text.value
    show("before", render(text))
    obj.keys.pop(1)
    obj.values.pop(1)
    out = render(text)
    show("after ", out)
    show("verdict", "PASS" if '"b"' not in out else "FAIL")


def main() -> int:
    cases = [
        ("01: del obj.key_value_pairs[i]                     (likely NO-OP)", case_01_del_key_value_pairs),
        ("02: obj.key_value_pairs[i] = new_kv                 (replace via property)", case_02_replace_key_value_pairs_index),
        ("03: del obj.keys[i]; del obj.values[i]              (coordinated)", case_03_del_keys_and_values),
        ("04: del obj.keys[i] alone                            (asymmetric)", case_04_asymmetric_del_keys_only),
        ("05: obj.values[i] = new_node                         (replace value)", case_05_replace_value_via_values_index),
        ("06: obj['a']                                         (dict get)", case_06_dict_get_item),
        ("07: obj['d'] = ...                                   (dict set NEW)", case_07_dict_set_item),
        ("08: del obj['b']                                     (dict del)", case_08_dict_del_item),
        ("09: len(obj), 'a' in obj, list(obj)                  (collection protocol)", case_09_len_contains_iter),
        ("10: kv.value = new_node                              (NamedTuple immutability)", case_10_kv_value_assignment),
        ("11: obj.key_value_pairs[:] = [...]                   (slice assign)", case_11_slice_key_value_pairs),
        ("12: descriptor inspection of key_value_pairs         (root-cause confirm)", case_12_property_check),
        ("13: obj.keys.pop / obj.values.pop                    (canonical list pop)", case_13_keys_values_canonical_pop),
    ]
    for name, fn in cases:
        run(name, fn)
    print()
    print("Probe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
