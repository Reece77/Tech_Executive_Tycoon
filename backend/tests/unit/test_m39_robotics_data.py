"""M39 sub-task 1 (formulas.md 53, 53.4 target 1): robotics.yaml cites a source for every value
(each number is tagged S, D, R or A; money carries its dollar year), it loads and cross-checks,
its totals agree with IFR's world figures, and history to 2025 follows it: makers' shares are
pinned, the humanoid market is closed before its era, and the robotaxi services' dates hold."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities.compute import home_region_of
from tst.sim.robotics import demand
from tst.sim.robotics import robotaxi as rt
from tst.sim.robotics.data import year_at

DATA = Path(__file__).resolve().parents[2] / "data" / "robotics.yaml"
TAGS = {"S", "D", "R", "A"}
UNTAGGED = {"cpi"}  # CPI is the file's converter (R, as vehicles.yaml's)
TEXT_KEYS = {
    "key", "label", "region", "country", "company", "origin", "owner", "era", "city",
    "driverless", "end", "ended", "month", "operator",
}  # fmt: skip


def _walk(node: Any, path: str, out: list[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if path == "" and k in UNTAGGED:
                continue
            if k in TEXT_KEYS or k == "suspended_months":
                continue
            _walk(v, f"{path}.{k}", out)
        return
    if isinstance(node, list):
        if node and isinstance(node[0], int | float) and isinstance(node[-1], str):
            if node[-1] not in TAGS:
                out.append(f"{path}: unknown tag {node[-1]!r}")
            if (path.endswith("_usd") or "_usd." in path) and len(node) != 3:
                out.append(f"{path}: money needs [value, dollar year, tag]")
            return
        for i, x in enumerate(node):
            _walk(x, f"{path}[{i}]", out)
        return
    if isinstance(node, int | float) and not isinstance(node, bool):
        out.append(f"{path}: {node!r} has no source tag")


def test_every_value_is_tagged() -> None:
    raw = yaml.safe_load(DATA.read_text())
    problems: list[str] = []
    _walk(raw, "", problems)
    assert problems == []


def test_totals_match_ifr(loaded: LoadedData) -> None:
    r = loaded.game_data.robotics
    assert r is not None
    for year, world in ((2010, 120.6), (2015, 253.7), (2021, 517.4), (2024, 542.1)):
        total = sum(x.installed_at(year) for x in r.regions)
        assert total == pytest.approx(world, rel=0.06), year  # WIR S; the rest of the world A
    china_2024 = 295.0 / 542.1  # IFR: China 54% of 2024's installations
    assert r.region("east_asia").installed_at(2024) / 542.1 > china_2024


def test_makers_pinned_to_their_shares(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    r = d.robotics
    assert r is not None
    state = replace(fresh_game(loaded), turn=ym_to_turn(2018, 7))
    state = demand.set_demand(state, b, d)
    state = demand.pin(state, b, d)
    home = home_region_of(state, b, d)
    t = year_at(state.turn)
    for maker in r.makers:
        company = next(c for c in state.companies if c.name == maker.company)
        (product,) = [
            p for p in state.company_products(company.id) if p.category == b.robotics.industrial
        ]
        for s in state.segments_of(product.id):
            market = state.market(b.robotics.industrial, s.segment)
            assert market is not None
            assert s.customers == pytest.approx(maker.share_at(home, t) * market.addressable)
            assert s.price_cents is not None


def test_humanoid_makers_have_no_price_before_the_era(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = demand.pin(replace(fresh_game(loaded), turn=ym_to_turn(2025, 6)), b, d)
    for p in state.products:
        if p.category == b.robotics.humanoid:
            assert all(s.price_cents is None and s.customers == 0 for s in state.segments_of(p.id))


def test_robotaxi_history(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    r = d.robotics
    assert r is not None
    ops = {op.key: op for op in r.robotaxi.operators}
    waymo = {s.city: s.driverless for s in ops["waymo"].services}
    assert waymo["phoenix"] == "2020-10" and waymo["san_francisco"] == "2023-08"
    assert waymo["los_angeles"] == "2024-11" and waymo["austin"] == "2025-03"
    assert ops["cruise"].services[0].end == "2023-10" and ops["cruise"].ended == "2024-12"
    assert ops["tesla"].services[0].driverless == "2025-06"
    assert ops["zoox"].services[0].driverless == "2025-09"
    assert ops["apollo_go"].services[0].driverless == "2022-08"
    state = replace(fresh_game(loaded), turn=ym_to_turn(2024, 1))
    assert rt.rival_fleet(state, "san_francisco", b, d) > 0
    # Cruise's San Francisco cars are off the road after the suspension
    before = replace(state, turn=ym_to_turn(2023, 9))
    after = replace(state, turn=ym_to_turn(2023, 11))
    cruise = ops["cruise"].services[0]
    assert cruise.running(before.turn) and not cruise.running(after.turn)
    # Waymo's 2025 rides a week across its cities: about 250,000 in April (WAYMO S (search))
    mid = ym_to_turn(2025, 4)
    total = sum(rt._service_rides(s, mid, b) for s in ops["waymo"].services)
    assert 150_000 < total < 400_000
