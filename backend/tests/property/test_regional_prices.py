"""M10r finding 5: every region pair and personality factor prices exactly as the decimal
data was written, rounded half-to-even once (ADR-0003, 19.5, 19.6)."""

from __future__ import annotations

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import DATA_DIR
from tst.loader import LoadedData, load_all
from tst.sim.geo import formulas as gf

LOADED: LoadedData = load_all(DATA_DIR)
DATA = LOADED.game_data
REGIONS = [m.region for m in DATA.region_markets]
FACTORS = [None, *LOADED.balance.rivals.price_factor.values()]


def _decimal(x: float) -> Fraction:
    return Fraction(str(x))  # the YAML's decimal, e.g. 0.35 is 35/100


@settings(max_examples=500, deadline=None)
@given(
    st.integers(1, 2_000_000),
    st.sampled_from(REGIONS),
    st.sampled_from(REGIONS),
    st.sampled_from(FACTORS),
)
def test_regional_price_is_exact(
    reference: int, region: str, home: str, factor: float | None
) -> None:
    row, base = DATA.region_market(region), DATA.region_market(home)
    value = Fraction(reference) * _decimal(row.price_index) / _decimal(base.price_index)
    if factor is not None:
        value *= _decimal(factor)
    expected = max(1, round(value))
    args = () if factor is None else (factor,)
    assert gf.regional_price_cents(reference, region, home, DATA, *args) == expected


def test_every_half_cent_case_rounds_to_even() -> None:
    """Exhaustively over small references: a half cent always goes to the even cent."""
    for reference in range(1, 401):
        for region in REGIONS:
            for home in REGIONS:
                for factor in FACTORS:
                    row, base = DATA.region_market(region), DATA.region_market(home)
                    value = Fraction(reference) * _decimal(row.price_index)
                    value /= _decimal(base.price_index)
                    if factor is not None:
                        value *= _decimal(factor)
                    args = () if factor is None else (factor,)
                    got = gf.regional_price_cents(reference, region, home, DATA, *args)
                    assert got == max(1, round(value)), (reference, region, home, factor)
