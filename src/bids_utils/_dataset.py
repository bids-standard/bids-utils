"""BIDS dataset discovery and representation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from bids_utils._types import AnnexedMode

if TYPE_CHECKING:
    from bids_utils._schema import BIDSSchema
    from bids_utils._vcs import VCSBackend


@dataclass
class BIDSDataset:
    """Represents a BIDS dataset rooted at a dataset_description.json file."""

    root: Path
    bids_version: str
    schema_version: str | None = None
    annexed_mode: AnnexedMode = AnnexedMode.ERROR
    _vcs: VCSBackend | None = field(default=None, repr=False)

    @classmethod
    def from_path(cls, path: str | Path) -> BIDSDataset:
        """Find and load a BIDS dataset from any path within it.

        Walks up from *path* to find dataset_description.json.

        Raises
        ------
        FileNotFoundError
            If no dataset_description.json is found.
        ValueError
            If dataset_description.json is malformed.
        """
        path = Path(path).resolve()
        search = path if path.is_dir() else path.parent

        while True:
            desc_file = search / "dataset_description.json"
            if desc_file.is_file():
                try:
                    desc = json.loads(desc_file.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    msg = f"Malformed dataset_description.json: {desc_file}"
                    raise ValueError(msg) from exc

                bids_version = desc.get("BIDSVersion", "")
                if not bids_version:
                    msg = f"Missing BIDSVersion in {desc_file}"
                    raise ValueError(msg)

                return cls(root=search, bids_version=bids_version)

            parent = search.parent
            if parent == search:
                break
            search = parent

        msg = f"No dataset_description.json found at or above {path}"
        raise FileNotFoundError(msg)

    @property
    def vcs(self) -> VCSBackend:
        """Detected version control backend (lazy)."""
        if self._vcs is None:
            from bids_utils._vcs import detect_vcs

            self._vcs = detect_vcs(self.root)
        return self._vcs

    @property
    def schema(self) -> BIDSSchema:
        """Schema for this dataset's BIDS version (lazy)."""
        from bids_utils._schema import BIDSSchema

        return BIDSSchema.load(self.schema_version or self.bids_version)
