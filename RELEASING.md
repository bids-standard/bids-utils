# Releasing bids-utils

This project uses [`intuit/auto`][auto] for label-driven releases on PyPI.

In normal operation **maintainers do not run any release command by hand** —
labels on merged PRs drive everything via `.github/workflows/release.yml`.
The exceptions are (a) the first release (`v0.1.0`) and (b) one-off manual
ships triggered through `workflow_dispatch`. Both are documented below.

## TL;DR — releasing a new version (0.1.1 onward)

1. On the PR you want to ship, apply **one bump label** (`major`, `minor`, or
   `patch`) **and** the `release` label.
2. Merge the PR to `main`.
3. The `release.yml` workflow runs `auto shipit
   --only-publish-with-release-label`, which:
   - computes the new version from the bump label,
   - prepends a new entry to `CHANGELOG.md`,
   - creates the git tag (`vX.Y.Z`) and the GitHub release,
   - runs `python -m build && twine upload dist/*` to publish to PyPI.
4. After the workflow succeeds, the merged PR is auto-commented with
   "Released on `vX.Y.Z`" and labelled `released`.

If multiple PRs are merged before a release fires, `auto` aggregates their
labels and bumps to the highest of (`major` > `minor` > `patch`).

## Manual ship via workflow_dispatch

Go to **Actions → Auto-release on PR merge → Run workflow** on GitHub.
This skips the `--only-publish-with-release-label` filter and releases
whatever's on `main` since the last tag. Useful for shipping a hot fix
where the bump label was forgotten.

---

### Step 5 (TODO) — confirm the release.yml workflow is healthy

After v0.1.0 is tagged, the next merge to `main` will trigger
`release.yml`. If that merged PR has no `release` label, the workflow
exits early (this is the `--only-publish-with-release-label` behaviour)
— this is the expected idle state and confirms the wiring is correct.

To force a no-op smoke test of the workflow, use **Actions → Auto-release
on PR merge → Run workflow → main**: it should report "no PRs found to
release" or similar, NOT a permission error.

If the workflow fails on the first auto-driven release attempt with
a 403/permission error from `github-actions[bot]`, see "Upgrading to
the protected-branch pattern" below.

---

## Upgrading to the protected-branch pattern

If branch protection on `main` rejects pushes from `github-actions[bot]`,
the auto-release will fail with a permission error. Switch from the
default-token flow to a bot-PAT flow:

1. Create a dedicated bot account (e.g. `bidsbot`) with `write` access to
   the repo.
2. Store its PAT as repo secret `PROTECTED_BRANCH_REVIEWER_TOKEN`.
3. Add `protected-branch` to the `plugins` list in `.autorc`.
4. Add `PROTECTED_BRANCH_REVIEWER_TOKEN: ${{ secrets.GH_TOKEN }}` to the
   `env:` block of the release job, and `${{ secrets.GH_TOKEN }}` as
   `GH_TOKEN` instead of `secrets.GITHUB_TOKEN`.

See [dandi-cli's setup][dandi-release] for a reference.

## Optional: PR label enforcement

If you want CI to refuse a PR that's missing a bump label, copy
[dandi-cli's `labels.yml`][dandi-labels] into `.github/workflows/`. This
adds an `actions/github-script` check that fails the PR unless one of
`[major, minor, patch, performance, internal, documentation, tests,
dependencies]` is applied.

## Optional: PyPI Trusted Publishing

For projects that prefer OIDC-based publishing over a long-lived PyPI
token:

1. On <https://pypi.org/manage/project/bids-utils/settings/publishing/>,
   register `bids-standard/bids-utils` with workflow `release.yml` as a
   Trusted Publisher.
2. Replace the `twine upload dist/*` portion of the `afterRelease` hook
   (or the equivalent step in `release.yml`) with the
   `pypa/gh-action-pypi-publish@release/v1` step.
3. Add `permissions: id-token: write` to the release job.
4. Drop the `PYPI_TOKEN` secret.

[auto]: https://intuit.github.io/auto/
[dandi-release]: https://github.com/dandi/dandi-cli/blob/master/.github/workflows/release.yml
[dandi-labels]: https://github.com/dandi/dandi-cli/blob/master/.github/workflows/labels.yml
