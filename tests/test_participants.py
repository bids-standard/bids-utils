"""Tests for _participants.py — participants.tsv operations."""

from pathlib import Path

import pytest

from bids_utils._participants import (
    add_participant,
    read_participants_tsv,
    remove_participant,
    rename_participant,
)


class TestReadParticipants:
    @pytest.mark.ai_generated
    def test_read(self, tmp_bids_dataset: Path) -> None:
        p = tmp_bids_dataset / "participants.tsv"
        rows = read_participants_tsv(p)
        assert len(rows) == 2
        assert rows[0]["participant_id"] == "sub-01"


class TestRenameParticipant:
    @pytest.mark.ai_generated
    def test_rename(self, tmp_bids_dataset: Path) -> None:
        p = tmp_bids_dataset / "participants.tsv"
        result = rename_participant(p, "sub-01", "sub-99")
        assert result is True
        rows = read_participants_tsv(p)
        ids = [r["participant_id"] for r in rows]
        assert "sub-99" in ids
        assert "sub-01" not in ids

    @pytest.mark.ai_generated
    def test_rename_not_found(self, tmp_bids_dataset: Path) -> None:
        p = tmp_bids_dataset / "participants.tsv"
        result = rename_participant(p, "sub-99", "sub-100")
        assert result is False


class TestRemoveParticipant:
    @pytest.mark.ai_generated
    def test_remove(self, tmp_bids_dataset: Path) -> None:
        p = tmp_bids_dataset / "participants.tsv"
        result = remove_participant(p, "sub-01")
        assert result is True
        rows = read_participants_tsv(p)
        assert len(rows) == 1
        assert rows[0]["participant_id"] == "sub-02"

    @pytest.mark.ai_generated
    def test_remove_not_found(self, tmp_bids_dataset: Path) -> None:
        p = tmp_bids_dataset / "participants.tsv"
        result = remove_participant(p, "sub-99")
        assert result is False


class TestAddParticipant:
    @pytest.mark.ai_generated
    def test_add(self, tmp_bids_dataset: Path) -> None:
        p = tmp_bids_dataset / "participants.tsv"
        result = add_participant(p, "sub-03", age="35", sex="M")
        assert result is True
        rows = read_participants_tsv(p)
        assert len(rows) == 3
        sub03 = [r for r in rows if r["participant_id"] == "sub-03"][0]
        assert sub03["age"] == "35"

    @pytest.mark.ai_generated
    def test_add_duplicate(self, tmp_bids_dataset: Path) -> None:
        p = tmp_bids_dataset / "participants.tsv"
        result = add_participant(p, "sub-01")
        assert result is False
