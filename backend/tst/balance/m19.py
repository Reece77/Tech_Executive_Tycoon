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
from tst.sim.mining.models import Mine, MineMonth
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
        default_factory=lambda: {
            "accident": "investigate",
            "takeover": "partner",
            "crash": "keep",
            "protest": "benefit",
        }
    )
    log: Counter[str] = field(default_factory=Counter)
    posted: list[LedgerEntry] = field(default_factory=list)
    events: list[tuple[int, str, int]] = field(default_factory=list)  # (turn, kind, mine)
    months: dict[int, list[MineMonth]] = field(default_factory=dict)  # every mine's months

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
        for m in self.state.mines:
            if m.history and m.history[-1].turn == self.state.turn:
                self.months.setdefault(m.id, []).append(m.history[-1])
        self._answer()

    def _answer(self) -> None:
        b, d = self.loaded.balance, self.loaded.game_data
        for m in sorted(self.state.mines, key=lambda m: m.id):
            for when, template, kind in (
                (m.accident_turn, "mine_fatal_accident", "accident"),
                (m.takeover_turn, TAKEOVER_TEMPLATE, "takeover"),
                (m.crash_turn, "mine_price_crash", "crash"),
                (m.protest_turn, "mine_protest", "protest"),
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


# --- 35.6: the targets, printed -----------------------------------------------------------------

COMMODITIES: Final = ("copper", "lithium_carbonate", "cobalt", "ndpr_oxide")
RISKY: Final = ("africa", "latin_america")  # the two regions of highest resource nationalism
T4_FROM, T4_TO = 192, 359  # January 2026 - December 2039
T5_FROM, T5_TO = 132, 179  # January 2021 - December 2024
T5_BUILD = 48  # January 2014: producing well before 2021
T5_MARGIN = 0.1  # cost plus 10%


def _one(args: tuple[int, str]) -> list[MineResult]:
    from tst.config import Settings
    from tst.loader import load_all

    seed, commodity_key = args
    return mines_for(load_all(Settings().data_dir), seed, commodity_key, 3)


def returns(seeds: tuple[int, ...], jobs: int) -> list[MineResult]:
    """Targets 1-2: every seed's mines on positive-NPV definitive studies (35.6)."""
    jobs_list = [(s, c) for s in seeds for c in COMMODITIES]
    if jobs <= 1:
        return [r for j in jobs_list for r in _one(j)]
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(jobs) as ex:
        return [r for rs in ex.map(_one, jobs_list) for r in rs]


def accident_rates(loaded: LoadedData) -> dict[str, float]:
    """Target 3: the chance a mine-year at average safety (a full crew of skill 10, normal
    spend) by subtype, and skill 15's rate over skill 8's."""
    from tst.sim.mining import formulas as mf

    mb = loaded.balance.mining
    ab = mb.accident
    out = {
        k: mf.accident_chance(v.accident_base, 10.0, 1.0, "normal", ab) * 12
        for k, v in mb.subtypes.items()
    }
    base = mb.subtypes["open_pit"].accident_base
    out["skill15_over_skill8"] = mf.accident_chance(
        base, 15.0, 1.0, "normal", ab
    ) / mf.accident_chance(base, 8.0, 1.0, "normal", ab)
    return out


def risky_hits(loaded: LoadedData, seeds: tuple[int, ...]) -> dict[int, int]:
    """Target 4: per seed, the 2026-2039 events (takeovers or export bans) that hit a lithium
    mine in each of the two highest-risk regions (Africa, Latin America)."""
    from tst.sim.mining.risk import region_events

    out = {}
    for seed in seeds:
        rng = RngFactory(seed)
        n = 0
        for t in range(T4_FROM, T4_TO + 1):
            for e in region_events(rng, t, loaded.balance, loaded.game_data):
                if e.region in RISKY and e.commodity == "lithium_carbonate":
                    n += 1
        out[seed] = n
    return out


@dataclass(frozen=True, slots=True)
class Volatility:
    seed: int
    spot: float
    integrated: float

    @property
    def ratio(self) -> float:
        return self.integrated / self.spot if self.spot else math.nan


def bom_volatility(loaded: LoadedData, seed: int) -> Volatility | None:
    """Target 5: a reference phone's bill of materials (M17's 33.6 target 2: components at
    index 1.0, the device mix at spot) month by month in 2021-2024, against the same phone with
    lithium and cobalt from the group's own mines at cost plus 10% (the mines' cash cost a t
    each month). Volatility: the monthly cost's standard deviation over its mean."""
    from tst.sim.commodities import commodity as cm

    b, d = loaded.balance, loaded.game_data
    run = miner(loaded, seed)
    run.state = replace(run.state, turn=T5_BUILD)
    mines: dict[str, int] = {}
    for key in ("lithium_carbonate", "cobalt"):
        for _ in range(12):
            try:
                p = permitted_project(run, key)
            except LookupError:
                return None
            if (p.npv_mid_cents or 0) > 0:
                break
        if run.act(BuildMine(run.founder, p.id)) is None:
            return None
        mine = run.state.mines[-1]
        from tst.sim.mining import formulas as mf

        uid = add_engineers(run, mf.staff_needed(mine.capacity_t, b.mining.staff_per_kt), 12.0)
        run.act(StaffMine(run.founder, mine.id, uid))
        mines[key] = mine.id
    run_until(run, T5_TO)
    mix = b.commodity.mixes["device_bom"]
    assert d.commodities is not None
    spot_costs: list[float] = []
    own_costs: list[float] = []
    cost_at = {
        k: {m.turn: m.cost_usd_t for m in run.months.get(i, []) if m.output_t > 0}
        for k, i in mines.items()
    }
    for t in range(T5_FROM, T5_TO + 1):
        spot_mix = own_mix = 0.0
        for g, w in mix.weights.items():
            mean = cm.mean_of(d, g)
            idx = cm.price(run.state, g, t, d, b) / mean
            spot_mix += w * idx
            if g in cost_at and t in cost_at[g]:
                usd_mean = mean * d.commodities.good(g).usd_per_unit * per_t_of(d, g)
                own_mix += w * cost_at[g][t] * (1 + T5_MARGIN) / usd_mean
            else:
                own_mix += w * idx
        spot_costs.append((1 - mix.share) + mix.share * spot_mix)
        own_costs.append((1 - mix.share) + mix.share * own_mix)
    return Volatility(seed, _cv(spot_costs), _cv(own_costs))


def per_t_of(d: object, g: str) -> float:
    from tst.sim.mining.prices import per_t

    assert hasattr(d, "commodities")
    return per_t(d.commodities.good(g).volume_unit)


def _cv(xs: list[float]) -> float:
    m = statistics.fmean(xs)
    return statistics.pstdev(xs) / m if m else math.nan


def unchanged(loaded: LoadedData, seeds: tuple[int, ...], turns: int = 24) -> bool:
    """Target 6: a company that never mines plays exactly as before: the same game with the
    mining phases and with them replaced by no-ops, identical month ends."""
    import tst.sim.turn as turn_module
    from tst.sim.mining import phase as real

    class _Off:
        @staticmethod
        def build_month(state: GameState, *_: object) -> tuple[GameState, tuple[()], tuple[()]]:
            return state, (), ()

        operate_month = build_month

    for seed in seeds:
        runs = []
        for off in (False, True):
            setattr(turn_module, "mining", _Off if off else real)  # noqa: B010
            try:
                game = start_game(loaded, seed)
                for _ in range(turns):
                    game.turn()
                runs.append(game.snapshots)
            finally:
                setattr(turn_module, "mining", real)  # noqa: B010
        if runs[0] != runs[1]:
            return False
    return True


@dataclass(frozen=True)
class Results:
    seeds: tuple[int, ...]
    mines: list[MineResult]
    accidents: dict[str, float]
    hits: dict[int, int]
    hits_more: dict[int, int]
    volatility: list[Volatility]
    unchanged: bool


def run_all(seeds: tuple[int, ...], jobs: int, more: tuple[int, ...] = ()) -> Results:
    from tst.config import Settings
    from tst.loader import load_all

    loaded = load_all(Settings().data_dir)
    vols = [v for s in seeds if (v := bom_volatility(loaded, s)) is not None]
    return Results(
        seeds,
        returns(seeds, jobs),
        accident_rates(loaded),
        risky_hits(loaded, seeds),
        risky_hits(loaded, more),
        vols,
        unchanged(loaded, seeds[:2]),
    )


def summary(r: Results) -> dict[str, float]:
    irrs = [x.irr if x.irr is not None else -1.0 for x in r.mines]
    copper = [x for x in r.mines if x.aisc_usd_lb is not None]
    aisc = sorted(x.aisc_usd_lb for x in copper if x.aisc_usd_lb is not None)
    q1 = aisc[len(aisc) // 4] if aisc else math.nan
    by_grade = sorted(copper, key=lambda x: x.grade_ratio)
    top = by_grade[-max(1, len(by_grade) // 4) :]
    top_aisc = median([x.aisc_usd_lb for x in top if x.aisc_usd_lb is not None])
    return {
        "mines": len(r.mines),
        "median_irr": median(irrs),
        "below_5pct": sum(1 for i in irrs if i < 0.05) / len(irrs) if irrs else math.nan,
        "copper_mines": len(copper),
        "copper_aisc_median": median(aisc),
        "copper_aisc_q1": q1,
        "high_grade_aisc_median": top_aisc,
        "seeds_hit": sum(1 for n in r.hits.values() if n > 0),
        "share_hit_more": (
            sum(1 for n in r.hits_more.values() if n > 0) / len(r.hits_more)
            if r.hits_more
            else math.nan
        ),
        "vol_ratio_max": max((v.ratio for v in r.volatility), default=math.nan),
        "vol_ratio_median": median([v.ratio for v in r.volatility]),
    }


def report(r: Results) -> str:
    s = summary(r)
    a = r.accidents
    lines = [
        f"M19 35.6 targets, seeds {r.seeds[0]}-{r.seeds[-1]}",
        f"T1 mines are good bets on average, bad ones often: {s['mines']:.0f} mines; median IRR "
        f"{s['median_irr']:.1%} (10-20%); {s['below_5pct']:.0%} below 5% (>= 25%)",
        f"T2 copper costs: {s['copper_mines']:.0f} mines; median AISC "
        f"${s['copper_aisc_median']:.2f}/lb "
        f"(1.5-3.0); the highest-grade quartile's median ${s['high_grade_aisc_median']:.2f}/lb, "
        f"the bottom quartile below ${s['copper_aisc_q1']:.2f}/lb",
        "T3 accidents a mine-year at average safety: "
        + ", ".join(f"{k} {v:.2%}" for k, v in a.items() if k != "skill15_over_skill8")
        + f" (0.1-0.5%); skill 15 / skill 8 = {a['skill15_over_skill8']:.2f} (<= 0.60)",
        f"T4 a takeover or export ban hits the lithium mines in Africa and Latin America in "
        f"2026-2039 on {s['seeds_hit']:.0f} of {len(r.hits)} seeds (3-7)"
        + (
            f"; {s['share_hit_more']:.0%} of seeds {min(r.hits_more)}-{max(r.hits_more)}"
            if r.hits_more
            else ""
        ),
        f"T5 BOM-cost volatility 2021-2024, integrated / spot: median {s['vol_ratio_median']:.2f}, "
        f"at most {s['vol_ratio_max']:.2f} on {len(r.volatility)} seeds (<= 0.50)",
        f"T6 a company that never mines plays exactly as before: {r.unchanged} (and the golden "
        "snapshots are unchanged)",
    ]
    return "\n".join(lines)
