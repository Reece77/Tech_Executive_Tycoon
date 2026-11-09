"""docs/formulas.md 19.9 worked examples, plus the M9 data as loaded (M9 sub-task 1)."""

from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.geo.formulas import (
    city_market_mid_cents,
    close_penalty_cents,
    cross_region_factor,
    fit_out_cents,
    flexible_seat_cents,
    lease_rent_cents,
    localization_cents,
    regional_d0,
    regional_growth,
    regional_price_cents,
    talent_bonus,
)


def test_lease(loaded: LoadedData) -> None:
    """50 seats in Berlin: 50 x $600 x 0.45 x 0.75 = $10,125 a month, fit-out $30,375."""
    berlin = loaded.game_data.city("berlin")
    rent = lease_rent_cents(50, berlin.rent_index, loaded.balance)
    assert rent == 1_012_500
    assert fit_out_cents(rent, loaded.balance) == 3_037_500
    assert close_penalty_cents(rent, loaded.balance) == 3_037_500


def test_flexible_space(loaded: LoadedData) -> None:
    """Flexible space is $600 x rent index a head: unchanged for a San Francisco HQ (19.2)."""
    data = loaded.game_data
    assert flexible_seat_cents(data.city("san_francisco").rent_index, loaded.balance) == 60_000
    assert flexible_seat_cents(data.city("bangalore").rent_index, loaded.balance) == 9_000


def test_market_rate(loaded: LoadedData) -> None:
    """A senior software engineer (band mid $115,000) in Bangalore:
    `$115,000 x 0.30 x 0.876` (geo.pay_level) = $30,222 a year."""
    band = loaded.game_data.role("software_engineer").salary_band_mid_cents["senior"]
    assert band == 11_500_000
    assert loaded.balance.geo.pay_level == 0.876
    bangalore = loaded.game_data.city("bangalore")
    assert city_market_mid_cents(band, bangalore, loaded.balance) == 3_022_200


def test_regional_market(loaded: LoadedData) -> None:
    """B2B SaaS SMB in Europe: D0 = 400,000 x 0.55 = 220,000 (M10d) and p_ref = $50 x 0.90 = $45."""
    data = loaded.game_data
    market = data.category("b2b_saas").market("smb")
    assert regional_d0(market.addressable, "europe", "north_america", data) == pytest.approx(
        220_000
    )
    assert regional_price_cents(market.reference_price_cents, "europe", "north_america", data) == (
        4_500
    )
    # Relative to another home region's row (19.5): Europe home, North America is 1/0.55.
    assert regional_d0(400_000, "north_america", "europe", data) == pytest.approx(400_000 / 0.55)


def test_localization(loaded: LoadedData) -> None:
    """A cybersecurity product (sigma = 7): $80,000 x 7 / 6 = $93,333 (M10d)."""
    scope = loaded.game_data.category("cybersecurity").scope
    assert scope == 7
    assert localization_cents(scope, loaded.balance) == 9_333_333
    assert loaded.balance.markets.localize_months == 6


def test_cross_region_factor(loaded: LoadedData) -> None:
    """x max(0.85, 1 - 0.05 x (regions - 1)) (19.4)."""
    b = loaded.balance
    assert cross_region_factor(1, b) == 1.0
    assert cross_region_factor(2, b) == pytest.approx(0.95)
    assert cross_region_factor(4, b) == pytest.approx(0.85)
    assert cross_region_factor(7, b) == pytest.approx(0.85)


def test_cities_table(loaded: LoadedData) -> None:
    """19.1's table as loaded: 15 cities, then Africa's three (M15r addendum c), multipliers,
    rent and talent bonuses."""
    data = loaded.game_data
    assert len(data.cities) == 21  # M18: Perth, Santiago, Johannesburg appended
    sf, tel_aviv, shenzhen = (
        data.city("san_francisco"),
        data.city("tel_aviv"),
        data.city("shenzhen"),
    )
    assert (sf.salary_multiplier_bp, sf.rent_index) == (10_000, 1.0)
    assert talent_bonus(sf, "software_engineering", data) == 1.0
    assert talent_bonus(sf, "sales", data) == 0.5
    assert talent_bonus(sf, "leadership", data) == 0.0
    assert talent_bonus(tel_aviv, "security", data) == 1.5
    assert talent_bonus(tel_aviv, "data", data) == 0.8
    assert talent_bonus(shenzhen, "manufacturing", data) == 1.5
    assert talent_bonus(shenzhen, "software_engineering", data) == 0.0
    assert data.region_city("europe") == "london"
    assert data.region_city("africa") == "london"  # pre-M9 people keep their home city


def test_regional_growth(loaded: LoadedData) -> None:
    data = loaded.game_data
    assert regional_growth(0.20, "south_southeast_asia", data) == pytest.approx(0.32)
    assert regional_growth(0.20, "europe", data) == pytest.approx(0.20)
    assert data.region_market("africa").neighbour == "europe"


def test_regional_incumbents(loaded: LoadedData) -> None:
    """19.5's table: six regional incumbents, each listing only its own region."""
    rows = {
        c.name: (c.personality, c.builder_skill, c.products[0].category, c.products[0].regions)
        for c in loaded.game_data.incumbents[17:23]  # M12a's cloud hosts and M12b's come after
    }
    assert rows == {
        "SAP": ("premium", 13, "b2b_saas", ("europe",)),
        "Kaspersky": ("cost_leader", 13, "cybersecurity", ("europe",)),
        "Tencent": ("aggressive", 13, "consumer_apps", ("east_asia",)),
        "Alibaba": ("aggressive", 12, "fintech", ("east_asia",)),
        "Baidu": ("fast_follower", 12, "ai_models", ("east_asia",)),
        "Infosys": ("cost_leader", 11, "fintech", ("south_southeast_asia",)),
    }
    assert set(loaded.game_data.incumbents[22].products[0].segments) == {"enterprise"}
