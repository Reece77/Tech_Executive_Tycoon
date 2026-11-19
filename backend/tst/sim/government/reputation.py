"""Reputation and politics (docs/formulas.md 57.4).

When the player's award of a **defence** tender stands:

- **Brand:** each live product in `consumer_categories` loses `brand_first` points for the
  company's first defence award, `brand_next` for each later one, at most `brand_year_cap` over a
  trailing 12 months.
- **Persona** (32.4): the founder's traits move by `persona` (Ruthless up, Beloved down).
- **Influence** (32.5): the company's influence in the government's region rises `influence`
  points (to 100).
- **Blocs:** the company now supplies that government's bloc's militaries; governments that
  refuse that bloc's suppliers will not buy from it (sourcing.requirements).
- **Staff:** objectors are employees (not the founder) with an `objector_interests` interest or
  adaptability at or below `low_tolerance`. Each gets a `morale_pct` morale-target modifier for
  `morale_months` (23.2). Then an open letter is drawn (stream `defence` (4, company_id, turn))
  with chance min(`letter_max`, `letter_base` + `letter_slope` x the objectors' share of staff):
  a critical event next month (template `defence_open_letter`, trigger `government`, answers
  `carry_on`, `withdraw`, `ethics_board`, applied by `government_step`, events.py).

A company that never wins a defence award is never touched here."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import Modifier, QueuedEvent
from tst.sim.founder.influence import of as influence_value
from tst.sim.founder.models import Influence
from tst.sim.founder.persona import raise_trait
from tst.sim.founder.stress import new_life
from tst.sim.government import draws
from tst.sim.government.data import MONTHS, PCT, file, gov_bloc, gov_region
from tst.sim.government.models import Contract, DefenceRecord
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    influence_of,
    life_of,
    with_influence,
    with_life,
    with_modifier,
    with_product,
    with_queued,
)

LETTER_TEMPLATE: Final = "defence_open_letter"
WHY: Final = "defence work"


def objectors(state: GameState, company_id: int, balance: Balance) -> tuple[int, ...]:
    rb = balance.government.reputation
    founder = state.founder_of(company_id)
    out = []
    for e in state.staff(company_id):
        if founder is not None and e.person_id == founder.id:
            continue
        p = state.person(e.person_id)
        adapt = p.personality.as_dict().get("adaptability", PCT)
        if set(p.interests) & set(rb.objector_interests) or adapt <= rb.low_tolerance:
            out.append(p.id)
    return tuple(sorted(out))


def _record(state: GameState, company_id: int) -> DefenceRecord:
    return state.defence_record(company_id) or DefenceRecord(company_id=company_id)


def _with_record(state: GameState, record: DefenceRecord) -> GameState:
    others = tuple(r for r in state.defence_records if r.company_id != record.company_id)
    return replace(
        state, defence_records=tuple(sorted((*others, record), key=lambda r: r.company_id))
    )


def queue_letter(state: GameState, company_id: int) -> GameState:
    """The open letter's critical event, next month (one at a time)."""
    qid, ids = state.next_ids.take("queued")
    return with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid,
            company_id=company_id,
            template_id=LETTER_TEMPLATE,
            due_turn=state.turn + 1,
            source_event_id=None,
        ),
    )


def on_defence_award(
    state: GameState, contract: Contract, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    rb = balance.government.reputation
    gov = file(data).government(contract.government)
    turn = state.turn
    cid = contract.company_id
    record = _record(state, cid)
    first = record.awards == 0
    # brand
    recent = sum(p for t, p in record.brand_lost if t > turn - MONTHS)
    points = min(rb.brand_first if first else rb.brand_next, max(0.0, rb.brand_year_cap - recent))
    lost = record.brand_lost
    if points > 0:
        hit = False
        for p in state.products:
            if p.company_id == cid and p.status == "live" and p.category in rb.consumer_categories:
                state = with_product(state, replace(p, brand=max(0.0, p.brand - points)))
                hit = True
        if hit:
            lost = (*lost, (turn, points))
    # persona
    founder = state.founder_of(cid)
    if founder is not None and rb.persona:
        life = life_of(state, founder.id) or new_life(founder.id, balance)
        for trait, value in rb.persona.items():
            life = raise_trait(life, trait, value, WHY, turn, balance)
        state = with_life(state, life)
    # influence
    region = gov_region(gov, data)
    inf = influence_of(state, cid, region) or Influence(company_id=cid, region=region)
    state = with_influence(
        state, replace(inf, value=min(PCT, influence_value(state, cid, region) + rb.influence))
    )
    # blocs
    bloc = gov_bloc(gov, data, turn)
    blocs = record.blocs if bloc in record.blocs else tuple(sorted((*record.blocs, bloc)))
    # staff
    objecting = objectors(state, cid, balance)
    for pid in objecting:
        mid, ids = state.next_ids.take("modifier")
        state = with_modifier(
            replace(state, next_ids=ids),
            Modifier(
                id=mid,
                company_id=cid,
                event_id=None,
                target=f"person:{pid}",
                stat="morale_target",
                value_pct=rb.morale_pct,
                start_turn=turn,
                end_turn=turn + rb.morale_months,
            ),
        )
    staff = len(state.staff(cid))
    share = len(objecting) / staff if staff else 0.0
    chance = min(rb.letter_max, rb.letter_base + rb.letter_slope * share) if objecting else 0.0
    g = draws.gen(rng, turn, draws.REACTION, cid, turn)
    letter = float(g.random()) < chance and record.letter_turn is None
    reactions = record.reactions
    letter_turn = record.letter_turn
    logs = [
        inbox_item(
            turn,
            cid,
            "defence_award_reaction",
            government=gov.label,
            objectors=str(len(objecting)),
            brand=f"{points:.1f}",
        )
    ]
    if letter:
        reactions = (*reactions, turn)
        letter_turn = turn + 1
        state = queue_letter(state, cid)
    state = _with_record(
        state,
        replace(
            record,
            awards=record.awards + 1,
            first_turn=record.first_turn if record.first_turn is not None else turn,
            blocs=blocs,
            brand_lost=lost,
            reactions=reactions,
            letter_turn=letter_turn,
            objectors=objecting if letter else record.objectors,
            contract_id=contract.id if letter else record.contract_id,
        ),
    )
    return state, logs
