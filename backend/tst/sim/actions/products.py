"""Product actions (ADR-0014): create, price, segments, staffing, marketing, launch, sunset
and cancel (docs/formulas.md 11.2, 11.3, 11.5), and the founder's scouting of a search (11.12).
They take effect at once and spend the actor's energy (formulas.md section 6).

Every rule an action could break raises `ProductRuleError` (or `LaunchNotReadyError`, which
names what is missing), changing nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.actions.org import active_unit, scout_candidates
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import (
    InvalidActionError,
    LaunchNotReadyError,
    ProductRuleError,
    UnknownProductError,
    UnknownSearchError,
)
from tst.sim.log import inbox_item
from tst.sim.products.models import Product, ProductSegment
from tst.sim.products.phases import (
    PRODUCT_LINK,
    current_feature,
    release_assignments,
    shown_turn,
)
from tst.sim.state import GameState, with_company, with_product, with_product_segment, with_unit

PRODUCT_NAME_MAX: Final = 80  # tunable-exempt: product.name column width


# --- Action types ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CreateProduct:
    actor_id: int
    name: str
    category: str
    segments: tuple[str, ...] = field(default_factory=tuple)
    kind: Literal["create_product"] = "create_product"

    def __post_init__(self) -> None:  # decision_log stores the segments as a JSON list
        object.__setattr__(self, "segments", tuple(self.segments))


@dataclass(frozen=True, slots=True)
class SetPrice:
    actor_id: int
    product_id: int
    segment: str
    price_cents: int  # monthly, per customer (per user for consumer apps)
    kind: Literal["set_price"] = "set_price"


@dataclass(frozen=True, slots=True)
class AddSegment:
    actor_id: int
    product_id: int
    segment: str
    kind: Literal["add_segment"] = "add_segment"


@dataclass(frozen=True, slots=True)
class AssignUnit:
    actor_id: int
    product_id: int
    unit_id: int | None  # None = the company root
    kind: Literal["assign_unit"] = "assign_unit"


@dataclass(frozen=True, slots=True)
class UnassignUnit:
    actor_id: int
    unit_id: int | None  # None = the company root
    kind: Literal["unassign_unit"] = "unassign_unit"


@dataclass(frozen=True, slots=True)
class SetMarketing:
    actor_id: int
    product_id: int
    budget_cents: int  # per month
    kind: Literal["set_marketing"] = "set_marketing"


@dataclass(frozen=True, slots=True)
class LaunchProduct:
    actor_id: int
    product_id: int
    kind: Literal["launch_product"] = "launch_product"


@dataclass(frozen=True, slots=True)
class SunsetProduct:
    actor_id: int
    product_id: int
    kind: Literal["sunset_product"] = "sunset_product"


@dataclass(frozen=True, slots=True)
class CancelProduct:
    actor_id: int
    product_id: int
    kind: Literal["cancel_product"] = "cancel_product"


@dataclass(frozen=True, slots=True)
class ScoutSearch:
    """scouting_month (formulas.md 4) on every open candidate of one search (11.12)."""

    actor_id: int
    search_id: int
    kind: Literal["scout_search"] = "scout_search"


type ProductAction = (
    CreateProduct
    | SetPrice
    | AddSegment
    | AssignUnit
    | UnassignUnit
    | SetMarketing
    | LaunchProduct
    | SunsetProduct
    | CancelProduct
    | ScoutSearch
)


# --- Shared steps ---------------------------------------------------------------------------


def own_product(state: GameState, company_id: int, product_id: int) -> Product:
    """A product of the acting company that is not retired."""
    product = state.product(product_id)
    if product is None or product.company_id != company_id or product.status == "retired":
        raise UnknownProductError(f"no product {product_id}")
    return product


def _positive_cents(value: int, what: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProductRuleError(f"{what} must be a positive amount in cents")


def _clean_name(state: GameState, company_id: int, name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned:
        raise ProductRuleError("a product needs a name")
    if len(cleaned) > PRODUCT_NAME_MAX:
        raise ProductRuleError(f"a product name may have at most {PRODUCT_NAME_MAX} characters")
    taken = {p.name.casefold() for p in state.company_products(company_id) if p.status != "retired"}
    if cleaned.casefold() in taken:
        raise ProductRuleError(f"there is already a product named {cleaned!r}")
    return cleaned


def assignment_of(state: GameState, company_id: int, unit_id: int | None) -> int | None:
    """The product a unit (or the company root) works on, if any."""
    if unit_id is None:
        return state.company(company_id).root_product_id
    unit = state.unit(unit_id)
    return unit.product_id if unit is not None else None


def launch_problems(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> list[str]:
    """What still stands between a product in development and its launch (11.2)."""
    pb = balance.products
    problems = []
    if product.status != "in_development":
        problems.append(f"it is already {product.status.replace('_', ' ')}")
        return problems
    if product.quality < pb.launch_min_quality:
        problems.append(f"quality {product.quality:.0f} of the {pb.launch_min_quality:.0f} needed")
    feature = current_feature(product, data, shown_turn(state))
    if feature < pb.launch_min_feature:
        problems.append(f"feature score {feature:.0f} of the {pb.launch_min_feature:.0f} needed")
    for seg in state.segments_of(product.id):
        if seg.price_cents is None:
            problems.append(f"a price for {data.segment(seg.segment).label}")
    return problems


# --- Actions --------------------------------------------------------------------------------


def create_product(
    state: GameState, action: CreateProduct, balance: Balance, data: GameData
) -> Outcome:
    company = acting_company(state, action.actor_id)
    name = _clean_name(state, company, action.name)
    if action.category not in {c.key for c in data.categories}:
        raise ProductRuleError(f"unknown category {action.category!r}")
    category = data.category(action.category)
    if not action.segments:
        raise ProductRuleError("a product needs at least one segment")
    if len(set(action.segments)) != len(action.segments):
        raise ProductRuleError("a segment is listed twice")
    for seg in action.segments:
        if seg not in category.segment_keys:
            raise ProductRuleError(f"{category.label} does not sell to segment {seg!r}")
    state = spend_energy(state, action.actor_id, "create_product", balance)
    product_id, ids = state.next_ids.take("product")
    product = Product(
        id=product_id,
        company_id=company,
        category=category.key,
        name=name,
        status="in_development",
        quality=balance.products.start_quality,
        feature_points=0.0,
        brand=0.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
    )
    state = replace(with_product(state, product), next_ids=ids)
    for seg in category.segment_keys:  # categories.yaml order
        if seg in action.segments:
            state = with_product_segment(
                state, ProductSegment(product_id, seg, None, added_turn=state.turn)
            )
    return Outcome(state)


def set_price(state: GameState, action: SetPrice, balance: Balance) -> Outcome:
    company = acting_company(state, action.actor_id)
    product = own_product(state, company, action.product_id)
    seg = state.product_segment(product.id, action.segment)
    if seg is None:
        raise ProductRuleError(f"{product.name} does not sell to segment {action.segment!r}")
    _positive_cents(action.price_cents, "a price")
    if seg.price_cents == action.price_cents:
        raise ProductRuleError("that is already the price")
    state = spend_energy(state, action.actor_id, "set_price", balance)
    return Outcome(with_product_segment(state, replace(seg, price_cents=action.price_cents)))


def add_segment(state: GameState, action: AddSegment, balance: Balance, data: GameData) -> Outcome:
    """Customers start at 0; the segment sells once it has a price (11.2)."""
    company = acting_company(state, action.actor_id)
    product = own_product(state, company, action.product_id)
    if product.status == "sunset":
        raise ProductRuleError(f"{product.name} is being sunset")
    category = data.category(product.category)
    if action.segment not in category.segment_keys:
        raise ProductRuleError(f"{category.label} does not sell to segment {action.segment!r}")
    if state.product_segment(product.id, action.segment) is not None:
        raise ProductRuleError(f"{product.name} already sells to that segment")
    state = spend_energy(state, action.actor_id, "add_segment", balance)
    seg = ProductSegment(product.id, action.segment, None, added_turn=state.turn)
    return Outcome(with_product_segment(state, seg))


def assign_unit(state: GameState, action: AssignUnit, balance: Balance) -> Outcome:
    """A unit (or the root) works on at most one product (11.3)."""
    company = acting_company(state, action.actor_id)
    product = own_product(state, company, action.product_id)
    if action.unit_id is not None:
        active_unit(state, company, action.unit_id)
    current = assignment_of(state, company, action.unit_id)
    where = "the company" if action.unit_id is None else "that unit"
    if current == product.id:
        raise ProductRuleError(f"{where} already works on {product.name}")
    if current is not None:
        other = state.product(current)
        other_name = other.name if other is not None else f"product {current}"
        raise ProductRuleError(f"{where} already works on {other_name}; unassign it first")
    state = spend_energy(state, action.actor_id, "assign_unit", balance)
    if action.unit_id is None:
        return Outcome(
            with_company(state, replace(state.company(company), root_product_id=product.id))
        )
    unit = active_unit(state, company, action.unit_id)
    return Outcome(with_unit(state, replace(unit, product_id=product.id)))


def unassign_unit(state: GameState, action: UnassignUnit, balance: Balance) -> Outcome:
    company = acting_company(state, action.actor_id)
    if action.unit_id is not None:
        active_unit(state, company, action.unit_id)
    if assignment_of(state, company, action.unit_id) is None:
        where = "the company" if action.unit_id is None else "that unit"
        raise ProductRuleError(f"{where} does not work on a product")
    state = spend_energy(state, action.actor_id, "unassign_unit", balance)
    if action.unit_id is None:
        return Outcome(with_company(state, replace(state.company(company), root_product_id=None)))
    unit = active_unit(state, company, action.unit_id)
    return Outcome(with_unit(state, replace(unit, product_id=None)))


def set_marketing(state: GameState, action: SetMarketing, balance: Balance) -> Outcome:
    """Paid in phase 6 each month, even with negative cash until M4 (11.8)."""
    company = acting_company(state, action.actor_id)
    product = own_product(state, company, action.product_id)
    budget = action.budget_cents
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
        raise ProductRuleError("a marketing budget must be zero or more cents")
    if budget == product.marketing_budget_cents:
        raise ProductRuleError("that is already the budget")
    state = spend_energy(state, action.actor_id, "set_marketing", balance)
    return Outcome(with_product(state, replace(product, marketing_budget_cents=budget)))


def launch_product(
    state: GameState, action: LaunchProduct, balance: Balance, data: GameData
) -> Outcome:
    """Allowed at quality >= 25 and feature score >= 30 with every segment priced (11.2)."""
    company = acting_company(state, action.actor_id)
    product = own_product(state, company, action.product_id)
    problems = launch_problems(state, product, balance, data)
    if problems:
        raise LaunchNotReadyError(f"{product.name} cannot launch yet: needs " + "; ".join(problems))
    state = spend_energy(state, action.actor_id, "launch_product", balance)
    launched = replace(product, status="live", launched_turn=state.turn)
    labels = [data.segment(s.segment).label for s in state.segments_of(product.id)]
    note = inbox_item(
        state.turn,
        company,
        "product_launched",
        link_kind=PRODUCT_LINK,
        link_id=product.id,
        product=product.name,
        segments=_join(labels),
    )
    return Outcome(with_product(state, launched), log=(note,))


def sunset_product(state: GameState, action: SunsetProduct, balance: Balance) -> Outcome:
    """No new customers; existing ones churn 3x faster; cannot be undone (11.2)."""
    company = acting_company(state, action.actor_id)
    product = own_product(state, company, action.product_id)
    if product.status == "in_development":
        raise ProductRuleError(
            f"{product.name} is still in development; cancel its development instead"
        )
    if product.status != "live":
        raise ProductRuleError(f"only a live product can be sunset; {product.name} is not live")
    state = spend_energy(state, action.actor_id, "sunset_product", balance)
    return Outcome(with_product(state, replace(product, status="sunset", sunset_turn=state.turn)))


def cancel_product(state: GameState, action: CancelProduct, balance: Balance) -> Outcome:
    """A product in development retires at once and its units are freed (11.2, M3b)."""
    company = acting_company(state, action.actor_id)
    product = own_product(state, company, action.product_id)
    if product.status != "in_development":
        raise ProductRuleError(
            f"only a product in development can be cancelled; {product.name} is "
            f"{product.status.replace('_', ' ')}"
        )
    state = spend_energy(state, action.actor_id, "cancel_product", balance)
    state = with_product(state, replace(product, status="retired", retired_turn=state.turn))
    return Outcome(release_assignments(state, product.id))


def scout_search(
    state: GameState, action: ScoutSearch, balance: Balance, data: GameData
) -> Outcome:
    """The delegates' scouting pass (13.10 step 4), over one search's open candidates."""
    company = acting_company(state, action.actor_id)
    search = state.search(action.search_id)
    targets = [c for c in state.open_candidates(company) if c.search_id == action.search_id]
    if search is None and not targets:
        raise UnknownSearchError(f"no search {action.search_id}")
    if not targets:
        raise InvalidActionError(f"search {action.search_id} has no open candidates to scout")
    state = spend_energy(state, action.actor_id, "scout_search", balance)
    return Outcome(scout_candidates(state, company, action.actor_id, targets, balance, data))


def _join(labels: list[str]) -> str:
    """'SMB', 'SMB and Mid-market', 'SMB, Mid-market and Enterprise'."""
    if len(labels) <= 1:
        return "".join(labels)
    return ", ".join(labels[:-1]) + " and " + labels[-1]
