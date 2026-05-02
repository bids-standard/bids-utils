# Contract: Library API Surface

**Date**: 2026-04-03

## Public API (importable by users)

### `bids_utils.BIDSDataset`

```python
class BIDSDataset:
    root: Path
    bids_version: str
    annexed_mode: AnnexedMode = AnnexedMode.ERROR

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

### `bids_utils.rename` (mv-like — FR-039, FR-043)

```python
def rename_file(
    dataset: BIDSDataset,
    src: PathArg,                # single path OR sequence (multi-source mv)
    dst: str | Path,
    *,
    dry_run: bool = False,
    include_sourcedata: bool = False,
) -> OperationResult:
    """Rename one or more BIDS files (and their sidecars) into `dst`.

    Pure mv-like semantics — does NOT mutate entity values via parameters
    (use `edit_filename()` for that). Sidecars are discovered by FR-038
    full-literal-stem matching, so non-BIDS source filenames such as
    heudiconv duplicate-run output (`..._bold__dup-01.nii.gz`) are
    handled correctly.

    `src` accepts a single path or a sequence of paths. When multiple
    paths are passed, `dst` MUST be an existing directory (mirrors Unix
    `mv`). The whole batch is atomic — any conflict aborts before
    filesystem mutation (FR-043).

    Cross-container detection: when `dst` lives under a different
    `sub-XX/[ses-YY]/` than the source(s) (or `dst` is a directory),
    the destination filename's `sub-` / `ses-` entity labels are
    rewritten to match the destination path, delegating to
    `edit_filename`'s `_rewrite_entities_for_target_filename(...)` core.
    Result satisfies entity-order normalization (FR-035).

    Conflicts (any target file already exists) raise exit code 2 (FR-011).
    """
```

### `bids_utils.edit_filename` (FR-040)

```python
PathLike = str | Path
PathArg = PathLike | Sequence[PathLike]

def edit_filename(
    dataset: BIDSDataset,
    paths: PathArg,
    *,
    set_entities: dict[str, str] | None = None,
    delete_entities: list[str] | None = None,
    set_suffix: str | None = None,
    dry_run: bool = False,
    include_sourcedata: bool = False,
) -> OperationResult:
    """In-place edits to one or many BIDS filenames (and their sidecars).

    Canonical home for the `--set` / `--delete` / `--set-suffix` semantics
    formerly attached to `rename`. Edits the filename in place — both the
    entity portion and the suffix — without moving the file to a different
    directory. (Use `rename_file()` for cross-directory / cross-container
    moves.)

    Batch / glob input (FR-043):
    - `paths` accepts either a single path or a sequence of paths.
    - The CLI passes through shell-globbed lists, so
      `bids-utils edit-filename sub-*/func/sub-*_task-rest_bold.nii.gz
      --set task=nback` operates across many files (and across multiple
      subjects/sessions) in a single invocation. The same edit is applied
      to each path; if any path conflicts (target already exists, schema
      validation fails, etc.) the whole batch is refused with exit code 2
      before any filesystem mutation (atomic batch — FR-043).
    - Sidecars are discovered per source path via FR-038 full-literal-stem
      matching, so heudiconv-style non-BIDS filenames are handled.
    - `_scans.tsv` updates are coalesced per (subject, session) container
      so a single batch produces one update per scans file.

    - `set_entities`: insert/overwrite entity values (applied to every path).
    - `delete_entities`: remove the listed entity keys (applied to every path).
    - `set_suffix`: replace the BIDS suffix (applied to every path).

    Output filenames satisfy entity-order normalization (FR-035).
    Robust to non-BIDS source filenames: unrecognized trailing segments
    (e.g. heudiconv `__dup-NN`) are preserved verbatim — explicit
    canonicalization is deferred to a future `normalize` command (FR-037).

    Conflicts (any target file already exists) raise exit code 2 (FR-011).
    """
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
    level: MigrationLevel = MigrationLevel.SAFE,
    mode: MigrationMode = MigrationMode.AUTO,
    rule_ids: list[str] | None = None,      # Include only these rules (None = all at level)
    exclude_rules: list[str] | None = None,  # Exclude these rule IDs
    dry_run: bool = False,
) -> MigrationResult:
    """Apply schema-driven migrations filtered by level and rule selection."""

def audit_schema_coverage(
    schema_version: str | None = None,
) -> AuditResult:
    """Compare registered migration rules against schema deprecation markers (FR-033).

    Scans all schema levels: rules/sidecars, rules/checks, objects/metadata,
    objects/enums, objects/columns, objects/suffixes.
    Reports unimplemented deprecations."""
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

### `bids_utils.run`

```python
def remove_run(
    dataset: BIDSDataset,
    subject: str,
    run: str,
    *,
    suffix: str | None = None,
    task: str | None = None,
    session: str | None = None,
    shift: bool = True,
    dry_run: bool = False,
    force: bool = False,
) -> OperationResult:
    """Remove a run and optionally reindex subsequent runs."""
```

### `bids_utils.split`

```python
def split_dataset(
    dataset: BIDSDataset,
    target: str | Path,
    *,
    suffixes: list[str] | None = None,
    datatypes: list[str] | None = None,
    dry_run: bool = False,
) -> OperationResult:
    """Extract a subset of a dataset by suffix/datatype filter."""
```

### `bids_utils.merge`

```python
def merge_datasets(
    sources: list[str | Path],
    target: str | Path,
    *,
    into_sessions: list[str] | None = None,
    on_conflict: Literal["error", "add-runs"] = "error",
    reconcile_metadata: bool = False,
    dry_run: bool = False,
) -> OperationResult:
    """Merge multiple BIDS datasets.

    When reconcile_metadata=True, conflicting top-level sidecar metadata
    is segregated down to the appropriate level and re-aggregated to produce
    correct inheritance (see US9 acceptance scenario 6).
    """
```

### `bids_utils._vcs.VCSBackend` (Protocol)

```python
class VCSBackend(Protocol):
    name: str

    # Existing operations
    def move(self, src: Path, dst: Path) -> None: ...
    def remove(self, path: Path) -> None: ...
    def is_dirty(self) -> bool: ...
    def commit(self, message: str, paths: list[Path]) -> None: ...

    # Content availability (FR-022)
    def has_content(self, path: Path) -> bool: ...
    def get_content(self, paths: list[Path]) -> None: ...

    # Write lifecycle for annexed files (FR-022)
    def unlock(self, paths: list[Path]) -> None: ...
    def add(self, paths: list[Path]) -> None: ...
```

| Backend   | `has_content`         | `get_content`       | `unlock`              | `add`               |
|-----------|-----------------------|---------------------|-----------------------|---------------------|
| NoVCS     | always `True`         | no-op               | no-op                 | no-op               |
| Git       | always `True`         | no-op               | no-op                 | `git add`           |
| GitAnnex  | symlink target exists | `git annex get`     | `git annex unlock`    | `git annex add`     |
| DataLad   | symlink target exists | `datalad get`       | `datalad unlock`      | `git annex add`     |

### `bids_utils._io` (Content-aware I/O)

```python
def ensure_content(path: Path, vcs: VCSBackend, mode: AnnexedMode) -> None:
    """Ensure file content is available for reading. Enforces --annexed policy."""

def ensure_writable(path: Path, vcs: VCSBackend) -> None:
    """Unlock annexed file if locked (symlink to .git/annex/objects).
    Always applied for GitAnnex/DataLad, regardless of --annexed mode."""

def mark_modified(paths: list[Path], vcs: VCSBackend) -> None:
    """Re-annex files after modification (git annex add).
    Always applied for GitAnnex/DataLad, regardless of --annexed mode."""

def read_json(path: Path, vcs: VCSBackend, mode: AnnexedMode) -> dict | None:
    """Read JSON with content-awareness. Returns None if skipped."""
```

## CLI Contract

Group-level options (before the command):
- `--annexed MODE`: How to handle git-annex files without local content. Modes: `error` (default), `get`, `skip-warning`, `skip`. Also settable via `BIDS_UTILS_ANNEXED` env var.

Per-command common options:
- `--dry-run` / `-n`: Show what would change without modifying. Accepts optional value: `overview` (default, summary) or `detailed` (every file operation listed).
- `--json`: Machine-readable JSON output
- `-v` / `-q`: Verbosity control
- `--force`: Skip confirmation on destructive operations
- `--include-sourcedata`: Extend operation to `sourcedata/` and `.heudiconv/`
- `--schema-version VERSION`: Override detected schema version

Rename / edit-filename split (FR-039, FR-040, FR-043):
- `bids-utils rename SRC [SRC ...] DST` — mv-like. Accepts either `SRC DST` (single source) or `SRC ... DST` where DST is a directory (multi-source, mirroring Unix `mv`). Does NOT accept `--set` / `--delete` / `--suffix` (these were the pre-2026-04-27 flags); passing them yields a non-zero exit and a hint pointing to `edit-filename`. Detects cross-container moves and rewrites `sub-` / `ses-` labels in the destination filename automatically.
- `bids-utils edit-filename SRC [SRC ...] --set KEY=VALUE [--set ...] [--delete KEY ...] [--set-suffix SUFFIX]` — in-place edits to the filename (entities and/or suffix) for one or many BIDS files. `SRC` accepts shell globs and may span subjects/sessions in a single invocation; the same edit is applied to each source. `--set` / `--delete` are repeatable. The whole batch is atomic — any conflict aborts before filesystem mutation (FR-043). Operates within each `SRC`'s directory only — for cross-directory moves, use `rename`.

Migrate-specific options:
- `--to VERSION`: Target BIDS version (default: current released 1.x)
- `--level safe|advisory|all`: Migration tier filter (default: `safe`)
- `--mode auto|non-interactive|interactive`: Interaction behavior (default: `auto`)
- `--rule-id ID`: Include only this rule (repeatable)
- `--exclude-rule ID`: Exclude this rule (repeatable)
- `--audit`: Compare registered rules against schema deprecation markers and report gaps

Exit codes:
- 0: Success
- 1: Error (unexpected failure)
- 2: Refused to act (would break validity, conflict detected)
