"""docs/formulas.md 25.10 worked examples and the 25 tables (M13 sub-task 1)."""

from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.markets_public import formulas as pf
from tst.sim.rng import STREAM_IDS


def test_fundamental_value_example(loaded: LoadedData) -> None:
    """ARR $120M, growth 45%, operating margin -5%, base rate 1.5%, climate 1.2:
    m = (2 + 11.25 - 0.75 + 0.75) x 1.2 = 13.25 x 1.2 = 15.9, so V_f = $1.908B."""
    # 25.3's coefficients (balance.yaml tunes growth to 18 and margin to 5 for 25.9 target 4)
    mb = loaded.balance.public.multiple.model_copy(update={"growth": 25, "margin": 15})
    m = pf.multiple(0.45, -0.05, 1.5, 1.2, mb)
    assert m == pytest.approx(15.9)
    assert pf.fundamental_value_cents(120_000_000_00, m) == 1_908_000_000_00
    tuned = pf.multiple(0.45, -0.05, 1.5, 1.2, loaded.balance.public.multiple)
    assert tuned == pytest.approx((2 + 18 * 0.45 - 5 * 0.05 + 0.75) * 1.2)


def test_multiple_clamps_before_the_climate(loaded: LoadedData) -> None:
    mb = loaded.balance.public.multiple
    assert pf.multiple(5.0, 0.5, 0.0, 1.0, mb) == pytest.approx(30)  # held at 30
    assert pf.multiple(-1.0, -1.0, 8.0, 0.8, mb) == pytest.approx(0.8)  # 1 x v
    # a higher base rate lowers the multiple: 1.5 per point above 2%
    assert pf.multiple(0.3, 0.1, 3.0, 1.0, mb) == pytest.approx(
        pf.multiple(0.3, 0.1, 2.0, 1.0, mb) - 1.5
    )


def test_listing_example(loaded: LoadedData) -> None:
    """100M shares before, 15% sold: 17.65M new shares. A middle offer at V_f / 117.65M =
    $16.22 raises $286M before a 6% fee ($269M net). Demand 1.4 gives r = +10%, closing
    at $17.84."""
    ib = loaded.balance.ipo
    new = pf.new_shares(100_000_000, ib.share_sold["middle"])
    assert new == 17_647_059  # 17.65M
    bank = next(b for b in loaded.game_data.banks if b.fee == 0.06)
    assert bank.quality == 1.0
    price = pf.offer_price_cents(
        1_908_000_000_00, 100_000_000 + new, bank.quality, ib.ambition["middle"], 0.0
    )
    assert price == 16_22
    gross = price * new
    assert gross == pytest.approx(286_000_000_00, rel=0.002)
    fee = pf.fee_cents(gross, bank.fee)
    assert gross - fee == pytest.approx(269_000_000_00, rel=0.002)
    r = pf.first_day_return(1.4, ib.ambition["middle"], ib.first_day)
    assert r == pytest.approx(0.10)
    assert round(price * (1 + r)) == 17_84


def test_first_day_bounds_and_ambition(loaded: LoadedData) -> None:
    fd = loaded.balance.ipo.first_day
    assert pf.first_day_return(3.0, 0.9, fd) == pytest.approx(0.6)  # 0.5 + 0.1
    assert pf.first_day_return(0.3, 1.15, fd) == pytest.approx(-0.3)  # held at -30%
    assert pf.first_day_return(1.0, 1.15, fd) == pytest.approx(-0.15)  # high ambition
    assert pf.first_day_return(1.0, 0.9, fd) == pytest.approx(0.10)  # low ambition


def test_book_demand_and_words(loaded: LoadedData) -> None:
    ib = loaded.balance.ipo
    assert pf.book_demand(0.0, 1.0, ib.demand) == pytest.approx(1.0)
    assert pf.book_demand(0.0, 1.5, ib.demand) == pytest.approx(1.3)  # 1 + 0.6 x 0.5
    assert pf.book_demand(-10.0, 1.0, ib.demand) == pytest.approx(0.3)
    assert pf.book_demand(20.0, 1.0, ib.demand) == pytest.approx(3.0)
    assert pf.demand_word(0.5, ib) == "weak"
    assert pf.demand_word(1.35, ib) == "strong"
    assert pf.demand_word(2.5, ib) == "very strong"
    assert ib.raise_min_demand == 1.3


def test_earnings_example(loaded: LoadedData) -> None:
    """Guidance $32M, actual $33M (s = +3.1%), margin on guidance: x (1 + 0.094)."""
    eb = loaded.balance.public.earnings
    s = pf.surprise(33_000_000_00, 32_000_000_00)
    assert s == pytest.approx(0.03125)
    sm = pf.margin_surprise_points(1500, 1500)
    assert pf.earnings_jump(s, sm, eb) == pytest.approx(0.094, abs=0.0005)
    assert pf.result_of(s, eb) == "beat"
    assert pf.result_of(-0.03, eb) == "miss"
    assert pf.result_of(-0.01, eb) == "inline"
    assert pf.earnings_jump(-0.5, 0.0, eb) == -0.25
    assert pf.earnings_jump(0.5, 0.0, eb) == 0.20
    assert pf.earnings_jump(0.0, 5.0, eb) == pytest.approx(0.1)  # 0.02 a point


def test_price_sentiment_and_analysts(loaded: LoadedData) -> None:
    pb = loaded.balance.public
    assert pf.share_price_cents(1_908_000_000_00, 117_647_059, 1.0) == 16_22
    assert pf.sentiment_step(1.5, 0.0, pb.sentiment) == pytest.approx(1.45)  # toward 1.0
    assert pf.sentiment_step(1.0, -100.0, pb.sentiment) == 0.5
    assert pf.sentiment_step(1.0, 100.0, pb.sentiment) == 1.8
    ab = pb.analysts
    assert pf.analyst_count(50_000_000_000, ab) == 3
    assert pf.analyst_count(4 * ab.base_cap_cents, ab) == 5
    assert pf.analyst_count(10**15, ab) == 8
    assert pf.rating(1200, 1000, ab) == "buy"
    assert pf.rating(1000, 1000, ab) == "hold"
    assert pf.rating(850, 1000, ab) == "sell"


def test_keys_and_streams(loaded: LoadedData) -> None:
    b = loaded.balance
    assert b.ipo.min_arr_cents == 80_000_000_00
    assert b.ipo.hire_energy == 10
    assert b.public.earnings.guidance_energy == 4
    assert (b.public.capital.buyback_energy, b.public.capital.dividend_energy) == (6, 4)
    assert b.public.capital.secondary_energy == 10
    assert (b.ceo.appoint_energy, b.ceo.override_energy, b.ceo.chair_energy) == (10, 6, 40)
    assert {bank.name for bank in loaded.game_data.banks} == {
        "Goldman Sachs",
        "Morgan Stanley",
        "J.P. Morgan",
    }
    assert STREAM_IDS["ipo"] == 33
    assert STREAM_IDS["market_sentiment"] == 34
    assert 35 not in STREAM_IDS.values()  # reserved for lane B
