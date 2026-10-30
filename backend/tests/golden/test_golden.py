"""Golden seeds and determinism (ADR-0002).

Seeds 1..10 are played for 24 turns through the full persistence path, as an
ex_big_tech_founders game following a scripted plan (M1b hiring; M2a interviews before every
offer, two teams with leads at turn 6, a department once there are 10 staff, and a
recruiter-led hiring plan; M3a a B2B SaaS product built by the company root from turn 2
and the Product team from turn 7, launched when allowed, an account executive and a
marketer sought from turn 8, and a price cut at turn 18; M4a a $1M SAFE from turn 3 at a
cap of 1.2 x V_base, a $2M seed once the product is live and a Series A once ARR passes $1M),
and their per-turn snapshots are
compared with
tests/golden/snapshots/seed_NN.json. The founder's current
ability after each turn goes to seed_NN.founder_ca.json instead: CA is hidden (ADR-0007), so
it never enters turn_snapshot, which the API returns. Never edit these files by hand:
regenerate with `uv run pytest tests/golden --update-golden` and record why in CHANGELOG.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from tests.helpers import answer_critical
from tst.db.models import LedgerEntryRow, TurnSnapshotRow
from tst.db.repository import create_save, load_state, open_session, run_action, run_turn
from tst.loader import LoadedData
from tst.sim.actions import (
    AcceptBridge,
    AcceptTermSheet,
    AssignUnit,
    CloseSearch,
    CreatePlan,
    CreateProduct,
    CreateUnit,
    Interview,
    LaunchProduct,
    MakeOffer,
    MovePerson,
    OpenSearch,
    RaiseSafe,
    SetLeader,
    SetPrice,
    StartRound,
)
from tst.sim.actions.org import departments_unlocked
from tst.sim.actions.products import launch_problems
from tst.sim.calendar import format_turn
from tst.sim.finance import statements as fs
from tst.sim.finance.captable import last_round, open_round
from tst.sim.finance.fundraising import base_value, next_series, series_problem
from tst.sim.people.models import current_ability
from tst.sim.state import GameState

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"
SEEDS = range(1, 11)
TURNS = 24


TARGET_STAFF = 10  # the player stops making offers at this many employees
CLOSE_JOB_POST_TURN = 6
TEAMS_TURN = 6  # two teams with leads (M2a)
INTERVIEW_ENERGY = 8  # founder.energy_cost.interview (M4c)
PLAN_ROLE = "software_engineer"  # the recruiter-led plan (M2a)
PLAN_TARGET = 2
PLAN_RATIO_BP = 11_000
PRODUCT_TURN = 2  # M3a: the root starts building a B2B SaaS product
PRODUCT_PRICES = {"smb": 4000, "mid_market": 70_000}  # $40 and $700 a month
GO_TO_MARKET_TURN = 8  # network searches for an account executive and a marketer
GO_TO_MARKET_ROLES = ("account_executive", "marketer")
GO_TO_MARKET_RATIO = 1.2  # offers at 1.2x the ask, whatever the headcount
PRICE_CUT_TURN = 18
PRICE_CUT_CENTS = 3500  # SMB to $35
SAFE_TURN = 3  # M4a: a SAFE from this turn until one fills
SAFE_AMOUNT = 100_000_000  # $1M
SAFE_OPTIMISM = 1.2  # cap = 1.2 x V_base: an even chance (formulas.md 14.4)
ROUND_TARGETS = {"seed": 200_000_000, "a": 600_000_000}  # $2M seed, $6M Series A


def _state(path: Path) -> GameState:
    with open_session(path) as session:
        return load_state(session)


def _employees(state: GameState) -> list[int]:
    return sorted(e.person_id for e in state.staff(1) if e.person_id != 1 and e.status == "active")


def _unit_of(state: GameState, person_id: int) -> int | None:
    employment = state.employment_of(person_id)
    assert employment is not None
    return employment.unit_id


def _role_of(state: GameState, person_id: int) -> str:
    employment = state.employment_of(person_id)
    assert employment is not None
    return employment.role


def org_plan(path: Path, data: LoadedData, state: GameState) -> None:
    """M2a: two teams with leads at turn 6, a department once departments unlock, and a
    hiring plan run by the first recruiter on staff. Choices go by person id."""
    actor = 1
    if state.turn == TEAMS_TURN:
        people = _employees(state)
        for name, members in (("Platform", people[0::2]), ("Product", people[1::2])):
            if not members:
                continue
            run_action(path, data, CreateUnit(actor, "team", name))
            unit = max(_state(path).units, key=lambda u: u.id).id
            for pid in members:
                run_action(path, data, MovePerson(actor, pid, unit))
            run_action(path, data, SetLeader(actor, unit, members[0]))
    if (
        state.turn > TEAMS_TURN
        and not any(u.kind == "department" for u in state.units)
        and departments_unlocked(state, 1, data.balance)
    ):
        run_action(path, data, CreateUnit(actor, "department", "Engineering"))
        after = _state(path)
        dept = max(after.units, key=lambda u: u.id).id
        in_root = [p for p in _employees(after) if _unit_of(after, p) is None]
        for pid in in_root:
            run_action(path, data, MovePerson(actor, pid, dept))
        if in_root:
            run_action(path, data, SetLeader(actor, dept, in_root[0]))
    recruiters = [p for p in _employees(state) if _role_of(state, p) == "recruiter"]
    if recruiters and not state.plans and state.next_ids.plan == 1:
        run_action(
            path,
            data,
            CreatePlan(actor, recruiters[0], PLAN_ROLE, PLAN_TARGET, "any", PLAN_RATIO_BP),
        )


def product_plan(path: Path, data: LoadedData) -> None:
    """M3a: one B2B SaaS product (SMB and mid-market) built by the company root from turn 2,
    and by the Product team (formed at turn 6) from turn 7, launched as soon as it is
    allowed; network searches for an account executive and a
    marketer at turn 8, each offered 1.2x the ask (after an interview) until one is on staff;
    a price cut to $35 in SMB at turn 18. Runs before the hiring steps, so their energy use
    comes after these."""
    actor = 1
    state = _state(path)
    product = next(iter(state.company_products(1)), None)
    if state.turn == PRODUCT_TURN and product is None:
        product_id = state.next_ids.product
        run_action(
            path, data, CreateProduct(actor, "Golden CRM", "b2b_saas", tuple(PRODUCT_PRICES))
        )
        for segment, price in PRODUCT_PRICES.items():
            run_action(path, data, SetPrice(actor, product_id, segment, price))
        run_action(path, data, AssignUnit(actor, product_id, None))
        state = _state(path)
        product = state.product(product_id)
    ready = product is not None and not launch_problems(
        state, product, data.balance, data.game_data
    )
    if product is not None and product.status == "in_development" and ready:
        run_action(path, data, LaunchProduct(actor, product.id))
    if product is not None and state.turn == PRICE_CUT_TURN:
        run_action(path, data, SetPrice(actor, product.id, "smb", PRICE_CUT_CENTS))
    team = next((u for u in state.units if u.name == "Product"), None)
    if product is not None and team is not None and team.product_id is None:
        run_action(path, data, AssignUnit(actor, product.id, team.id))
    if state.turn == GO_TO_MARKET_TURN:
        for role in GO_TO_MARKET_ROLES:
            run_action(path, data, OpenSearch(actor, role, "network"))
    state = _state(path)
    for role in GO_TO_MARKET_ROLES:
        if any(_role_of(state, p) == role for p in _employees(state)):
            continue
        pool = [c for c in state.candidates if state.person(c.person_id).role == role]
        if any(state.pending_offer_for(c.person_id) for c in pool):
            continue
        for candidate in pool:
            if candidate.interviewed_turn is None:
                if (state.person_state(actor).energy or 0) < INTERVIEW_ENERGY:
                    break
                run_action(path, data, Interview(actor, candidate.person_id))
            ask = state.person(candidate.person_id).salary_expectation_cents or 0
            offer = MakeOffer(actor, candidate.person_id, round(ask * GO_TO_MARKET_RATIO), 0)
            run_action(path, data, offer)
            break


def funding_plan(path: Path, data: LoadedData) -> None:
    """M4a: a $1M SAFE from turn 3 at a cap of 1.2 x V_base, raised again until one fills;
    a $2M seed once the product is live and a $6M Series A once ARR passes $1M, accepting
    the highest pre-money term sheet (and starting again if a round fails or lapses); any
    bridge offer accepted. Runs first each turn, before the energy goes on hiring."""
    actor = 1
    state = _state(path)
    safes = state.company_safes(1)
    raised = any(
        s.kind == "safe" and s.status in ("pending", "outstanding", "converted") for s in safes
    )
    if state.turn >= SAFE_TURN and not raised and not last_round(state, 1):
        cap = round(SAFE_OPTIMISM * base_value(state, 1, data.balance, data.game_data))
        run_action(path, data, RaiseSafe(actor, SAFE_AMOUNT, cap))
    for safe in safes:
        if safe.kind == "bridge" and safe.status == "offered":
            run_action(path, data, AcceptBridge(actor, safe.id))
    current = open_round(state, 1)
    if current is not None:
        sheets = [t for t in state.sheets_of(current.id) if t.status == "offered"]
        if current.status == "open" and sheets:
            best = max(sheets, key=lambda t: (t.pre_money_cents, -t.id))
            run_action(path, data, AcceptTermSheet(actor, best.id))
        return
    series = next_series(state, 1)
    live = any(p.status == "live" for p in state.company_products(1))
    if series in ROUND_TARGETS and live and series_problem(state, 1, series, data.balance) is None:
        run_action(path, data, StartRound(actor, series, ROUND_TARGETS[series]))


def hiring_plan(path: Path, data: LoadedData) -> None:
    """Scripted player actions between turns, exercising payroll, morale and departures.

    Turn 0 opens all three channels, plus a network search for a recruiter. Every turn, while
    staff are below TARGET_STAFF, open candidates without an offer are interviewed (while the
    founder has the energy) and get one: 1.10x the ask for odd ids, 0.90x for even ids (some
    underpaid hires, to stress morale), no equity. The job post closes at turn 6. Then the
    M2a org steps (org_plan).
    """
    state = _state(path)
    actor = 1
    if state.turn == 0:
        run_action(path, data, OpenSearch(actor, "software_engineer", "job_post"))
        run_action(path, data, OpenSearch(actor, "product_manager", "recruiter"))
        run_action(path, data, OpenSearch(actor, "designer", "network"))
        run_action(path, data, OpenSearch(actor, "recruiter", "network"))
    if state.turn == CLOSE_JOB_POST_TURN:
        for search in state.searches:
            if search.actor_id == actor:
                run_action(path, data, CloseSearch(actor, search.id))
    staff = len(state.staff(1)) - 1
    energy = state.person_state(actor).energy or 0
    for candidate in state.candidates:
        if staff >= TARGET_STAFF:
            break
        if state.pending_offer_for(candidate.person_id) is not None:
            continue
        if candidate.interviewed_turn is None:
            if energy < INTERVIEW_ENERGY:
                break
            run_action(path, data, Interview(actor, candidate.person_id))
            energy -= INTERVIEW_ENERGY
        ask = state.person(candidate.person_id).salary_expectation_cents or 0
        ratio = 1.10 if candidate.person_id % 2 else 0.90
        run_action(path, data, MakeOffer(actor, candidate.person_id, round(ask * ratio), 0))
        staff += 1  # count pending offers toward the target
    org_plan(path, data, _state(path))


def play(
    save_dir: Path, slug: str, seed: int, data: LoadedData
) -> tuple[Path, list[dict[str, Any]]]:
    """Play TURNS turns with the hiring plan; return the save and the founder's CA per turn."""
    path = create_save(
        slug,
        seed,
        "ex_big_tech_founders",
        company_name="Golden Co",
        data=data,
        save_dir=save_dir,
    )
    founder_ca = []
    for _ in range(TURNS):
        funding_plan(path, data)
        product_plan(path, data)
        hiring_plan(path, data)
        answer_critical(path, data)  # M6: a critical event must be answered before Continue
        result = run_turn(path, data)
        with open_session(path) as session:
            founder = next(p for p in load_state(session).people if p.is_founder)
        founder_ca.append(
            {
                "turn": result.snapshot.turn,
                "date": format_turn(result.snapshot.turn),
                "founder_ca": current_ability(founder, data.game_data),
            }
        )
    return path, founder_ca


def _check_golden(name: str, actual: object, update: bool) -> None:
    golden = SNAPSHOT_DIR / name
    if update:
        SNAPSHOT_DIR.mkdir(exist_ok=True)
        with golden.open("w", encoding="utf-8", newline="\n") as fh:
            json.dump(actual, fh, indent=2)
            fh.write("\n")
        return
    if not golden.is_file():
        pytest.fail(f"{golden.name} missing; run `uv run pytest tests/golden --update-golden`")
    assert actual == json.loads(golden.read_text(encoding="utf-8"))


def snapshots(path: Path, company_id: int | None = 1) -> list[dict[str, Any]]:
    """Month-end snapshots: the player's (the golden files), or every company's (None)."""
    with open_session(path) as session:
        query = select(TurnSnapshotRow).order_by(TurnSnapshotRow.turn, TurnSnapshotRow.company_id)
        if company_id is not None:
            query = query.where(TurnSnapshotRow.company_id == company_id)
        rows = session.scalars(query).all()
        return [
            {"turn": r.turn, "date": format_turn(r.turn), "company_id": r.company_id, **r.kpis}
            for r in rows
        ]


def ledger_rows(path: Path) -> list[tuple[Any, ...]]:
    with open_session(path) as session:
        entries = session.scalars(select(LedgerEntryRow).order_by(LedgerEntryRow.id)).all()
        return [
            (e.id, e.turn, e.company_id, e.memo, ln.id, ln.account_code, ln.amount_cents)
            for e in entries
            for ln in e.lines
        ]


def assert_statements_reconcile(path: Path, loaded: LoadedData) -> None:
    """formulas.md 14.1 on every turn: the balance sheet balances, cash flow's parts add up
    to the cash account's movement, and month-end cash matches turn_snapshot."""
    types = {a.code: a.type for a in loaded.game_data.accounts}
    lines = [
        (turn, account, amount)
        for _, turn, company, _, _, account, amount in ledger_rows(path)
        if company == 1
    ]
    cash_at = {row["turn"]: row["cash_cents"] for row in snapshots(path)}
    for turn in range(TURNS):
        sheet = fs.balance_sheet(lines, types, turn)
        assert sheet.total_assets == sheet.total_liabilities_and_equity, turn
        assert sheet.assets.get("1000_cash", 0) == cash_at[turn], turn
        flow = fs.cash_flow(lines, types, turn, turn)
        assert flow.reconciles, turn
    for period in fs.PERIODS:
        for first, last in fs.period_bounds(period, TURNS - 1):
            assert fs.cash_flow(lines, types, first, last).reconciles


@pytest.mark.parametrize("seed", SEEDS)
def test_golden_seed(
    seed: int,
    tmp_path: Path,
    loaded: LoadedData,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if seed == 1:  # M6.0: every reuse of the remembered state is compared with the save
        monkeypatch.setenv("TST_STATE_CACHE_CHECK", "1")
    path, founder_ca = play(tmp_path, f"golden-{seed}", seed, loaded)
    actual = snapshots(path)
    assert len(actual) == TURNS
    # CA is hidden (ADR-0007): it must never appear in turn_snapshot, which the API returns.
    assert all("founder_ca" not in row and "current_ability" not in row for row in actual)
    update = bool(request.config.getoption("--update-golden"))
    _check_golden(f"seed_{seed:02d}.json", actual, update)
    _check_golden(f"seed_{seed:02d}.founder_ca.json", founder_ca, update)
    assert_statements_reconcile(path, loaded)


def test_same_seed_twice_is_identical(tmp_path: Path, loaded: LoadedData) -> None:
    first, first_ca = play(tmp_path / "a", "twin", 42, loaded)
    second, second_ca = play(tmp_path / "b", "twin", 42, loaded)
    assert first_ca == second_ca
    with open_session(first) as a, open_session(second) as b:
        assert load_state(a).people == load_state(b).people
    assert snapshots(first, None) == snapshots(second, None)  # rivals' books too (M5)
    assert ledger_rows(first) == ledger_rows(second)
    assert len(ledger_rows(first)) > 2 + 3 * TURNS  # payroll and fees on top of office/overhead
