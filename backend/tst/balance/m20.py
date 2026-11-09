"""M20's balance runs (docs/formulas.md 36.5): refineries' margins, power, wafers for chips and
by-products in a ban, and "nothing else moves". Printed by tools/m20_targets.py.

Each run is a real game (`tst.balance.game`), the plant ordered through `build_refinery`,
staffed by a unit of process engineers at a set skill, and (to save simulated years) made
ready at once from its order month: construction and the overrun are tested elsewhere.
"""

from __future__ import annotations

import statistics as st
from collections.abc import Sequence
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path

from tst.balance.game import Game, start_game
from tst.loader import LoadedData, load_all
from tst.sim.actions.facilities import StaffFacility
from tst.sim.calendar import ym_to_turn
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH, PPE
from tst.sim.org.models import OrgUnit
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.refining import goods as rg
from tst.sim.refining.actions import BuildRefinery
from tst.sim.refining.plants import refinery_of
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    with_employment,
    with_facility,
    with_person,
    with_person_state,
    with_unit,
)

DATA = Path(__file__).resolve().parents[2] / "data"
PLAYER = 1
RICH = 10**14  # cents: cash is never the constraint in these runs
SKILL = 12.0  # the staff's manufacturing skill
SALARY = 7_800_000  # a mid process engineer's salary, cents a year (roles.yaml)


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


def game_at(seed: int, turn: int, scenario: str = "funded_spinout") -> Game:
    g = start_game(loaded(), seed, scenario)
    g.balances[(PLAYER, "1000_cash")] = g.balances.get((PLAYER, "1000_cash"), 0) + RICH
    g.state = replace(g.state, turn=turn)
    return g


def hire_unit(game: Game, name: str, n: int, skill: float = SKILL, seed: int = 1) -> int:
    """A team of `n` process engineers at manufacturing skill `skill`; its unit id."""
    state = game.state
    lg = loaded()
    role = lg.game_data.role("process_engineer")
    uid, ids = state.next_ids.take("unit")
    state = replace(state, next_ids=ids)
    state = with_unit(
        state,
        OrgUnit(
            id=uid,
            company_id=PLAYER,
            kind="team",
            name=name,
            parent_id=None,
            leader_id=None,
            policy=None,
            created_turn=state.turn,
        ),
    )
    rng = RngFactory(seed)
    for i in range(n):
        pid, ids = state.next_ids.take("person")
        eid, ids = ids.take("employment")
        state = replace(state, next_ids=ids)
        person = generate_person(
            rng.stream(0, "misc", 500 + uid * 1000 + i),
            lg.game_data,
            lg.balance,
            state.turn,
            role,
            "mid",
            "north_america",
            person_id=pid,
        )
        person = replace(person, skills=person.skills.updated({"manufacturing": skill}))
        state = with_person(state, person)
        state = with_employment(
            state,
            Employment(
                id=eid,
                person_id=pid,
                company_id=PLAYER,
                role="process_engineer",
                level="mid",
                salary_cents=SALARY,
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
                unit_id=uid,
            ),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=65.0))
    game.state = state
    return uid


def build(
    game: Game,
    recipe: str,
    region: str,
    capacity: int,
    *,
    ready_now: bool = True,
    skill: float = SKILL,
    host_id: int | None = None,
) -> int:
    """Order, staff (full coverage) and, by default, finish a plant now. Its facility id."""
    b = loaded().balance
    kind = b.facility.kinds[b.refining.recipes[recipe].kind]
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))
    fid = game.state.next_ids.facility
    ok = game.act(BuildRefinery(game.founder_id, recipe, region, capacity, host_id=host_id))
    if not ok:
        raise RuntimeError(f"build_refinery refused: {dict(game.refused)}")
    need = -(-capacity // int(kind.staff_per)) if kind.staff_per >= 1 else capacity
    uid = hire_unit(game, f"{recipe} {fid}", max(1, need), skill, seed=fid)
    game.state = with_person_state(game.state, replace(ps, energy=100))
    game.act(StaffFacility(game.founder_id, fid, uid))
    if ready_now:  # built and paid for: capex to PPE now, so it depreciates as a real plant
        f = game.state.facility(fid)
        assert f is not None
        game.state = with_facility(
            game.state,
            replace(
                f,
                ready_turn=game.state.turn,
                late_turn=game.state.turn,
                on_time=f.capacity,
                status="building",
                capex_paid_cents=f.capex_cents,
            ),
        )
        game.balances[(PLAYER, CASH)] = game.balances.get((PLAYER, CASH), 0) - f.capex_cents
        game.balances[(PLAYER, PPE)] = game.balances.get((PLAYER, PPE), 0) + f.capex_cents
    game.notes[f"staff:{fid}"] = uid
    return fid


def keep_staffed(game: Game, skill: float = SKILL) -> None:
    """A sensible player replaces engineers who leave: each plant's unit is topped up to its
    need (the balance runs measure plants, not retention)."""
    from tst.sim.facilities import lifecycle

    b = loaded().balance
    for f in list(game.state.facilities):
        uid = game.notes.get(f"staff:{f.id}")
        if uid is None or f.status == "closed":
            continue
        s = lifecycle.staffing(game.state, f, b)
        if s.staff < s.needed:
            _add_staff(game, uid, s.needed - s.staff, skill, f.id)


def _add_staff(game: Game, uid: int, n: int, skill: float, seed: int) -> None:
    state = game.state
    lg = loaded()
    role = lg.game_data.role("process_engineer")
    rng = RngFactory(seed)
    for i in range(n):
        pid, ids = state.next_ids.take("person")
        eid, ids = ids.take("employment")
        state = replace(state, next_ids=ids)
        person = generate_person(
            rng.stream(state.turn, "misc", pid, i),
            lg.game_data,
            lg.balance,
            state.turn,
            role,
            "mid",
            "north_america",
            person_id=pid,
        )
        person = replace(person, skills=person.skills.updated({"manufacturing": skill}))
        state = with_person(state, person)
        state = with_employment(
            state,
            Employment(
                id=eid,
                person_id=pid,
                company_id=PLAYER,
                role="process_engineer",
                level="mid",
                salary_cents=SALARY,
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
                unit_id=uid,
            ),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=65.0))
    game.state = state


def play(game: Game, n: int = 1) -> None:
    """Months with the plants kept staffed."""
    for _ in range(n):
        keep_staffed(game)
        game.turn()


def months(game: Game, n: int) -> None:
    for _ in range(n):
        game.turn()


@dataclass(frozen=True)
class PlantRun:
    recipe: str
    region: str
    margins: tuple[float, ...]
    units: tuple[float, ...]  # unit cost each month
    markets: tuple[float, ...]

    @property
    def median_margin(self) -> float:
        return st.median(self.margins) if self.margins else float("nan")


def run_plant(
    recipe: str,
    region: str,
    start: tuple[int, int],
    end: tuple[int, int],
    seed: int = 1,
    capacity: int | None = None,
    process_lead: float = 20.0,
) -> PlantRun:
    """A plant live from `start` through `end` (inclusive), its input bought at spot. The
    company has a process lead (as if researched, 36.3) so semiconductor grades run at their
    stated yield: a sensible player does not run a wafer plant at half yield."""
    from tst.sim.research.models import ResearchLead
    from tst.sim.state import with_research_lead

    b = loaded().balance
    kind = b.facility.kinds[b.refining.recipes[recipe].kind]
    size = capacity or (kind.sizes or b.facility.sizes)[1]
    game = game_at(seed, ym_to_turn(*start) - 1)
    domain = b.refining.domain
    game.state = with_research_lead(game.state, ResearchLead(PLAYER, domain, process_lead))
    fid = build(game, recipe, region, size)
    margins: list[float] = []
    units: list[float] = []
    markets: list[float] = []
    ramp = b.refining.recipes[recipe].ramp_months
    last = ym_to_turn(*end)
    while game.state.turn <= last:
        play(game)
        ref = refinery_of(game.state, fid)
        assert ref is not None and ref.month is not None
        pm = ref.month
        if pm.turn - ym_to_turn(*start) + 1 < ramp:  # 36.5 measures running plants
            continue
        if pm.margin is not None:
            margins.append(pm.margin)
            units.append(pm.unit_cost_cents)
            markets.append(pm.market_cents)
    return PlantRun(recipe, region, tuple(margins), tuple(units), tuple(markets))


def price_now(game: Game, good: str) -> float:
    lg = loaded()
    return rg.price_cents(game.state, good, lg.balance, lg.game_data)


def seeds(n: int) -> Sequence[int]:
    return range(1, n + 1)


# --- Chip companies (36.2, targets 3 and 4) --------------------------------------------------


def chip_game(
    seed: int,
    start: tuple[int, int],
    months: int = 240,
    process_lead: float = 20.0,
) -> tuple[Game, int]:
    """M12b's device maker with its own mobile SoC (formulas.md 26.6 target 4's company): a
    live device on a contract-manufacturing contract and a fabless SoC on a TSMC wafer
    contract signed at `start`, every chip going into its devices; plus a process lead (as if
    researched) so semiconductor grades run at full yield. The chip product's id."""
    from tst.balance import m12b
    from tst.sim.research.models import ResearchLead
    from tst.sim.state import with_research_lead

    lg = loaded()
    m12b_game, _ = m12b.device_company(seed, own_chip=True, start=ym_to_turn(*start))
    game = game_at(seed, ym_to_turn(*start))
    state = replace(
        m12b_game.state, save_meta=game.state.save_meta
    )  # m12b's company, this module's balances
    chip = next(p for p in state.company_products(PLAYER) if p.category == "chips_mobile_soc")
    for c in state.production_contracts:
        state = m12b.with_production_contract(
            state, replace(c, end_turn=c.signed_turn + months - 1)
        )
    domain = lg.balance.refining.domain
    game.state = with_research_lead(state, ResearchLead(PLAYER, domain, process_lead))
    return game, chip.id


@dataclass(frozen=True)
class WaferRun:
    seed: int
    own_share: tuple[float, ...]  # own wafers / starts each month
    saving: tuple[float, ...]  # 1 - own wafer price / market wafer price, months with own wafers
    shortage_delivered: tuple[float, ...]  # wafers delivered / starts in 2021-2022
    spot_shortage_delivered: tuple[float, ...]  # the same for a twin without a wafer plant

    @property
    def mean_saving(self) -> float:
        return st.mean(self.saving) if self.saving else float("nan")


def wafer_run(seed: int) -> WaferRun:
    """Target 3: a fabless AI-accelerator company with its own 300 mm wafer plant (enough for
    its starts) from January 2015 to December 2025, against a twin without one."""
    from tst.sim.chips import chips

    lg = loaded()
    b, d = lg.balance, lg.game_data
    out: dict[bool, list[tuple[float, float, float, int]]] = {}
    from tst.balance import m12b

    for own in (True, False):
        game, pid = chip_game(seed, (2015, 1), months=12)
        wafer = next(c for c in game.state.production_contracts if c.product_id == pid)
        if own:
            build(game, "wafer_plant", "east_asia", 120_000)
        rows = []
        while game.state.turn <= ym_to_turn(2025, 12):
            if game.state.turn % 12 == 0 and game.state.turn > ym_to_turn(2015, 1):
                price = chips.index_wafer_cents(game.state, "mobile_soc", b, d, "tsmc")
                game.state = m12b.contract(
                    game.state, pid, "wafer", wafer.units, price, game.state.turn, 12
                )  # a fabless company signs its wafers a year at a time
                game.state = _renew_assembly(game.state)
            play(game)
            state = replace(game.state, turn=game.state.turn - 1)  # the month just played
            contracts = chips.wafer_contracts(state, pid)
            starts = sum(c.units for c in contracts)
            delivered = sum(chips.wafers_delivered(state, c, b, d) for c in contracts)
            vol, price, market = chips.own_wafers(state, pid)
            share = vol / starts if starts else 0.0
            saving = 1 - price / market if vol > 0 and market > 0 else float("nan")
            rows.append((share, saving, delivered / starts if starts else 0.0, state.turn))
        out[own] = rows
    lo, hi = ym_to_turn(2021, 1), ym_to_turn(2022, 12)
    return WaferRun(
        seed=seed,
        own_share=tuple(r[0] for r in out[True]),
        saving=tuple(r[1] for r in out[True] if r[1] == r[1]),
        shortage_delivered=tuple(r[2] for r in out[True] if lo <= r[3] <= hi),
        spot_shortage_delivered=tuple(r[2] for r in out[False] if lo <= r[3] <= hi),
    )


def _renew_assembly(state: GameState) -> GameState:
    """The device's contract-manufacturing contract runs on with the wafers."""
    out = state
    for c in state.production_contracts:
        if c.kind == "assembly" and c.end_turn < state.turn + 12:
            from tst.balance import m12b

            out = m12b.with_production_contract(out, replace(c, end_turn=state.turn + 12))
    return out


# --- Power (target 2) ------------------------------------------------------------------------


@dataclass(frozen=True)
class PowerRun:
    cheapest: str
    cheap_unit: float  # mean unit cost 2015-2025, cents a tonne
    europe_unit: float

    @property
    def saving(self) -> float:
        return 1 - self.cheap_unit / self.europe_unit


def cheapest_power_region(turn: int) -> str:
    from tst.sim.commodities import power

    lg = loaded()
    game = game_at(1, turn)
    return min(lg.game_data.region_keys, key=lambda r: power.index(game.state, r, lg.game_data))


def power_run(seed: int = 1) -> PowerRun:
    region = cheapest_power_region(ym_to_turn(2015, 1))
    cheap = run_plant("silicon_smelter", region, (2015, 1), (2025, 12), seed)
    europe = run_plant("silicon_smelter", "europe", (2015, 1), (2025, 12), seed)
    return PowerRun(region, st.mean(cheap.units), st.mean(europe.units))


# --- Margins (target 1) ----------------------------------------------------------------------


def margin_runs(seed: int = 1) -> dict[str, PlantRun]:
    """Target 1: each recipe's plant in North America (power 1.0), live from January 2015, its
    input bought at spot, measured once its ramp is done, through December 2025. A by-product
    line stands on a silicon smelter."""
    out: dict[str, PlantRun] = {}
    for recipe in loaded().balance.refining.order:
        if recipe.startswith("byproduct_"):
            out[recipe] = _byproduct_run(recipe, seed)
        else:
            out[recipe] = run_plant(recipe, "north_america", (2015, 1), (2025, 12), seed)
    return out


def _byproduct_run(recipe: str, seed: int) -> PlantRun:
    b = loaded().balance
    game = game_at(seed, ym_to_turn(2015, 1) - 1)
    host = build(game, "silicon_smelter", "north_america", 10_000)
    fid = build(game, recipe, "north_america", 25, host_id=host)
    margins: list[float] = []
    units: list[float] = []
    markets: list[float] = []
    ramp = b.refining.recipes[recipe].ramp_months
    while game.state.turn <= ym_to_turn(2025, 12):
        play(game)
        ref = refinery_of(game.state, fid)
        assert ref is not None and ref.month is not None
        if ref.month.turn - ym_to_turn(2015, 1) + 1 < ramp or ref.month.margin is None:
            continue
        margins.append(ref.month.margin)
        units.append(ref.month.unit_cost_cents)
        markets.append(ref.month.market_cents)
    return PlantRun(recipe, "north_america", tuple(margins), tuple(units), tuple(markets))
