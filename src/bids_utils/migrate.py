"""Schema-driven migration for BIDS datasets (User Stories 2, 3).

Handles 1.x deprecation fixes and 2.0 migration using rules derived
from bidsschematools.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from bids_utils._dataset import BIDSDataset
from bids_utils._scans import find_scans_tsv, read_scans_tsv, write_scans_tsv
from bids_utils._types import Change, OperationResult

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class MigrationRule:
    """A single migration rule."""

    id: str
    from_version: str
    category: str  # field_rename, value_rename, suffix_rename, path_format, cross_file_move, enum_rename
    description: str
    old_field: str | None = None
    new_field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    affected_suffixes: list[str] = field(default_factory=list)
    metadata_key: str | None = None  # for value renames: which metadata key
    handler: Callable[..., list[MigrationFinding]] | None = field(
        default=None, repr=False
    )


@dataclass
class MigrationFinding:
    """A specific instance where a rule matches a file."""

    rule: MigrationRule
    file: Path
    current_value: Any
    proposed_value: Any
    can_auto_fix: bool = True
    reason: str | None = None


@dataclass
class MigrationResult:
    """Result of a migrate operation."""

    success: bool = True
    dry_run: bool = False
    from_version: str = ""
    to_version: str = ""
    findings: list[MigrationFinding] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Migration registry
# ---------------------------------------------------------------------------

_RULES: list[MigrationRule] = []


def _register_rule(rule: MigrationRule) -> None:
    _RULES.append(rule)


def _get_rules(from_version: str, to_version: str) -> list[MigrationRule]:
    """Get applicable rules between two versions."""
    from packaging.version import Version

    from_v = Version(from_version)
    to_v = Version(to_version)

    applicable = []
    for rule in _RULES:
        try:
            rule_v = Version(rule.from_version)
        except Exception:
            continue
        if from_v < rule_v <= to_v:
            applicable.append(rule)
        # Also include rules at from_version for deprecations already present
        elif rule_v <= from_v <= to_v:
            applicable.append(rule)

    return applicable


# ---------------------------------------------------------------------------
# Built-in migration rules (1.x deprecations)
# ---------------------------------------------------------------------------

# Metadata field renames
_FIELD_RENAMES = [
    ("BasedOn", "Sources", "1.5.0"),
    ("RawSources", "Sources", "1.5.0"),
]

for old, new, ver in _FIELD_RENAMES:
    _register_rule(
        MigrationRule(
            id=f"field_rename_{old}_to_{new}",
            from_version=ver,
            category="field_rename",
            description=f"Rename metadata field '{old}' to '{new}'",
            old_field=old,
            new_field=new,
        )
    )

# Enum value renames
_ENUM_RENAMES = [
    ("MEGCoordinateSystem", "ElektaNeuromag", "NeuromagElektaMEGIN", "1.6.0"),
    ("MEGCoordinateSystem", "KitYokogawa", "YokogawaKIT", "1.6.0"),
]

for key, old_val, new_val, ver in _ENUM_RENAMES:
    _register_rule(
        MigrationRule(
            id=f"enum_rename_{key}_{old_val}",
            from_version=ver,
            category="enum_rename",
            description=f"Rename {key} value '{old_val}' to '{new_val}'",
            old_value=old_val,
            new_value=new_val,
            metadata_key=key,
        )
    )

# Path format migrations (relative paths -> BIDS URIs)
_PATH_FORMAT_FIELDS = ["IntendedFor", "AssociatedEmptyRoom", "Sources"]

for fld in _PATH_FORMAT_FIELDS:
    _register_rule(
        MigrationRule(
            id=f"path_format_{fld}",
            from_version="1.8.0",
            category="path_format",
            description=f"Convert relative paths to BIDS URIs in '{fld}'",
            metadata_key=fld,
        )
    )

# DatasetDOI format
_register_rule(
    MigrationRule(
        id="doi_uri_format",
        from_version="1.8.0",
        category="value_rename",
        description="Convert bare DOIs to URI format in DatasetDOI",
        metadata_key="DatasetDOI",
        old_value=r"^10\.",  # regex pattern for bare DOI
        new_value="doi:",  # prefix
    )
)

# Cross-file moves
_register_rule(
    MigrationRule(
        id="scandate_to_scans_tsv",
        from_version="1.6.0",
        category="cross_file_move",
        description="Move ScanDate from JSON sidecar to acq_time column in _scans.tsv",
        old_field="ScanDate",
    )
)


# ---------------------------------------------------------------------------
# Scanning and fixing logic
# ---------------------------------------------------------------------------


def _scan_json_files(dataset_root: Path) -> list[Path]:
    """Find all JSON sidecar files in the dataset."""
    return sorted(dataset_root.rglob("*.json"))


def _scan_for_field_rename(
    json_files: list[Path],
    rule: MigrationRule,
) -> list[MigrationFinding]:
    """Scan for deprecated metadata field names."""
    findings: list[MigrationFinding] = []
    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        if rule.old_field and rule.old_field in data:
            findings.append(
                MigrationFinding(
                    rule=rule,
                    file=jf,
                    current_value=f"{rule.old_field}: {data[rule.old_field]}",
                    proposed_value=f"{rule.new_field}: {data[rule.old_field]}",
                )
            )
    return findings


def _scan_for_enum_rename(
    json_files: list[Path],
    rule: MigrationRule,
) -> list[MigrationFinding]:
    """Scan for deprecated enum values."""
    findings: list[MigrationFinding] = []
    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        key = rule.metadata_key
        if key and key in data and data[key] == rule.old_value:
            findings.append(
                MigrationFinding(
                    rule=rule,
                    file=jf,
                    current_value=data[key],
                    proposed_value=rule.new_value,
                )
            )
    return findings


def _scan_for_path_format(
    json_files: list[Path],
    rule: MigrationRule,
) -> list[MigrationFinding]:
    """Scan for relative paths that should be BIDS URIs."""
    findings: list[MigrationFinding] = []
    key = rule.metadata_key
    if not key:
        return findings

    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict) or key not in data:
            continue

        value = data[key]
        paths_to_check: list[str] = []
        if isinstance(value, str):
            paths_to_check = [value]
        elif isinstance(value, list):
            paths_to_check = [v for v in value if isinstance(v, str)]

        for p in paths_to_check:
            if p and not p.startswith("bids:") and "/" in p:
                findings.append(
                    MigrationFinding(
                        rule=rule,
                        file=jf,
                        current_value=p,
                        proposed_value=f"bids::{p}",
                    )
                )
    return findings


def _scan_for_scandate(
    dataset_root: Path,
    json_files: list[Path],
    rule: MigrationRule,
) -> list[MigrationFinding]:
    """Scan for ScanDate in JSON sidecars (should move to _scans.tsv)."""
    findings: list[MigrationFinding] = []
    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        if "ScanDate" in data:
            findings.append(
                MigrationFinding(
                    rule=rule,
                    file=jf,
                    current_value=f"ScanDate: {data['ScanDate']}",
                    proposed_value="Move to acq_time in _scans.tsv",
                )
            )
    return findings


def _scan_for_doi_format(
    json_files: list[Path],
    rule: MigrationRule,
) -> list[MigrationFinding]:
    """Scan for bare DOIs that should be URI format."""
    findings: list[MigrationFinding] = []
    for jf in json_files:
        if not jf.name.endswith("dataset_description.json"):
            continue
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        doi = data.get("DatasetDOI", "")
        if isinstance(doi, str) and re.match(r"^10\.", doi):
            findings.append(
                MigrationFinding(
                    rule=rule,
                    file=jf,
                    current_value=doi,
                    proposed_value=f"doi:{doi}",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Apply fixes
# ---------------------------------------------------------------------------


def _apply_field_rename(finding: MigrationFinding) -> Change | None:
    """Apply a metadata field rename."""
    jf = finding.file
    try:
        data = json.loads(jf.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    rule = finding.rule
    if rule.old_field and rule.old_field in data:
        value = data.pop(rule.old_field)
        # Merge into new field (handle Sources consolidation)
        if rule.new_field:
            existing = data.get(rule.new_field)
            if existing is not None:
                # Merge lists
                if isinstance(existing, list) and isinstance(value, list):
                    data[rule.new_field] = existing + value
                elif isinstance(existing, list):
                    data[rule.new_field] = existing + [value]
                # else: existing value takes precedence
            else:
                data[rule.new_field] = value
        jf.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return Change(
            action="modify",
            source=jf,
            detail=f"Renamed field {rule.old_field} → {rule.new_field}",
        )
    return None


def _apply_enum_rename(finding: MigrationFinding) -> Change | None:
    """Apply an enum value rename."""
    jf = finding.file
    try:
        data = json.loads(jf.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    rule = finding.rule
    key = rule.metadata_key
    if key and key in data and data[key] == rule.old_value:
        data[key] = rule.new_value
        jf.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return Change(
            action="modify",
            source=jf,
            detail=f"Updated {key}: {rule.old_value} → {rule.new_value}",
        )
    return None


def _apply_path_format(finding: MigrationFinding) -> Change | None:
    """Convert relative path to BIDS URI."""
    jf = finding.file
    try:
        data = json.loads(jf.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    rule = finding.rule
    key = rule.metadata_key
    if not key or key not in data:
        return None

    modified = False
    value = data[key]
    if isinstance(value, str) and not value.startswith("bids:") and "/" in value:
        data[key] = f"bids::{value}"
        modified = True
    elif isinstance(value, list):
        new_list = []
        for v in value:
            if isinstance(v, str) and not v.startswith("bids:") and "/" in v:
                new_list.append(f"bids::{v}")
                modified = True
            else:
                new_list.append(v)
        data[key] = new_list

    if modified:
        jf.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return Change(
            action="modify",
            source=jf,
            detail=f"Converted {key} to BIDS URI format",
        )
    return None


def _apply_scandate_move(
    finding: MigrationFinding, dataset_root: Path
) -> Change | None:
    """Move ScanDate from JSON to _scans.tsv acq_time."""
    jf = finding.file
    try:
        data = json.loads(jf.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    scan_date = data.pop("ScanDate", None)
    if scan_date is None:
        return None

    jf.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    # Try to find the corresponding _scans.tsv and update acq_time
    scans_path = find_scans_tsv(jf, dataset_root)
    if scans_path is not None:
        rows = read_scans_tsv(scans_path)
        # Find the data file that corresponds to this JSON
        stem = jf.stem  # e.g., sub-01_bold
        for row in rows:
            fn = row.get("filename", "")
            if fn.replace(".nii.gz", "").replace(".nii", "").endswith(stem):
                if not row.get("acq_time"):
                    row["acq_time"] = scan_date
                break
        write_scans_tsv(scans_path, rows)

    return Change(
        action="modify",
        source=jf,
        detail=f"Moved ScanDate ({scan_date}) to _scans.tsv acq_time",
    )


def _apply_doi_format(finding: MigrationFinding) -> Change | None:
    """Convert bare DOI to URI format."""
    jf = finding.file
    try:
        data = json.loads(jf.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    doi = data.get("DatasetDOI", "")
    if isinstance(doi, str) and re.match(r"^10\.", doi):
        data["DatasetDOI"] = f"doi:{doi}"
        jf.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return Change(
            action="modify",
            source=jf,
            detail=f"Converted DatasetDOI to URI format: doi:{doi}",
        )
    return None


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def migrate_dataset(
    dataset: BIDSDataset,
    *,
    to_version: str | None = None,
    dry_run: bool = False,
) -> MigrationResult:
    """Apply schema-driven migrations to a BIDS dataset.

    Parameters
    ----------
    dataset
        The BIDS dataset to migrate.
    to_version
        Target BIDS version. If None, defaults to the current schema version.
    dry_run
        If True, scan and report findings without modifying files.

    Returns
    -------
    MigrationResult
        Findings and changes made (or planned).
    """
    from_version = dataset.bids_version

    if to_version is None:
        # Default to the schema's version
        to_version = dataset.schema.bids_version

    result = MigrationResult(
        dry_run=dry_run,
        from_version=from_version,
        to_version=to_version,
    )

    # Get applicable rules
    rules = _get_rules(from_version, to_version)

    if not rules:
        result.warnings.append("No applicable migration rules found")
        return result

    # Scan all JSON files
    json_files = _scan_json_files(dataset.root)

    # Scan for findings per rule category
    _SCANNERS: dict[str, Callable[..., list[MigrationFinding]]] = {
        "field_rename": lambda r: _scan_for_field_rename(json_files, r),
        "enum_rename": lambda r: _scan_for_enum_rename(json_files, r),
        "path_format": lambda r: _scan_for_path_format(json_files, r),
        "cross_file_move": lambda r: _scan_for_scandate(dataset.root, json_files, r),
        "value_rename": lambda r: _scan_for_doi_format(json_files, r),
    }

    for rule in rules:
        scanner = _SCANNERS.get(rule.category)
        if scanner:
            findings = scanner(rule)
            result.findings.extend(findings)

    if not result.findings:
        result.warnings.append("Nothing to migrate — dataset is up to date")
        return result

    if dry_run:
        return result

    # Apply fixes
    _APPLIERS: dict[str, Callable[..., Change | None]] = {
        "field_rename": lambda f: _apply_field_rename(f),
        "enum_rename": lambda f: _apply_enum_rename(f),
        "path_format": lambda f: _apply_path_format(f),
        "cross_file_move": lambda f: _apply_scandate_move(f, dataset.root),
        "value_rename": lambda f: _apply_doi_format(f),
    }

    for finding in result.findings:
        if not finding.can_auto_fix:
            result.warnings.append(
                f"Cannot auto-fix: {finding.file}: {finding.reason}"
            )
            continue

        applier = _APPLIERS.get(finding.rule.category)
        if applier:
            change = applier(finding)
            if change:
                result.changes.append(change)

    return result
