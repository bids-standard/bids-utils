# Quickstart — Format-Preserving I/O

This is the developer quickstart for the format-preserving I/O feature.
It shows the new internal API and how to migrate an existing read-modify-
write site to it.

## When to use the new API

Use the profile-aware API any time you read a JSON sidecar, TSV table, or
plain-text BIDS file with the intent to modify and write it back. If you
are only reading (no write), you can use the existing `read_json` /
`read_tsv` and ignore profiles. If you are creating a brand-new file with
no source to mirror, write with `profile=None` to use the documented
default (FR-006).

## Minimal example — JSON sidecar

```python
from bids_utils._io import read_json_with_profile, write_json

data, profile = read_json_with_profile(sidecar_path, vcs, mode)
if data is None:
    return  # skipped or unreadable

# ... mutate data in place ...
data["NewField"] = "value"

# write_if_changed is implicit; returns True iff bytes changed
wrote = write_json(sidecar_path, data, vcs, profile=profile)
```

## Minimal example — TSV

```python
from bids_utils._tsv import read_tsv_with_profile, write_tsv

rows, profile = read_tsv_with_profile(tsv_path, vcs, annexed_mode)

# ... mutate one row ...
rows[5]["age"] = "42"

# Pass changed_indices so untouched rows are spliced verbatim (preserving quoting)
write_tsv(tsv_path, rows, vcs, profile=profile, changed_indices={5})
```

## Migrating an existing site

**Before** (in `migrate.py` or `metadata.py`):
```python
data = json.loads(jf.read_text(encoding="utf-8"))
data["X"] = "y"
jf.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
```

**After**:
```python
from bids_utils._io import read_json_with_profile, write_json

data, profile = read_json_with_profile(jf, vcs, annexed_mode)
data["X"] = "y"
write_json(jf, data, vcs, profile=profile)
```

That's the whole change. The profile carries indent, separators, line
endings, BOM, and trailing-newline state through to the write. No-op
write suppression (FR-007) happens automatically.

## Verifying the contract locally

```bash
# Unit tests for profile detection / serialization
tox -e py312 -- tests/test_format.py

# Integration sweep over bids-examples (slowest)
tox -e py312 -- tests/integration/test_format_preservation.py

# Full gate — must be green before commit
tox
```

The integration test asserts SC-001 (byte identity on no-op),
SC-002 (≤5-line diff on one-field edit, ≥95% of sidecars), and
SC-003 (≤3-line diff on one-row edit, 100% of TSVs). It runs the sweep
in both regular-git and tmp_annex_dataset modes (constitution VII).

## Defaults for new files (FR-006)

If you are writing a file that has no source on disk:

```python
write_json(new_sidecar_path, data, vcs)            # profile=None → DEFAULT_JSON_PROFILE
write_tsv(new_tsv_path, rows, vcs)                 # profile=None → DEFAULT_TSV_PROFILE
```

The defaults are 2-space indent for JSON, LF line endings, trailing
newline, no BOM. They are defined once in `_format.py` —
`DEFAULT_JSON_PROFILE`, `DEFAULT_TSV_PROFILE`, `DEFAULT_TEXT_PROFILE` —
and must not be redefined per command.

## Troubleshooting

- **My write isn't happening.** Check the return of `write_json` /
  `write_tsv`. It is `False` when no semantic change was made, by design
  (FR-007). If you see this on a real edit, your mutation didn't survive
  serialization (e.g., you mutated a copy).
- **My CRLF file came back as LF.** You are using the legacy
  `write_json(path, data, vcs)` without a profile. Use
  `read_json_with_profile` and pass `profile=` to the write.
- **A new key landed in the middle of the object.** You assigned via
  something other than `data[k] = v` on the dict (e.g., constructed a
  new dict). To preserve order + append-at-end, mutate the existing
  parsed dict in place.
- **Diff is bigger than expected on a one-field edit.** Confirm the
  source profile was passed to the write. If profiles match and the diff
  is still large, the source likely uses unusual separators (e.g.,
  `" : "`) that the detector falls back from; this is documented as
  acceptable normalization in `research.md` R3.
