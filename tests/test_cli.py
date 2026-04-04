"""CLI smoke tests for bids-utils."""

from pathlib import Path

import pytest
from click.testing import CliRunner

# Import to register the rename command
import bids_utils.cli.rename  # noqa: F401
from bids_utils.cli import main


class TestCLIHelp:
    @pytest.mark.ai_generated
    def test_main_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "CLI for manipulating BIDS datasets" in result.output

    @pytest.mark.ai_generated
    def test_rename_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["rename", "--help"])
        assert result.exit_code == 0
        assert "--set" in result.output
        assert "--dry-run" in result.output

    @pytest.mark.ai_generated
    def test_version(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "bids-utils" in result.output


class TestCLIRename:
    @pytest.mark.ai_generated
    def test_rename_dry_run(self, tmp_bids_dataset: Path) -> None:
        runner = CliRunner()
        bold = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz"
        result = runner.invoke(
            main,
            ["rename", str(bold), "--set", "task=nback", "--dry-run"],
        )
        assert result.exit_code == 0
        assert "Rename" in result.output
        # File should still exist (dry run)
        assert bold.exists()

    @pytest.mark.ai_generated
    def test_rename_json_output(self, tmp_bids_dataset: Path) -> None:
        runner = CliRunner()
        bold = tmp_bids_dataset / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz"
        result = runner.invoke(
            main,
            ["rename", str(bold), "--set", "task=nback", "--dry-run", "--json"],
        )
        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert data["success"] is True
        assert data["dry_run"] is True

    @pytest.mark.ai_generated
    def test_rename_no_dataset(self, tmp_path: Path) -> None:
        runner = CliRunner()
        f = tmp_path / "orphan.nii.gz"
        f.write_bytes(b"")
        result = runner.invoke(main, ["rename", str(f), "--set", "task=nback"])
        assert result.exit_code != 0
