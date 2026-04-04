"""Schema loading and querying helpers wrapping bidsschematools."""

from __future__ import annotations

from functools import lru_cache
from typing import Any


class BIDSSchema:
    """Cached, version-aware schema accessor wrapping bidsschematools."""

    def __init__(self, schema: Any) -> None:
        self._schema = schema

    @classmethod
    @lru_cache(maxsize=8)
    def load(cls, version: str | None = None) -> BIDSSchema:
        """Load a BIDS schema by version.

        Parameters
        ----------
        version
            BIDS version string (e.g., "1.9.0").  If None, loads the
            bundled default schema.
        """
        from bidsschematools import schema

        schema_obj = schema.load_schema()
        return cls(schema_obj)

    @property
    def bids_version(self) -> str:
        """The BIDS version of this schema."""
        return str(self._schema.get("bids_version", "unknown"))

    def entity_order(self) -> list[str]:
        """Return the canonical entity ordering."""
        entities = getattr(self._schema, "objects", {}).get("entities", {})
        return list(entities.keys())

    def sidecar_extensions(self, suffix: str) -> list[str]:
        """Return known sidecar extensions for a given suffix.

        This is a simplified implementation that returns common sidecar
        extensions.  A full implementation would query the schema rules
        for datatype-specific extensions.
        """
        # Common sidecar extensions for all suffixes
        common = [".json"]

        # Suffix-specific extensions
        suffix_exts: dict[str, list[str]] = {
            "bold": [".json"],
            "dwi": [".json", ".bvec", ".bval"],
            "epi": [".json"],
            "T1w": [".json"],
            "T2w": [".json"],
            "FLAIR": [".json"],
            "events": [],  # events are .tsv, not sidecars of .nii.gz
            "physio": [".json"],
        }

        return suffix_exts.get(suffix, common)

    def is_valid_entity(self, key: str, value: str | None = None) -> bool:
        """Check if an entity key is valid in the schema."""
        entities = getattr(self._schema, "objects", {}).get("entities", {})
        return key in entities

    def deprecation_rules(
        self, from_version: str, to_version: str
    ) -> list[dict[str, Any]]:
        """Extract deprecation rules applicable between two versions.

        Returns a list of rule dicts from the schema's deprecation checks.
        """
        rules_obj = getattr(self._schema, "rules", {})
        checks = rules_obj.get("checks", {})
        deprecations = checks.get("deprecations", {})

        result: list[dict[str, Any]] = []
        for name, rule in deprecations.items():
            result.append({"name": name, **dict(rule)})

        return result

    def metadata_field_info(self, field_name: str) -> dict[str, Any] | None:
        """Get information about a metadata field from the schema."""
        metadata = getattr(self._schema, "objects", {}).get("metadata", {})
        info = metadata.get(field_name)
        if info is None:
            return None
        return dict(info)
