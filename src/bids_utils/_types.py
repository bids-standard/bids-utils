"""Core type definitions for bids-utils."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal


class AnnexedMode(Enum):
    """Policy for handling git-annex files without local content."""

    ERROR = "error"
    GET = "get"
    SKIP_WARNING = "skip-warning"
    SKIP = "skip"


class MigrationLevel(str, Enum):
    """Tier of a migration rule."""

    SAFE = "safe"
    ADVISORY = "advisory"
    NON_AUTO_FIXABLE = "non-auto-fixable"


class MigrationMode(str, Enum):
    """Interaction mode for migration."""

    AUTO = "auto"
    NON_INTERACTIVE = "non-interactive"
    INTERACTIVE = "interactive"


class ContentNotAvailableError(FileNotFoundError):
    """Raised when annexed file content is not locally available."""

    def __init__(self, path: Path, hint: str = "") -> None:
        self.path = path
        msg = f"Content not available for annexed file: {path}"
        if hint:
            msg += f"\n{hint}"
        super().__init__(msg)


@dataclass(frozen=True)
class Entity:
    """A BIDS key-value pair (e.g., sub-01, task-rest)."""

    key: str
    value: str

    def __str__(self) -> str:
        return f"{self.key}-{self.value}"


def rename_change(source: Path, target: Path, detail: str) -> Change:
    """Create a rename :class:`Change`."""
    return Change(action="rename", source=source, target=target, detail=detail)


@dataclass
class BIDSPath:
    """A parsed BIDS file path decomposed into entities, suffix, and extension.

    Parses BIDS filenames of the form:
        key1-val1[_key2-val2[...]]_suffix.extension
    """

    entities: dict[str, str]
    suffix: str
    extension: str
    datatype: str = ""

    # Regex: greedy match of key-value pairs, then suffix and extension
    _ENTITY_PATTERN: re.Pattern[str] = field(
        default=re.compile(r"([a-zA-Z0-9]+)-([a-zA-Z0-9]+)"),
        init=False,
        repr=False,
        compare=False,
    )

    _EXT_PATTERN: re.Pattern[str] = field(
        default=re.compile(r"(\.[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)?)$"),
        init=False,
        repr=False,
        compare=False,
    )

    @classmethod
    def from_path(cls, path: str | Path) -> BIDSPath:
        """Parse a BIDS file path into its components.

        Works with both full paths and bare filenames.  Handles compound
        extensions like ``.nii.gz``.

        Does NOT require a schema — this is pure filename parsing.
        """
        path = Path(path)
        filename = path.name
        datatype = ""

        # Detect datatype from parent directory if present
        if path.parent != Path("."):
            parts = path.parts
            # datatype is the immediate parent (func/, anat/, fmap/, etc.)
            datatype = parts[-2] if len(parts) >= 2 else ""

        # Extract extension (handle .nii.gz)
        ext_match = re.search(r"(\.nii\.gz|\.tsv\.gz|\.[a-zA-Z0-9]+)$", filename)
        if ext_match:
            extension = ext_match.group(1)
            stem = filename[: ext_match.start()]
        else:
            extension = ""
            stem = filename

        # Split stem by underscores
        parts_list = stem.split("_")

        # Last part is the suffix (e.g., bold, T1w, events)
        entities: dict[str, str] = {}
        suffix = ""

        for i, part in enumerate(parts_list):
            m = re.fullmatch(r"([a-zA-Z0-9]+)-(.+)", part)
            if m:
                entities[m.group(1)] = m.group(2)
            else:
                # If it's the last part, it's the suffix
                if i == len(parts_list) - 1:
                    suffix = part
                # Otherwise it's a non-standard segment — keep as-is in suffix
                # (handles malformed filenames gracefully)
                else:
                    # Accumulate non-entity parts into a combined suffix later
                    suffix = "_".join(parts_list[i:])
                    break

        return cls(
            entities=entities,
            suffix=suffix,
            extension=extension,
            datatype=datatype,
        )

    def to_filename(self) -> str:
        """Reconstruct the BIDS filename from components."""
        parts = [f"{k}-{v}" for k, v in self.entities.items()]
        if self.suffix:
            parts.append(self.suffix)
        return "_".join(parts) + self.extension

    def to_relative_path(self) -> Path:
        """Reconstruct a relative path including sub-/ses-/datatype dirs."""
        parts: list[str] = []
        if "sub" in self.entities:
            parts.append(f"sub-{self.entities['sub']}")
        if "ses" in self.entities:
            parts.append(f"ses-{self.entities['ses']}")
        if self.datatype:
            parts.append(self.datatype)
        parts.append(self.to_filename())
        return Path(*parts)

    def with_entities(self, **overrides: str) -> BIDSPath:
        """Return a new BIDSPath with updated entities."""
        new_entities = {**self.entities, **overrides}
        return BIDSPath(
            entities=new_entities,
            suffix=self.suffix,
            extension=self.extension,
            datatype=self.datatype,
        )

    def with_suffix(self, suffix: str) -> BIDSPath:
        """Return a new BIDSPath with a different suffix."""
        return BIDSPath(
            entities=dict(self.entities),
            suffix=suffix,
            extension=self.extension,
            datatype=self.datatype,
        )

    def with_extension(self, extension: str) -> BIDSPath:
        """Return a new BIDSPath with a different extension."""
        return BIDSPath(
            entities=dict(self.entities),
            suffix=self.suffix,
            extension=extension,
            datatype=self.datatype,
        )


@dataclass
class Change:
    """A single change made (or planned) by an operation."""

    action: Literal["rename", "delete", "create", "modify"]
    source: Path
    target: Path | None = None
    detail: str = ""


@dataclass
class OperationResult:
    """Result of a mutating bids-utils operation."""

    success: bool = True
    dry_run: bool = False
    changes: list[Change] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-friendly dict."""
        return {
            "success": self.success,
            "dry_run": self.dry_run,
            "changes": [
                {
                    "action": c.action,
                    "source": str(c.source),
                    "target": str(c.target) if c.target else None,
                    "detail": c.detail,
                }
                for c in self.changes
            ],
            "warnings": self.warnings,
            "errors": self.errors,
        }


def normalize_subject_id(label: str) -> str:
    """Ensure a subject label has the ``sub-`` prefix."""
    return label if label.startswith("sub-") else f"sub-{label}"


def require_subject_dir(
    dataset_root: Path,
    sub_id: str,
    result: OperationResult,
) -> Path | None:
    """Validate that a subject directory exists under *dataset_root*.

    On success, return the directory ``Path``.  On failure, mark *result*
    as failed and return ``None``.
    """
    sub_dir = dataset_root / sub_id
    if not sub_dir.is_dir():
        result.success = False
        result.errors.append(f"Subject directory not found: {sub_dir}")
        return None
    return sub_dir
