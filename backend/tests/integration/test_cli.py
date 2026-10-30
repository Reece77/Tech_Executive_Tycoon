from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.helpers import event_cash_cents
from tst.cli import app, format_money

runner = CliRunner()


@pytest.fixture(autouse=True)
def save_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "saves"
    monkeypatch.setenv("TST_SAVE_DIR", str(path))
    return path


def run(*args: str) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, result.output
    return result.output


def test_acceptance_flow(save_dir: Path) -> None:
    out = run(
        "new-game",
        "--seed",
        "42",
        "--name",
        "dev",
        "--scenario",
        "garage_bootstrap",
        "--company-name",
        "Test Co",
    )
    assert "Created dev.tst.sqlite" in out
    assert (save_dir / "dev.tst.sqlite").is_file()

    out = run("inspect", "--save", "dev")
    assert "Date:    Jan 2010" in out
    assert "Cash:    $50,000.00" in out
    # Runway at this month's projected costs, like the Overview (M1c decision): $50,000 / $1,100.
    assert "Runway:  45 months at this month's projected costs" in out

    out = run("advance", "--save", "dev", "--turns", "24")
    assert "now Jan 2012" in out

    out = run("inspect", "--save", "dev")
    assert "Date:    Jan 2012 (turn 24)" in out
    # $50,000 - 24 x ($500 overhead + $600 office), plus what events cost or brought (M6).
    cash = 2_360_000 + event_cash_cents(save_dir / "dev.tst.sqlite")
    assert f"Cash:    ${cash / 100:,.2f}" in out
    # Last month's burn includes what its events cost (M7a: a solo founder has early-days events).
    path = save_dir / "dev.tst.sqlite"
    burn = 110_000 - (
        event_cash_cents(path, through_turn=23) - event_cash_cents(path, through_turn=22)
    )
    assert f"Burn:    ${burn / 100:,.2f} / month" in out
    assert f"Runway:  {cash // 110_000} months at this month's projected costs\n" in out

    out = run("list")
    assert "dev" in out and "Test Co" in out and "Jan 2012" in out


def test_errors_exit_nonzero() -> None:
    result = runner.invoke(app, ["inspect", "--save", "missing"])
    assert result.exit_code == 1
    assert "no save named 'missing'" in result.output

    args = ["new-game", "--seed", "1", "--name", "x", "--company-name", "X"]
    result = runner.invoke(app, [*args, "--scenario", "mineral_first_prospector"])
    assert result.exit_code == 1
    assert "unlocks in v3" in result.output


def test_list_empty() -> None:
    assert run("list").strip() == "No saves."


@pytest.mark.parametrize(
    ("cents", "text"),
    [(0, "$0.00"), (5, "$0.05"), (123_456, "$1,234.56"), (-200_000, "-$2,000.00")],
)
def test_format_money(cents: int, text: str) -> None:
    assert format_money(cents) == text


def test_new_game_founder_options() -> None:
    out = run(
        "new-game",
        "--seed",
        "7",
        "--name",
        "m1a",
        "--company-name",
        "M1a Co",
        "--founder-background",
        "salesperson",
        "--founder-preset",
        "hustler",
    )
    assert "Created m1a.tst.sqlite" in out


@pytest.mark.parametrize(
    ("flag", "value", "message"),
    [
        ("--founder-background", "astronaut", "unknown background 'astronaut'"),
        ("--founder-background", "geologist", "unlocks in v3"),
        ("--founder-preset", "dreamer", "unknown personality preset 'dreamer'"),
    ],
)
def test_new_game_rejects_bad_founder(flag: str, value: str, message: str) -> None:
    args = ["new-game", "--seed", "1", "--name", "x", "--company-name", "X", flag, value]
    result = runner.invoke(app, args)
    assert result.exit_code == 1
    assert message in result.output


def test_inspect_person_founder() -> None:
    run(
        "new-game",
        "--seed",
        "7",
        "--name",
        "m1a",
        "--company-name",
        "M1a Co",
        "--founder-background",
        "engineer",
    )
    out = run("inspect", "--save", "m1a", "--person", "founder")
    assert "(person 1, north_america)" in out
    assert "age 28" in out
    assert "Ability:     CA" in out
    assert "* software_engineering   16.00" in out
    assert "Personality:" in out and "Hidden:" in out
    run("advance", "--save", "m1a", "--turns", "12")
    later = run("inspect", "--save", "m1a", "--person", "1")
    assert "Jan 2011" in later
    assert "* software_engineering   16.00" not in later  # skills moved

    result = runner.invoke(app, ["inspect", "--save", "m1a", "--person", "9"])
    assert result.exit_code == 1 and "no person '9'" in result.output
