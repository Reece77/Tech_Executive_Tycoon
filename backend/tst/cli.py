"""Headless commands: new-game, advance, inspect, list, and hiring (M1b).

Hiring commands call the same action functions as the API, with the founder as actor.
They show what the company knows (ranges), never true values; only `inspect --person`
prints true values, as a debug view.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Any

import typer

from tst.api import views
from tst.config import Settings
from tst.db import inbox as inbox_db
from tst.db import repository
from tst.loader import DataLoadError, LoadedData, load_all
from tst.sim.actions import (
    Action,
    ActionResult,
    CloseSearch,
    Fire,
    Interview,
    MakeOffer,
    OpenSearch,
    ReferenceCheck,
)
from tst.sim.calendar import format_turn
from tst.sim.data_models import DEFAULT_DIFFICULTY
from tst.sim.errors import SimError
from tst.sim.hiring.rules import offer_preview
from tst.sim.money import cents, format_money
from tst.sim.people.founder import FounderSpec
from tst.sim.people.models import current_ability, growth_role
from tst.sim.setup import DEFAULT_FOUNDER
from tst.sim.state import GameState

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Tech Startup Tycoon")


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
    mission: Annotated[
        str | None,
        typer.Option(
            help="Two interests, comma-separated (e.g. ai,enterprise); default: the "
            "founder's first two"
        ),
    ] = None,
) -> None:
    """Create a new save file at schema head, with a founder built from a background."""
    settings, data = _context()
    founder = FounderSpec(background=founder_background, personality_preset=founder_preset)
    chosen = None if mission is None else tuple(k.strip() for k in mission.split(",") if k.strip())
    try:
        path = repository.create_save(
            name,
            seed,
            scenario,
            company_name=company_name,
            difficulty=difficulty,
            founder=founder,
            mission=chosen,
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
            ov = repository.player_overview(session, history=1, balance=data.balance)
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
    typer.echo(f"Runway:  {runway} at this month's projected costs")


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
    employment = state.employment_of(found.id)
    level = employment.level if employment else found.level
    typer.echo(f"Role:        {role.key} ({kind}); level {level or 'n/a'}")
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


# --- Hiring (M1b) ---------------------------------------------------------------------------

search_app = typer.Typer(no_args_is_help=True, help="Open, close and list searches")
app.add_typer(search_app, name="search")

SaveOpt = Annotated[str, typer.Option("--save", help="Save slug")]


def _game(save: str) -> tuple[Path, LoadedData, GameState]:
    settings, data = _context()
    try:
        path = repository.existing_save_path(settings.resolved_save_dir(), save)
        with repository.open_session(path) as session:
            return path, data, repository.load_state(session)
    except SimError as exc:
        raise _fail(exc.message) from exc


def _actor(state: GameState) -> int:
    founder = state.founder_of(state.player.id)
    if founder is None:
        raise _fail("this save has no founder to act")
    return founder.id


def _run(path: Path, data: LoadedData, action: Action) -> ActionResult:
    try:
        return repository.run_action(path, data, action)
    except SimError as exc:
        raise _fail(exc.message) from exc


def _energy(state: GameState, data: LoadedData) -> str:
    e = views.energy(state, data)
    return f"energy {e.energy}/{e.max}"


def _ranges(attrs: list[Any], keys: Iterable[str]) -> str:
    by_key = {a.key: a for a in attrs}
    parts = []
    for key in keys:
        r = by_key[key].range
        shown = f"{r.min}" if r.min == r.max else f"{r.min}-{r.max}"
        parts.append(f"{by_key[key].label} {shown}")
    return ", ".join(parts)


@search_app.command("open")
def search_open(
    save: SaveOpt,
    role: Annotated[str, typer.Option(help="Role key, e.g. software_engineer")],
    channel: Annotated[str, typer.Option(help="network|job_post|recruiter")],
) -> None:
    """Open a search; candidates arrive at the end of this month."""
    path, data, state = _game(save)
    result = _run(path, data, OpenSearch(_actor(state), role, channel))  # type: ignore[arg-type]
    search = max(result.new_state.searches, key=lambda s: s.id)
    typer.echo(
        f"Opened search {search.id}: {search.role} via {search.channel}; "
        f"{_energy(result.new_state, data)}"
    )


@search_app.command("close")
def search_close(
    save: SaveOpt, search: Annotated[int, typer.Option("--search", help="Search id")]
) -> None:
    """Close a search (a job post stops costing money; its candidates stay until they expire)."""
    path, data, state = _game(save)
    _run(path, data, CloseSearch(_actor(state), search))
    typer.echo(f"Closed search {search}")


@search_app.command("list")
def search_list(save: SaveOpt) -> None:
    """List open searches."""
    _, data, state = _game(save)
    searches = state.open_searches(state.player.id)
    if not searches:
        typer.echo("No open searches.")
    for s in searches:
        out = views.search_out(state, s, data)
        cost = f", {format_money(out.monthly_cost_cents)}/month" if out.monthly_cost_cents else ""
        typer.echo(
            f"{out.search_id:>3}  {out.role_label:<22} {out.channel:<10} "
            f"opened {format_turn(out.opened_turn)}, {out.open_candidates} candidates{cost}"
        )


@app.command()
def candidates(save: SaveOpt) -> None:
    """List open candidates with what you know about them."""
    _, data, state = _game(save)
    company = state.player.id
    found = state.open_candidates(company)
    if not found:
        typer.echo("No candidates. Open a search and advance a turn.")
    for c in found:
        p = views.person_summary(state, company, c.person_id, data)
        assert p.candidacy is not None and p.role is not None
        role = data.game_data.role(p.role)
        made = p.candidacy.pending_offer
        pending = f"; offer {format_money(made.salary_cents)} pending" if made else ""
        if p.candidacy.offer_blocked_reason == views.INTERVIEW_REQUIRED:
            pending += "; interview first"
        typer.echo(
            f"{p.person_id:>4}  {p.name:<24} {p.level:<7} {p.role_label:<20} age {p.age:<3} "
            f"ask {format_money(p.candidacy.salary_expectation_cents)}  "
            f"until {format_turn(p.candidacy.expires_turn)}  potential {p.potential_phrase}"
            f"{pending}"
        )
        typer.echo(f"        {_ranges(p.skills, role.primary)}")


def _show_profile(path: Path, data: LoadedData, person_id: int) -> None:
    with repository.open_session(path) as session:
        state = repository.load_state(session)
        p = views.person_profile(session, state, state.player.id, person_id, data)
    typer.echo(f"{p.name} ({p.role_label}, {p.level}, age {p.age}); potential {p.potential_phrase}")
    if p.interests is not None:
        typer.echo(f"  interests {', '.join(p.interests)}; work style {p.work_style}")
    typer.echo(f"  skills: {_ranges(p.skills, [s.key for s in p.skills])}")
    typer.echo(f"  personality: {_ranges(p.personality, [t.key for t in p.personality])}")
    for tag in p.noticed_tags:
        typer.echo(f"  noticed: {p.name.split()[0]} {tag.text}")
    typer.echo(f"  {_energy(state, data)}")


@app.command()
def interview(
    save: SaveOpt, candidate: Annotated[int, typer.Option("--candidate", help="Candidate id")]
) -> None:
    """Interview a candidate (6 energy): narrows skills, personality and potential."""
    path, data, state = _game(save)
    _run(path, data, Interview(_actor(state), candidate))
    _show_profile(path, data, candidate)


@app.command()
def references(
    save: SaveOpt, candidate: Annotated[int, typer.Option("--candidate", help="Candidate id")]
) -> None:
    """Check a candidate's references (3 energy): narrows personality and potential."""
    path, data, state = _game(save)
    _run(path, data, ReferenceCheck(_actor(state), candidate))
    _show_profile(path, data, candidate)


@app.command()
def offer(
    save: SaveOpt,
    candidate: Annotated[int, typer.Option("--candidate", help="Candidate id")],
    salary: Annotated[str, typer.Option(help="Annual salary in dollars, e.g. 92000")],
    equity_bp: Annotated[int, typer.Option("--equity-bp", help="Equity in basis points")] = 0,
    preview: Annotated[bool, typer.Option(help="Show the hint without sending")] = False,
) -> None:
    """Make an offer (resolved at the next Continue), or preview it with --preview."""
    path, data, state = _game(save)
    try:
        salary_cents = cents(salary)
    except SimError as exc:
        raise _fail(exc.message) from exc
    c = state.candidate(candidate)
    if c is None or c.status != "open":
        raise _fail(f"no open candidate {candidate}")
    if preview:
        pv = offer_preview(
            state, c, salary_cents, equity_bp, data.balance, data.game_data, _actor(state)
        )
        typer.echo(
            f"Hint: {pv.hint}. Offer is {pv.ratio:.2f}x the ask of "
            f"{format_money(pv.expectation_cents)}; below {format_money(pv.floor_cents)} "
            "is always declined."
        )
        for problem in pv.problems:
            typer.echo(f"  would break: {problem}")
        return
    result = _run(path, data, MakeOffer(_actor(state), candidate, salary_cents, equity_bp))
    made = result.new_state.pending_offer_for(candidate)
    assert made is not None
    typer.echo(
        f"Offer {made.id} sent: {format_money(salary_cents)} and {equity_bp} bp. "
        "The answer comes at the next Continue."
    )


@app.command()
def fire(save: SaveOpt, person: Annotated[int, typer.Option("--person", help="Person id")]) -> None:
    """Fire an employee: severance is paid now and everyone else loses morale."""
    path, data, state = _game(save)
    result = _run(path, data, Fire(_actor(state), person))
    severance = sum(ln.amount for e in result.ledger_entries for ln in e.lines if ln.amount > 0)
    typer.echo(f"Fired person {person}; severance {format_money(severance)}")


@app.command()
def people(save: SaveOpt) -> None:
    """List your staff."""
    _, data, state = _game(save)
    company = state.player.id
    for e in sorted(state.staff(company), key=lambda e: e.person_id):
        p = views.person_summary(state, company, e.person_id, data)
        assert p.employment is not None
        morale = "" if p.morale is None else f"  morale {p.morale:.0f}"
        notice = "  (on notice)" if p.employment.status == "notice" else ""
        typer.echo(
            f"{p.person_id:>4}  {p.name:<24} {p.employment.level:<9} {p.role_label:<22} "
            f"{format_money(p.employment.salary_cents):>13}/yr{morale}{notice}"
        )


@app.command()
def inbox(
    save: SaveOpt,
    all_items: Annotated[bool, typer.Option("--all", help="Show read items too")] = False,
    mark_read: Annotated[bool, typer.Option(help="Mark the shown items read")] = False,
) -> None:
    """Show inbox messages, newest first (unread only unless --all)."""
    path, _, state = _game(save)
    with repository.open_session(path) as session, session.begin():
        items = inbox_db.list_inbox(session, state.player.id, unread_only=not all_items)
        if not items:
            typer.echo("No messages.")
        for m in items:
            flag = " " if m.read else "*"
            typer.echo(f"{flag} {format_turn(m.turn)}  {m.title}")
            typer.echo(f"    {m.body}")
            if mark_read and not m.read:
                inbox_db.mark_read(session, state.player.id, m.id)


if __name__ == "__main__":
    app()
