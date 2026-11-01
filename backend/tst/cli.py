"""Headless commands: new-game, advance, inspect, list, hiring (M1b), the org (M2a), and
products and markets (M3a).

Hiring commands call the same action functions as the API, with the founder as actor.
They show what the company knows (ranges), never true values; only `inspect --person`
prints true values, as a debug view.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Any

import typer

from tst import holiday as hol
from tst.api import finance_views, org_views, product_views, views
from tst.config import Settings
from tst.db import inbox as inbox_db
from tst.db import repository
from tst.db import saves as saves_db
from tst.db.models import InboxItemRow
from tst.loader import DataLoadError, LoadedData, load_all
from tst.sim.actions import (
    AcceptBridge,
    AcceptTermSheet,
    Action,
    ActionResult,
    AddSegment,
    AssignUnit,
    CancelProduct,
    ClosePlan,
    CloseSearch,
    CreatePlan,
    CreateProduct,
    CreateUnit,
    DissolveUnit,
    Fire,
    GiveRaise,
    Interview,
    LaunchProduct,
    MakeOffer,
    MovePerson,
    MoveUnit,
    OpenSearch,
    Promote,
    RaiseSafe,
    ReferenceCheck,
    RenameUnit,
    ScoutSearch,
    SetLeader,
    SetMarketing,
    SetPolicy,
    SetPrice,
    StartRound,
    SunsetProduct,
    UnassignUnit,
    UpdatePlan,
)
from tst.sim.actions.products import assignment_of, own_product
from tst.sim.calendar import format_turn
from tst.sim.data_models import DEFAULT_DIFFICULTY
from tst.sim.errors import CriticalEventOpenError, SimError
from tst.sim.finance import statements as fs
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
    hq: Annotated[
        str | None, typer.Option(help="HQ city key (tst cities); default: San Francisco")
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
            hq_city=hq,
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
    except CriticalEventOpenError as exc:
        raise _fail(f"{exc.message} (tst events --save {save}; tst choose)") from exc
    except SimError as exc:
        raise _fail(exc.message) from exc
    assert result is not None
    typer.echo(f"Advanced {turns} turn(s); now {format_turn(result.new_state.turn)}")


@app.command()
def holiday(
    save: Annotated[str, typer.Option(help="Save slug")],
    months: Annotated[int | None, typer.Option(help="Months (1 to holiday.max_months)")] = None,
    stop: Annotated[
        str | None, typer.Option(help="minor|major|critical: stop after an event this severe")
    ] = None,
) -> None:
    """Continue month after month until a stop reason (formulas.md 17.1), then summarise."""
    settings, data = _context()
    keys = data.balance.holiday
    level = stop or keys.default_stop
    if level not in hol.STOP_LEVELS:
        raise _fail(f"--stop takes {', '.join(hol.STOP_LEVELS)}")
    try:
        path = repository.existing_save_path(settings.resolved_save_dir(), save)
        token = repository.reserve(path)
        try:
            with repository.holding(token):
                result = hol.run_holiday(
                    path,
                    data,
                    months if months is not None else keys.default_months,
                    level,
                )
        finally:
            repository.release(path, token)
    except CriticalEventOpenError as exc:
        raise _fail(f"{exc.message} (tst events --save {save}; tst choose)") from exc
    except SimError as exc:
        raise _fail(exc.message) from exc
    typer.echo(
        f"Holiday: {result.months_played} month(s), now {format_turn(result.end.turn)};"
        f" stopped because {hol.REASON_TEXT[result.reason]}"
    )
    with repository.open_session(path) as session:
        item = session.get(InboxItemRow, result.summary_item_id)
        typer.echo(item.body if item else "")


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
            ov = repository.player_overview(session, history=1, data=data)
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
    mrr = ov.history[-1][1].mrr_cents if ov.history else 0
    typer.echo(f"MRR:     {format_money(mrr)} (ARR {format_money(12 * mrr)})")


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


# --- Saves manager (M7b) -------------------------------------------------------------------

saves_app = typer.Typer(no_args_is_help=True, help="Rename, duplicate, delete and restore saves")
app.add_typer(saves_app, name="saves")


def _save_file(save: str) -> Path:
    settings = Settings()
    try:
        return repository.existing_save_path(settings.resolved_save_dir(), save)
    except SimError as exc:
        raise _fail(exc.message) from exc


def _show_save(s: saves_db.SaveFile) -> str:
    size = f"{s.size_bytes / 1_000_000:.1f} MB"
    return (
        f"{s.slug:<28} {s.display_name:<32} {s.company_name:<24} {s.scenario_id:<22}"
        f" {s.difficulty:<9} {format_turn(s.current_turn):<9} turn {s.current_turn:<4}"
        f" {s.game_state:<16} {s.last_played:%Y-%m-%d %H:%M} {size}"
    )


@saves_app.command("list")
def saves_list() -> None:
    """Every save, most recently played first, with its state, last play and size."""
    found = saves_db.list_files(Settings().resolved_save_dir())
    if not found:
        typer.echo("No saves.")
    for s in found:
        typer.echo(_show_save(s))


@saves_app.command("rename")
def saves_rename(
    save: Annotated[str, typer.Option(help="Save slug")],
    name: Annotated[str, typer.Option(help="New display name (the company keeps its name)")],
) -> None:
    """Change a save's display name."""
    try:
        typer.echo(_show_save(saves_db.rename(_save_file(save), name)))
    except SimError as exc:
        raise _fail(exc.message) from exc


@saves_app.command("duplicate")
def saves_duplicate(
    save: Annotated[str, typer.Option(help="Save slug")],
    name: Annotated[str, typer.Option(help="The copy's display name")],
) -> None:
    """Save as: copy a save under a new name (not for Ironman saves)."""
    try:
        typer.echo(_show_save(saves_db.duplicate(_save_file(save), name)))
    except SimError as exc:
        raise _fail(exc.message) from exc


@saves_app.command("delete")
def saves_delete(
    save: Annotated[str, typer.Option(help="Save slug")],
    confirm: Annotated[str, typer.Option(help="Type the save slug again to confirm")],
) -> None:
    """Delete a save and its backups."""
    if confirm != save:
        raise _fail("--confirm must repeat the save slug")
    try:
        saves_db.delete(_save_file(save))
    except SimError as exc:
        raise _fail(exc.message) from exc
    typer.echo(f"Deleted {save}")


@saves_app.command("restore")
def saves_restore(
    save: Annotated[str, typer.Option(help="Save slug")],
    backup: Annotated[
        str | None, typer.Option(help="Backup file name; omit to list the backups")
    ] = None,
) -> None:
    """List a save's backups, or restore one as a new save (not for Ironman saves)."""
    path = _save_file(save)
    try:
        if backup is None:
            found = saves_db.backups(path)
            if not found:
                typer.echo("No backups.")
            for b in found:
                typer.echo(
                    f"{b.backup_id:<56} {b.kind:<12} {format_turn(b.turn):<9}"
                    f" {b.created:%Y-%m-%d %H:%M}"
                )
            return
        typer.echo(_show_save(saves_db.restore(path, backup)))
    except SimError as exc:
        raise _fail(exc.message) from exc


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
    with repository.write_session(path) as session:
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
    projected = sum(
        a for _, _, a in monthly_costs(state, state.player.id, data.balance, data.game_data)
    )
    try:
        b = org_views.morale_breakdown(state, state.player.id, person, data, cash, projected)
    except SimError as exc:
        raise _fail(exc.message) from exc
    name = views.person_name(state.person(person))
    manager = f"; manager {b.manager_name}" if b.manager_name else ""
    typer.echo(f"{name}: morale {b.morale:.1f}, heading for {b.target:.1f}{manager}")
    for t in b.terms:
        typer.echo(f"  {t.label:<34} {t.value:+7.2f}")


# --- Products and markets (M3a) -------------------------------------------------------------

product_app = typer.Typer(no_args_is_help=True, help="Create, price, staff and launch products")
app.add_typer(product_app, name="product")
ProductOpt = Annotated[int, typer.Option("--product", help="Product id")]
HISTORY_MONTHS = 12


def _dollars(value: str) -> int:
    try:
        return cents(value)
    except SimError as exc:
        raise _fail(exc.message) from exc


def _product_out(path: Path, state: GameState, data: LoadedData, product_id: int) -> Any:
    try:
        product = own_product(state, state.player.id, product_id)
    except SimError as exc:
        raise _fail(exc.message) from exc
    with repository.open_session(path) as session:
        history = repository.product_history(session, product.id, state.turn - HISTORY_MONTHS)
    return product_views.product_out(state, product, history, data)


def _product_line(p: Any) -> str:
    return (
        f"{p.product_id:>3}  {p.name:<24} {p.category_label:<16} {p.lifecycle_label:<15} "
        f"Q {p.quality:5.1f}  F {p.feature_score:5.1f}  brand {p.brand:5.1f}  "
        f"MRR {format_money(p.mrr_cents)}"
    )


def _product_done(save: str, product_id: int, action: Action) -> None:
    path, data, _ = _game(save)
    result = _run(path, data, action)
    out = _product_out(path, result.new_state, data, product_id)
    typer.echo(_product_line(out))
    typer.echo(f"  {_energy(result.new_state, data)}")


@app.command()
def products(save: SaveOpt) -> None:
    """List your products."""
    path, data, state = _game(save)
    found = state.company_products(state.player.id)
    if not found:
        typer.echo("No products. Create one with `tst product create`.")
    for product in found:
        typer.echo(_product_line(_product_out(path, state, data, product.id)))


@product_app.command("create")
def product_create(
    save: SaveOpt,
    name: Annotated[str, typer.Option(help="Product name")],
    category: Annotated[str, typer.Option(help="b2b_saas|dev_tools|consumer_apps|cybersecurity")],
    segments: Annotated[str, typer.Option(help="Comma-separated, e.g. smb,mid_market")],
) -> None:
    """Create a product in development (quality 10, no features yet)."""
    _, _, state = _game(save)
    chosen = tuple(s.strip() for s in segments.split(",") if s.strip())
    action = CreateProduct(_actor(state), name, category, chosen)
    _product_done(save, state.next_ids.product, action)


@product_app.command("show")
def product_show(save: SaveOpt, product: ProductOpt) -> None:
    """Scores, segments, team, launch readiness and recent history of one product."""
    path, data, state = _game(save)
    p = _product_out(path, state, data, product)
    typer.echo(_product_line(p))
    rot = "; nobody works on it, so quality is falling" if p.rotting else ""
    typer.echo(f"  pace {p.pace}{rot}; marketing {format_money(p.marketing_budget_cents)}/month")
    typer.echo(f"  units: {', '.join(u.name for u in p.assigned_units) or 'none'}")
    for label, people in (
        ("builders", p.builders),
        ("sellers", p.sellers),
        ("marketers", p.marketers),
    ):
        typer.echo(f"  {label}: {', '.join(x.name for x in people) or 'none'}")
    for seg in p.segments:
        price = "no price" if seg.price_cents is None else f"{format_money(seg.price_cents)}/mo"
        appeal = "" if seg.appeal is None else f"  appeal {seg.appeal:.1f}"
        churn = "" if seg.churn_rate is None else f"  churn {seg.churn_rate:.1%}"
        typer.echo(
            f"  {seg.label:<11} {price:<14} customers {seg.customers:,.0f}  "
            f"share {seg.share_of_served:.1%}{appeal}{churn}  MRR {format_money(seg.mrr_cents)}"
        )
        if seg.note:
            typer.echo(f"    {seg.note}")
    if p.status == "in_development":
        if p.launch.ready:
            typer.echo("  Ready to launch: tst product launch")
        else:
            typer.echo(f"  Launch needs: {'; '.join(p.launch.missing)}")
    for m in p.history[-6:]:
        typer.echo(
            f"    {m.date_label}  {m.segment:<11} Q {m.quality:5.1f}  F {m.feature_score:5.1f}  "
            f"customers {m.customers:,.0f} (+{m.new:,.1f} / -{m.churned:,.1f})  "
            f"revenue {format_money(m.revenue_cents)}"
        )


@product_app.command("price")
def product_price(
    save: SaveOpt,
    product: ProductOpt,
    segment: Annotated[str, typer.Option(help="Segment key, e.g. smb")],
    price: Annotated[str, typer.Option(help="Monthly price in dollars, e.g. 40 or 0.35")],
    preview: Annotated[bool, typer.Option(help="Show appeal and share* without saving")] = False,
) -> None:
    """Set a segment's monthly price, or preview it against today's competitors."""
    _, data, state = _game(save)
    price_cents = _dollars(price)
    if preview:
        try:
            pv = product_views.price_preview(
                state, own_product(state, state.player.id, product), segment, price_cents, data
            )
        except SimError as exc:
            raise _fail(exc.message) from exc
        now = ""
        if pv.current_appeal is not None and pv.current_choice_share is not None:
            now = f" (now {pv.current_appeal:.1f}, {pv.current_choice_share:.1%})"
        typer.echo(
            f"At {format_money(price_cents)}: price score {pv.price_score:.1f}, "
            f"appeal {pv.appeal:.1f}, share* {pv.choice_share:.1%}{now}"
        )
        return
    _product_done(save, product, SetPrice(_actor(state), product, segment, price_cents))


@product_app.command("segment")
def product_segment(
    save: SaveOpt,
    product: ProductOpt,
    segment: Annotated[str, typer.Option(help="Segment key to add")],
) -> None:
    """Sell into another segment of the category (it needs a price before it sells)."""
    _, _, state = _game(save)
    _product_done(save, product, AddSegment(_actor(state), product, segment))


@product_app.command("assign")
def product_assign(
    save: SaveOpt,
    product: ProductOpt,
    unit: Annotated[str | None, typer.Option(help="Unit id, or root for the company")] = None,
) -> None:
    """Put a unit (default: the company root, with the founder) on the product."""
    _, _, state = _game(save)
    _product_done(save, product, AssignUnit(_actor(state), product, _unit_arg(unit)))


@product_app.command("unassign")
def product_unassign(
    save: SaveOpt,
    product: ProductOpt,
    unit: Annotated[str | None, typer.Option(help="Unit id, or root for the company")] = None,
) -> None:
    """Take a unit (default: the company root) off the product."""
    _, _, state = _game(save)
    unit_id = _unit_arg(unit)
    if assignment_of(state, state.player.id, unit_id) != product:
        raise _fail(f"that unit does not work on product {product}")
    _product_done(save, product, UnassignUnit(_actor(state), unit_id))


@product_app.command("marketing")
def product_marketing(
    save: SaveOpt,
    product: ProductOpt,
    budget: Annotated[str, typer.Option(help="Monthly budget in dollars, e.g. 10000")],
) -> None:
    """Set the monthly marketing budget (paid each month; builds brand)."""
    _, _, state = _game(save)
    _product_done(save, product, SetMarketing(_actor(state), product, _dollars(budget)))


@product_app.command("launch")
def product_launch(save: SaveOpt, product: ProductOpt) -> None:
    """Launch (quality 25 and feature score 30 needed, and a price in every segment)."""
    _, _, state = _game(save)
    _product_done(save, product, LaunchProduct(_actor(state), product))


@product_app.command("sunset")
def product_sunset(save: SaveOpt, product: ProductOpt) -> None:
    """Sunset a live product: no new customers, faster churn, retired when none remain."""
    _, _, state = _game(save)
    _product_done(save, product, SunsetProduct(_actor(state), product))


@product_app.command("cancel")
def product_cancel(save: SaveOpt, product: ProductOpt) -> None:
    """Cancel a product in development: it retires at once and its units are freed."""
    path, data, state = _game(save)
    result = _run(path, data, CancelProduct(_actor(state), product))
    cancelled = result.new_state.product(product)
    name = cancelled.name if cancelled is not None else f"product {product}"
    typer.echo(f"Cancelled {name}; {_energy(result.new_state, data)}")


@app.command()
def market(
    save: SaveOpt,
    category: Annotated[str, typer.Option(help="b2b_saas|dev_tools|consumer_apps|cybersecurity")],
) -> None:
    """Every product in a category's market, segment by segment (* marks yours)."""
    _, data, state = _game(save)
    try:
        out = product_views.market_out(state, category, data)
    except SimError as exc:
        raise _fail(exc.message) from exc
    typer.echo(out.label)
    for seg in out.segments:
        typer.echo(
            f"  {seg.label}: {seg.addressable:,} addressable, "
            f"{seg.served:,.0f} served ({seg.reach})"
        )
        for p in seg.products:
            mine = "*" if p.is_player else " "
            typer.echo(
                f"   {mine} {p.name:<24} {p.company_name:<14} "
                f"{format_money(p.price_cents):>11}/mo  "
                f"Q {p.quality:3.0f} F {p.feature_score:3.0f} B {p.brand:3.0f}  "
                f"appeal {p.appeal:5.1f}  customers {p.customers:>11,.0f} "
                f"({p.share_of_served:5.1%})  churn {p.churn_rate:.1%}"
            )


@app.command()
def scout(save: SaveOpt, search: Annotated[int, typer.Option(help="Search id")]) -> None:
    """Scout every open candidate of a search yourself (20 energy)."""
    path, data, state = _game(save)
    result = _run(path, data, ScoutSearch(_actor(state), search))
    company = state.player.id
    scouted = sum(1 for c in result.new_state.open_candidates(company) if c.search_id == search)
    typer.echo(f"Scouted {scouted} candidates; {_energy(result.new_state, data)}")


# --- Finance (M4a) --------------------------------------------------------------------------

round_app = typer.Typer(no_args_is_help=True, help="Priced rounds: start, term sheets, accept")
app.add_typer(round_app, name="round")
bridge_app = typer.Typer(no_args_is_help=True, help="Bridge SAFEs from existing investors")
app.add_typer(bridge_app, name="bridge")


def _pct(fraction: float) -> str:
    return f"{fraction * 100:.2f}%"


@app.command()
def statements(
    save: SaveOpt,
    period: Annotated[str, typer.Option(help="month|quarter|year")] = "month",
) -> None:
    """Profit and loss, cash flow and the balance sheet by closed period (formulas.md 14.1)."""
    path, data, state = _game(save)
    if period not in fs.PERIODS:
        raise _fail(f"period must be one of {', '.join(fs.PERIODS)}")
    with repository.open_session(path) as session:
        lines = repository.ledger_lines(session, state.player.id)
    out = finance_views.statements_out(state, lines, period, data)
    if not out.periods:
        typer.echo("No month has closed yet.")
    for p in out.periods:
        pnl, flow, sheet = p.profit_and_loss, p.cash_flow, p.balance_sheet
        partial = "" if p.complete else " (so far)"
        typer.echo(f"{p.label}{partial}")
        typer.echo(
            f"  revenue {format_money(pnl.total_revenue_cents)}  gross margin "
            f"{format_money(pnl.gross_margin_cents)}  operating result "
            f"{format_money(pnl.operating_result_cents)}  net {format_money(pnl.net_result_cents)}"
        )
        typer.echo(
            f"  cash flow: operating {format_money(flow.operating_cents)}  financing "
            f"{format_money(flow.financing_cents)}  "
            f"change {format_money(flow.change_in_cash_cents)}"
        )
        typer.echo(
            f"  balance sheet: assets {format_money(sheet.total_assets_cents)} = liabilities "
            f"and equity {format_money(sheet.total_liabilities_and_equity_cents)} "
            f"(accumulated result {format_money(sheet.accumulated_result_cents)})"
        )


@app.command()
def captable(save: SaveOpt) -> None:
    """Holders, classes, shares and percentages, and every option grant (14.2)."""
    path, data, state = _game(save)
    with repository.open_session(path) as session:
        names = repository.person_names(session, [g.person_id for g in state.grants])
    out = finance_views.captable_out(state, names, data)
    typer.echo(f"Fully diluted: {out.fd_shares:,} shares at ${out.share_price_dollars} a share")
    for h in out.holders:
        typer.echo(f"  {h.holder:<28} {h.share_class:<16} {h.shares:>12,}  {_pct(h.fraction):>7}")
    typer.echo(
        f"Options: {out.granted_options:,} granted ({out.vested_options:,} vested), "
        f"{out.unallocated_options:,} unallocated ({out.pool_left_bp} bp left for offers)"
    )
    for g in out.grants:
        staff = "" if g.on_staff else " (left)"
        typer.echo(
            f"  {g.name}{staff}: {g.granted:,} from {g.start_label}, {g.vested:,} vested, "
            f"{g.unvested:,} unvested"
        )


@app.command()
def safe(
    save: SaveOpt,
    amount: Annotated[str, typer.Option(help="Dollars, e.g. 300000")],
    cap: Annotated[str, typer.Option(help="Post-money valuation cap in dollars")],
    preview: Annotated[bool, typer.Option(help="Show the hint band without raising")] = False,
) -> None:
    """Raise money on a SAFE; investors answer at the next advance (14.4)."""
    path, data, state = _game(save)
    amount_cents, cap_cents = _dollars(amount), _dollars(cap)
    hint = finance_views.safe_hint_out(state, amount_cents, cap_cents, data)
    typer.echo(f"Hint: {hint.hint}; the holders would get {_pct(hint.fraction)} at the next round")
    if preview:
        for problem in hint.problems:
            typer.echo(f"  cannot: {problem}")
        return
    result = _run(path, data, RaiseSafe(_actor(state), amount_cents, cap_cents))
    typer.echo(f"SAFE raised for {format_money(amount_cents)}; {_energy(result.new_state, data)}")


@round_app.command("start")
def round_start(
    save: SaveOpt,
    series: Annotated[str, typer.Option(help="seed|a|b")],
    target: Annotated[str, typer.Option(help="Target amount in dollars")],
) -> None:
    """Start a priced round; term sheets arrive at the next advance (14.5)."""
    path, data, state = _game(save)
    result = _run(path, data, StartRound(_actor(state), series, _dollars(target)))
    typer.echo(f"Round started; {_energy(result.new_state, data)}")


@round_app.command("sheets")
def round_sheets(save: SaveOpt) -> None:
    """The open round's term sheets, with the founder's ownership after each."""
    _, data, state = _game(save)
    out = finance_views.rounds_out(state, data)
    current = next((r for r in out.rounds if r.status in ("open", "accepted")), None)
    guide = out.next
    if current is None:
        why = "allowed" if guide.allowed else (guide.problem or "")
        typer.echo(f"No round is open. Next: {guide.series_label or 'none'} ({why})")
        return
    typer.echo(f"{current.series_label}: {current.status}, open until {current.expires_label}")
    founder = state.founder_of(state.player.id)
    for t in current.term_sheets:
        sheet = state.term_sheet(t.sheet_id)
        mine = ""
        if sheet is not None and t.status == "offered" and founder is not None:
            pv = finance_views.round_preview_out(state, sheet, data)
            line = next((x for x in pv.lines if x.holder == views.person_name(founder)), None)
            mine = f"; you own {_pct(line.fraction_after)} after" if line else ""
        typer.echo(
            f"  sheet {t.sheet_id}: {t.firm_name} {format_money(t.amount_cents)} at "
            f"{format_money(t.pre_money_cents)} pre-money ({t.status}){mine}"
        )


@round_app.command("accept")
def round_accept(save: SaveOpt, sheet: Annotated[int, typer.Option(help="Term sheet id")]) -> None:
    """Accept a term sheet; the round closes at the next advance."""
    path, data, state = _game(save)
    result = _run(path, data, AcceptTermSheet(_actor(state), sheet))
    typer.echo(f"Accepted sheet {sheet}; {_energy(result.new_state, data)}")


@bridge_app.command("accept")
def bridge_accept(save: SaveOpt) -> None:
    """Accept the open bridge offer; its money arrives at the next advance (14.7)."""
    path, data, state = _game(save)
    offers = [
        s
        for s in state.company_safes(state.player.id)
        if s.kind == "bridge" and s.status == "offered"
    ]
    if not offers:
        raise _fail("there is no bridge offer to accept")
    offer = offers[-1]
    result = _run(path, data, AcceptBridge(_actor(state), offer.id))
    typer.echo(
        f"Bridge of {format_money(offer.amount_cents)} accepted; {_energy(result.new_state, data)}"
    )


@app.command()
def board(save: SaveOpt) -> None:
    """Directors, their confidence, and how close a removal vote is (14.6)."""
    _, data, state = _game(save)
    out = finance_views.board_out(state, data)
    if not out.directors:
        typer.echo("No board yet: it forms with the first priced round.")
        return
    avg = "n/a" if out.average_confidence is None else f"{out.average_confidence:.0f}"
    typer.echo(
        f"Board confidence {avg} ({out.label}); "
        f"{out.votes_to_remove} of {out.seats} would vote to remove you"
    )
    for d in out.directors:
        conf = "backs you" if d.confidence is None else f"{d.confidence:.0f} ({d.label})"
        firm = f", {d.firm_name}" if d.firm_name else ""
        typer.echo(f"  {d.kind:<12} {d.name}{firm}: {conf}")
    if state.ended:
        typer.echo(f"Game over: {state.save_meta.game_state.replace('_', ' ')}")


if __name__ == "__main__":
    app()


# --- Rivals (M5, formulas.md 15) --------------------------------------------------------------


def _rival_view(save: str) -> tuple[Path, LoadedData, GameState, dict[tuple[int, str], int]]:
    path, data, state = _game(save)
    with repository.open_session(path) as session:
        balances = repository.ledger_balances(session, state.turn)
    return path, data, state, balances


@app.command()
def rivals(
    save: SaveOpt,
    view: Annotated[str, typer.Option(help="all|markets|startups")] = "all",
) -> None:
    """List rival companies: style, where they meet you, staff, money and last move."""
    from tst.api import rival_views

    _, data, state, balances = _rival_view(save)
    out = rival_views.rivals_out(state, balances, data, list(state.rival_moves), view)
    typer.echo(
        f"{out.established} established, {out.startups_alive} startups alive, "
        f"{out.startups_failed} failed"
    )
    for r in out.rivals:
        tag = " (startup)" if r.is_startup else ""
        money = r.money_label or "-"
        where = ", ".join(r.competes_in) or "-"
        typer.echo(
            f"{r.company_id:>3}  {r.name + tag:<28} {r.personality_label:<14} "
            f"staff ~{r.staff_estimate:<6} {money:<13} {r.stance:<13} "
            f"in: {where}; last: {r.last_move or '-'}"
        )


@app.command()
def rival(
    save: SaveOpt, rival_id: Annotated[int, typer.Option("--id", help="Rival company id")]
) -> None:
    """One rival: products, key people (your ranges) and recent moves."""
    from tst.api import rival_views

    _, data, state, balances = _rival_view(save)
    company = next((c for c in state.companies if c.id == rival_id and not c.is_player), None)
    if company is None:
        raise _fail(f"no rival {rival_id}")
    p = rival_views.rival_profile(state, company, balances, data, list(state.rival_moves))
    typer.echo(f"{p.name} ({p.personality_label}): {p.style_text}")
    typer.echo(
        f"Staff ~{p.staff_estimate}, money {p.money_label or '-'}, {p.stance}: {p.stance_reason}"
    )
    for s in p.segments:
        running = f", {s.running} until {s.running_until_label}" if s.running else ""
        typer.echo(
            f"  {s.product_name} / {s.segment_label}: quality {s.quality:.0f}, features "
            f"{s.feature_score:.0f}, brand {s.brand:.0f}, price "
            f"{format_money(s.price_cents or 0)}, customers {s.customers:,.0f}{running}"
        )
    typer.echo("Key people:")
    for k in p.key_people:
        skills = ", ".join(f"{a.short_label} {a.range.min}-{a.range.max}" for a in k.top_skills)
        typer.echo(
            f"  {k.person_id:>8}  {k.name:<24} {k.role_label} ({k.level}); {skills}; "
            f"{k.potential_phrase}"
        )
    for m in p.recent_moves[:10]:
        typer.echo(f"  {m.date_label}  [{m.tag}] {m.detail}")


@app.command()
def news(save: SaveOpt) -> None:
    """Market news: rival moves and startup events, newest month first."""
    from tst.api import rival_views

    _, _, state = _game(save)
    months = rival_views.news_months(list(state.rival_moves))
    if not months:
        typer.echo("No market news yet.")
    for month in months:
        typer.echo(month.date_label)
        for m in month.moves:
            typer.echo(f"  [{m.tag}] {m.detail}")


@app.command()
def poach(
    save: SaveOpt,
    rival_id: Annotated[int, typer.Option("--rival", help="Rival company id")],
    role: Annotated[
        str, typer.Option(help="Role key, e.g. software_engineer")
    ] = "software_engineer",
) -> None:
    """Open a "Poach from a rival" search: their key people arrive at the end of this month."""
    path, data, state = _game(save)
    action = OpenSearch(_actor(state), role, "poach", rival_id=rival_id)
    result = _run(path, data, action)
    search = max(result.new_state.searches, key=lambda s: s.id)
    typer.echo(
        f"Opened search {search.id}: poach {role} from "
        f"{result.new_state.company(rival_id).name}; {_energy(result.new_state, data)}"
    )


# --- Events (M6) ------------------------------------------------------------------------------


@app.command()
def events(save: SaveOpt) -> None:
    """This month's events with their choices and what each does (in words), then the last
    few answered ones. Minor and major events take their first choice at Continue; a critical
    one must be answered first."""
    from tst.api import event_views

    _, data, state = _game(save)
    cid = state.player.id
    shown = [e for e in state.open_events(cid) if e.status == "open"]
    if not shown:
        typer.echo("No events to answer this month.")
    for event in shown:
        out = event_views.event_out(state, event, data)
        tag = "CRITICAL" if out.severity == "critical" else out.severity
        story = f" · {out.storyline.title}, step {out.storyline.step}" if out.storyline else ""
        typer.echo(f"Event {out.event_id} [{out.category_label}, {tag}]{story}: {out.title}")
        typer.echo(f"  {out.body}")
        for choice in out.choices:
            words = "; ".join(choice.effects) or "nothing else"
            typer.echo(f"  {choice.key}. {choice.label} — {words}")
        if out.follow_up_note:
            typer.echo(f"  {out.follow_up_note}")
    answered = sorted(
        (e for e in state.events if e.company_id == cid and e.status in ("answered", "auto")),
        key=lambda e: -e.id,
    )[:5]
    for event in answered:
        chosen = event.choice(event.chosen or "")
        how = "you chose" if event.status == "answered" else "at Continue"
        label = chosen.label if chosen else "nothing"
        typer.echo(f"Answered {event.id} ({how}): {event.title} — {label}")


@app.command()
def choose(
    save: SaveOpt,
    event: Annotated[int, typer.Option("--event", help="Event id")],
    choice: Annotated[str, typer.Option("--choice", help="A, B or C")],
) -> None:
    """Answer an event: its effects apply at once (energy 0)."""
    from tst.sim.actions import ChooseEvent

    path, data, state = _game(save)
    result = _run(path, data, ChooseEvent(_actor(state), event, choice.upper()))
    answered = result.new_state.event(event)
    assert answered is not None
    label = answered.choice(choice.upper())
    typer.echo(f"Answered event {event}: {label.label if label else choice}")


@app.command()
def storylines(save: SaveOpt) -> None:
    """Storylines: active ones first, with their latest summary."""
    from sqlalchemy import select

    from tst.db.mappers import storyline_from_row
    from tst.db.models import StorylineRow
    from tst.db.state_io import has_table

    path, _, _ = _game(save)
    with repository.open_session(path) as session:
        rows = (
            session.scalars(select(StorylineRow).order_by(StorylineRow.id.desc())).all()
            if has_table(session, StorylineRow)
            else []
        )
        stories = [storyline_from_row(r) for r in rows]
    if not stories:
        typer.echo("No storylines yet.")
    for story in sorted(stories, key=lambda s: (s.status != "active", -s.id)):
        since = format_turn(story.started_turn)
        typer.echo(f"{story.title} ({story.status}, step {story.step}, from {since})")
        typer.echo(f"  {story.summary}")


# --- Divisions and executives (M8, formulas.md 18) --------------------------------------------


def _scaleup(path: Path, state: GameState, data: LoadedData) -> Any:
    from tst.api import scaleup_views

    with repository.open_session(path) as session:
        lines = repository.division_lines(session, state.player.id)
        months = repository.division_months(session, state.player.id)
    profit = scaleup_views.last_month_profit(lines, months, state, data)
    return scaleup_views.scaleup_out(state, data, profit)


@app.command()
def divisions(save: SaveOpt) -> None:
    """Divisions with their president, shared services and last month's P&L; support
    coverage by pool; products built across divisions (18.1-18.4)."""
    path, data, state = _game(save)
    out = _scaleup(path, state, data)
    if not out.in_play:
        typer.echo(f"Divisions, executives and support apply from stage {out.unlock_stage}.")
        return
    if not out.divisions:
        typer.echo("No divisions yet. Create one with the Org screen or the API.")
    for d in out.divisions:
        pres = d.president_name or "no president"
        profit = (
            "n/a" if d.operating_profit_cents is None else format_money(d.operating_profit_cents)
        )
        products = ", ".join(d.product_names) or "no products"
        typer.echo(
            f"{d.unit_id:>3}  {d.name:<20} {d.headcount:>4} staff  {d.services:<8} {pres}; "
            f"operating profit {profit}; {products}"
        )
        typer.echo(f"     {d.effect_note}")
    typer.echo(out.support_rule)
    for p in out.support:
        typer.echo(
            f"  {p.label}: {p.support_staff} support of {p.needed} needed for {p.headcount} "
            f"staff; output {p.output_effect_pct:+.1f}%, morale {p.morale_effect:+.1f}"
        )
    for c in out.cross_division:
        typer.echo(
            f"  {c.product_name} is built in {', '.join(c.division_names)}: output "
            f"{c.output_effect_pct:+.0f}%. {c.fix}."
        )


@app.command()
def execs(save: SaveOpt) -> None:
    """The executive team: holders, fit and estimated effects, and vacancy penalties (18.3)."""
    path, data, state = _game(save)
    out = _scaleup(path, state, data)
    typer.echo("CEO      you (until the IPO)")
    for s in out.seats:
        if s.holder_name:
            est = "" if s.estimated_effect_pct is None else f", {s.estimated_effect_pct:+.1f}%"
            typer.echo(f"{s.label:<8} {s.holder_name} ({s.fit}{est} {s.effect_label}, est.)")
        elif s.vacancy_penalty_pct is not None:
            typer.echo(f"{s.label:<8} vacant: {s.vacancy_penalty_pct:+.1f}% {s.effect_label}")
        else:
            typer.echo(f"{s.label:<8} vacant (seats open at stage {out.unlock_stage})")
    typer.echo(out.note)


@app.command()
def appoint(
    save: SaveOpt,
    seat: Annotated[str, typer.Option(help="coo|cfo|cto|cpo|cmo|cro")],
    person: Annotated[int, typer.Option(help="Person id")],
    salary: Annotated[
        str | None,
        typer.Option(help="New annual salary in dollars; default: the exec market rate"),
    ] = None,
) -> None:
    """Appoint an employee (senior or above) to an executive seat: they become exec level at
    a new salary (the exec market rate unless set, never below their pay now) and gain +5
    morale, plus a raise's bonus; energy 5 (18.3)."""
    from tst.sim.actions import AppointExecutive

    path, data, state = _game(save)
    founder = state.founder_of(state.player.id)
    if founder is None:
        raise _fail("the company has no founder")
    pay = cents(salary) if salary is not None else None
    result = _run(path, data, AppointExecutive(founder.id, seat.lower(), person, pay))
    who = result.new_state.person(person)
    employment = result.new_state.employment_of(person)
    paid = format_money(employment.salary_cents) if employment else "?"
    typer.echo(
        f"{who.first_name} {who.last_name} is now {seat.upper()} (exec level, {paid} a year)"
    )
    typer.echo(f"  {_energy(result.new_state, data)}")


# --- Cities, offices and regions (M9, formulas.md 19) ----------------------------------------


def _founder(state: GameState) -> int:
    founder = state.founder_of(state.player.id)
    if founder is None:
        raise _fail("the company has no founder")
    return founder.id


@app.command()
def cities(save: SaveOpt) -> None:
    """Every city: region, salary and rent indexes, talent bonuses, your people there."""
    from tst.api.geo_views import geo_out

    _, data, state = _game(save)
    out = geo_out(state, data)
    for c in out.cities:
        talent = ", ".join(f"{t.label} {t.marks}" for t in c.talent) or "-"
        hq = " (HQ)" if c.is_hq else ""
        typer.echo(
            f"{c.key:<14} {c.label + hq:<20} {c.region_label:<26} salary x{c.salary_index:.2f} "
            f"rent x{c.rent_index:.2f}  {c.people:>3} people  talent: {talent}"
        )


@app.command()
def offices(save: SaveOpt) -> None:
    """Your flexible HQ space and leased offices: seats, people, rent, cost per head, units."""
    from tst.api.geo_views import geo_out

    _, data, state = _game(save)
    out = geo_out(state, data)
    for o in out.offices:
        ident = "flex" if o.office_id is None else f"{o.office_id:>4}"
        seats = "-" if o.seats is None else str(o.seats)
        per = "n/a" if o.cost_per_head_cents is None else format_money(o.cost_per_head_cents)
        units = ", ".join(u.name for u in o.units) or "no units"
        crowded = f"  CROWDED ({o.crowded_morale:+.0f} morale)" if o.crowded else ""
        typer.echo(
            f"{ident} {o.city_label:<28} {o.people:>4}/{seats:<4} people  rent "
            f"{format_money(o.monthly_rent_cents)} a month, {per} a head; {units}{crowded}"
        )


@app.command()
def lease(
    save: SaveOpt,
    city: Annotated[str, typer.Option(help="City key (tst cities)")],
    seats: Annotated[int, typer.Option(help="25, 50, 100 or 250")],
) -> None:
    """Lease an office: rent every month, the fit-out now; energy 10 (19.2)."""
    from tst.sim.actions.geo import LeaseOffice

    path, data, state = _game(save)
    result = _run(path, data, LeaseOffice(_founder(state), city, seats))
    office = max(result.new_state.company_offices(state.player.id), key=lambda o: o.id)
    rent = office_rent(office, data)
    typer.echo(
        f"Leased office {office.id}: {seats} seats in {data.game_data.city(city).label}, "
        f"{format_money(rent)} a month"
    )
    typer.echo(f"  {_energy(result.new_state, data)}")


def office_rent(office: object, data: LoadedData) -> int:
    from tst.sim.actions.geo import office_rent_cents
    from tst.sim.geo.models import Office

    assert isinstance(office, Office)
    return office_rent_cents(office, data.balance, data.game_data)


@app.command("close-office")
def close_office(
    save: SaveOpt, office: Annotated[int, typer.Option(help="Office id (tst offices)")]
) -> None:
    """Close a lease early: 3 months' rent as a penalty; energy 10 (19.2)."""
    from tst.sim.actions.geo import CloseOffice

    path, data, state = _game(save)
    result = _run(path, data, CloseOffice(_founder(state), office))
    typer.echo(f"Closed office {office}")
    typer.echo(f"  {_energy(result.new_state, data)}")


@app.command("unit-office")
def unit_office(
    save: SaveOpt,
    unit: Annotated[int, typer.Option(help="Unit id")],
    office: Annotated[int | None, typer.Option(help="Office id; omit for the parent's")] = None,
) -> None:
    """Move a unit (and its people) to an office; energy 2 (19.2)."""
    from tst.sim.actions.geo import SetUnitOffice

    path, data, state = _game(save)
    result = _run(path, data, SetUnitOffice(_founder(state), unit, office))
    typer.echo(f"Unit {unit} now works {'in office ' + str(office) if office else 'at the HQ'}")
    typer.echo(f"  {_energy(result.new_state, data)}")


@app.command("launch-region")
def launch_region(
    save: SaveOpt,
    product: Annotated[int, typer.Option(help="Product id")],
    region: Annotated[str, typer.Option(help="Region key, e.g. europe")],
) -> None:
    """Launch a live product in another region: localization cost now, live in 3 months
    (19.5); energy 4."""
    from tst.sim.actions.geo import LaunchInRegion

    path, data, state = _game(save)
    result = _run(path, data, LaunchInRegion(_founder(state), product, region))
    launch = result.new_state.product_region(product, region)
    assert launch is not None
    typer.echo(
        f"Localizing for {data.game_data.region(region).label}; live in "
        f"{format_turn(launch.live_turn)}"
    )
    typer.echo(f"  {_energy(result.new_state, data)}")


@app.command()
def regions(save: SaveOpt, product: Annotated[int, typer.Option(help="Product id")]) -> None:
    """Where a product sells: status, customers and MRR by region, and reach."""
    from tst.api.geo_views import product_regions_out

    _, data, state = _game(save)
    out = product_regions_out(state, product, data)
    for r in out.regions:
        typer.echo(
            f"{r.label:<26} {r.status_label:<28} {r.customers:>10,.0f} customers  "
            f"{format_money(r.mrr_cents)} MRR  {r.rivals} rivals; {r.reach_note}"
        )
    spread = ", ".join(f"{t.label} {t.builders}" for t in out.team) or "no builders"
    typer.echo(f"Builders: {spread}; time-zone factor x{out.time_zone_factor:.2f}")
