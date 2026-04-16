#!/bin/bash
# Code duplication detection (Constitution XI: DRY).
# Run via: tox -e duplication
# Requires: npx (Node.js) for jscpd, pylint for AST-aware detection

set -eu

echo "=== pylint duplicate-code check ==="
pylint --disable=all --enable=duplicate-code src/bids_utils/

echo
echo "=== jscpd token-based duplication check ==="
if command -v npx >/dev/null 2>&1; then
    # jscpd reads .jscpd.json for config (threshold, ignores, etc.)
    npx --yes jscpd@latest src/ tests/
else
    echo "WARNING: npx not found — skipping jscpd check. Install Node.js for full duplication detection."
fi
