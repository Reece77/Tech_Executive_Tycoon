"""M50's balance readings (docs/formulas.md 60.3; docs/tasks/M50-the-2008-start.md).

Target 1 (a 2010 game is unchanged) is the golden snapshots and the state caches, not here.

- **Target 2, the crisis bites.** On 10 seeds a 2008 game and a 2010 game are played with the
  player idle. *Scarcer*: rival startups' funding rounds closed per attempt (15.4: chance 0.6 x
  climate) in Q4 2008-Q2 2009 against 2010, and the term sheets a seed round can expect (the
  sum over seed firms of 14.5's answer chance at the month's climate). *Cheaper*: V_base
  (14.3) for one standard company (ARR $1M, doubling in 6 months, live, 6 staff) at the
  month's climate. *Failures*: of the rival startups with under 12 months of runway (cash over
  last month's operating loss) in October 2008, the share closed within 12 months, against
  the same share from January 2010 and January 2011 in the 2010 games.
- **Target 3, the world arrives sensibly.** January 2010 in a 2008 game against January 2010 in
  a 2010 game (after that month is played): each category's addressable customers (home and
  regional) and each named v1 incumbent's MRR, as ratios; the median per seed, then over seeds.
- **Target 4, every strategy plays.** V1's founder-played strategies from January 2008, V1's
  own measure (wins by mean founder value over the run's last 12 months, at year 10), and the
  same from 2010 for reference. `--long` plays them 360 months (to December 2037).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from statistics import median
from typing import Final

from tst.balance import m30
from tst.balance.game import Game
from tst.balance.report import SCENARIO
from tst.loader import LoadedData
from tst.sim.calendar import format_turn, ym_to_turn
from tst.sim.finance import formulas as ff
from tst.sim.finance.fundraising import climate
from tst.sim.ledger import CASH, apply_entries
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import GameState

SEEDS: Final = tuple(range(1, 11))
CRISIS: Final = (ym_to_turn(2008, 10), ym_to_turn(2009, 6))  # Q4 2008 to Q2 2009, inclusive
CALM: Final = (ym_to_turn(2010, 1), ym_to_turn(2010, 12))  # 2010
OCTOBER_2008: Final = ym_to_turn(2008, 10)
CALM_SNAPSHOTS: Final = (ym_to_turn(2010, 1), ym_to_turn(2011, 1))
FAIL_WINDOW: Final = 12  # months after the snapshot
SHORT_RUNWAY: Final = 12  # months of runway
SCARCER: Final = 0.40  # 60.3 target 2: at least 40% fewer rounds
CHEAPER: Final = 0.20  # and 20% cheaper
FAIL_RATIO: Final = 2.0  # short-runway startups fail at least twice as often
BAND: Final = (0.7, 1.3)  # 60.3 target 3
TURNS_TO_2011: Final = ym_to_turn(2012, 1)  # the 2010 games play to December 2011
TURNS_2008: Final = ym_to_turn(2010, 2)  # the 2008 games play through January 2010
STANDARD_ARR: Final = 100_000_000  # cents: $1M ARR (target 2's standard company)
STANDARD_GROWTH: Final = 1.0  # doubling over 6 months
STANDARD_STAFF: Final = 6
V1_YEARS: Final = 120  # V1 reads year 10
LONG: Final = 360  # to December 2037


def loaded() -> LoadedData:
    return m30.loaded()


def start(seed: int, start_year: int, scenario: str = SCENARIO) -> Game:
    """A new game as create_save makes it, in memory, begun in January of `start_year`."""
    data = loaded()
    sd = data.game_data.scenario(scenario)
    assert sd is not None
    state, entries = new_game(
        save_name="m50",
        master_seed=seed,
        scenario=sd,
        difficulty="standard",
        company_name="Balance Co",
        founder=DEFAULT_FOUNDER,
        balance=data.balance,
        data=data.game_data,
        start_year=start_year,
    )
    game = Game(data, state, apply_entries({}, entries))
    game.record_value()
    return game


@dataclass(slots=True)
class WorldRun:
    """One idle game's readings."""

    seed: int
    start_year: int
    attempts: dict[int, int] = field(default_factory=dict)  # turn -> startups trying to raise
    funded: dict[int, int] = field(default_factory=dict)  # turn -> rounds closed
    climate: dict[int, float] = field(default_factory=dict)
    sheets: dict[int, float] = field(default_factory=dict)  # expected seed term sheets
    value: dict[int, float] = field(default_factory=dict)  # the standard company's V_base
    short: dict[int, list[tuple[int, bool]]] = field(default_factory=dict)  # snapshot -> (id, failed)
    markets: dict[str, float] = field(default_factory=dict)  # Jan 2010 addressable, by category
    revenue: dict[str, int] = field(default_factory=dict)  # Jan 2010 MRR, by named incumbent


def _runway_short(state: GameState, balances: dict[tuple[int, str], int]) -> list[int]:
    out = []
    for c in state.companies:
        if not c.is_startup or not c.alive or not c.op_history:
            continue
        loss = -c.op_history[-1]
        cash = balances.get((c.id, CASH), 0)
        if loss > 0 and cash < SHORT_RUNWAY * loss:
            out.append(c.id)
    return out


def _named(data: LoadedData) -> set[str]:
    """The v1 incumbents (software, cloud, devices, chips, servers, manufacturing)."""
    families = {None, "chips"}
    return {
        inc.name
        for inc in data.game_data.incumbents
        if inc.products
        and all(
            data.game_data.category(p.category).family in families
            and p.category not in ("vehicles", "industrial_robots", "humanoid_robots")
            for p in inc.products
        )
    }


def world_run(job: tuple[int, int]) -> WorldRun:
    seed, start_year = job
    game = start(seed, start_year)
    data = game.loaded
    run = WorldRun(seed, start_year)
    firms = [f for f in data.game_data.investors if "seed" in f.series]
    rb = data.balance.finance.round
    last = TURNS_2008 if start_year < 2010 else TURNS_TO_2011
    snapshots = (OCTOBER_2008,) if start_year < 2010 else CALM_SNAPSHOTS
    named = _named(data)
    while game.state.turn < last:
        turn = game.state.turn
        if turn in snapshots:
            run.short[turn] = [(cid, False) for cid in _runway_short(game.state, game.balances)]
        before = {c.id: c.last_raise_turn for c in game.state.companies if c.is_startup}
        v = climate(game.state, data.game_data)
        run.climate[turn] = v
        run.sheets[turn] = sum(
            ff.response_chance(f.response, v, rb.max_response, 1.0) for f in firms
        )
        run.value[turn] = float(
            ff.base_value_cents(
                STANDARD_ARR, STANDARD_GROWTH, v, True, STANDARD_STAFF, data.balance.finance
            )
        )
        game.turn()
        result = game.last_result
        assert result is not None
        run.attempts[turn] = sum(
            1
            for c in game.state.companies
            if c.is_startup and c.last_raise_turn == turn and before.get(c.id) != turn
        )
        run.funded[turn] = sum(1 for m in result.rival_moves if m.action == "funded")
        for snap, rows in run.short.items():
            if snap < turn <= snap + FAIL_WINDOW:
                run.short[snap] = [
                    (cid, failed or not game.state.company(cid).alive) for cid, failed in rows
                ]
        if turn == 0:
            st = game.state
            for m in (*st.markets, *st.regional_markets):
                run.markets[m.category] = run.markets.get(m.category, 0.0) + m.addressable
            for c in st.companies:
                if c.name in named and c.mrr_history:
                    run.revenue[c.name] = c.mrr_history[-1]
    return run


def worlds(seeds: Sequence[int] = SEEDS, jobs: int = 4) -> list[WorldRun]:
    plan = [(s, y) for s in seeds for y in (2008, 2010)]
    if jobs <= 1:
        return [world_run(j) for j in plan]
    with ProcessPoolExecutor(jobs) as pool:
        return list(pool.map(world_run, plan))


def _window(d: dict[int, float] | dict[int, int], span: tuple[int, int]) -> list[float]:
    return [float(v) for t, v in d.items() if span[0] <= t <= span[1]]


@dataclass(frozen=True, slots=True)
class Reading:
    target: str
    measure: str
    value: float | None
    band: str
    ok: bool | None


def crisis_readings(runs: Sequence[WorldRun]) -> list[Reading]:
    early = [r for r in runs if r.start_year < 2010]
    late = [r for r in runs if r.start_year == 2010]
    out: list[Reading] = []

    def rate(rs: Sequence[WorldRun], span: tuple[int, int]) -> float | None:
        tries = sum(sum(_window(r.attempts, span)) for r in rs)
        got = sum(sum(_window(r.funded, span)) for r in rs)
        return got / tries if tries else None

    crisis_rate, calm_rate = rate(early, CRISIS), rate(late, CALM)
    drop = None if not crisis_rate or not calm_rate else 1 - crisis_rate / calm_rate
    out.append(
        Reading(
            "60.3 T2",
            "startup rounds closed per attempt, Q4 2008-Q2 2009 vs 2010 (fewer by)",
            drop,
            f">= {SCARCER:.0%}",
            None if drop is None else drop >= SCARCER,
        )
    )
    sheets_c = median(v for r in early for v in _window(r.sheets, CRISIS))
    sheets_n = median(v for r in late for v in _window(r.sheets, CALM))
    out.append(
        Reading(
            "60.3 T2",
            "expected seed term sheets, median month (fewer by)",
            1 - sheets_c / sheets_n,
            f">= {SCARCER:.0%}",
            1 - sheets_c / sheets_n >= SCARCER,
        )
    )
    value_c = median(v for r in early for v in _window(r.value, CRISIS))
    value_n = median(v for r in late for v in _window(r.value, CALM))
    out.append(
        Reading(
            "60.3 T2",
            "standard company's V_base, median month (cheaper by)",
            1 - value_c / value_n,
            f">= {CHEAPER:.0%}",
            1 - value_c / value_n >= CHEAPER,
        )
    )

    def failed(rs: Sequence[WorldRun]) -> tuple[int, int]:
        rows = [row for r in rs for snap in r.short.values() for row in snap]
        return sum(1 for _, f in rows if f), len(rows)

    fc, nc = failed(early)
    fn, nn = failed(late)
    ratio = None if not nc or not nn or not fn else (fc / nc) / (fn / nn)
    out.append(
        Reading(
            "60.3 T2",
            f"short-runway startups failing within a year: Oct 2008 {fc}/{nc} vs 2010-11 {fn}/{nn}"
            " (x)",
            ratio,
            f">= {FAIL_RATIO:g}x",
            None if ratio is None else ratio >= FAIL_RATIO,
        )
    )
    return out


def arrival_readings(runs: Sequence[WorldRun]) -> list[Reading]:
    by_seed = {(r.seed, r.start_year): r for r in runs}
    seeds = sorted({r.seed for r in runs})
    markets, revenue = [], []
    for s in seeds:
        a, b = by_seed.get((s, 2008)), by_seed.get((s, 2010))
        if a is None or b is None:
            continue
        m = [a.markets[k] / b.markets[k] for k in b.markets if b.markets[k] and k in a.markets]
        r = [a.revenue[k] / b.revenue[k] for k in b.revenue if b.revenue[k] and k in a.revenue]
        markets.append(median(m))
        revenue.append(median(r))
    out = []
    for label, values in (("category sizes", markets), ("named rivals' MRR", revenue)):
        v = median(values) if values else None
        out.append(
            Reading(
                "60.3 T3",
                f"{label}, January 2010 in a 2008 game over a 2010 game (median of seeds)",
                v,
                f"{BAND[0]}-{BAND[1]}x",
                None if v is None else BAND[0] <= v <= BAND[1],
            )
        )
    return out


# --- Target 4: V1's strategies from 2008 ------------------------------------------------------


def strategy_run(job: tuple[str, int, int, int]) -> tuple[str, int, int, float, str]:
    """(strategy, seed, start year, mean founder value over the last 12 months, game state)."""
    from tst.balance.strategies_v2 import STRATEGIES as V2

    name, seed, start_year, months = job
    game = start(seed, start_year)
    script = V2[name]
    first = game.state.turn
    while game.state.turn < first + months and not game.state.ended:
        script(game)
        game.turn()
    end = first + months
    window = [game.founder_value.get(t, 0) for t in range(end - 11, end + 1)]
    return name, seed, start_year, sum(window) / len(window), game.state.save_meta.game_state


def strategy_readings(
    seeds: Sequence[int] = SEEDS, months: int = V1_YEARS, jobs: int = 4
) -> tuple[list[Reading], str]:
    from tst.balance.strategies_v2 import DELEGATED, STRATEGIES
    from tst.balance.v2 import V1_MAX_WINS

    played = [s for s in STRATEGIES if s not in DELEGATED]
    plan = [(s, seed, y, months) for y in (2008, 2010) for s in played for seed in seeds]
    with ProcessPoolExecutor(jobs) as pool:
        results = list(pool.map(strategy_run, plan))
    lines, out = [], []
    for year in (2008, 2010):
        wins: Counter[str] = Counter()
        for seed in seeds:
            row = [(v, s) for s, sd, y, v, _ in results if sd == seed and y == year]
            best = max(v for v, _ in row)
            top = [s for v, s in row if v == best]
            if len(top) == 1 and best > 0:
                wins[top[0]] += 1
        most = max(wins.values(), default=0)
        cap = V1_MAX_WINS * len(seeds) / 10
        detail = ", ".join(f"{s} {wins[s]}" for s in played if wins.get(s))
        lines.append(f"  from {year}: {detail or '-'}")
        out.append(
            Reading(
                "60.3 T4" if year == 2008 else "60.3 T4 (2010, reference)",
                f"V1 from January {year}, {months} months: most wins of one strategy",
                float(most),
                f"<= {cap:g}/{len(seeds)}",
                most <= cap,
            )
        )
    return out, "\n".join(lines)


def table(readings: Sequence[Reading]) -> str:
    rows = [f"{'target':<26} {'measure':<92} {'value':>8}  {'band':<12} ok"]
    for r in readings:
        v = "-" if r.value is None else f"{r.value:.3f}"
        ok = "-" if r.ok is None else ("ok" if r.ok else "MISS")
        rows.append(f"{r.target:<26} {r.measure:<92} {v:>8}  {r.band:<12} {ok}")
    return "\n".join(rows)


def report(seeds: Sequence[int] = SEEDS, jobs: int = 4, strategies: bool = True) -> str:
    runs = worlds(seeds, jobs)
    readings = crisis_readings(runs) + arrival_readings(runs)
    extra = ""
    if strategies:
        more, extra = strategy_readings(seeds, jobs=jobs)
        readings += more
    climate_line = ", ".join(
        f"{format_turn(t)} {v:.2f}"
        for t, v in sorted(next(r for r in runs if r.start_year < 2010).climate.items())
        if t % 3 == 0
    )
    return f"{table(readings)}\n\nclimate (quarters): {climate_line}\n{extra}\n"
