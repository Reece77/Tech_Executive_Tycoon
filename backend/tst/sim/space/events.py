"""A launch failure with the player's satellites aboard: a critical event (docs/formulas.md 56.1;
data/events/space.yaml).

The engine queues the event for the month after the failure (trigger `space`); the satellites are
lost and written off already, and an own vehicle is grounded. The answer, applied by the engine
(`space_step`):

- **review**: an independent failure review: the vehicle's grounding left x (1 - `review_cut`),
  at `review_cents`;
- **rebuild**: rush replacements: the lost satellites are back on the ground at `rebuild_cents`
  each (capitalized, 1500);
- **claim**: contest the insurer over the uninsured part: at `claim_cents`, with `claim_chance`
  (stream space (3, constellation_id, lost)) the insurer pays the rest of the value (4900).

Left unanswered, the first choice (review) applies at Continue.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import GameEvent, QueuedEvent
from tst.sim.ledger import CASH, GENERAL_ADMIN, OTHER_INCOME, PPE, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import exact
from tst.sim.rng import RngFactory
from tst.sim.space import draws
from tst.sim.space.models import Constellation
from tst.sim.state import GameState, with_queued

TEMPLATES: Final = (
    "launch_failure_payload",
    "launch_failure_upper_stage",
)  # data/events/space.yaml


def queue_failure(
    state: GameState, c: Constellation, sats: int, value: int, vehicle_id: int | None
) -> GameState:
    """Queue the critical event for next month (one a month for the company)."""
    due = state.turn + 1
    if any(x.event_turn == due for x in state.space.constellations if x.company_id == c.company_id):
        return state
    template = TEMPLATES[c.id % len(TEMPLATES)]
    qid, ids = state.next_ids.take("queued")
    state = with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid,
            company_id=c.company_id,
            template_id=template,
            due_turn=due,
            source_event_id=None,
        ),
    )
    cons = tuple(
        replace(
            x,
            event_turn=due,
            event_sats=sats,
            event_value_cents=value,
            event_vehicle_id=vehicle_id,
        )
        if x.id == c.id
        else x
        for x in state.space.constellations
    )
    return replace(state, space=replace(state.space, constellations=cons))


def _for_event(state: GameState, event: GameEvent) -> Constellation | None:
    return next(
        (
            c
            for c in state.space.constellations
            if c.company_id == event.company_id and c.event_turn == event.turn
        ),
        None,
    )


def space_step(
    state: GameState, event: GameEvent, step: str, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """A failure's answer (module docstring), applied by the engine."""
    c = _for_event(state, event)
    if c is None:
        return state, [], []
    eb = balance.space.event
    turn = state.turn
    company = c.company_id
    entries: list[LedgerEntry] = []
    new = replace(c, event_turn=None)
    space = state.space
    if step == "review":
        if eb.review_cents > 0:
            entries.append(_cost(turn, company, "Launch failure review", eb.review_cents))
        if c.event_vehicle_id is not None:
            spec = space.spec(c.event_vehicle_id)
            if spec is not None and spec.grounded_until is not None:
                left = max(0, spec.grounded_until - turn)
                spec = replace(spec, grounded_until=turn + round(left * (1 - eb.review_cut)))
                space = replace(
                    space,
                    launch_specs=tuple(
                        spec if s.product_id == spec.product_id else s for s in space.launch_specs
                    ),
                )
    elif step == "rebuild" and c.event_sats > 0:
        cents = eb.rebuild_cents * c.event_sats
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=company,
                memo=f"Constellation {c.name}: rush replacements",
                debit=PPE,
                credit=CASH,
                amount=cents,
            )
        )
        new = replace(
            new,
            ground=new.ground + c.event_sats,
            capex_cents=new.capex_cents + cents,
            cash_cents=new.cash_cents - cents,
        )
    elif step == "claim":
        entries.append(_cost(turn, company, "Insurance claim: legal costs", eb.claim_cents))
        rng = RngFactory(state.save_meta.master_seed)
        u = float(draws.gen(rng, turn, draws.AFTER, c.id, c.event_sats).random())
        rest = round(exact(c.event_value_cents) * exact(1 - balance.space.failure.insured_share))
        if c.insured and u < eb.claim_chance and rest > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=company,
                    memo=f"Constellation {c.name}: insurer pays the claim",
                    debit=CASH,
                    credit=OTHER_INCOME,
                    amount=rest,
                )
            )
            new = replace(new, cash_cents=new.cash_cents + rest)
        new = replace(new, cash_cents=new.cash_cents - eb.claim_cents)
    space = replace(
        space, constellations=tuple(new if x.id == c.id else x for x in space.constellations)
    )
    log = inbox_item(turn, company, "space_failure_answered", step=step, constellation=c.name)
    return replace(state, space=space), [e for e in entries if e.lines[0].amount], [log]


def _cost(turn: int, company: int, memo: str, cents: int) -> LedgerEntry:
    return LedgerEntry.transfer(
        turn=turn, company_id=company, memo=memo, debit=GENERAL_ADMIN, credit=CASH, amount=cents
    )
