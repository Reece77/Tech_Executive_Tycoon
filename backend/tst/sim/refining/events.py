"""Refining's events (docs/formulas.md 36.4), drawn on stream `refining` keyed by facility id.

- **Power curbs** on smelters and polysilicon plants (recipes with `curbs`): history first
  (China's dual-control curbs, September-October 2021, in East Asia), then seeded from
  `refining.curb.after`: each month a live plant that is not curbed starts one with its
  region's chance; it then runs at 50-70% of capacity for 1-3 months. Three uniforms are drawn
  whenever a plant is eligible (start, share, months), in that order.
- **Plant incidents** (a fire or chemical release) at plants whose recipe has an
  `incident_rate` (rare-earth and polysilicon plants), a critical event: the monthly chance is
  M19's accident formula (35.4) with the plant's staff skill and coverage. At the incident the
  company loses brand on every segment and credibility; the answer (next month, or the first
  choice at Continue) sets the rest: stop and investigate (months at zero output, half the
  fine), compensate (money and Beloved), or contest (the fine, Ruthless, and a chance of legal
  costs). Two uniforms are drawn for each eligible plant (incident, template).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import GameEvent, QueuedEvent
from tst.sim.facilities import lifecycle
from tst.sim.facilities.config import month_to_turn
from tst.sim.facilities.models import Facility
from tst.sim.ledger import CASH, GENERAL_ADMIN, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import format_money
from tst.sim.refining import formulas as rf
from tst.sim.refining.draws import CURB, INCIDENT, LEGAL, refining_draws
from tst.sim.refining.models import Refinery
from tst.sim.refining.plants import live_refineries, recipe_of, refinery_of
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_queued, with_refinery

TEMPLATES: Final = ("refinery_fire", "chemical_release")  # data/events/refining.yaml
STEPS: Final = ("stop", "compensate", "contest")  # tst.sim.events.data REFINING_STEPS
CURB_DRAWS: Final = 3  # tunable-exempt: start, share and length (module docstring)


def _lerp(lo: float, hi: float, u: float) -> float:
    return lo + (hi - lo) * u


def history_curb(turn: int, region: str, balance: Balance) -> tuple[int, float, str] | None:
    """The historical curb running in `turn` in `region`: (its last month, run share, label)."""
    for c in balance.refining.curb.history:
        if c.region == region and month_to_turn(c.start) <= turn <= month_to_turn(c.end):
            return month_to_turn(c.end), c.run, c.label
    return None


def _curb(
    state: GameState,
    ref: Refinery,
    facility: Facility,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[Refinery, list[LogItem]]:
    cb = balance.refining.curb
    turn = state.turn
    if not recipe_of(ref, balance).curbs or ref.curbed(turn):
        return ref, []
    name = lifecycle.facility_name(facility, balance, data)
    found = history_curb(turn, facility.region, balance)
    if found is not None:
        end, run, label = found
    elif turn >= month_to_turn(cb.after):
        u_start, u_run, u_months = (
            float(x) for x in refining_draws(rng, turn, CURB, ref.facility_id).random(CURB_DRAWS)
        )
        if u_start >= cb.monthly.get(facility.region, 0.0):
            return ref, []
        run = _lerp(cb.run.lo, cb.run.hi, u_run)
        span = int(cb.months.hi) - int(cb.months.lo) + 1
        end = turn + int(cb.months.lo) + min(span - 1, int(u_months * span)) - 1
        label = "A power curb"
    else:
        return ref, []
    log = inbox_item(
        turn,
        ref.company_id,
        "refinery_curbed",
        link_kind="refinery",
        link_id=ref.facility_id,
        plant=name,
        cause=label,
        run=f"{run:.0%}",
        until=format_turn(end),
    )
    return replace(ref, curb_until=end, curb_run=run), [log]


def _incident(
    state: GameState,
    ref: Refinery,
    facility: Facility,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    hit: set[int],
) -> tuple[GameState, Refinery, list[LogItem]]:
    r = recipe_of(ref, balance)
    ib = balance.refining.incident
    turn = state.turn
    if r.incident_rate <= 0 or ref.incident_turn is not None or facility.live_capacity(turn) <= 0:
        return state, ref, []
    u, u_kind = (float(x) for x in refining_draws(rng, turn, INCIDENT, ref.facility_id).random(2))
    staffing = lifecycle.staffing(state, facility, balance)
    chance = rf.incident_chance(
        r.incident_rate,
        staffing.mean_skill,
        staffing.coverage,
        ib.skill_base,
        ib.skill_slope,
        ib.cover_base,
    )
    if ref.company_id in hit or u >= chance:
        return state, ref, []
    hit.add(ref.company_id)
    template = TEMPLATES[min(len(TEMPLATES) - 1, int(u_kind * len(TEMPLATES)))]
    qid, ids = state.next_ids.take("queued")
    state = with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid,
            company_id=ref.company_id,
            template_id=template,
            due_turn=turn + 1,
            source_event_id=None,
        ),
    )
    state = _always(state, ref.company_id, balance)
    name = lifecycle.facility_name(facility, balance, data)
    log = inbox_item(
        turn,
        ref.company_id,
        "refinery_incident",
        link_kind="refinery",
        link_id=ref.facility_id,
        plant=name,
    )
    return state, replace(ref, incident_turn=turn + 1, incidents=ref.incidents + 1), [log]


def _always(state: GameState, company_id: int, balance: Balance) -> GameState:
    """Brand on every one of the company's products, and credibility (36.4)."""
    from tst.sim.press.moments import adjust_credibility
    from tst.sim.state import with_product

    ib = balance.refining.incident
    for product in state.company_products(company_id):
        state = with_product(
            state, replace(product, brand=max(0.0, product.brand - ib.brand_points))
        )
    return adjust_credibility(
        state, company_id, -ib.credibility_points, "a plant incident", balance
    )


def events_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Phase 4, before the plants run: curbs, then incidents, by facility id."""
    logs: list[LogItem] = []
    hit: set[int] = set()
    for ref, facility in list(live_refineries(state)):
        if facility.status != "live":
            continue
        ref, notes = _curb(state, ref, facility, rng, balance, data)
        logs += notes
        state, ref, notes = _incident(state, ref, facility, rng, balance, data, hit)
        logs += notes
        state = with_refinery(state, ref)
    return state, logs


def _refinery_for_event(state: GameState, event: GameEvent) -> Refinery | None:
    for ref in state.refineries:
        if ref.company_id == event.company_id and ref.incident_turn == event.turn:
            return ref
    return None


def refining_step(
    state: GameState, event: GameEvent, step: str, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """An incident's answer (module docstring), applied by the engine."""
    ref = _refinery_for_event(state, event)
    if ref is None:
        return state, [], []
    ib = balance.refining.incident
    turn = state.turn
    facility = state.facility(ref.facility_id)
    name = lifecycle.facility_name(facility, balance, data) if facility else "a plant"
    fine = ib.fine_cents
    cost = 0
    logs: list[LogItem] = []
    founder = state.founder_of(state.player.id)
    if step == "stop":
        fine = round(fine * ib.stop_fine_share)
        ref = replace(ref, stop_until=turn + ib.stop_months - 1)
    elif step == "compensate":
        cost = ib.compensate_cents
        state = _persona(
            state,
            founder,
            "beloved",
            ib.compensate_beloved,
            "compensated after a plant incident",
            balance,
        )
    elif step == "contest":
        state = _persona(
            state, founder, "ruthless", ib.contest_ruthless, "contested a plant incident", balance
        )
        u = float(
            refining_draws(
                RngFactory(state.save_meta.master_seed), turn, LEGAL, ref.facility_id
            ).random()
        )
        if u < ib.contest_legal:
            cost = ib.contest_legal_cents
    entries = [
        LedgerEntry.transfer(
            turn=turn,
            company_id=ref.company_id,
            memo=f"{memo}: {name}",
            debit=GENERAL_ADMIN,
            credit=CASH,
            amount=amount,
        )
        for memo, amount in (("Incident fine", fine), (f"Incident ({step})", cost))
        if amount > 0
    ]
    logs.append(
        inbox_item(
            turn,
            ref.company_id,
            "refinery_incident_closed",
            link_kind="refinery",
            link_id=ref.facility_id,
            plant=name,
            cost=format_money(fine + cost),
        )
    )
    return with_refinery(state, replace(ref, incident_turn=None)), entries, logs


def _persona(
    state: GameState, founder: object, trait: str, value: float, why: str, balance: Balance
) -> GameState:
    if founder is None or not value:
        return state
    from tst.sim.founder.persona import raise_trait
    from tst.sim.founder.stress import new_life
    from tst.sim.state import life_of, with_life

    fid = founder.id  # type: ignore[attr-defined]
    life = life_of(state, fid) or new_life(fid, balance)
    return with_life(state, raise_trait(life, trait, value, why, state.turn, balance))


__all__ = ["STEPS", "TEMPLATES", "events_month", "history_curb", "refinery_of", "refining_step"]
