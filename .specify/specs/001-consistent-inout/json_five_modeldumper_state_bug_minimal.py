#!/usr/bin/env python3
"""Minimal demonstrator: ModelDumper output buffer persists across calls.

Reusing a single ``ModelDumper`` instance across two ``dumps()`` calls
returns the **concatenation** of both inputs on the second call. This
makes the model API unusable for any program that processes more than
one document, and likely explains why ``tests/test_roundtrip.py`` is
fully commented out upstream.

Reproduce
---------

    python3 -m venv /tmp/json5bug && . /tmp/json5bug/bin/activate
    pip install json-five==1.1.2
    python json_five_modeldumper_state_bug.py

Expected output
---------------

    first  dumps -> '{"a": 1}'
    second dumps -> '{"b": 2}'

Actual output (json-five 1.1.2)
-------------------------------

    first  dumps -> '{"a": 1}'
    second dumps -> '{"a": 1}{"b": 2}'

Workaround
----------

Construct a fresh ``ModelDumper()`` for every ``dumps()`` call.

Suggested fix
-------------

Reset the internal output buffer at the start of ``ModelDumper.dumps()``
(or pass a fresh buffer per call inside the function) so that consecutive
calls do not accumulate state.

Environment
-----------

- json-five==1.1.2  (PyPI distribution; import name ``json5``)
- Python 3.12.13 on Linux x86_64
- Discovered while round-tripping 2,151 sidecars from the bids-examples
  corpus; the shared dumper produced 80,000-line outputs for 1-line inputs
  because each output included every previously-dumped sidecar.
"""

from json5.dumper import ModelDumper, dumps
from json5.loader import ModelLoader, loads


dumper = ModelDumper()  # SINGLE instance, reused below

a = loads('{"a": 1}', loader=ModelLoader())
b = loads('{"b": 2}', loader=ModelLoader())

out_a = dumps(a, dumper=dumper)
out_b = dumps(b, dumper=dumper)

print(f"first  dumps -> {out_a!r}")
print(f"second dumps -> {out_b!r}")
