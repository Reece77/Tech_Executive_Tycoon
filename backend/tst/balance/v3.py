"""M23b's v3 balance targets (docs/tasks/M23b-v3-balance.md), printed by tools/v3_targets.py and
checked weekly (tests/balance/test_v3_balance.py, .github/workflows/weekly.yml). True values
are read here; this is a tool.

- **Integration pays modestly** (I1-I3): the v2 founder-played strategies and the three v3
  scripts (tst.balance.strategies_v3) played for 20 years on 10 seeds. full_integrator's group
  operating margin over year 20 is 3-10 points above steady_regions', its ARR 0.9-1.4x, and it
  wins at most 4 of 10 seeds by founder value at year 20.
- **Chains feel shocks** (S1, S2): the 2021-2022 lithium spike raises an unhedged device
  maker's unit cost visibly (M17's reference phone, at least 3%); the December 2024 gallium
  ban limits an unhedged chip maker's **output** through allocation (playtest 5), not only its
  price.
- **Foundry demand** (F1): the foundry script's 28 nm fab reaches 70%+ use within 3 years of
  going live on 7 of 10 seeds.
- **30 years across the chain** (L1-L4): full_integrator, mineral_baron and foundry to December
  2039 on 10 seeds: at least one era arrival in 2026-2039 in every domain with an era
  scheduled after 2025; rival miners, refiners and foundries alive in every chain category in
  December 2039; every commodity's index inside its band (no 36-month run above 3.0 or below
  1/3, M17's 33.6 target 5 both ways); the full integrator's chain built (the rungs' months).
- **Long bets** (35.6, 38.5) are M19's and M21's own runs on the combined code
  (tools/m19_targets.py, tools/m21_targets.py), and V6 extended is
  tests/integration/test_v6_perf.py on a 2039 full_integrator save (tools/v6_save.py).
"""

from __future__ import annotations

import math
import os
import statistics as st
import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path
from typing import Final

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.report import SCENARIO, Row
from tst.balance.strategies_v2 import DELEGATED, PLAYABLE
from tst.balance.strategies_v3 import V3, V3_ARMS
from tst.loader import LoadedData, load_all
from tst.sim.calendar import turn_to_ym, ym_to_turn
from tst.sim.state import GameState

DATA: Final = Path(__file__).resolve().parents[2] / "data"
SEEDS: Final = tuple(range(1, 11))
ALL: Final = {**PLAYABLE, **V3, **V3_ARMS}
YEARS_20: Final = ym_to_turn(2029, 12) + 1  # 240: January 2010 to December 2029
LONG_TURNS: Final = ym_to_turn(2039, 12) + 1  # 360
BASE: Final = "steady_regions"
INTEGRATOR: Final = "full_integrator"
# The strategies whose wins I3 counts at year 20: the v2 founder-played scripts (V1's, less
# v1's four, which do not reach year 20 as companies worth comparing: M23b decision) and the
# three v3 scripts.
COMPARED: Final = (
    "steady_regions",
    "research_heavy",
    "acquirer",
    "integrator",
    "full_integrator",
    "mineral_baron",
    "foundry",
)
DEVICES: Final = "devices_regions"  # the like-for-like baseline (I1d, I2d), not counted in I3
PLAYED_20: Final = (*COMPARED, DEVICES)
LONG_STRATEGIES: Final = tuple(V3)
MARGIN_GAP: Final = (0.03, 0.10)  # I1: full_integrator's margin over steady_regions'
ARR_RATIO: Final = (0.9, 1.4)  # I2
MAX_WINS: Final = 4  # I3
FAB_USE: Final = 0.70  # F1: use within FAB_MONTHS of going live
FAB_MONTHS: Final = 36
FAB_SEEDS: Final = 7  # F1: of 10
FAB_NODE: Final = "n28"
LITHIUM_RISE: Final = 0.03  # S1: the reference phone's peak unit cost rise, at least
GALLIUM_CUT: Final = 0.05  # S2: output below its pre-ban level by at least this in the ban
ERA_FROM: Final = ym_to_turn(2026, 1)
BAND: Final = (1 / 3, 3.0)  # L3: a commodity's index band
BAND_MONTHS: Final = 36  # L3: longest run outside it


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


def _in(value: float | None, band: tuple[float, float]) -> bool:
    return value is not None and band[0] <= value <= band[1]


# --- One run ----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FabTrace:
    node: str
    live_turn: int
    use: tuple[float, ...]  # run / available each month from going live


@dataclass(frozen=True, slots=True)
class V3Run:
    strategy: str
    seed: int
    turns: int
    ended_turn: int | None
    value: int  # founder value at the last month end, cents
    revenue_year: int  # the group's last 12 months, cents (intercompany eliminated)
    operating_year: int
    revenue_month: int  # the group's last month
    rungs: dict[str, int]  # rung -> the month it was reached (strategies_v3._mark)
    fabs: tuple[FabTrace, ...]
    mines: int
    seconds: float
    # 30-year runs only (empty otherwise)
    eras: dict[str, int] = field(default_factory=dict)  # domain -> arrivals from 2026
    chain_alive: dict[str, int] = field(default_factory=dict)  # chain category -> rivals alive
    band_runs: dict[str, int] = field(default_factory=dict)  # good -> longest run outside BAND

    @property
    def margin(self) -> float | None:
        return self.operating_year / self.revenue_year if self.revenue_year > 0 else None

    @property
    def arr(self) -> int:
        """12 x the group's last month's revenue (M23b decision: a group's revenue includes
        units, mine sales and foundry slots, which the MRR-based ARR leaves out)."""
        return 12 * self.revenue_month


def _fab_traces(state: GameState) -> tuple[FabTrace, ...]:
    out = []
    for fab in state.fabs:
        if fab.company_id != PLAYER:
            continue
        # history rows: (turn, yield, use, cost a start, market price)
        rows = [h for h in fab.history if h[0] >= fab.live_turn]
        out.append(FabTrace(fab.node, fab.live_turn, tuple(h[2] for h in rows)))
    return tuple(out)


def play(job: tuple[str, int, int]) -> V3Run:
    strategy, seed, turns = job
    started = time.perf_counter()
    game = start_game(loaded(), seed, SCENARIO)
    script = ALL[strategy]
    long = turns >= LONG_TURNS
    bands: dict[str, list[float]] = {}
    while game.state.turn < turns and not game.state.ended:
        script(game)
        game.turn()
        if long and game.state.turn - 1 >= ERA_FROM:
            _indices(game, bands)
    return _result(game, strategy, seed, turns, started, bands if long else None)


def _indices(game: Game, bands: dict[str, list[float]]) -> None:
    from tst.sim.commodities import commodity

    d = game.loaded.game_data
    if d.commodities is None:
        return
    state = replace(game.state, turn=game.state.turn - 1)  # the month just played
    for good in d.commodities.goods:
        bands.setdefault(good.key, []).append(commodity.index_now(state, good.key, d))


def _longest_outside(xs: Sequence[float]) -> int:
    best = run = 0
    for x in xs:
        run = run + 1 if not BAND[0] <= x <= BAND[1] else 0
        best = max(best, run)
    return best


def _result(
    game: Game,
    strategy: str,
    seed: int,
    turns: int,
    started: float,
    bands: dict[str, list[float]] | None,
) -> V3Run:
    state = game.state
    last = max(game.group_pnl) if game.group_pnl else 0
    year = [game.group_pnl[t] for t in range(last - 11, last + 1) if t in game.group_pnl]
    value = game.founder_value.get(max(game.founder_value), 0) if game.founder_value else 0
    run = V3Run(
        strategy=strategy,
        seed=seed,
        turns=turns,
        ended_turn=state.save_meta.ended_turn,
        value=value,
        revenue_year=sum(r for r, _ in year),
        operating_year=sum(o for _, o in year),
        revenue_month=game.group_pnl.get(last, (0, 0))[0],
        rungs={k.removeprefix("rung:"): v for k, v in game.notes.items() if k.startswith("rung:")},
        fabs=_fab_traces(state),
        mines=sum(1 for m in state.mines if m.status != "closed"),
        seconds=time.perf_counter() - started,
    )
    if bands is None:
        return run
    return replace(
        run,
        eras=era_domains(state),
        chain_alive=chain_rivals(state),
        band_runs={g: _longest_outside(xs) for g, xs in bands.items()},
    )


def run_all(
    strategies: Sequence[str], seeds: Sequence[int], turns: int, jobs: int = 1
) -> list[V3Run]:
    plan = [(s, seed, turns) for s in strategies for seed in seeds]
    if jobs <= 1:
        return [play(j) for j in plan]
    with ProcessPoolExecutor(jobs) as pool:
        return list(pool.map(play, plan))


# --- The 30-year chain measures ----------------------------------------------------------------


def era_domains(state: GameState) -> dict[str, int]:
    """Era arrivals from January 2026 by domain."""
    d = loaded().game_data
    domain = {e.key: e.domain for e in d.eras.eras}
    out: dict[str, int] = {}
    for a in state.era_arrivals:
        if a.turn >= ERA_FROM and a.key in domain:
            out[domain[a.key]] = out.get(domain[a.key], 0) + 1
    return out


def future_domains() -> tuple[str, ...]:
    """The domains with an era scheduled after 2025 (a window, not a historical arrival):
    L1 asks each of them for an arrival. Domains without one are printed (M23b decision)."""
    d = loaded().game_data
    out = []
    for e in d.eras.eras:
        if e.window is not None and e.domain not in out:
            out.append(e.domain)
    return tuple(out)


def chain_categories() -> dict[str, tuple[str, ...]]:
    """Chain category -> its goods: miners (the explored commodities), refiners (the refining
    recipes' outputs) and foundries (one category)."""
    lg = loaded()
    b, d = lg.balance, lg.game_data
    mined = tuple(c.key for c in d.geology.commodities) if d.geology else ()
    refined = tuple(sorted({r.output_good for r in b.refining.recipes.values()}))
    return {
        **{f"miners:{g}": (g,) for g in mined},
        **{f"refiners:{g}": (g,) for g in refined},
        "foundries": ("wafer_starts",),
    }


def chain_rivals(state: GameState) -> dict[str, int]:
    """Rivals still producing in each chain category this month: rival miners with output
    (35.5's abstract capacity), suppliers of each refined good still signing (33.4) or, for a
    good M20 derives with no named seller, its spot market still allocating, and rival
    foundries with capacity (38.3)."""
    from tst.sim.fabs import market as fm
    from tst.sim.fabs import nodes as nd
    from tst.sim.mining.risk import rival_capacity
    from tst.sim.refining import goods as rg
    from tst.sim.rng import RngFactory

    lg = loaded()
    b, d = lg.balance, lg.game_data
    turn = state.turn
    out: dict[str, int] = {}
    miners = rival_capacity(RngFactory(state.save_meta.master_seed), turn, state, b, d)
    for key, goods in chain_categories().items():
        kind = key.split(":")[0]
        if kind == "miners":
            out[key] = len(
                {r.supplier for r in miners if r.commodity in goods and r.output_share > 0}
            )
        elif kind == "refiners":
            suppliers = d.suppliers.suppliers if d.suppliers else ()
            named = sum(1 for s in suppliers if any(s.sells(g, turn) for g in goods))
            # a good M20 derives (300 mm wafers, solar polysilicon: refining.goods) has no
            # named seller: its rival supply is the abstract market, alive while a spot
            # buyer is allocated any of it (M23b decision)
            derived = any(
                g in b.refining.goods and rg.allocation(state, g, b, d) > 0 for g in goods
            )
            out[key] = named or int(derived)
        else:
            tl = fm.timeline(state, b, d)
            foundries = d.nodes.foundries if d.nodes else ()
            out[key] = sum(1 for f in foundries if nd.capacity(tl, f, turn, b.fab) > 0)
    return out


# --- Chains feel shocks (S1, S2) --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GalliumRun:
    seed: int
    before_output: float  # the chips' allocation share, January-November 2024 mean
    ban_output: float  # the lowest month, December 2024 to December 2025
    before_cost: float  # the chip's unit cost, cents, January-November 2024 mean
    ban_cost: float  # the highest month in the ban

    @property
    def cut(self) -> float:
        return 1 - self.ban_output / self.before_output if self.before_output else math.nan

    @property
    def rise(self) -> float:
        return self.ban_cost / self.before_cost - 1 if self.before_cost else math.nan


BAN_TURN: Final = ym_to_turn(2024, 12)


def gallium_run(seed: int) -> GalliumRun:
    """S2: M20's device maker with its own SoC (tst.balance.m20.chip_game: a TSMC foundry
    contract, every chip into its devices, no offtake or own gallium) from January 2024 to
    December 2025: the share of its chips it may make (the foundry-wafer mix's allocation with
    the export controls' cut, which caps a chip product's starts: tst.sim.hardware.production),
    and the chip's unit cost, before and in the December 2024 gallium ban."""
    from tst.balance import m20
    from tst.sim.chips import chips
    from tst.sim.commodities import costs

    lg = m20.loaded()
    b, d = lg.balance, lg.game_data
    game, pid = m20.chip_game(seed, (2024, 1), months=36)
    rows: list[tuple[int, float, float]] = []
    while game.state.turn <= ym_to_turn(2025, 12):
        m20.play(game)
        state = replace(game.state, turn=game.state.turn - 1)
        use = costs.company_use(state, PLAYER, b, d)
        share = costs.product_allocation(state, PLAYER, b.chips.good, use, b, d)
        product = state.product(pid)
        assert product is not None
        cost = chips.unit_cost_cents(state, product, b, d)
        rows.append((state.turn, share, cost))
    before = [r for r in rows if r[0] < BAN_TURN]
    during = [r for r in rows if r[0] >= BAN_TURN]
    return GalliumRun(
        seed=seed,
        before_output=st.fmean(r[1] for r in before),
        ban_output=min(r[1] for r in during),
        before_cost=st.fmean(r[2] for r in before),
        ban_cost=max(r[2] for r in during),
    )


def lithium_rise() -> float:
    """S1: M17's reference phone (33.6 target 2): its peak unit cost in 2021-2022 against
    2020, all at spot (unhedged)."""
    from tst.balance import m17

    return m17.target_2().rise


# --- Rows -------------------------------------------------------------------------------------


def _runs(runs: Sequence[V3Run], strategy: str) -> list[V3Run]:
    return [r for r in runs if r.strategy == strategy]


def _median(xs: Sequence[float]) -> float | None:
    return st.median(xs) if xs else None


def _gap_and_ratio(runs: Sequence[V3Run], base_name: str) -> tuple[float | None, float | None]:
    base, top = _runs(runs, base_name), _runs(runs, INTEGRATOR)
    m_base = _median([m for r in base if (m := r.margin) is not None])
    m_top = _median([m for r in top if (m := r.margin) is not None])
    gap = m_top - m_base if m_top is not None and m_base is not None else None
    a_base = _median([r.arr for r in base])
    a_top = _median([r.arr for r in top])
    ratio = a_top / a_base if a_top is not None and a_base else None
    return gap, ratio


def _gap_rows(runs: Sequence[V3Run], base_name: str, suffix: str) -> list[Row]:
    gap, ratio = _gap_and_ratio(runs, base_name)
    return [
        Row(
            f"I1{suffix}",
            f"full_integrator margin - {base_name}, year 20 (points)",
            "-" if gap is None else f"{gap * 100:+.1f}",
            "+3 to +10",
            _in(gap, MARGIN_GAP) if _runs(runs, base_name) else None,
            score=None if gap is None else -gap,
        ),
        Row(
            f"I2{suffix}",
            f"full_integrator ARR / {base_name}, year 20",
            "-" if ratio is None else f"{ratio:.2f}x",
            "0.90-1.40x",
            _in(ratio, ARR_RATIO) if _runs(runs, base_name) else None,
        ),
    ]


def integration_rows(runs: Sequence[V3Run]) -> list[Row]:
    """I1-I3 over 20-year runs of COMPARED on the same seeds; I1d and I2d the same gap and
    ratio against devices_regions, printed (the like-for-like baseline M23b proposes)."""
    wins: dict[str, int] = {}
    for seed in sorted({r.seed for r in runs}):
        field_ = [r for r in runs if r.seed == seed and r.strategy in COMPARED]
        if field_:
            best = max(field_, key=lambda r: (r.value, r.strategy))
            wins[best.strategy] = wins.get(best.strategy, 0) + 1
    n = len({r.seed for r in runs})
    won = wins.get(INTEGRATOR, 0)
    like = [replace(r, ok=None) for r in _gap_rows(runs, DEVICES, "d")]
    return [
        *_gap_rows(runs, BASE, ""),
        *like,
        Row(
            "I3",
            f"full_integrator wins of {n} (year 20 founder value)",
            f"{won} ({', '.join(f'{k} {v}' for k, v in sorted(wins.items()))})",
            f"<= {MAX_WINS}",
            won <= MAX_WINS,
        ),
    ]


def fab_rows(runs: Sequence[V3Run]) -> list[Row]:
    """F1: the foundry script's first 28 nm fab, months to 70% use within 36 months."""
    hits = total = 0
    months: list[str] = []
    for r in _runs(runs, "foundry"):
        trace = next((f for f in r.fabs if f.node == FAB_NODE), None)
        total += 1
        if trace is None:
            months.append("none")
            continue
        when = next((i for i, u in enumerate(trace.use[:FAB_MONTHS]) if u >= FAB_USE), None)
        months.append("-" if when is None else str(when + 1))
        hits += when is not None
    return [
        Row(
            "F1",
            f"foundry 28 nm fab at {FAB_USE:.0%}+ use within {FAB_MONTHS} months",
            f"{hits} of {total} (months: {', '.join(months)})",
            f">= {FAB_SEEDS} of 10",
            hits >= FAB_SEEDS if total else None,
        )
    ]


def shock_rows(lithium: float, gallium: Sequence[GalliumRun]) -> list[Row]:
    cuts = [g.cut for g in gallium]
    rises = [g.rise for g in gallium]
    cut = _median(cuts)
    return [
        Row(
            "S1",
            "lithium spike: unhedged phone's peak unit cost rise, 2021-22 vs 2020",
            f"{lithium:+.1%}",
            f">= +{LITHIUM_RISE:.0%}",
            lithium >= LITHIUM_RISE,
        ),
        Row(
            "S2",
            "gallium ban: unhedged chip maker's output cut (median; unit cost rise)",
            "-"
            if cut is None
            else f"{cut:.1%} (cost {st.median(rises):+.1%}; {sum(c >= GALLIUM_CUT for c in cuts)}"
            f" of {len(cuts)} seeds)",
            f">= {GALLIUM_CUT:.0%}",
            None if cut is None else cut >= GALLIUM_CUT,
        ),
    ]


def long_rows(runs: Sequence[V3Run]) -> list[Row]:
    """L1-L4 over the 30-year runs."""
    rows: list[Row] = []
    domains = future_domains()
    missing = [f"{r.strategy}/{r.seed}:{d}" for r in runs for d in domains if r.eras.get(d, 0) < 1]
    rows.append(
        Row(
            "L1",
            f"an era arrival 2026-2039 in each of {', '.join(domains)}",
            "all" if not missing else f"missing {', '.join(missing[:6])}",
            "every run",
            not missing,
        )
    )
    dead = sorted({f"{k}" for r in runs for k, n in r.chain_alive.items() if n < 1})
    rows.append(
        Row(
            "L2",
            "rivals alive in every chain category, December 2039",
            "all" if not dead else f"none in {', '.join(dead)}",
            "every category, every run",
            not dead,
        )
    )
    worst = max(((n, g) for r in runs for g, n in r.band_runs.items()), default=(0, "-"))
    rows.append(
        Row(
            "L3",
            "commodity index outside [1/3, 3.0]: longest run, 2026-2039",
            f"{worst[0]} months ({worst[1]})",
            f"<= {BAND_MONTHS} months",
            worst[0] <= BAND_MONTHS,
        )
    )
    chain = (
        "devices",
        "chip",
        "mine:lithium_carbonate",
        "refinery:li_converter",
        "refinery:wafer_plant",
        "fab",
    )
    full = _runs(runs, INTEGRATOR)
    by_15 = ym_to_turn(2024, 12)
    built = [r for r in full if all(r.rungs.get(k, LONG_TURNS) <= by_15 for k in chain)]
    late = [f"{r.seed}:{k}" for r in full for k in chain if r.rungs.get(k, LONG_TURNS) > by_15]
    rows.append(
        Row(
            "L4",
            "full_integrator's whole chain ordered by year 15 (December 2024)",
            f"{len(built)} of {len(full)}" + (f" (late: {', '.join(late[:8])})" if late else ""),
            "printed",
            None,
        )
    )
    return rows


def rung_table(runs: Sequence[V3Run]) -> str:
    keys = sorted({k for r in runs for k in r.rungs})
    lines = ["strategy        seed  " + "  ".join(f"{k[:14]:>14}" for k in keys)]
    for r in sorted(runs, key=lambda r: (r.strategy, r.seed)):
        cells = []
        for k in keys:
            t = r.rungs.get(k)
            label = "-" if t is None else "{}-{:02d}".format(*turn_to_ym(t))
            cells.append(f"{label:>14}")
        lines.append(f"{r.strategy:15} {r.seed:4}  " + "  ".join(cells))
    return "\n".join(lines)


def run_table(runs: Sequence[V3Run]) -> str:
    lines = ["strategy        seed  value $M   ARR $M  margin  mines  fabs  seconds"]
    for r in sorted(runs, key=lambda r: (r.strategy, r.seed)):
        m = r.margin
        lines.append(
            f"{r.strategy:15} {r.seed:4} {r.value / 1e8:9,.0f} {r.arr / 1e8:8,.0f} "
            f"{'-' if m is None else f'{m:+.1%}':>7} {r.mines:6} {len(r.fabs):5} {r.seconds:8.0f}"
        )
    return "\n".join(lines)


def jobs() -> int:
    return os.cpu_count() or 1


_ = DELEGATED  # the delegation benchmark (ceo) is V4's, not compared here
