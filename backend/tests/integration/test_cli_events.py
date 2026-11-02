"""M6 CLI: `tst events`, `tst choose --event --choice`, `tst storylines`, and Continue blocked
by a critical event."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.helpers import open_event
from tst.cli import app
from tst.db.repository import create_save
from tst.loader import LoadedData

runner = CliRunner()
SAVE = "clievents"


@pytest.fixture
def save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loaded: LoadedData) -> Path:
    path = tmp_path / "saves"
    monkeypatch.setenv("TST_SAVE_DIR", str(path))
    return create_save(
        SAVE, 4, "ex_big_tech_founders", company_name="Cli Co", data=loaded, save_dir=path
    )


def run(*args: str, code: int = 0) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == code, result.output
    return result.output


def test_events_choose_storylines_and_the_critical_block(save: Path, loaded: LoadedData) -> None:
    event_id = open_event(save, loaded, "quiet_tax_credit", severity="minor")
    out = run("events", "--save", SAVE)
    assert f"Event {event_id} [Finance, minor]" in out and "A. Claim it — brings in $" in out
    assert "Answered" in run("choose", "--save", SAVE, "--event", str(event_id), "--choice", "a")
    assert f"Answered {event_id} (you chose)" in run("events", "--save", SAVE)
    crit = open_event(save, loaded, "runway_payroll_crunch", severity="critical")
    blocked = run("advance", "--save", SAVE, code=1)
    assert "critical event" in blocked and "tst events" in blocked
    run("choose", "--save", SAVE, "--event", str(crit), "--choice", "A")
    assert "now Feb 2010" in run("advance", "--save", SAVE)
    assert run("storylines", "--save", SAVE).strip()
