"""M33 (docs/formulas.md 47.4): the lithography programme's gates, hidden draws, spending,
outcomes, own tools and their sales; and the fab link (tests/equipment_helpers.py)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.equipment_helpers import START, fresh, run
from tst.loader import LoadedData
from tst.sim.equipment import data as ed
from tst.sim.equipment import programme as ep
from tst.sim.equipment import sales, stock
from tst.sim.equipment.models import OwnTools, Programme, ToolOrder
from tst.sim.ledger import RESEARCH, TOOL_SALES
from tst.sim.rng import RngFactory


def _staffed(monkeypatch: pytest.MonkeyPatch, n: int = 200, skill: float = 12.0) -> None:
    monkeypatch.setattr(ep, "staffing", lambda *a, **k: ep.Staffing(n, skill))


def test_a_stage_needs_stage_five_a_chip_and_a_fab(loaded: LoadedData) -> None:
    state, _ = fresh(loaded, 1, turn=START)
    why = ep.why_not(state, 1, "litho_1", loaded.balance, loaded.game_data)
    assert why is not None and "stage 5" in why
    assert "unknown" in (ep.why_not(state, 1, "litho_9", loaded.balance, loaded.game_data) or "")


def test_the_draws_are_seeded_and_hidden_in_the_engine(loaded: LoadedData) -> None:
    """Hidden-value invariant (47.6): the draws live on the record, from stream equipment, and
    the same seed draws the same; another attempt draws again."""
    b, d = loaded.balance, loaded.game_data
    state, _ = fresh(loaded, 5, turn=START)
    a = ep.start(state, 1, "litho_1", 1.1, RngFactory(5), b, d)
    again = ep.start(state, 1, "litho_1", 1.1, RngFactory(5), b, d)
    assert a == again
    p = d.equipment.stage("litho_1") if d.equipment else None
    assert p is not None
    lo, hi = p.months
    assert (
        lo * (1 + b.equipment.programme.overrun.lo)
        <= a.work
        <= hi * (1 + b.equipment.programme.overrun.hi)
    )
    second = ep.start(
        replace(state, programmes=(replace(a, status="failed"),)),
        1,
        "litho_1",
        1.1,
        RngFactory(5),
        b,
        d,
    )
    assert second.attempt == 2 and second.success_u != a.success_u


def test_a_stage_spends_progresses_and_ends(
    loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    b, d = loaded.balance, loaded.game_data
    _staffed(monkeypatch)
    state, _ = fresh(loaded, 2, turn=START)
    prog = replace(ep.start(state, 1, "litho_1", 1.0, RngFactory(2), b, d), work=3.0, success_u=0.0)
    state = replace(state, programmes=(prog,))
    rng = RngFactory(2)
    spent = []
    for t in range(START, START + 4):
        state = replace(state, turn=t)
        state, entries, ended = ep.month(state, rng, b, d)
        spent += [e for e in entries if any(line.account == RESEARCH for line in e.lines)]
        if ended:
            break
    assert ended and ended[0][1] == "succeeded"
    done = state.programmes[0]
    assert (
        done.status == "succeeded"
        and b.equipment.programme.throughput.lo
        <= done.throughput
        <= b.equipment.programme.throughput.hi
    )
    assert all(sum(line.amount for line in e.lines) == 0 for e in spent)  # balanced
    assert ep.line(state, 1, "duv_immersion") is not None


def test_a_bad_draw_fails_and_keeps_nothing(
    loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    b, d = loaded.balance, loaded.game_data
    _staffed(monkeypatch)
    state, _ = fresh(loaded, 2, turn=START)
    prog = replace(
        ep.start(state, 1, "litho_1", 1.0, RngFactory(2), b, d), work=1.0, success_u=0.999
    )
    state, _, ended = ep.month(replace(state, programmes=(prog,)), RngFactory(2), b, d)
    assert ended[0][1] == "failed" and not state.own_tools


def test_success_falls_with_less_funding_and_skill(loaded: LoadedData) -> None:
    b = loaded.balance
    assert (
        ep.success_chance(1.5, 15, b) > ep.success_chance(1.0, 10, b) > ep.success_chance(0.5, 6, b)
    )
    lo, hi = b.equipment.programme.success_range.lo, b.equipment.programme.success_range.hi
    assert lo <= ep.success_chance(0.0, 1, b) and ep.success_chance(9.0, 20, b) <= hi


def test_own_tools_improve_with_installed_use(loaded: LoadedData) -> None:
    b = loaded.balance
    state, _ = fresh(loaded, 1, turn=START)
    prog = Programme(
        1,
        "litho_2",
        1,
        START,
        1.0,
        10.0,
        0.0,
        0.1,
        status="succeeded",
        throughput=0.5,
        yield_cut=10.0,
    )
    state = replace(state, programmes=(prog,))
    new = OwnTools(1, "litho_2", "euv_low")
    used = replace(new, tool_months=5 * b.equipment.programme.learn_tool_months)
    assert ep.own_throughput(state, new, b) == pytest.approx(0.5)
    assert ep.own_throughput(state, used, b) > 0.99
    assert ep.own_yield_cut(state, used, b) < ep.own_yield_cut(state, new, b) == pytest.approx(10.0)


def test_own_tools_sell_to_rivals_when_the_queue_is_long(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _ = fresh(loaded, 1, turn=START + 11)  # December 2026
    prog = Programme(
        1,
        "litho_2",
        1,
        START,
        1.0,
        10.0,
        0.0,
        0.1,
        status="succeeded",
        throughput=0.9,
        yield_cut=5.0,
    )
    line = OwnTools(1, "litho_2", "euv_low", made=10)
    book = ToolOrder(1, "tsmc", "euv_low", 400, placed_turn=START)
    state = replace(state, programmes=(prog,), own_tools=(line,), tool_orders=(book,))
    state = stock.add(state, 1, "euv_low", 10, "own", 10 * 15_000_000_000)
    state, entries, sold = sales.december(state, b, d)
    assert sold and sold[0][1] > 0
    assert any(any(x.account == TOOL_SALES for x in e.lines) for e in entries)
    assert all(sum(x.amount for x in e.lines) == 0 for e in entries)
    assert state.tool_orders[0].tools < 400  # rivals bought ours instead
    # ASML responds the next December: a price cut
    after, _, _ = run(loaded, replace(state, turn=START + 23), START + 23)
    assert ed.price_mult(after, "euv_low") < 1.0
