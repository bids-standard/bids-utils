# Contract: Library API Surface

**Date**: 2026-04-03

## Public API (importable by users)

### `bids_utils.BIDSDataset`

```python
class BIDSDataset:
    root: Path
    bids_version: str

    @classmethod
    def from_path(cls, path: str | Path) -> BIDSDataset:
        """Find and load BIDS dataset from any path within it."""

    @property
    def vcs(self) -> VCSBackend:
        """Detected version control backend."""

    @property
    def schema(self) -> BIDSSchema:
        """Schema for this dataset's BIDS version."""
```

### `bids_utils.rename`

```python
def rename_file(
    dataset: BIDSDataset,
    path: str | Path,
    *,
    set_entities: dict[str, str] | None = None,
    new_suffix: str | None = None,
    dry_run: bool = False,
    include_sourcedata: bool = False,
) -> OperationResult:
    """Rename a BIDS file and all its sidecars."""
```

### `bids_utils.subject`

```python
def rename_subject(
    dataset: BIDSDataset,
    old: str,
    new: str,
    *,
    dry_run: bool = False,
    include_sourcedata: bool = False,
) -> OperationResult:
    """Rename a subject across the entire dataset."""

def remove_subject(
    dataset: BIDSDataset,
    subject: str,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> OperationResult:
    """Remove a subject from the dataset."""
```

### `bids_utils.session`

```python
def rename_session(
    dataset: BIDSDataset,
    old: str,
    new: str,
    *,
    subject: str | None = None,  # None = all subjects
    dry_run: bool = False,
) -> OperationResult:
    """Rename a session. old="" for move-into-session."""
```

### `bids_utils.migrate`

```python
def migrate_dataset(
    dataset: BIDSDataset,
    *,
    to_version: str | None = None,  # None = current released
    dry_run: bool = False,
) -> MigrationResult:
    """Apply schema-driven migrations."""
```

### `bids_utils.metadata`

```python
def aggregate_metadata(
    dataset: BIDSDataset,
    *,
    scope: str | Path | None = None,  # None = entire dataset
    mode: Literal["copy", "move"] = "move",
    dry_run: bool = False,
) -> OperationResult:
    """Hoist common metadata up the inheritance hierarchy."""

def segregate_metadata(
    dataset: BIDSDataset,
    *,
    scope: str | Path | None = None,
    dry_run: bool = False,
) -> OperationResult:
    """Push all metadata down to leaf-level sidecars."""

def audit_metadata(
    dataset: BIDSDataset,
) -> AuditResult:
    """Report metadata inconsistencies."""
```

### `bids_utils.merge`

```python
def merge_datasets(
    sources: list[str | Path],
    target: str | Path,
    *,
    into_sessions: list[str] | None = None,
    on_conflict: Literal["error", "add-runs"] = "error",
    dry_run: bool = False,
) -> OperationResult:
    """Merge multiple BIDS datasets."""
```

## CLI Contract

All commands follow this pattern:
- `--dry-run` / `-n`: Show what would change without modifying
- `--json`: Machine-readable JSON output
- `-v` / `-q`: Verbosity control
- `--force`: Skip confirmation on destructive operations
- `--include-sourcedata`: Extend operation to `sourcedata/` and `.heudiconv/`
- `--schema-version VERSION`: Override detected schema version

Exit codes:
- 0: Success
- 1: Error (unexpected failure)
- 2: Refused to act (would break validity, conflict detected)
