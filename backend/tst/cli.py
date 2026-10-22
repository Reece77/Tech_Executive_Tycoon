"""Headless commands: `tst new-game`, `tst advance`, `tst inspect`, `tst list`."""

from __future__ import annotations

from typing import Annotated

import typer

from tst.config import Settings
from tst.db import repository
from tst.loader import DataLoadError, LoadedData, load_all
from tst.sim.calendar import format_turn
from tst.sim.data_models import DEFAULT_DIFFICULTY
from tst.sim.errors import SimError
from tst.sim.money import CENTS_PER_DOLLAR, Cents
from tst.sim.people.founder import FounderSpec
from tst.sim.setup import DEFAULT_FOUNDER

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Tech Startup Tycoon")


def format_money(amount: Cents) -> str:
    """$1,234.56 style; negative amounts as -$1,234.56."""
    sign = "-" if amount < 0 else ""
    dollars, cents = divmod(abs(amount), CENTS_PER_DOLLAR)
    return f"{sign}${dollars:,}.{cents:02d}"


def _fail(message: str) -> typer.Exit:
    typer.echo(f"error: {message}", err=True)
    return typer.Exit(code=1)


def _context() -> tuple[Settings, LoadedData]:
    settings = Settings()
    try:
        return settings, load_all(settings.data_dir)
    except DataLoadError as exc:
        raise _fail(str(exc)) from exc


@app.command("new-game")
def new_game(
    seed: Annotated[int, typer.Option(help="Master seed (0..2**63-1)")],
    name: Annotated[str, typer.Option(help="Save slug, e.g. dev")],
    company_name: Annotated[str, typer.Option(help="Company name")],
    scenario: Annotated[str, typer.Option(help="Scenario id")] = "garage_bootstrap",
    difficulty: Annotated[str, typer.Option(help="easy|standard|hard|ironman")] = (
        DEFAULT_DIFFICULTY
    ),
    founder_background: Annotated[
        str, typer.Option(help="engineer|salesperson|academic|ex_big_tech")
    ] = DEFAULT_FOUNDER.background,
    founder_preset: Annotated[
        str | None,
        typer.Option(help="visionary|operator|hustler|scientist; omit for a random personality"),
    ] = None,
) -> None:
    """Create a new save file at schema head, with a founder built from a background."""
    settings, data = _context()
    founder = FounderSpec(background=founder_background, personality_preset=founder_preset)
    try:
        path = repository.create_save(
            name,
            seed,
            scenario,
            company_name=company_name,
            difficulty=difficulty,
            founder=founder,
            data=data,
            save_dir=settings.resolved_save_dir(),
        )
    except SimError as exc:
        raise _fail(exc.message) from exc
    typer.echo(f"Created {path.name}: {company_name}, {format_turn(0)}")


@app.command()
def advance(
    save: Annotated[str, typer.Option(help="Save slug")],
    turns: Annotated[int, typer.Option(min=1, help="Turns to play")] = 1,
) -> None:
    """Play N monthly turns, each in its own transaction."""
    settings, data = _context()
    try:
        path = repository.existing_save_path(settings.resolved_save_dir(), save)
        result = None
        for _ in range(turns):
            result = repository.run_turn(path, data)
    except SimError as exc:
        raise _fail(exc.message) from exc
    assert result is not None
    typer.echo(f"Advanced {turns} turn(s); now {format_turn(result.new_state.turn)}")


@app.command()
def inspect(save: Annotated[str, typer.Option(help="Save slug")]) -> None:
    """Print the company summary: date, cash, burn, runway."""
    settings, _ = _context()
    try:
        path = repository.existing_save_path(settings.resolved_save_dir(), save)
        with repository.open_session(path) as session:
            ov = repository.player_overview(session, history=1)
    except SimError as exc:
        raise _fail(exc.message) from exc
    if ov.runway_months is None:
        runway = "n/a (not burning cash)"
    else:
        runway = f"{ov.runway_months} month{'' if ov.runway_months == 1 else 's'}"
    typer.echo(f"{ov.company_name} ({ov.slug}, {ov.scenario_id})")
    typer.echo(f"Date:    {ov.date_label} (turn {ov.turn})")
    typer.echo(f"Cash:    {format_money(ov.cash_cents)}")
    typer.echo(f"Burn:    {format_money(ov.monthly_burn_cents)} / month")
    typer.echo(f"Runway:  {runway}")


@app.command("list")
def list_saves() -> None:
    """List saves in TST_SAVE_DIR."""
    settings = Settings()
    saves = repository.list_saves(settings.resolved_save_dir())
    if not saves:
        typer.echo("No saves.")
        return
    for s in saves:
        typer.echo(
            f"{s.slug:<24} {s.company_name:<30} {format_turn(s.current_turn):<9} {s.scenario_id}"
        )


if __name__ == "__main__":
    app()
