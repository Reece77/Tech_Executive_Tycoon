"""M23a sub-task 3 (Codex review 5 findings 9-12): hidden future node economics stay out of fab
quotes; offtake prepayments and the other v3 money paths are exact; the founder's salary is
monthly; the tariff property test means something (tests/property/test_m22_invariants.py)."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from tst.balance import m21
from tst.sim.calendar import ym_to_turn
from tst.sim.fabs import market as fm
from tst.sim.fabs.actions import quote

# --- Finding 9: a fab quote for an unarrived node ----------------------------------------------


@pytest.mark.parametrize("year", [2014, 2026])
def test_a_future_nodes_quote_does_not_depend_on_its_seeded_economics(year: int) -> None:
    """A differential test: two seeds whose timelines draw different A16 capital and wafer
    prices quote the same capex and the same cost a start before A16 arrives."""
    from tst.api.fab_views import quote_out

    lg = m21.loaded()
    b, d = lg.balance, lg.game_data
    turn = ym_to_turn(year, 1)
    games = [m21.game_at(seed, turn) for seed in (1, 2)]
    tls = [fm.timeline(g.state, b, d) for g in games]
    assert tls[0].capital_cents["a16"] != tls[1].capital_cents["a16"]  # the hidden draws differ
    assert all(tl.arrival["a16"] > turn for tl in tls)
    quotes = [quote(g.state, 1, "a16", "east_asia", 10_000, b, d) for g in games]
    assert quotes[0].capex_cents == quotes[1].capex_cents
    outs = [quote_out(g.state, "a16", "east_asia", 10_000, False, lg) for g in games]
    assert outs[0].capex_cents == outs[1].capex_cents
    assert outs[0].cost_per_start_cents == outs[1].cost_per_start_cents


def test_an_arrived_nodes_quote_is_its_real_capital() -> None:
    from tst.sim.fabs import formulas as fx

    lg = m21.loaded()
    b, d = lg.balance, lg.game_data
    game = m21.game_at(1, ym_to_turn(2021, 1))
    tl = fm.timeline(game.state, b, d)
    q = quote(game.state, 1, "n5", "east_asia", 10_000, b, d)
    assert q.capex_cents == fx.capex_cents(10_000, tl.capital_cents["n5"], b.fab.capex_scale, 1.0)


# --- Finding 11: the founder's salary is monthly -----------------------------------------------


def test_a_year_of_founder_salary_reaches_the_book_once_after_tax() -> None:
    """A full year's company payroll against the personal book's after-tax receipts, from an
    independently calculated annual total."""
    from tests.helpers import fresh_game
    from tst.sim.founder import personal
    from tst.sim.state import with_employment

    lg = m21.loaded()
    state = fresh_game(lg)
    founder = state.founder_of(state.player.id)
    assert founder is not None
    job = state.employment_of(founder.id)
    assert job is not None
    annual = 12_000_000
    state = with_employment(state, replace(job, salary_cents=annual))
    tax = Fraction(str(lg.balance.personal.tax_rate))
    before = personal.cash_cents(state, founder.id)
    for _ in range(12):
        state = personal.salary_month(state, lg.balance)
    got = personal.cash_cents(state, founder.id) - before
    monthly = round(Fraction(annual, 12))
    assert got == 12 * (monthly - round(monthly * tax))
    assert got == pytest.approx(annual * (1 - tax), abs=12)  # a year's salary after tax, once


# --- Finding 10: offtake prepayments and v3 money in exact arithmetic --------------------------


def _half_even(x: Fraction) -> int:
    """An independent rational reference: x rounded half to even."""
    floor = x.numerator // x.denominator
    rest = x - floor
    if rest > Fraction(1, 2) or (rest == Fraction(1, 2) and floor % 2 == 1):
        return floor + 1
    return floor


@pytest.mark.parametrize(
    ("year", "prepay"),
    [
        (100_000_000_100, "0.085"),  # Codex: production 8,500,000,009; exact 8,500,000,008
        (100_000_000_300, "0.085"),
        (1_000_000_001, "0.05"),
        (999_999_999_999, "0.1"),
    ],
)
def test_an_offtake_prepayment_is_exact(
    year: int, prepay: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tst.balance import m22
    from tst.sim.commodities import offtake

    lg = m22.loaded()
    b, d = lg.balance, lg.game_data
    game = m21.game_at(1, ym_to_turn(2016, 1))
    assert d.suppliers is not None
    supplier = next(s for s in d.suppliers.suppliers if s.sells("copper", game.state.turn))
    monkeypatch.setattr(offtake, "value_cents", lambda *_: float(year))
    q = offtake.offtake_quote(game.state, "copper", supplier.key, 5, 1_000.0, float(prepay), b, d)
    assert q.year_value_cents == year
    assert q.prepaid_cents == _half_even(year * Fraction(prepay))


@pytest.mark.parametrize("cents", [1_001, 1_003, 123_456_789_011, 7])
@pytest.mark.parametrize("rate", ["0.5", "0.085", "0.35", "0.06", "0.1"])
def test_money_times_a_rate_rounds_half_even_once(cents: int, rate: str) -> None:
    from tst.sim.money import times

    assert times(cents, float(rate)) == _half_even(cents * Fraction(rate))
