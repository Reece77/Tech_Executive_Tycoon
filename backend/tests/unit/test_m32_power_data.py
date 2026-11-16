"""M32 sub-task 1 (formulas.md 46, ADR-0022): power.yaml loads, cites a source for every value,
converts money to 2010 dollars, and the loader rejects data that does not fit."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.conftest import DATA_DIR
from tst.loader import DataLoadError, LoadedData, load_all

POWER = DATA_DIR / "power.yaml"


def _raw() -> dict[str, Any]:
    with POWER.open(encoding="utf-8") as f:
        out: dict[str, Any] = yaml.safe_load(f)
    return out


def _tagged(value: Any) -> bool:
    """A source tag: S, D, R or A with its source (a mixed series names each year's tag)."""
    return isinstance(value, str) and any(f"{tag}:" in value for tag in ("S", "D", "R", "A"))


def test_every_plant_value_has_a_tag() -> None:
    for t in _raw()["plant_types"]:
        for field in ("capex", "fixed_om", "variable_om", "heat_rate"):
            for year, point in t.get(field, {}).items():
                assert _tagged(point[-1]), (t["key"], field, year)
        for field in ("build_months", "life_years"):
            assert _tagged(t[field][-1]), (t["key"], field)
        for region, cf in t["capacity_factor"].items():
            assert _tagged(cf[-1]), (t["key"], region)
        if "fuel_mwh" in t:
            assert _tagged(t["fuel_mwh"][-1])


def test_every_region_series_and_producer_has_a_source() -> None:
    raw = _raw()
    for r in raw["regions"]:
        for series in ("gas", "generation", "grid_intensity", "carbon", "queue"):
            assert _tagged(r[f"{series}_tag"]), (r["key"], series)
        assert _tagged(r["outages_a_year"][-1]) and _tagged(r["demand_growth"][-1])
    for p in raw["producers"]:
        assert _tagged(p["tag"]), p["key"]
    for kind, draw in raw["draws"].items():
        assert _tagged(draw[-1]), kind
    assert _tagged(raw["build_months"][-1])


def test_money_is_in_2010_dollars(loaded: LoadedData) -> None:
    pf = loaded.game_data.power
    assert pf is not None
    gas = pf.plant_type("gas")
    # EIA's 2013 conventional CC, $917 in 2012 dollars, x CPI 2010 / CPI 2012
    assert gas.capex_kw[2012] == pytest.approx(917 * 218.056 / 229.594)
    assert gas.heat_rate_at(2012) == 7050
    assert gas.intensity_at(2012) == pytest.approx(7.05 * 52.91 / 1000)  # about 0.373 t/MWh
    nuclear = pf.plant_type("nuclear")
    assert nuclear.capex_kw[2023] == pytest.approx(7861 * 218.056 / 304.702)
    assert pf.plant_type("smr").era == (2030, 2036)
    eu = pf.region("europe")
    # 2023's EU ETS average EUR 83.60 at 0.925 EUR a dollar, deflated
    assert eu.carbon_at(2023) == pytest.approx(83.60 / 0.925 * 218.056 / 304.702)
    assert pf.region("north_america").carbon_at(2020) == 0.0
    assert pf.region("east_asia").carbon_at(2020) == 0.0  # China's national ETS from 2021
    assert pf.region("east_asia").carbon_at(2021) > 0
    oz = pf.region("oceania")
    assert oz.carbon_at(2013) > 0 and oz.carbon_at(2014) > 0
    assert pf.region("north_america").gas[2022] == pytest.approx(6.45 * 218.056 / 292.655)


def test_regions_follow_regions_yaml(loaded: LoadedData) -> None:
    pf = loaded.game_data.power
    assert pf is not None
    assert [r.key for r in pf.regions] == list(loaded.game_data.region_keys)
    assert set(pf.others) == set(loaded.game_data.region_keys)
    assert {p.key for p in pf.producers}.isdisjoint(
        {c.key for c in loaded.game_data.chain_companies.companies}  # type: ignore[union-attr]
    )
    # the data-centre draws reproduce the old operating cost at the reference price (ADR-0022 1)
    ref = loaded.balance.refining.power_cents_per_mwh
    for kind in loaded.balance.power.paid_by:
        opex = loaded.balance.facility.kinds[kind].opex_per_unit_cents
        assert pf.draws[kind] * ref == pytest.approx(opex, rel=1e-3)


def _copy(tmp_path: Path) -> Path:
    target = tmp_path / "data"
    shutil.copytree(DATA_DIR, target)
    return target


def test_loader_rejects_a_region_out_of_order(tmp_path: Path) -> None:
    data = _copy(tmp_path)
    raw = _raw()
    raw["regions"] = list(reversed(raw["regions"]))
    (data / "power.yaml").write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(DataLoadError, match=r"power.yaml"):
        load_all(data)


def test_loader_rejects_a_mix_that_does_not_add_up(tmp_path: Path) -> None:
    data = _copy(tmp_path)
    raw = _raw()
    raw["producers"][0]["mix"]["gas"] = 0.9
    (data / "power.yaml").write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(DataLoadError, match="mix"):
        load_all(data)


def test_loader_rejects_an_unknown_country(tmp_path: Path) -> None:
    data = _copy(tmp_path)
    raw = _raw()
    raw["producers"][0]["country"] = "atlantis"
    (data / "power.yaml").write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(DataLoadError, match="atlantis"):
        load_all(data)
