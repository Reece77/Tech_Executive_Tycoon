"""M2a CLI: the brief's manual check, automated (org, units, morale, plans, raises)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.integration.test_api_org import seed_staff
from tst.cli import app
from tst.db.repository import create_save
from tst.loader import LoadedData

runner = CliRunner()
SAVE = "cliorg"


@pytest.fixture
def save_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loaded: LoadedData) -> Path:
    path = tmp_path / "saves"
    monkeypatch.setenv("TST_SAVE_DIR", str(path))
    save = create_save(
        SAVE, 11, "funded_spinout", company_name="Org Co", data=loaded, save_dir=path
    )
    seed_staff(save, loaded, 12, leaders=(2, 3))
    return path


def run(*args: str, code: int = 0) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == code, result.output
    return result.output


def manager_term(out: str) -> float:
    match = re.search(r"Their manager\s+([+-][\d.]+)", out)
    assert match, out
    return float(match.group(1))


def test_manual_check_flow(save_dir: Path) -> None:
    out = run("org", "--save", SAVE)
    assert "Org Co (company; office); leader" in out and "OVER SPAN" in out
    assert "manages 12 (limit 7, S 0.58)" in out

    flat = run("morale", "--save", SAVE, "--person", "9")
    assert manager_term(flat) == pytest.approx(-3.68, abs=0.01)
    assert "heading for" in flat and "Other" in flat

    assert "Created team 1: Alpha" in run(
        "unit", "create", "--save", SAVE, "--kind", "team", "--name", "Alpha"
    )
    run("unit", "create", "--save", SAVE, "--kind", "team", "--name", "Beta")
    preview = run("unit", "move", "--save", SAVE, "--person", "4", "--unit", "1", "--preview")
    assert "Costs 1 energy." in preview and "morale -2" in preview
    for unit, people in (("1", (2, 4, 5, 6, 7, 8)), ("2", (3, 9, 10, 11, 12, 13))):
        for pid in people:
            run("unit", "move", "--save", SAVE, "--person", str(pid), "--unit", unit)
    run("unit", "lead", "--save", SAVE, "--unit", "1", "--person", "2")
    run("unit", "lead", "--save", SAVE, "--unit", "2", "--person", "3")
    led = run("morale", "--save", SAVE, "--person", "9")
    assert manager_term(led) == pytest.approx(2.0) and "manager" in led
    assert "OVER SPAN" not in run("org", "--save", SAVE)

    out = run(
        "plan", "create", "--save", SAVE, "--owner", "4", "--role", "software_engineer",
        "--target", "3", "--ratio", "1.15", "--unit", "1",
    )  # fmt: skip
    assert "0/3 hired" in out and "owner" in out and "unit Alpha" in out
    run("advance", "--save", SAVE, "--turns", "3")
    plans = run("plan", "list", "--save", SAVE)
    assert "software engineer" in plans.lower()
    inbox = run("inbox", "--save", SAVE)
    assert "worked on the software engineer plan" in inbox
    hired = re.search(r"(\d)/3 hired", plans)
    assert hired and int(hired.group(1)) >= 1
    alpha = run("org", "--save", SAVE).split("Beta (team 2")[0]
    assert len(re.findall(r"Software engineer", alpha)) == 6 + int(hired.group(1))

    preview = run("raise", "--save", SAVE, "--person", "5", "--salary", "95000", "--preview")
    assert "one-off morale +3" in preview
    assert "now $95,000.00" in run("raise", "--save", SAVE, "--person", "5", "--salary", "95000")
    assert "one-off morale +5" in run("promote", "--save", SAVE, "--person", "5", "--preview")
    assert "now senior" in run("promote", "--save", SAVE, "--person", "5")
    run("unit", "policy", "--save", SAVE, "--unit", "2", "--policy", "remote")
    assert "Beta (team 2; remote)" in run("org", "--save", SAVE)
    run("plan", "update", "--save", SAVE, "--plan", "1", "--target", "5", "--unit", "root")
    assert "unit Org Co" in run("plan", "list", "--save", SAVE)
    assert "Closed hiring plan 1" in run("plan", "close", "--save", SAVE, "--plan", "1")
    assert "No hiring plans." in run("plan", "list", "--save", SAVE)


def test_errors_are_one_line(save_dir: Path) -> None:
    out = run(
        "unit", "create", "--save", SAVE, "--kind", "team", "--name", "A", "--parent", "9", code=1
    )
    assert "no unit 9" in out
    assert "give --person or --remove" in run("unit", "lead", "--save", SAVE, "--unit", "1", code=1)
    assert "founder has no morale" in run("morale", "--save", SAVE, "--person", "1", code=1)


def test_reparent_a_team(save_dir: Path) -> None:
    run("unit", "create", "--save", SAVE, "--kind", "department", "--name", "Eng")
    run("unit", "create", "--save", SAVE, "--kind", "team", "--name", "Web")
    preview = run("unit", "reparent", "--save", SAVE, "--unit", "2", "--parent", "1", "--preview")
    assert "Costs 2 energy." in preview and "No one's morale changes." in preview
    run("unit", "reparent", "--save", SAVE, "--unit", "2", "--parent", "1")
    assert "\n    Web (team 2" in run("org", "--save", SAVE)  # two levels down, under Eng
    out = run("unit", "reparent", "--save", SAVE, "--unit", "1", "--parent", "2", code=1)
    assert "under the company or a division" in out


def test_plan_focus(save_dir: Path) -> None:
    out = run(
        "plan", "create", "--save", SAVE, "--owner", "4", "--role", "designer",
        "--target", "1", "--focus", "potential",
    )  # fmt: skip
    assert "spotting potential" in out
    out = run("plan", "update", "--save", SAVE, "--plan", "1", "--focus", "current")
    assert "best now" in out


def test_rename_a_unit(save_dir: Path) -> None:
    run("unit", "create", "--save", SAVE, "--kind", "team", "--name", "Web")
    run("unit", "rename", "--save", SAVE, "--unit", "1", "--name", "Platform")
    assert "Platform (team 1" in run("org", "--save", SAVE)
    assert "already named" in run(
        "unit", "rename", "--save", SAVE, "--unit", "1", "--name", "Platform", code=1
    )
