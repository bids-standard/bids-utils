# bids-utils integration tests

Integration tests in this directory operate over real `bids-examples`
datasets and (where available) the BIDS validator. They are organised
around a per-test **git-worktree fixture pattern** (FR-042) so each
test gets a clean, throwaway working copy without any in-place mutation
of the shared `bids-examples` submodule clone.

## Worktree fixture pattern

All FR-041 / SC-009 / SC-010 tests use the fixtures from
`_worktree_fixture.py`:

```python
def test_my_thing(bids_examples_worktree):
    ds = bids_examples_worktree("ds001")  # → Path to a fresh ds001 worktree
    # ... mutate ds freely; teardown is automatic
```

Two flavours are available:

| Fixture                            | Backing storage                          | Use it for                  |
| ---------------------------------- | ---------------------------------------- | --------------------------- |
| `bids_examples_worktree`           | `git worktree add --detach`              | Most file-touching tests    |
| `bids_examples_worktree_annexed`   | `shutil.copytree` + fresh `git annex init` | SC-008 / locked-symlink     |

The annexed variant is implemented as a fully standalone `git init` +
`git annex init` of the dataset (NOT a real `git worktree`) because
`git annex init` would otherwise write to the parent `bids-examples`
clone's `.git/annex/` and break the "host clone untouched" guarantee.
The fixture name keeps the `worktree` prefix for API symmetry.

### Rule: never `git worktree prune`

Per the project-wide CLAUDE.md global rule, this directory's helpers
**must not** call `git worktree prune` (or any `--expire=*` variant) —
sandboxed worktrees can appear absent from inside a sandbox even when
they exist on the host, and `prune` permanently deletes their
registration from the shared `.git/worktrees/`. The fixture only ever
calls `git worktree remove --force <path>` on paths it created itself
in the current test.

## Non-BIDS suffix injection (`_nonbids_inject.py`)

`inject_nonbids_suffixes(worktree_root, *, kinds, seed, count)` synthesizes
adversarial trailing segments into a deterministic, seeded selection of
data files within a worktree. This drives FR-041 / SC-009 coverage
without requiring a real heudiconv/DICOM toolchain in CI.

| `kind`       | Trailing segment | Origin                                 |
| ------------ | ---------------- | -------------------------------------- |
| `dup`        | `__dup-01`       | heudiconv duplicate-run output         |
| `plus_mine`  | `+mine`          | adversarial: forbidden punctuation     |
| `crap`       | `--crap`         | adversarial: arbitrary user scrawl     |
| `test`       | `_test`          | adversarial: stray non-BIDS suffix     |

For each kind, `count` primary files are picked from the worktree's
data-file pool, and a sibling with the injected suffix is created for
each (plus its sidecars, paired by exact stem). Each kind gets an
**independent seeded RNG** (`Random((seed, kind))`), so adding a new
kind does not perturb the file selection of existing kinds.

### Deterministic seed contract

For a fixed `(seed, kinds, count)` and a fixed worktree state (i.e. a
specific `bids-examples` HEAD), the set of selected source files is
stable across runs. Test authors can rely on the same `seed` choosing
the same files. If a future bids-examples bump rotates the candidate
list, seed-stability holds for fresh checkouts but diffs may appear
across the bump — that is expected.

## Validator helpers (`_validator.py`)

`assert_validator_flags(worktree_root, expected_files=...)` is the
SC-009 *pre*-condition: it confirms the synthetic injection actually
produced an invalid dataset (the validator notices the injected files).

`assert_validator_passes(worktree_root, ignore_pre_existing=...)` is
the SC-009 *post*-condition: after the operation under test, the
validator passes modulo a caller-supplied set of pre-existing issue
codes (so `bids-examples` datasets with prior known issues don't make
the test fail).

Both helpers `pytest.skip` gracefully when `bids-validator-deno` is not
installed.

## Running locally

```bash
# Full integration sweep (default tox env)
tox -e py3 -- tests/integration/

# Just the fixture self-tests
tox -e py3 -- tests/integration/test_worktree_fixture.py

# Skip integration tests entirely
tox -e py3 -- -m "not integration"
```

The fixtures degrade gracefully when their dependencies are missing:

* `bids-examples` submodule absent → all worktree-using tests skip.
* `git-annex` not installed → annexed-variant tests skip.
* `bids-validator-deno` not installed → validator-helper tests skip.
