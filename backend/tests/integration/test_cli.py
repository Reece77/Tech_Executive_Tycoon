from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

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
    assert "Runway:  n/a" in out

    out = run("advance", "--save", "dev", "--turns", "24")
    assert "now Jan 2012" in out

    out = run("inspect", "--save", "dev")
    assert "Date:    Jan 2012 (turn 24)" in out
    assert "Cash:    $2,000.00" in out  # $50,000 - 24 x $2,000
    assert "Burn:    $2,000.00 / month" in out
    assert "Runway:  1 month\n" in out

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
