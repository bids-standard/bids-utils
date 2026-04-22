# bids-utils

[![CI](https://github.com/bids-standard/bids-utils/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/bids-standard/bids-utils/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Typed: mypy](https://img.shields.io/badge/typed-mypy-1f5082.svg)](https://mypy.readthedocs.io/)

A CLI and Python library for manipulating BIDS datasets: rename files,
subjects, sessions, and runs; migrate datasets between BIDS versions;
aggregate, segregate, and audit metadata; merge and split datasets.
Schema-driven throughout (via [`bidsschematools`][bst]) and aware of
version control, including git-annex and DataLad datasets.

> ⚠️ **Status**: early development. APIs, CLI commands, and behaviors
> may change before the first tagged release.


## What it does

- **File / subject / session / run renaming** with sidecar, `_scans.tsv`,
  and `participants.tsv` updates, plus BIDS URI fix-up.
- **Schema-driven migration** between BIDS versions, including 1.x
  deprecation fixes and 2.0 structural changes. Tiered rule levels
  (`safe` / `advisory` / `non-auto-fixable`).
- **Metadata management** — aggregate, segregate, and audit inheritance
  chains across sidecar JSONs.
- **Dataset-level operations** — `merge`, `split`, `remove`.
- **VCS-aware** — git, git-annex, and DataLad backends; annexed content
  is fetched / unlocked / re-added as needed (`--annexed=get`).


## Install

```bash
# one-shot (isolated) invocation
uvx bids-utils --help

# inside a project env
uv pip install bids-utils     # or: pip install bids-utils
```

## Commands

```console
$ bids-utils --help
Usage: bids-utils [OPTIONS] COMMAND [ARGS]...

  CLI for manipulating BIDS datasets.

Options:
  --version                       Show the version and exit.
  --annexed [error|get|skip-warning|skip]
                                  How to handle git-annex files without local
                                  content.
  -h, --help                      Show this message and exit.

Commands:
  completion      Output shell completion activation script.
  merge           Merge multiple BIDS datasets.
  metadata        Metadata manipulation commands.
  migrate         Apply schema-driven migrations to resolve deprecations.
  remove          Remove a subject from the dataset.
  remove-run      Remove a run and optionally reindex subsequent runs.
  rename          Rename a BIDS file and all its sidecars.
  session-rename  Rename a session.
  split           Extract a subset of a BIDS dataset.
  subject-rename  Rename a subject across the entire dataset.
```

Run `bids-utils <COMMAND> --help` for per-command options.

## Quick tour

```bash
# Rename a BOLD file; sidecars and _scans.tsv follow automatically.
bids-utils rename path/to/sub-01_task-rest_bold.nii.gz --set task=nback

# Migrate an older 1.x dataset to the current 1.x release.
bids-utils migrate /data/ds001 --dry-run

# Rename a subject across the whole dataset (VCS-aware).
bids-utils subject-rename /data/ds001 --from 01 --to 99
```

The same operations are available as a Python library:

```python
from bids_utils import BIDSDataset
from bids_utils.subject import rename_subject

ds = BIDSDataset.from_path("/data/ds001")
rename_subject(ds, old="01", new="99")
```

## Shell completion

`bids-utils completion` emits an activation script for the detected
shell (bash, zsh, or fish) with BIDS-aware suggestions for `sub-*`,
`ses-*`, and entity keys from the schema.

```bash
# Enable for the current shell (one-shot):
eval "$(bids-utils completion)"

# Persist it: append to your shell rc file.
echo 'eval "$(bids-utils completion)"' >> ~/.bashrc   # or ~/.zshrc
```

For fish:

```fish
bids-utils completion fish | source
```

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for tooling conventions, the
pre-commit `tox` gate, and where to find the design documents under
`.specify/specs/`. Integration tests use the [`bids-examples`][bex]
submodule — run `git submodule update --init --recursive` after
cloning.

## License

Apache License 2.0.

[bst]: https://github.com/bids-standard/bids-specification
[bex]: https://github.com/bids-standard/bids-examples


<!-- Bounty fix for #11 -->
