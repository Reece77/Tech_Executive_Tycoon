"""docs/formulas.md 20.6 worked examples and the 20.1 macro history (M10 sub-tasks 1-2)."""

from __future__ import annotations

import itertools
import statistics

import pytest

from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.finance import macro
from tst.sim.finance.debt import monthly_interest_cents, rate_bp, scheduled_principal
from tst.sim.finance.models import Loan
from tst.sim.rng import STREAM_IDS, RngFactory

# M4's climate.yaml, before it was folded into macro_history.yaml (formulas.md 14.3).
OLD_CLIMATE = {
    2010: 0.90, 2011: 1.00, 2012: 1.00, 2013: 1.10, 2014: 1.20, 2015: 1.25, 2016: 1.00,
    2017: 1.10, 2018: 1.20, 2019: 1.20, 2020: 1.30, 2021: 1.60, 2022: 0.90, 2023: 0.75,
    2024: 0.90, 2025: 1.00,
}  # fmt: skip


def _venture(amount: int, rate: int) -> Loan:
    return Loan(
        id=1,
        company_id=1,
        instrument="venture_debt",
        lender="svb",
        principal_cents=amount,
        balance_cents=amount,
        rate_bp=rate,
        signed_turn=24,
        term_months=36,
        interest_only_months=12,
    )


def test_venture_debt_example(loaded: LoadedData) -> None:
    """$6M after a $20M Series A at r = 0.25%: 6.25%; month-1 interest $31,250; from month 13,
    $250,000 of principal a month."""
    # formulas.md 20.6 keeps 30% of the round (M10d tuned balance.yaml to 50%)
    vb = loaded.balance.debt.venture.model_copy(update={"max_of_round_bp": 3000})
    assert 20_000_000_00 * vb.max_of_round_bp // 10_000 == 6_000_000_00
    r = rate_bp(0.25, vb.spread_bp)
    assert r == 625
    assert monthly_interest_cents(6_000_000_00, r) == 31_250_00
    loan = _venture(6_000_000_00, r)
    assert [scheduled_principal(loan, 24 + m) for m in range(12)] == [0] * 12
    assert scheduled_principal(loan, 24 + 12) == 250_000_00  # month 13


def test_ar1_step_example() -> None:
    """Climate 1.30 with shock +0.02: 1.1 + 0.95 x 0.20 + 0.02 = 1.31."""
    assert macro.ar1_step(1.30, 1.1, 0.95, 0.02) == pytest.approx(1.31)


def test_confidence_on_adoption_example(loaded: LoadedData) -> None:
    """cc = 81 gives (0.81)^0.5 = x 0.90 on consumer and SMB adoption."""
    assert macro.confidence_factor(81, loaded.balance.macro.confidence_exponent) == pytest.approx(
        0.90
    )
    assert set(loaded.balance.macro.confidence_segments) == {"consumer", "smb"}


def test_macro_balance_matches_the_table(loaded: LoadedData) -> None:
    """20.1's AR(1) parameters and downturn sizes are data."""
    mb = loaded.balance.macro
    assert (mb.rate.mean, mb.rate.phi, mb.rate.shock_sd) == (3.0, 0.97, 0.15)
    assert (mb.rate.bounds.lo, mb.rate.bounds.hi) == (0, 8)
    assert (mb.climate.mean, mb.climate.phi, mb.climate.shock_sd) == (1.1, 0.95, 0.05)
    assert (mb.confidence.mean, mb.confidence.phi, mb.confidence.shock_sd) == (100, 0.95, 2.5)
    assert (mb.ai_change.mean, mb.ai_change.phi, mb.ai_change.shock_sd) == (-0.10, 0.8, 0.08)
    d = mb.downturn
    assert (d.monthly, d.gap_months, d.months) == (0.012, 36, 12)
    assert (d.climate, d.confidence, d.rate) == (-0.04, -1.5, -0.25)
    assert STREAM_IDS["macro"] == 21


def test_history_is_the_old_climate_and_confidence_averages_100(loaded: LoadedData) -> None:
    data = loaded.game_data
    assert macro.last_history_turn(data) == ym_to_turn(2025, 12)
    for year, value in OLD_CLIMATE.items():
        for month in range(1, 13):
            m = macro.history_month(ym_to_turn(year, month), data)
            assert m is not None and m.climate == value
    base = [
        macro.history_month(t, data).confidence  # type: ignore[union-attr]
        for t in range(ym_to_turn(2010, 1), ym_to_turn(2019, 12) + 1)
    ]
    assert statistics.mean(base) == pytest.approx(100)
    rise = macro.history_month(ym_to_turn(2022, 12), data)
    assert rise is not None and rise.base_rate > 4 > macro.history_month(0, data).base_rate  # type: ignore[union-attr]
    assert macro.history_month(ym_to_turn(2026, 1), data) is None


def _run(seed: int, loaded: LoadedData, last_turn: int) -> list[macro.MacroMonth]:
    rng = RngFactory(seed)
    months: list[macro.MacroMonth] = []
    prev = None
    for turn in range(last_turn + 1):
        prev = macro.month_for(turn, prev, rng, loaded.balance, loaded.game_data)
        months.append(prev)
    return months


def test_history_on_every_seed_then_seeded_cycles(loaded: LoadedData) -> None:
    """Through 2025 the indicators equal history whatever the seed; after it the same seed
    gives the same future and another seed a different one."""
    last = ym_to_turn(2030, 12)
    end = macro.last_history_turn(loaded.game_data)
    a, b, c = (_run(s, loaded, last) for s in (1, 2, 1))
    assert a[: end + 1] == b[: end + 1]
    assert all(m == macro.history_month(m.turn, loaded.game_data) for m in a[: end + 1])
    assert a == c
    assert a[end + 1 :] != b[end + 1 :]
    mb = loaded.balance.macro
    for m in a[end + 1 :]:
        assert mb.rate.bounds.lo <= m.base_rate <= mb.rate.bounds.hi
        assert mb.climate.bounds.lo <= m.climate <= mb.climate.bounds.hi
        assert mb.confidence.bounds.lo <= m.confidence <= mb.confidence.bounds.hi
        assert m.ai_index > 0


def test_ai_index_steps_only_in_january(loaded: LoadedData) -> None:
    months = _run(5, loaded, ym_to_turn(2028, 12))
    end = macro.last_history_turn(loaded.game_data)
    for m, prev in zip(months[end + 1 :], months[end:], strict=False):
        if (m.turn - end - 1) % 12:
            assert m.ai_index == prev.ai_index


def test_downturn_spacing(loaded: LoadedData) -> None:
    """Downturns start only after 36 months without one, last 12 months, and push the
    indicators down; over many seeds some start."""
    mb = loaded.balance.macro
    starts = 0
    for seed in range(1, 41):
        months = _run(seed, loaded, ym_to_turn(2039, 12))
        begun = sorted({m.downturn_turn for m in months if m.downturn_turn is not None})
        starts += len(begun)
        for first, second in itertools.pairwise(begun):
            assert second - (first + mb.downturn.months) >= mb.downturn.gap_months
    assert starts > 0


def test_downturn_pushes_before_the_step(loaded: LoadedData) -> None:
    mb = loaded.balance.macro
    prev = macro.MacroMonth(200, 3.0, 1.1, 100.0, 1.0, -0.1, downturn_turn=195)
    m = macro.step_month(prev, 201, (0.0, 0.0, 0.0, 0.0), 0.99, mb)
    assert m.climate == pytest.approx(1.1 + 0.95 * -0.04)
    assert m.confidence == pytest.approx(100 + 0.95 * -1.5)
    assert m.base_rate == pytest.approx(3.0 + 0.97 * -0.25)
    starts = macro.step_month(
        macro.MacroMonth(200, 3.0, 1.1, 100.0, 1.0, -0.1), 201, (0.0,) * 4, 0.0, mb
    )
    assert starts.downturn_turn == 201
    blocked = macro.step_month(
        macro.MacroMonth(200, 3.0, 1.1, 100.0, 1.0, -0.1, downturn_turn=170),
        201,
        (0.0,) * 4,
        0.0,
        mb,
    )
    assert blocked.downturn_turn == 170  # ended at 182: 19 months, under the 36-month gap
