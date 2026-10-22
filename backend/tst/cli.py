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
from tst.sim.people.models import current_ability, growth_role
from tst.sim.setup import DEFAULT_FOUNDER
from tst.sim.state import GameState

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
def inspect(
    save: Annotated[str, typer.Option(help="Save slug")],
    person: Annotated[
        str | None,
        typer.Option(help="'founder' or a person id: print TRUE values (debug only, not the API)"),
    ] = None,
) -> None:
    """Print the company summary (date, cash, burn, runway), or one person's true values."""
    settings, data = _context()
    try:
        path = repository.existing_save_path(settings.resolved_save_dir(), save)
        with repository.open_session(path) as session:
            if person is not None:
                state = repository.load_state(session)
                _print_person(state, person, data)
                return
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


def _print_person(state: GameState, which: str, data: LoadedData) -> None:
    """Debug view of TRUE values. Never expose this through the API (ADR-0007)."""
    if which == "founder":
        found = next((p for p in state.people if p.is_founder), None)
    elif which.isdigit():
        found = next((p for p in state.people if p.id == int(which)), None)
    else:
        raise _fail("--person takes 'founder' or a person id")
    if found is None:
        raise _fail(f"no person {which!r} in this save")
    game = data.game_data
    role = growth_role(found, game)
    typer.echo(f"{found.first_name} {found.last_name} (person {found.id}, {found.region})")
    typer.echo(f"Date:        {format_turn(state.turn)}; age {found.age(state.turn)}")
    kind = "best-fit role" if found.role is None else "role"
    typer.echo(f"Role:        {role.key} ({kind}); level {found.level or 'n/a'}")
    typer.echo(
        f"Ability:     CA {current_ability(found, game):.1f} / PA {found.potential_ability:.1f}"
    )
    typer.echo(f"Interests:   {', '.join(found.interests)}; work style {found.work_style}")
    typer.echo(f"Tags:        {', '.join(found.tags) or '(none)'}")
    typer.echo("Skills:")
    for key, value in found.skills.items:
        marker = "*" if key in role.primary else ("+" if key in role.secondary else " ")
        typer.echo(f"  {marker} {key:<22} {value:5.2f}")
    typer.echo("Personality:")
    for key, value in found.personality.items:
        typer.echo(f"    {key:<22} {value:5.2f}")
    typer.echo("Hidden:")
    for key, value in found.hidden.items:
        typer.echo(f"    {key:<22} {value:5.2f}")


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
