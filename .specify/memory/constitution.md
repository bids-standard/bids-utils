# bids-utils Constitution

## Preamble

bids-utils is a community-driven Python library and CLI for manipulating datasets
formatted according to the Brain Imaging Data Structure (BIDS) standard.
It exists because BIDS datasets contain inherent redundancy and cross-references
that make seemingly trivial operations (renaming a subject, reorganizing metadata)
surprisingly complex. This constitution encodes the principles that keep the tool
safe, reliable, and welcoming.

## Core Principles

### I. Do No Harm (NON-NEGOTIABLE)

A valid BIDS dataset MUST remain valid after any bids-utils operation completes
successfully. This is the project's prime directive: users trust this tool with
their research data, and breaking a dataset is unacceptable.

- Every command operates on a copy or uses atomic transactions; partial failures
  must not leave datasets in an inconsistent state.
- Destructive operations (remove subject, remove run) require explicit confirmation
  unless `--force` is passed.
- When in doubt about correctness, refuse to act and explain why. It is always
  better to abort with a clear message than to silently corrupt data.
- **Fail loudly, never degrade silently.** If a mandated tool or check is
  unavailable (e.g., `jscpd` not installed, validator crashes), the operation
  MUST fail with a clear error — never emit a "warning" and continue as if
  the check passed. Warnings that mask missing checks are worse than errors
  because they create a false sense of compliance.
- Before modifying any file, verify the dataset's structural integrity for the
  affected entities (not necessarily a full validation, but targeted checks).

### II. Schema-Driven and Version-Flexible

bids-utils derives its understanding of BIDS from the machine-readable schema via
`bidsschematools`, not from hardcoded rules.

- Entity names, allowed suffixes, file naming patterns, and metadata inheritance
  rules come from the schema.
- When the BIDS specification evolves, bids-utils should adapt by updating its
  schema dependency, not by patching internal logic.
- The `migrate` command is the canonical mechanism for adapting datasets to
  specification changes (deprecations, breaking changes for BIDS 2.0).
- **Multi-version support is required.** Users must not be forced to use the
  latest schema version. Real-world datasets may conform to older schema versions
  and upgrading may be infeasible (institutional constraints, validation pipelines,
  downstream tool compatibility). bids-utils must:
  - Accept an explicit schema version parameter (e.g., `--schema-version 1.8.0`)
    or detect the version from `dataset_description.json` `BIDSVersion` field.
  - Default to the schema version declared by the dataset, not the latest
    available.
  - Ensure version-specific operations (e.g., `migrate`) clearly state what
    source and target versions they operate on.
  - Test against multiple schema versions in CI, not just the latest.
- Schema version compatibility must be explicit: document which schema versions
  each release supports, and maintain a compatibility matrix.

### III. Library-First

Every feature starts as a Python library with a clean, importable API. The CLI
is a thin layer on top.

- Public API functions must be independently usable without the CLI.
- Libraries must be self-contained and independently testable.
- CLI commands map directly to library functions with consistent argument naming.
- API design follows the principle of least surprise: method names should read
  naturally (e.g., `rename_subject(dataset, old="01", new="02")`).

### IV. CLI Excellence

The CLI is the primary user-facing interface and must be exemplary.

- Text in, text out: stdin/args in, stdout out, errors to stderr.
- Support both human-readable (default) and machine-readable (`--json`) output.
- Dry-run mode (`--dry-run` / `-n`) for every mutating command, showing exactly
  what would change. This is mandatory, not optional.
- Verbose/quiet controls (`-v` / `-q`) for all commands.
- Progress reporting for operations on large datasets.
- Exit codes must be meaningful: 0 for success, 1 for errors, 2 for "refused
  to act" (e.g., would break validity).

### V. Test-First (NON-NEGOTIABLE)

TDD is mandatory. Tests are written before implementation.

- Red-Green-Refactor cycle strictly enforced.
- Every command must be tested against the `bids-examples` collection: sweep
  through datasets, perform the operation, verify the dataset remains valid.
- Property-based and randomized testing where applicable (e.g., randomly select
  a subject to rename, randomly generate new names).
- Integration tests against real filesystem layouts, not just mocks.
- Tests must cover edge cases: datasets with `sourcedata/`, `.heudiconv/`,
  `_scans.tsv` files, inheritance hierarchies, missing metadata files.
- **git-annex testing is mandatory**: the `bids-examples` sweep must run in
  both regular git and git-annex modes (all files forced into annex). A
  `tmp_annex_dataset` fixture with locked symlinks must be used for unit tests
  of any file-manipulating operation.
- bids-examples is a git submodule or test fixture, always available in CI.

### VI. Performance at Scale

BIDS datasets can be enormous (thousands of subjects, millions of files). The tool
must remain usable at scale.

- Avoid loading entire datasets into memory when only a subset of entities is
  needed.
- Use lazy evaluation and streaming where possible.
- File operations should be batched and parallelizable.
- Profile before optimizing, but design data structures with scale in mind
  from the start.
- For remote/annexed datasets, support transparent access via fsspec and
  git-annex awareness (datalad-fuse) without requiring full local copies.

### VII. VCS Awareness (NON-NEGOTIABLE for git-annex)

Many BIDS datasets live under version control (git, git-annex, DataLad).
bids-utils must respect this. **Git-annex support is not an afterthought —
a majority of large BIDS datasets are managed with DataLad/git-annex.**

- Detect and use the VCS layer when present: `git mv` instead of `os.rename`,
  `git rm` instead of `os.unlink`.
- Support git-annex: handle annexed (locked) files correctly, use `git annex`
  commands when appropriate.
- **Annexed files are symlinks.** Code MUST treat symlinks as files everywhere:
  - `Path.is_file()` follows symlinks — returns `False` for annexed files
    without content. Use `not path.is_dir()` for file iteration.
  - `Path.exists()` follows symlinks — returns `False` for broken symlinks.
    Use `path.exists() or path.is_symlink()` when checking file existence.
  - `Path.resolve()` follows symlinks — resolves to `.git/annex/objects/...`.
    Use `Path.absolute()` to preserve the symlink path.
- **All tests MUST pass on both regular and git-annex datasets.** The
  `bids-examples` sweep tests must run in both plain-git and git-annex modes
  (force all files into annex) to verify no operation breaks on symlinks.
- When DataLad is available, prefer `datalad run` semantics for provenance.
- When no VCS is detected, operate directly on the filesystem.
- Never silently ignore VCS state: if a git working tree is dirty in a way
  that would conflict with the operation, warn or abort.

### VIII. Observability

Users must be able to understand what the tool is doing and what it did.

- Structured logging with configurable verbosity.
- Every mutating operation produces a summary of changes (files moved, renamed,
  created, deleted; metadata fields modified).
- Machine-readable change manifests (JSON) available for programmatic consumption.
- Dry-run output must be identical in format to actual-run output, differing
  only in the action header.

### IX. Simplicity and YAGNI

Start simple. Resist the urge to over-engineer.

- Each command does one thing well. Composition over monoliths.
- No plugin system, no middleware, no abstract base classes unless genuinely
  needed by multiple concrete implementations.
- Prefer flat module structure over deep nesting.
- If a feature can be achieved by composing existing commands, do not create
  a new command.

### X. Versioning & Breaking Changes

Version numbering MUST follow semantic versioning (MAJOR.MINOR.PATCH):
- **MAJOR**: Breaking changes (incompatible API changes).
- **MINOR**: New features (backward compatible additions).
- **PATCH**: Bug fixes (backward compatible corrections).

Breaking changes REQUIRE:
- Migration guide in release notes.
- Deprecation warnings in prior MINOR version (when possible).
- Clear documentation of changed behavior.

**Rationale**: Predictable versioning builds trust with users and integrators.
Clear migration paths enable safe upgrades—especially important for a tool
that manipulates irreplaceable research data.

### XI. DRY Principle — No Code Duplication

**Duplication is evil.** Code MUST NOT contain duplicated logic or functionality.

**Before writing new code**:
- Introspect existing codebase for similar functionality.
- Search for patterns that solve the same or related problems.
- Identify opportunities to extract common functionality.
- Prefer reusing existing functions over creating new ones.

**When duplication is detected**:
- Extract common functionality into reusable functions/modules.
- Refactor immediately (do not defer "for later").
- Create utility functions for repeated patterns.
- Use composition and higher-order functions for variations.

**Code review MUST**:
- Actively check for code duplication (copy-paste, similar logic).
- Identify opportunities to refactor into reusable components.
- Reject PRs with obvious duplication without justification.
- Suggest existing functions/modules that solve the same problem.

**Allowed exceptions** (duplication is acceptable):
- **Automated generation**: Generated code (type definitions from schema,
  documentation).
- **Build artifacts**: Compiled output, bundled assets.
- **Test fixtures**: Similar test setup where abstraction reduces readability.
- **Configuration**: Environment-specific configs with overlapping values.
- **Explicit performance**: Inlining for performance (must be justified and
  measured).

All exceptions MUST be documented with rationale.

**Tools and enforcement**:
- **pylint duplicate-code** (`pylint --disable=all --enable=duplicate-code`):
  Line-based detection with Python-native AST awareness. Supports ignoring
  imports, docstrings, and signatures to reduce false positives. Use via
  `pylint` (not standalone `symilar`) to get `# pylint: disable=duplicate-code`
  pragma support and `--ignore-paths` for excluding files (e.g., migrations,
  generated code, legacy Python 2 files).
- **jscpd** (`npx jscpd --format python`): Token-based detection via
  Rabin-Karp algorithm. More sensitive than pylint — catches duplication across
  formatting differences. Provides built-in `--threshold` for CI gating
  (exit non-zero if duplication exceeds N%) and rich reporting (JSON, HTML).
- Both tools should run in CI as a `tox` testenv (e.g., `tox -e duplication`).
  pylint catches Python-idiomatic duplication; jscpd catches
  formatting-resistant clones. They are complementary.
- Files with acceptable duplication (migrations, generated code) should be
  excluded via `--ignore-paths` (pylint) or `--ignore` globs (jscpd), not
  by raising thresholds globally.
- Regular refactoring to address accumulated duplication.

**Rationale**: Code duplication multiplies maintenance burden, bugs, and
inconsistencies. Every duplicated block is a potential source of divergence
and technical debt. Extracting common functionality makes the codebase smaller,
more maintainable, and easier for new contributors to understand.

## Ecosystem Integration

### Relationship to bidsschematools

bids-utils depends on bidsschematools for schema access. It does NOT fork or
vendor the schema. When bidsschematools evolves, bids-utils follows.

### Relationship to PyBIDS and bids2table

PyBIDS is a substantial library with its own abstractions, database-backed
indexing, and conventions. While its implementation and interfaces should be
**consulted** during design (to avoid gratuitous incompatibility), adopting
PyBIDS as a dependency—even optional—requires a **very significant, clearly
demonstrated benefit** that cannot be achieved with lighter alternatives.
The bar is high because PyBIDS brings considerable transitive complexity.

**bids2table** is a more lightweight alternative for dataset querying and
tabular access. Where bids-utils needs to enumerate or query dataset contents,
bids2table should be evaluated first as a potentially adoptable dependency
before considering PyBIDS.

Core operations (rename, migrate, metadata manipulation) must work without
either PyBIDS or bids2table. Any dataset querying dependency, if adopted,
must be optional.

### Relationship to bids-validator

After any mutating operation, bids-utils should be able to invoke the BIDS
validator to confirm the dataset remains valid. The validator is a recommended
but optional dependency (used in testing, available as a post-operation check).

The **primary validator** is the Deno-based official BIDS validator, available
from PyPI as **`bids-validator-deno`**. This is the reference implementation
maintained by the BIDS community.

There is a **work-in-progress Python-native validator**
(https://github.com/bids-standard/python-validator) which may be adopted later
as an alternative or additional validation backend. Until it matures, bids-utils
should target `bids-validator-deno` as the default validation tool and not
depend on the Python validator for correctness guarantees.

### Scope boundaries

bids-utils manipulates existing datasets. It does NOT:
- Convert raw data to BIDS (that's what converters like BIDScoin, HeuDiConv do).
- Validate datasets (that's bids-validator).
- Query datasets for analysis (that's PyBIDS, bids2table, rsbids).
- Define the specification (that's bids-specification).

## Development Workflow

### Branching and Review

- Feature branches off `main`.
- PRs require at least one review before merge.
- CI must pass (tests, linting, type checking) before merge.
- **`tox` must pass before committing.** Never auto-commit if `tox` (or any
  of its constituent envs: tests, lint, type, duplication) fails. Fix the
  failures first, verify `tox` is green, then commit.
- Spec-driven development via spec-kit: specify, plan, then implement.

### Tooling

- **Package management**: `uv` with `pyproject.toml` as single source of truth.
- **Testing**: `pytest` orchestrated by `tox` (with `tox-uv`).
- **Linting**: `ruff` for formatting and linting.
- **Type checking**: `mypy` with strict mode on new code.
- **Duplication detection**: `pylint --duplicate-code` (AST-aware, Python-native)
  and `jscpd` (token-based, cross-format). Both run as dedicated `tox` testenvs.
- **Documentation**: `mkdocs` (aligned with bids-specification).
- **CI**: GitHub Actions invoking `tox`, using `tox-gh-actions`.

### Releases

Releases MUST be automated. Manual release processes are error-prone and
create bus-factor risk.

- Use **intuit/auto** (or a comparable automated release tool) to drive
  versioning, changelog generation, and publishing from PR labels.
- Every merged PR must carry a release label (e.g., `patch`, `minor`, `major`,
  `internal`, `documentation`) that determines version impact.
- Changelog is generated automatically from PR titles and labels — no manual
  CHANGELOG.md editing.
- Release workflow runs in CI: tag, build, publish to PyPI, create GitHub
  Release with generated notes.
- This pattern is proven in the ecosystem (dandi-cli uses intuit/auto;
  datalad uses an auto-inspired homebrewed approach).

### Dependency Layering

```
[project.optional-dependencies]
test = ["pytest", "pytest-cov", "pytest-timeout", ...]
devel = ["bids-utils[test]", "ruff", "mypy", "tox", "tox-uv", ...]
ci = ["bids-utils[devel]", "tox-gh-actions", ...]
```

## Community and Governance

### BIDS Alignment

bids-utils operates under the umbrella of the BIDS standard organization
(`bids-standard` on GitHub). It adopts:

- The [BIDS Code of Conduct](https://github.com/bids-standard/bids-specification/blob/master/CODE_OF_CONDUCT.md).
- The spirit of BIDS governance: strive for consensus, promote open discussion,
  minimize administrative burden, grow the community, maximize bus factor.
- OpenStand principles: Due Process, Broad Consensus, Transparency, Balance,
  Openness.

### Contributor Friendliness

BIDS is community-driven. bids-utils must lower the barrier to contribution:

- Clear CONTRIBUTING.md with setup instructions, architecture overview, and
  "good first issue" labeling.
- Comprehensive developer documentation: how modules relate, how to add a new
  command, how testing works.
- Small, focused PRs over large monolithic ones.
- Respectful, constructive code review culture.
- AI-assisted development welcome (spec-kit workflow), with AI-generated tests
  marked `@pytest.mark.ai_generated`.

### Licensing

Apache-2.0 (permissive, compatible with the broader BIDS ecosystem which uses
a mix of MIT, Apache-2.0, and CC licenses).

## Governance

This constitution supersedes all other development practices for bids-utils.
Amendments require:

1. A PR modifying this document with rationale.
2. Review and approval from at least one maintainer.
3. Update of all dependent templates (see constitution_update_checklist.md).

All PRs and reviews must verify compliance with these principles. Deviations
from the constitution must be explicitly justified and documented.

**Version**: 1.5.0 | **Ratified**: 2026-03-21 | **Last Amended**: 2026-04-10
