"""M52's balance runs (docs/formulas.md 66.4).

**Target 1, nothing else moves:** M30's state cache, the golden snapshots and M45's dynasty
cache (unchanged; their own tests).

**Target 2, the round trip:** every scenarios.yaml entry opened in the editor and saved
unchanged (`custom.from_historical`, through the canonical file text) starts a game identical to
the original's: each month's full-state digest (M30's) equal to month 12, seeds 1-3, with the
custom game's mode record read as the original's (its key, hash and empty growth changes are
the only fields that name it a custom game).

**Target 3, determinism:** `custom_digests` plays the custom scenario `DETERMINISM` (an edited
EV maker) for 24 months on seed 1 and digests every month; the `determinism` job runs it on
Linux and Windows (tools/platform_digests.py).

**Target 4, long play:** `sandbox_2100` continues a 2069 dynasty game in sandbox to December
2100 (sub-task 5).

Each start is built as `create_save` builds it (`new_game` in the world's first year, then
`start_mode`), held in memory as a `Game`.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from typing import Final

from tst import scenario_files as sf
from tst.balance import m30
from tst.balance.game import Game
from tst.loader import LoadedData
from tst.sim.ledger import apply_entries
from tst.sim.modes import custom
from tst.sim.modes import scenarios as sc
from tst.sim.modes.custom_config import CustomScenario
from tst.sim.modes.world import start_mode
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import GameState

SEEDS: Final = (1, 2, 3)
ROUND_TRIP_MONTHS: Final = 12  # 66.4 target 2: the state hash at month 12
DETERMINISM_MONTHS: Final = 24  # 66.4 target 3: at month 24
DETERMINISM_SEED: Final = 1

log = logging.getLogger(__name__)


def _start(loaded: LoadedData, key: str, seed: int, spec: CustomScenario | None) -> Game:
    """A scenario's start (`spec` None) or a custom one's, as `create_save` builds it."""
    data = loaded.game_data
    if spec is not None:
        data = custom.with_custom(data, spec)
        key = custom.custom_key(spec.key)
    h = sc.scenario(data, key)
    background = data.scenario(h.background)
    assert background is not None
    founder = sc.founder_spec(h, DEFAULT_FOUNDER)
    state, entries = new_game(
        save_name="balance",
        master_seed=seed,
        scenario=background,
        difficulty="standard",
        company_name="Balance Co",
        founder=founder,
        balance=loaded.balance,
        data=data,
        start_year=sc.world_year(h),
        hq_city=h.hq_city,
        family=sc.family_spec(h),
    )
    mode = sc.scenario_spec(key, data) if spec is None else custom.mode_spec(spec, sf.sha256(spec))
    state, opening = start_mode(
        state, entries, mode, founder, RngFactory(seed), loaded.balance, data, custom=spec
    )
    if spec is not None:  # the game plays with the data its save would load
        from tst.db.custom_io import data_with

        loaded = data_with(loaded, spec)
    game = Game(loaded, state, dict(apply_entries({}, opening)))
    game.record_value()
    return game


def start_historical(loaded: LoadedData, key: str, seed: int) -> Game:
    return _start(loaded, key, seed, None)


def start_custom(loaded: LoadedData, spec: CustomScenario, seed: int) -> Game:
    return _start(loaded, spec.key, seed, spec)


def opened_and_saved(loaded: LoadedData, key: str) -> CustomScenario:
    """A scenarios.yaml entry opened in the editor and saved unchanged: through the file text."""
    h = loaded.game_data.historical_scenario(key)
    assert h is not None
    spec = custom.from_historical(h)
    return sf.validate(sf.parse(sf.canonical(spec)), loaded.balance, loaded.game_data)


def as_original(state: GameState, key: str) -> GameState:
    """A custom game's state with its mode record read as the original scenario's."""
    mode = state.mode
    if mode is None or not mode.custom:
        return state
    return replace(state, mode=replace(mode, scenario=key, scenario_sha256=None, growth_delta=()))


def month_digests(game: Game, months: int, key: str | None = None) -> list[str]:
    """Each month's full-state digest (M30's), the start month's first."""
    digester = m30.Digester()

    def digest() -> str:
        state = digester.digest(as_original(game.state, key) if key is not None else game.state)
        balances = digester.digest(game.balances)
        digester.next_month()
        return hashlib.sha256(state + balances).hexdigest()

    out = [digest()]
    start = game.state.turn
    while game.state.turn < start + months and not game.state.ended:
        game.turn()
        out.append(digest())
    return out


@dataclass(frozen=True, slots=True)
class RoundTrip:
    key: str
    seed: int
    months: int
    identical: bool
    first_difference: str | None


def round_trip(job: tuple[str, int, int]) -> RoundTrip:
    key, seed, months = job
    loaded = m30.loaded()
    want = month_digests(start_historical(loaded, key, seed), months)
    spec = opened_and_saved(loaded, key)
    got = month_digests(start_custom(loaded, spec, seed), months, key)
    diff = m30.first_difference(got, want)
    return RoundTrip(key, seed, len(got) - 1, diff is None and len(got) == len(want), diff)


def round_trips(
    keys: Sequence[str] | None = None,
    seeds: Sequence[int] = SEEDS,
    months: int = ROUND_TRIP_MONTHS,
    workers: int = 1,
) -> list[RoundTrip]:
    loaded = m30.loaded()
    keys = keys if keys is not None else [h.key for h in loaded.game_data.historical]
    jobs = [(k, s, months) for k in keys for s in seeds]
    if workers <= 1:
        return [round_trip(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(round_trip, jobs))


# --- Target 3: one custom scenario for the determinism job -----------------------------------


def determinism_spec(loaded: LoadedData) -> CustomScenario:
    """The EV maker edited: double the cash, a removed incumbent, a richer and a weaker rival,
    a bigger cloud market growing faster, two added rivals and the Hard rivals rule."""
    h = loaded.game_data.historical_scenario("ev_maker")
    assert h is not None
    base = custom.from_historical(h)
    names = sorted(c.name for c in loaded.game_data.incumbents)
    raw = base.model_dump(mode="json")
    raw["key"] = "determinism-ev"
    raw["label"] = "The EV maker, edited"
    raw["cash_dollars"] = base.cash_dollars * 2
    raw["overrides"] = {
        "company": {"name": "Volt Motors"},
        "rivals": {
            names[0]: {"present": False},
            names[1]: {"cash_mult": 2.0},
            names[2]: {"quality_delta": -10.0},
        },
        "markets": {"cloud_hosting": {"market_mult": 1.5, "growth_delta": 0.05}},
        "added_rivals": [{"category": "dev_tools", "count": 2}],
        "rules": {"challenges": ["hard_rivals"]},
    }
    return sf.validate(sf.from_dict(raw), loaded.balance, loaded.game_data)


def custom_game(seed: int = DETERMINISM_SEED) -> Game:
    loaded = m30.loaded()
    return start_custom(loaded, determinism_spec(loaded), seed)


# --- Target 4: sandbox past 2069 (66.3, sub-task 5) --------------------------------------------

INT64: Final = 2**63 - 1  # SQLite's INTEGER: every money column holds a signed 64-bit integer
ECONOMY_MARGIN: Final = 1000  # 66.3: the 2100 economy at least this many times below the limit
SANDBOX_END: Final = 1092  # the turn after December 2100 (January 2101)
LATE_MONTHS: Final = 12  # the late months timed: the year to December 2100


@dataclass(frozen=True, slots=True)
class LongPlay:
    seed: int
    reached: str  # the last month played
    error: str | None
    largest_int: int  # the largest integer anywhere in the state or the balances
    largest_balance: int  # the largest ledger balance (cents)
    revenue_2100: int  # every company's revenue in 2100, cents (the economy's size)
    late_ms: tuple[int, ...]  # each of 2100's months in memory, ms
    ended: str  # the game state at the end
    # 66.4 target 1 on the way: the months to December 2069 against M45's dynasty fixture
    # (None: all 720 identical; else the first difference)
    m45_difference: str | None = None


def _largest_int(value: object) -> int:
    """The largest absolute integer in a state (every field, tuple and mapping walked)."""
    import dataclasses

    best = 0
    stack = [value]
    seen: set[int] = set()
    while stack:
        v = stack.pop()
        if isinstance(v, bool) or v is None or isinstance(v, float | str):
            continue
        if isinstance(v, int):
            best = max(best, abs(v))
            continue
        if id(v) in seen:
            continue
        seen.add(id(v))
        if dataclasses.is_dataclass(v) and not isinstance(v, type):
            stack.extend(getattr(v, f.name) for f in dataclasses.fields(v))
        elif isinstance(v, tuple | list | frozenset | set):
            stack.extend(v)
        elif isinstance(v, dict):
            stack.extend(v.keys())
            stack.extend(v.values())
    return best


def _revenue(game: Game) -> int:
    """Every company's revenue so far (credits on revenue accounts), cents."""
    kinds = {a.code: a.type for a in game.loaded.game_data.accounts}
    return -sum(v for (_, a), v in game.balances.items() if kinds.get(a) == "revenue")


def sandbox_2100(seed: int, until: int = SANDBOX_END) -> LongPlay:
    """M45's dynasty game (full_integrator with a family) to December 2069, continued in
    sandbox (`ContinueSandbox`) and played to December 2100, in memory."""
    return play_2100(seed, until)[1]


def play_2100(seed: int, until: int = SANDBOX_END) -> tuple[Game, LongPlay]:
    """`sandbox_2100` with the game kept (tools/m52_save.py writes it to a save)."""
    import time

    from tst.balance import m37, m45
    from tst.sim.calendar import format_turn
    from tst.sim.dynasty.mode import continue_dynasty, continue_sandbox, final_turn

    loaded = m30.loaded()
    game = m37._family_game(seed)
    game.state = continue_dynasty(game.state, loaded.balance)
    script = m30.strategy(m37.STRATEGY)
    error = None
    late: list[int] = []
    revenue_start = 0
    digester = m30.Digester(m45.SKIP)  # M45's own digest of each month to 2069
    want = m45.recorded().get(m45.key(seed), [])
    got: list[str] = []
    try:
        while game.state.turn < until:
            if game.state.turn == final_turn(loaded.balance) and game.state.ended:
                game.state = continue_sandbox(game.state, loaded.balance)
            if game.state.ended:
                break
            if game.state.turn == until - LATE_MONTHS:
                revenue_start = _revenue(game)
            script(game)
            started = time.perf_counter()
            game.turn()
            if len(got) < len(want):
                got.append(m30.month_digest(digester, game))
            if game.state.turn > until - LATE_MONTHS:
                late.append(round((time.perf_counter() - started) * 1000))
    except Exception as exc:  # the run reports the error rather than stopping the table
        log.exception("sandbox_2100 seed %s", seed)
        error = f"{type(exc).__name__}: {exc}"
    return game, LongPlay(
        seed=seed,
        reached=format_turn(game.state.turn - 1),
        error=error,
        largest_int=max(_largest_int(game.state), max(map(abs, game.balances.values()))),
        largest_balance=max(map(abs, game.balances.values())),
        revenue_2100=_revenue(game) - revenue_start,
        late_ms=tuple(late),
        ended=game.state.save_meta.game_state,
        m45_difference=m30.first_difference(got, want) if len(got) == len(want) else "short",
    )


def long_play(seeds: Sequence[int] = SEEDS, workers: int = 3) -> list[LongPlay]:
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(sandbox_2100, seeds))
