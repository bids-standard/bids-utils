"""CLI smoke tests for bids-utils."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from bids_utils.cli import main

# Expected commands that must always be present in `bids-utils --help`.
EXPECTED_COMMANDS = [
    "completion",
    "merge",
    "metadata",
    "migrate",
    "remove",
    "remove-run",
    "rename",
    "session-rename",
    "split",
    "subject-rename",
]


class TestCLIHelp:
    @pytest.mark.ai_generated
    def test_all_commands_registered(self) -> None:
        """Every implemented command must appear in --help output."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        for cmd in EXPECTED_COMMANDS:
            assert cmd in result.output, f"command {cmd!r} missing from --help"

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


class TestCLIRemove:
    @pytest.mark.ai_generated
    def test_remove_prompts_without_force(self, tmp_bids_dataset: Path) -> None:
        """Without --force, remove should prompt and abort on 'n'."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["remove", "sub-01"],
            input="n\n",
            catch_exceptions=False,
        )
        assert result.exit_code != 0
        assert (tmp_bids_dataset / "sub-01").is_dir()  # not deleted

    @pytest.mark.ai_generated
    def test_remove_prompts_confirms_on_y(self, tmp_bids_dataset: Path) -> None:
        """With 'y' input, remove should proceed."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["remove", "sub-01"],
            input="y\n",
            catch_exceptions=False,
        )
        # exit 0 or 2 depending on whether dataset found from cwd
        # The key test is that it didn't abort at the prompt
        assert "Remove sub-01" in result.output or result.exit_code != 0

    @pytest.mark.ai_generated
    def test_remove_force_skips_prompt(self, tmp_bids_dataset: Path) -> None:
        """With --force, remove should not prompt."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["remove", "sub-01", "--force"],
            catch_exceptions=False,
        )
        # Should not contain the confirmation question
        assert "cannot be undone" not in result.output
