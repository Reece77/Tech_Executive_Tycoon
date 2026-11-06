"""M14 CLI: targets, diligence, a bid with `tst offer --company`, and a brand's directive."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.helpers import fund_save
from tst.cli import app
from tst.db.repository import create_save, load_state, open_session
from tst.loader import LoadedData

runner = CliRunner()
SAVE = "climna"


@pytest.fixture
def save_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loaded: LoadedData) -> Path:
    path = tmp_path / "saves"
    monkeypatch.setenv("TST_SAVE_DIR", str(path))
    save = create_save(
        SAVE, 4, "ex_big_tech_founders", company_name="Cli Co", data=loaded, save_dir=path
    )
    fund_save(save, 50_000_000_000_00)
    return path


def run(*args: str, code: int = 0) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == code, result.output
    return result.output


def test_targets_diligence_bid_and_directive(save_dir: Path) -> None:
    out = run("targets", "--save", SAVE)
    assert "Zoho (incumbent): value $" in out and "Salesforce (incumbent): market cap $" in out
    run("diligence", "--save", SAVE, "--company", "Evernote")
    assert "Evernote (incumbent)" in run("targets", "--save", SAVE)
    bid = run("offer", "--save", SAVE, "--company", "Evernote", "--price", "1", "--brand")
    assert "counters at" in bid
    with open_session(save_dir / f"{SAVE}.tst.sqlite") as session:
        state = load_state(session)
    counter = state.target_files[0].counter_cents
    assert counter is not None
    agreed = run(
        "offer", "--save", SAVE, "--company", "Evernote", "--price", str(counter), "--brand"
    )
    assert "Deal agreed: Evernote" in agreed
    run("advance", "--save", SAVE, "--turns", "1")
    assert "Bought Evernote (brand)" in run("targets", "--save", SAVE)
    assert "Directive set: harvest." in run(
        "directive", "--save", SAVE, "--company", "Evernote", "--mode", "harvest"
    )
    run("offer", "--save", SAVE, code=1)  # neither a candidate nor a company
