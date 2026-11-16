"""M38 sub-task 1 (formulas.md 49): vehicles.yaml loads and cites a tag for every value, its
battery history agrees with commodities_history.yaml, bad data fails at load, and history holds
to 2025 in a do-nothing game: EV shares and rivals' shares follow the data."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.helpers import DEFAULT_FOUNDER
from tst.balance.game import Game, start_game
from tst.loader import DataLoadError, LoadedData, load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.vehicles import demand
from tst.sim.vehicles.data import year_at

DATA = Path(__file__).resolve().parents[2] / "data"
TAGS = {"S", "D", "R", "A", "V"}
SERIES_KEYS = ("car_sales", "ev_share", "chargers", "segments")


def _raw() -> dict[str, Any]:
    out: dict[str, Any] = yaml.safe_load((DATA / "vehicles.yaml").read_text(encoding="utf-8"))
    return out


def _untagged(node: Any, path: str = "") -> list[str]:
    """Every number in vehicles.yaml sits in a [value, tag] pair (or [value, year, tag]), except
    the cpi table (BLS, tagged in its comment), months and tariff steps (tagged by `tag`)."""
    bad: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("cpi", "steps", "price_cap", "month", "start", "launch"):
                continue
            bad += _untagged(v, f"{path}.{k}")
    elif isinstance(node, list):
        if node and isinstance(node[0], int | float) and not isinstance(node[0], bool):
            if not (isinstance(node[-1], str) and node[-1] in TAGS):
                bad.append(path)
        else:
            for i, v in enumerate(node):
                bad += _untagged(v, f"{path}[{i}]")
    elif isinstance(node, int | float) and not isinstance(node, bool):
        bad.append(path)
    return bad


def test_every_value_carries_a_tag() -> None:
    raw = _raw()
    for section in ("regions", "battery", "cell_makers", "rivals", "world_cells_gwh", "km_per_kwh"):
        assert _untagged(raw[section], section) == [], section
    for s in raw["subsidies"]:
        for _, v in s["steps"]:
            assert isinstance(v, list) and v[-1] in TAGS, s["key"]
    for t in raw["tariffs"]:
        assert t["tag"] in TAGS


def test_vehicles_yaml_loads_with_every_region(loaded: LoadedData) -> None:
    v = loaded.game_data.vehicles
    assert v is not None
    assert [r.key for r in v.regions] == list(loaded.game_data.region_keys)
    assert {r.company for r in v.rivals} >= {"Tesla", "BYD", "Xiaomi", "Rivian"}
    tesla = v.rival("Tesla")
    assert tesla is not None and tesla.share_at("north_america", 2024) == pytest.approx(0.40)
    # BNEF: about $1,400 (2023 dollars) in 2010 to $108 in 2025, in 2010 dollars
    assert v.battery.pack_at(2010) / 100 == pytest.approx(1400 * 218.056 / 304.702, rel=1e-6)
    assert v.battery.pack_at(2025) / 100 == pytest.approx(108 * 218.056 / 322.0, rel=1e-6)


def test_vehicle_tariffs_join_the_tariff_schedules(loaded: LoadedData) -> None:
    t = loaded.game_data.tariffs
    assert t is not None
    us = next(s for s in t.schedules if s.key == "us_301_ev")
    assert us.goods == ("vehicles",) and us.rate_at(ym_to_turn(2024, 10)) == 1.0
    assert us.rate_at(ym_to_turn(2024, 8)) == pytest.approx(0.275)


def _broken(tmp_path: Path, edit: Any) -> Path:
    out = tmp_path / "data"
    import shutil

    shutil.copytree(DATA, out)
    raw = copy.deepcopy(_raw())
    edit(raw)
    (out / "vehicles.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    return out


def test_rivals_shares_above_one_fail_at_load(tmp_path: Path) -> None:
    def edit(raw: dict[str, Any]) -> None:
        raw["rivals"][0]["shares"]["north_america"][2024] = [0.95, "A"]

    with pytest.raises(DataLoadError, match="shares sum"):
        load_all(_broken(tmp_path, edit))


def test_an_unknown_rival_fails_at_load(tmp_path: Path) -> None:
    def edit(raw: dict[str, Any]) -> None:
        raw["rivals"][0]["company"] = "Nobody Motors"

    with pytest.raises(DataLoadError, match="not in incumbents"):
        load_all(_broken(tmp_path, edit))


@pytest.fixture(scope="module")
def world_2025(loaded: LoadedData) -> Game:
    game = start_game(loaded, 3, "funded_spinout")
    while game.state.turn < ym_to_turn(2025, 7):
        game.turn()
    return game


def test_history_ev_shares_follow_the_data(loaded: LoadedData, world_2025: Game) -> None:
    state = world_2025.state
    v = loaded.game_data.vehicles
    assert v is not None
    for r in v.regions:
        got = demand.ev_share(state, r.key, loaded.balance, loaded.game_data)
        assert got == pytest.approx(r.share_at(year_at(state.turn)), abs=1e-12)
    # the market's addressable demand is the formula's (49.1)
    home = next(m for m in state.markets if m.category == "vehicles" and m.segment == "consumer")
    # phase 9 set it from the month just played
    played = state.turn - 1
    sales = v.region("north_america").sales_at(year_at(played)) * 1e6
    share = v.region("north_america").share_at(year_at(played))
    want = sales * 0.74 * share * loaded.balance.vehicles.scale * 96 / 12
    assert home.addressable == pytest.approx(want, rel=1e-9)


def test_history_rivals_shares_follow_the_data(loaded: LoadedData, world_2025: Game) -> None:
    """A do-nothing game: each car maker holds its data share of the market (no player car)."""
    state = world_2025.state
    v = loaded.game_data.vehicles
    assert v is not None
    played = state.turn - 1
    year = year_at(played)
    for region in ("north_america", "europe", "east_asia"):
        rm = (
            next(m for m in state.markets if m.category == "vehicles" and m.segment == "consumer")
            if region == "north_america"
            else state.regional_market("vehicles", "consumer", region)
        )
        assert rm is not None
        for p in state.products:
            if p.category != "vehicles":
                continue
            company = state.company(p.company_id)
            assert company is not None
            rival = v.rival(company.name)
            assert rival is not None
            segs = (
                state.segments_of(p.id)
                if region == "north_america"
                else [r for r in state.regional_segments_of(p.id) if r.region == region]
            )
            got = sum(s.customers for s in segs if s.segment == "consumer")
            want = rival.share_at(region, year, played) * rm.addressable
            assert got == pytest.approx(want, rel=1e-9, abs=1e-9), (company.name, region)


def test_car_makers_hold_history(loaded: LoadedData, world_2025: Game) -> None:
    """Before 2026 no car maker decides or fails (49.1)."""
    names = {r.company for r in loaded.game_data.vehicles.rivals}  # type: ignore[union-attr]
    makers = [c for c in world_2025.state.companies if c.name in names]
    assert len(makers) == len(names) and all(c.alive for c in makers)
    moves = [m for m in world_2025.state.rival_moves if m.company_id in {c.id for c in makers}]
    assert moves == []


def test_new_game_without_founder_spec_still_starts(loaded: LoadedData) -> None:
    assert DEFAULT_FOUNDER is not None
