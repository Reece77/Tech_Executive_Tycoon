"""M19's balance harness and 35.6 targets (docs/formulas.md 35.6; tools/m19_targets.py).

`Miner` runs the months that matter to a mine in memory: M17's commodity and power months
(phase 4's first step), the mining phases (35.2-35.5), and the answers to mine events. A mine
is built on a permitted project made by M18's own functions (survey, sampling, 40 holes, an
estimate and a definitive study), so its deposit and study are what a player would have.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Final

from tst.balance import m18
from tst.balance.game import start_game
from tst.loader import LoadedData
from tst.sim.actions import Action, ActionResult, apply_action
from tst.sim.commodities import commodity
from tst.sim.errors import SimError
from tst.sim.events.models import GameEvent
from tst.sim.exploration import pipeline as xp
from tst.sim.exploration.models import Project
from tst.sim.exploration.pipeline import TakeLicence
from tst.sim.facilities import goods
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry, apply_entries
from tst.sim.mining import phase as mp
from tst.sim.mining.actions import BuildMine, StaffMine
from tst.sim.mining.models import Mine
from tst.sim.mining.risk import TAKEOVER_TEMPLATE, mining_step
from tst.sim.org.models import OrgUnit
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    reach_stage,
    with_company,
    with_employment,
    with_person,
    with_person_state,
    with_unit,
)

PLAYER: Final = 1
CASH_CENTS: Final = 2_000_000_000_000  # $20B: never short in a balance run
ENERGY: Final = 100
HOLES: Final = 40


@dataclass
class Miner:
    loaded: LoadedData
    state: GameState
    balances: dict[tuple[int, str], int]
    seq: int = 0
    answers: dict[str, str] = field(
        default_factory=lambda: {"accident": "investigate", "takeover": "partner", "crash": "keep"}
    )
    log: Counter[str] = field(default_factory=Counter)
    posted: list[LedgerEntry] = field(default_factory=list)
    events: list[tuple[int, str, int]] = field(default_factory=list)  # (turn, kind, mine)

    @property
    def founder(self) -> int:
        f = self.state.founder_of(PLAYER)
        assert f is not None
        return f.id

    @property
    def rng(self) -> RngFactory:
        return RngFactory(self.state.save_meta.master_seed)

    def act(self, action: Action) -> ActionResult | None:
        self.seq += 1
        ps = self.state.person_state(self.founder)
        self.state = with_person_state(self.state, replace(ps, energy=ENERGY))
        try:
            out = apply_action(
                self.state,
                action,
                self.rng,
                self.loaded.balance,
                self.loaded.game_data,
                self.balances,
                seq=self.seq,
            )
        except SimError as exc:
            self.log[f"refused {action.kind}: {exc}"] += 1
            return None
        self._post(out.new_state, out.ledger_entries)
        return out

    def _post(self, state: GameState, entries: tuple[LedgerEntry, ...]) -> None:
        self.state = state
        self.balances = apply_entries(self.balances, entries)
        self.posted += entries

    def month(self) -> None:
        """One month: the turn moves on, then phase 4's commodity months and the mines'
        months, then the answers to any mine event (the event's month is the next one)."""
        b, d = self.loaded.balance, self.loaded.game_data
        state = replace(self.state, turn=self.state.turn + 1)
        extra = commodity.months(state, self.rng, b, d)
        state = goods.supply_phase(state, self.rng, b, d)
        state = replace(state, supply=state.supply + extra)
        state, e1, _ = mp.build_month(state, self.rng, b, d)
        self._post(state, e1)
        state, e2, _ = mp.operate_month(self.state, self.rng, b, d)
        self._post(state, e2)
        self._answer()

    def _answer(self) -> None:
        b, d = self.loaded.balance, self.loaded.game_data
        for m in sorted(self.state.mines, key=lambda m: m.id):
            for when, template, kind in (
                (m.accident_turn, "mine_fatal_accident", "accident"),
                (m.takeover_turn, TAKEOVER_TEMPLATE, "takeover"),
                (m.crash_turn, "mine_price_crash", "crash"),
            ):
                if when is None:
                    continue
                self.events.append((when, kind, m.id))
                event = GameEvent(
                    id=0,
                    company_id=PLAYER,
                    turn=when,
                    template_id=template,
                    category="mining",
                    severity="critical",
                    trigger="mining",
                    strength=1.0,
                )
                nxt = replace(self.state, turn=when)
                state, posted, _ = mining_step(nxt, event, self.answers[kind], b, d)
                self._post(replace(state, turn=self.state.turn), tuple(posted))


# --- Fixtures ------------------------------------------------------------------------------------


def miner(loaded: LoadedData, seed: int, cash: int = CASH_CENTS) -> Miner:
    """A new game's player at stage 3 with `cash` more in the bank and three geologists."""
    game = start_game(loaded, seed)
    state = with_company(game.state, reach_stage(game.state.player, 3, 0))
    state = m18.add_geologists(state, loaded, 12.0, 3)
    balances = dict(game.balances)
    balances[(PLAYER, CASH)] = balances.get((PLAYER, CASH), 0) + cash
    balances[(PLAYER, COMMON_EQUITY)] = balances.get((PLAYER, COMMON_EQUITY), 0) - cash
    return Miner(loaded, state, balances)


def free_deposit(
    state: GameState, commodity_key: str, region: str | None = None
) -> tuple[str, int]:
    for blk in state.geo_blocks:
        if (
            blk.true_commodity == commodity_key
            and (region is None or blk.region == region)
            and xp.holder_of(state, blk.region, blk.index) is None
        ):
            return blk.region, blk.index
    raise LookupError(f"no free {commodity_key} deposit")


def permitted_project(run: Miner, commodity_key: str, region: str | None = None) -> Project:
    """A licence on a block holding the commodity, taken to a definitive study and a permit
    by M18's own functions (only the months between are skipped)."""
    b, d = run.loaded.balance, run.loaded.game_data
    r, block = free_deposit(run.state, commodity_key, region)
    out = run.act(TakeLicence(run.founder, r, block))
    assert out is not None, run.log
    p = run.state.projects[-1]
    blk = next(x for x in run.state.geo_blocks if x.region == r and x.index == block)
    p = replace(p, commodity=commodity_key, reading="strong", kind=blk.true_kind or "hard_rock")
    rng = run.rng
    p = xp.sample_result(run.state, p, rng, b, d)
    run.state = xp.with_project(run.state, p)
    holes = tuple(xp.drill_hole(run.state, p, n, rng, b, d) for n in range(1, HOLES + 1))
    run.state = replace(run.state, holes=(*run.state.holes, *holes))
    p = xp.estimate_result(run.state, p, rng, b, d)
    p = xp.study_result(run.state, p, "definitive", rng, b, d)
    t = run.state.turn
    p = replace(p, status="permitted", permit_start=t, hidden_due_turn=t, permit_turn=t)
    run.state = xp.with_project(run.state, p)
    return p


def add_engineers(run: Miner, n: int, skill: float, company_id: int = PLAYER) -> int:
    """A unit of `n` mining engineers whose mining engineering and operations are `skill`;
    returns the unit's id."""
    loaded = run.loaded
    role = loaded.game_data.role("mining_engineer")
    state = run.state
    uid, ids = state.next_ids.take("unit")
    state = replace(state, next_ids=ids)
    state = with_unit(
        state, OrgUnit(uid, company_id, "team", f"Mine crew {uid}", None, None, None, state.turn)
    )
    rng = RngFactory(state.save_meta.master_seed)
    for i in range(n):
        pid, ids = state.next_ids.take("person")
        eid, ids = ids.take("employment")
        state = replace(state, next_ids=ids)
        person = generate_person(
            rng.stream(0, "misc", 400 + uid * 50 + i),
            loaded.game_data,
            loaded.balance,
            state.turn,
            role,
            "senior",
            "oceania",
            person_id=pid,
        )
        person = replace(
            person,
            skills=person.skills.updated({"mining_engineering": skill, "operations": skill}),
        )
        state = with_person(state, person)
        state = with_employment(
            state,
            Employment(
                eid,
                pid,
                company_id,
                role.key,
                "senior",
                11_000_000,
                0,
                state.turn,
                None,
                "active",
                unit_id=uid,
            ),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=65.0))
    run.state = state
    return uid


def build(run: Miner, commodity_key: str, region: str | None = None, skill: float = 12.0) -> Mine:
    """A permitted project, a mine at its design capacity, and a full crew at `skill`."""
    p = permitted_project(run, commodity_key, region)
    out = run.act(BuildMine(run.founder, p.id))
    assert out is not None, run.log
    mine = run.state.mines[-1]
    from tst.sim.mining import formulas as mf

    need = mf.staff_needed(mine.capacity_t, run.loaded.balance.mining.staff_per_kt)
    uid = add_engineers(run, need, skill)
    assert run.act(StaffMine(run.founder, mine.id, uid)) is not None, run.log
    return run.state.mines[-1]


def run_until(run: Miner, turn: int, stop: Callable[[Miner], bool] | None = None) -> None:
    while run.state.turn < turn:
        run.month()
        if stop is not None and stop(run):
            return


def mine_of(run: Miner, mine_id: int) -> Mine:
    m = run.state.mine(mine_id)
    assert m is not None
    return m


def median(xs: list[float]) -> float:
    return statistics.median(xs) if xs else math.nan


# --- 35.6 targets 1 and 2: mines' returns and copper costs --------------------------------------

BUILD_YEARS: Final = 9  # mines are built in January of 2012-2020, by seed: some at price peaks
FIRST_BUILD: Final = 24  # January 2012
END_TURN: Final = 480  # December 2049 at most: a mine's whole life


@dataclass(frozen=True, slots=True)
class MineResult:
    seed: int
    commodity: str
    mine_id: int
    npv_mid_cents: int
    irr: float | None
    aisc_usd_lb: float | None  # copper: the life's median all-in sustaining cost a pound
    grade_ratio: float  # true grade / the commodity's median grade
    life_months: int


def build_turn(seed: int) -> int:
    return FIRST_BUILD + (seed % BUILD_YEARS) * 12


def _mine_flows(run: Miner, mine: Mine, data_names: str) -> list[float]:
    """Yearly cash flows of one mine (its entries carry its name): capex, margins,
    royalties, fines, reclamation."""
    years: dict[int, float] = {}
    for e in run.posted:
        if data_names not in e.memo:
            continue
        cash = sum(x.amount for x in e.lines if x.account == CASH)
        y = (e.turn - mine.ordered_turn) // 12
        years[y] = years.get(y, 0.0) + cash
    if not years:
        return []
    return [years.get(y, 0.0) for y in range(max(years) + 1)]


def mines_for(loaded: LoadedData, seed: int, commodity_key: str, n: int) -> list[MineResult]:
    """Up to `n` mines on this seed's deposits of the commodity whose definitive study's NPV
    midpoint is positive (what a sensible player builds), run to the end of their lives."""
    from tst.sim.mining.actions import mine_name

    run = miner(loaded, seed)
    run.state = replace(run.state, turn=build_turn(seed))
    built: list[tuple[Mine, int]] = []
    tried = 0
    while len(built) < n and tried < n * 10:
        tried += 1
        try:
            p = permitted_project(run, commodity_key)
        except LookupError:
            break
        if (p.npv_mid_cents or 0) <= 0:
            continue  # kept (held): the next deposit is another block
        if run.act(BuildMine(run.founder, p.id)) is None:
            continue
        mine = run.state.mines[-1]
        from tst.sim.mining import formulas as mf

        need = mf.staff_needed(mine.capacity_t, loaded.balance.mining.staff_per_kt)
        uid = add_engineers(run, need, 12.0)
        run.act(StaffMine(run.founder, mine.id, uid))
        built.append((mine, p.npv_mid_cents or 0))
    run_until(run, END_TURN, lambda r: all(not m.is_open for m in r.state.mines))
    d = loaded.game_data
    assert d.geology is not None
    results: list[MineResult] = []
    for mine, npv in built:
        final = mine_of(run, mine.id)
        flows = _mine_flows(run, final, f"{mine_name(final, d)}")
        aisc = _life_aisc(run, final)
        results.append(
            MineResult(
                seed,
                commodity_key,
                mine.id,
                npv,
                _irr(flows),
                aisc,
                final.hidden_grade / d.geology.commodity(commodity_key).grade_median,
                (final.closed_turn or run.state.turn) - final.ready_turn,
            )
        )
    return results


def _irr(flows: list[float]) -> float | None:
    from tst.sim.mining import formulas as mf

    return mf.project_irr(flows)


def _life_aisc(run: Miner, mine: Mine) -> float | None:
    """The life's all-in sustaining cost a pound: cash costs and royalties over output."""
    from tst.sim.mining import formulas as mf

    tracked = [m for m in mine.history if m.output_t > 0]
    if mine.commodity != "copper" or not tracked:
        return None
    return mf.usd_per_lb(statistics.median(m.cost_usd_t for m in tracked))
