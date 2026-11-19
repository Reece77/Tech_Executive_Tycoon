"""M40 sub-task 1 (formulas.md 56, 56.4 target 1): space.yaml cites a source for every value (each
number is tagged S, D, R or A; money carries its dollar year), it loads and cross-checks, and
history to 2025 follows it: launch providers hold their shares of the world's launches, operators
their subscribers, and nobody sells before their service or direct-to-device opens."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.space import history
from tst.sim.space.data import THOUSAND, year_at

DATA = Path(__file__).resolve().parents[2] / "data" / "space.yaml"
TAGS = {"S", "D", "R", "A"}
UNTAGGED = {"cpi"}  # CPI is the file's converter (R, as robotics.yaml's)
TEXT_KEYS = {
    "key", "label", "company", "origin", "kind", "first", "first_launch", "service", "month",
    "open", "first_flight", "retired", "reusable_from", "vehicle", "bought_vehicle", "year",
}  # fmt: skip
FLAGS = {"d2d", "target"}


def _walk(node: Any, path: str, out: list[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if path == "" and k in UNTAGGED:
                continue
            if k in TEXT_KEYS or k in FLAGS:
                continue
            _walk(v, f"{path}.{k}", out)
        return
    if isinstance(node, list):
        if node and isinstance(node[0], int | float) and isinstance(node[-1], str):
            if node[-1] not in TAGS:
                out.append(f"{path}: unknown tag {node[-1]!r}")
            if ("_usd" in path) and len(node) != 3:
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


def test_every_entry_names_a_source() -> None:
    """Every tagged line carries a comment naming its source or basis (the file's legend)."""
    lines = DATA.read_text().splitlines()
    bare = [
        n
        for n, line in enumerate(lines, 1)
        if any(f", {t}]" in line for t in TAGS)
        and "#" not in line
        and not lines[n - 2].lstrip().startswith("#")  # a comment block just above
        and not line.lstrip().startswith(("20", "- {"))  # year rows under a sourced block
    ]
    assert bare == []


def test_history_figures(loaded: LoadedData) -> None:
    f = loaded.game_data.space
    assert f is not None
    world = f.launch.world
    assert (world[2010], world[2015], world[2020], world[2023], world[2025]) == (
        74,
        87,
        114,
        223,
        330,
    )
    spacex = f.launch.provider("SpaceX")
    assert spacex is not None and spacex.launches[2024] == 134 and spacex.launches[2025] == 165
    starlink = f.constellation("starlink")
    assert starlink is not None
    assert starlink.subscribers[2022] == 1000 and starlink.subscribers[2025] == 8900
    f9 = f.launch.vehicle("falcon9")
    assert f9 is not None and f9.payload_kg == 22800
    # Falcon 9 about $2,720 a kg (2018, SLMC S) in 2010 dollars: $62M (2016) / 22.8 t
    assert f9.cost_per_kg_at(2016) / 100 == pytest.approx(2720 * 218.056 / 240.007, rel=0.05)
    shuttle = f.launch.vehicle("shuttle")
    assert shuttle is not None and shuttle.cost_per_kg_at(2010) / 100 > 50_000
    assert f.d2d.open == "2025-07"


def test_providers_pinned_to_their_launch_shares(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    f = d.space
    assert f is not None
    state = replace(fresh_game(loaded), turn=ym_to_turn(2020, 7))
    state = history.pin(state, b, d)
    t = year_at(state.turn)
    for provider in f.launch.providers:
        company = next(c for c in state.companies if c.name == provider.company)
        (line,) = [p for p in state.company_products(company.id) if p.category == b.space.launch]
        for s in state.segments_of(line.id):
            if provider.first_turn is not None and state.turn < provider.first_turn:
                assert s.price_cents is None and s.customers == 0
                continue
            market = state.market(b.space.launch, s.segment)
            assert market is not None
            others = sum(
                x.customers
                for p in state.products
                if p.category == b.space.launch
                and state.company(p.company_id).name not in {q.company for q in f.launch.providers}
                for x in state.segments_of(p.id)
                if x.segment == s.segment
            )
            share = provider.launches_at(t) / f.launch.world_at(t)
            assert s.customers == pytest.approx(share * (market.addressable - others))


def test_starlink_follows_its_subscribers(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2024, 12))
    # a fresh game's markets are January 2010's: grow them so the pin is not capped by demand
    state = replace(
        state,
        markets=tuple(replace(m, addressable=m.addressable * 10) for m in state.markets),
        regional_markets=tuple(
            replace(m, addressable=m.addressable * 10) for m in state.regional_markets
        ),
    )
    state = history.pin(state, b, d)
    spacex = next(c for c in state.companies if c.name == "SpaceX")
    (line,) = [p for p in state.company_products(spacex.id) if p.category == b.space.broadband]
    total = sum(s.customers for s in state.segments_of(line.id)) + sum(
        s.customers for s in state.regional_segments_of(line.id)
    )
    f = d.space
    assert f is not None
    starlink = f.constellation("starlink")
    assert starlink is not None
    want = starlink.subscribers_at(year_at(state.turn)) * THOUSAND * b.space.scale
    assert total == pytest.approx(want, rel=0.01)


def test_nobody_sells_before_service_or_d2d(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = history.pin(replace(fresh_game(loaded), turn=ym_to_turn(2019, 1)), b, d)
    for p in state.products:
        name = state.company(p.company_id).name
        if p.category == b.space.broadband and name in {
            "SpaceX",
            "Amazon Kuiper",
            "Eutelsat OneWeb",
        }:
            assert all(s.price_cents is None and s.customers == 0 for s in state.segments_of(p.id))
    later = history.pin(replace(fresh_game(loaded), turn=ym_to_turn(2025, 3)), b, d)
    spacex = next(c for c in later.companies if c.name == "SpaceX")
    (line,) = [p for p in later.company_products(spacex.id) if p.category == b.space.broadband]
    d2d = [s for s in later.segments_of(line.id) if s.segment == b.space.d2d_segment]
    assert d2d and all(s.price_cents is None for s in d2d)
    open_ = history.pin(replace(fresh_game(loaded), turn=ym_to_turn(2025, 8)), b, d)
    d2d = [s for s in open_.segments_of(line.id) if s.segment == b.space.d2d_segment]
    assert d2d and all(s.price_cents is not None for s in d2d)
