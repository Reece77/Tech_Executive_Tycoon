"""M43r finding 6 (Codex review 9): pharma's sales read the month's own ceiling level.

Phase 5 books drug sales; the area's level for the month (54.1, 55.4) must be computed before
demand reads it, not in phase 12 after the sales ran on last month's level. A final clamp keeps
a market that was under its ceiling from stepping over it; one already over is held (M43a)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.pharma_helpers import base
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.pharma import ceilings, demand
from tst.sim.pharma import data as pd
from tst.sim.pharma.month import sales_month

REGION = "north_america"
CEILING = 100.0


def _market(monkeypatch: pytest.MonkeyPatch, loaded: LoadedData, path: dict[int, float]) -> str:
    """Metabolic in North America follows `path` (uncapped value by turn) against a ceiling of
    100; every other area and region has no market."""
    area = pd.area(loaded.game_data, "metabolic")

    def uncapped(data, balance, a, region, turn):  # type: ignore[no-untyped-def]
        return path.get(turn, 0.0) if (a.key, region) == (area.key, REGION) else 0.0

    def ceiling(state, balance, data, category, region):  # type: ignore[no-untyped-def]
        return CEILING

    monkeypatch.setattr(ceilings, "_uncapped_cents", uncapped)
    monkeypatch.setattr(ceilings.saturation, "ceiling_cents", ceiling)
    return area.category


def _read_by_sales(monkeypatch: pytest.MonkeyPatch, category: str) -> list[float]:
    seen: list[float] = []

    def month(state, balance, data):  # type: ignore[no-untyped-def]
        seen.append(ceilings.level(state, category, REGION))
        return state, [], demand.Month()

    monkeypatch.setattr(demand, "month", month)
    return seen


def test_sales_read_the_months_level_at_the_boundary(
    loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex's case: 99.9 against 100 with 1% uncapped growth. Sales must see 99.900999, not
    the stale level's 100.899."""
    turn = ym_to_turn(2030, 3)
    category = _market(monkeypatch, loaded, {turn - 1: 99.9, turn: 99.9 * 1.01})
    seen = _read_by_sales(monkeypatch, category)
    state = base(loaded, turn=turn)
    sales_month(state, loaded.balance, loaded.game_data)
    assert len(seen) == 1
    assert seen[0] * 99.9 * 1.01 == pytest.approx(99.900999, rel=1e-12)
    assert seen[0] * 99.9 * 1.01 <= CEILING


def test_sales_read_the_months_level_in_a_later_near_ceiling_month(
    loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    turn = ym_to_turn(2031, 7)
    path = {turn - 1: 99.0, turn: 99.0 * 1.01, turn + 1: 99.0 * 1.01**2}
    category = _market(monkeypatch, loaded, path)
    seen = _read_by_sales(monkeypatch, category)
    state = base(loaded, turn=turn)
    expected = 99.0
    for t in (turn, turn + 1):
        state, _, _ = sales_month(replace(state, turn=t), loaded.balance, loaded.game_data)
        expected *= 1 + 0.01 * (1 - expected / CEILING)
        assert seen[-1] * path[t] == pytest.approx(expected, rel=1e-12)
        assert seen[-1] * path[t] <= CEILING


def test_a_step_never_carries_a_market_over_its_ceiling(
    loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under its ceiling at 50 with the data path quadrupling: saturation alone gives 125; the
    final clamp holds it at the ceiling."""
    turn = ym_to_turn(2032, 1)
    category = _market(monkeypatch, loaded, {turn - 1: 50.0, turn: 200.0})
    seen = _read_by_sales(monkeypatch, category)
    sales_month(base(loaded, turn=turn), loaded.balance, loaded.game_data)
    assert seen[0] * 200.0 == pytest.approx(CEILING, rel=1e-12)


def test_a_market_already_over_its_ceiling_is_held_not_cut(
    loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    turn = ym_to_turn(2026, 1)
    category = _market(monkeypatch, loaded, {turn - 1: 150.0, turn: 165.0})
    seen = _read_by_sales(monkeypatch, category)
    sales_month(base(loaded, turn=turn), loaded.balance, loaded.game_data)
    assert seen[0] * 165.0 == pytest.approx(150.0, rel=1e-12)
