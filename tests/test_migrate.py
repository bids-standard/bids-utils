"""Tests for migrate.py — schema-driven migration.

Migration rule test matrix (T125)
---------------------------------

BIDS 1.x migration rules fall into two coverage categories:

* **Real-world fixtures (bids-examples).** These deprecation patterns
  appear in the pinned ``bids-examples`` tree and are exercised by the
  integration sweep in ``tests/integration/``:

    - ``IntendedFor`` relative-path → BIDS URI (path_format)
    - ``AssociatedEmptyRoom`` relative-path → BIDS URI (path_format)
    - ``RawSources`` → ``Sources`` field rename
    - ``ElektaNeuromag`` → ``NeuromagElektaMEGIN`` enum rename
    - ``SoftwareFilters`` schema presence (used as merge target)
    - ``DatasetDOI`` bare DOI → ``doi:`` URI
    - ``AcquisitionDuration`` → ``FrameAcquisitionDuration``

* **Synthetic fixtures (in this file).** The schema declares these
  deprecations but ``bids-examples`` lacks representative data, so the
  tests below construct the minimal JSON/TSV directly:

    - ``DCOffsetCorrection`` → ``SoftwareFilters`` structural migration
      (T105)
    - ``BasedOn`` → ``Sources`` field rename
    - ``ScanDate`` → ``_scans.tsv`` ``acq_time`` cross-file move
      (including the missing-``_scans.tsv`` path from T036)
    - ``HardcopyDeviceSoftwareVersion`` advisory removal
    - ``_phase`` suffix → ``part-phase_bold``
    - ``_T2star`` / ``_FLASH`` / ``_PD`` ambiguous suffix deprecations
    - ``"89+"`` age string → numeric, HIPAA age cap to 89
    - Deprecated templates (``fsaverage3``–``fsaverage6``,
      ``fsaveragesym``, ``UNCInfant*``)

When a new rule is added, cover it here if ``bids-examples`` lacks a
concrete instance; otherwise prefer extending the integration sweep.
"""

import json
from pathlib import Path

import pytest

from bids_utils._dataset import BIDSDataset
from bids_utils.migrate import (
    _RULES,
    MigrationRule,
    _register_rule,
    migrate_dataset,
)


def _make_dataset(tmp_path: Path, bids_version: str = "1.4.0") -> Path:
    """Create a minimal dataset with a specific BIDSVersion."""
    ds = tmp_path / "dataset"
    ds.mkdir()
    (ds / "dataset_description.json").write_text(
        json.dumps({"Name": "Test", "BIDSVersion": bids_version, "DatasetType": "raw"})
    )
    (ds / "participants.tsv").write_text("participant_id\nsub-01\n")
    return ds


class TestFieldRename:
    @pytest.mark.ai_generated
    def test_basedon_to_sources(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        sidecar = func / "sub-01_task-rest_bold.json"
        sidecar.write_text(json.dumps({"BasedOn": ["sub-01/anat/sub-01_T1w.nii.gz"]}))

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        assert result.findings
        assert any("BasedOn" in str(f.current_value) for f in result.findings)
        # Verify the fix was applied
        data = json.loads(sidecar.read_text())
        assert "BasedOn" not in data
        assert "Sources" in data

    @pytest.mark.ai_generated
    def test_rawsources_to_sources(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        sidecar = ds_path / "sub-01_bold.json"
        sidecar.write_text(json.dumps({"RawSources": ["rawdata/sub-01.nii"]}))
        (ds_path / "sub-01").mkdir()

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        assert any("RawSources" in str(f.current_value) for f in result.findings)

    @pytest.mark.ai_generated
    def test_sources_merge_mixed_types(self, tmp_path: Path) -> None:
        """Existing Sources as string + incoming array must merge, not be dropped."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        sidecar = func / "sub-01_task-rest_bold.json"
        sidecar.write_text(
            json.dumps(
                {
                    "Sources": "existing_source.nii",
                    "BasedOn": ["new_source_a.nii", "new_source_b.nii"],
                }
            )
        )

        ds = BIDSDataset.from_path(ds_path)
        migrate_dataset(ds)

        data = json.loads(sidecar.read_text())
        assert "BasedOn" not in data
        assert isinstance(data["Sources"], list)
        assert set(data["Sources"]) == {
            "existing_source.nii",
            "new_source_a.nii",
            "new_source_b.nii",
        }

    @pytest.mark.ai_generated
    def test_sources_three_way_merge(self, tmp_path: Path) -> None:
        """BasedOn + RawSources + existing Sources all merge into Sources."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        sidecar = func / "sub-01_task-rest_bold.json"
        sidecar.write_text(
            json.dumps(
                {
                    "Sources": ["orig.nii"],
                    "BasedOn": ["basedon.nii"],
                    "RawSources": ["rawsources.nii"],
                }
            )
        )

        ds = BIDSDataset.from_path(ds_path)
        migrate_dataset(ds)

        data = json.loads(sidecar.read_text())
        assert "BasedOn" not in data
        assert "RawSources" not in data
        assert isinstance(data["Sources"], list)
        assert set(data["Sources"]) == {
            "orig.nii",
            "basedon.nii",
            "rawsources.nii",
        }

    @pytest.mark.ai_generated
    def test_sources_three_way_merge_mixed_types(self, tmp_path: Path) -> None:
        """3-way merge: string Sources + list BasedOn + string RawSources."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        sidecar = func / "sub-01_task-rest_bold.json"
        sidecar.write_text(
            json.dumps(
                {
                    "Sources": "orig.nii",
                    "BasedOn": ["basedon_a.nii", "basedon_b.nii"],
                    "RawSources": "rawsources.nii",
                }
            )
        )

        ds = BIDSDataset.from_path(ds_path)
        migrate_dataset(ds)

        data = json.loads(sidecar.read_text())
        assert isinstance(data["Sources"], list)
        assert set(data["Sources"]) == {
            "orig.nii",
            "basedon_a.nii",
            "basedon_b.nii",
            "rawsources.nii",
        }


class TestEnumRename:
    @pytest.mark.ai_generated
    def test_elektaneuromag(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        meg = ds_path / "sub-01" / "meg"
        meg.mkdir(parents=True)
        sidecar = meg / "sub-01_coordsystem.json"
        sidecar.write_text(json.dumps({"MEGCoordinateSystem": "ElektaNeuromag"}))

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        assert result.findings
        data = json.loads(sidecar.read_text())
        assert data["MEGCoordinateSystem"] == "NeuromagElektaMEGIN"


class TestPathFormat:
    @pytest.mark.ai_generated
    def test_intendedfor_to_bids_uri(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        fmap = ds_path / "sub-01" / "fmap"
        fmap.mkdir(parents=True)
        sidecar = fmap / "sub-01_phasediff.json"
        sidecar.write_text(
            json.dumps(
                {"IntendedFor": "ses-01/func/sub-01_ses-01_task-rest_bold.nii.gz"}
            )
        )

        ds = BIDSDataset.from_path(ds_path)
        migrate_dataset(ds)

        data = json.loads(sidecar.read_text())
        assert data["IntendedFor"].startswith("bids::")

    @pytest.mark.ai_generated
    def test_intendedfor_list(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        fmap = ds_path / "sub-01" / "fmap"
        fmap.mkdir(parents=True)
        sidecar = fmap / "sub-01_phasediff.json"
        sidecar.write_text(
            json.dumps(
                {
                    "IntendedFor": [
                        "func/sub-01_task-rest_bold.nii.gz",
                        "func/sub-01_task-motor_bold.nii.gz",
                    ]
                }
            )
        )

        ds = BIDSDataset.from_path(ds_path)
        migrate_dataset(ds)

        data = json.loads(sidecar.read_text())
        assert isinstance(data["IntendedFor"], list)
        assert all(v.startswith("bids::") for v in data["IntendedFor"])


class TestDOIFormat:
    @pytest.mark.ai_generated
    def test_bare_doi_to_uri(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        desc = ds_path / "dataset_description.json"
        data = json.loads(desc.read_text())
        data["DatasetDOI"] = "10.1234/example"
        desc.write_text(json.dumps(data))

        ds = BIDSDataset.from_path(ds_path)
        migrate_dataset(ds)

        data = json.loads(desc.read_text())
        assert data["DatasetDOI"] == "doi:10.1234/example"


class TestScanDateMove:
    @pytest.mark.ai_generated
    def test_scandate_to_scans_tsv(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        sub = ds_path / "sub-01" / "func"
        sub.mkdir(parents=True)
        sidecar = sub / "sub-01_task-rest_bold.json"
        sidecar.write_text(json.dumps({"ScanDate": "2020-01-15", "TaskName": "rest"}))
        nii = sub / "sub-01_task-rest_bold.nii.gz"
        nii.write_bytes(b"")

        # Create scans.tsv
        scans = ds_path / "sub-01" / "sub-01_scans.tsv"
        scans.write_text("filename\tacq_time\nfunc/sub-01_task-rest_bold.nii.gz\t\n")

        ds = BIDSDataset.from_path(ds_path)
        migrate_dataset(ds)

        # ScanDate should be removed from JSON
        data = json.loads(sidecar.read_text())
        assert "ScanDate" not in data

        # And moved to scans.tsv
        from bids_utils._scans import read_scans_tsv

        rows = read_scans_tsv(scans)
        assert rows[0]["acq_time"] == "2020-01-15"

    @pytest.mark.ai_generated
    def test_scandate_creates_scans_tsv_when_missing(self, tmp_path: Path) -> None:
        """If no _scans.tsv exists, one is created to avoid data loss."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        sub = ds_path / "sub-01" / "func"
        sub.mkdir(parents=True)
        sidecar = sub / "sub-01_task-rest_bold.json"
        sidecar.write_text(json.dumps({"ScanDate": "2020-06-01"}))
        # data file present so the TSV filename entry resolves naturally
        (sub / "sub-01_task-rest_bold.nii.gz").write_bytes(b"")

        # No _scans.tsv exists anywhere
        assert not (ds_path / "sub-01" / "sub-01_scans.tsv").exists()

        ds = BIDSDataset.from_path(ds_path)
        migrate_dataset(ds)

        # JSON no longer carries ScanDate
        data = json.loads(sidecar.read_text())
        assert "ScanDate" not in data

        # A _scans.tsv was created with the correct acq_time and filename
        from bids_utils._scans import read_scans_tsv

        scans = ds_path / "sub-01" / "sub-01_scans.tsv"
        assert scans.exists()
        rows = read_scans_tsv(scans)
        assert len(rows) == 1
        assert rows[0]["acq_time"] == "2020-06-01"
        assert rows[0]["filename"] == "func/sub-01_task-rest_bold.nii.gz"

    @pytest.mark.ai_generated
    def test_scandate_creates_scans_tsv_with_session(self, tmp_path: Path) -> None:
        """Multi-session datasets get a session-level _scans.tsv created."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        ses = ds_path / "sub-01" / "ses-pre" / "func"
        ses.mkdir(parents=True)
        sidecar = ses / "sub-01_ses-pre_task-rest_bold.json"
        sidecar.write_text(json.dumps({"ScanDate": "2020-08-10"}))
        (ses / "sub-01_ses-pre_task-rest_bold.nii.gz").write_bytes(b"")

        ds = BIDSDataset.from_path(ds_path)
        migrate_dataset(ds)

        from bids_utils._scans import read_scans_tsv

        scans = ds_path / "sub-01" / "ses-pre" / "sub-01_ses-pre_scans.tsv"
        assert scans.exists()
        rows = read_scans_tsv(scans)
        assert rows[0]["acq_time"] == "2020-08-10"
        assert rows[0]["filename"] == "func/sub-01_ses-pre_task-rest_bold.nii.gz"


class TestDryRun:
    @pytest.mark.ai_generated
    def test_dry_run_no_modifications(self, tmp_path: Path) -> None:
        ds_path = _make_dataset(tmp_path, "1.4.0")
        fmap = ds_path / "sub-01" / "fmap"
        fmap.mkdir(parents=True)
        sidecar = fmap / "sub-01_phasediff.json"
        original = json.dumps({"IntendedFor": "func/sub-01_bold.nii.gz"})
        sidecar.write_text(original)

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, dry_run=True)

        assert result.dry_run
        assert result.findings
        assert len(result.changes) == 0  # No changes in dry run
        # File should be unmodified
        assert sidecar.read_text() == original


class TestSuffixDeprecation:
    @pytest.mark.ai_generated
    def test_phase_suffix_renamed_to_part_phase_bold(self, tmp_path: Path) -> None:
        """_phase suffix auto-fixed to part-phase entity + bold suffix."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        # Create a _phase file and its sidecar
        phase_nii = func / "sub-01_task-rest_phase.nii.gz"
        phase_nii.write_bytes(b"")
        phase_json = func / "sub-01_task-rest_phase.json"
        phase_json.write_text(json.dumps({"TaskName": "rest"}))

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        # Should find the deprecated suffix
        suffix_findings = [
            f for f in result.findings if f.rule.category == "suffix_deprecation"
        ]
        assert suffix_findings
        assert any(f.can_auto_fix for f in suffix_findings)

        # The phase file should have been renamed
        expected = func / "sub-01_task-rest_part-phase_bold.nii.gz"
        assert expected.exists()
        assert not phase_nii.exists()

    @pytest.mark.ai_generated
    def test_t2star_suffix_flagged_not_auto_fixed(self, tmp_path: Path) -> None:
        """T2star suffix is flagged but not auto-fixed (ambiguous)."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        anat = ds_path / "sub-01" / "anat"
        anat.mkdir(parents=True)
        t2star = anat / "sub-01_T2star.nii.gz"
        t2star.write_bytes(b"")

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        suffix_findings = [
            f
            for f in result.findings
            if f.rule.category == "suffix_deprecation"
            and "T2star" in str(f.current_value)
        ]
        assert suffix_findings
        assert not suffix_findings[0].can_auto_fix
        # File should NOT have been renamed
        assert t2star.exists()

    @pytest.mark.ai_generated
    def test_flash_suffix_flagged_not_auto_fixed(self, tmp_path: Path) -> None:
        """FLASH suffix is flagged but not auto-fixed (removed)."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        anat = ds_path / "sub-01" / "anat"
        anat.mkdir(parents=True)
        flash = anat / "sub-01_FLASH.nii.gz"
        flash.write_bytes(b"")

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        suffix_findings = [
            f
            for f in result.findings
            if f.rule.category == "suffix_deprecation"
            and "FLASH" in str(f.current_value)
        ]
        assert suffix_findings
        assert not suffix_findings[0].can_auto_fix
        assert flash.exists()

    @pytest.mark.ai_generated
    def test_pd_suffix_flagged_not_auto_fixed(self, tmp_path: Path) -> None:
        """PD suffix is flagged but not auto-fixed (ambiguous)."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        anat = ds_path / "sub-01" / "anat"
        anat.mkdir(parents=True)
        pd_file = anat / "sub-01_PD.nii.gz"
        pd_file.write_bytes(b"")

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        suffix_findings = [
            f
            for f in result.findings
            if f.rule.category == "suffix_deprecation"
            and f.current_value == "suffix=PD"
        ]
        assert suffix_findings
        assert not suffix_findings[0].can_auto_fix
        assert pd_file.exists()

    @pytest.mark.ai_generated
    def test_phase_suffix_dry_run(self, tmp_path: Path) -> None:
        """Dry run reports phase suffix finding without renaming."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        phase_nii = func / "sub-01_task-rest_phase.nii.gz"
        phase_nii.write_bytes(b"")

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, dry_run=True)

        suffix_findings = [
            f for f in result.findings if f.rule.category == "suffix_deprecation"
        ]
        assert suffix_findings
        # File should NOT have been renamed in dry run
        assert phase_nii.exists()
        assert not result.changes


class TestDeprecatedTemplate:
    @pytest.mark.ai_generated
    def test_fsaverage3_flagged(self, tmp_path: Path) -> None:
        """Deprecated template identifier fsaverage3 is flagged."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        meg = ds_path / "sub-01" / "meg"
        meg.mkdir(parents=True)
        sidecar = meg / "sub-01_coordsystem.json"
        sidecar.write_text(json.dumps({"MEGCoordinateSystem": "fsaverage3"}))

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        tmpl_findings = [
            f for f in result.findings if f.rule.category == "deprecated_template"
        ]
        assert tmpl_findings
        assert not tmpl_findings[0].can_auto_fix
        assert "fsaverage3" in tmpl_findings[0].current_value

    @pytest.mark.ai_generated
    def test_uncinfant_flagged(self, tmp_path: Path) -> None:
        """Deprecated UNCInfant template is flagged."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        eeg = ds_path / "sub-01" / "eeg"
        eeg.mkdir(parents=True)
        sidecar = eeg / "sub-01_coordsystem.json"
        sidecar.write_text(json.dumps({"EEGCoordinateSystem": "UNCInfant1V22"}))

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        tmpl_findings = [
            f for f in result.findings if f.rule.category == "deprecated_template"
        ]
        assert tmpl_findings
        assert not tmpl_findings[0].can_auto_fix
        assert "UNCInfant1V22" in tmpl_findings[0].current_value

    @pytest.mark.ai_generated
    def test_fsaveragesym_flagged(self, tmp_path: Path) -> None:
        """Deprecated fsaveragesym template is flagged."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        meg = ds_path / "sub-01" / "meg"
        meg.mkdir(parents=True)
        sidecar = meg / "sub-01_coordsystem.json"
        sidecar.write_text(json.dumps({"MEGCoordinateSystem": "fsaveragesym"}))

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        tmpl_findings = [
            f for f in result.findings if f.rule.category == "deprecated_template"
        ]
        assert tmpl_findings
        assert not tmpl_findings[0].can_auto_fix

    @pytest.mark.ai_generated
    def test_non_deprecated_template_not_flagged(self, tmp_path: Path) -> None:
        """Current template identifier 'fsaverage' is NOT flagged."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        meg = ds_path / "sub-01" / "meg"
        meg.mkdir(parents=True)
        sidecar = meg / "sub-01_coordsystem.json"
        sidecar.write_text(json.dumps({"MEGCoordinateSystem": "fsaverage"}))

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds)

        tmpl_findings = [
            f for f in result.findings if f.rule.category == "deprecated_template"
        ]
        assert not tmpl_findings

    @pytest.mark.ai_generated
    def test_deprecated_template_not_modified(self, tmp_path: Path) -> None:
        """Deprecated template value is not auto-modified in the file."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        meg = ds_path / "sub-01" / "meg"
        meg.mkdir(parents=True)
        sidecar = meg / "sub-01_coordsystem.json"
        original = json.dumps({"MEGCoordinateSystem": "fsaverage5"})
        sidecar.write_text(original)

        ds = BIDSDataset.from_path(ds_path)
        migrate_dataset(ds)

        # File should be unchanged since can_auto_fix=False
        assert sidecar.read_text() == original


class TestNothingToDo:
    @pytest.mark.ai_generated
    def test_up_to_date_dataset(self, tmp_bids_dataset: Path) -> None:
        ds = BIDSDataset.from_path(tmp_bids_dataset)
        result = migrate_dataset(ds)

        # Dataset at 1.9.0, no deprecated fields → nothing to do
        assert any(
            "up to date" in w.lower() or "nothing" in w.lower() for w in result.warnings
        )


# ---------------------------------------------------------------------------
# Phase 4: BIDS 2.0 Migration Tests (T044)
# ---------------------------------------------------------------------------


@pytest.fixture()
def _register_synthetic_2x_rules():
    """Register synthetic 2.0 rules for testing and clean up afterward."""
    rules_to_add = [
        MigrationRule(
            id="entity_rename_acq_to_acquisition",
            from_version="2.0.0",
            category="entity_rename",
            description="Rename entity 'acq' to 'acquisition'",
            old_field="acq",
            new_field="acquisition",
        ),
        MigrationRule(
            id="metadata_key_change_EchoTime1",
            from_version="2.0.0",
            category="metadata_key_change",
            description="Rename metadata field 'EchoTime1' to 'EchoTimePrimary'",
            old_field="EchoTime1",
            new_field="EchoTimePrimary",
        ),
        MigrationRule(
            id="structural_reorg_derivatives_layout",
            from_version="2.0.0",
            category="structural_reorg",
            description="Derivatives directory layout changed in 2.0",
        ),
    ]
    for rule in rules_to_add:
        _register_rule(rule)

    yield

    # Clean up: remove the synthetic rules
    for rule in rules_to_add:
        _RULES.remove(rule)


class TestMigrate20:
    """BIDS 2.0 migration infrastructure tests using synthetic rules."""

    @pytest.mark.ai_generated
    @pytest.mark.usefixtures("_register_synthetic_2x_rules")
    def test_cumulative_migration_applies_1x_first(self, tmp_path: Path) -> None:
        """Migrating from 1.4 to 2.0 applies all 1.x deprecation fixes too."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        fmap = ds_path / "sub-01" / "fmap"
        fmap.mkdir(parents=True)
        sidecar = fmap / "sub-01_phasediff.json"
        sidecar.write_text(
            json.dumps({"IntendedFor": "func/sub-01_bold.nii.gz"})
        )

        ds = BIDSDataset.from_path(ds_path)
        # dry_run to inspect findings without triggering the abort
        result = migrate_dataset(ds, to_version="2.0.0", dry_run=True)

        # Should include 1.x path_format findings AND 2.0 structural_reorg
        categories = {f.rule.category for f in result.findings}
        assert "path_format" in categories, "1.x rules should be included"
        assert "structural_reorg" in categories, "2.0 rules should be included"

    @pytest.mark.ai_generated
    @pytest.mark.usefixtures("_register_synthetic_2x_rules")
    def test_entity_rename_detected(self, tmp_path: Path) -> None:
        """2.0 entity rename rule detects files with the old entity key."""
        ds_path = _make_dataset(tmp_path, "1.9.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        # File with acq entity
        nii = func / "sub-01_task-rest_acq-lowres_bold.nii.gz"
        nii.write_bytes(b"")

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, to_version="2.0.0", dry_run=True)

        entity_findings = [
            f for f in result.findings if f.rule.category == "entity_rename"
        ]
        assert entity_findings
        assert entity_findings[0].can_auto_fix
        assert "acq-lowres" in entity_findings[0].current_value
        assert "acquisition-lowres" in entity_findings[0].proposed_value

    @pytest.mark.ai_generated
    @pytest.mark.usefixtures("_register_synthetic_2x_rules")
    def test_metadata_key_change_detected(self, tmp_path: Path) -> None:
        """2.0 metadata key change rule detects deprecated field names."""
        ds_path = _make_dataset(tmp_path, "1.9.0")
        fmap = ds_path / "sub-01" / "fmap"
        fmap.mkdir(parents=True)
        sidecar = fmap / "sub-01_phasediff.json"
        sidecar.write_text(json.dumps({"EchoTime1": 0.00492}))

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, to_version="2.0.0", dry_run=True)

        key_findings = [
            f for f in result.findings if f.rule.category == "metadata_key_change"
        ]
        assert key_findings
        assert "EchoTime1" in str(key_findings[0].current_value)
        assert "EchoTimePrimary" in str(key_findings[0].proposed_value)

    @pytest.mark.ai_generated
    @pytest.mark.usefixtures("_register_synthetic_2x_rules")
    def test_structural_reorg_flagged_not_auto_fixable(self, tmp_path: Path) -> None:
        """Structural reorg findings are flagged but not auto-fixable."""
        ds_path = _make_dataset(tmp_path, "1.9.0")

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, to_version="2.0.0", dry_run=True)

        reorg_findings = [
            f for f in result.findings if f.rule.category == "structural_reorg"
        ]
        assert reorg_findings
        assert not reorg_findings[0].can_auto_fix
        assert "human judgment" in reorg_findings[0].reason

    @pytest.mark.ai_generated
    @pytest.mark.usefixtures("_register_synthetic_2x_rules")
    def test_ambiguities_abort_major_migration(self, tmp_path: Path) -> None:
        """Major version migration aborts when unfixable findings exist."""
        ds_path = _make_dataset(tmp_path, "1.9.0")

        ds = BIDSDataset.from_path(ds_path)
        # Non-dry-run should abort due to structural_reorg being unfixable
        result = migrate_dataset(ds, to_version="2.0.0")

        assert not result.success
        assert result.errors
        assert any("Cannot auto-fix" in e for e in result.errors)
        assert any("aborted" in w.lower() for w in result.warnings)

    @pytest.mark.ai_generated
    @pytest.mark.usefixtures("_register_synthetic_2x_rules")
    def test_already_at_target_nothing_to_do(self, tmp_path: Path) -> None:
        """Dataset already at 2.0 → nothing to do."""
        ds_path = _make_dataset(tmp_path, "2.0.0")

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, to_version="2.0.0")

        assert any(
            "nothing" in w.lower() or "no applicable" in w.lower()
            for w in result.warnings
        )


# ---------------------------------------------------------------------------
# Phase 3a: Migration Rule Schema & Tiered Levels (T099–T110)
# ---------------------------------------------------------------------------


class TestMigrationLevels:
    """Tests for tiered migration levels (FR-029, FR-030)."""

    @pytest.mark.ai_generated
    def test_default_level_safe(self, tmp_path: Path) -> None:
        """--level=safe applies only safe rules."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        # BasedOn is safe; HardcopyDeviceSoftwareVersion is advisory (MRI)
        sidecar = func / "sub-01_task-rest_bold.json"
        sidecar.write_text(
            json.dumps(
                {
                    "BasedOn": ["sub-01/anat/sub-01_T1w.nii.gz"],
                    "HardcopyDeviceSoftwareVersion": "1.0",
                }
            )
        )

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, level="safe")

        rule_ids = {f.rule.id for f in result.findings}
        assert "field_rename_BasedOn_to_Sources" in rule_ids
        assert "field_removal_HardcopyDeviceSoftwareVersion" not in rule_ids

    @pytest.mark.ai_generated
    def test_level_advisory_includes_safe(self, tmp_path: Path) -> None:
        """--level=advisory applies both safe and advisory rules."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        sidecar = func / "sub-01_task-rest_bold.json"
        sidecar.write_text(
            json.dumps(
                {
                    "BasedOn": ["sub-01/anat/sub-01_T1w.nii.gz"],
                    "HardcopyDeviceSoftwareVersion": "1.0",
                }
            )
        )

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, level="advisory")

        rule_ids = {f.rule.id for f in result.findings}
        assert "field_rename_BasedOn_to_Sources" in rule_ids
        assert "field_removal_HardcopyDeviceSoftwareVersion" in rule_ids

    @pytest.mark.ai_generated
    def test_level_all_includes_everything(self, tmp_path: Path) -> None:
        """--level=all includes non-auto-fixable in findings."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        anat = ds_path / "sub-01" / "anat"
        anat.mkdir(parents=True)
        t2star = anat / "sub-01_T2star.nii.gz"
        t2star.write_bytes(b"")

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, level="all", dry_run=True)

        suffix_findings = [
            f
            for f in result.findings
            if f.rule.category == "suffix_deprecation"
            and "T2star" in str(f.current_value)
        ]
        assert suffix_findings
        assert not suffix_findings[0].can_auto_fix

    @pytest.mark.ai_generated
    def test_rule_id_filter(self, tmp_path: Path) -> None:
        """--rule-id selects specific rules only."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        sidecar = func / "sub-01_task-rest_bold.json"
        sidecar.write_text(
            json.dumps(
                {
                    "BasedOn": ["sub-01/anat/sub-01_T1w.nii.gz"],
                    "RawSources": ["rawdata/sub-01.nii"],
                }
            )
        )

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(
            ds,
            rule_ids=["field_rename_BasedOn_to_Sources"],
            dry_run=True,
        )

        rule_ids = {f.rule.id for f in result.findings}
        assert "field_rename_BasedOn_to_Sources" in rule_ids
        assert "field_rename_RawSources_to_Sources" not in rule_ids

    @pytest.mark.ai_generated
    def test_exclude_rule_filter(self, tmp_path: Path) -> None:
        """--exclude-rule excludes specific rules."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        sidecar = func / "sub-01_task-rest_bold.json"
        sidecar.write_text(
            json.dumps(
                {
                    "BasedOn": ["sub-01/anat/sub-01_T1w.nii.gz"],
                    "RawSources": ["rawdata/sub-01.nii"],
                }
            )
        )

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(
            ds,
            exclude_rules=["field_rename_BasedOn_to_Sources"],
            dry_run=True,
        )

        rule_ids = {f.rule.id for f in result.findings}
        assert "field_rename_BasedOn_to_Sources" not in rule_ids
        assert "field_rename_RawSources_to_Sources" in rule_ids


class TestAcquisitionDuration:
    @pytest.mark.ai_generated
    def test_renamed_when_volumetiming_present(self, tmp_path: Path) -> None:
        """AcquisitionDuration renamed when VolumeTiming is present."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        sidecar = func / "sub-01_task-rest_bold.json"
        sidecar.write_text(
            json.dumps(
                {
                    "AcquisitionDuration": 30.0,
                    "VolumeTiming": [0, 2, 4],
                }
            )
        )

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, level="safe")

        acq_findings = [
            f
            for f in result.findings
            if "AcquisitionDuration" in str(f.current_value)
        ]
        assert acq_findings
        assert acq_findings[0].can_auto_fix

        data = json.loads(sidecar.read_text())
        assert "AcquisitionDuration" not in data
        assert data["FrameAcquisitionDuration"] == 30.0

    @pytest.mark.ai_generated
    def test_flagged_not_auto_fixable_without_volumetiming(
        self, tmp_path: Path
    ) -> None:
        """AcquisitionDuration flagged as advisory without VolumeTiming."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        sidecar = func / "sub-01_task-rest_bold.json"
        original = json.dumps({"AcquisitionDuration": 30.0})
        sidecar.write_text(original)

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, level="advisory", dry_run=True)

        acq_findings = [
            f
            for f in result.findings
            if "AcquisitionDuration" in str(f.current_value)
        ]
        assert acq_findings
        assert not acq_findings[0].can_auto_fix


class TestDCOffsetCorrectionMigration:
    """DCOffsetCorrection → SoftwareFilters.DCOffsetCorrection.description (T105)."""

    @pytest.mark.ai_generated
    def test_standalone_dcoffset_nested_under_softwarefilters(
        self, tmp_path: Path
    ) -> None:
        """DCOffsetCorrection alone is moved into SoftwareFilters at level=safe."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        ieeg = ds_path / "sub-01" / "ieeg"
        ieeg.mkdir(parents=True)
        sidecar = ieeg / "sub-01_task-rest_ieeg.json"
        sidecar.write_text(json.dumps({"DCOffsetCorrection": "none"}))

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, level="safe")

        nest_findings = [
            f
            for f in result.findings
            if f.rule.id == "dcoffset_to_softwarefilters"
        ]
        assert nest_findings
        assert nest_findings[0].can_auto_fix

        data = json.loads(sidecar.read_text())
        assert "DCOffsetCorrection" not in data
        assert data["SoftwareFilters"] == {
            "DCOffsetCorrection": {"description": "none"}
        }

    @pytest.mark.ai_generated
    def test_merge_into_existing_softwarefilters_dict(
        self, tmp_path: Path
    ) -> None:
        """DCOffsetCorrection is merged into an existing SoftwareFilters dict."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        ieeg = ds_path / "sub-01" / "ieeg"
        ieeg.mkdir(parents=True)
        sidecar = ieeg / "sub-01_task-rest_ieeg.json"
        sidecar.write_text(
            json.dumps(
                {
                    "DCOffsetCorrection": "none",
                    "SoftwareFilters": {
                        "HighPass": {"description": "0.1 Hz"},
                    },
                }
            )
        )

        ds = BIDSDataset.from_path(ds_path)
        migrate_dataset(ds, level="safe")

        data = json.loads(sidecar.read_text())
        assert "DCOffsetCorrection" not in data
        # Existing entry preserved
        assert data["SoftwareFilters"]["HighPass"] == {"description": "0.1 Hz"}
        # New nested entry added
        assert data["SoftwareFilters"]["DCOffsetCorrection"] == {
            "description": "none"
        }

    @pytest.mark.ai_generated
    def test_non_ieeg_sidecar_not_migrated(self, tmp_path: Path) -> None:
        """DCOffsetCorrection in a non-iEEG sidecar is not touched."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        sidecar = func / "sub-01_task-rest_bold.json"
        original = json.dumps({"DCOffsetCorrection": "none"})
        sidecar.write_text(original)

        ds = BIDSDataset.from_path(ds_path)
        migrate_dataset(ds, level="safe")

        data = json.loads(sidecar.read_text())
        # Scope is iEEG only (FR-031) — func sidecars remain untouched
        assert data == {"DCOffsetCorrection": "none"}


class TestFieldRemoval:
    @pytest.mark.ai_generated
    def test_hardcopydevicesoftwareversion_removed_at_advisory(
        self, tmp_path: Path
    ) -> None:
        """HardcopyDeviceSoftwareVersion removed when level=advisory."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        func = ds_path / "sub-01" / "func"
        func.mkdir(parents=True)
        sidecar = func / "sub-01_task-rest_bold.json"
        sidecar.write_text(
            json.dumps({"HardcopyDeviceSoftwareVersion": "1.0"})
        )

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, level="advisory")

        removal_findings = [
            f
            for f in result.findings
            if f.rule.id == "field_removal_HardcopyDeviceSoftwareVersion"
        ]
        assert removal_findings

        data = json.loads(sidecar.read_text())
        assert "HardcopyDeviceSoftwareVersion" not in data


class TestAge89:
    @pytest.mark.ai_generated
    def test_89plus_string_converted_to_numeric(self, tmp_path: Path) -> None:
        """String '89+' in age column converted to '89'."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        participants = ds_path / "participants.tsv"
        participants.write_text(
            "participant_id\tage\nsub-01\t89+\nsub-02\t25\n"
        )

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, level="safe")

        age_findings = [
            f for f in result.findings if f.rule.id == "age_89plus_string"
        ]
        assert age_findings

        text = participants.read_text()
        assert "89+" not in text
        # The value should now be "89"
        lines = text.strip().split("\n")
        cols = lines[1].split("\t")
        assert cols[1] == "89"

    @pytest.mark.ai_generated
    def test_numeric_above_89_not_changed_at_safe(self, tmp_path: Path) -> None:
        """Numeric age > 89 is NOT changed at level=safe."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        participants = ds_path / "participants.tsv"
        participants.write_text(
            "participant_id\tage\nsub-01\t95\n"
        )

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, level="safe")

        age_findings = [
            f for f in result.findings if f.rule.id == "age_cap_89"
        ]
        assert not age_findings

        text = participants.read_text()
        assert "95" in text

    @pytest.mark.ai_generated
    def test_numeric_above_89_capped_at_advisory(self, tmp_path: Path) -> None:
        """Numeric age > 89 capped to 89 at level=advisory."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        participants = ds_path / "participants.tsv"
        participants.write_text(
            "participant_id\tage\nsub-01\t95\nsub-02\t25\n"
        )

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, level="advisory")

        age_findings = [
            f for f in result.findings if f.rule.id == "age_cap_89"
        ]
        assert age_findings

        text = participants.read_text()
        lines = text.strip().split("\n")
        cols = lines[1].split("\t")
        assert cols[1] == "89"

    @pytest.mark.ai_generated
    def test_age_non_year_units_skipped(self, tmp_path: Path) -> None:
        """Age column with non-year units is skipped."""
        ds_path = _make_dataset(tmp_path, "1.4.0")
        participants = ds_path / "participants.tsv"
        participants.write_text(
            "participant_id\tage\nsub-01\t89+\n"
        )
        # Sidecar specifying non-year units
        participants_json = ds_path / "participants.json"
        participants_json.write_text(
            json.dumps({"age": {"Description": "Age in months", "Units": "months"}})
        )

        ds = BIDSDataset.from_path(ds_path)
        result = migrate_dataset(ds, level="safe")

        age_findings = [
            f for f in result.findings if "age" in f.rule.id
        ]
        # Should have a non-auto-fixable finding explaining the skip
        assert len(age_findings) == 1
        assert not age_findings[0].can_auto_fix
        assert "non-year" in (age_findings[0].reason or "").lower()

        # Value unchanged
        text = participants.read_text()
        assert "89+" in text
