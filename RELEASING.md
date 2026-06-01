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

## Cutting v0.1.0 (initial release) — full runbook

The first release is intentionally manual because `auto` needs a baseline
tag (`v0.1.0`) to start counting PR labels from. After 0.1.0 the
label-driven workflow takes over.

### Step 0 — prerequisites (one-time, on the maintainer's machine)

```bash
# Ensure local build tooling is available
pip install --upgrade build twine

# Optional but recommended: install auto so you can dry-run locally
npm install -g auto    # or use the binary download path from release.yml

# Ensure your PyPI account has write access to the bids-utils project,
# OR that you have a project-scoped API token for it
```

### Step 1 — merge the release-pipeline branch

Merge the `enh-auto-release` PR (containing `.autorc`,
`.github/workflows/release.yml`, `CHANGELOG.md`, `RELEASING.md`,
CONTRIBUTING.md updates) into `main`. The first release CANNOT proceed
until this is on `main`, because `release.yml` and the `auto` config are
what wire everything together.

### Step 2 — create repo labels and the PyPI token (one-time, on GitHub side)

```bash
# Create the auto release labels (major, minor, patch, release, ...)
GH_TOKEN=$(git config hub.oauthtoken) intuit-auto create-labels
```

Then on the GitHub web UI:

1. Generate a project-scoped API token at
   <https://pypi.org/manage/account/token/> (scoped to `bids-utils`).
2. Add it as repo secret `PYPI_TOKEN` under
   *Settings → Secrets and variables → Actions*.

If you prefer OIDC-based publishing without a long-lived token, see
"Optional: PyPI Trusted Publishing" below — equivalent end-state, just a
different setup.

### Step 3 — cut the tag and publish

```bash
# 1. Make sure you're on main and clean
git checkout main
git pull --ff-only
git status   # must be clean

# 2. Run the full local test suite as a final gate
tox

# 3. Sanity-check what hatch-vcs will produce AT the tag
#    (without the tag, this shows a 0.1.devNN+gSHA dev version)
python -m build
ls dist/
rm -rf dist/   # discard the dev-version artifacts; we'll rebuild at the tag

# 4. Tag v0.1.0 and push the tag
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0

# 5. Build the release artifacts from the tagged commit
python -m build
ls dist/
# Expect: bids_utils-0.1.0-py3-none-any.whl  AND  bids_utils-0.1.0.tar.gz

# 6. (Optional but recommended) twine check before upload
twine check dist/*

# 7. Upload to PyPI
twine upload dist/*
#   When prompted:
#     Username: __token__
#     Password: <the project-scoped pypi token from Step 2>

# 8. Create the GitHub release with the CHANGELOG entry as the body
gh release create v0.1.0 --title "v0.1.0" \
    --notes "$(awk '/^# v0\.1\.0/,/^---$/' CHANGELOG.md | sed '$d')"
```

### Step 4 — sanity-check the release

```bash
# Verify the artifact is up on PyPI
pip index versions bids-utils

# Verify a fresh install works
python -m venv /tmp/bids-utils-smoke && \
    /tmp/bids-utils-smoke/bin/pip install bids-utils==0.1.0 && \
    /tmp/bids-utils-smoke/bin/bids-utils --help
```

### Step 5 — confirm the release.yml workflow is healthy

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
