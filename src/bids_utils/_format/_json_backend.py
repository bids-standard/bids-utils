"""JSON backend Protocol + concrete implementation.

This module is the **only** module in ``bids_utils`` that imports from
``json5``. The adapter-isolation invariant is enforced by the meta-test
``tests/test_format.py::test_only_json_backend_imports_json5``.

To swap backends: write a class implementing ``JSONBackend`` and update
``_format._json._default_backend``. No call site changes are required.

See ``.specify/specs/001-consistent-inout/research.md`` R1.1 for the
upstream-bug defenses required of any concrete implementation.
"""

from __future__ import annotations

# Implementation deferred to Phase 3 (US1). Phase 2 only locks the
# package layout in.
