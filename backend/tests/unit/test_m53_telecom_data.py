"""M53 sub-task 1 (formulas.md 62, 62.5 target 1): telecom.yaml cites a source for every value
(each number is tagged S, D, R or A; money carries its dollar year), it loads and cross-checks,
and history to 2025 follows it: operators hold their subscribers, vendors their RAN shares, lines
open and close on their dates, and the markets' size is the data's at the game's scale."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tests.helpers import fresh_game
from tst.balance.game import start_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities.compute import home_region_of
from tst.sim.geo.formulas import price_ratio
from tst.sim.telecom import demand, history
from tst.sim.telecom.data import MILLION, end_year_at

DATA = Path(__file__).resolve().parents[2] / "data" / "telecom.yaml"
TAGS = {"S", "D", "R", "A"}
UNTAGGED = {"cpi"}  # CPI is the file's converter (R, as space.yaml's)
TEXT_KEYS = {
    "key", "label", "company", "origin", "region", "area", "band", "month", "first", "last",
    "supplier", "vendor", "announced", "no_new", "replace_by", "rfs", "start", "end", "decided",
    "outcome", "method", "lte", "nr", "year",
}  # fmt: skip
FLAGS = {"mid_band_needed"}
LISTS = {"regions", "owners"}


def _walk(node: Any, path: str, out: list[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if path == "" and k in UNTAGGED:
                continue
            if k in TEXT_KEYS or k in FLAGS or k in LISTS:
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
        if path.endswith(".winners") or ".winners." in path:
            return  # blocks won: counts, sourced on the auction's line
        out.append(f"{path}: {node!r} has no source tag")


def test_every_value_is_tagged() -> None:
    raw = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    problems: list[str] = []
    _walk(raw, "", problems)
    assert problems == []


def test_every_entry_names_a_source() -> None:
    """Every tagged line carries a comment naming its source or basis, or sits under one."""
    lines = DATA.read_text(encoding="utf-8").splitlines()
    bare = []
    for n, line in enumerate(lines, 1):
        if not any(f", {t}]" in line for t in TAGS) or "#" in line:
            continue
        above = lines[n - 2].lstrip()
        if above.startswith("#") or line.lstrip().startswith("20"):
            continue  # a comment block just above, or a year row under a sourced block
        # a field of an entry whose block carries the source further up (an auction's mhz)
        if line.startswith("    ") and not line.lstrip().startswith("- "):
            continue
        bare.append(n)
    assert bare == []


def test_it_loads_and_reaches_2025(loaded: LoadedData) -> None:
    f = loaded.game_data.telecom
    assert f is not None
    assert {r.key for r in f.regions} == set(loaded.game_data.region_keys)
    for r in f.regions:
        assert min(r.mobile) <= 2008 and max(r.mobile) >= 2025
        assert min(r.fixed) <= 2008 and max(r.fixed) >= 2025
    c_band = f.auction("us_cband_2021")
    assert c_band is not None and c_band.winners["Verizon"] == 8
    assert f.region("east_asia").area("china").method == "closed"


def test_history_figures(loaded: LoadedData) -> None:
    """Sourced figures as the dossier's corrections record them."""
    f = loaded.game_data.telecom
    assert f is not None
    verizon = f.operator("Verizon", "north_america")
    assert verizon is not None and verizon.mobile[2015] == 104 and verizon.mobile[2025] == 146
    assert f.operator("Sprint", "north_america").last == "2020-04"  # the merger, 1 Apr 2020
    assert f.operator("Reliance Jio", "south_southeast_asia").first == "2016-09"
    assert f.region("north_america").mobile[2017] == 541  # LSBB S-sum + Mexico
    a73 = f.auction("us_700_2008")
    assert a73 is not None and a73.blocks == 10 and a73.winners == {"Verizon": 5, "AT&T": 3}


def test_demand_follows_the_data(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    f = d.telecom
    assert f is not None
    state = fresh_game(loaded)
    state = demand.set_demand(state, b, d)
    year = end_year_at(state.turn)
    for rm in state.regional_markets:
        if rm.category == b.telecom.mobile:
            want = f.region(rm.region).mobile_at(year) * MILLION * b.telecom.scale
            assert abs(rm.addressable - want * b.telecom.mobile_split[rm.segment]) < 1e-3


def test_operators_hold_their_subscribers_before_2026(loaded: LoadedData) -> None:
    """December 2015: each operator line's customers are its data subscribers at the game's
    scale (the history's pin), Jio has no price before its launch and Sprint's line is closed."""
    b, d = loaded.balance, loaded.game_data
    g = start_game(loaded, 2)
    while g.state.turn < ym_to_turn(2015, 12):
        g.turn()
    g.turn()  # December 2015 played: phase 9 pinned it
    s = g.state
    names = {c.id: c.name for c in s.companies}
    year = end_year_at(ym_to_turn(2015, 12))
    for p, source in history.lines(s, b, d):
        if p.category != b.telecom.mobile:
            continue
        name = names[p.company_id]
        total = sum(x.customers for x in s.segments_of(p.id)) + sum(
            x.customers for x in s.regional_segments_of(p.id)
        )
        if not source.active(ym_to_turn(2015, 12)):  # type: ignore[union-attr]
            assert total == 0, name  # Vodafone Idea before its merger
            continue
        if name == "Reliance Jio":
            assert total == 0
            assert all(x.price_cents is None for x in s.regional_segments_of(p.id))
            continue
        want = source.mobile_at(year) * MILLION * b.telecom.scale  # type: ignore[union-attr]
        assert abs(total - want) / want < 1e-6, name


def test_a_category_price_index_replaces_the_regions(loaded: LoadedData) -> None:
    d = loaded.game_data
    state = fresh_game(loaded)
    home = home_region_of(state, loaded.balance, d)
    assert float(price_ratio("south_southeast_asia", home, d, "mobile")) == 0.065
    assert float(price_ratio("south_southeast_asia", home, d)) == 0.35  # every other category
    assert float(price_ratio("south_southeast_asia", home, d, "b2b_saas")) == 0.35
