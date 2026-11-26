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
