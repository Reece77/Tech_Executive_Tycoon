"""Data-centre outages (docs/formulas.md 22.5), in phase 6.

Each month each live facility has an outage with probability base x (100 - reliability) / 10:
one uniform on stream `facility`, key (facility_id,), by facility id. In an outage every
product it hosts loses `outage.customers_share` of the critical customers_pct cap of its
customers, and the company's Cloud hosting customers churn `cloud_churn_mult` times as fast
that month (the extra churn comes off now). The player's company gets a critical
`facility_outage` event next month (one however many sites failed), whose choices trade cash
against brand.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import QueuedEvent
from tst.sim.facilities import compute
from tst.sim.facilities import formulas as ff
from tst.sim.facilities.lifecycle import facility_name, staffing
from tst.sim.facilities.models import Outage
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    player_companies,
    with_outage,
    with_product_segment,
    with_queued,
    with_regional_segment,
)

OUTAGE_TEMPLATE = "facility_outage"  # data/events/facility.yaml
CRITICAL = 2  # tunable-exempt: index of the critical severity in balance.events.caps
PERCENT = 100  # tunable-exempt: customers_pct is in percent


def roll(state: GameState, rng: RngFactory, balance: Balance) -> list[int]:
    """Ids of the live facilities that have an outage this month, by id (22.5)."""
    hit: list[int] = []
    for facility in state.facilities:
        if facility.live_capacity(state.turn) <= 0:
            continue
        rel = staffing(state, facility, balance).reliability
        chance = ff.outage_chance(rel, balance.facility.outage.base)
        u = float(rng.stream(state.turn, "facility", facility.id).random())
        if u < chance:
            hit.append(facility.id)
    return hit


def _lose(state: GameState, product_id: int, share: float) -> tuple[GameState, float, str | None]:
    """Every segment of the product loses `share` of its customers; returns the customers
    lost and the segment that lost most."""
    lost = 0.0
    worst: tuple[float, str] | None = None
    for seg in state.segments_of(product_id):
        gone = seg.customers * share
        lost += gone
        state = with_product_segment(state, replace(seg, customers=seg.customers - gone))
        if worst is None or gone > worst[0]:
            worst = (gone, seg.segment)
    for rseg in state.regional_segments_of(product_id):
        gone = rseg.customers * share
        lost += gone
        state = with_regional_segment(state, replace(rseg, customers=rseg.customers - gone))
    return state, lost, worst[1] if worst else None


def outages_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Phase 6: roll outages and apply them (22.5)."""
    return apply_outages(state, roll(state, rng, balance), balance, data)


def apply_outages(
    state: GameState, hit: list[int], balance: Balance, data: GameData
) -> tuple[GameState, tuple[LogItem, ...]]:
    """The outages of the facilities in `hit` (ids), in order: lost customers, history, the
    player's inbox note and one critical event (22.5)."""
    if not hit:
        return state, ()
    ob = balance.facility.outage
    share = ob.customers_share * balance.events.caps["customers_pct"][CRITICAL] / PERCENT
    logs: list[LogItem] = []
    players = {c.id for c in player_companies(state)}
    queued_for: set[int] = set()
    allocs = {}
    for facility_id in hit:
        facility = state.facility(facility_id)
        assert facility is not None
        company = facility.company_id
        if company not in allocs:  # who it hosted, before anyone lost customers
            allocs[company] = compute.allocate(state, company, balance, data)
        alloc = allocs[company]
        lost_total = 0.0
        worst: tuple[float, int, str | None] | None = None
        for product_id in sorted(alloc.hosted.get(facility_id, set())):
            state, lost, segment = _lose(state, product_id, share)
            lost_total += lost
            if worst is None or lost > worst[0]:
                worst = (lost, product_id, segment)
        cloud = compute.capacity_product(state, company, data)
        if cloud is not None and alloc.sold.get(facility_id, 0.0) > 0:
            category = data.category(cloud.category)
            for seg in state.segments_of(cloud.id):  # churn x mult: the extra comes off now
                extra = (ob.cloud_churn_mult - 1) * data.segment(seg.segment).base_churn
                gone = seg.customers * min(1.0, extra)
                lost_total += gone
                state = with_product_segment(state, replace(seg, customers=seg.customers - gone))
                if worst is None or gone > worst[0]:
                    worst = (gone, cloud.id, seg.segment)
            del category
        outage_id, ids = state.next_ids.take("outage")
        state = with_outage(
            replace(state, next_ids=ids),
            Outage(outage_id, facility_id, company, state.turn, lost_total),
        )
        if company in players:
            logs.append(
                inbox_item(
                    state.turn,
                    company,
                    "outage_hit",
                    facility=facility_name(facility, balance, data),
                    lost=f"{lost_total:,.0f}",
                )
            )
        if company in players and company not in queued_for and worst is not None:
            queued_for.add(company)
            queued_id, ids = state.next_ids.take("queued")
            state = with_queued(
                replace(state, next_ids=ids),
                QueuedEvent(
                    id=queued_id,
                    company_id=company,
                    template_id=OUTAGE_TEMPLATE,
                    due_turn=state.turn + 1,
                    source_event_id=None,  # the engine queued it
                    product_id=worst[1],
                    segment=worst[2],
                ),
            )
    return state, tuple(logs)
