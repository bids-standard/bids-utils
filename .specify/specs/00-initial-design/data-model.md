# Data Model: bids-utils

**Branch**: `00-initial-design` | **Date**: 2026-04-03

## Core Types

### BIDSDataset

Represents a BIDS dataset rooted at a `dataset_description.json` file.

```python
@dataclass
class BIDSDataset:
    root: Path                    # Directory containing dataset_description.json
    bids_version: str             # From dataset_description.json BIDSVersion field
    schema_version: str | None    # Explicit override or None (use bids_version)
    vcs: VCSBackend               # Detected VCS (NoVCS, Git, GitAnnex, DataLad)
```

**Discovery**: `BIDSDataset.from_path(path)` walks up from any path to find `dataset_description.json`.

### Entity

A BIDS key-value pair as it appears in filenames and directory names.

```python
@dataclass(frozen=True)
class Entity:
    key: str    # e.g., "sub", "ses", "task", "run", "acq", "part"
    value: str  # e.g., "01", "pre", "rest", "02"
```

### BIDSPath

A parsed BIDS file path, decomposed into its constituent entities, suffix, and extension.

```python
@dataclass
class BIDSPath:
    entities: dict[str, str]  # Ordered dict: {"sub": "01", "ses": "pre", "task": "rest"}
    suffix: str               # e.g., "bold", "T1w", "events"
    extension: str            # e.g., ".nii.gz", ".json", ".tsv"
    datatype: str             # e.g., "func", "anat", "fmap" (from directory)

    @classmethod
    def from_path(cls, path: Path, schema: Schema) -> BIDSPath: ...

    def to_filename(self) -> str: ...
    def to_relative_path(self) -> Path: ...  # Includes sub-/ses-/datatype/ dirs

    def with_entities(self, **overrides: str) -> BIDSPath: ...
    def with_suffix(self, suffix: str) -> BIDSPath: ...
    def with_extension(self, extension: str) -> BIDSPath: ...
```

### VCSBackend

Abstract interface for version control operations.

```python
class VCSBackend(Protocol):
    name: str  # "none", "git", "git-annex", "datalad"

    def move(self, src: Path, dst: Path) -> None: ...
    def remove(self, path: Path) -> None: ...
    def is_dirty(self) -> bool: ...
    def commit(self, message: str, paths: list[Path]) -> None: ...

class NoVCS: ...      # Direct filesystem operations
class Git: ...        # git mv, git rm, git commit
class GitAnnex: ...   # git annex commands + git operations
class DataLad: ...    # datalad run semantics
```

**Detection order**: DataLad → GitAnnex → Git → NoVCS (most specific first).

### OperationResult

Every mutating operation returns a structured result.

```python
@dataclass
class OperationResult:
    success: bool
    dry_run: bool
    changes: list[Change]
    warnings: list[str]
    errors: list[str]

@dataclass
class Change:
    action: Literal["rename", "delete", "create", "modify"]
    source: Path
    target: Path | None  # None for delete/modify
    detail: str          # Human-readable description
```

## Schema Access

Wraps `bidsschematools` to provide typed, convenient access:

```python
class BIDSSchema:
    """Cached, version-aware schema accessor."""

    @classmethod
    def load(cls, version: str | None = None) -> BIDSSchema: ...

    def entity_order(self) -> list[str]: ...
    def sidecar_extensions(self, suffix: str) -> list[str]: ...
    def is_valid_entity(self, key: str, value: str, datatype: str) -> bool: ...
    def deprecation_rules(self, from_version: str, to_version: str) -> list[DeprecationRule]: ...
    def metadata_field_info(self, field: str) -> MetadataFieldInfo | None: ...
```

## File Operations Model

### Sidecar Discovery

Given a primary file, find all associated sidecars:

```
Input:  sub-01/func/sub-01_task-rest_bold.nii.gz
Output: [
    sub-01/func/sub-01_task-rest_bold.json,
    sub-01/func/sub-01_task-rest_bold.bvec,  # if exists
    sub-01/func/sub-01_task-rest_bold.bval,  # if exists
]
```

Extensions to check come from the schema (for the given suffix).

### Scans File Model

```
_scans.tsv format:
filename                                    acq_time
func/sub-01_task-rest_bold.nii.gz          2020-01-01T12:00:00
anat/sub-01_T1w.nii.gz                    2020-01-01T11:00:00
```

- Paths in `_scans.tsv` are relative to the subject (or session) directory
- When a file is renamed, the corresponding row must be updated
- When a file is removed, the corresponding row must be removed

### Inheritance Chain

For metadata operations, the inheritance chain for a file is:

```
dataset_root/bold.json                    # Level 0: dataset root
dataset_root/task-rest_bold.json          # Level 0: task-specific
dataset_root/sub-01/bold.json             # Level 1: subject
dataset_root/sub-01/sub-01_bold.json      # Level 1: subject (entity-prefixed)
dataset_root/sub-01/ses-pre/bold.json     # Level 2: session
dataset_root/sub-01/ses-pre/func/bold.json                    # Level 3: datatype
dataset_root/sub-01/ses-pre/func/sub-01_ses-pre_task-rest_bold.json  # Level 3: leaf
```

Resolved metadata = merge all levels, leaf overrides higher levels.

## Migration Model

```python
@dataclass
class MigrationRule:
    """A single schema-derived migration rule."""
    id: str                        # Rule identifier from schema
    from_version: str              # First version where this is deprecated
    category: Literal["field_rename", "value_rename", "suffix_rename",
                       "path_format", "cross_file_move"]
    description: str               # Human-readable

    # Category-specific fields
    old_field: str | None          # For field_rename
    new_field: str | None
    old_value: str | None          # For value_rename
    new_value: str | None
    affected_suffixes: list[str]   # Which file types this applies to

@dataclass
class MigrationPlan:
    """Complete plan for migrating a dataset."""
    dataset: BIDSDataset
    from_version: str
    to_version: str
    rules: list[MigrationRule]     # Ordered by version, then priority
    findings: list[MigrationFinding]  # What was found in the actual dataset

@dataclass
class MigrationFinding:
    """A specific instance where a rule matches a file."""
    rule: MigrationRule
    file: Path
    current_value: Any
    proposed_value: Any
    can_auto_fix: bool             # False if human judgment needed
    reason: str | None             # Why it can't be auto-fixed (if applicable)

@dataclass
class MigrationResult:
    """Result of migrate_dataset(), extends MigrationPlan with outcome."""
    plan: MigrationPlan
    success: bool
    dry_run: bool
    applied: list[MigrationFinding]   # Findings that were auto-fixed
    skipped: list[MigrationFinding]   # Findings requiring human judgment
    errors: list[str]
```
