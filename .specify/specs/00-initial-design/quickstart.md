# Quickstart: bids-utils

**Branch**: `00-initial-design` | **Date**: 2026-04-03

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

### Rename a file

```bash
# Fix a task entity
bids-utils rename sub-01/func/sub-01_task-rest_bold.nii.gz --set task=nback

# Preview changes without modifying
bids-utils rename sub-01/func/sub-01_task-rest_bold.nii.gz --set task=nback --dry-run

# Machine-readable output
bids-utils rename sub-01/func/sub-01_task-rest_bold.nii.gz --set task=nback --json
```

### Migrate a dataset

```bash
# Apply all 1.x deprecation fixes (default: current released version)
bids-utils migrate

# Migrate to a specific version
bids-utils migrate --to 1.9.0

# Migrate toward BIDS 2.0
bids-utils migrate --to 2.0

# Preview migration plan
bids-utils migrate --dry-run
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
from bids_utils.migrate import migrate_dataset
from bids_utils.metadata import aggregate_metadata

# Load a dataset
dataset = BIDSDataset.from_path("path/to/dataset")

# Rename a file
result = rename_file(
    dataset,
    path="sub-01/func/sub-01_task-rest_bold.nii.gz",
    set_entities={"task": "nback"},
    dry_run=True,
)
for change in result.changes:
    print(f"{change.action}: {change.source} → {change.target}")

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
