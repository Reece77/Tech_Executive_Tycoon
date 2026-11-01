"""Placeholder names for an event (docs/formulas.md 16.4) and template rendering. Only what
the player can see: names, a unit's name, a product's name, a segment's label, a rival's
name and the runway in whole months.
"""

from __future__ import annotations

from collections.abc import Mapping

from tst.sim.data_models import GameData
from tst.sim.events.data import PLACEHOLDER_RE
from tst.sim.people.models import Person
from tst.sim.state import GameState


def full_name(person: Person) -> str:
    return f"{person.first_name} {person.last_name}"


def placeholder_names(
    state: GameState,
    data: GameData,
    company_id: int,
    *,
    person_ids: tuple[int, ...] = (),
    unit_id: int | None = None,
    product_id: int | None = None,
    segment: str | None = None,
    rival_id: int | None = None,
    months: int | None = None,
    amount: str | None = None,
    lender: str | None = None,
) -> dict[str, str]:
    company = state.company(company_id)
    founder = state.founder_of(company_id)
    names = {"company": company.name, "founder": full_name(founder) if founder else "the founder"}
    people = [state.person(p) for p in person_ids if any(x.id == p for x in state.people)]
    if people:
        names["person"] = full_name(people[0])
    if len(people) > 1:
        names["other"] = full_name(people[1])
    # The company root has no unit row: its {unit} is the company (M7c: an unhappy root
    # had no unit id and no people, and its title showed "{unit}" as written).
    unit = state.unit(unit_id) if unit_id is not None else None
    names["unit"] = unit.name if unit is not None else company.name
    product = state.product(product_id) if product_id is not None else None
    if product is not None:
        names["product"] = product.name
    if segment is not None:
        names["segment"] = data.segment(segment).label
    if rival_id is not None:
        names["rival"] = state.company(rival_id).name
    if months is not None:
        names["months"] = str(months)
    if amount is not None:
        names["amount"] = amount
    if lender is not None:
        names["lender"] = lender
    return names


def loan_names(state: GameState, data: GameData, loan_id: int | None) -> dict[str, str]:
    """{lender} and {amount} (the balance) for a lender event (M10, 20.3)."""
    loan = state.loan(loan_id) if loan_id is not None else None
    if loan is None:
        return {}
    lender = next((x.name for x in data.lenders if x.key == loan.lender), loan.lender)
    return {"lender": lender, "amount": f"${loan.balance_cents / 100:,.0f}"}  # tunable-exempt


def render(text: str, names: Mapping[str, str]) -> str:
    """Fill {placeholders}; an unknown one is left as written (templates are checked at load)."""
    return PLACEHOLDER_RE.sub(lambda m: names.get(m.group(1), m.group(0)), text)
