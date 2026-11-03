"""M5 CLI: rivals, one rival, market news, and a poach search."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from tst.cli import app
from tst.db.repository import create_save, load_state, open_session
from tst.loader import LoadedData

runner = CliRunner()
SAVE = "clirivals"


@pytest.fixture
def save_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loaded: LoadedData) -> Path:
    path = tmp_path / "saves"
    monkeypatch.setenv("TST_SAVE_DIR", str(path))
    create_save(SAVE, 4, "ex_big_tech_founders", company_name="Cli Co", data=loaded, save_dir=path)
    return path


def run(*args: str, code: int = 0) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == code, result.output
    return result.output


def test_rivals_rival_news_and_poach(save_dir: Path) -> None:
    out = run("rivals", "--save", SAVE)
    assert "27 established, 0 startups alive" in out and "Salesforce" in out and "Premium" in out
    run("advance", "--save", SAVE, "--turns", "2")
    profile = run("rival", "--save", SAVE, "--id", "2")
    assert profile.startswith("Salesforce (Premium)") and "Key people:" in profile
    assert "Sales Cloud / SMB" in profile
    news = run("news", "--save", SAVE)
    assert "[" in news  # at least one tagged move
    with open_session(save_dir / f"{SAVE}.tst.sqlite") as session:
        state = load_state(session)
    before = state.person_state(1).energy or 0  # events can move this month's energy (M6, M7a)
    poach = run("poach", "--save", SAVE, "--rival", "2")
    assert "poach software_engineer from Salesforce" in poach
    assert f"energy {before - 10}/60" in poach
    run("rival", "--save", SAVE, "--id", "1", code=1)
