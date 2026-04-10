"""Tests for --dry-run=overview|detailed (T098)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from bids_utils.cli import main


class TestDryRunOverview:
    @pytest.mark.ai_generated
    def test_dry_run_no_value_is_overview(
        self, tmp_bids_dataset: Path
    ) -> None:
        """--dry-run without value defaults to overview."""
        runner = CliRunner()
        bold = (
            tmp_bids_dataset
            / "sub-01"
            / "func"
            / "sub-01_task-rest_bold.nii.gz"
        )
        result = runner.invoke(
            main,
            ["rename", str(bold), "--set", "task=nback", "--dry-run"],
        )
        assert result.exit_code == 0
        # Overview shows the detail string, not the raw source path
        assert "Rename" in result.output

    @pytest.mark.ai_generated
    def test_dry_run_overview_explicit(
        self, tmp_bids_dataset: Path
    ) -> None:
        runner = CliRunner()
        bold = (
            tmp_bids_dataset
            / "sub-01"
            / "func"
            / "sub-01_task-rest_bold.nii.gz"
        )
        result = runner.invoke(
            main,
            [
                "rename",
                str(bold),
                "--set",
                "task=nback",
                "--dry-run=overview",
            ],
        )
        assert result.exit_code == 0
        assert "Rename" in result.output


class TestDryRunDetailed:
    @pytest.mark.ai_generated
    def test_dry_run_detailed_shows_paths(
        self, tmp_bids_dataset: Path
    ) -> None:
        """--dry-run=detailed shows action: source → target per file."""
        runner = CliRunner()
        bold = (
            tmp_bids_dataset
            / "sub-01"
            / "func"
            / "sub-01_task-rest_bold.nii.gz"
        )
        result = runner.invoke(
            main,
            [
                "rename",
                str(bold),
                "--set",
                "task=nback",
                "--dry-run=detailed",
            ],
        )
        assert result.exit_code == 0
        # Detailed mode shows "action: path" format
        assert "rename:" in result.output

    @pytest.mark.ai_generated
    def test_session_dry_run_detailed_lists_files(
        self,
        tmp_bids_dataset_with_sessions: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Session rename --dry-run=detailed lists individual file renames."""
        monkeypatch.chdir(tmp_bids_dataset_with_sessions)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["session-rename", "pre", "baseline", "--dry-run=detailed"],
        )
        assert result.exit_code == 0, result.output
        # Detailed mode shows "action: path" format
        assert "rename:" in result.output
        # Should have more lines than just the summary
        lines = [
            ln
            for ln in result.output.strip().splitlines()
            if ln.startswith("[DRY RUN]")
        ]
        # At minimum: 1 dir rename + files for 2 subjects
        assert len(lines) > 2

    @pytest.mark.ai_generated
    def test_session_dry_run_overview_is_summary(
        self,
        tmp_bids_dataset_with_sessions: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Session rename --dry-run (overview) shows only summary."""
        monkeypatch.chdir(tmp_bids_dataset_with_sessions)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["session-rename", "pre", "baseline", "--dry-run"],
        )
        assert result.exit_code == 0, result.output
        lines = [
            ln
            for ln in result.output.strip().splitlines()
            if ln.startswith("[DRY RUN]")
        ]
        # Overview: one line per subject at most
        assert len(lines) <= 4  # 2 subjects × ~2 lines each


class TestAnnexLogging:
    @pytest.mark.ai_generated
    def test_ensure_content_get_logs(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """ensure_content with GET mode should log at INFO."""
        from bids_utils._io import ensure_content
        from bids_utils._types import AnnexedMode

        vcs = MagicMock()
        vcs.has_content.return_value = False
        f = tmp_path / "test.json"

        with caplog.at_level(logging.INFO, logger="bids_utils._io"):
            ensure_content(f, vcs, AnnexedMode.GET)

        assert "Fetching" in caplog.text

    @pytest.mark.ai_generated
    def test_ensure_writable_logs_debug(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """ensure_writable should log at DEBUG."""
        from bids_utils._io import ensure_writable

        vcs = MagicMock()
        target = tmp_path / "real"
        target.write_text("x")
        link = tmp_path / "linked"
        link.symlink_to(target)

        with caplog.at_level(logging.DEBUG, logger="bids_utils._io"):
            ensure_writable(link, vcs)

        assert "Unlocking" in caplog.text

    @pytest.mark.ai_generated
    def test_mark_modified_logs_debug(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """mark_modified should log at DEBUG."""
        from bids_utils._io import mark_modified

        vcs = MagicMock()
        f = tmp_path / "test.tsv"

        with caplog.at_level(logging.DEBUG, logger="bids_utils._io"):
            mark_modified([f], vcs)

        assert "Re-adding" in caplog.text
