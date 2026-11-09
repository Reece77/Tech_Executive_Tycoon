"""Headless commands: new-game, advance, inspect, list, hiring (M1b), the org (M2a), and
products and markets (M3a).

Hiring commands call the same action functions as the API, with the founder as actor.
They show what the company knows (ranges), never true values; only `inspect --person`
prints true values, as a debug view.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Annotated, Any

import typer

from tst import holiday as hol
from tst.api import capital_views, finance_views, org_views, product_views, views
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
    RepayLoan,
    ScoutSearch,
    SetLeader,
    SetMarketing,
    SetPolicy,
    SetPrice,
    StartRound,
    SunsetProduct,
    TakeLoan,
    UnassignUnit,
    UpdatePlan,
)
from tst.sim.actions.products import assignment_of, own_product
from tst.sim.calendar import format_turn, ym_to_turn
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


def _save_data(settings: Settings, path: Path, data: LoadedData) -> LoadedData:
    """The data a save plays with: the base data, or its mod's (M25)."""
    from tst.mods.store import data_for_save

    try:
        return data_for_save(path, settings.data_dir, data)
    except DataLoadError as exc:
        raise _fail(str(exc)) from exc


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
    scenario: Annotated[
        str,
        typer.Option(
            help="Background id, or a historical scenario's key (M15b): ai_lab, "
            "mobile_first, survive_2022, chip_startup, turnaround"
        ),
    ] = "garage_bootstrap",
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
    sandbox: Annotated[bool, typer.Option(help="A Sandbox start (M15b, 30.2)")] = False,
    year: Annotated[int | None, typer.Option(help="Sandbox: the start year")] = None,
    cash: Annotated[
        int | None, typer.Option(help="Sandbox: starting cash in dollars; default the background's")
    ] = None,
    rivals: Annotated[str, typer.Option(help="Sandbox: all|half|none")] = "all",
    eras: Annotated[str, typer.Option(help="Sandbox: historical|seeded")] = "historical",
    mod: Annotated[
        str | None, typer.Option("--mod", help="A data-editor mod in saves/mods (M25; tst mods)")
    ] = None,
) -> None:
    """Create a new save file at schema head, with a founder built from a background. A
    historical scenario's key as --scenario starts that scenario (30.3); --sandbox starts a
    Sandbox game in --year (30.2)."""
    from tst.sim.modes.scenarios import scenario_spec
    from tst.sim.modes.world import ModeSpec

    settings, data = _context()
    if mod is not None:
        from tst.mods.store import read_mod, validate

        try:
            data = validate(settings.data_dir, read_mod(settings.resolved_save_dir(), mod))
        except SimError as exc:
            raise _fail(exc.message) from exc
    mode: ModeSpec | None = None
    if data.game_data.historical_scenario(scenario) is not None:
        if sandbox:
            raise _fail("choose a Sandbox or a historical scenario, not both")
        mode = scenario_spec(scenario, data.game_data)
    elif sandbox:
        if year is None:
            raise _fail("a Sandbox start needs --year")
        if rivals not in ("all", "half", "none") or eras not in ("historical", "seeded"):
            raise _fail("--rivals is all|half|none and --eras historical|seeded")
        mode = ModeSpec(
            "sandbox",
            year,
            None if cash is None else cash * 100,  # tunable-exempt: cents in a dollar
            rivals,  # type: ignore[arg-type]
            eras,  # type: ignore[arg-type]
        )
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
            mode=mode,
        )
    except SimError as exc:
        raise _fail(exc.message) from exc
    start = 0 if mode is None else ym_to_turn(mode.start_year, 1)
    note = f" with mod {mod!r} (earns no achievements)" if mod else ""
    typer.echo(f"Created {path.name}: {company_name}, {format_turn(start)}{note}")


@app.command()
def advance(
    save: Annotated[str, typer.Option(help="Save slug")],
    turns: Annotated[int, typer.Option(min=1, help="Turns to play")] = 1,
    until_needed: Annotated[
        bool, typer.Option(help="M15b (30.5): continue until something needs you, up to a year")
    ] = False,
) -> None:
    """Play N monthly turns, each in its own transaction."""
    settings, data = _context()
    if until_needed:
        from tst.sim.modes.continue_until import LABELS

        try:
            path = repository.existing_save_path(settings.resolved_save_dir(), save)
            data = _save_data(settings, path, data)  # M25: its mod, if any
            played, why = repository.continue_until(path, data)
        except SimError as exc:
            raise _fail(exc.message) from exc
        with repository.read_session(path) as session:
            now = repository.read_state(session).turn
        typer.echo(f"Played {played} month(s); now {format_turn(now)}. Stopped: {LABELS[why]}.")
        return
    try:
        path = repository.existing_save_path(settings.resolved_save_dir(), save)
        data = _save_data(settings, path, data)  # M25: its mod, if any
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
        data = _save_data(settings, path, data)  # M25: its mod, if any
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


@app.command()
def score(save: Annotated[str, typer.Option(help="Save slug")]) -> None:
    """Print the company score now and its parts (30.1): public inputs only."""
    from tst.api.modes_views import score_out

    settings, data = _context()
    try:
        path = repository.existing_save_path(settings.resolved_save_dir(), save)
        with repository.open_session(path) as session:
            state = repository.load_state(session)
            balances = repository.ledger_balances(session)
    except SimError as exc:
        raise _fail(exc.message) from exc
    out = score_out(state, state.player.id, balances, data)
    sandbox = state.mode is not None and state.mode.kind == "sandbox"
    note = " (Sandbox: kept out of the Hall of Fame and the Saves list)" if sandbox else ""
    typer.echo(f"{state.player.name}: {out.score} / 1,000{note}")
    for label, points in (
        ("Value", out.value_points),
        ("Growth", out.growth_points),
        ("Profit", out.profit_points),
        ("Leadership", out.leadership_points),
        ("Reputation", out.reputation_points),
    ):
        typer.echo(f"  {label:<11} {points:6.1f}")
    typer.echo(f"  Estimate    {format_money(out.estimate_cents)}")
    if out.last_december is not None:
        typer.echo(f"  Last December: {out.last_december}")


@app.command()
def rankings(
    save: Annotated[str, typer.Option(help="Save slug")],
    year: Annotated[int | None, typer.Option(help="The year; default the latest")] = None,
) -> None:
    """Print a January's industry rankings (30.4)."""
    from tst.api.modes_views import rankings_out

    settings, _ = _context()
    try:
        path = repository.existing_save_path(settings.resolved_save_dir(), save)
        with repository.open_session(path) as session:
            state = repository.load_state(session)
    except SimError as exc:
        raise _fail(exc.message) from exc
    out = rankings_out(state, year)
    if out.year is None:
        typer.echo("No rankings yet: the first lists come out in January.")
        return
    typer.echo(f"Industry rankings {out.year}")
    for ranked in out.lists:
        typer.echo(f"\n{ranked.label}")
        for e in ranked.entries[:10]:  # tunable-exempt: lines printed per list
            you = " (you)" if e.is_you else ""
            typer.echo(f"  {e.place:>3}. {e.name}{you}  {e.value_label}")


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
        data = _save_data(settings, path, data)  # M25: its mod, if any
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
    candidate: Annotated[int | None, typer.Option("--candidate", help="Candidate id")] = None,
    salary: Annotated[str, typer.Option(help="Annual salary in dollars, e.g. 92000")] = "",
    equity_bp: Annotated[int, typer.Option("--equity-bp", help="Equity in basis points")] = 0,
    preview: Annotated[bool, typer.Option(help="Show the hint without sending")] = False,
    company: Annotated[str | None, typer.Option(help="M14: bid for this company")] = None,
    price: Annotated[int, typer.Option(help="M14: the bid in cents")] = 0,
    cash_share: Annotated[float, typer.Option(help="M14: share paid in cash, 0-1")] = 1.0,
    hostile: Annotated[bool, typer.Option(help="M14: a hostile tender")] = False,
    brand: Annotated[bool, typer.Option(help="M14: keep it as a brand")] = False,
) -> None:
    """Make a job offer to --candidate (resolved at the next Continue; --preview shows the
    hint), or with --company and --price a bid for a company (M14, 28.3)."""
    if company is not None:
        _company_bid(save, company, price, cash_share, hostile, brand)
        return
    if candidate is None or not salary:
        raise _fail("give --candidate and --salary for a job offer, or --company and --price")
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


# --- Infrastructure (M12a, formulas.md 22) -------------------------------------------------


def _infrastructure(path: Path, state: GameState, data: LoadedData) -> Any:
    from tst.api.facility_views import infrastructure_out
    from tst.api.routers.facilities import _stored

    return infrastructure_out(state, data, _stored(path, state, data), state.player.id)


@app.command()
def facilities(save: SaveOpt) -> None:
    """Component indexes, your data centres, contracts and Cloud hosting (22.6)."""
    path, data, state = _game(save)
    out = _infrastructure(path, state, data)
    for c in out.components:
        typer.echo(
            f"{c.label:<18} index {c.index:.2f} ({c.change_12m:+.0%} in 12 months), "
            f"allocation {c.allocation:.0%}: {c.note}"
        )
    for s in out.spot:
        typer.echo(f"Spot {s.label:<16} {format_money(s.cents_per_unit)} a CU a month")
    if not out.facilities:
        typer.echo("No data centres. Build one with tst build-dc.")
    for f in out.facilities:
        if f.status == "building":
            state_text = f"building, ready {f.ready}"
        else:
            rel = "-" if f.reliability is None else f"{f.reliability:.0f}"
            per = "-" if f.cost_per_used_cents is None else format_money(f.cost_per_used_cents)
            state_text = (
                f"own {f.own_use:,.0f} sold {f.sold_use:,.0f} free {f.free:,.0f} "
                f"({f.utilization:.0%}); reliability {rel}; {per} per used CU "
                f"(spot {format_money(f.spot_cents)})"
            )
        typer.echo(
            f"{f.facility_id:>4} {f.name:<44} {f.units:>6,} {f.unit}  staff {f.staff}/"
            f"{f.staff_needed}  book {format_money(f.book_value_cents)}; {state_text}"
        )
    for k in out.contracts:
        typer.echo(
            f"Contract {k.contract_id}: {k.good_label} at {k.index:.2f}, {k.used}/{k.volume} "
            f"used, until {k.ends} ({k.status})"
        )
    cloud = out.cloud
    if cloud.selling:
        typer.echo(
            f"Cloud hosting: {cloud.customers:,.0f} customers, {cloud.units_sold:,.0f} CU, "
            f"{format_money(cloud.revenue_cents)} a month; {cloud.outages_12m} outages in 12 months"
        )


@app.command("build-dc")
def build_dc(
    save: SaveOpt,
    region: Annotated[str, typer.Option(help="Region key, e.g. north_america")],
    kind: Annotated[str, typer.Option(help="general or gpu")] = "general",
    cu: Annotated[int, typer.Option(help="100, 500, 2000 or 10000")] = 500,
    contract: Annotated[int | None, typer.Option(help="Component contract id")] = None,
) -> None:
    """Build a data centre: capex paid over the build; energy 12 (22.2)."""
    from tst.sim.actions.facilities import BuildFacility

    path, data, state = _game(save)
    key = kind if kind in data.balance.facility.kinds else f"data_centre_{kind}"
    result = _run(path, data, BuildFacility(_founder(state), key, region, cu, contract))
    facility = max(result.new_state.company_facilities(state.player.id), key=lambda f: f.id)
    late = facility.capacity - facility.on_time
    typer.echo(
        f"Ordered data centre {facility.id}: {cu:,} CU for {format_money(facility.capex_cents)}"
        f", live {format_turn(facility.ready_turn)}"
        + (f" ({late:,} CU late, {format_turn(facility.late_turn)})" if late else "")
    )
    typer.echo(f"  {_energy(result.new_state, data)}")


@app.command("sell-dc")
def sell_dc(save: SaveOpt, facility: Annotated[int, typer.Option(help="Data centre id")]) -> None:
    """Sell a data centre for half its book value; energy 12 (22.2)."""
    from tst.sim.actions.facilities import SellFacility

    path, data, state = _game(save)
    result = _run(path, data, SellFacility(_founder(state), facility))
    typer.echo(f"Sold data centre {facility}")
    typer.echo(f"  {_energy(result.new_state, data)}")


@app.command("staff-dc")
def staff_dc(
    save: SaveOpt,
    facility: Annotated[int, typer.Option(help="Data centre id")],
    unit: Annotated[int | None, typer.Option(help="Unit id; omit for nobody")] = None,
) -> None:
    """The unit whose DevOps and security engineers staff a data centre; energy 2."""
    from tst.sim.actions.facilities import StaffFacility

    path, data, state = _game(save)
    result = _run(path, data, StaffFacility(_founder(state), facility, unit))
    typer.echo(f"Data centre {facility} is staffed by unit {unit}")
    typer.echo(f"  {_energy(result.new_state, data)}")


@app.command()
def contract(
    save: SaveOpt,
    index: Annotated[str, typer.Option(help="Component: server or gpu")],
    months: Annotated[int, typer.Option(help="12 to 36")],
    cu: Annotated[int, typer.Option(help="CU of builds it covers")],
) -> None:
    """Lock a component price for builds, with full allocation; take-or-pay; energy 6."""
    from tst.sim.actions.facilities import SignContract

    path, data, state = _game(save)
    result = _run(path, data, SignContract(_founder(state), index, months, cu))
    signed = max(result.new_state.company_contracts(state.player.id), key=lambda c: c.id)
    typer.echo(
        f"Contract {signed.id}: {cu:,} CU of {index} builds at index {signed.index:.2f} "
        f"until {format_turn(signed.end_turn)}"
    )
    typer.echo(f"  {_energy(result.new_state, data)}")


@app.command("sell-capacity")
def sell_capacity(save: SaveOpt) -> None:
    """Start selling spare data-centre capacity as Cloud hosting (22.3)."""
    from tst.sim.actions.facilities import SellCapacity

    path, data, state = _game(save)
    result = _run(path, data, SellCapacity(_founder(state)))
    typer.echo("Selling spare capacity as Cloud hosting")
    typer.echo(f"  {_energy(result.new_state, data)}")


# --- Hardware and chips (M12b, formulas.md 26) ---------------------------------------------


@app.command()
def hardware(save: SaveOpt) -> None:
    """Plants, contracts, chips, contract-manufacturing sales and the hardware indexes (26.5)."""
    from tst.api.hardware_views import hardware_out
    from tst.api.routers.facilities import _stored

    path, data, state = _game(save)
    out = hardware_out(state, data, _stored(path, state, data))
    for c in out.components:
        typer.echo(
            f"{c.label:<20} index {c.index:.2f} ({c.change_12m:+.0%} in 12 months), "
            f"allocation {c.allocation:.0%}: {c.note}"
        )
    for prod in out.products:
        margin = "-" if prod.gross_margin is None else f"{prod.gross_margin:.0%}"
        lines = ", ".join(f"{line.line} {format_money(line.cents)}" for line in prod.lines)
        typer.echo(
            f"{prod.product_id:>4} {prod.name:<28} unit cost "
            f"{format_money(prod.unit_cost_cents)} ({lines}); margin {margin}; sold "
            f"{prod.units_sold:,.0f}, lost {prod.units_lost:,.0f}"
        )
    if not out.plants:
        typer.echo("No assembly plants. Build one with tst build-plant.")
    for f in out.plants:
        per = (
            "-" if f.cost_per_good_unit_cents is None else format_money(f.cost_per_good_unit_cents)
        )
        y = "-" if f.plant_yield is None else f"{f.plant_yield:.1%}"
        typer.echo(
            f"{f.facility_id:>4} {f.name:<36} {f.units:>7,} units/month {f.status}; own "
            f"{f.own_use:,.0f} sold {f.sold_use:,.0f} ({f.utilization:.0%}); yield {y}; staff "
            f"{f.staff}/{f.staff_needed}; {per} a good unit (contract fee "
            f"{format_money(f.contract_fee_cents)})"
        )
    for k in out.contracts:
        typer.echo(
            f"Contract {k.contract_id} ({k.kind}): {k.product_name} with {k.supplier_label}, "
            f"{k.units:,} a month at {format_money(k.price_cents)}, used {k.used:,.0f} of "
            f"{k.delivered:,.0f}, take-or-pay {format_money(k.take_or_pay_cents)}, until {k.ends}"
        )
    for chip in out.chips:
        typer.echo(
            f"Chip {chip.name} ({chip.chip_label}): yield {chip.chip_yield:.0%}, unit cost "
            f"{format_money(chip.unit_cost_cents)} vs market "
            f"{format_money(chip.market_price_cents)}; internal {chip.internal_units:,.0f}, "
            f"market {chip.market_units:,.0f}"
        )
    if out.cm.started:
        typer.echo(
            f"Contract manufacturing: {out.cm.units_sold:,.0f} units a month sold, "
            f"{format_money(out.cm.revenue_cents)} a month"
        )


@app.command("cm-contract")
def cm_contract(
    save: SaveOpt,
    product: Annotated[int, typer.Option(help="Device or server product id")],
    units: Annotated[int, typer.Option(help="Units a month")],
    months: Annotated[int, typer.Option(help="12 to 24")],
    manufacturer: Annotated[str, typer.Option(help="foxconn or pegatron")] = "foxconn",
    city: Annotated[str, typer.Option(help="City key; Shenzhen is cheapest")] = "shenzhen",
) -> None:
    """Sign a contract-manufacturing contract; take-or-pay 50% a month; energy 6 (26.2)."""
    from tst.sim.actions.hardware import SignManufacturingContract

    path, data, state = _game(save)
    action = SignManufacturingContract(_founder(state), product, manufacturer, city, units, months)
    result = _run(path, data, action)
    signed = max(result.new_state.production_contracts, key=lambda c: c.id)
    typer.echo(
        f"Contract {signed.id}: {units:,} units a month at "
        f"{format_money(round(signed.price_cents))} until {format_turn(signed.end_turn)}"
    )
    typer.echo(f"  {_energy(result.new_state, data)}")


@app.command("wafer-contract")
def wafer_contract(
    save: SaveOpt,
    product: Annotated[int, typer.Option(help="Chip product id")],
    wafers: Annotated[int, typer.Option(help="Wafer starts a month")],
    months: Annotated[int, typer.Option(help="12 to 36")],
    foundry: Annotated[str, typer.Option(help="tsmc or samsung")] = "tsmc",
) -> None:
    """Sign a wafer contract at this month's wafer price; take-or-pay; energy 6 (26.3)."""
    from tst.sim.actions.hardware import SignWaferContract

    path, data, state = _game(save)
    result = _run(path, data, SignWaferContract(_founder(state), product, foundry, wafers, months))
    signed = max(result.new_state.production_contracts, key=lambda c: c.id)
    typer.echo(
        f"Wafer contract {signed.id}: {wafers:,} wafers a month at "
        f"{format_money(round(signed.price_cents))} until {format_turn(signed.end_turn)}"
    )
    typer.echo(f"  {_energy(result.new_state, data)}")


@app.command("build-plant")
def build_plant(
    save: SaveOpt,
    city: Annotated[str, typer.Option(help="City key, e.g. shenzhen")],
    units: Annotated[int, typer.Option(help="5000, 20000, 50000 or 100000 units a month")],
) -> None:
    """Build an assembly plant: capex over 12 months; energy 12 (26.2)."""
    from tst.sim.actions.facilities import BuildFacility

    path, data, state = _game(save)
    region = data.game_data.city(city).region if data.game_data.has_city(city) else ""
    kind = data.balance.hardware.plant_kind
    result = _run(path, data, BuildFacility(_founder(state), kind, region, units, None, city))
    plant = max(result.new_state.company_facilities(state.player.id), key=lambda f: f.id)
    typer.echo(
        f"Ordered assembly plant {plant.id}: {units:,} units a month for "
        f"{format_money(plant.capex_cents)}, live {format_turn(plant.ready_turn)}"
    )
    typer.echo(f"  {_energy(result.new_state, data)}")


@app.command("sell-plant-capacity")
def sell_plant_capacity(save: SaveOpt) -> None:
    """Start selling spare plant capacity as contract manufacturing (26.2)."""
    from tst.sim.actions.hardware import SellPlantCapacity

    path, data, state = _game(save)
    result = _run(path, data, SellPlantCapacity(_founder(state)))
    typer.echo("Selling spare plant capacity as contract manufacturing")
    typer.echo(f"  {_energy(result.new_state, data)}")


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
        reports = scaleup_views.reports_out(repository.exec_reports(session, state.player.id))
        cash = company_cash(repository.current_balances(session, state.turn), state.player.id)
    profit = scaleup_views.last_month_profit(lines, months, state, data)
    return scaleup_views.scaleup_out(state, data, profit, reports, cash)


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
    from tst.sim.state import ceo_of

    ceo = ceo_of(state, state.player.id)  # M13 (25.6)
    if ceo is None:
        typer.echo("CEO      you" + ("" if state.player.stage >= 4 else " (until the IPO)"))
    else:
        holder = state.person(ceo.person_id)
        typer.echo(f"CEO      {holder.first_name} {holder.last_name} (you are Chair)")
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


@app.command()
def authority(
    save: SaveOpt,
    seat: Annotated[str, typer.Option(help="cto|cro|cmo|coo|cfo")],
    on: Annotated[bool, typer.Option("--on/--off", help="Give or withdraw authority")] = True,
    guard: Annotated[
        list[str] | None,
        typer.Option(help="A guardrail as key=value, e.g. headcount_cap=20 (repeatable)"),
    ] = None,
) -> None:
    """Give a filled seat authority over its function within guardrails, or withdraw it; the
    executive then acts each month in phase 2 (24.1). Energy 2."""
    from tst.sim.actions.authority import SetAuthority

    path, data, state = _game(save)
    rails: list[tuple[str, int | float | tuple[int, ...] | tuple[str, ...]]] = []
    for g in guard or []:
        key, _, value = g.partition("=")
        if not value:
            raise _fail(f"a guardrail is key=value, not {g!r}")
        if key in ("protected_units", "protected_products"):
            rails.append((key, tuple(int(x) for x in value.split(",") if x)))
        elif key == "categories":  # the CPO's (M13b, 27.1)
            rails.append((key, tuple(x for x in value.split(",") if x)))
        else:
            try:
                number = float(value)
            except ValueError as exc:
                raise _fail(f"{key} takes a number, not {value!r}") from exc
            rails.append((key, int(number) if number.is_integer() else number))
    result = _run(path, data, SetAuthority(_actor(state), seat.lower(), on, tuple(rails)))
    a = result.new_state.authority(result.new_state.player.id, seat.lower())
    shown = ", ".join(f"{k}={v}" for k, v in a.guardrails) if a else ""
    typer.echo(f"{seat.upper()} authority {'on' if on else 'off'}: {shown}")
    typer.echo(f"  {_energy(result.new_state, data)}")


@app.command()
def reports(save: SaveOpt) -> None:
    """Each seat's latest quarterly report, then this quarter's decisions and the proposals
    (24.3, 24.4)."""
    path, data, state = _game(save)
    out = _scaleup(path, state, data)
    if not out.reports:
        typer.echo("No reports yet: filled seats report at the end of each quarter.")
    for r in out.reports:
        typer.echo(f"{r.seat.upper()} {r.name}, {r.date_label}:")
        typer.echo(f"  {r.text}")
    for d in out.decisions:
        slip = " (a misstep)" if d.mistake else ""
        typer.echo(f"{d.date_label}  {d.name} ({d.seat.upper()}) {d.text}{slip}")
    for p in out.proposals:
        typer.echo(f"Proposal {p.proposal_id} [{p.status}] {p.name}: {p.text}")


@app.command()
def pitches(save: SaveOpt) -> None:
    """Executives' pitches, pending first, with their cases, and each one's record; the
    Holiday spend limit (27.1, M13b)."""
    path, data, state = _game(save)
    out = _scaleup(path, state, data)
    if not out.pitches:
        typer.echo("No pitches yet: executives with authority pitch at most once a quarter.")
    for p in out.pitches:
        outcome = f", {p.outcome.replace('_', ' ')}" if p.outcome else ""
        typer.echo(
            f"Pitch {p.pitch_id} [{p.status}{outcome}] {p.name} ({p.seat.upper()}), {p.date_label}:"
        )
        typer.echo(f"  {p.title}: {p.why}.")
        typer.echo(
            f"  Cost {format_money(p.cost_cents)} over 12 months; in 24 months {p.case_label}. "
            f"Risk: {p.risk}."
        )
    for seat in out.seats:
        if seat.record and seat.record.pitches:
            r = seat.record
            typer.echo(
                f"{seat.label} {seat.holder_name}: {r.pitches} pitched, {r.approved} approved, "
                f"{r.hits} hit, {r.misses} missed, {r.too_early} too early"
            )
    if out.pitch_policy is not None:
        pol = out.pitch_policy
        which = "default, 5% of cash" if pol.auto_approve_cents is None else "set"
        typer.echo(
            f"Holiday auto-approve limit {format_money(pol.limit_cents)} ({which})"
            + ("; Holiday stops for bigger pitches" if pol.stop_for_big else "")
        )


def _answer_pitch(save: str, pitch: int, answer: str) -> None:
    from tst.sim.actions.authority import AnswerPitch

    path, data, state = _game(save)
    result = _run(path, data, AnswerPitch(_actor(state), pitch, answer))  # type: ignore[arg-type]
    done = result.new_state.pitch(pitch)
    status = done.status.replace("_", " ") if done else answer
    typer.echo(f"Pitch {pitch} {status}: {done.title if done else ''}")
    typer.echo(f"  {_energy(result.new_state, data)}")


@app.command("approve-pitch")
def approve_pitch(save: SaveOpt, pitch: Annotated[int, typer.Argument()]) -> None:
    """Approve a pitch: the move runs at once, as the executive (27.1)."""
    _answer_pitch(save, pitch, "approve")


@app.command("decline-pitch")
def decline_pitch(save: SaveOpt, pitch: Annotated[int, typer.Argument()]) -> None:
    """Decline a pitch: the executive's morale dips (27.1)."""
    _answer_pitch(save, pitch, "decline")


@app.command("pitch-limit")
def pitch_limit(
    save: SaveOpt,
    cents: Annotated[
        int | None,
        typer.Option(help="Holiday auto-approve limit; omit for 5% of cash, 0 to always ask"),
    ] = None,
    stop: Annotated[bool, typer.Option(help="Holiday stops for pitches above the limit")] = False,
) -> None:
    """Set the Holiday spend limit for pitches (27.1)."""
    from tst.sim.actions.authority import SetPitchPolicy

    path, data, state = _game(save)
    _run(path, data, SetPitchPolicy(_actor(state), cents, stop))
    typer.echo("Pitch limit " + ("5% of cash" if cents is None else format_money(cents)))


# --- Debt and macro (M10, formulas.md 20) ------------------------------------------------------


def _macro_rows(path: Path, turn: int) -> dict[int, Any]:
    from sqlalchemy import select

    from tst.db.models import MacroMonthRow
    from tst.db.state_io import macro_from_row

    with repository.open_session(path) as session:
        return {
            r.turn: macro_from_row(r)
            for r in session.scalars(select(MacroMonthRow).where(MacroMonthRow.turn <= turn))
        }


@app.command("macro")
def macro_command(save: SaveOpt) -> None:
    """The base rate, venture climate, consumer confidence and AI compute cost (20.1)."""
    path, data, state = _game(save)
    out = capital_views.macro_out(state, _macro_rows(path, state.turn), data)
    typer.echo(f"Macro, {out.current.label}{' (downturn under way)' if out.downturn else ''}")
    for i in out.indicators:
        typer.echo(f"  {i.label:<20} {i.display:<16} {i.context}")
    if out.after_history:
        typer.echo(f"  History ended {out.history_ends_label}; the economy now moves in cycles.")


@app.command()
def loan(
    save: SaveOpt,
    type: Annotated[str, typer.Option("--type", help="venture_debt|bank_loan")] = "venture_debt",
    amount: Annotated[str | None, typer.Option(help="Dollars; omit to see the terms")] = None,
) -> None:
    """Show loans and what lenders offer, or sign one: `--type venture_debt --amount 2000000`
    (20.3; energy 10)."""
    path, data, state = _game(save)
    if amount is not None:
        result = _run(path, data, TakeLoan(_actor(state), type, _dollars(amount)))
        typer.echo(
            f"Signed for {format_money(_dollars(amount))}; {_energy(result.new_state, data)}"
        )
        with repository.open_session(path) as session:
            state = repository.load_state(session)
    with repository.open_session(path) as session:
        cash = company_cash(repository.ledger_balances(session), state.player.id)
    out = capital_views.loans_out(state, cash, data)
    for x in out.loans:
        typer.echo(
            f"  loan {x.id}: {x.instrument_label} from {x.lender}, "
            f"{format_money(x.principal_cents)}"
            f" signed {x.signed_label} at {x.rate_bp / 100:.2f}%: {x.status_label}, balance "
            f"{format_money(x.balance_cents)}"
        )
        if x.next_payment is not None:
            p = x.next_payment
            typer.echo(
                f"    this month: interest {format_money(p.interest_cents)}, principal "
                f"{format_money(p.principal_cents)}"
            )
        for c in x.covenants:
            state_word = "holds" if c.holds else "BROKEN"
            typer.echo(
                f"    covenant: {c.description}: {state_word}, headroom "
                f"{format_money(c.headroom_cents)}"
            )
    for o in out.offers:
        if o.eligible:
            typer.echo(
                f"  {o.instrument_label}: {o.lender} up to {format_money(o.max_cents)} at "
                f"{o.rate_bp / 100:.2f}% over {o.term_months} months"
            )
        else:
            typer.echo(f"  {o.instrument_label}: not offered ({o.problem})")


@app.command()
def repay(
    save: SaveOpt,
    loan_id: Annotated[int, typer.Option("--loan", help="Loan id")],
    amount: Annotated[str | None, typer.Option(help="Dollars; omit to repay it all")] = None,
) -> None:
    """Repay a loan early, in part or in full, with no fee (20.3; energy 5)."""
    path, data, state = _game(save)
    cents = _dollars(amount) if amount is not None else None
    result = _run(path, data, RepayLoan(_actor(state), loan_id, cents))
    after = result.new_state.loan(loan_id)
    left = format_money(after.balance_cents) if after is not None else "?"
    typer.echo(f"Repaid; balance {left}; {_energy(result.new_state, data)}")


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


# --- Research (M11, formulas.md 21) ----------------------------------------------------------


@app.command()
def research(save: SaveOpt) -> None:
    """Domain levels (baseline + lead), projects, licences, rivals' leads as ranges and the
    era timeline (21.7)."""
    from tst.api.research_views import research_out

    _, data, state = _game(save)
    out = research_out(state, data, state.player.id)
    typer.echo("Domain             Baseline   Lead  Level  Next era (threshold)")
    for d in out.domains:
        era = f"{d.next_era} ({d.next_threshold:.1f})" if d.next_era else "-"
        typer.echo(f"{d.label:<18} {d.baseline:8.1f} {d.lead:6.1f} {d.level:6.1f}  {era}")
    typer.echo(f"Leads decay {out.decay_pct:.1f}% a month.")
    for p in out.projects:
        era = (
            f"; {p.next_era} in ~{p.months_to_era} months"
            if p.next_era and p.months_to_era is not None
            else ""
        )
        typer.echo(
            f"Project {p.project_id}: {p.unit_name} on {p.domain_label}, {p.researchers} "
            f"researchers, {p.funded_pct:.0f}% funded of {format_money(p.needed_cents)}, "
            f"+{p.gain_per_month:.2f} lead a month{era}"
        )
    if out.units:
        free = ", ".join(f"{u.name} (unit {u.unit_id}, {u.researchers})" for u in out.units)
        typer.echo(f"Units free for a project: {free}")
    for x in out.licenses:
        typer.echo(
            f"Licence {x.direction} {x.company}: {x.points:.1f} {x.domain_label} points, "
            f"signed {x.signed}"
        )
    for e in out.eras:
        when = f"arrived {e.arrived}" if e.arrived else f"threshold {e.threshold:.1f}"
        who = f" ({e.caused_by}, {e.months_early} months early)" if e.caused_by else ""
        typer.echo(f"Era {e.label:<22} {e.status:<8} {when}{who}")


@app.command()
def project(
    save: SaveOpt,
    unit: Annotated[int, typer.Option(help="Org unit id (not on a product)")],
    domain: Annotated[str, typer.Option(help="Domain key, e.g. ai")],
    budget: Annotated[
        str | None, typer.Option(help="Monthly budget in dollars; default full")
    ] = None,
) -> None:
    """Start a research project: a unit researches a domain (21.3); energy 6."""
    from tst.sim.actions.research import StartProject

    path, data, state = _game(save)
    amount = cents(budget) if budget is not None else None
    result = _run(path, data, StartProject(_founder(state), unit, domain, amount))
    p = result.new_state.unit_project(unit)
    assert p is not None
    typer.echo(f"Project {p.id} started: unit {unit} researches {domain}")
    typer.echo(f"  {_energy(result.new_state, data)}")


@app.command()
def license(
    save: SaveOpt,
    domain: Annotated[str, typer.Option(help="Domain key, e.g. ai")],
    points: Annotated[float, typer.Option(help="Lead points")],
    from_: Annotated[
        int | None, typer.Option("--from", help="Rival company id to license in from")
    ] = None,
    to: Annotated[int | None, typer.Option(help="Rival company id to license out to")] = None,
) -> None:
    """License research in from a rival (--from) or out to one (--to) (21.5); energy 8."""
    from tst.sim.actions.research import LicenseIn, LicenseOut

    if (from_ is None) == (to is None):
        raise typer.BadParameter("give exactly one of --from and --to")
    path, data, state = _game(save)
    action = (
        LicenseIn(_founder(state), from_, domain, points)
        if from_ is not None
        else LicenseOut(_founder(state), to or 0, domain, points)
    )
    result = _run(path, data, action)
    level = result.new_state.research_lead(result.new_state.player.id, domain)
    typer.echo(f"Licensed {points:g} {domain} points; your lead is now {level:.1f}")
    typer.echo(f"  {_energy(result.new_state, data)}")


# --- M13: IPO, public company, Chair and CEO (formulas.md 25) --------------------------------


@app.command("ipo")
def ipo_cmd(
    save: SaveOpt,
    bank: Annotated[
        str | None, typer.Option(help="Hire this bank (goldman_sachs, morgan_stanley, jp_morgan)")
    ] = None,
) -> None:
    """The IPO: eligibility and the chain's status; --bank hires the banks (energy 10, 25.2)."""
    from tst.api.public_views import ipo_out
    from tst.sim.actions.public import HireBanks
    from tst.sim.markets_public.ipo import eligibility_problem

    path, data, state = _game(save)
    if bank is not None:
        state = _run(path, data, HireBanks(_founder(state), bank)).new_state
        typer.echo(f"Hired {data.game_data.bank(bank).name}; {_energy(state, data)}")
    out = ipo_out(state, state.player.id, data)
    if out is None:
        problem = eligibility_problem(state, state.player.id, data.balance)
        typer.echo("Eligible for an IPO." if problem is None else f"Not eligible: {problem}.")
        for b in data.game_data.banks:
            typer.echo(f"  {b.key:<16}{b.name:<16}fee {b.fee:.1%}")
        return
    typer.echo(f"IPO with {out.bank} (fee {out.fee_pct:.1f}%), hired {out.hired}: {out.status}")
    for s in out.steps:
        typer.echo(f"  [{s.state:<4}] {s.label}: {s.detail}")
    if out.demand:
        typer.echo(f"  The book is {out.demand}.")
    if out.price_cents:
        typer.echo(
            f"  Price {format_money(out.price_cents)} a share; {out.new_shares:,} new shares; "
            f"implied market cap {format_money(out.implied_cap_cents)}"
        )
    if out.listed:
        typer.echo(f"  Listed {out.listed}; first day {out.first_day_pct or 0:+.1f}%")


@app.command()
def guidance(
    save: SaveOpt,
    revenue: Annotated[
        str | None, typer.Option(help="The quarter's revenue in dollars; omit to see consensus")
    ] = None,
    margin: Annotated[float, typer.Option(help="Operating margin in percent")] = 0.0,
) -> None:
    """Quarterly guidance (energy 4, 25.4): set it in a quarter's first month."""
    from tst.sim.actions.public import SetGuidance
    from tst.sim.markets_public.public import consensus, guidance_problem

    path, data, state = _game(save)
    rev, margin_bp = consensus(state, state.player.id)
    if revenue is None:
        problem = guidance_problem(state, state.player.id, rev, data.balance)
        typer.echo(
            f"Consensus: revenue {format_money(rev)}, operating margin {margin_bp / 100:.1f}%"
            + (f" ({problem})" if problem else "")
        )
        return
    try:
        amount = cents(revenue)
    except SimError as exc:
        raise _fail(exc.message) from exc
    result = _run(path, data, SetGuidance(_founder(state), amount, round(margin * 100)))
    typer.echo(
        f"Guided {format_money(amount)} at {margin:.1f}% (consensus {format_money(rev)}); "
        f"{_energy(result.new_state, data)}"
    )


@app.command()
def buyback(
    save: SaveOpt,
    amount: Annotated[str, typer.Option(help="Dollars to spend, e.g. 5000000")],
) -> None:
    """Buy back shares at the price + 2% (energy 6, 25.5)."""
    from tst.sim.actions.public import Buyback

    path, data, state = _game(save)
    try:
        amount_cents = cents(amount)
    except SimError as exc:
        raise _fail(exc.message) from exc
    before = state.player.id
    result = _run(path, data, Buyback(_founder(state), amount_cents))
    from tst.sim.finance.captable import fd_shares

    bought = fd_shares(state, before) - fd_shares(result.new_state, before)
    typer.echo(f"Bought back {bought:,} shares; {_energy(result.new_state, data)}")


@app.command("appoint-ceo")
def appoint_ceo(
    save: SaveOpt,
    person: Annotated[int | None, typer.Option(help="Person id; omit to list candidates")] = None,
) -> None:
    """Appoint a CEO and step up to Chair (stage 4, energy 10, 25.6)."""
    from tst.api.public_views import ceo_out
    from tst.sim.actions.public import AppointCeo

    path, data, state = _game(save)
    if person is None:
        out = ceo_out(state, state.player.id, data)
        if out.name:
            typer.echo(f"CEO: {out.name} since {out.since}")
            for d in out.decisions[:10]:
                flag = " (overridden)" if d.overridden else " (a misstep)" if d.mistake else ""
                typer.echo(f"  {d.label} [{d.id}] {d.scope}: {d.text}{flag}")
            return
        if out.problem:
            typer.echo(out.problem)
        for c in out.candidates:
            typer.echo(f"  {c.person_id:>5}  {c.name:<24}{c.role} ({c.level})")
        return
    result = _run(path, data, AppointCeo(_founder(state), person))
    name = result.new_state.person(person)
    typer.echo(
        f"{name.first_name} {name.last_name} is CEO; you are Chair. "
        f"{_energy(result.new_state, data)}"
    )


# --- M14: mergers and acquisitions (formulas.md 28) -------------------------------------------

from tst.api.schemas.mna import MnaOut  # noqa: E402


def _mna(path: Path, state: GameState, data: LoadedData) -> MnaOut:
    from tst.api import mna_views

    with repository.open_session(path) as session:
        balances = repository.current_balances(session, state.turn)
    return mna_views.mna_out(state, balances, data)


def _company_named(state: GameState, name: str) -> int:
    for c in state.companies:
        if c.name.lower() == name.lower() or str(c.id) == name:
            return c.id
    raise _fail(f"no company called {name!r}")


@app.command()
def targets(save: SaveOpt) -> None:
    """Companies you could buy, by name: market cap or value range, diligence and deals (28)."""
    path, data, state = _game(save)
    out = _mna(path, state, data)
    for t in out.targets:
        if t.listed and t.market_cap_cents is not None:
            value = f"market cap {format_money(t.market_cap_cents)}"
        else:
            value = (
                f"value {format_money(t.value_low_cents or 0)}-"
                f"{format_money(t.value_high_cents or 0)}"
            )
        extra = f"; findings: {', '.join(t.findings) or 'none'}" if t.diligence == "done" else ""
        typer.echo(
            f"{t.company_id:>4} {t.name} ({t.kind}): {value}; "
            f"diligence {t.diligence.replace('_', ' ')}{extra}"
        )
    for d in out.deals:
        typer.echo(
            f"Deal {d.deal_id} {d.target_name}: {format_money(d.price_cents)} [{d.status}], "
            f"{d.mode or 'mode not set'}"
        )
    for a in out.acquisitions:
        typer.echo(
            f"Bought {a.name} ({a.mode}): kept {a.pool_kept}, let go {a.let_go}, "
            f"{a.departed} of {a.key_people} key people left"
        )


@app.command()
def diligence(
    save: SaveOpt, company: Annotated[str, typer.Option(help="Company name or id")]
) -> None:
    """Start two months of due diligence on a company (28.2)."""
    from tst.sim.mna.deals import StartDiligence

    path, data, state = _game(save)
    _run(path, data, StartDiligence(_actor(state), _company_named(state, company)))
    typer.echo("Diligence started: the findings arrive in two months.")


def _company_bid(
    save: str, company: str, price: int, cash_share: float, hostile: bool, brand: bool
) -> None:
    """Bid for a company (28.3). The answer names no hidden number."""
    from tst.sim.mna.deals import BidForCompany

    path, data, state = _game(save)
    action = BidForCompany(
        _actor(state),
        _company_named(state, company),
        price,
        cash_share,
        hostile,
        "brand" if brand else "integrate",
    )
    result = _run(path, data, action)
    for item in result.log_items:
        params = dict(item.params)
        if item.template == "deal_update":
            typer.echo(f"{params.get('title')}. {params.get('detail')}")


@app.command()
def directive(
    save: SaveOpt,
    company: Annotated[str, typer.Option(help="A kept brand's name or id")],
    mode: Annotated[str, typer.Option(help="grow, harvest or defend")],
) -> None:
    """Set a kept brand's directive (28.5)."""
    from tst.sim.mna.integration import SetDirective

    if mode not in ("grow", "harvest", "defend"):
        raise _fail("mode must be grow, harvest or defend")
    path, data, state = _game(save)
    _run(path, data, SetDirective(_actor(state), _company_named(state, company), mode))  # type: ignore[arg-type]
    typer.echo(f"Directive set: {mode}.")


# --- M14b: press, promises and feuds (formulas.md 29) ---------------------------------------


@app.command("press")
def press_cmd(save: SaveOpt) -> None:
    """Credibility and its last changes, and recent press moments (29.1, 29.3)."""
    from tst.api.press_views import press_out

    _, data, state = _game(save)
    out = press_out(state, data)
    typer.echo(f"Credibility {out.credibility.value:.0f}/100")
    for c in out.credibility.history:
        typer.echo(f"  {c.label}  {c.change:+.1f}  {c.cause}")
    for m in out.moments:
        tone = f", answered {m.tone}" if m.tone else ""
        typer.echo(f"  {m.shown or '-':<9} {m.label}: {m.status}{tone}")
    if out.form.moment_id is not None:
        typer.echo(
            "  You can make a promise in this month's press moment (tst promises --make ...)."
        )


@app.command()
def promises(
    save: SaveOpt,
    make: Annotated[
        str | None,
        typer.Option(help="ship, beat, research, no_layoffs or no_price_rise: make a promise"),
    ] = None,
    product: Annotated[int | None, typer.Option(help="Your product id")] = None,
    rival_product: Annotated[int | None, typer.Option(help="The rival's product id (beat)")] = None,
    domain: Annotated[str | None, typer.Option(help="Research domain key")] = None,
    level: Annotated[int | None, typer.Option(help="Research lead to reach")] = None,
    months: Annotated[int | None, typer.Option(help="Months to the deadline (3-18)")] = None,
) -> None:
    """Your public promises; --make one in this month's answered press moment (29.2)."""
    from tst.api.press_views import press_out
    from tst.sim.actions.press import MakePromise

    path, data, state = _game(save)
    if make is not None:
        action = MakePromise(_founder(state), make, product, rival_product, domain, level, months)
        state = _run(path, data, action).new_state
        typer.echo(f"Promised; {_energy(state, data)}")
    out = press_out(state, data)
    if not out.promises:
        typer.echo("No promises yet.")
    for p in out.promises:
        typer.echo(f"  [{p.promise_id}] {p.status:<6} {p.words} ({p.progress})")


@app.command()
def feuds(save: SaveOpt) -> None:
    """Feuds with rival CEOs, highest first, with their recent causes (29.4)."""
    from tst.api.press_views import feud_out

    _, data, state = _game(save)
    ids = sorted({f.rival_id for f in state.feuds if f.company_id == state.player.id})
    rows = sorted((feud_out(state, rid, data) for rid in ids), key=lambda f: -f.score)
    if not rows:
        typer.echo("No feuds.")
    for f in rows:
        flag = " RIVALRY" if f.rivalry else ""
        typer.echo(f"{f.rival:<24} {f.ceo or '-':<24} {f.score:5.1f}{flag}")
        for c in f.causes:
            typer.echo(f"    {c.label}  +{c.change:.0f}  {c.cause}")


# --- M24: the founder's life (formulas.md 32) -----------------------------------------------


@app.command("founder")
def founder_cmd(
    save: SaveOpt,
    sell: Annotated[
        int | None, typer.Option(help="Sell this many of your own shares once listed (32.2)")
    ] = None,
) -> None:
    """Stress, persona and your personal account (32.1-32.4); --sell shares once listed."""
    from tst.api.founder_views import founder_out
    from tst.sim.actions.founder import SellFounderShares

    path, data, state = _game(save)
    if sell is not None:
        state = _run(path, data, SellFounderShares(_founder(state), sell)).new_state
        typer.echo(f"Sold {sell:,} shares; {_energy(state, data)}")
    out = founder_out(state, data)
    s = out.stress
    flag = " BURNT OUT" if s.burnout else ""
    typer.echo(f"{out.founder_name}: stress {s.stress:.0f} / 100{flag} ({s.burnouts} burnouts)")
    for c in s.causes[-6:]:
        typer.echo(f"  {c.date_label:<10} {c.change:+5.1f}  {c.cause}")
    typer.echo("Persona: " + ", ".join(f"{t.label} {t.value:.0f}" for t in out.persona.traits))
    p = out.personal
    typer.echo(
        f"Personal cash {format_money(p.cash_cents)}; endowment {format_money(p.endowment_cents)}"
    )
    for source, amount in p.income.items():
        if amount:
            typer.echo(f"  income from {source}: {format_money(amount)}")
    if p.stake_value_cents is not None:
        typer.echo(f"Stake: {p.stake_shares:,} shares worth {format_money(p.stake_value_cents)}")
    lg = out.legacy
    typer.echo(
        f"Legacy {lg.total} (best score {lg.best_score}, giving {lg.giving:.0f}, "
        f"persona {lg.persona:+.0f})"
    )


@app.command("foundation")
def foundation_cmd(
    save: SaveOpt,
    create: Annotated[bool, typer.Option("--create", help="Create your foundation")] = False,
    cause: Annotated[
        str | None, typer.Option(help="education, climate, health or local (with --create)")
    ] = None,
    name: Annotated[str, typer.Option(help="The foundation's name")] = "",
    city: Annotated[str | None, typer.Option(help="local: a cities.yaml key")] = None,
) -> None:
    """Your foundation (32.3); --create one with a --cause once you hold $1M personally."""
    from tst.api.founder_views import founder_out
    from tst.sim.actions.founder import CreateFoundation

    path, data, state = _game(save)
    if create:
        if cause is None:
            raise typer.BadParameter("--create needs a --cause")
        state = _run(path, data, CreateFoundation(_founder(state), cause, name, city)).new_state
        typer.echo(f"Foundation created; {_energy(state, data)}")
    f = founder_out(state, data).foundation
    if f is None:
        typer.echo("No foundation yet.")
        return
    typer.echo(f"{f.name} ({f.cause_label}), founded {f.created_label}")
    typer.echo(
        f"  endowment {format_money(f.endowment_cents)}; lifetime grants "
        f"{format_money(f.grants_cents)}"
    )
    if f.effect:
        typer.echo(f"  running: {f.effect} until {f.effect_until_label}")


@app.command("give")
def give_cmd(
    save: SaveOpt,
    amount: Annotated[
        int, typer.Option("--cents", help="Personal cash to give to your foundation, cents")
    ],
) -> None:
    """Give personal cash to your foundation's endowment (32.3)."""
    from tst.sim.actions.founder import GiveToFoundation

    path, data, state = _game(save)
    _run(path, data, GiveToFoundation(_founder(state), amount))
    typer.echo(f"Gave {format_money(amount)} to your foundation")


@app.command("lobby")
def lobby_cmd(
    save: SaveOpt,
    region: Annotated[str | None, typer.Option(help="regions.yaml key")] = None,
    monthly: Annotated[
        int | None, typer.Option(help="Monthly lobbying in dollars; 0 stops it")
    ] = None,
) -> None:
    """Government affairs (32.5): influence and exposure by region; set --region --monthly."""
    from tst.api.founder_views import government_out
    from tst.sim.actions.founder import SetLobbying

    path, data, state = _game(save)
    if region is not None or monthly is not None:
        if region is None or monthly is None:
            raise typer.BadParameter("give both --region and --monthly")
        state = _run(path, data, SetLobbying(_founder(state), region, monthly)).new_state
        typer.echo(f"Lobbying set; {_energy(state, data)}")
    gov = government_out(state, data)
    if not gov.regions:
        typer.echo("No lobbying.")
    for r in gov.regions:
        typer.echo(
            f"{r.region_label:<26} influence {r.influence:5.1f}  "
            f"{format_money(r.monthly_cents)}/month  exposure {r.exposure}  "
            f"scandals {r.scandals}"
        )


# --- The group (M16, formulas.md 31) ----------------------------------------------------------


def _group_table(path: Path, data: LoadedData) -> None:
    from tst.api.group_views import group_out

    with repository.open_session(path) as session:
        state = repository.load_state(session)
        balances = repository.ledger_balances(session)
    g = group_out(state, balances, data)
    if not g.formed:
        typer.echo(
            "No holding company yet: "
            + ("you can form one (tst form-holding)." if g.can_form else "; ".join(g.reasons))
        )
    for e in g.entities:
        stake = "" if e.depth == 0 else f" {e.stake_bp / 100:.1f}% {e.treatment}"
        margin = "—" if e.operating_margin is None else f"{e.operating_margin:.1%}"
        if e.market_cap_cents is not None:
            value = f"cap {format_money(e.market_cap_cents)}"
        elif e.value_low_cents is not None and e.value_high_cents is not None:
            value = f"value {format_money(e.value_low_cents)}-{format_money(e.value_high_cents)}"
        else:
            value = ""
        typer.echo(
            f"{'  ' * e.depth}{e.name} [{e.role}]{stake}: revenue {format_money(e.revenue_cents)}"
            f" (12 months), margin {margin}, cash {format_money(e.cash_cents)} {value}".rstrip()
        )


@app.command("group")
def group_cmd(save: SaveOpt) -> None:
    """The group (31.10): the entity tree with stakes, treatments and each company's numbers."""
    path, data, _ = _game(save)
    _group_table(path, data)


@app.command("form-holding")
def form_holding_cmd(save: SaveOpt) -> None:
    """Form the holding company (31.2): it takes the listing, the cap table and the board."""
    from tst.sim.group.actions import FormHolding

    path, data, state = _game(save)
    state = _run(path, data, FormHolding(_founder(state))).new_state
    typer.echo(f"Holding company formed; {_energy(state, data)}")
    _group_table(path, data)


@app.command("mandate")
def mandate_cmd(
    save: SaveOpt,
    company: Annotated[int, typer.Option("--company", help="A subsidiary's company id")],
    kind: Annotated[str, typer.Option("--kind", help="grow, margin or return_cash")],
    capex: Annotated[int, typer.Option("--capex-cents", help="Yearly capex limit; 0: none")] = 0,
) -> None:
    """Set a subsidiary's mandate (31.4): what its CEO runs it for."""
    from tst.sim.group.actions import SetMandate

    path, data, state = _game(save)
    state = _run(path, data, SetMandate(_founder(state), company, kind, capex)).new_state  # type: ignore[arg-type]
    typer.echo(f"Mandate set; {_energy(state, data)}")
    _group_table(path, data)


def _group_act(save: str, make: Callable[[int], Action]) -> None:
    path, data, state = _game(save)
    state = _run(path, data, make(_founder(state))).new_state
    typer.echo(f"Done; {_energy(state, data)}")
    _group_table(path, data)


CompanyOpt = Annotated[int, typer.Option("--company", help="The company's id")]
PctOpt = Annotated[float, typer.Option("--pct", help="Percent of the company, e.g. 30")]


@app.command("sell-stake")
def sell_stake_cmd(save: SaveOpt, company: CompanyOpt, pct: PctOpt) -> None:
    """Sell part of a subsidiary to investors; the group keeps control (31.5)."""
    from tst.sim.group.actions import SellStake

    _group_act(save, lambda f: SellStake(f, company, round(pct * 100)))


@app.command("buy-out")
def buy_out_cmd(save: SaveOpt, company: CompanyOpt) -> None:
    """Buy out a subsidiary's minorities at the premium (31.5)."""
    from tst.sim.group.actions import BuyOutMinorities

    _group_act(save, lambda f: BuyOutMinorities(f, company))


@app.command("carve-out")
def carve_out_cmd(save: SaveOpt, company: CompanyOpt, pct: PctOpt) -> None:
    """List 10-40% of a subsidiary (31.5)."""
    from tst.sim.group.actions import CarveOut

    _group_act(save, lambda f: CarveOut(f, company, round(pct * 100)))


@app.command("spin-off")
def spin_off_cmd(
    save: SaveOpt,
    company: CompanyOpt,
    keep: Annotated[
        float, typer.Option("--keep", help="Percent the group keeps, at most 19.9")
    ] = 0.0,
) -> None:
    """Give a subsidiary's shares to the holding company's shareholders (31.5)."""
    from tst.sim.group.actions import SpinOff

    _group_act(save, lambda f: SpinOff(f, company, round(keep * 100)))


@app.command("stake")
def stake_cmd(save: SaveOpt, company: CompanyOpt, pct: PctOpt) -> None:
    """Buy a listed rival's shares on the market up to --pct (31.5)."""
    from tst.sim.group.actions import BuyStake

    _group_act(save, lambda f: BuyStake(f, company, round(pct * 100)))


@app.command("venture")
def venture_cmd(
    save: SaveOpt,
    startup: Annotated[int, typer.Option("--startup", help="The startup's company id")],
    cents: Annotated[int, typer.Option("--cents", help="The investment, cents")],
) -> None:
    """Invest in a startup's round for 5-25% (31.5)."""
    from tst.sim.group.actions import VentureInvest

    _group_act(save, lambda f: VentureInvest(f, startup, cents))


@app.command("transfer-price")
def transfer_price_cmd(
    save: SaveOpt,
    flow: Annotated[str, typer.Option("--flow", help="SELLER:BUYER:GOOD, e.g. 7:1:compute")],
    kind: Annotated[str, typer.Option("--kind", help="cost, cost_plus or market")],
    margin: Annotated[float | None, typer.Option(help="cost plus: the margin, 0-1")] = None,
) -> None:
    """Set the price one group company supplies another at (31.6)."""
    from tst.sim.group.actions import SetTransferPrice

    seller, buyer, good = flow.split(":")
    _group_act(save, lambda f: SetTransferPrice(f, int(seller), int(buyer), good, kind, margin))


# --- M25: Explain, achievements and mods ---------------------------------------------------


@app.command("explain")
def explain_cmd(
    save: SaveOpt,
    metric: Annotated[str, typer.Option("--metric", help="A metric key, e.g. churn or cash")],
    entity: Annotated[
        str | None,
        typer.Option(
            "--entity", help="Product or person id, account code (cost_line) or category key"
        ),
    ] = None,
) -> None:
    """Print a number's driver breakdown, its trend and the template explanation (M25)."""
    from tst.advisor.ask import explained
    from tst.advisor.metrics import METRICS
    from tst.advisor.template import amount, driver_text

    path, data, _ = _game(save)
    try:
        found = explained(path, data, metric, entity)
    except SimError as exc:
        keys = ", ".join(METRICS)
        raise _fail(f"{exc.message} (metrics: {keys})") from exc
    e = found.explanation
    value = "-" if e.value is None else amount(e.value, e.metric.unit)
    typer.echo(f"{e.metric.label} of {e.subject}: {value}")
    for item in e.items:
        typer.echo(f"  {item.label:<48} {amount(item.amount, item.unit)}")
    if e.note:
        typer.echo(f"  ({e.note})")
    if e.trend:
        trend = ", ".join(
            f"{format_turn(p.turn)} {amount(p.value, e.metric.unit)}" for p in e.trend
        )
        typer.echo(f"Trend: {trend}")
    for d in e.drivers:
        typer.echo(f"  - {driver_text(d, e.metric.unit, e.metric.label.lower())}")
    typer.echo(found.template)


@app.command("mods")
def mods_cmd() -> None:
    """List the data-editor mods in saves/mods (M25): name, files changed, description."""
    from tst.mods.store import list_mods

    settings = Settings()
    found = list_mods(settings.resolved_save_dir())
    if not found:
        typer.echo(
            "No mods. Make one in the Data editor (main menu), or write saves/mods/<name>.yaml."
        )
    for m in found:
        files = ", ".join(sorted(m.files)) or "no changes"
        typer.echo(f"{m.name:<24} {files}" + (f"  {m.description}" if m.description else ""))
