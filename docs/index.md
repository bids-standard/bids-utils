# bids-utils

CLI and Python library for manipulating BIDS datasets.

## Features

- **Rename** files with automatic sidecar and `_scans.tsv` updates
- **Migrate** datasets across BIDS versions (1.x deprecations and 2.0)
- **Subject/session rename** across entire datasets
- **Metadata aggregate/segregate** using BIDS inheritance
- **Merge/split** datasets with conflict handling
- **VCS-aware**: uses `git mv` when under version control

## Quick Start

```bash
pip install bids-utils

# Rename a file
bids-utils rename sub-01/func/sub-01_task-rest_bold.nii.gz --set task=nback

# Migrate deprecations
bids-utils migrate --dry-run
```
