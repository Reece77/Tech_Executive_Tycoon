"""A class I recall's answers (docs/formulas.md 50.5), applied by the engine (`medical_step`).

- `full`: recall every affected unit (the cost already posted); half the brand points lost
  come back for the candour.
- `correct`: correct units in the field: 40% of the recall's cost comes back, and 3 more brand
  points go (A: field corrections leave units in use).
- `dispute`: dispute the classification: 60% of the cost comes back, and the FDA answers with a
  warning letter (its hold and brand loss)."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import GameEvent
from tst.sim.ledger import CASH, RECALLS, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.medical import data as md
from tst.sim.medical.models import Inspection, Recall
from tst.sim.money import format_money, times
from tst.sim.state import GameState, with_product

CORRECT_BACK: Final = 0.4  # tunable-exempt: the template's text states it (describe.py)
DISPUTE_BACK: Final = 0.6  # tunable-exempt: the template's text states it
CORRECT_BRAND: Final = 3.0  # tunable-exempt: the template's text states it


def latest(state: GameState, product_id: int) -> Recall | None:
    rows = [r for r in state.med_recalls if r.product_id == product_id and r.klass == "I"]
    return max(rows, key=lambda r: r.id) if rows else None


def event_names(state: GameState, event: GameEvent) -> dict[str, str]:
    r = latest(state, event.product_id or -1)
    if r is None:
        return {"units": "every", "cost": "the field action"}
    return {"units": f"{r.units:,}", "cost": format_money(r.cost_cents)}


def medical_step(
    state: GameState, event: GameEvent, step: str, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    r = latest(state, event.product_id or -1)
    product = state.product(event.product_id or -1)
    if r is None or product is None:
        return state, [], []
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    hit = balance.medical.recall.brand_hit["I"]
    if step == "full":
        state = with_product(state, replace(product, brand=min(100.0, product.brand + hit / 2)))
        return state, [], []
    back = times(r.cost_cents, CORRECT_BACK if step == "correct" else DISPUTE_BACK)
    if back > 0:
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=r.company_id,
                memo=f"Recall cost avoided ({step}): {product.name}",
                debit=CASH,
                credit=RECALLS,
                amount=back,
            )
        )
    if step == "correct":
        state = with_product(state, replace(product, brand=max(0.0, product.brand - CORRECT_BRAND)))
        return state, entries, logs
    # dispute: the FDA answers with a warning letter (u = 0 draws the gravest finding it can)
    if md.cleared(state, product.id, md.FDA, state.turn):
        state, e, lg = _warning(state, r.company_id, balance, data)
        entries += e
        logs += lg
    return state, entries, logs


def _warning(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """A warning letter from the FDA, without a draw (the answer's stated consequence)."""

    ib = balance.medical.inspection
    turn = state.turn
    until = turn + balance.medical.review.warning_hold_months
    for p in state.company_products(company_id):
        if md.is_medical(p, data) and md.cleared(state, p.id, md.FDA, turn):
            state = with_product(state, replace(p, brand=max(0.0, p.brand - ib.warning_brand_hit)))
    iid = max((i.id for i in state.med_inspections), default=0) + 1
    rec = Inspection(iid, company_id, md.FDA, turn, "warning_letter", until, 0, True)
    state = replace(state, med_inspections=(*state.med_inspections, rec))
    log = inbox_item(
        turn,
        company_id,
        "medical_inspection_warning_letter",
        link_kind="medical",
        regulator=md.regulator(data, md.FDA).name,
        months=until - turn,
        fine_cents=0,
    )
    return state, [], [log]
