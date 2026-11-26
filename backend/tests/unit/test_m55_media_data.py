"""M55 sub-task 1 (formulas.md 65, 65.8 target 1): media.yaml cites a source for every value (each
number is tagged S, D, R or A; money carries its dollar year), it loads and cross-checks, and
history to 2025 follows it: rival lines hold their customers, lines open on their dates, and the
markets' size is the data's at the game's scale."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.helpers import fresh_game
from tst.balance.game import Game, start_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.media import demand, history
from tst.sim.media.config import MILLION
from tst.sim.media.data import end_year_at
from tst.sim.vehicles.config import interp

DATA = Path(__file__).resolve().parents[2] / "data" / "media.yaml"
TAGS = {"S", "D", "R", "A"}
UNTAGGED = {"cpi"}
TEXT_KEYS = {
    "key", "label", "company", "line", "category", "region", "month", "first", "last", "deadline",
    "until", "from", "to", "format", "default_note", "ad_tier_from", "epic_from",
}  # fmt: skip
FLAGS = {"enforced", "ios_only"}
LISTS = {"regions"}


def _walk(node: Any, path: str, out: list[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if path == "" and k in UNTAGGED:
                continue
            if k in TEXT_KEYS or k in FLAGS or k in LISTS or k == "source":
                continue
            _walk(v, f"{path}.{k}", out)
        return
    if isinstance(node, list):
        if node and isinstance(node[0], int | float) and isinstance(node[-1], str):
            if node[-1] not in TAGS:
                out.append(f"{path}: unknown tag {node[-1]!r}")
            if "_usd" in path and len(node) != 3:  # tunable-exempt: [value, year, tag]
                out.append(f"{path}: money needs [value, dollar year, tag]")
            return
        for i, x in enumerate(node):
            _walk(x, f"{path}[{i}]", out)
        return
    if isinstance(node, int | float) and not isinstance(node, bool):
        out.append(f"{path}: {node!r} has no source tag")


def test_every_value_is_tagged() -> None:
    raw = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    problems: list[str] = []
    _walk(raw, "", problems)
    assert problems == []


def test_every_rule_names_a_source() -> None:
    raw = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    for name in ("formats", "console_generations", "loot_box_rules", "strikes", "divest_laws"):
        for row in raw[name]:
            assert row.get("source"), f"{name} {row}"
    for row in raw["ads"]["privacy"]:
        assert row.get("source")


def test_loads_with_lines_on_incumbents(loaded: LoadedData) -> None:
    f = loaded.game_data.media
    assert f is not None
    names = {c.name for c in loaded.game_data.incumbents}
    assert {x.company for x in f.lines} <= names
    assert len(f.lines) >= 30  # tunable-exempt: media.yaml's rival lines


def _netflix_customers(game: Game) -> float:
    netflix = next(c for c in game.state.companies if c.name == "Netflix")
    (product,) = game.state.company_products(netflix.id)
    segs = [*game.state.segments_of(product.id), *game.state.regional_segments_of(product.id)]
    return sum(s.customers for s in segs)


def test_history_holds_lines_to_the_data_and_lines_open_on_their_dates(
    loaded: LoadedData,
) -> None:
    """A rival line's customers are its data's x scale (65.8 target 1); Disney+ opens in November
    2019, not before."""
    balance, data = loaded.balance, loaded.game_data
    assert data.media is not None
    row = data.media.line("Netflix", "Netflix")
    assert row is not None
    game = start_game(loaded, 1)
    checked = 0
    while game.state.turn < ym_to_turn(2019, 12):
        game.turn()
        # the pin ran in phase 9 of the month just played (turn - 1)
        if game.state.turn in (ym_to_turn(2012, 12), ym_to_turn(2016, 12)):
            want = (
                interp(row.customers, end_year_at(game.state.turn - 1)) * MILLION * balance.media.scale
            )
            assert _netflix_customers(game) == pytest.approx(want, rel=1e-6)
            checked += 1
        disney = next(c for c in game.state.companies if c.name == "Disney")
        plus = next(p for p in game.state.company_products(disney.id) if p.name == "Disney+")
        rows = [*game.state.segments_of(plus.id), *game.state.regional_segments_of(plus.id)]
        opened = any(s.price_cents is not None for s in rows)
        assert opened == (game.state.turn - 1 >= ym_to_turn(2019, 11))
    assert checked == 2  # tunable-exempt: two checkpoints


def test_markets_are_the_data_at_scale(loaded: LoadedData) -> None:
    state = fresh_game(loaded, seed=1)
    balance, data = loaded.balance, loaded.game_data
    social = next(
        m for m in state.regional_markets if m.category == "social" and m.region == "europe"
    )
    assert social.addressable == pytest.approx(
        demand.addressable(state, "europe", "social", balance, data)
    )
    assert history.lines(state, balance, data)
