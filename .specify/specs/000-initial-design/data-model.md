# Data Model: bids-utils

**Branch**: `000-initial-design` | **Date**: 2026-04-03

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
    trailing: str = ""        # Non-BIDS trailing segment preserved verbatim
                              # (e.g., "__dup-01" from heudiconv). Empty for valid BIDS.

    @classmethod
    def from_path(cls, path: Path, schema: Schema) -> BIDSPath: ...
    # Robust to non-BIDS filenames (FR-038): captures unrecognized trailing
    # segments after the suffix in `trailing` rather than failing. This enables
    # rename/edit-filename to operate on heudiconv duplicate-run output
    # (`..._bold__dup-01.nii.gz`) without canonicalization. Explicit
    # canonicalization is deferred to a future `normalize` command (FR-037).

    def to_filename(self, schema: BIDSSchema | None = None) -> str: ...
    # When `schema` is provided, entities are emitted in `schema.entity_order()`
    # rather than dict insertion order (FR-035). The `trailing` segment, if any,
    # is appended verbatim before the extension.
    def to_relative_path(self) -> Path: ...  # Includes sub-/ses-/datatype/ dirs

    def with_entities(self, **overrides: str) -> BIDSPath: ...
    def without_entities(self, *keys: str) -> BIDSPath: ...   # FR-040 / edit-filename --delete
    def with_suffix(self, suffix: str) -> BIDSPath: ...
    def with_extension(self, extension: str) -> BIDSPath: ...
```

### VCSBackend

Abstract interface for version control operations.

```python
class VCSBackend(Protocol):
    name: str  # "none", "git", "git-annex", "datalad"

    # Core filesystem operations
    def move(self, src: Path, dst: Path) -> None: ...
    def remove(self, path: Path) -> None: ...
    def is_dirty(self) -> bool: ...
    def commit(self, message: str, paths: list[Path]) -> None: ...

    # Annex content lifecycle (FR-022, FR-023)
    def has_content(self, path: Path) -> bool: ...
    def get_content(self, paths: list[Path]) -> None: ...
    def unlock(self, paths: list[Path]) -> None: ...
    def add(self, paths: list[Path]) -> None: ...

class NoVCS: ...      # Direct filesystem; has_content=True, unlock/add no-op
class Git: ...        # git mv/rm/commit; has_content=True, unlock no-op, add=`git add`
class GitAnnex: ...   # git annex get/unlock/add; checks symlink target for has_content
class DataLad: ...    # datalad get/unlock; add via `git annex add`
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

**Batch atomicity (FR-043).** `rename_file()` and `edit_filename()` accept
either a single `PathLike` or a sequence of paths. When a batch is passed,
the implementation precomputes every (source, target) pair, validates the
whole batch (no missing source, no target collision, no schema violation),
and only then begins filesystem mutation. If any precondition fails, the
returned `OperationResult` has `success=False`, `errors` populated, and the
filesystem is left untouched (verified by SC-010). `_scans.tsv` updates
are aggregated per `(subject, session)` so a batch produces one update
per scans file rather than one per source.

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

**FR-038 — full-literal-stem rule for non-BIDS source filenames.** When the
primary file does not parse as a valid `BIDSPath` (e.g., heudiconv duplicate
output `..._bold__dup-01.nii.gz`), `find_sidecars()` falls back to using the
**full literal stem** (basename minus final extension) for sibling matching.
Only files sharing that exact stem are treated as sidecars. The function
MUST NOT canonicalize or strip non-BIDS trailing segments before comparison.
Rationale: heudiconv emits a paired sidecar per duplicate (each `__dup-NN`
carries its own acquisition metadata); merging them would be semantically
wrong. This is also the only safe default for unrecognized non-BIDS suffixes
from other tools (e.g., `+mine`, `--crap`, stray `_test`).

```
Input:  sub-01/func/sub-01_task-rest_bold__dup-01.nii.gz   # non-BIDS
Output: [
    sub-01/func/sub-01_task-rest_bold__dup-01.json,        # full-literal-stem match
    sub-01/func/sub-01_task-rest_bold__dup-01.bvec,        # full-literal-stem match
]
# (sub-01/func/sub-01_task-rest_bold.json, if it existed, is NOT returned —
#  it's a different sidecar set for a different acquisition.)
```

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
class MigrationLevel(str, Enum):
    """Tier of a migration rule (FR-029)."""
    SAFE = "safe"                  # Auto-applied by default
    ADVISORY = "advisory"          # Opt-in via --level=advisory (data-lossy or context-dependent)
    NON_AUTO_FIXABLE = "non-auto-fixable"  # Report only (ambiguous, needs human judgment)

class MigrationMode(str, Enum):
    """Interaction mode for migration (FR-030)."""
    AUTO = "auto"                  # Interactive when PTY available, non-interactive otherwise
    NON_INTERACTIVE = "non-interactive"  # Only auto-fixable, skip prompts
    INTERACTIVE = "interactive"    # Prompt for each advisory/ambiguous finding

@dataclass
class MigrationRule:
    """A single schema-derived migration rule (FR-029).

    Formalized schema analogous to validator schemas (cf. dandi-cli).
    Rules are filterable by id, level, category, from_version."""
    id: str                        # Unique identifier (e.g., "age_89plus_string", "field_rename_BasedOn_to_Sources")
    from_version: str              # First version where this is deprecated
    level: MigrationLevel          # safe, advisory, or non-auto-fixable
    category: Literal["field_rename", "value_rename", "suffix_rename",
                       "path_format", "cross_file_move", "field_removal",
                       "tsv_column_value", "file_rename", "column_rename",
                       "enum_rename", "deprecated_template",
                       "entity_rename", "structural_reorg", "metadata_key_change"]
    description: str               # Human-readable

    # Category-specific fields
    old_field: str | None          # For field_rename/field_removal
    new_field: str | None
    old_value: str | None          # For value_rename
    new_value: str | None
    affected_suffixes: list[str]   # Which file types this applies to
    metadata_key: str | None       # For value renames: which metadata key
    condition: Callable[..., bool] | None  # Contextual guard (e.g., VolumeTiming present)
    handler: Callable[..., list[MigrationFinding]] | None

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
    """Result of migrate_dataset()."""
    success: bool
    dry_run: bool
    from_version: str
    to_version: str
    findings: list[MigrationFinding]  # All matches found
    changes: list[Change]             # What was actually applied
    warnings: list[str]
    errors: list[str]

@dataclass
class AuditResult:
    """Result of schema deprecation audit (FR-033)."""
    schema_version: str
    implemented: list[str]            # Rule IDs with coverage
    missing: list[dict]               # Schema deprecations without rules
    schema_locations_scanned: list[str]  # Which schema levels were checked
```
