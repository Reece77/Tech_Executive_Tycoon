"""docs/formulas.md 20.5 targets 2-5 (M10), nightly; tools/m10_targets.py prints the same.
Values recorded in the M10 brief and docs/balance-targets.md."""

from __future__ import annotations

import os

import pytest

from tst.balance import m10


def _jobs() -> int:
    return int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))


GAIN_REASON = (
    "recorded miss: debt saves +4.8 founder points (needs +5; +5.2 on main before M9): "
    "incumbents' sales abroad fund bigger rival teams, so steady grows a little slower "
    "(M9, Reece 2026-11-01); rebalance in M15"
)


@pytest.fixture(scope="module")
def dilution() -> tuple[float, float]:
    """20.5 target 2: (founder points saved by debt, extra bankruptcy points)."""
    runs = m10.run(("equity", "debt"), m10.SEEDS, _jobs())
    gain = (m10.median_bp(runs, "debt") - m10.median_bp(runs, "equity")) / 100
    risk = (m10.share(runs, "debt", "bankrupt") - m10.share(runs, "equity", "bankrupt")) * 100
    print(f"20.5 target 2: {gain:+.1f} founder points, bankruptcy {risk:+.0f} points")
    return gain, risk


@pytest.mark.nightly
def test_2_debt_bankruptcy_risk(dilution: tuple[float, float]) -> None:
    assert dilution[1] <= 10


@pytest.mark.nightly
@pytest.mark.xfail(strict=False, reason=GAIN_REASON)
def test_2_debt_saves_dilution(dilution: tuple[float, float]) -> None:
    assert dilution[0] >= 5


@pytest.mark.nightly
@pytest.mark.xfail(
    strict=False,
    reason=(
        "recorded miss: 90% of seeds breach (needs 20-60%): blitzscale with venture debt goes "
        "below zero cash before its next round on 8 of 10 seeds, which breaks any cash-vs-burn "
        "covenant (Reece 2026-11-01); rebalance in M15"
    ),
)
def test_3_covenants_bite_sometimes() -> None:
    runs = m10.run(("blitz_debt",), m10.SEEDS, _jobs())
    rate = m10.share(runs, "blitz_debt", "breached")
    print(f"20.5 target 3: {rate:.0%} of seeds breach")
    assert 0.2 <= rate <= 0.6


def test_4_the_future_varies() -> None:
    """Fast (the macro layer alone), so it runs in every check."""
    future = m10.macro_future()
    print(f"20.5 target 4: {future.with_downturn}/{future.seeds}, sd {future.climate_2030_sd:.3f}")
    assert future.with_downturn >= 0.8 * future.seeds
    assert future.climate_2030_sd >= 0.15


@pytest.mark.nightly
def test_5_later_rounds_happen() -> None:
    runs = m10.run(("blitz_later",), m10.SEEDS, _jobs())
    count = m10.reached(runs, "blitz_later", "c")
    print(f"20.5 target 5: {count} of {len(m10.SEEDS)} reach a Series C")
    assert count >= 4
