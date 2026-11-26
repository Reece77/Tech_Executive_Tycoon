"""M52 sub-task 5 (formulas.md 66.3): sandbox past 2069. Continue in sandbox after December 2069,
a sandbox begun endless, the third era wave (eras.yaml's beyond_2069) gated at January 2070,
series continued by 52.2's rules to dynasty.beyond.end_year at load with every year to 2069
unchanged, and more node successors after 2069. The long run (a 2069 save to December 2100 on
seeds 1-3) is tests/balance/test_m52_balance.py (weekly)."""

from __future__ import annotations

import itertools
from dataclasses import replace

import pytest

from tests.helpers import DEFAULT_FOUNDER
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.dynasty import mode
from tst.sim.dynasty.config import DynastyBalance
from tst.sim.dynasty.markets import with_maturity
from tst.sim.errors import InvalidActionError
from tst.sim.modes.models import GameMode
from tst.sim.research import levels
from tst.sim.setup import new_game
from tst.sim.state import GameState

BEYOND = (
    "room_temperature_superconductors",
    "synthetic_biology_compute",
    "autonomous_science",
    "orbital_industry",
    "post_scarcity_software",
)


@pytest.fixture(scope="module")
def start(loaded: LoadedData) -> GameState:
    d = loaded.game_data
    state, _ = new_game(
        save_name="t",
        master_seed=52,
        scenario=d.scenario("ex_big_tech_founders"),  # type: ignore[arg-type]
        difficulty="standard",
        company_name="Kestrel",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=d,
    )
    return state


def _at_2069_end(state: GameState, loaded: LoadedData) -> GameState:
    b = loaded.balance
    dynasty = replace(state, mode=GameMode(kind="campaign", length="dynasty"))
    return mode.close_at_final(replace(dynasty, turn=mode.final_turn(b)), b)


def test_a_dynasty_game_ends_after_2069_and_continues_in_sandbox(
    start: GameState, loaded: LoadedData
) -> None:
    b = loaded.balance
    over = _at_2069_end(start, loaded)
    assert over.save_meta.game_state == "dynasty_end" and over.ended
    on = mode.continue_sandbox(over, b)
    assert on.save_meta.game_state == "active" and on.save_meta.ended_turn is None
    assert on.mode is not None and on.mode.length == "endless" and on.mode.endless
    later = replace(on, turn=ym_to_turn(2100, 12) + 1)
    assert mode.close_at_final(later, b) is later  # no end
    with pytest.raises(InvalidActionError):
        mode.continue_dynasty(on, b)
    assert not mode.at_standard_end(on, b)


def test_continue_in_sandbox_only_after_2069(start: GameState, loaded: LoadedData) -> None:
    with pytest.raises(InvalidActionError, match="only after December 2069"):
        mode.continue_sandbox(start, loaded.balance)


def test_a_sandbox_begun_endless_never_closes(start: GameState, loaded: LoadedData) -> None:
    b = loaded.balance
    sandbox = replace(start, mode=GameMode(kind="sandbox", length="endless"))
    late = replace(sandbox, turn=mode.final_turn(b) + 600)
    assert mode.close_at_final(late, b).save_meta.game_state == "active"
    plain = replace(start, mode=GameMode(kind="sandbox"))
    closed = mode.close_at_final(replace(plain, turn=mode.final_turn(b)), b)
    assert closed.save_meta.game_state == "dynasty_end"  # as before M52


def test_the_third_wave_follows_every_other_era(loaded: LoadedData) -> None:
    keys = [e.key for e in loaded.game_data.eras.eras]
    assert tuple(keys[-len(BEYOND) :]) == BEYOND
    assert keys.index("ambient_ai") < keys.index(BEYOND[0])


@pytest.mark.parametrize("key", BEYOND)
def test_the_third_wave_is_in_play_only_from_2070(loaded: LoadedData, key: str) -> None:
    era = next(e for e in loaded.game_data.eras.eras if e.key == key)
    assert era.window is not None and era.window[0][0] >= 2070 and era.window[1][0] <= 2120
    b = loaded.balance
    assert not levels.in_play(era, ym_to_turn(2069, 12), b)
    assert levels.in_play(era, ym_to_turn(2070, 1), b)
    second = next(e for e in loaded.game_data.eras.eras if e.key == "ambient_ai")
    assert levels.in_play(second, ym_to_turn(2040, 1), b)  # the second wave as before


def test_growth_continues_past_2069_and_is_unchanged_before(loaded: LoadedData) -> None:
    b = loaded.balance
    rule = b.dynasty
    old = DynastyBalance.model_validate(
        {**rule.model_dump(), "beyond": {**rule.beyond.model_dump(), "end_year": rule.end_year}}
    )
    cats = loaded.game_data.categories
    mine, _ = with_maturity(cats, loaded.game_data.eras, rule)
    theirs, _ = with_maturity(cats, loaded.game_data.eras, old)
    for a, c in zip(mine, theirs, strict=True):
        for year in range(2010, rule.end_year + 1):
            assert a.growth_in(year) == c.growth_in(year)
    devices = next(c for c in cats if c.key == "devices")
    assert devices.growth_by_year is not None and max(devices.growth_by_year) == 2120
    assert devices.growth_in(9000) == devices.growth_in(2120)  # no upper bound below 9999


def test_research_baselines_continue_by_decade(loaded: LoadedData) -> None:
    tech = loaded.game_data.tech
    assert tech is not None
    for d in tech.domains:
        years = sorted(y for y in d.baseline.per_year if y >= 2070)
        assert years and years[-1] <= 2120


def test_more_node_successors_after_2069(loaded: LoadedData) -> None:
    nodes = loaded.game_data.nodes
    assert nodes is not None
    later = [n for n in nodes.dynasty_future if n.start_turn >= ym_to_turn(2070, 1)]
    assert [n.key for n in later] == ["atomic5", "atomic6", "atomic7", "atomic8"]
    starts = [n.start_turn for n in nodes.dynasty_future]
    gaps = [b - a for a, b in itertools.pairwise(starts)]
    assert all(g2 > g1 for g1, g2 in itertools.pairwise(gaps))  # slowing
    first_six = [n.key for n in nodes.dynasty_future][:6]
    assert first_six == ["a2", "a1", "atomic1", "atomic2", "atomic3", "atomic4"]


REAL_MONEY = frozenset({"llm_call_log", "coo_answer"})


def test_every_money_column_is_a_64_bit_integer() -> None:
    """66.3's overflow guard: every money column (cents, millicents) is an INTEGER, which
    SQLite stores as a signed 64-bit value; none is a float or text. The LLM logs' costs are
    real API spend in fractional cents, not game money."""
    from sqlalchemy import Integer

    from tst.db.models import Base

    money = [
        (t.name, c.name, c.type)
        for t in Base.metadata.tables.values()
        for c in t.columns
        if c.name.endswith(("_cents", "_millicents")) and t.name not in REAL_MONEY
    ]
    assert len(money) > 20
    assert [m for m in money if not isinstance(m[2], Integer)] == []
