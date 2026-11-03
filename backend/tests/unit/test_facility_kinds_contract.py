"""Facility kinds contract (Codex review 3, finding 7; ADR-0020 2): a kind whose output is
not a compute good runs the shared lifecycle (capex, going live, depreciation, operating
cost, sale) but adds no Cloud capacity, no Cloud quality, no outages, and does not break the
Infrastructure view. The kind here is synthetic, so the rule holds for v3's mines and fabs as
well as M12b's assembly plants."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, with_product
from tst.api.facility_views import infrastructure_out
from tst.loader import LoadedData
from tst.sim.facilities import compute, lifecycle, outages
from tst.sim.facilities.config import FacilityKindDef
from tst.sim.facilities.models import Facility
from tst.sim.ledger import (
    ACCUMULATED_DEPRECIATION,
    CASH,
    DEPRECIATION,
    PPE,
    apply_entries,
)
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_facility

WORKS = "test_works"


@pytest.fixture
def works(loaded: LoadedData) -> LoadedData:
    """The real data plus a non-compute kind with outages left at their default (True)."""
    kind = FacilityKindDef(
        label="Test works",
        unit="widgets/month",
        input_good="equipment",
        output_good="widget",  # not in compute.goods
        capex_per_unit_cents=10_000,
        build_months=3,
        opex_per_unit_cents=0,
        life_months=24,
        staff_per=100,
        staff_roles=("manufacturing_engineer",),
        staff_skill="manufacturing",
        fixed_opex_cents=50_000,
    )
    fb = loaded.balance.facility
    balance = loaded.balance.model_copy(
        update={"facility": fb.model_copy(update={"kinds": {**fb.kinds, WORKS: kind}})}
    )
    return replace(loaded, balance=balance)


def _live(state: GameState, data: LoadedData, kind: str, units: int) -> GameState:
    k = data.balance.facility.kinds[kind]
    fid, ids = state.next_ids.take("facility")
    capex = units * k.capex_per_unit_cents
    facility = Facility(
        id=fid,
        company_id=1,
        kind=kind,
        region="north_america",
        capacity=units,
        on_time=units,
        ordered_turn=state.turn - k.build_months,
        ready_turn=state.turn,
        late_turn=state.turn,
        capex_cents=capex,
        input_index=1.0,
        capex_paid_cents=capex,
        status="live",
    )
    return with_facility(replace(state, next_ids=ids), facility)


def test_a_non_compute_kind_runs_the_shared_lifecycle(works: LoadedData) -> None:
    """Order, pay capex as built, go live, depreciate, cost its fixed operating cost, sell:
    every entry balances and book value ends where the ledger says."""
    b, d = works.balance, works.game_data
    state = fresh_game(works)
    q = lifecycle.quote(state, 1, WORKS, "north_america", 500, b, d)
    assert q.capex_cents == 500 * 10_000  # equipment index 1.0 in January 2010
    state, facility = lifecycle.order_build(state, 1, q)
    balances: dict[tuple[int, str], int] = {}
    for turn in range(8):
        state = replace(state, turn=turn)
        current = state.facility(facility.id)
        assert current is not None
        state, entries, _ = lifecycle.facility_month(state, current, b, d)
        balances = dict(apply_entries(balances, entries))
    live = state.facility(facility.id)
    assert live is not None and live.status == "live"
    assert live.capex_paid_cents == q.capex_cents
    assert live.depreciated_cents == round(q.capex_cents * 5 / 24)  # live turns 3-7
    assert balances[(1, PPE)] + balances[(1, ACCUMULATED_DEPRECIATION)] == live.book_value_cents
    lines = lifecycle.operating_lines(state, 1, b)
    assert [(memo, amount) for memo, _, amount, _ in lines] == [
        ("Assembly plant operations", 50_000)
    ]
    state, entry, proceeds = lifecycle.sell(state, live, b, d)
    assert entry is not None and sum(line.amount for line in entry.lines) == 0
    assert proceeds == round(live.book_value_cents * b.facility.sale_share)
    balances = dict(apply_entries(balances, [entry]))
    assert balances.get((1, PPE), 0) == 0 and balances.get((1, ACCUMULATED_DEPRECIATION), 0) == 0
    spent = q.capex_cents - proceeds  # capex less the sale's cash: all of it depreciation or loss
    assert balances[(1, CASH)] == -spent and balances[(1, DEPRECIATION)] == spent


def test_it_adds_no_cloud_capacity_quality_or_outages(works: LoadedData) -> None:
    b, d = works.balance, works.game_data
    base = _live(
        with_product(fresh_game(works), customers={"smb": 50_000.0}),
        works,
        "data_centre_general",
        500,
    )
    both = _live(base, works, WORKS, 10_000)
    works_id = max(f.id for f in both.facilities)
    assert not compute.is_compute(both.facility(works_id), b)  # type: ignore[arg-type]
    assert [f.id for f in compute.live_facilities(both, 1, b)] == [
        f.id for f in compute.live_facilities(base, 1, b)
    ]
    assert compute.allocate(both, 1, b, d) == compute.allocate(base, 1, b, d)
    assert compute.spare_by_region(both, 1, b, d) == compute.spare_by_region(base, 1, b, d)
    assert lifecycle.mean_reliability(both, 1, b) == lifecycle.mean_reliability(base, 1, b)
    assert not outages.has_outages(both.facility(works_id), b)  # type: ignore[arg-type]
    for seed in range(1, 30):  # unstaffed: a data centre at reliability 0 would roll often
        assert works_id not in outages.roll(both, RngFactory(seed), b)
    only = _live(fresh_game(works), works, WORKS, 10_000)
    assert compute.allocate(only, 1, b, d) == compute.Allocation()
    assert compute.spare_by_region(only, 1, b, d) == {r: 0.0 for r in d.region_keys}


def test_the_infrastructure_view_skips_it(works: LoadedData) -> None:
    both = _live(_live(fresh_game(works), works, "data_centre_general", 500), works, WORKS, 10_000)
    out = infrastructure_out(both, works, {})
    assert [f.kind for f in out.facilities] == ["data_centre_general"]
    assert WORKS not in {k.key for k in out.kinds}
    alone = infrastructure_out(_live(fresh_game(works), works, WORKS, 10_000), works, {})
    assert alone.facilities == [] and not alone.cloud.can_start
