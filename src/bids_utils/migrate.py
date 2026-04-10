"""Schema-driven migration for BIDS datasets (User Stories 2, 3).

Handles 1.x deprecation fixes and 2.0 migration using rules derived
from bidsschematools.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bids_utils._dataset import BIDSDataset
from bids_utils._io import read_json as _read_json
from bids_utils._io import write_json as _write_json
from bids_utils._scans import find_scans_tsv, read_scans_tsv, write_scans_tsv
from bids_utils._types import AnnexedMode, BIDSPath, Change
from bids_utils._vcs import VCSBackend

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class MigrationRule:
    """A single migration rule."""

    id: str
    from_version: str
    category: str  # field_rename, value_rename, suffix_rename, etc.
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


def _get_rules(
    from_version: str, to_version: str, *, major_only: bool = False
) -> list[MigrationRule]:
    """Get applicable rules between two versions.

    Parameters
    ----------
    from_version
        Current dataset version.
    to_version
        Target version.
    major_only
        If True, only return rules for the target major version
        (e.g., only 2.0 rules, not 1.x rules).
    """
    from packaging.version import InvalidVersion, Version

    try:
        from_v = Version(from_version)
        to_v = Version(to_version)
    except InvalidVersion:
        return []

    applicable = []
    for rule in _RULES:
        try:
            rule_v = Version(rule.from_version)
        except Exception:
            continue

        if major_only:
            # Only include rules whose major version matches the target
            if rule_v.major != to_v.major:
                continue
            if rule_v <= to_v:
                applicable.append(rule)
        else:
            if from_v < rule_v <= to_v or rule_v <= from_v <= to_v:
                applicable.append(rule)

    return applicable


def _is_major_version_upgrade(from_version: str, to_version: str) -> bool:
    """Check if migration crosses a major version boundary."""
    from packaging.version import InvalidVersion, Version

    try:
        from_v = Version(from_version)
        to_v = Version(to_version)
    except InvalidVersion:
        return False
    return to_v.major > from_v.major


def _latest_1x_version() -> str:
    """Return the latest known 1.x BIDS version."""
    return "1.11.1"


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

# Suffix deprecations (T034)
# _phase -> _part-phase_bold (auto-fixable, func datatype only)
_register_rule(
    MigrationRule(
        id="suffix_phase_to_part_phase_bold",
        from_version="1.6.0",
        category="suffix_deprecation",
        description="Replace '_phase' suffix with 'part-phase' entity"
        " and 'bold' suffix",
        old_value="phase",
        new_value="bold",  # new suffix
        affected_suffixes=["phase"],
    )
)
# T2star -> ambiguous (T2starw or T2starmap) — not auto-fixable
_register_rule(
    MigrationRule(
        id="suffix_T2star_ambiguous",
        from_version="1.6.0",
        category="suffix_deprecation",
        description="Suffix 'T2star' is deprecated"
        " — replace with 'T2starw' or 'T2starmap'",
        old_value="T2star",
        affected_suffixes=["T2star"],
    )
)
# FLASH -> removed — not auto-fixable
_register_rule(
    MigrationRule(
        id="suffix_FLASH_removed",
        from_version="1.6.0",
        category="suffix_deprecation",
        description="Suffix 'FLASH' has been removed"
        " — use vendor-neutral suffix instead",
        old_value="FLASH",
        affected_suffixes=["FLASH"],
    )
)
# PD -> ambiguous (PDw or PDmap) — not auto-fixable
_register_rule(
    MigrationRule(
        id="suffix_PD_ambiguous",
        from_version="1.6.0",
        category="suffix_deprecation",
        description="Suffix 'PD' is deprecated — replace with 'PDw' or 'PDmap'",
        old_value="PD",
        affected_suffixes=["PD"],
    )
)

# Deprecated template identifiers in coordinate system fields (T035)
_COORDINATE_SYSTEM_KEYS = [
    "MEGCoordinateSystem",
    "EEGCoordinateSystem",
    "iEEGCoordinateSystem",
    "NIRSCoordinateSystem",
    "FiducialsCoordinateSystem",
    "AnatomicalLandmarkCoordinateSystem",
    "DigitizedHeadPointsCoordinateSystem",
    "DigitizedLandmarkCoordinateSystem",
]

_DEPRECATED_TEMPLATES = [
    "fsaverage3",
    "fsaverage4",
    "fsaverage5",
    "fsaverage6",
    "fsaveragesym",
    "UNCInfant0V21",
    "UNCInfant0V22",
    "UNCInfant0V23",
    "UNCInfant1V21",
    "UNCInfant1V22",
    "UNCInfant1V23",
    "UNCInfant2V21",
    "UNCInfant2V22",
    "UNCInfant2V23",
]

for tmpl in _DEPRECATED_TEMPLATES:
    _register_rule(
        MigrationRule(
            id=f"deprecated_template_{tmpl}",
            from_version="1.6.0",
            category="deprecated_template",
            description=f"Template identifier '{tmpl}' is deprecated",
            old_value=tmpl,
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
# BIDS 2.0 migration rules (placeholder infrastructure)
#
# The BIDS 2.0 schema is not yet finalized.  The rules below register the
# *categories* of change that 2.0 will require so that the engine, scanner,
# applier, and test infrastructure are exercised end-to-end.  Concrete rules
# will be added once the 2.0 schema stabilizes.
# ---------------------------------------------------------------------------

# NOTE: No concrete 2.0 rules are registered yet because the schema is not
# finalized.  When rules are added they should use from_version="2.0.0" and
# one of the 2.0-specific categories below:
#   - "entity_rename"         (entity key changes, e.g. hypothetical acq→acquisition)
#   - "structural_reorg"      (directory layout changes)
#   - "metadata_key_change"   (metadata key renames specific to 2.0)


# ---------------------------------------------------------------------------
# Scanning and fixing logic
# ---------------------------------------------------------------------------


def _read_json_safe(
    path: Path,
    vcs: VCSBackend | None,
    mode: AnnexedMode,
) -> dict[str, Any] | None:
    """Read JSON gracefully, delegating to ``_io.read_json``."""
    return _read_json(path, vcs, mode)


def _scan_json_files(dataset_root: Path) -> list[Path]:
    """Find all JSON sidecar files in the dataset."""
    return sorted(dataset_root.rglob("*.json"))


def _scan_for_field_rename(
    json_files: list[Path],
    rule: MigrationRule,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> list[MigrationFinding]:
    """Scan for deprecated metadata field names."""
    findings: list[MigrationFinding] = []
    for jf in json_files:
        data = _read_json_safe(jf, vcs, annexed_mode)
        if data is None:
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
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> list[MigrationFinding]:
    """Scan for deprecated enum values."""
    findings: list[MigrationFinding] = []
    for jf in json_files:
        data = _read_json_safe(jf, vcs, annexed_mode)
        if data is None:
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
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> list[MigrationFinding]:
    """Scan for relative paths that should be BIDS URIs."""
    findings: list[MigrationFinding] = []
    key = rule.metadata_key
    if not key:
        return findings

    for jf in json_files:
        data = _read_json_safe(jf, vcs, annexed_mode)
        if data is None or key not in data:
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
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> list[MigrationFinding]:
    """Scan for ScanDate in JSON sidecars (should move to _scans.tsv)."""
    findings: list[MigrationFinding] = []
    for jf in json_files:
        data = _read_json_safe(jf, vcs, annexed_mode)
        if data is None:
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
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> list[MigrationFinding]:
    """Scan for bare DOIs that should be URI format."""
    findings: list[MigrationFinding] = []
    for jf in json_files:
        if not jf.name.endswith("dataset_description.json"):
            continue
        data = _read_json_safe(jf, vcs, annexed_mode)
        if data is None:
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


def _scan_bids_files(dataset_root: Path) -> list[Path]:
    """Find all BIDS data files (non-JSON, non-TSV) in the dataset."""
    results: list[Path] = []
    for p in sorted(dataset_root.rglob("*")):
        if p.is_dir():
            continue
        # Skip non-BIDS directories
        rel = p.relative_to(dataset_root)
        parts = rel.parts
        if parts and parts[0] in (
            "derivatives",
            "sourcedata",
            "code",
            ".git",
            ".datalad",
        ):
            continue
        # Skip JSON sidecars, TSV files, and dataset_description
        if p.suffix in (".json", ".tsv"):
            continue
        results.append(p)
    return results


def _scan_for_suffix_deprecation(
    dataset_root: Path,
    rule: MigrationRule,
) -> list[MigrationFinding]:
    """Scan for files with deprecated suffixes."""
    findings: list[MigrationFinding] = []
    deprecated_suffix = rule.old_value
    if not deprecated_suffix:
        return findings

    bids_files = _scan_bids_files(dataset_root)
    for fp in bids_files:
        try:
            bp = BIDSPath.from_path(fp)
        except Exception:
            continue
        if bp.suffix != deprecated_suffix:
            continue

        if deprecated_suffix == "phase":
            # Auto-fixable: _phase -> _part-phase_bold
            findings.append(
                MigrationFinding(
                    rule=rule,
                    file=fp,
                    current_value=f"suffix={deprecated_suffix}",
                    proposed_value="suffix=bold, part=phase",
                    can_auto_fix=True,
                )
            )
        else:
            # T2star, FLASH, PD — ambiguous, cannot auto-fix
            findings.append(
                MigrationFinding(
                    rule=rule,
                    file=fp,
                    current_value=f"suffix={deprecated_suffix}",
                    proposed_value=rule.description,
                    can_auto_fix=False,
                    reason=rule.description,
                )
            )
    return findings


def _scan_for_deprecated_template(
    json_files: list[Path],
    rule: MigrationRule,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> list[MigrationFinding]:
    """Scan for deprecated template identifiers in coordinate system fields."""
    findings: list[MigrationFinding] = []
    deprecated_value = rule.old_value
    if not deprecated_value:
        return findings

    for jf in json_files:
        data = _read_json_safe(jf, vcs, annexed_mode)
        if data is None:
            continue

        for key in _COORDINATE_SYSTEM_KEYS:
            if key in data and data[key] == deprecated_value:
                findings.append(
                    MigrationFinding(
                        rule=rule,
                        file=jf,
                        current_value=f"{key}={deprecated_value}",
                        proposed_value=(
                            f"Replace '{deprecated_value}'"
                            " with a current template identifier"
                        ),
                        can_auto_fix=False,
                        reason=(
                            f"Template '{deprecated_value}' is deprecated;"
                            " replacement requires manual selection"
                        ),
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# 2.0-specific scanners
# ---------------------------------------------------------------------------


def _scan_for_entity_rename(
    dataset_root: Path,
    rule: MigrationRule,
) -> list[MigrationFinding]:
    """Scan for files using a deprecated entity key (2.0 migration)."""
    findings: list[MigrationFinding] = []
    old_key = rule.old_field
    new_key = rule.new_field
    if not old_key:
        return findings

    bids_files = _scan_bids_files(dataset_root)
    for fp in bids_files:
        try:
            bp = BIDSPath.from_path(fp)
        except Exception:
            continue
        if old_key in bp.entities:
            findings.append(
                MigrationFinding(
                    rule=rule,
                    file=fp,
                    current_value=f"{old_key}-{bp.entities[old_key]}",
                    proposed_value=f"{new_key}-{bp.entities[old_key]}",
                    can_auto_fix=True,
                )
            )
    return findings


def _scan_for_metadata_key_change(
    json_files: list[Path],
    rule: MigrationRule,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> list[MigrationFinding]:
    """Scan for metadata keys that changed in 2.0."""
    return _scan_for_field_rename(
        json_files, rule, vcs=vcs, annexed_mode=annexed_mode
    )


def _scan_for_structural_reorg(
    dataset_root: Path,
    rule: MigrationRule,
) -> list[MigrationFinding]:
    """Scan for structural layout issues requiring 2.0 reorganization.

    Structural reorganization rules are inherently ambiguous and require
    human judgment.  This scanner flags findings but marks them as not
    auto-fixable.
    """
    findings: list[MigrationFinding] = []
    # Structural reorg rules describe directory layout changes that cannot
    # be applied automatically without understanding dataset intent.
    # Flag the entire dataset as needing review.
    findings.append(
        MigrationFinding(
            rule=rule,
            file=dataset_root / "dataset_description.json",
            current_value="current layout",
            proposed_value=rule.description,
            can_auto_fix=False,
            reason=(
                "Structural reorganization requires human judgment;"
                " review the BIDS 2.0 specification for guidance"
            ),
        )
    )
    return findings


# ---------------------------------------------------------------------------
# 2.0-specific appliers
# ---------------------------------------------------------------------------


def _apply_entity_rename(
    finding: MigrationFinding, dataset: BIDSDataset
) -> Change | None:
    """Apply an entity key rename by delegating to rename_file()."""
    from bids_utils.rename import rename_file

    fp = finding.file
    rule = finding.rule
    old_key = rule.old_field
    new_key = rule.new_field
    if not old_key or not new_key:
        return None

    try:
        bp = BIDSPath.from_path(fp)
    except Exception:
        return None

    if old_key not in bp.entities:
        return None

    # Rename: drop old entity, add new entity with same value
    value = bp.entities[old_key]
    result = rename_file(
        dataset,
        fp,
        set_entities={new_key: value},
        drop_entities=[old_key],
    )
    if result.success and result.changes:
        return result.changes[0]
    return None


# ---------------------------------------------------------------------------
# Apply fixes
# ---------------------------------------------------------------------------


def _apply_field_rename(
    finding: MigrationFinding,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> Change | None:
    """Apply a metadata field rename."""
    jf = finding.file
    data = _read_json_safe(jf, vcs, annexed_mode)
    if data is None:
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
        if vcs is not None:
            _write_json(jf, data, vcs)
        else:
            jf.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
        return Change(
            action="modify",
            source=jf,
            detail=f"Renamed field {rule.old_field} → {rule.new_field}",
        )
    return None


def _apply_enum_rename(
    finding: MigrationFinding,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> Change | None:
    """Apply an enum value rename."""
    jf = finding.file
    data = _read_json_safe(jf, vcs, annexed_mode)
    if data is None:
        return None
    rule = finding.rule
    key = rule.metadata_key
    if key and key in data and data[key] == rule.old_value:
        data[key] = rule.new_value
        if vcs is not None:
            _write_json(jf, data, vcs)
        else:
            jf.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
        return Change(
            action="modify",
            source=jf,
            detail=f"Updated {key}: {rule.old_value} → {rule.new_value}",
        )
    return None


def _apply_path_format(
    finding: MigrationFinding,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> Change | None:
    """Convert relative path to BIDS URI."""
    jf = finding.file
    data = _read_json_safe(jf, vcs, annexed_mode)
    if data is None:
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
        if vcs is not None:
            _write_json(jf, data, vcs)
        else:
            jf.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
        return Change(
            action="modify",
            source=jf,
            detail=f"Converted {key} to BIDS URI format",
        )
    return None


def _apply_scandate_move(
    finding: MigrationFinding,
    dataset_root: Path,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> Change | None:
    """Move ScanDate from JSON to _scans.tsv acq_time."""
    jf = finding.file
    data = _read_json_safe(jf, vcs, annexed_mode)
    if data is None:
        return None

    scan_date = data.pop("ScanDate", None)
    if scan_date is None:
        return None

    if vcs is not None:
        _write_json(jf, data, vcs)
    else:
        jf.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    # Try to find the corresponding _scans.tsv and update acq_time
    scans_path = find_scans_tsv(jf, dataset_root)
    if scans_path is not None:
        rows = read_scans_tsv(
            scans_path, vcs=vcs, annexed_mode=annexed_mode
        )
        # Find the data file that corresponds to this JSON
        stem = jf.stem  # e.g., sub-01_bold
        for row in rows:
            fn = row.get("filename", "")
            if fn.replace(".nii.gz", "").replace(".nii", "").endswith(stem):
                if not row.get("acq_time"):
                    row["acq_time"] = scan_date
                break
        write_scans_tsv(scans_path, rows, vcs=vcs)

    return Change(
        action="modify",
        source=jf,
        detail=f"Moved ScanDate ({scan_date}) to _scans.tsv acq_time",
    )


def _apply_doi_format(
    finding: MigrationFinding,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> Change | None:
    """Convert bare DOI to URI format."""
    jf = finding.file
    data = _read_json_safe(jf, vcs, annexed_mode)
    if data is None:
        return None
    doi = data.get("DatasetDOI", "")
    if isinstance(doi, str) and re.match(r"^10\.", doi):
        data["DatasetDOI"] = f"doi:{doi}"
        if vcs is not None:
            _write_json(jf, data, vcs)
        else:
            jf.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
        return Change(
            action="modify",
            source=jf,
            detail=f"Converted DatasetDOI to URI format: doi:{doi}",
        )
    return None


def _apply_suffix_deprecation(
    finding: MigrationFinding, dataset: BIDSDataset
) -> Change | None:
    """Apply suffix deprecation fix by delegating to rename_file()."""
    from bids_utils.rename import rename_file

    fp = finding.file
    bp = BIDSPath.from_path(fp)

    if bp.suffix == "phase":
        # _phase -> _part-phase_bold
        result = rename_file(
            dataset,
            fp,
            set_entities={"part": "phase"},
            new_suffix="bold",
        )
        if result.success and result.changes:
            return result.changes[0]
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

    When the target is a major version upgrade (e.g., 1.x → 2.0), migration
    is **cumulative**: all 1.x deprecation fixes are applied first, then
    2.0-specific transformations.

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

    is_major_upgrade = _is_major_version_upgrade(from_version, to_version)

    if is_major_upgrade:
        # Cumulative migration: apply all 1.x fixes first, then 2.0 rules
        latest_1x = _latest_1x_version()
        onex_rules = _get_rules(from_version, latest_1x)
        twox_rules = _get_rules(from_version, to_version, major_only=True)
        rules = onex_rules + twox_rules
    else:
        rules = _get_rules(from_version, to_version)

    if not rules:
        result.warnings.append("No applicable migration rules found")
        return result

    # Scan all JSON files
    json_files = _scan_json_files(dataset.root)
    vcs = dataset.vcs
    amode = dataset.annexed_mode

    # Scan for findings per rule category
    scanners: dict[str, Callable[..., list[MigrationFinding]]] = {
        "field_rename": lambda r: _scan_for_field_rename(
            json_files, r, vcs=vcs, annexed_mode=amode
        ),
        "enum_rename": lambda r: _scan_for_enum_rename(
            json_files, r, vcs=vcs, annexed_mode=amode
        ),
        "path_format": lambda r: _scan_for_path_format(
            json_files, r, vcs=vcs, annexed_mode=amode
        ),
        "cross_file_move": lambda r: _scan_for_scandate(
            dataset.root, json_files, r, vcs=vcs, annexed_mode=amode
        ),
        "value_rename": lambda r: _scan_for_doi_format(
            json_files, r, vcs=vcs, annexed_mode=amode
        ),
        "suffix_deprecation": lambda r: _scan_for_suffix_deprecation(
            dataset.root, r
        ),
        "deprecated_template": lambda r: _scan_for_deprecated_template(
            json_files, r, vcs=vcs, annexed_mode=amode
        ),
        # 2.0-specific categories
        "entity_rename": lambda r: _scan_for_entity_rename(dataset.root, r),
        "metadata_key_change": lambda r: _scan_for_metadata_key_change(
            json_files, r, vcs=vcs, annexed_mode=amode
        ),
        "structural_reorg": lambda r: _scan_for_structural_reorg(
            dataset.root, r
        ),
    }

    for rule in rules:
        scanner = scanners.get(rule.category)
        if scanner:
            findings = scanner(rule)
            result.findings.extend(findings)

    if not result.findings:
        result.warnings.append("Nothing to migrate — dataset is up to date")
        return result

    # T043: Check for ambiguities that should abort migration
    unfixable = [f for f in result.findings if not f.can_auto_fix]
    if is_major_upgrade and unfixable and not dry_run:
        # For major version upgrades, unfixable findings abort the migration
        # rather than partially applying (user must resolve ambiguities first)
        result.success = False
        for f in unfixable:
            result.errors.append(
                f"Cannot auto-fix ({f.rule.id}): {f.file}: {f.reason}"
            )
        result.warnings.append(
            "Migration aborted: resolve the above ambiguities manually "
            "before migrating to a new major version. "
            "Run with --dry-run to see all findings."
        )
        return result

    if dry_run:
        return result

    # Apply fixes
    appliers: dict[str, Callable[..., Change | None]] = {
        "field_rename": lambda f: _apply_field_rename(
            f, vcs=vcs, annexed_mode=amode
        ),
        "enum_rename": lambda f: _apply_enum_rename(
            f, vcs=vcs, annexed_mode=amode
        ),
        "path_format": lambda f: _apply_path_format(
            f, vcs=vcs, annexed_mode=amode
        ),
        "cross_file_move": lambda f: _apply_scandate_move(
            f, dataset.root, vcs=vcs, annexed_mode=amode
        ),
        "value_rename": lambda f: _apply_doi_format(
            f, vcs=vcs, annexed_mode=amode
        ),
        "suffix_deprecation": lambda f: _apply_suffix_deprecation(f, dataset),
        # 2.0-specific appliers
        "entity_rename": lambda f: _apply_entity_rename(f, dataset),
        "metadata_key_change": lambda f: _apply_field_rename(
            f, vcs=vcs, annexed_mode=amode
        ),
        # deprecated_template, structural_reorg: no applier — can_auto_fix=False
    }

    for finding in result.findings:
        if not finding.can_auto_fix:
            result.warnings.append(f"Cannot auto-fix: {finding.file}: {finding.reason}")
            continue

        applier = appliers.get(finding.rule.category)
        if applier:
            change = applier(finding)
            if change:
                result.changes.append(change)

    return result
