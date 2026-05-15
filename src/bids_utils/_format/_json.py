"""Format-preserving JSON document + parse/serialize entry points.

Does NOT import from ``json5``. The backend Protocol in
``_json_backend`` is the only place the json-five integration lives.
See ``.specify/specs/001-consistent-inout/contracts/io_contract.md``
Part A.
"""

from __future__ import annotations

# Implementation deferred to Phase 3 (US1).
