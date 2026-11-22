"""M37's balance runs (docs/formulas.md 52.5; docs/tasks/M37-dynasty-mode.md).

**Target 1, nothing moves before 2040.** `pre_2040_hashes` plays M30's nine state-cache runs
(tst.balance.m30) to December 2039 with dynasty mode off or on (on: switched at turn 0, as the
new-game setting does) and digests every month with the fields M37 added left out
(`GameState.dynasty`, `GameMode.length`) and a dynasty campaign's mode read as the standard
campaign's (None). Each month's digest must equal the one recorded before M37 (`m30_state_hashes
.json` as `main` had it): anything M37 changed before 2040 would show as the first month that
differs. After M37 merges the fixture is re-recorded with the new fields (CHANGELOG), and
`legacy` keeps this comparison: `tests/fixtures/m37_pre_2040_hashes.json`.

**Targets 2-5** play dynasty games to December 2069 (`dynasty_run`) and print their readings.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Final

from tst.balance import m30
from tst.balance.game import Game, start_game
from tst.balance.report import SCENARIO
from tst.loader import LoadedData
from tst.sim.dynasty.mode import continue_dynasty
from tst.sim.modes.models import GameMode
from tst.sim.state import GameState, group_companies

TURNS: Final = 360  # January 2010 to December 2039
LEGACY_FILE: Final = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "m37_pre_2040_hashes.json"
)
# the fields M37 added: left out, so a digest is what it was before M37
SKIP: Final[Mapping[type, frozenset[str]]] = {
    GameState: frozenset({"dynasty"}),
    GameMode: frozenset({"length"}),
}

type Hashes = dict[str, list[str]]


def legacy_view(state: GameState) -> GameState:
    """A dynasty campaign's state as a standard one's: its mode, made only of the setting,
    read as None (a standard campaign has no mode)."""
    mode = state.mode
    if mode is not None and mode == GameMode(kind="campaign", length="dynasty"):
        return replace(state, mode=None)
    return state


def _digest(digester: m30.Digester, game: Game) -> str:
    import hashlib

    state = digester.digest(legacy_view(game.state))
    balances = digester.digest(game.balances)
    digester.next_month()
    return hashlib.sha256(state + balances).hexdigest()[: m30.HEX]


def pre_2040_hashes(
    job: tuple[str, int, bool], turns: int = TURNS, *, reference: bool = False
) -> list[str]:
    """One M30 run to December 2039, dynasty mode off or on, M37's fields left out.
    `reference`: on the same code with M37's rules disabled (`reference_loaded`)."""
    name, seed, dynasty = job
    loaded = reference_loaded() if reference else m30.loaded()
    game = start_game(loaded, seed, SCENARIO)
    if dynasty:
        game.state = continue_dynasty(game.state, loaded.balance)
    script = m30.strategy(name)
    digester = m30.Digester(SKIP)
    out: list[str] = []
    while game.state.turn < turns and not game.state.ended:
        script(game)
        game.turn()
        out.append(_digest(digester, game))
    return out


def jobs(dynasty: Sequence[bool] = (False, True)) -> list[tuple[str, int, bool]]:
    return [(name, seed, d) for d in dynasty for name, seed in m30.jobs()]


def all_pre_2040(workers: int, dynasty: Sequence[bool] = (False, True)) -> dict[str, list[str]]:
    todo = jobs(dynasty)
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        runs = list(pool.map(pre_2040_hashes, todo))
    return {
        f"{m30.key(n, s)}/{'dynasty' if d else 'standard'}": r
        for (n, s, d), r in zip(todo, runs, strict=True)
    }


def legacy() -> Hashes:
    """The digests recorded before M37 (main's m30_state_hashes.json, kept by M37)."""
    out: Hashes = json.loads(LEGACY_FILE.read_text(encoding="utf-8"))
    return out


def compare(runs: Mapping[str, list[str]], want: Hashes) -> dict[str, str | None]:
    """run -> None if identical to the pre-M37 digests, else the first difference."""
    return {k: m30.first_difference(v, want[k.rsplit("/", 1)[0]]) for k, v in runs.items()}


# --- Target 1's same-code differential (M43r, Codex review 9 finding 14) ----------------------
#
# A fixture re-recorded from current runs takes in any change both settings share, so the
# mode-parity check above cannot see an M37 rule moved before 2040 in both. The differential
# replays each run on the same code against a reference arm with M37's rules disabled: the data
# loaded with dynasty.start_year (and end_year) moved REFERENCE_SHIFT years on, so every rule
# M37 keys on its start (the turn's January steps, eras' and nodes' windows, the loader's
# maturity, slowdown and successors) lies past the horizon. Approved changes of any other
# milestone run on both sides; a month that differs before 2040 is an M37 rule moved early.

REFERENCE_SHIFT: Final = 200  # years M37's start moves in the reference arm (past any horizon)
_REFERENCE: dict[str, LoadedData] = {}


def reference_loaded(data_dir: Path | None = None) -> LoadedData:
    """The game's data with M37 disabled: a copy whose dynasty.start_year and end_year are
    REFERENCE_SHIFT years later, loaded once a process."""
    import re
    import shutil
    import tempfile

    from tst.loader import load_all

    source = data_dir or m30.DATA
    key = str(source)
    if key not in _REFERENCE:
        target = Path(tempfile.mkdtemp(prefix="tst-m37-reference-")) / "data"
        shutil.copytree(source, target)
        path = target / "balance.yaml"
        text = path.read_text(encoding="utf-8")

        def shift(m: re.Match[str]) -> str:
            return f"{m.group(1)}{int(m.group(2)) + REFERENCE_SHIFT}"

        block = re.compile(r"(?ms)^dynasty:.*?(?=^\S)")
        head = block.search(text)
        assert head is not None, "balance.yaml has no dynasty block"
        moved = re.sub(r"(?m)^(  (?:start|end)_year: )(\d+)", shift, head.group(0), count=2)
        path.write_text(text[: head.start()] + moved + text[head.end() :], encoding="utf-8")
        loaded = load_all(target)
        b = loaded.balance.dynasty
        assert b.start_year == m30.loaded().balance.dynasty.start_year + REFERENCE_SHIFT
        _REFERENCE[key] = loaded
    return _REFERENCE[key]


def reference_hashes(job: tuple[str, int]) -> list[str]:
    name, seed = job
    return pre_2040_hashes((name, seed, False), reference=True)


def all_reference(workers: int) -> dict[str, list[str]]:
    todo = m30.jobs()
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        runs = list(pool.map(reference_hashes, todo))
    return {m30.key(n, s): r for (n, s), r in zip(todo, runs, strict=True)}


def differential(
    runs: Mapping[str, list[str]], ref: Mapping[str, list[str]]
) -> dict[str, str | None]:
    """run -> None if every month to December 2039 equals the reference arm's, else the first
    month that differs."""
    return {k: m30.first_difference(v, ref[k.rsplit("/", 1)[0]]) for k, v in runs.items()}


def replay_pair(
    start: GameState,
    months: int,
    loaded: LoadedData,
    reference: LoadedData,
    balances: Mapping[tuple[int, str], int] | None = None,
) -> tuple[list[str], list[str]]:
    """A short differential from one state: `months` months on `loaded` and on `reference`,
    each month's digest (M37's fields left out). The reference arm starts from its own copy,
    so no cache built in one arm is read in the other."""
    import pickle

    out: list[list[str]] = []
    for arm in (loaded, reference):
        state: GameState = pickle.loads(pickle.dumps(start))
        game = Game(arm, state, dict(balances or {}))
        digester = m30.Digester(SKIP)
        digests: list[str] = []
        for _ in range(months):
            if game.state.ended:
                break
            game.turn()
            digests.append(_digest(digester, game))
        out.append(digests)
    return out[0], out[1]


def first_differing_turn(start_turn: int, a: Sequence[str], b: Sequence[str]) -> int | None:
    """The turn of the first month the arms differ (`start_turn` is the first month played)."""
    for i, (x, y) in enumerate(zip(a, b, strict=False)):
        if x != y:
            return start_turn + i
    return None if len(a) == len(b) else start_turn + min(len(a), len(b))


# --- Targets 2-5: dynasty games to December 2069 ---------------------------------------------

SEEDS: Final = tuple(range(1, 11))
STRATEGY: Final = "full_integrator"  # every system the turn runs (M30's chain builder)
END: Final = 720  # the turn after December 2069
START: Final = 360  # January 2040
DECADES: Final = ((360, 480), (480, 600), (600, 720))  # the 2040s, 2050s and 2060s
COMMODITY_FROM, COMMODITY_TO = 240, 360  # the 2030s, the reference average
FAMILY_AGES: Final = (2, 5)
# SQLite stores money as int64 (9.2e18 cents): a balance must stay within two thirds of it by
# 2069 (the largest AI incumbent's books, already about $230T a year by 2040, set the scale)
INT64_HEADROOM: Final = 6.1e18  # children at the start (M36's family_game)


@dataclass(frozen=True, slots=True)
class DynastyResult:
    seed: int
    ended: str  # the game state at the end
    end_turn: int
    eras: int  # eras arrived in 2040-2069
    min_rivals: dict[str, int]  # "category/decade" -> fewest active rivals in a January
    commodity_excursion: dict[str, int]  # good -> longest run of months outside 1/3-3x
    successions: int  # generations handed over, or a professional CEO appointed
    deaths: int
    leader_changes: int
    entrants: int
    cost_ratio: float  # leading-edge cost per transistor, December 2069 / January 2040
    gaps_lengthen: bool
    max_balance: int = 0  # the largest |ledger balance| at the end, cents (int64 headroom)
    # the PM's diagnosis (2026-11-17): where that balance is and how the markets grew
    max_key: tuple[str, str] = ("", "")  # (company, account) of the largest balance
    max_2039: int = 0  # the same balance after December 2039, cents
    markets: dict[int, dict[str, float]] = field(default_factory=dict)  # year -> category ->
    # annualised revenue (this month's x 12), cents, at the end of December


def _family_game(seed: int) -> Game:
    from tst.balance.game import Game
    from tst.sim.family.setup import FamilySpec
    from tst.sim.ledger import apply_entries
    from tst.sim.setup import DEFAULT_FOUNDER, new_game

    data = m30.loaded()
    scenario = data.game_data.scenario(SCENARIO)
    assert scenario is not None
    state, entries = new_game(
        save_name="m37",
        master_seed=seed,
        scenario=scenario,
        difficulty="standard",
        company_name="Dynasty Co",
        founder=DEFAULT_FOUNDER,
        balance=data.balance,
        data=data.game_data,
        family=FamilySpec("children", FAMILY_AGES),
    )
    game = Game(data, state, apply_entries({}, entries))
    game.record_value()
    return game


def _cost_ratio(seed: int) -> tuple[float, bool]:
    from tst.sim.dynasty import nodes as dn
    from tst.sim.fabs import nodes as fnodes

    data = m30.loaded()
    nf = data.game_data.nodes
    assert nf is not None
    tl = fnodes.timeline(seed, nf, data.balance.fab)

    def cost(turn: int) -> float:
        node = tl.leading(turn)
        return tl.wafer_cents[node] / dn.density(seed, nf, node)

    mids = [n.start_turn + n.months // 2 for n in nf.dynasty_future]
    gaps = [b - a for a, b in itertools.pairwise(mids)]
    lengthen = all(b > a for a, b in itertools.pairwise(gaps))
    return cost(END - 1) / cost(START), lengthen


def dynasty_run(seed: int, turns: int = END) -> DynastyResult:
    """One dynasty game with a family (M36's two children), full_integrator, to `turns`."""
    from tst.sim.commodities.commodity import index_now
    from tst.sim.dynasty.rivals import DYNASTY_KEY, active_rivals

    data = m30.loaded()
    g = data.game_data
    game = _family_game(seed)
    game.state = continue_dynasty(game.state, data.balance)
    script = m30.strategy(STRATEGY)
    goods = [c.key for c in g.commodities.goods] if g.commodities else []
    prices: dict[str, list[float]] = {k: [] for k in goods}
    rivals: dict[str, int] = {}
    markets: dict[int, dict[str, float]] = {}
    balances_2039: dict[tuple[int, str], int] = {}
    while game.state.turn < turns and not game.state.ended:
        script(game)
        game.turn()
        s = game.state
        if s.turn in MARKET_YEARS:
            markets[MARKET_YEARS[s.turn]] = category_revenue(s, data)
        if s.turn == START:
            balances_2039 = dict(game.balances)
        for k in goods:
            prices[k].append(index_now(s, k, g))
        if s.turn > START and s.turn % 12 == 1:  # after each January's turn, 2040 on
            mine = {c.id for c in group_companies(s, s.player.id)}
            decade = next(i for i, (a, b) in enumerate(DECADES) if a <= s.turn - 1 < b)
            for c in g.categories:
                if not c.markets:
                    continue
                key = f"{c.key}/{2040 + 10 * decade}s"
                rivals[key] = min(rivals.get(key, 10**6), active_rivals(s, c.key, mine))
    s = game.state
    excursion: dict[str, int] = {}
    for k, series in prices.items():
        ref = series[COMMODITY_FROM - 1 : COMMODITY_TO - 1]
        if not ref or len(series) < START:
            continue
        mean = sum(ref) / len(ref)
        run = worst = 0
        for p in series[START - 1 :]:
            run = run + 1 if not mean / 3 <= p <= 3 * mean else 0
            worst = max(worst, run)
        excursion[k] = worst
    family = s.family
    successions = 0
    if family is not None:
        successions = len(family.generations) - 1 + (family.head_mode == "family_head")
    d = s.dynasty
    ratio, lengthen = _cost_ratio(seed)
    top = max(game.balances, key=lambda k: abs(game.balances[k]), default=None)
    return DynastyResult(
        seed=seed,
        ended=s.save_meta.game_state,
        end_turn=s.turn,
        eras=sum(1 for a in s.era_arrivals if a.turn >= START),
        min_rivals=rivals,
        commodity_excursion=excursion,
        successions=successions,
        deaths=len(d.deaths) if d else 0,
        leader_changes=len(d.leader_changes) if d else 0,
        entrants=sum(1 for c in s.companies if c.rival_key[:1] == (DYNASTY_KEY,)),
        cost_ratio=ratio,
        gaps_lengthen=lengthen,
        max_balance=abs(game.balances[top]) if top else 0,
        max_key=(s.company(top[0]).name, top[1]) if top else ("", ""),
        max_2039=abs(balances_2039.get(top, 0)) if top else 0,
        markets=markets,
    )


MARKET_YEARS: Final = {192: 2025, 360: 2039, 720: 2069}  # the state after December of the year
MONEY_LIMIT: Final = 1.0e18  # cents: the PM's guard (2026-11-17) on any ledger balance


def category_revenue(state: GameState, data: LoadedData) -> dict[str, float]:
    """Each category's revenue this month (customers x prices, every region) x 12, cents."""
    from tst.sim.score import market_revenue

    out: dict[str, float] = {}
    for (category, _, _), by in market_revenue(state, data.game_data, data.balance).items():
        out[category] = out.get(category, 0.0) + 12 * sum(by.values())
    return out


@dataclass(frozen=True, slots=True)
class MoneyRow:
    """The PM's money guard as a judged row (tst.balance.known_misses): ok while every ledger
    balance stays under MONEY_LIMIT; the score is the largest over the limit."""

    target: str
    ok: bool
    score: float
    detail: str


def money_row(results: Sequence[DynastyResult]) -> MoneyRow:
    worst = max(results, key=lambda r: r.max_balance)
    company, account = worst.max_key
    return MoneyRow(
        "M37.money",
        worst.max_balance < MONEY_LIMIT,
        worst.max_balance / MONEY_LIMIT,
        f"seed {worst.seed}: {company} {account} {worst.max_balance:.3e} cents in December 2069 "
        f"({worst.max_2039:.3e} in December 2039); limit {MONEY_LIMIT:.1e}",
    )


def diagnosis(results: Sequence[DynastyResult], money: float) -> str:
    """The largest balance and the markets' annualised revenue in 2025, 2039 and 2069, in game
    cents and in real dollars (game dollars / economy_scale.money)."""
    lines = [
        money_row(results).detail,
        "",
        "| seed | year | AI models | top three |",
        "| --- | --- | --- | --- |",
    ]
    for r in results:
        for year, cats in sorted(r.markets.items()):
            top = sorted(cats.items(), key=lambda kv: -kv[1])[:3]
            ai = cats.get("ai_models", 0.0)

            def real(cents: float) -> str:
                return f"{cents:.2e} (${cents / 100 / money / 1e12:,.1f}T real)"

            lines.append(
                f"| {r.seed} | {year} | {real(ai)} | "
                + "; ".join(f"{k} {real(v)}" for k, v in top)
                + " |"
            )
    return "\n".join(lines)


def run_all(workers: int, seeds: Sequence[int] = SEEDS) -> list[DynastyResult]:
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(dynasty_run, seeds))


@dataclass(frozen=True, slots=True)
class Readings:
    eras_median: float  # target 2
    rivals_ok_seeds: int  # target 2: seeds where every category had 3+ in every decade
    thin: list[str]  # "seed:category/decade" short of 3
    commodity_ok: bool  # target 2: no good outside 1/3-3x its 2030s mean for over 60 months
    excursions: dict[str, int]
    cost_ratio_min: float  # target 3: at least 0.5
    gaps_lengthen: bool  # target 3
    succession_seeds: int  # target 4: seeds with a succession by 2069 (9 of 10)
    max_balance: int  # the largest |ledger balance|: under INT64_HEADROOM (SQLite's integers)


def readings(results: Sequence[DynastyResult]) -> Readings:
    import statistics

    thin = [f"{r.seed}:{k}" for r in results for k, n in sorted(r.min_rivals.items()) if n < 3]
    bad_seeds = {t.split(":")[0] for t in thin}
    worst: dict[str, int] = {}
    for r in results:
        for k, n in r.commodity_excursion.items():
            worst[k] = max(worst.get(k, 0), n)
    return Readings(
        eras_median=statistics.median(r.eras for r in results),
        rivals_ok_seeds=len(results) - len(bad_seeds),
        thin=thin,
        commodity_ok=all(n <= 60 for n in worst.values()),
        excursions=worst,
        cost_ratio_min=min(r.cost_ratio for r in results),
        gaps_lengthen=all(r.gaps_lengthen for r in results),
        succession_seeds=sum(1 for r in results if r.successions > 0 or r.deaths > 0),
        max_balance=max((r.max_balance for r in results), default=0),
    )


def report(results: Sequence[DynastyResult]) -> str:
    x = readings(results)
    n = len(results)
    lines = [
        "| Target | Reading | Band | Result |",
        "| --- | --- | --- | --- |",
        f"| 52.5 T2 eras 2040-2069 (median) | {x.eras_median} | >= 4 | "
        f"{'pass' if x.eras_median >= 4 else 'MISS'} |",
        f"| 52.5 T2 every category 3+ rivals each decade | {x.rivals_ok_seeds} of {n} | 9 of 10 | "
        f"{'pass' if x.rivals_ok_seeds >= 0.9 * n else 'MISS'} |",
        f"| 52.5 T2 commodity months outside 1/3-3x | max {max(x.excursions.values(), default=0)} "
        f"| <= 60 | {'pass' if x.commodity_ok else 'MISS'} |",
        f"| 52.5 T3 gaps lengthen | {x.gaps_lengthen} | true | "
        f"{'pass' if x.gaps_lengthen else 'MISS'} |",
        f"| 52.5 T3 cost per transistor 2069/2040 | min {x.cost_ratio_min:.2f} | >= 0.50 | "
        f"{'pass' if x.cost_ratio_min >= 0.5 else 'MISS'} |",
        f"| 52.5 T4 a succession by 2069 | {x.succession_seeds} of {n} | 9 of 10 | "
        f"{'pass' if x.succession_seeds >= 0.9 * n else 'MISS'} |",
        f"| M37 the largest ledger balance (cents) | {x.max_balance:.2e} | "
        f"< {INT64_HEADROOM:.1e} | {'pass' if x.max_balance < INT64_HEADROOM else 'MISS'} |",
    ]
    for r in results:
        lines.append(
            f"<!-- seed {r.seed}: {r.ended} at {r.end_turn}, eras {r.eras}, successions "
            f"{r.successions}, deaths {r.deaths}, leaders {r.leader_changes}, entrants "
            f"{r.entrants}, cost ratio {r.cost_ratio:.2f} -->"
        )
    if x.thin:
        lines.append(f"<!-- thin: {', '.join(x.thin)} -->")
    return "\n".join(lines)


def dynasty_digests(seed: int, turns: int) -> list[str]:
    """M30's digest of a family dynasty game, month by month to `turns` (the seeded test)."""
    data = m30.loaded()
    game = _family_game(seed)
    game.state = continue_dynasty(game.state, data.balance)
    script = m30.strategy(STRATEGY)
    digester = m30.Digester()
    out: list[str] = []
    while game.state.turn < turns and not game.state.ended:
        script(game)
        game.turn()
        out.append(m30.month_digest(digester, game))
    return out
