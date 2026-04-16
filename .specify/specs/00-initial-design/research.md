# Research: bids-utils — Prior Art & Ecosystem Analysis

**Branch**: `00-initial-design` | **Date**: 2026-04-03

## 1. Migration Prototypes

### bids-specification PR #2282 — `bst migrate` (Copilot-extracted)

- **Source**: https://github.com/bids-standard/bids-specification/pull/2282
- **Origin**: Extracted from PR #1775 which proposed migration paths for BIDS 2.0
- **Language**: Python, integrated into the `bst` (bids-specification-tools) CLI

**Architecture**:
- **Migration Registry Pattern**: Decorator-based registration for modular, versioned migrations
  ```python
  @registry.register(name="...", version="1.10.0", description="...")
  def migration_function(dataset_path):
      return {"success": bool, "modified_files": list, "message": str}
  ```
- **CLI interface**: `bst migrate list`, `bst migrate run [name] [path]`, `bst migrate all [path] --skip [name]`
- **Dry-run support**: Full preview capability
- **JSON-safe operations**: Careful JSON read/write with error logging
- **Dataset discovery**: Uses `rglob()` to locate `dataset_description.json` files

**Currently Implements 3 Migrations**:
1. **`standardize_generatedby` (v1.10.0)**: Legacy provenance fields (`Pipeline`, `Software`, `Tool`, `Provenance`) → `GeneratedBy` array (BEP028 format)
2. **`fix_inheritance_overloading` (v1.10.1)**: Detects deprecated inheritance patterns with conflicting field values across scopes
3. **`fix_tsv_entity_prefix` (v1.10.1)**: Validates entity prefix consistency in TSV column headers

**Code quality**: 29 new tests (119 total passing), ruff formatting, YAML linting all clean. Uses sets for O(1) lookups.

**Key insight for bids-utils**:
- The decorator-based registry is clean, extensible, and directly reusable
- Dry-run infrastructure is already functional
- Only covers a small subset of needed migrations — bids-utils must extend significantly
- bids-utils should implement as a standalone library, not tied to the specification repo
- Support cumulative migration (1.4 → 1.6 → 1.8 → 1.9 → 2.0)

### bids-specification PR #1775 — Original migration proposal

- **Source**: https://github.com/bids-standard/bids-specification/pull/1775
- **Approach**: Patch application system — sequential numeric ordering (`01-01-*`, `01-02-*`) processed via bash `apply_all` script
- **Dual patch types**: Executable shell scripts for custom logic + standard unified `.patch` files
- **CI-tested**: GitHub Actions applies patches and validates against BIDS validator
- **Initial focus**: Renaming "participants" → "subjects" throughout specification
- **Key insight**: Demonstrated community interest and the complexity of migration paths; patch-based approach too fragile for general use

## 2. Metadata Manipulation

### IP-freely (@Lestropie)

- **Source**: https://github.com/Lestropie/IP-freely
- **Language**: Python 3.9+ (~3,145 LOC including tests, ~1,287 LOC core)
- **Dependencies**: Only `numpy` (for numerical matrix handling) + `pre-commit`

**Architecture — Graph-based relational model**:
- **m4d (Metadata-for-Data)**: Maps each data file → its associated metadata files, indexed by extension (`.json`, `.bval`, `.bvec`, `.tsv`)
- **d4m (Data-for-Metadata)**: Inverse mapping — metadata file paths → applicable data files
- **Graph pruning**: Full unpruned graph tracks all possible associations; pruning applies inheritance behavior rules

**Three Inheritance Behaviors**:
1. **Merge** (`.json`): Multiple JSONs aggregated with precedence (last wins for key collisions)
2. **Nearest** (`.bval`, `.bvec`): Only most proximal metadata file; must be unambiguous
3. **Forbidden** (`.tsv`): No inheritance; strictly 1:1 data-metadata pairing

**Ruleset-Based System** (multiple IP versions):
- **1.1.x / 1.7.x**: Original BIDS IP (unique metadata per filesystem level, JSON field overloading permitted)
- **1.11.x**: Same but key-value overrides are warnings, not permitted
- **PR1003**: Ordered by entity count, multiple metadata files allowed
- **I1195**: Multiple JSONs but no key-value overloading
- **forbidden**: Strictest — one metadata file per data file

Each ruleset parameterizes: `json_inheritance_within_dir`, `nonjson_inheritance_within_dir`, `keyvalue_override`, `permit_multiple_metadata_per_data`, etc.

**Capabilities**:
- Detect IP violations (including subtle ones other validators miss)
- Generate data-metadata association graphs (JSON format)
- Extract properly resolved metadata accounting for inheritance chains
- Convert datasets to eliminate IP manifestations
- Audit metadata distribution and key-value overrides

**Applicability Rules**:
- Metadata file must be in ancestor directory of data file
- Entity matching: metadata entities must be subset of data file entities
- Suffix matching required

**Key insights for bids-utils**:
- **Bidirectional m4d/d4m mapping pattern** is elegant for metadata queries — adopt this
- **Ruleset architecture** is cleanly parameterized and extensible
- The "missing file" edge case is critical — aggregation must not assume values for absent files
- Metadata loading abstraction (`load_metadata()` + extension-based dispatch) is reusable
- **No schema integration** — purely filesystem-based; bids-utils should add schema awareness
- Could serve as reference implementation, optional dependency, or foundation library
- Key API surface: `metafiles_for_datafile()` and `load_keyvalues()`

## 3. File Renaming Tools

### rename-tool (@just-meng)

- **Source**: https://github.com/just-meng/rename-tool
- **Language**: Python
- **Purpose**: Batch file/directory renaming with pattern-based transformations
- **Key features**:
  - **Mode inference** from two arguments (replace, prefix, suffix, delete, number offset, regex) — intuitive UX
  - **Collision-safe reordering** to prevent overwrites during batch operations
  - **Number offsetting** (e.g., `_T1 → _T38`) — useful for run reindexing (Story 8)
  - **DataLad integration** for provenance tracking
  - Never overwrites existing files by default
- **Key insight**: Collision-safe reordering algorithm is essential for batch renames. Number offsetting directly useful for `remove-run --shift`. DataLad integration pattern is a reference for FR-004.

### spacetop rename_file (ds005256)

- **Source**: https://github.com/spatialtopology/ds005256/blob/master/code/rename_file
- **Language**: Bash
- **Purpose**: Dataset-specific BIDS file renaming for the spacetop dataset
- **Key features**:
  - Uses `git mv` for VCS awareness
  - Automatic `_scans.tsv` entry updates
  - Sidecar JSON updates (e.g., fieldmap references)
  - `--swap` flag: exchange two filenames via temp file (safe reordering)
  - `--all-extensions` flag: rename all related variants (`.nii.gz`, `.json`, `.tsv`)
  - `--dry-run` flag
  - Error checking: source/destination must be in same directory
  - Integration with `datalad` and `git-annex`
- **Key insight**: **Direct reference implementation for Story 1**. The multi-step consistency sequence (rename → update `_scans.tsv` → update sidecars → verify VCS) is exactly what bids-utils needs. The `--swap` pattern solves race conditions in batch reordering. Every dataset team writes their own ad-hoc script — bids-utils eliminates this.

### file-mapper (DCAN-Labs)

- **Source**: https://github.com/DCAN-Labs/file-mapper
- **Language**: Python 3.7+
- **Purpose**: Copy/move/symlink files between directory structures using JSON configuration
- **Key features**:
  - Multiple actions: copy, move, symlink, move+symlink
  - Template variable replacement (e.g., `{SUBJECT}=sub-01`)
  - Sidecar support (JSON metadata files)
  - Relative symlink creation for portability
  - Test mode (dry-run) with preview
  - Both GUI and CLI interfaces
  - Specifically designed for BIDS dataset reorganization
- **Key insight**: Configuration-driven approach interesting for complex reorganizations (Stories 9-10). Template variable replacement useful for systematic entity transformations. However, bids-utils should keep merge/split operations BIDS-aware rather than adopting a generic mapping framework.

## 4. bidsschematools

- **Package**: `bidsschematools` on PyPI (current version: 1.2.2)
- **License**: MIT
- **Source**: Within `bids-specification` repo at `tools/schemacode/`

### Core API

```python
from bidsschematools import schema

# Load default bundled schema (cached via @lru_cache)
schema_obj = schema.load_schema()

# Load from custom YAML directory or JSON file
schema_obj = schema.load_schema("/path/to/schema")
schema_obj = schema.load_schema("https://bids-specification.readthedocs.io/en/v1.8.0/schema.json")
```

Returns a `Namespace` object (dict-like, supports both dot and bracket notation).

### Schema Structure

**`schema.objects`** (12 sub-namespaces):
- **`entities`** — Name-value pairs in filenames (`sub`, `ses`, `task`, etc.)
- **`metadata`** — JSON sidecar field definitions (includes deprecation markers)
- **`suffixes`** — Filename suffixes (`bold`, `T1w`, etc.)
- **`datatypes`** — Subdirectory types (`anat`, `func`, `meg`, etc.)
- **`extensions`** — File extensions (`.nii.gz`, `.json`, etc.)
- **`columns`** — TSV column definitions
- **`enums`** — Enumerated values (including deprecated ones with replacements)
- **`formats`**, **`modalities`**, **`common_principles`**

**`schema.rules`** (constraints and validation):
- **`rules.files`** — Filename requirements by datatype (`rules.files.raw.anat`)
- **`rules.sidecars`** — JSON metadata field specifications
- **`rules.checks`** — Validation rules with error codes
- **`rules.tabular_data`** — TSV column requirements

**`schema.meta`** — Version information: `schema.bids_version`, `schema.schema_version`

### Key API Functions

- **`load_schema(path=None)`** — Load schema (cached). Path: YAML dir, JSON file, or URL
- **`export_schema(schema)`** — Serialize to JSON
- **`dereference(schema)`** — Replace `$ref` references (auto for YAML, not JSON)
- **`flatten_enums(schema)`** — Simplify enum structures
- **`validate_schema(schema)`** — Validate against BIDS metaschema
- **`filter_schema(schema, keyword)`** — Filter by criteria
- **`rules.regexify_all()`** — Convert all schema rules into regex patterns

### Deprecation Handling

Deprecated elements are marked at **multiple independent schema levels** — all must be scanned for complete coverage:

1. **`rules/sidecars`** — Field-level `deprecated` annotations on sidecar metadata fields (e.g., `DCOffsetCorrection: deprecated` in `ieeg/iEEGRecommended`, `HardcopyDeviceSoftwareVersion: deprecated` in `mri/MRIHardware`, `AcquisitionDuration` with deprecated level in `func/MRIFuncTimingParameters`, `ScanDate` with deprecated level in `pet/PETTime`, `RawSources: deprecated` in `derivatives/common_derivatives`)
2. **`rules/checks`** — Validator check rules with error codes (e.g., `func.PhaseSuffixDeprecated`, `func.DeprecatedAcquisitionDuration`, `privacy.CheckAge89`)
3. **`objects/metadata`** — Description text containing "DEPRECATED" (e.g., `BasedOn`, `RawSources`, `ScanDate`, `DatasetDOI`, `IntendedFor`, `AssociatedEmptyRoom`)
4. **`objects/enums`** — Deprecated enum values (e.g., `ElektaNeuromag`, `_StandardTemplateDeprecatedCoordSys` list)
5. **`objects/columns`** — Column-level deprecations (e.g., `age` column: "89+" string format DEPRECATED)
6. **`objects/suffixes`** — Deprecated suffixes (e.g., `phase`)

**Critical finding (2026-04-15)**: Initial implementation only scanned `rules/checks` and `objects/metadata`, missing `rules/sidecars` field annotations entirely. This caused `DCOffsetCorrection` and `HardcopyDeviceSoftwareVersion` to be overlooked. A schema deprecation audit (FR-033) must scan all 6 levels to prevent gaps.

### Version Support

- Each `bidsschematools` release bundles one specific BIDS schema version
- To work with different versions: install different `bidsschematools` versions, or load from external URL/path
- Version accessible via `schema.bids_version` and `schema.schema_version`

### Integration Guidance for bids-utils

- Load schema once via `_schema.py` wrapper, pass around (cached)
- Access definitions via `schema.objects.entities.<name>`, etc.
- Use `rules.regexify_*()` for filename validation
- Check `deprecated` field when accessing entities/metadata for migration
- Schema is **read-only** — don't modify the loaded object
- **Dereferencing**: automatic for YAML sources, not JSON
- Document which `bidsschematools` version (and thus BIDS schema) is expected

## 5. Copier Templates (Project Scaffolding)

### copier-astral (@ritwiktiwari)

- **Source**: https://github.com/ritwiktiwari/copier-astral
- **Focus**: Minimal, uv-oriented Python project template
- **Tools**: uv, ruff, **ty** (Astral's type checker), pytest with hatch, mkdocs + Material, Typer (CLI)
- **Extras**: pre-commit, git-cliff (changelog), gitleaks (secrets), pysentry-rs (vuln scanning), semgrep, Renovate
- **Assessment**: Most aligned with bids-utils needs. Uses `ty` instead of `mypy` and `hatch` instead of `tox` — would need adjustment.

### NLeSC python-template

- **Source**: https://github.com/NLeSC/python-template
- **Focus**: Research software packages (Netherlands eScience Center)
- **Features**: Copier-based with 3 customization levels (Minimum/Recommended/Let me choose), FAIR compliance, SonarCloud, Zenodo/citation support, CONTRIBUTING.md, CODE_OF_CONDUCT.md, EditorConfig, Apache-2.0
- **Assessment**: Strong research software alignment. Governance docs and citation support directly relevant to bids-utils as a BIDS community tool. May include more infrastructure than needed initially.

### substrate (@superlinear-ai)

- **Source**: https://github.com/superlinear-ai/substrate
- **Focus**: Modern Python packages/applications
- **Features**: uv, ruff, ty, Commitizen (semver), mkdocs + GitHub Pages, Dev Containers + Codespaces, Dependabot, GitHub Actions or GitLab CI
- **Assessment**: Dev Container pattern useful for reproducibility. Commitizen aligns with auto-release needs.

### Template Decision

Given the constitution requirements (uv, tox, tox-uv, ruff, mypy, mkdocs, pytest):
- **copier-astral** is closest to desired stack but uses `ty`/`hatch` instead of `mypy`/`tox`
- **NLeSC** adds scientific community alignment (FAIR, citation, governance docs) but more setup
- **Recommendation**: Start with **copier-astral** as base, swap `ty→mypy`, `hatch→tox+tox-uv`, add tox.ini manually. Adopt NLeSC patterns for governance docs (CONTRIBUTING.md, citation). This keeps scaffolding minimal while aligning with constitution.

## 6. Related Ecosystem

### PyBIDS

- **Role**: Dataset querying and indexing (NOT a dependency for bids-utils core)
- **Constitution stance**: "Very significant, clearly demonstrated benefit" required to adopt
- **Assessment**: Not needed. Core operations use `bidsschematools` + filesystem ops.

### bids2table

- **Role**: Lightweight tabular access to BIDS datasets
- **Constitution stance**: "Evaluate first before considering PyBIDS"
- **Assessment**: Could be useful for merge/split operations that need efficient enumeration. Evaluate when implementing Stories 9-10.

### bids-validator-deno

- **Role**: Reference BIDS validator from PyPI as `bids-validator-deno`
- **Usage**: Integration testing — validate datasets before and after operations
- **Not a runtime dependency** — recommended for `[test]` extras

## 7. Summary of Key Decisions from Research

1. **Schema-driven approach validated** by `bst migrate` (PR #2282) and IP-freely
2. **Migration registry pattern from PR #2282 is directly reusable** — decorator-based, versioned, with dry-run
3. **No existing tool covers bids-utils scope** — all prototypes are narrow/ad-hoc
4. **bidsschematools provides everything needed** — entities, suffixes, metadata, deprecations, enums all accessible via `load_schema()`
5. **IP-freely's bidirectional m4d/d4m pattern** is the right data structure for metadata operations
6. **spacetop rename_file is the reference implementation** for Story 1 (rename → scans → sidecars → VCS)
7. **rename-tool's collision-safe reordering** is essential for batch operations and run reindexing
8. **Template: copier-astral + manual tox/mkdocs adjustments** — minimal, modern
9. **No PyBIDS dependency** — use bidsschematools directly
10. **Migration must be cumulative and version-aware** — schema supports this via version metadata on rules

## 8. Reuse vs Build Assessment

### Directly Reusable from Ecosystem
- Migration registry framework (PR #2282) — import or adapt the decorator pattern
- `bidsschematools` schema loading and querying — direct dependency
- IP-freely's inheritance resolution algorithm — adapt for `metadata.py`

### Must Build Fresh
- File/directory rename with sidecar discovery + `_scans.tsv` patching
- `participants.tsv` management
- VCS-aware file operations (`_vcs.py`)
- Dataset merge/split logic
- CLI framework and `--dry-run`/`--json` infrastructure
- Integration testing harness against `bids-examples`

### Partially Available (extend existing)
- Deprecation application — PR #2282 has 3 of many needed migrations
- Schema version targeting — `load_schema()` exists but glue layer needed for auto-detect from `BIDSVersion`
