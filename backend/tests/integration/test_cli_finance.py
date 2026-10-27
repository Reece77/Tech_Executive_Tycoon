"""M4a CLI: the brief's manual check, automated (safe, round start/sheets/accept, captable,
board, statements, bridge)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tst.cli import app
from tst.db.repository import create_save
from tst.loader import LoadedData

runner = CliRunner()
SAVE = "clifin"


@pytest.fixture
def save_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loaded: LoadedData) -> Path:
    path = tmp_path / "saves"
    monkeypatch.setenv("TST_SAVE_DIR", str(path))
    # Seed 16: investors answer this garage's seed round (see test_fundraising).
    create_save(SAVE, 16, "garage_bootstrap", company_name="Cli Co", data=loaded, save_dir=path)
    return path


def run(*args: str, code: int = 0) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == code, result.output
    return result.output


def test_manual_check_flow(save_dir: Path) -> None:
    preview = run("safe", "--save", SAVE, "--amount", "300000", "--cap", "1000000", "--preview")
    assert "Hint: likely; the holders would get 30.00%" in preview
    out = run("safe", "--save", SAVE, "--amount", "300000", "--cap", "1000000")
    assert "SAFE raised for $300,000.00; energy 90/100" in out
    assert "error" in run("safe", "--save", SAVE, "--amount", "10", "--cap", "1000000", code=1)
    run("advance", "--save", SAVE)
    assert "No round is open. Next: Seed (allowed)" in run("round", "sheets", "--save", SAVE)
    run("round", "start", "--save", SAVE, "--series", "seed", "--target", "1500000")
    run("advance", "--save", SAVE)
    sheets = run("round", "sheets", "--save", SAVE)
    assert "Seed: open" in sheets and "you own" in sheets
    sheet = re.findall(r"sheet (\d+):", sheets)[0]
    assert "Accepted sheet" in run("round", "accept", "--save", SAVE, "--sheet", sheet)
    run("advance", "--save", SAVE)
    cap = run("captable", "--save", SAVE)
    assert "Fully diluted:" in cap and "SAFE holders" in cap and "Option pool" in cap
    board = run("board", "--save", SAVE)
    assert "Board confidence" in board and "backs you" in board and "investor" in board
    quarters = run("statements", "--save", SAVE, "--period", "quarter")
    assert "Q1 2010" in quarters and "assets" in quarters
    assert "error" in run("statements", "--save", SAVE, "--period", "week", code=1)
    assert "no bridge offer" in run("bridge", "accept", "--save", SAVE, code=1)
