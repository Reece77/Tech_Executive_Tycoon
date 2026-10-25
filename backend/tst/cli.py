"""Headless commands: new-game, advance, inspect, list, hiring (M1b), and the org (M2a).

Hiring commands call the same action functions as the API, with the founder as actor.
They show what the company knows (ranges), never true values; only `inspect --person`
prints true values, as a debug view.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Any

import typer

from tst.api import org_views, views
from tst.config import Settings
from tst.db import inbox as inbox_db
from tst.db import repository
from tst.loader import DataLoadError, LoadedData, load_all
from tst.sim.actions import (
    Action,
    ActionResult,
    ClosePlan,
    CloseSearch,
    CreatePlan,
    CreateUnit,
    DissolveUnit,
    Fire,
    GiveRaise,
    Interview,
    MakeOffer,
    MovePerson,
    MoveUnit,
    OpenSearch,
    Promote,
    ReferenceCheck,
    RenameUnit,
    SetLeader,
    SetPolicy,
    UpdatePlan,
)
from tst.sim.calendar import format_turn
from tst.sim.data_models import DEFAULT_DIFFICULTY
from tst.sim.errors import SimError
from tst.sim.hiring.phases import monthly_costs
from tst.sim.hiring.rules import offer_preview
from tst.sim.money import cents, format_money
from tst.sim.people.founder import FounderSpec
from tst.sim.people.models import current_ability, growth_role
from tst.sim.setup import DEFAULT_FOUNDER
from tst.sim.state import GameState, company_cash

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


# --- Organization (M2a) ---------------------------------------------------------------------

unit_app = typer.Typer(no_args_is_help=True, help="Create, dissolve, lead and staff org units")
app.add_typer(unit_app, name="unit")
plan_app = typer.Typer(no_args_is_help=True, help="Hiring plans run by delegates")
app.add_typer(plan_app, name="plan")

PreviewOpt = Annotated[bool, typer.Option(help="Show the effect without doing it")]
ROOT_UNIT = "root"  # --unit value for the company root
BP_PER_RATIO = 10_000
FOCUS_LABELS = {"current": "best now", "potential": "spotting potential"}


def _unit_arg(value: str | None) -> int | None:
    """A unit id, or None for the company root ('root' or omitted)."""
    if value is None or value == ROOT_UNIT:
        return None
    if not value.isdigit():
        raise _fail(f"--unit takes a unit id or '{ROOT_UNIT}'")
    return int(value)


def _org_preview(state: GameState, data: LoadedData, action: Action) -> None:
    pv = org_views.change_preview(state, action, data)
    if not pv.allowed:
        typer.echo(f"Not allowed: {pv.problem}")
        return
    typer.echo(f"Costs {pv.energy_cost} energy.")
    if not pv.morale_changes:
        typer.echo("No one's morale changes.")
    for change in pv.morale_changes:
        typer.echo(f"  {change.name:<24} morale {change.change:+.0f}")


def _org_run(save: str, action: Action, preview: bool = False) -> None:
    path, data, state = _game(save)
    if preview:
        _org_preview(state, data, action)
        return
    _run(path, data, action)
    typer.echo(f"Done; {_energy(_game(save)[2], data)}")


@app.command("org")
def org_tree(save: SaveOpt) -> None:
    """Show the org chart: units, leaders, members, and each manager's span."""
    _, data, state = _game(save)
    org = org_views.org_out(state, state.player.id, data)
    units = {u.unit_id: u for u in org.units}
    managers = {m.person_id: m for m in org.managers}

    def show(unit_id: int | None, depth: int) -> None:
        unit = units[unit_id]
        pad = "  " * depth
        own = unit.policy or f"inherits {unit.effective_policy}"
        label = unit.kind if unit_id is None else f"{unit.kind} {unit_id}"
        typer.echo(f"{pad}{unit.name} ({label}; {own}); leader {unit.leader_name or 'none'}")
        for m in unit.members:
            span = ""
            if m.person_id in managers:
                mgr = managers[m.person_id]
                over = "  OVER SPAN" if mgr.over_span else ""
                span = (
                    f"  manages {len(mgr.reports)} (limit {mgr.span_limit}, "
                    f"S {mgr.span_factor:.2f}){over}"
                )
            lead = " *" if m.is_leader else "  "
            typer.echo(f"{pad} {lead}{m.person_id:>4}  {m.name:<24} {m.role_label:<20}{span}")
        for child in unit.child_unit_ids:
            show(child, depth + 1)

    show(None, 0)
    if not org.departments_unlocked:
        typer.echo(
            f"Departments unlock at {data.balance.org.department_unlock_headcount} staff "
            f"(you have {org.headcount})."
        )


@unit_app.command("create")
def unit_create(
    save: SaveOpt,
    kind: Annotated[str, typer.Option(help="team|department")],
    name: Annotated[str, typer.Option(help="Unit name")],
    parent: Annotated[int | None, typer.Option(help="Parent department id (teams only)")] = None,
) -> None:
    """Create a team (under the company or a department) or a department."""
    path, data, state = _game(save)
    result = _run(path, data, CreateUnit(_actor(state), kind, name, parent))  # type: ignore[arg-type]
    unit = max(result.new_state.units, key=lambda u: u.id)
    typer.echo(f"Created {unit.kind} {unit.id}: {unit.name}; {_energy(result.new_state, data)}")


@unit_app.command("dissolve")
def unit_dissolve(
    save: SaveOpt, unit: Annotated[int, typer.Option(help="Unit id")], preview: PreviewOpt = False
) -> None:
    """Dissolve a unit: its members and teams move to its parent (members lose 2 morale)."""
    _org_run(save, DissolveUnit(_actor(_game(save)[2]), unit), preview)


@unit_app.command("rename")
def unit_rename(
    save: SaveOpt,
    unit: Annotated[int, typer.Option(help="Unit id")],
    name: Annotated[str, typer.Option(help="New name")],
) -> None:
    """Rename a department or team (free)."""
    _org_run(save, RenameUnit(_actor(_game(save)[2]), unit, name))


@unit_app.command("reparent")
def unit_reparent(
    save: SaveOpt,
    unit: Annotated[int, typer.Option(help="Team id")],
    parent: Annotated[str, typer.Option(help="Department id, or 'root'")],
    preview: PreviewOpt = False,
) -> None:
    """Move a team under a department or the company; its members go with it."""
    _org_run(save, MoveUnit(_actor(_game(save)[2]), unit, _unit_arg(parent)), preview)


@unit_app.command("lead")
def unit_lead(
    save: SaveOpt,
    unit: Annotated[int, typer.Option(help="Unit id")],
    person: Annotated[int | None, typer.Option(help="New leader (a member of the unit)")] = None,
    remove: Annotated[bool, typer.Option(help="Remove the current leader")] = False,
    preview: PreviewOpt = False,
) -> None:
    """Set, replace or remove a unit's leader."""
    if (person is None) == (not remove):
        raise _fail("give --person or --remove")
    _org_run(save, SetLeader(_actor(_game(save)[2]), unit, None if remove else person), preview)


@unit_app.command("move")
def unit_move(
    save: SaveOpt,
    person: Annotated[int, typer.Option(help="Person id")],
    unit: Annotated[str | None, typer.Option(help="Unit id, or 'root'")] = None,
    preview: PreviewOpt = False,
) -> None:
    """Move someone to another unit (they lose 2 morale)."""
    _org_run(save, MovePerson(_actor(_game(save)[2]), person, _unit_arg(unit)), preview)


@unit_app.command("policy")
def unit_policy(
    save: SaveOpt,
    policy: Annotated[str, typer.Option(help="office|remote|inherit")],
    unit: Annotated[str | None, typer.Option(help="Unit id, or 'root' for the company")] = None,
) -> None:
    """Set a unit's (or the company's) work-location policy."""
    chosen = None if policy == "inherit" else policy
    _org_run(save, SetPolicy(_actor(_game(save)[2]), _unit_arg(unit), chosen))  # type: ignore[arg-type]


def _pay_preview(state: GameState, data: LoadedData, action: GiveRaise | Promote) -> None:
    pv = org_views.pay_preview(state, action, data)
    if not pv.allowed:
        typer.echo(f"Not allowed: {pv.problem}")
    typer.echo(
        f"Level {pv.level} -> {pv.new_level}; salary {format_money(pv.salary_cents)} -> "
        f"{format_money(pv.new_salary_cents)}; market rate {format_money(pv.market_rate_cents)}"
        f" -> {format_money(pv.new_market_rate_cents)}"
    )
    typer.echo(
        f"Pay term {pv.pay_term:+.1f} -> {pv.new_pay_term:+.1f}; one-off morale "
        f"{pv.morale_change:+.0f}; costs {pv.energy_cost} energy"
    )


@app.command("raise")
def give_raise(
    save: SaveOpt,
    person: Annotated[int, typer.Option(help="Person id")],
    salary: Annotated[str, typer.Option(help="New annual salary in dollars, e.g. 98000")],
    preview: PreviewOpt = False,
) -> None:
    """Change someone's salary from the next payroll (5%+ raises lift morale once a year)."""
    path, data, state = _game(save)
    try:
        salary_cents = cents(salary)
    except SimError as exc:
        raise _fail(exc.message) from exc
    action = GiveRaise(_actor(state), person, salary_cents)
    if preview:
        _pay_preview(state, data, action)
        return
    result = _run(path, data, action)
    typer.echo(
        f"Salary of person {person} is now {format_money(salary_cents)}; "
        f"{_energy(result.new_state, data)}"
    )


@app.command()
def promote(
    save: SaveOpt,
    person: Annotated[int, typer.Option(help="Person id")],
    preview: PreviewOpt = False,
) -> None:
    """Promote someone one level (+5 morale; the new level's market rate applies)."""
    path, data, state = _game(save)
    action = Promote(_actor(state), person)
    if preview:
        _pay_preview(state, data, action)
        return
    result = _run(path, data, action)
    employment = result.new_state.employment_of(person)
    assert employment is not None
    typer.echo(f"Person {person} is now {employment.level}; {_energy(result.new_state, data)}")


def _ratio_bp(ratio: float) -> int:
    return round(ratio * BP_PER_RATIO)


def _plan_line(plan: Any) -> str:
    activity = plan.last_activity
    last = f"; {activity.date_label}: {activity.summary}" if activity else ""
    return (
        f"{plan.plan_id:>3}  {plan.role_label:<20} {plan.hired}/{plan.target} hired, "
        f"{plan.pending_offers} pending  owner {plan.owner_name} ({plan.owner_energy} energy)  "
        f"unit {plan.unit_name}  {plan.channel} at {plan.ratio_bp / BP_PER_RATIO:.2f}x  "
        f"{FOCUS_LABELS.get(plan.focus, plan.focus)}  "
        f"[{plan.status}]{last}"
    )


@plan_app.command("create")
def plan_create(
    save: SaveOpt,
    owner: Annotated[int, typer.Option(help="Delegate's person id (not the founder)")],
    role: Annotated[str, typer.Option(help="Role key, e.g. software_engineer")],
    target: Annotated[int, typer.Option(help="Hires wanted")],
    channel: Annotated[str, typer.Option(help="any|job_post|recruiter|network")] = "any",
    ratio: Annotated[float, typer.Option(help="Salary offered as a multiple of the ask")] = 1.0,
    equity_bp: Annotated[int, typer.Option("--equity-bp", help="Equity per offer, bp")] = 0,
    unit: Annotated[str | None, typer.Option(help="Unit the hires join, or 'root'")] = None,
    focus: Annotated[
        str, typer.Option(help="current (best now) or potential (juniors and mids)")
    ] = "current",
) -> None:
    """Create a hiring plan; the delegate works it each month on their own energy."""
    path, data, state = _game(save)
    action = CreatePlan(
        _actor(state),
        owner,
        role,
        target,
        channel,  # type: ignore[arg-type]
        _ratio_bp(ratio),
        equity_bp,
        _unit_arg(unit),
        focus,  # type: ignore[arg-type]
    )
    result = _run(path, data, action)
    plan = max(result.new_state.plans, key=lambda p: p.id)
    typer.echo(_plan_line(org_views.plan_out(result.new_state, plan, data)))


@plan_app.command("list")
def plan_list(save: SaveOpt) -> None:
    """List hiring plans that are not closed."""
    _, data, state = _game(save)
    plans = state.live_plans(state.player.id)
    if not plans:
        typer.echo("No hiring plans.")
    for plan in plans:
        typer.echo(_plan_line(org_views.plan_out(state, plan, data)))


@plan_app.command("update")
def plan_update(
    save: SaveOpt,
    plan: Annotated[int, typer.Option(help="Plan id")],
    owner: Annotated[int | None, typer.Option(help="New delegate")] = None,
    target: Annotated[int | None, typer.Option(help="Hires wanted")] = None,
    channel: Annotated[str | None, typer.Option(help="any|job_post|recruiter|network")] = None,
    ratio: Annotated[float | None, typer.Option(help="Salary multiple of the ask")] = None,
    equity_bp: Annotated[int | None, typer.Option("--equity-bp", help="Equity, bp")] = None,
    unit: Annotated[str | None, typer.Option(help="Unit id, or 'root'")] = None,
    focus: Annotated[str | None, typer.Option(help="current or potential")] = None,
) -> None:
    """Change a plan; a paused plan restarts once its owner is on staff."""
    path, data, state = _game(save)
    current = state.plan(plan)
    if current is None or current.status == "closed":
        raise _fail(f"no hiring plan {plan}")
    action = UpdatePlan(
        _actor(state),
        plan,
        owner_id=current.owner_id if owner is None else owner,
        role=current.role,
        target=current.target if target is None else target,
        channel=current.channel if channel is None else channel,  # type: ignore[arg-type]
        ratio_bp=current.ratio_bp if ratio is None else _ratio_bp(ratio),
        equity_bp=current.equity_bp if equity_bp is None else equity_bp,
        unit_id=current.unit_id if unit is None else _unit_arg(unit),
        focus=current.focus if focus is None else focus,  # type: ignore[arg-type]
    )
    result = _run(path, data, action)
    updated = result.new_state.plan(plan)
    assert updated is not None
    typer.echo(_plan_line(org_views.plan_out(result.new_state, updated, data)))


@plan_app.command("close")
def plan_close(save: SaveOpt, plan: Annotated[int, typer.Option(help="Plan id")]) -> None:
    """Close a plan (free). Offers it already made still get their answer."""
    path, data, state = _game(save)
    _run(path, data, ClosePlan(_actor(state), plan))
    typer.echo(f"Closed hiring plan {plan}")


@app.command()
def morale(save: SaveOpt, person: Annotated[int, typer.Option(help="Person id")]) -> None:
    """Why someone's morale is moving: this month's target, term by term (what you know)."""
    path, data, _ = _game(save)
    with repository.open_session(path) as session:
        state = repository.load_state(session)
        cash = company_cash(repository.ledger_balances(session), state.player.id)
    projected = sum(a for _, _, a in monthly_costs(state, state.player.id, data.balance))
    try:
        b = org_views.morale_breakdown(state, state.player.id, person, data, cash, projected)
    except SimError as exc:
        raise _fail(exc.message) from exc
    name = views.person_name(state.person(person))
    manager = f"; manager {b.manager_name}" if b.manager_name else ""
    typer.echo(f"{name}: morale {b.morale:.1f}, heading for {b.target:.1f}{manager}")
    for t in b.terms:
        typer.echo(f"  {t.label:<34} {t.value:+7.2f}")


if __name__ == "__main__":
    app()
