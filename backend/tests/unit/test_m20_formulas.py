"""M20 (formulas.md 36): each recipe's unit cost at a given power index (the worked examples in
formulas.md 36.6), the yield rule for semiconductor grades, the ramp, the incident chance and
the derived goods' prices."""

from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.refining import formulas as rf

# recipe -> (input price, cents a unit), {power index: unit cost in cents} at full output, with
# fixed cost and depreciation spread over a year's output (formulas.md 36.6)
WORKED = {
    "silicon_smelter": (4_000, {1.0: 262_100.0, 1.5: 302_900.0}),
    "poly_plant_semi": (280_000, {1.0: 5_940.0, 1.5: 6_280.0}),
    "poly_plant": (280_000, {1.0: 1_174.1111, 1.5: 1_378.1111}),
    "wafer_plant": (6_500, {1.0: 7_098.6667, 1.5: 7_149.6667}),
    "li_converter": (700_000, {1.0: 1_073_029.42, 1.5: 1_083_229.42}),
    "co_refinery": (2_800_000, {1.0: 3_424_111.08, 1.5: 3_437_711.08}),
    "ree_separator": (600_000, {1.0: 4_558.0, 1.5: 4_592.0}),
    "byproduct_gallium": (0, {1.0: 50_673.3333, 1.5: 50_843.3333}),
    "byproduct_germanium": (0, {1.0: 118_273.3333, 1.5: 118_443.3333}),
}


@pytest.mark.parametrize("recipe", sorted(WORKED))
def test_each_recipe_unit_cost_matches_its_worked_example(
    loaded: LoadedData, recipe: str
) -> None:
    b = loaded.balance
    rb = b.refining
    r = rb.recipes[recipe]
    kind = b.facility.kinds[r.kind]
    price, expected = WORKED[recipe]
    fixed = r.fixed_cents / r.per_capacity_unit
    dep = kind.capex_per_unit_cents * 12 / kind.life_months / r.per_capacity_unit
    for index, cents in expected.items():
        unit = rf.unit_cost_cents(
            price,
            r.input_per_output,
            r.mwh_per_unit,
            rb.power_cents_per_mwh,
            index,
            r.other_cents,
            fixed,
            dep,
        )
        assert unit == pytest.approx(cents, abs=0.01)


def test_the_module_docstring_example() -> None:
    """formulas.py: a smelter at $40/t quartz, 12 MWh at $68, $1,000 other, $120 fixed, $150
    depreciation: $2,186; at 0.85 power $2,063.60, at 1.5 $2,594."""
    for index, dollars in ((1.0, 2186.0), (0.85, 2063.6), (1.5, 2594.0)):
        unit = rf.unit_cost_cents(4000, 2.5, 12, 6800, index, 100_000, 12_000, 15_000)
        assert unit == pytest.approx(dollars * 100)


def test_power_is_what_separates_smelter_regions(loaded: LoadedData) -> None:
    """36.5 target 2's mechanism: only power moves with the region."""
    r = loaded.balance.refining.recipes["silicon_smelter"]
    cheap = rf.power_cents(r.mwh_per_unit, loaded.balance.refining.power_cents_per_mwh, 0.85)
    europe = rf.power_cents(r.mwh_per_unit, loaded.balance.refining.power_cents_per_mwh, 1.5)
    assert europe - cheap == pytest.approx(12 * 6800 * 0.65)


def test_semiconductor_grades_halve_their_yield_below_the_process_level() -> None:
    assert rf.effective_yield(0.8, True, 39.9, 40, 0.5) == pytest.approx(0.4)
    assert rf.effective_yield(0.8, True, 40, 40, 0.5) == pytest.approx(0.8)
    assert rf.effective_yield(0.9, False, 0, 40, 0.5) == pytest.approx(0.9)  # solar grade
    # half the yield takes twice the input a unit
    assert rf.input_per_output(0.00125, 0.8, 0.4) == pytest.approx(0.0025)


def test_ramp() -> None:
    assert rf.ramp_share(9, 10, 12) == 0.0
    assert rf.ramp_share(10, 10, 12) == pytest.approx(1 / 12)
    assert rf.ramp_share(15, 10, 12) == pytest.approx(0.5)
    assert rf.ramp_share(40, 10, 12) == 1.0
    assert rf.ramp_share(10, 10, 0) == 1.0


def test_incident_chance_follows_m19s_accident_rule() -> None:
    """rate / 12 x (1.6 - 0.04 x skill) x (1.3 - coverage): skill 15 cuts it by 40% against 8."""
    at8 = rf.incident_chance(0.03, 8, 1.0, 1.6, 0.04, 1.3)
    at15 = rf.incident_chance(0.03, 15, 1.0, 1.6, 0.04, 1.3)
    assert at8 == pytest.approx(0.03 / 12 * 1.28 * 0.3)
    assert 1 - at15 / at8 == pytest.approx(1 - 1.0 / 1.28)
    assert rf.incident_chance(0.03, 20, 1.3, 1.6, 0.04, 1.3) == 0.0


def test_derived_goods_prices() -> None:
    # a concentrate: share x the refined price (x the source units in a unit)
    assert rf.derived_price_cents("share", 0.12, 7_000, 1.0, 1000, 0) == pytest.approx(840_000)
    # solar polysilicon: the semiconductor price / 5
    assert rf.derived_price_cents("divisor", 5, 6_000, 1.0, 1, 0) == pytest.approx(1_200)
    # a wafer: $110 x (0.45 + 0.55 x the polysilicon index)
    assert rf.derived_price_cents("index", 0.55, 0, 2.0, 1, 11_000) == pytest.approx(17_050)


def test_margin() -> None:
    assert rf.margin(100.0, 92.0) == pytest.approx(0.08)
    assert rf.margin(0.0, 5.0) == 0.0


def test_recipes_are_set_for_thin_margins(loaded: LoadedData) -> None:
    """Every recipe's band is 36.5 target 1's 2-15%."""
    for r in loaded.balance.refining.recipes.values():
        assert (r.margin.lo, r.margin.hi) == (0.02, 0.15)
