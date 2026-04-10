"""Tests for shared CLI helpers in bids_utils.cli._common."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from bids_utils._types import Change, OperationResult
from bids_utils.cli import main
from bids_utils.cli._common import load_dataset, output_result


@pytest.mark.ai_generated
def test_output_result_json(capsys: pytest.CaptureFixture[str]) -> None:
    """output_result emits valid JSON when json_output is True."""
    result = OperationResult(
        success=True,
        dry_run=True,
        changes=[
            Change(
                action="rename",
                source=Path("/a"),
                target=Path("/b"),
                detail="moved",
            )
        ],
        warnings=["w1"],
        errors=[],
    )
    output_result(result, json_output=True, dry_run=True)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["success"] is True
    assert data["dry_run"] is True
    assert len(data["changes"]) == 1
    assert data["changes"][0]["action"] == "rename"
    assert data["warnings"] == ["w1"]


@pytest.mark.ai_generated
def test_output_result_text(capsys: pytest.CaptureFixture[str]) -> None:
    """output_result prints human-readable text when json_output is False."""
    result = OperationResult(
        success=True,
        dry_run=True,
        changes=[
            Change(
                action="rename",
                source=Path("/a"),
                target=Path("/b"),
                detail="moved a",
            )
        ],
    )
    output_result(result, json_output=False, dry_run=True)
    captured = capsys.readouterr()
    assert "[DRY RUN] moved a" in captured.out


@pytest.mark.ai_generated
def test_output_result_exits_on_failure() -> None:
    """output_result calls sys.exit when result.success is False."""
    result = OperationResult(success=False, errors=["bad"])
    with pytest.raises(SystemExit) as exc_info:
        output_result(result, json_output=False, dry_run=False)
    assert exc_info.value.code == 2


@pytest.mark.ai_generated
def test_load_dataset_missing_dir(tmp_path: Path) -> None:
    """load_dataset exits with code 1 for a non-BIDS directory."""
    with pytest.raises(SystemExit) as exc_info:
        load_dataset(tmp_path)
    assert exc_info.value.code == 1


@pytest.mark.ai_generated
def test_load_dataset_success(tmp_path: Path) -> None:
    """load_dataset returns a BIDSDataset for a valid dataset."""
    desc = tmp_path / "dataset_description.json"
    desc.write_text('{"Name": "test", "BIDSVersion": "1.9.0"}')
    ds = load_dataset(tmp_path)
    assert ds.root == tmp_path


class TestAnnexedOption:
    @pytest.mark.ai_generated
    def test_annexed_appears_in_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "--annexed" in result.output

    @pytest.mark.ai_generated
    def test_annexed_invalid_choice(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--annexed=bogus", "rename", "--help"])
        assert result.exit_code != 0

    @pytest.mark.ai_generated
    def test_annexed_default_is_error(
        self, tmp_bids_dataset: Path
    ) -> None:
        """Without --annexed, load_dataset should default to ERROR."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["rename", "--help"],
        )
        assert result.exit_code == 0

    @pytest.mark.ai_generated
    def test_annexed_envvar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """BIDS_UTILS_ANNEXED env var should set the annexed mode."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--help"],
            env={"BIDS_UTILS_ANNEXED": "get"},
        )
        assert result.exit_code == 0
