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

## Pull Requests and Release Labels

Releases on this project are driven by [intuit/auto][auto] — version bumps
and PyPI uploads happen automatically when a PR is merged to `main`, based
on the labels applied to that PR. **Picking the right labels is part of
the review process.**

### Bump labels (pick exactly one when you intend a release)

| Label | Effect | Use for |
| --- | --- | --- |
| `major` | bumps `X.0.0` | Breaking changes to the CLI surface or library API |
| `minor` | bumps `0.X.0` | New features, new commands, backwards-compatible additions |
| `patch` | bumps `0.0.X` | Bug fixes, performance, internal refactors, docs that ship in a release |

### Other labels

| Label | Effect | Use for |
| --- | --- | --- |
| `release` | Required alongside `major`/`minor`/`patch` to actually publish on merge. Without it the workflow exits early. | The PR that should trigger a release |
| `internal` | No version bump (counted as "skip-release") | Test-only changes, CI tweaks, refactors that don't need a release |
| `documentation` | No version bump | Docs-only PRs (mkdocs / README / CHANGELOG fixups) |
| `tests` | No version bump | Pure test additions |
| `dependencies` | No version bump | Routine dep bumps (e.g. Dependabot) |
| `performance` | No version bump on its own — combine with a bump label if a perf change should ship | Performance-only changes |
| `released` | Applied automatically by `auto` after the release ships | (do not apply manually) |

If multiple PRs are merged before a release fires, `auto` aggregates their
labels and bumps to the highest of (`major` > `minor` > `patch`).

### What the maintainer does

1. Apply the appropriate bump label and (if you want to release on merge)
   the `release` label.
2. Merge to `main`.
3. The `release.yml` workflow runs `auto shipit`, which builds the
   changelog entry, tags the release, creates the GitHub release, and
   uploads to PyPI. No manual steps.

See [RELEASING.md](RELEASING.md) for the full release procedure, including
the manual v0.1.0 cutover and one-time repo-settings tasks.

[auto]: https://intuit.github.io/auto/
