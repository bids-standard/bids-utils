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
from bids_utils._participants import read_participants_tsv, write_participants_tsv
from bids_utils._scans import find_scans_tsv, read_scans_tsv, write_scans_tsv
from bids_utils._types import AnnexedMode, BIDSPath, Change, _is_bids_data_entry
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
    level: str = "safe"  # "safe", "advisory", "non-auto-fixable"
    old_field: str | None = None
    new_field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    affected_suffixes: list[str] = field(default_factory=list)
    metadata_key: str | None = None  # for value renames: which metadata key
    handler: Callable[..., list[MigrationFinding]] | None = field(
        default=None, repr=False
    )
    condition: Callable[..., bool] | None = field(default=None, repr=False)


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


_LEVEL_TIERS: dict[str, set[str]] = {
    "safe": {"safe"},
    "advisory": {"safe", "advisory"},
    "all": {"safe", "advisory", "non-auto-fixable"},
}


def _get_rules(
    from_version: str,
    to_version: str,
    *,
    major_only: bool = False,
    level: str = "all",
    rule_ids: list[str] | None = None,
    exclude_rules: list[str] | None = None,
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
    level
        Filter by migration level tier: ``"safe"``, ``"advisory"``,
        or ``"all"``.
    rule_ids
        If provided, only include rules whose id is in this list (whitelist).
    exclude_rules
        If provided, exclude rules whose id is in this list (blacklist).
    """
    from packaging.version import InvalidVersion, Version

    try:
        from_v = Version(from_version)
        to_v = Version(to_version)
    except InvalidVersion:
        return []

    allowed_levels = _LEVEL_TIERS.get(level, _LEVEL_TIERS["all"])
    rule_id_set = set(rule_ids) if rule_ids else None
    exclude_set = set(exclude_rules) if exclude_rules else None

    applicable = []
    for rule in _RULES:
        try:
            rule_v = Version(rule.from_version)
        except Exception:
            continue

        # Level filtering
        if rule.level not in allowed_levels:
            continue

        # Whitelist filtering
        if rule_id_set is not None and rule.id not in rule_id_set:
            continue

        # Blacklist filtering
        if exclude_set is not None and rule.id in exclude_set:
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
        level="non-auto-fixable",
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
        level="non-auto-fixable",
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
        level="non-auto-fixable",
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
            level="non-auto-fixable",
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

# AcquisitionDuration -> FrameAcquisitionDuration (conditional on VolumeTiming)
_register_rule(
    MigrationRule(
        id="field_rename_AcquisitionDuration_to_FrameAcquisitionDuration",
        from_version="1.6.0",
        level="safe",
        category="field_rename",
        description=(
            "Rename 'AcquisitionDuration' to 'FrameAcquisitionDuration'"
            " (when VolumeTiming present)"
        ),
        old_field="AcquisitionDuration",
        new_field="FrameAcquisitionDuration",
        condition=lambda data: "VolumeTiming" in data,
    )
)
_register_rule(
    MigrationRule(
        id="field_AcquisitionDuration_without_VolumeTiming",
        from_version="1.6.0",
        level="advisory",
        category="field_rename",
        description="AcquisitionDuration found without VolumeTiming — ambiguous rename",
        old_field="AcquisitionDuration",
        new_field="FrameAcquisitionDuration",
        condition=lambda data: "VolumeTiming" not in data,
    )
)

# Structural migration: DCOffsetCorrection -> SoftwareFilters sub-entry
_register_rule(
    MigrationRule(
        id="dcoffset_to_softwarefilters",
        from_version="1.6.0",
        level="safe",
        category="field_nest",
        description=(
            "Move 'DCOffsetCorrection' into SoftwareFilters sub-entry (iEEG)"
        ),
        old_field="DCOffsetCorrection",
        new_field="SoftwareFilters",
    )
)
# Field removals (deprecated fields)
_register_rule(
    MigrationRule(
        id="field_removal_HardcopyDeviceSoftwareVersion",
        from_version="1.6.0",
        level="advisory",
        category="field_removal",
        description="Remove deprecated 'HardcopyDeviceSoftwareVersion' field (MRI)",
        old_field="HardcopyDeviceSoftwareVersion",
    )
)

# Age 89+ rules (participants.tsv)
_register_rule(
    MigrationRule(
        id="age_89plus_string",
        from_version="1.6.0",
        level="safe",
        category="tsv_column_value",
        description="Convert string '89+' in age column to numeric 89",
        old_field="age",
        old_value="89+",
        new_value="89",
    )
)
_register_rule(
    MigrationRule(
        id="age_cap_89",
        from_version="1.6.0",
        level="advisory",
        category="tsv_column_value",
        description="Cap numeric age values > 89 to 89",
        old_field="age",
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
    """Find all JSON sidecar files in the dataset (skips dotdirs)."""
    results: list[Path] = []
    for p in sorted(dataset_root.rglob("*.json")):
        rel = p.relative_to(dataset_root)
        if rel.parts and rel.parts[0].startswith("."):
            continue
        results.append(p)
    return results


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
            # Check condition if present
            if rule.condition is not None:
                cond_result = rule.condition(data)
                if not cond_result:
                    # Condition not met
                    if rule.level in ("advisory", "non-auto-fixable"):
                        # For advisory/non-auto-fixable rules whose condition
                        # is False, skip (the paired rule handles it)
                        continue
                    # For safe rules whose condition is False, skip silently
                    # (the separate advisory rule will catch it)
                    continue
            findings.append(
                MigrationFinding(
                    rule=rule,
                    file=jf,
                    current_value=f"{rule.old_field}: {data[rule.old_field]}",
                    proposed_value=f"{rule.new_field}: {data[rule.old_field]}",
                    can_auto_fix=rule.level == "safe",
                    reason=(
                        None
                        if rule.level == "safe"
                        else rule.description
                    ),
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
        if not _is_bids_data_entry(p):
            continue
        # Skip non-BIDS directories
        rel = p.relative_to(dataset_root)
        parts = rel.parts
        if parts and (
            parts[0].startswith(".")  # dotdirs: .git, .datalad, etc.
            or parts[0] in ("derivatives", "sourcedata", "code")
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


def _scan_for_field_removal(
    json_files: list[Path],
    rule: MigrationRule,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> list[MigrationFinding]:
    """Scan for deprecated metadata fields that should be removed."""
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
                    proposed_value=f"Remove '{rule.old_field}'",
                    can_auto_fix=True,
                )
            )
    return findings


def _scan_for_field_nest(
    json_files: list[Path],
    rule: MigrationRule,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> list[MigrationFinding]:
    """Scan for fields that should be nested under another metadata key.

    Currently targets the iEEG DCOffsetCorrection → SoftwareFilters
    structural migration: restricted to sidecars in an ``ieeg`` datatype
    directory.
    """
    findings: list[MigrationFinding] = []
    if not rule.old_field or not rule.new_field:
        return findings
    for jf in json_files:
        # Restrict to iEEG sidecars (scope per FR-031)
        if jf.parent.name != "ieeg":
            continue
        data = _read_json_safe(jf, vcs, annexed_mode)
        if data is None:
            continue
        if rule.old_field in data:
            findings.append(
                MigrationFinding(
                    rule=rule,
                    file=jf,
                    current_value=f"{rule.old_field}: {data[rule.old_field]}",
                    proposed_value=(
                        f"{rule.new_field}.{rule.old_field}.description: "
                        f"{data[rule.old_field]}"
                    ),
                    can_auto_fix=True,
                )
            )
    return findings


def _scan_for_age_column(
    dataset_root: Path,
    rule: MigrationRule,
) -> list[MigrationFinding]:
    """Scan participants.tsv for age values requiring migration."""
    findings: list[MigrationFinding] = []
    participants_tsv = dataset_root / "participants.tsv"
    if not participants_tsv.exists():
        return findings

    rows = read_participants_tsv(participants_tsv)
    if not rows:
        return findings

    # Check if 'age' column exists
    if "age" not in rows[0]:
        return findings

    # Unit check: read participants.json if it exists
    participants_json = dataset_root / "participants.json"
    if participants_json.exists():
        try:
            sidecar = json.loads(participants_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            sidecar = {}
        age_meta = sidecar.get("age", {})
        units = age_meta.get("Units", "")
        if units and units.lower() not in ("year", "years", ""):
            # Non-year units — produce a non-auto-fixable finding
            # so the user knows WHY the rule was skipped
            findings.append(
                MigrationFinding(
                    rule=rule,
                    file=participants_tsv,
                    current_value=f"age column units={units}",
                    proposed_value="skipped (89-year threshold applies to years only)",
                    can_auto_fix=False,
                    reason=f"Age column has units '{units}' — 89-year threshold "
                    "does not apply to non-year units",
                )
            )
            return findings

    for i, row in enumerate(rows):
        age_val = row.get("age", "")
        if not age_val or age_val == "n/a":
            continue

        if rule.id == "age_89plus_string":
            if age_val == "89+":
                findings.append(
                    MigrationFinding(
                        rule=rule,
                        file=participants_tsv,
                        current_value=f"age='89+' (row {i})",
                        proposed_value="age=89",
                        can_auto_fix=True,
                    )
                )
        elif rule.id == "age_cap_89":
            try:
                numeric_age = float(age_val)
            except ValueError:
                continue
            if numeric_age > 89:
                findings.append(
                    MigrationFinding(
                        rule=rule,
                        file=participants_tsv,
                        current_value=f"age={age_val} (row {i})",
                        proposed_value="age=89",
                        can_auto_fix=True,
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


def _apply_field_removal(
    finding: MigrationFinding,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> Change | None:
    """Remove a deprecated metadata field from a JSON sidecar."""
    jf = finding.file
    data = _read_json_safe(jf, vcs, annexed_mode)
    if data is None:
        return None
    rule = finding.rule
    if rule.old_field and rule.old_field in data:
        data.pop(rule.old_field)
        if vcs is not None:
            _write_json(jf, data, vcs)
        else:
            jf.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
        return Change(
            action="modify",
            source=jf,
            detail=f"Removed deprecated field '{rule.old_field}'",
        )
    return None


def _apply_field_nest(
    finding: MigrationFinding,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> Change | None:
    """Move a flat field into a nested dict under ``new_field``.

    For DCOffsetCorrection: produces
    ``SoftwareFilters[DCOffsetCorrection] = {"description": value}``.
    Preserves an existing ``SoftwareFilters`` dict and does not overwrite
    an existing nested description.
    """
    jf = finding.file
    data = _read_json_safe(jf, vcs, annexed_mode)
    if data is None:
        return None
    rule = finding.rule
    if not rule.old_field or not rule.new_field:
        return None
    if rule.old_field not in data:
        return None
    value = data.pop(rule.old_field)
    container = data.get(rule.new_field)
    if not isinstance(container, dict):
        container = {}
    existing_entry = container.get(rule.old_field)
    if isinstance(existing_entry, dict):
        existing_entry.setdefault("description", value)
    else:
        container[rule.old_field] = {"description": value}
    data[rule.new_field] = container
    if vcs is not None:
        _write_json(jf, data, vcs)
    else:
        jf.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
    return Change(
        action="modify",
        source=jf,
        detail=(
            f"Moved '{rule.old_field}' into '{rule.new_field}' sub-entry"
        ),
    )


def _apply_age_column(
    finding: MigrationFinding,
    dataset_root: Path,
    vcs: VCSBackend | None = None,
) -> Change | None:
    """Apply age value fixes in participants.tsv."""
    participants_tsv = dataset_root / "participants.tsv"
    if not participants_tsv.exists():
        return None

    rows = read_participants_tsv(participants_tsv, vcs=vcs)
    if not rows:
        return None

    rule = finding.rule
    modified = False

    for row in rows:
        age_val = row.get("age", "")
        if not age_val or age_val == "n/a":
            continue

        if rule.id == "age_89plus_string":
            if age_val == "89+":
                row["age"] = "89"
                modified = True
        elif rule.id == "age_cap_89":
            try:
                numeric_age = float(age_val)
            except ValueError:
                continue
            if numeric_age > 89:
                row["age"] = "89"
                modified = True

    if modified:
        write_participants_tsv(participants_tsv, rows, vcs=vcs)
        return Change(
            action="modify",
            source=participants_tsv,
            detail=f"Applied age migration rule '{rule.id}'",
        )
    return None


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
        # Merge into new field (handle Sources consolidation).
        # Normalize both sides to lists so mixed string/array types merge
        # correctly; 3-way merges (e.g. Sources + BasedOn + RawSources) work
        # iteratively as each rule runs.
        if rule.new_field:
            existing = data.get(rule.new_field)
            if existing is None:
                data[rule.new_field] = value
            else:
                existing_list = (
                    list(existing) if isinstance(existing, list) else [existing]
                )
                value_list = list(value) if isinstance(value, list) else [value]
                data[rule.new_field] = existing_list + value_list
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


def _default_scans_tsv_path(jf: Path, dataset_root: Path) -> Path | None:
    """Compute the canonical ``_scans.tsv`` location for a sidecar.

    Uses the sidecar's ``sub``/``ses`` entities to derive the conventional
    path (e.g. ``sub-01/ses-pre/sub-01_ses-pre_scans.tsv``).  Returns
    ``None`` if the sidecar does not carry a subject entity.
    """
    try:
        bp = BIDSPath.from_path(jf)
    except Exception:
        return None
    sub = bp.entities.get("sub")
    if not sub:
        return None
    ses = bp.entities.get("ses")
    if ses:
        container = dataset_root / f"sub-{sub}" / f"ses-{ses}"
        name = f"sub-{sub}_ses-{ses}_scans.tsv"
    else:
        container = dataset_root / f"sub-{sub}"
        name = f"sub-{sub}_scans.tsv"
    return container / name


def _scans_tsv_filename_entry(jf: Path, scans_path: Path) -> str:
    """Build the ``filename`` column entry for a sidecar row.

    Looks for a sibling data file (non-JSON, non-TSV) sharing the
    sidecar's stem; falls back to the sidecar's stem with ``.nii.gz``
    when none is found (synthetic datasets, JSON-only sidecars).
    """
    stem = jf.stem
    data_name: str | None = None
    if jf.parent.exists():
        for sibling in sorted(jf.parent.iterdir()):
            if sibling.name == jf.name:
                continue
            if sibling.suffix in (".json", ".tsv"):
                continue
            if not _is_bids_data_entry(sibling):
                continue
            sib_stem = sibling.name
            # Strip compound extensions for comparison
            for ext in (".nii.gz", ".tsv.gz"):
                if sib_stem.endswith(ext):
                    sib_stem = sib_stem[: -len(ext)]
                    break
            else:
                sib_stem = Path(sibling.name).stem
            if sib_stem == stem:
                data_name = sibling.name
                break
    if data_name is None:
        data_name = f"{stem}.nii.gz"
    try:
        return str(jf.parent.joinpath(data_name).relative_to(scans_path.parent))
    except ValueError:
        return data_name


def _apply_scandate_move(
    finding: MigrationFinding,
    dataset_root: Path,
    vcs: VCSBackend | None = None,
    annexed_mode: AnnexedMode = AnnexedMode.ERROR,
) -> Change | None:
    """Move ScanDate from JSON to _scans.tsv acq_time.

    If no ``_scans.tsv`` exists yet for the subject/session, one is
    created with the required ``filename``/``acq_time`` headers so the
    ScanDate value is never dropped silently.
    """
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

    # Try to find the corresponding _scans.tsv; create one if missing.
    scans_path = find_scans_tsv(jf, dataset_root)
    created_new = False
    if scans_path is None:
        scans_path = _default_scans_tsv_path(jf, dataset_root)
        if scans_path is None:
            # Cannot safely place a scans file — restore ScanDate rather
            # than drop it silently.
            data["ScanDate"] = scan_date
            if vcs is not None:
                _write_json(jf, data, vcs)
            else:
                jf.write_text(
                    json.dumps(data, indent=2) + "\n", encoding="utf-8"
                )
            return None
        scans_path.parent.mkdir(parents=True, exist_ok=True)
        created_new = True

    if created_new:
        rows: list[dict[str, str]] = []
    else:
        rows = read_scans_tsv(
            scans_path, vcs=vcs, annexed_mode=annexed_mode
        )

    stem = jf.stem  # e.g., sub-01_bold
    matched = False
    for row in rows:
        fn = row.get("filename", "")
        if fn.replace(".nii.gz", "").replace(".nii", "").endswith(stem):
            if not row.get("acq_time"):
                row["acq_time"] = scan_date
            matched = True
            break

    if not matched:
        filename_entry = _scans_tsv_filename_entry(jf, scans_path)
        rows.append({"filename": filename_entry, "acq_time": scan_date})

    # write_tsv is a no-op on empty rows, so ensure we always have content
    # (we just appended above when the file was new).
    write_scans_tsv(scans_path, rows, vcs=vcs)

    detail = (
        f"Moved ScanDate ({scan_date}) to {scans_path.name}:acq_time"
        + (" (created)" if created_new else "")
    )
    return Change(action="modify", source=jf, detail=detail)


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
    level: str = "all",
    mode: str = "auto",
    rule_ids: list[str] | None = None,
    exclude_rules: list[str] | None = None,
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
    level
        Filter by migration level tier: ``"safe"``, ``"advisory"``,
        or ``"all"``.  The default ``"all"`` includes every rule.
    mode
        Interaction mode: ``"auto"`` (behaves like ``"non-interactive"``
        for now), ``"non-interactive"`` (skip non-auto-fixable findings),
        or ``"interactive"`` (prompt — not yet implemented).
    rule_ids
        If provided, only run rules whose id is in this list (whitelist).
    exclude_rules
        If provided, skip rules whose id is in this list (blacklist).

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

    filter_kwargs: dict[str, Any] = {
        "level": level,
        "rule_ids": rule_ids,
        "exclude_rules": exclude_rules,
    }

    if is_major_upgrade:
        # Cumulative migration: apply all 1.x fixes first, then 2.0 rules
        latest_1x = _latest_1x_version()
        onex_rules = _get_rules(from_version, latest_1x, **filter_kwargs)
        twox_rules = _get_rules(
            from_version, to_version, major_only=True, **filter_kwargs
        )
        rules = onex_rules + twox_rules
    else:
        rules = _get_rules(from_version, to_version, **filter_kwargs)

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
        "field_removal": lambda r: _scan_for_field_removal(
            json_files, r, vcs=vcs, annexed_mode=amode
        ),
        "field_nest": lambda r: _scan_for_field_nest(
            json_files, r, vcs=vcs, annexed_mode=amode
        ),
        "tsv_column_value": lambda r: _scan_for_age_column(
            dataset.root, r
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
        "field_removal": lambda f: _apply_field_removal(
            f, vcs=vcs, annexed_mode=amode
        ),
        "field_nest": lambda f: _apply_field_nest(
            f, vcs=vcs, annexed_mode=amode
        ),
        "tsv_column_value": lambda f: _apply_age_column(
            f, dataset.root, vcs=vcs
        ),
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
