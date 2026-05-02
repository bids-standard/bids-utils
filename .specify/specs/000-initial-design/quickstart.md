# Quickstart: bids-utils

**Branch**: `000-initial-design` | **Date**: 2026-04-03

## Installation

```bash
# Install from PyPI (once published)
pip install bids-utils

# Install for development
git clone https://github.com/bids-standard/bids-utils.git
cd bids-utils
uv venv && source .venv/bin/activate
uv pip install -e ".[devel]"

# Run tests
tox
```

## CLI Usage

### Rename a file (mv-like)

`bids-utils rename SRC DST` is pure path-rename — primary file plus
sidecars plus `_scans.tsv` updates. Sidecars are matched by **full literal
stem**, so heudiconv-style non-BIDS source filenames (`..._bold__dup-01.*`)
are handled correctly.

```bash
# Same-directory rename (e.g., dropping a non-BIDS __dup-01 segment)
bids-utils rename \
  sub-qa64/ses-20220217/func/sub-qa64_ses-20220217_task-rest_acq-p2_bold__dup-01.nii.gz \
  sub-qa64/ses-20220217/func/sub-qa64_ses-20220217_task-rest_acq-p2_run-02_bold.nii.gz

# Cross-container move (sub- and ses- entity labels in the destination
# filename are rewritten automatically to match the destination path)
bids-utils rename \
  sub-01/ses-pre/func/sub-01_ses-pre_task-rest_bold.nii.gz \
  sub-02/ses-post/func/

# Preview without modifying
bids-utils rename SRC DST --dry-run

# Machine-readable output
bids-utils rename SRC DST --json
```

### Edit entity values in place (`edit-filename`)

For changing entity values (`task`, `run`, `acq`, etc.) without moving the
file to another folder, use `edit-filename`. This is the canonical home for what was
`rename --set ...` in earlier drafts.

```bash
# Change the task entity potentially in multiple (runs, nii.gz and json etc) files
bids-utils edit-filename sub-01/func/sub-01_task-rest_*bold.* --set task=nback

# Multiple edits in one call (entities are emitted in schema-defined order
# regardless of the order you list them) and across subjects
bids-utils edit-filename sub-*/func/sub-*-rest_bold.nii.gz \
  --set run=99 --set acq=p2

# Delete an entity
bids-utils edit-filename sub-01/func/sub-01_task-rest_acq-p2_bold.* --delete acq

# Replace the suffix
bids-utils edit-filename sub-*/func/sub-*_task-rest_bold.* --set-suffix cbv

# Preview / JSON output work the same as `rename`
bids-utils edit-filename SRC --set task=nback --dry-run
bids-utils edit-filename SRC --set task=nback --json
```

### Migrate a dataset

```bash
# Apply safe 1.x deprecation fixes (default: --level=safe)
bids-utils migrate

# Include advisory fixes (field removals, HIPAA age capping)
bids-utils migrate --level=advisory

# Apply only a specific rule
bids-utils migrate --level=advisory --rule-id=age_cap_89

# Interactive mode: prompt for each advisory/ambiguous finding
bids-utils migrate --level=all --mode=interactive

# Migrate to a specific version
bids-utils migrate --to 1.9.0

# Migrate toward BIDS 2.0 (participants.tsv → subjects.tsv, etc.)
bids-utils migrate --to 2.0

# Preview migration plan
bids-utils migrate --dry-run

# Audit: check for schema deprecations missing migration rules
bids-utils migrate --audit
```

### Rename a subject

```bash
bids-utils subject-rename sub-01 sub-99
bids-utils subject-rename sub-01 sub-99 --include-sourcedata
```

### Rename a session

```bash
bids-utils session-rename ses-pre ses-baseline
# Move into sessions (dataset without sessions → add ses-01)
bids-utils session-rename '' ses-01
```

### Metadata operations

```bash
# Hoist common metadata up the hierarchy
bids-utils metadata aggregate

# Push metadata down to leaf level
bids-utils metadata segregate

# Find inconsistent metadata
bids-utils metadata audit

# Scope to a single subject
bids-utils metadata aggregate sub-01/
```

## Library Usage

```python
from bids_utils import BIDSDataset
from bids_utils.rename import rename_file
from bids_utils.edit_filename import edit_filename
from bids_utils.migrate import migrate_dataset
from bids_utils.metadata import aggregate_metadata

# Load a dataset
dataset = BIDSDataset.from_path("path/to/dataset")

# Rename a file (mv-like — primary + sidecars + _scans.tsv)
result = rename_file(
    dataset,
    src_path="sub-qa64/ses-20220217/func/sub-qa64_ses-20220217_task-rest_acq-p2_bold__dup-01.nii.gz",
    dst_path="sub-qa64/ses-20220217/func/sub-qa64_ses-20220217_task-rest_acq-p2_run-02_bold.nii.gz",
    dry_run=True,
)
for change in result.changes:
    print(f"{change.action}: {change.source} → {change.target}")

# Edit entity values in place (replaces the old rename --set ...)
result = edit_filename(
    dataset,
    path="sub-01/func/sub-01_task-rest_bold.nii.gz",
    set_entities={"task": "nback", "run": "99"},
    dry_run=True,
)

# Migrate
result = migrate_dataset(dataset, to_version="1.9.0", dry_run=True)
for finding in result.findings:
    print(f"{finding.file}: {finding.rule.description}")

# Aggregate metadata
result = aggregate_metadata(dataset, mode="move", dry_run=True)
```

## Development

```bash
# Run all tests
tox

# Run specific test environment
tox -e py312

# Run linting
tox -e lint

# Run type checking
tox -e type

# Run a specific test
tox -e py312 -- tests/test_rename.py -k "test_rename_with_sidecar"
```
