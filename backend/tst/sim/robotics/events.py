"""A serious robotaxi incident's critical event (docs/formulas.md 53.3; data/events/robotics.yaml).

The engine queues the event for the month after the incident (trigger `robotics`); the zone is
suspended already. The answer, applied by the engine (`robotics_step`):

- **cooperate**: share the logs: the suspension's months left x `cooperate_share`, at
  `cooperate_cents`;
- **compensate**: pay `compensate_cents` and recall the software: the service's brand recovers
  `recover_points`;
- **contest**: no cost now; with `contest_chance` (stream robotics (1, zone_id, n_cities)) the
  regulator extends the suspension `contest_months`.

Left unanswered, the first choice (cooperate) applies at Continue.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import GameEvent, QueuedEvent
from tst.sim.ledger import CASH, GENERAL_ADMIN, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.robotics import draws
from tst.sim.robotics.data import file
from tst.sim.robotics.models import Zone
from tst.sim.state import GameState, with_product, with_queued

TEMPLATES: Final = ("robotaxi_collision", "robotaxi_pedestrian")  # data/events/robotics.yaml


def queue_incident(state: GameState, zone: Zone) -> GameState:
    """Queue the critical event for next month (one a month: a second serious incident in the
    same month adds no second event). The template alternates by zone id."""
    due = state.turn + 1
    if any(z.event_turn == due for z in state.zones if z.company_id == zone.company_id):
        return state
    template = TEMPLATES[zone.id % len(TEMPLATES)]
    qid, ids = state.next_ids.take("queued")
    state = with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid,
            company_id=zone.company_id,
            template_id=template,
            due_turn=due,
            source_event_id=None,
        ),
    )
    zones = tuple(replace(z, event_turn=due) if z.id == zone.id else z for z in state.zones)
    return replace(state, zones=zones)


def _zone_for_event(state: GameState, event: GameEvent) -> Zone | None:
    return next(
        (z for z in state.zones if z.company_id == event.company_id and z.event_turn == event.turn),
        None,
    )


def robotics_step(
    state: GameState, event: GameEvent, step: str, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """An incident's answer (module docstring), applied by the engine."""
    zone = _zone_for_event(state, event)
    if zone is None:
        return state, [], []
    eb = balance.robotics.incident_event
    turn = state.turn
    cost = 0
    until = zone.suspended_until
    if step == "cooperate" and until is not None:
        left = max(0, until - turn)
        until = turn + round(left * eb.cooperate_share)
        cost = eb.cooperate_cents
    elif step == "compensate":
        cost = eb.compensate_cents
        product = state.product(zone.product_id)
        if product is not None:
            state = with_product(
                state, replace(product, brand=min(100.0, product.brand + eb.recover_points))
            )
    elif step == "contest" and until is not None:
        n = len(file(data).robotaxi.cities)
        rng = RngFactory(state.save_meta.master_seed)
        u = float(draws.gen(rng, turn, draws.INCIDENT, zone.id, n).random())
        if u < eb.contest_chance:
            until += eb.contest_months
    current = state.zone(zone.id)
    assert current is not None
    new = replace(current, event_turn=None)
    if new.status == "suspended":
        new = replace(new, suspended_until=until)
    state = replace(state, zones=tuple(new if z.id == zone.id else z for z in state.zones))
    entries = (
        [
            LedgerEntry.transfer(
                turn=turn,
                company_id=zone.company_id,
                memo=f"Robotaxi incident ({step})",
                debit=GENERAL_ADMIN,
                credit=CASH,
                amount=cost,
            )
        ]
        if cost > 0
        else []
    )
    log = inbox_item(
        turn,
        zone.company_id,
        "robotaxi_answered",
        step=step,
        until=str(until) if until is not None else "",
    )
    return state, entries, [log]
