"""docs/formulas.md 28.10 worked examples and the section 28 rules as formulas (M14
sub-task 1)."""

from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.ledger import GOODWILL, INVESTMENT_SUBSIDIARIES
from tst.sim.markets_public import formulas as pf
from tst.sim.mna import formulas as mf
from tst.sim.rng import STREAM_IDS

M = 1_000_000_00  # $1M in cents


def test_startup_price_example(loaded: LoadedData) -> None:
    """ARR $4M, growth 60%, margin -20%, base rate 2%, climate 1.0: m = 2 + 25 x 0.6 +
    15 x (-0.2) - 0 = 14, so V_f = $56M. A fast_follower founder with ambition 14:
    p = 0.25 + 0.08 = 0.33, reservation $74.5M; with 4 months of cash p = 0.08, $60.5M."""
    mb = loaded.balance.mna
    # 25.3's coefficients (balance.yaml tunes growth to 18 and margin to 5, M13)
    multiple = loaded.balance.public.multiple.model_copy(update={"growth": 25, "margin": 15})
    m = pf.multiple(0.6, -0.2, 2.0, 1.0, multiple)
    assert m == pytest.approx(14)
    value = pf.fundamental_value_cents(4 * M, m)
    assert value == 56 * M
    p = mf.founder_premium(14, mb)
    assert p == pytest.approx(0.33)
    assert mf.reservation_cents(value, p, False, mb) == pytest.approx(74.48 * M, abs=1)
    assert mf.distressed(4 * 100, 100, mb)  # 4 months of costs: fewer than 6
    assert mf.reservation_cents(value, p, True, mb) == pytest.approx(60.48 * M, abs=1)


def test_reservation_premiums_by_personality(loaded: LoadedData) -> None:
    mb = loaded.balance.mna
    assert {k: mf.personality_premium(k, mb) for k in mb.premium} == {
        "aggressive": 0.50,
        "premium": 0.40,
        "fast_follower": 0.30,
        "cost_leader": 0.20,
    }
    assert mf.founder_premium(10, mb) == pytest.approx(0.25)


def test_antitrust_example(loaded: LoadedData) -> None:
    """SMB CRM (North America): the player 22% and the target 20%, S_c = 0.42, a review; in
    2022 the block probability is (0.42 - 0.35) / 0.15 x 1.0 = 0.47; in 2015, x 0.6 = 0.28."""
    ab = loaded.balance.antitrust
    sc = 0.22 + 0.20
    assert mf.antitrust_outcome(sc, ab) == "review"
    assert mf.block_probability(sc, 2022, ab) == pytest.approx(0.4667, abs=1e-4)
    assert mf.block_probability(sc, 2015, ab) == pytest.approx(0.28, abs=1e-4)
    assert mf.antitrust_outcome(0.34, ab) == "cleared" and mf.block_probability(0.34, 2022, ab) == 0
    assert mf.antitrust_outcome(0.50, ab) == "blocked" and mf.block_probability(0.5, 2015, ab) == 1


def test_integration_flight_example(loaded: LoadedData) -> None:
    """Distance 0.5: 0.02 + 0.03 = 5% a month; 1 - 0.95^12 = 46% over 12 months."""
    ib = loaded.balance.integration
    chance = mf.flight_chance(0.5, ib)
    assert chance == pytest.approx(0.05)
    assert 1 - (1 - chance) ** ib.months == pytest.approx(0.46, abs=0.005)
    assert mf.flight_chance(0.5, ib, brand=True) == pytest.approx(0.03)


def test_value_ranges_contain_the_truth_off_centre(loaded: LoadedData) -> None:
    mb = loaded.balance.mna
    value = 56 * M
    for u in (0.0, 0.25, 0.5, 0.75, 0.999):
        low, high = mf.value_range_cents(value, u, mb.range)
        assert low <= value <= high
        assert high - low == pytest.approx(2 * mb.range * value, abs=2)
    low, high = mf.value_range_cents(value, 0.9, mb.range)
    assert mf.midpoint_cents((low, high)) != value  # the midpoint is not the truth
    narrow = mf.value_range_cents(value, 0.9, mb.diligence.range)
    assert narrow[1] - narrow[0] < high - low


def test_board_bar_tender_and_fees(loaded: LoadedData) -> None:
    mb = loaded.balance.mna
    assert mf.board_bar(0.0, mb) == pytest.approx(0.30)
    assert mf.board_bar(1.0, mb) == pytest.approx(0.35)
    tb = mb.tender
    assert mf.tender_chance(0.15, False, tb) == 0
    assert mf.tender_chance(0.40, False, tb) == pytest.approx(0.5)
    assert mf.tender_chance(0.40, True, tb) == pytest.approx(0.3)
    assert mf.tender_chance(2.0, False, tb) == pytest.approx(0.9)
    assert mf.tender_fee_cents(100 * M, tb) == 1 * M
    assert mf.premium_over(130 * M, 100 * M) == pytest.approx(0.30)


def test_diligence_cost_and_acquihire(loaded: LoadedData) -> None:
    mb = loaded.balance.mna
    assert mf.diligence_cost_cents(56 * M, mb) == 28 * M // 100  # 0.5% = $280,000
    assert mf.diligence_cost_cents(1 * M, mb) == 50_000_00  # at least $50,000
    assert mf.acquihire_value_cents(2 * M, 4, mb) == 2 * M + 4 * 150_000_00


def test_integration_rules(loaded: LoadedData) -> None:
    ib = loaded.balance.integration
    assert mf.blended_lead(30.0, 10.0, ib) == pytest.approx(32.0)
    assert mf.personality_distance([2.0, -2.0], ib) == pytest.approx(0.5)
    assert mf.personality_distance([20.0], ib) == 1.0
    assert mf.clash_step(60.0, 40.0, 0.5, ib) == pytest.approx(59.0)
    assert mf.goodwill_cents(74 * M, 20 * M) == 54 * M


def test_streams_and_accounts(loaded: LoadedData) -> None:
    assert (STREAM_IDS["mna"], STREAM_IDS["integration"], STREAM_IDS["rival_mna"]) == (37, 38, 39)
    codes = {a.code for a in loaded.game_data.accounts}
    assert {GOODWILL, INVESTMENT_SUBSIDIARIES} <= codes
    listed = {c.name: c.listed_from for c in loaded.game_data.incumbents}
    assert listed["Facebook"] == (2012, 5) and listed["Atlassian"] == (2015, 12)
    assert listed["Zoho"] is None  # private
