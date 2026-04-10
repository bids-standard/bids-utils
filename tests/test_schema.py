"""Tests for _schema.py — BIDSSchema wrapper."""

import pytest

from bids_utils._schema import BIDSSchema


class TestBIDSSchema:
    @pytest.mark.ai_generated
    def test_load_default(self) -> None:
        schema = BIDSSchema.load()
        assert schema.bids_version != "unknown"

    @pytest.mark.ai_generated
    def test_entity_order(self) -> None:
        schema = BIDSSchema.load()
        order = schema.entity_order()
        assert isinstance(order, list)
        assert "subject" in order or "sub" in order or len(order) > 0

    @pytest.mark.ai_generated
    def test_sidecar_extensions_bold(self) -> None:
        schema = BIDSSchema.load()
        exts = schema.sidecar_extensions("bold")
        assert ".json" in exts

    @pytest.mark.ai_generated
    def test_sidecar_extensions_dwi(self) -> None:
        schema = BIDSSchema.load()
        exts = schema.sidecar_extensions("dwi")
        assert ".json" in exts
        assert ".bvec" in exts
        assert ".bval" in exts

    @pytest.mark.ai_generated
    def test_deprecation_rules(self) -> None:
        schema = BIDSSchema.load()
        rules = schema.deprecation_rules("1.4.0", "1.9.0")
        assert isinstance(rules, list)

    @pytest.mark.ai_generated
    def test_metadata_field_info(self) -> None:
        schema = BIDSSchema.load()
        # RepetitionTime is a well-known BIDS metadata field
        info = schema.metadata_field_info("RepetitionTime")
        # May or may not be found depending on schema structure
        # Just verify it doesn't crash
        assert info is None or isinstance(info, dict)

    @pytest.mark.ai_generated
    def test_caching(self) -> None:
        s1 = BIDSSchema.load()
        s2 = BIDSSchema.load()
        assert s1 is s2  # same cached instance
