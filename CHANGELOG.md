# v0.1.1 (Tue Jun 02 2026)

#### 📝 Documentation

- Remove completed initial release steps [#17](https://github.com/bids-standard/bids-utils/pull/17) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.1.0 (Mon Jun 01 2026)

Initial public alpha release of `bids-utils` — a Python library and CLI for
structural manipulation of BIDS datasets, designed to be schema-driven
(via [`bidsschematools`][bst]) and VCS-aware (plain git, git-annex, and
DataLad).

#### 🚀 What's in 0.1.0

- **CLI commands**: `rename`, `migrate`, `subject-rename`, `session-rename`,
  `remove-subject`, `remove-session`, `remove-run`, `merge`, `split`,
  `aggregate-metadata`, `segregate-metadata`, `audit-metadata`, `completion`.
- **Library API**: every CLI command maps to a public Python function with
  `OperationResult` return values; suitable for scripted pipelines.
- **Migration engine**: applies BIDS 1.x intra-major deprecation rules
  (`BasedOn`/`RawSources` → `Sources`, `ScanDate` → `_scans.tsv` `acq_time`,
  `DCOffsetCorrection` → `SoftwareFilters`, `AcquisitionDuration` →
  `FrameAcquisitionDuration`, deprecated coordinate-system labels, etc.) at
  `safe` / `advisory` / `non-auto-fixable` tiers, with a schema-coverage
  audit (`migrate --audit`) so missing rules surface as drift.
- **VCS integration**: detects DataLad → git-annex → git → plain
  filesystem; uses `git mv` (or the annex equivalent) for moves; preserves
  locked-annexed-symlink semantics during renames; configurable
  `--annexed={error,get,skip,skip-warning}` policy for fetched content.
- **Observability**: `--dry-run=overview|detailed`, `--json` output mode,
  exit codes (0 success / 1 partial / 2 refused), and per-source `Change`
  entries in batch operations.
- **Test infrastructure**: per-test `git worktree` fixture pattern over the
  `bids-examples` clone, plus an adversarial-suffix injection helper for
  heudiconv `__dup-NN` / `+mine` / `--crap` / `_test` source filenames.
  Mutating sweeps validate against the BIDS validator pre- and
  post-operation across ~1700 cases.

#### ⚠ Known limitations

- The `rename --set` / `edit-filename` split (FR-039 / FR-040, atomic-batch
  glob input per FR-043) is specified but **not yet implemented** —
  scheduled for 0.2.0. Use `rename --set key=value FILE` (current form) for
  entity edits until then.
- BIDS 2.0 migration is scaffolding-only — concrete rules are stubs.
- Performance optimization for >1000-subject datasets is unverified
  (SC-003 deferred).

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

[bst]: https://github.com/bids-standard/bids-specification/tree/master/tools/schemacode

---
