"""M1b CLI: hiring is playable without screens (the brief's manual check, automated)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tst.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def save_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "saves"
    monkeypatch.setenv("TST_SAVE_DIR", str(path))
    return path


def run(*args: str, code: int = 0) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == code, result.output
    return result.output


def new_game() -> None:
    run(
        "new-game",
        "--seed",
        "11",
        "--name",
        "m1b",
        "--scenario",
        "ex_big_tech_founders",
        "--company-name",
        "Test Co",
        "--mission",
        "ai,enterprise",
    )


def test_manual_check_flow() -> None:
    new_game()
    out = run(
        "search", "open", "--save", "m1b", "--role", "software_engineer", "--channel", "job_post"
    )
    assert "Opened search 1: software_engineer via job_post; energy 96/100" in out
    assert "1  Software engineer" in run("search", "list", "--save", "m1b")
    run("advance", "--save", "m1b", "--turns", "1")

    listing = run("candidates", "--save", "m1b")
    ids = [int(m) for m in re.findall(r"^\s+(\d+)\s{2}", listing, flags=re.MULTILINE)]
    asks = [int(a.replace(",", "")) for a in re.findall(r"ask \$([\d,]+)\.00", listing)]
    assert len(ids) == len(asks) >= 6
    assert "potential" in listing and "Software engineering" in listing

    out = run("interview", "--save", "m1b", "--candidate", str(ids[0]))
    assert "interests" in out and "energy 94/100" in out  # reset to 100 at Continue, then -6
    out = run("references", "--save", "m1b", "--candidate", str(ids[1]))
    assert "personality:" in out and "energy 91/100" in out

    target, ask = ids[0], asks[0]
    preview = run(
        "offer",
        "--save",
        "m1b",
        "--candidate",
        str(target),
        "--salary",
        str(ask),
        "--equity-bp",
        "50",
        "--preview",
    )
    assert re.search(r"Hint: (likely|uncertain|unlikely)\. Offer is 1\.00x the ask", preview)
    assert "always declined" in preview
    sent = run(
        "offer",
        "--save",
        "m1b",
        "--candidate",
        str(target),
        "--salary",
        str(round(ask * 1.6)),
        "--equity-bp",
        "50",
    )
    assert "Offer 1 sent" in sent
    run("advance", "--save", "m1b", "--turns", "1")

    inbox = run("inbox", "--save", "m1b", "--mark-read")
    assert "accepted your offer" in inbox and "candidates for Software engineer" in inbox
    assert run("inbox", "--save", "m1b").strip() == "No messages."
    assert "accepted your offer" in run("inbox", "--save", "m1b", "--all")
    people = run("people", "--save", "m1b")
    assert "Founder" in people and f"{target:>4}" in people and "morale" in people

    inspect = run("inspect", "--save", "m1b")
    assert "Date:    Mar 2010" in inspect
    founder = run("inspect", "--save", "m1b", "--person", "founder")
    assert "level exec" in founder  # brief fix: the founder's employment level

    fired = run("fire", "--save", "m1b", "--person", str(target))
    assert "severance $" in fired
    assert f"{target:>4}" not in run("people", "--save", "m1b")
    run("search", "close", "--save", "m1b", "--search", "1")
    assert run("search", "list", "--save", "m1b").strip() == "No open searches."


def test_mission_default_and_errors() -> None:
    run("new-game", "--seed", "1", "--name", "d", "--company-name", "D")
    bad = runner.invoke(
        app, ["new-game", "--seed", "1", "--name", "e", "--company-name", "E", "--mission", "ai"]
    )
    assert bad.exit_code == 1 and "exactly 2 different interests" in bad.output
    out = runner.invoke(app, ["offer", "--save", "d", "--candidate", "9", "--salary", "90000"])
    assert out.exit_code == 1 and "no open candidate 9" in out.output
    out = runner.invoke(app, ["interview", "--save", "d", "--candidate", "9"])
    assert out.exit_code == 1 and "no open candidate 9" in out.output
    out = runner.invoke(app, ["fire", "--save", "d", "--person", "1"])
    assert out.exit_code == 1 and "founder cannot be fired" in out.output
    out = runner.invoke(
        app, ["search", "open", "--save", "d", "--role", "pilot", "--channel", "network"]
    )
    assert out.exit_code == 1 and "unknown role 'pilot'" in out.output
    assert run("candidates", "--save", "d").startswith("No candidates.")
