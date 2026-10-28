"""M4c playtest fixes: the numbers the brief's acceptance criteria name."""

from __future__ import annotations

from dataclasses import replace
from functools import partial
from statistics import mean

import pytest

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.actions import StartRound, apply_action
from tst.sim.finance import formulas as f
from tst.sim.finance.fundraising import deliver_term_sheets
from tst.sim.hiring.formulas import energy_cost
from tst.sim.ledger import CASH
from tst.sim.rng import RngFactory
from tst.sim.state import with_company


def test_a_typical_hiring_month_costs_45_of_60(loaded: LoadedData) -> None:
    """formulas.md 6 (M4c): one job post, four interviews and two reference checks."""
    b = loaded.balance
    month = (
        energy_cost("job_post", b)
        + 4 * energy_cost("interview", b)
        + 2 * energy_cost("reference_check", b)
    )
    assert (month, b.founder.energy_per_month) == (45, 60)
    assert b.delegates.energy_per_month == 100  # delegates keep their whole month


# --- Investor heat (formulas.md 14.5, M4c) -----------------------------------------------------

HEAT_SEEDS = range(1, 51)


def test_round_heat_formula(loaded: LoadedData) -> None:
    rb = loaded.balance.finance.round
    gate = rb.gate_arr_cents["a"]
    heat = partial(f.round_heat, heat_max=rb.heat_max, seed_live=rb.heat_seed_live)
    assert heat("a", 110_000_000, gate, True) == pytest.approx(1.1)
    assert heat("a", 600_000_000, gate, True) == 3.0  # capped at heat_max
    assert heat("a", 50_000_000, gate, True) == 1.0  # never below 1
    assert heat("seed", 0, None, True) == 1.5 and heat("seed", 0, None, False) == 1.0
    assert f.response_chance(0.4, 1.0, 0.95, 3.0) == 0.95
    assert f.response_chance(0.3, 1.0, 0.95, 2.0) == pytest.approx(0.6)


def series_a_sheets(loaded: LoadedData, seed: int, arr_cents: int) -> int:
    """Term sheets a funded spinout (seed closed) gets for a Series A at this ARR."""
    state = fresh_game(loaded, seed=seed, scenario="funded_spinout")
    mrr = arr_cents // 12
    state = with_company(state, replace(state.player, mrr_history=(mrr,) * 7))
    out = apply_action(
        state,
        StartRound(1, "a", 600_000_000),
        RngFactory(seed),
        loaded.balance,
        loaded.game_data,
        {(1, CASH): 150_000_000},
        seq=1,
    )
    after, _ = deliver_term_sheets(
        out.new_state, RngFactory(seed), loaded.balance, loaded.game_data
    )
    return len(after.term_sheets)


def test_a_hot_series_a_draws_twice_the_term_sheets(loaded: LoadedData) -> None:
    """Acceptance: on the same seeds, a Series A at $6M ARR averages at least twice the term
    sheets of one at $1.1M (mean over 50 seeds)."""
    hot = mean(series_a_sheets(loaded, s, 600_000_000) for s in HEAT_SEEDS)
    cool = mean(series_a_sheets(loaded, s, 110_000_000) for s in HEAT_SEEDS)
    print(f"Series A term sheets, mean of 50 seeds: $6M ARR {hot:.2f}, $1.1M ARR {cool:.2f}")
    assert hot >= 2 * cool
