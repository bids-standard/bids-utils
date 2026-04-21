# bids-utils — Project Instructions

## Pre-Commit Gate: tox Must Pass

**MANDATORY**: Before committing ANY code changes, run `tox` and verify ALL
environments pass. Never auto-commit if `tox` fails.

```bash
# Run full tox suite
tox

# Or run individual envs to iterate faster
tox -e py312        # tests
tox -e lint         # ruff
tox -e type         # mypy
tox -e duplication  # pylint duplicate-code
```

If any environment fails:
1. Fix the issue
2. Re-run the failing environment to confirm the fix
3. Run the full `tox` suite once more
4. Only then commit

## Project Layout

- `src/bids_utils/` — library code (private modules prefixed with `_`)
- `src/bids_utils/cli/` — CLI commands (thin wrappers over library)
- `tests/` — pytest test suite
- `tests/integration/` — integration tests requiring bids-examples

## Testing

- `pytest` orchestrated by `tox` with `tox-uv`
- `bids-examples` is a git submodule used for integration tests
- AI-generated tests must be marked `@pytest.mark.ai_generated`

## Dependencies

- `bidsschematools` — BIDS schema access (core dep)
- `click` — CLI framework (core dep)
- `packaging` — version comparison for migration (core dep)
- All version specs live in `pyproject.toml` (single source of truth)
