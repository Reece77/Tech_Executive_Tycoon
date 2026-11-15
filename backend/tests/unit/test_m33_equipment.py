"""M33 (docs/formulas.md 47.1-47.3): equipment.yaml, ASML's capacity, the queue and its
allocation, prices with scarcity, and controls on tools (tests/equipment_helpers.py)."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from tests.equipment_helpers import HISTORY_END, START, fresh, run
from tst.loader import DATA_FILES, LoadedData
from tst.sim.equipment import data as ed
from tst.sim.equipment import queue as eq
from tst.sim.equipment.config import EquipmentFile
from tst.sim.equipment.models import ToolOrder

EQUIPMENT = Path("data/equipment.yaml")
TAG = re.compile(r"#.*\b(V|D|R|A)\b|tag: (V|D|R|A)\b")


def test_equipment_file_is_a_data_file() -> None:
    assert "equipment.yaml" in DATA_FILES


def test_every_value_line_cites_a_tag() -> None:
    """Acceptance 1: every value carries a source tag (V, D, R or A) on its line, inline in a
    flow mapping or as a comment (folded notes and the header's source list aside)."""
    folded = False
    for n, line in enumerate(EQUIPMENT.read_text(encoding="utf-8").splitlines(), 1):
        if folded and line.startswith("  "):
            continue
        folded = line.rstrip().endswith(">-")
        body = line.split("#")[0].strip()
        if folded or not body or body.endswith(":") or not re.search(r"\d", body):
            continue
        if body.startswith(("- key:", "key:", "label:", "maker:", "queued:", "nodes:")):
            continue
        assert TAG.search(line), f"line {n} has no V/D/R/A tag: {line}"


def test_a_buyer_split_that_does_not_sum_to_one_fails() -> None:
    raw = yaml.safe_load(EQUIPMENT.read_text(encoding="utf-8"))
    raw["generations"][1]["buyers"]["tsmc"] += 0.1
    with pytest.raises(ValueError, match="sum to 1"):
        EquipmentFile.model_validate(raw)


def test_history_matches_asml_filings(loaded: LoadedData) -> None:
    """Acceptance 1: shipments, prices and generations to 2025 follow equipment.yaml (ASML's
    20-F units: EUV 26 in 2019 ... 53 in 2023; ArFi 125 in 2023)."""
    ef = loaded.game_data.equipment
    assert ef is not None
    low = ef.generation("euv_low")
    assert [low.shipments_in(y) for y in (2019, 2020, 2021, 2022, 2023, 2024, 2025)] == [
        26, 31, 42, 40, 53, 42, 47,
    ]  # fmt: skip
    assert ef.generation("euv_high").shipments_in(2024) == 2
    assert ef.generation("duv_immersion").shipments_in(2023) == 125
    assert low.first_volume == "2019-01"
    assert ef.generation("euv_high").first_shipment == "2023-12"
    assert low.model_in(2021).model == "NXE:3600D" and low.model_in(2021).wph == 160
    assert low.price_in(2019) == pytest.approx(12_050_000_000)
    assert ef.generation_for("n5") is low
    assert ef.generation_for("a10") is ef.generation("euv_high")
    assert ef.generation_for("n28") is None


def _deliveries(state, generation: str, year: int) -> int:  # type: ignore[no-untyped-def]
    start = ed.year_turn(year)
    return sum(
        d.tools
        for d in state.tool_deliveries
        if d.generation == generation and start <= d.turn < start + 12
    )


def test_history_shipments_are_delivered_each_year(loaded: LoadedData) -> None:
    """Sub-task 3's history test: with no player orders, every year's quarters deliver exactly
    equipment.yaml's shipments to the rival buyers, 2010-2025, on any seed."""
    ef = loaded.game_data.equipment
    assert ef is not None
    for seed in (1, 7):
        state, _ = fresh(loaded, seed)
        for year in range(2010, 2026):
            state, _, _ = run(loaded, state, ed.year_turn(year + 1) - 1)
            for g in ef.queued():
                expect = g.shipments_in(year) if year >= 2010 else 0
                got = _deliveries(state, g.key, year)
                assert got == expect, (seed, g.key, year, got, expect)


def test_quarters_sum_to_the_year() -> None:
    raw = yaml.safe_load(EQUIPMENT.read_text(encoding="utf-8"))
    ef = EquipmentFile.model_validate(raw)
    g = ef.generation("euv_low")
    from tst.sim.state import GameState

    s = GameState.__new__(GameState)  # only supplier_years is read
    object.__setattr__(s, "supplier_years", ())
    for year in (2019, 2023):
        total = sum(ed.quarter_tools(s, g, ed.year_turn(year) + 3 * q) for q in range(4))
        assert total == g.shipments_in(year)


def test_allocation_is_seeded(loaded: LoadedData) -> None:
    """Sub-task 3's seeded test: the same seed allocates identically; another seed's jitter can
    break ties differently, never the totals."""

    def play(seed: int):  # type: ignore[no-untyped-def]
        state, _ = fresh(loaded, seed, turn=ed.year_turn(2021))
        state, _, _ = run(loaded, state, ed.year_turn(2021))
        order = ToolOrder(
            id=eq.next_order_id(state),
            buyer=eq.PLAYER,
            generation="euv_low",
            tools=12,
            placed_turn=state.turn,
            company_id=1,
            country="us",
            price_cents=1,
        )
        state = replace(state, tool_orders=(*state.tool_orders, order))
        state, _, _ = run(loaded, replace(state, turn=state.turn + 1), ed.year_turn(2023))
        return [(o.id, o.buyer, o.delivered) for o in state.tool_orders]

    a, b = play(3), play(3)
    assert a == b
    totals = {s: sum(x[2] for x in play(s)) for s in (3, 4)}
    assert totals[3] == totals[4]


def test_allocation_follows_the_place_in_the_queue(loaded: LoadedData) -> None:
    """47.2: queue order x buyer weight: a long-standing buyer's later order overtakes a new
    buyer's earlier one by up to history_months; a prepayment moves an order up."""
    b = loaded.balance
    qb = b.equipment.queue
    new = ToolOrder(1, eq.PLAYER, "euv_low", 10, placed_turn=0, company_id=1, jitter=0.5)
    old_hand = ToolOrder(2, "tsmc", "euv_low", 10, placed_turn=6, jitter=0.5)
    places = {1: eq.place(new, 0.0, b), 2: eq.place(old_hand, qb.history_months, b)}
    got = eq.allocate([new, old_hand], places, 12)
    assert got == {2: 10, 1: 2}
    prepaid = replace(new, prepaid=True)
    assert eq.place(prepaid, 0.0, b) == eq.place(new, 0.0, b) - qb.prepay_months


def test_a_long_standing_buyer_outweighs_a_new_one(loaded: LoadedData) -> None:
    state, _ = fresh(loaded, 1, turn=ed.year_turn(2021))
    state, _, _ = run(loaded, state, ed.year_turn(2021))
    assert eq.buyer_months(state, "tsmc", None, loaded.balance) > eq.buyer_months(
        state, eq.PLAYER, 1, loaded.balance
    )


def test_a_banned_buyer_gets_no_deliveries(loaded: LoadedData) -> None:
    """Sub-task 4: SMIC (the Netherlands' 2019 practice, then M22's rules) and a player order
    to China receive nothing; the player's order is lost with its place."""
    state, _ = fresh(loaded, 2, turn=ed.year_turn(2022))
    state, _, _ = run(loaded, state, ed.year_turn(2022))
    order = ToolOrder(
        id=eq.next_order_id(state),
        buyer=eq.PLAYER,
        generation="euv_low",
        tools=5,
        placed_turn=state.turn,
        company_id=1,
        country="china",
        price_cents=1,
    )
    state = replace(state, tool_orders=(*state.tool_orders, order))
    state, _, logs = run(loaded, replace(state, turn=state.turn + 1), ed.year_turn(2024))
    mine = next(o for o in state.tool_orders if o.id == order.id)
    assert mine.status == "lost" and mine.delivered == 0
    assert not any(d.buyer == "smic" for d in state.tool_deliveries)
    assert any(x.kind == "tools_order_lost" for x in logs)


def test_controls_on_the_queue_follow_the_dates(loaded: LoadedData) -> None:
    from tst.sim.equipment import controls as ec

    state, _ = fresh(loaded, 1)
    data = loaded.game_data
    early = replace(state, turn=ed.year_turn(2019) + 5)  # June 2019
    late = replace(state, turn=ed.year_turn(2019) + 6)  # July 2019
    assert ec.blocking(early, data, "euv_low", "china", name="SMIC") is None
    assert ec.blocking(late, data, "euv_low", "china", name="SMIC") is not None
    assert ec.blocking(late, data, "euv_low", "taiwan", name="TSMC") is None


def test_scarcity_prices_only_from_2026(loaded: LoadedData) -> None:
    ef = loaded.game_data.equipment
    assert ef is not None
    g = ef.generation("euv_low")
    state, _ = fresh(loaded, 1, turn=HISTORY_END)
    big = ToolOrder(999, "tsmc", "euv_low", 500, placed_turn=HISTORY_END)
    state = replace(state, tool_orders=(big,))
    assert ed.scarcity(state, g, loaded.balance) == 1.0
    later = replace(state, turn=START)
    assert ed.scarcity(later, g, loaded.balance) > 1.0
    assert ed.price_cents(later, g, loaded.balance) > ed.base_price_cents(
        g, START, loaded.balance.equipment.price.growth
    )


def test_asml_follows_its_plan_on_a_deep_book(loaded: LoadedData) -> None:
    state, _ = fresh(loaded, 1, turn=HISTORY_END - 1)
    state, _, _ = run(loaded, state, START + 12)
    caps = {(s.generation, s.year): s.capacity for s in state.supplier_years}
    assert caps[("euv_low", 2026)] >= 47
    assert caps[("euv_low", 2027)] >= caps[("euv_low", 2026)]
    assert caps[("euv_high", 2027)] > 3


def test_lead_is_a_range_without_weights(loaded: LoadedData) -> None:
    state, _ = fresh(loaded, 1, turn=ed.year_turn(2027))
    state, _, _ = run(loaded, replace(state, turn=HISTORY_END - 1), ed.year_turn(2027))
    order = ToolOrder(
        id=eq.next_order_id(state),
        buyer=eq.PLAYER,
        generation="euv_low",
        tools=10,
        placed_turn=state.turn,
        company_id=1,
        country="us",
        price_cents=1,
    )
    lead = eq.lead(state, order, loaded.balance, loaded.game_data)
    assert lead.low is not None and lead.high is not None
    assert lead.low <= lead.high
