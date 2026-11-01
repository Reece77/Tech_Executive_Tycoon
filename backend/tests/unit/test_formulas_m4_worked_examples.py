"""docs/formulas.md 14.10 worked examples (noise off), plus the M4 data tables."""

from __future__ import annotations

from fractions import Fraction

import pytest

from tst.loader import LoadedData
from tst.sim.finance import formulas as f

POOL_TARGET = Fraction(1, 10)


def test_investors_and_climate_match_formulas_tables(loaded: LoadedData) -> None:
    firms = loaded.game_data.investors
    assert [x.name for x in firms] == [
        "SV Angel",
        "First Round Capital",
        "Union Square Ventures",
        "Founders Fund",
        "Accel Partners",
        "Benchmark",
        "Sequoia Capital",
        "Andreessen Horowitz",
        "Kleiner Perkins",
        "Greylock Partners",
        # M10 (20.2): growth investors, appended
        "Insight Partners",
        "General Atlantic",
        "Tiger Global",
        "DST Global",
        "SoftBank Vision Fund",
    ]
    a16z = loaded.game_data.firm("a16z")
    assert (a16z.series, a16z.check_min_cents, a16z.check_max_cents) == (
        ("a", "b"),
        500_000_000,
        3_000_000_000,
    )
    assert (a16z.bias, a16z.response, a16z.patience) == (1.15, 0.35, 0)
    assert loaded.game_data.firm("kleiner").patience == -5
    # M10: the climate table moved into macro_history.yaml unchanged (20.1); after 2025 the
    # macro layer sets it (tests/unit/test_formulas_m10_worked_examples.py).
    climate = loaded.game_data.macro_history.climate  # type: ignore[union-attr]
    assert [climate[y] for y in (2010, 2015, 2021, 2023, 2025)] == [0.90, 1.25, 1.60, 0.75, 1.0]


def test_scenario_cap_tables(loaded: LoadedData) -> None:
    caps = {s.id: s.cap_table for s in loaded.game_data.scenarios}
    assert (caps["garage_bootstrap"].founder, caps["garage_bootstrap"].pool) == (
        9_000_000,
        1_000_000,
    )
    big = caps["ex_big_tech_founders"]
    assert (big.founder, big.others[0].name, big.others[0].shares) == (
        8_500_000,
        "Former colleagues",
        500_000,
    )
    seed = caps["funded_spinout"].seed
    assert seed is not None and (seed.lead, seed.shares) == ("first_round", 2_000_000)
    assert seed.amount_cents // seed.shares == 75  # $0.75 a share
    for cap in caps.values():
        assert cap.total == loaded.balance.finance.initial_fd_shares


def test_dilution_through_a_safe_and_three_rounds() -> None:
    """The 14.10 table, to the share."""
    founder, fd, unallocated = 9_000_000, 10_000_000, 600_000  # 400,000 of 1,000,000 granted
    safe = f.safe_fraction([(50_000_000, 500_000_000)])  # $500k at a $5M post-money cap
    assert safe == Fraction(1, 10) and founder / fd == 0.9

    seed = f.close_round(fd, safe, unallocated, 600_000_000, 200_000_000, POOL_TARGET)
    assert (seed.pool_shares, seed.safe_shares, seed.new_shares, seed.fd_after) == (
        1_034_783,
        1_226_087,
        4_086_957,
        16_347_827,
    )
    assert float(seed.price) / 100 == pytest.approx(0.48936, abs=5e-6)
    assert round(100 * founder / seed.fd_after, 2) == 55.05
    unallocated += seed.pool_shares
    assert round(unallocated / seed.fd_after, 4) == 0.1
    assert round(seed.safe_shares / seed.fd_after, 4) == 0.075
    assert round(seed.new_shares / seed.fd_after, 4) == 0.25

    unallocated -= 800_000  # more options granted
    a = f.close_round(
        seed.fd_after, Fraction(0), unallocated, 1_600_000_000, 500_000_000, POOL_TARGET
    )
    assert (a.pool_shares, a.safe_shares, a.new_shares, a.fd_after) == (
        1_508_914,
        0,
        5_580_232,
        23_436_973,
    )
    assert float(a.price) / 100 == pytest.approx(0.89602, abs=5e-6)
    assert round(100 * founder / a.fd_after, 2) == 38.40
    unallocated += a.pool_shares
    assert round(unallocated / a.fd_after, 4) == 0.1

    unallocated -= 1_000_000
    b = f.close_round(
        a.fd_after, Fraction(0), unallocated, 6_000_000_000, 1_500_000_000, POOL_TARGET
    )
    assert (b.pool_shares, b.safe_shares, b.new_shares, b.fd_after) == (
        1_812_485,
        0,
        6_312_364,
        31_561_822,
    )
    assert float(b.price) / 100 == pytest.approx(2.37629, abs=5e-6)
    assert round(100 * founder / b.fd_after, 2) == 28.52
    assert round((unallocated + b.pool_shares) / b.fd_after, 4) == 0.1
    assert round(b.new_shares / b.fd_after, 4) == 0.2


def test_investors_base_value(loaded: LoadedData) -> None:
    fb = loaded.balance.finance
    mrr_now = 15_083_333  # ARR $1.81M
    mrr_then = round(mrr_now / 1.068**6)
    g6 = f.growth_6(mrr_now, mrr_then, fb)
    assert round(mrr_now / mrr_then, 4) == pytest.approx(1.4840, abs=1e-4)
    assert g6 == pytest.approx(1.2022, abs=1e-3)
    assert f.arr_multiple(g6, 1.0, fb) == pytest.approx(8.809, abs=2e-3)
    value = f.base_value_cents(181_000_000, g6, 1.0, True, 12, fb)
    assert value / 1e8 == pytest.approx(15.94, abs=0.01)  # $15.94M, above the floor


def test_growth_and_floor_edge_cases(loaded: LoadedData) -> None:
    fb = loaded.balance.finance
    assert f.growth_6(1000, 0, fb) == 3  # MRR six months ago was 0
    assert f.growth_6(0, 5000, fb) == 0
    assert f.arr_multiple(-1.0, 1.0, fb) == 3  # clamped low
    assert f.arr_multiple(10.0, 0.9, fb) == pytest.approx(18)  # clamped high, then climate
    assert f.value_floor_cents(False, 1, fb) == 210_000_000
    assert f.value_floor_cents(True, 45, fb) == 700_000_000  # headcount capped at 30
    assert f.base_value_cents(0, 0, 1.0, False, 1, fb) == 210_000_000


def test_safe_acceptance(loaded: LoadedData) -> None:
    sb = loaded.balance.finance.safe
    base = 450_000_000
    assert f.safe_probability(base, 540_000_000, sb) == pytest.approx(0.50, abs=5e-4)
    assert f.safe_probability(base, 450_000_000, sb) == pytest.approx(0.769, abs=5e-4)
    assert f.safe_probability(base, 700_000_000, sb) == pytest.approx(0.202, abs=5e-4)
    assert f.safe_hint(base, 450_000_000, sb) == "likely"  # ratio 1.2
    assert f.safe_hint(base, 540_000_000, sb) == "uncertain"  # ratio 1.0
    assert f.safe_hint(base, 700_000_000, sb) == "unlikely"  # ratio 0.77


def test_board_confidence(loaded: LoadedData) -> None:
    bb = loaded.balance.board
    growth = f.growth_points(0.75, 1.5, bb)  # half of expected
    assert growth == -10
    target = f.confidence_target(growth, f.runway_points(4, bb), 0, bb)
    assert target == 25
    b = bb.start
    for _ in range(6):
        b = f.next_confidence(b, target, bb)
    assert b == pytest.approx(36.8, abs=0.05)  # warning territory
    target = f.confidence_target(growth, f.runway_points(2, bb), 0, bb)
    assert target == 10
    b, months = bb.start, 0
    while b >= bb.removal_below:
        b = f.next_confidence(b, target, bb)
        months += 1
    assert (months, round(b, 1)) == (7, 22.6)
    assert [f.runway_points(m, bb) for m in (None, 12, 11.9, 6, 3, 2.9)] == [10, 10, 0, 0, -15, -30]


def test_retention(loaded: LoadedData) -> None:
    fb = loaded.balance.finance
    price = Fraction(896, 10)  # $0.896 in cents per share
    factor = f.retention_factor(75_000, price, 9_500_000, fb)
    assert factor == pytest.approx(0.646, abs=5e-4)
    assert f.retention_factor(75_000, Fraction(0), 9_500_000, fb) == 1.0  # no share price yet
    assert f.retention_factor(10_000_000, price, 9_500_000, fb) == 0.5  # floor


def test_vesting(loaded: LoadedData) -> None:
    fb = loaded.balance.finance
    assert [f.vested_shares(48_000, m, fb) for m in (0, 11, 12, 13, 47, 48, 60)] == [
        0,
        0,
        12_000,
        13_000,
        47_000,
        48_000,
        48_000,
    ]
    assert f.vested_shares(100_001, 25, fb) == 52_083  # floor
    assert f.shares_for_bp(50, 10_000_000) == 50_000
    assert f.shares_for_bp(50, 16_347_827) == 81_739


def test_term_sheet_amount_and_fees() -> None:
    assert f.offered_amount_cents(150_000_000, 50_000_000, 200_000_000, 600_000_000, 0.5) == (
        150_000_000
    )
    assert f.offered_amount_cents(150_000_000, 50_000_000, 200_000_000, 200_000_000, 0.5) == (
        100_000_000  # at most half the pre-money
    )
    assert f.offered_amount_cents(10_000_000, 50_000_000, 200_000_000, 600_000_000, 0.5) == (
        50_000_000  # at least the firm's check
    )
    assert f.round_fee_cents(200_000_000, 1_500_000, 50) == 1_500_000
    assert f.round_fee_cents(1_500_000_000, 1_500_000, 50) == 7_500_000
    assert f.response_chance(0.6, 1.6, 0.95) == 0.95
