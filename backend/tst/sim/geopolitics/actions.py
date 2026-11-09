"""Geopolitics' immediate actions (ADR-0014, docs/formulas.md 39.3).

- **Request a licence** for a product's sales to a country under each licence-regime rule that
  restricts it there (energy geopolitics.licence.energy). The decision comes
  `decision_months` later (phase 12, `decide`): approved with chance `approval x (1 +
  influence x I / 100)` (at most 1), I the company's M24 influence in the rule actor's region;
  an approved licence runs `term_months` (or to the rule's end).
- **Sell through distributors** (`grey`): keeps the country open without a licence, at a
  monthly risk of listing (listing.py); `stop` ends it.
- **Launch a compliant variant** of a chip product a `product` good covers (energy
  geopolitics.variant.energy): from this month it sells where a rule restricts it, at its
  quality less variant.quality_penalty there (sales.py); a rule that `voids_variants` closes
  variants launched before it, and a new launch reopens them.
- **Take a local partner** for a company sitting in a partner-market country (39.3: cloud in
  China): the market opens, and the partner takes its share (tariffs.py).

Stream `geopolitics` (id 55) key (1, licence id) decides a licence: one uniform.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import GeopoliticsRuleError
from tst.sim.founder import influence
from tst.sim.geopolitics import rules as gr
from tst.sim.geopolitics import sales, world
from tst.sim.geopolitics.draws import LICENCE, geo_draws
from tst.sim.geopolitics.models import Licence, Site, Variant
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_licence, with_site, with_variant

PRODUCT_LINK: Final = "product"
WORLD_LINK: Final = "world"


@dataclass(frozen=True, slots=True)
class RequestLicence:
    actor_id: int
    product_id: int
    country: str
    kind: Literal["request_licence"] = "request_licence"


@dataclass(frozen=True, slots=True)
class SetGreyRoute:
    actor_id: int
    product_id: int
    country: str
    on: bool = True
    kind: Literal["set_grey_route"] = "set_grey_route"


@dataclass(frozen=True, slots=True)
class LaunchVariant:
    actor_id: int
    product_id: int
    kind: Literal["launch_variant"] = "launch_variant"


@dataclass(frozen=True, slots=True)
class TakeLocalPartner:
    actor_id: int
    company_id: int | None = None  # a group company (default: the actor's own)
    kind: Literal["take_local_partner"] = "take_local_partner"


type GeopoliticsAction = RequestLicence | SetGreyRoute | LaunchVariant | TakeLocalPartner

ACTION_TYPES: Final[dict[str, type]] = {
    "request_licence": RequestLicence,
    "set_grey_route": SetGreyRoute,
    "launch_variant": LaunchVariant,
    "take_local_partner": TakeLocalPartner,
}


def _group(state: GameState) -> set[int]:
    return {c.id for c in world.group(state)}


def _product(state: GameState, actor_id: int, product_id: int):  # type: ignore[no-untyped-def]
    acting_company(state, actor_id)
    product = state.product(product_id)
    if product is None or product.company_id not in _group(state):
        raise GeopoliticsRuleError(f"product {product_id} is not one of the group's")
    return product


def licence_rules(
    state: GameState, product_id: int, country: str, balance: Balance, data: GameData
) -> list[gr.ActiveRule]:
    """Licence-regime rules restricting the product in `country` without an open licence."""
    product = state.product(product_id)
    assert product is not None
    return [
        a
        for a in sales.restricting(state, product, balance, data)
        if a.rule.regime == "licence"
        and country in world.destination_countries(data, a.rule, state.turn)
        and not sales.licence_open(state, product_id, a.key, country)
        and not any(
            x.product_id == product_id
            and x.rule_key == a.key
            and x.country == country
            and x.status == "pending"
            for x in state.licences
        )
    ]


def next_licence_id(state: GameState) -> int:
    return max((x.id for x in state.licences), default=0) + 1


def request_licence(
    state: GameState,
    action: RequestLicence,
    balance: Balance,
    data: GameData,
    *,
    free: bool = False,
) -> Outcome:
    product = _product(state, action.actor_id, action.product_id)
    found = licence_rules(state, product.id, action.country, balance, data)
    if not found:
        raise GeopoliticsRuleError(
            f"no licence is needed or possible for {product.name} in {action.country}"
        )
    if not free:
        state = spend_energy(
            state,
            action.actor_id,
            "request_licence",
            balance,
            cost=balance.geopolitics.licence.energy,
        )
    lb = balance.geopolitics.licence
    for a in found:
        licence = Licence(
            id=next_licence_id(state),
            company_id=product.company_id,
            product_id=product.id,
            rule_key=a.key,
            country=action.country,
            requested_turn=state.turn,
            decide_turn=state.turn + lb.decision_months,
        )
        state = with_licence(state, licence)
    country = world.countries_of(data).country(action.country).label
    log = inbox_item(
        state.turn,
        product.company_id,
        "licence_requested",
        link_kind=PRODUCT_LINK,
        link_id=product.id,
        product=product.name,
        country=country,
        decision=format_turn(state.turn + lb.decision_months),
    )
    return Outcome(state, (), (log,))


def set_grey_route(
    state: GameState, action: SetGreyRoute, balance: Balance, data: GameData
) -> Outcome:
    product = _product(state, action.actor_id, action.product_id)
    if action.on:
        restrict = [
            a
            for a in sales.restricting(state, product, balance, data)
            if action.country in world.destination_countries(data, a.rule, state.turn)
            and not sales.licence_open(state, product.id, a.key, action.country)
        ]
        if not restrict:
            raise GeopoliticsRuleError(f"{product.name} is not restricted in {action.country}")
        for a in restrict:
            state = with_licence(
                state,
                Licence(
                    id=next_licence_id(state),
                    company_id=product.company_id,
                    product_id=product.id,
                    rule_key=a.key,
                    country=action.country,
                    requested_turn=state.turn,
                    decide_turn=state.turn,
                    status="grey",
                ),
            )
        return Outcome(state)
    for x in state.licences:
        if x.product_id == product.id and x.country == action.country and x.status == "grey":
            state = with_licence(state, replace(x, status="expired", until_turn=state.turn - 1))
    return Outcome(state)


def is_variant_product(product_category: str, balance: Balance, data: GameData) -> bool:
    chip_type = data.category(product_category).chip_type
    return chip_type is not None and any(
        g.kind == "product" and chip_type in g.chip_types
        for g in balance.geopolitics.goods.values()
    )


def launch_variant(
    state: GameState, action: LaunchVariant, balance: Balance, data: GameData, *, free: bool = False
) -> Outcome:
    product = _product(state, action.actor_id, action.product_id)
    if not is_variant_product(product.category, balance, data):
        raise GeopoliticsRuleError(f"{product.name} is not a controlled chip")
    current = next((v for v in state.variants if v.product_id == product.id), None)
    if current is not None and current.turn == state.turn:
        raise GeopoliticsRuleError(f"{product.name}'s compliant variant launched this month")
    if not free:
        state = spend_energy(
            state,
            action.actor_id,
            "launch_variant",
            balance,
            cost=balance.geopolitics.variant.energy,
        )
    state = with_variant(state, Variant(product.id, state.turn))
    log = inbox_item(
        state.turn,
        product.company_id,
        "variant_launched",
        link_kind=PRODUCT_LINK,
        link_id=product.id,
        product=product.name,
        penalty=f"{balance.geopolitics.variant.quality_penalty:.0f}",
    )
    return Outcome(state, (), (log,))


def take_local_partner(
    state: GameState, action: TakeLocalPartner, balance: Balance, data: GameData
) -> Outcome:
    own = acting_company(state, action.actor_id)
    cid = action.company_id if action.company_id is not None else own
    if cid not in _group(state):
        raise GeopoliticsRuleError(f"company {cid} is not one of the group's")
    lp = balance.geopolitics.local_partner
    company = state.company(cid)
    country = world.company_country(state, company, balance, data)
    if country not in lp.countries:
        raise GeopoliticsRuleError(
            f"{company.name} sits in {country}; only {list(lp.countries)} need a local partner"
        )
    site = next((s for s in state.sites if s.kind == "company" and s.id == cid), None)
    if site is not None and site.local_partner:
        raise GeopoliticsRuleError(f"{company.name} already has a local partner")
    state = spend_energy(state, action.actor_id, "take_local_partner", balance, cost=lp.energy)
    state = with_site(state, Site("company", cid, country, local_partner=True))
    log = inbox_item(
        state.turn,
        cid,
        "local_partner_taken",
        link_kind=WORLD_LINK,
        link_id=cid,
        company=company.name,
        share=f"{lp.share:.0%}",
    )
    return Outcome(state, (), (log,))


def apply_geopolitics(
    state: GameState, action: GeopoliticsAction, balance: Balance, data: GameData
) -> Outcome:
    if not world.enabled(data):
        raise GeopoliticsRuleError("geopolitics data is not loaded")
    match action:
        case RequestLicence():
            return request_licence(state, action, balance, data)
        case SetGreyRoute():
            return set_grey_route(state, action, balance, data)
        case LaunchVariant():
            return launch_variant(state, action, balance, data)
        case TakeLocalPartner():
            return take_local_partner(state, action, balance, data)


# --- Phase 12: decisions ------------------------------------------------------------------


def approval_chance(state: GameState, licence: Licence, balance: Balance, data: GameData) -> float:
    """approval x (1 + influence x I / 100), at most 1 (39.3)."""
    active = next((a for a in gr.all_rules(state, data) if a.key == licence.rule_key), None)
    if active is None:
        return 0.0
    region = world.actor_region(data, balance, active.rule.actor)
    i = influence.of(state, licence.company_id, region)
    return min(1.0, active.rule.approval * (1 + balance.geopolitics.licence.influence * i / 100))


def decide(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Pending licences due this month are decided; approved ones past their term expire."""
    logs: list[LogItem] = []
    turn = state.turn
    for x in state.licences:
        if x.status == "approved" and x.until_turn is not None and x.until_turn < turn:
            state = with_licence(state, replace(x, status="expired"))
            continue
        if x.status != "pending" or x.decide_turn > turn:
            continue
        u = float(geo_draws(rng, turn, LICENCE, x.id).random())
        approved = u < approval_chance(state, x, balance, data)
        active = next(a for a in gr.all_rules(state, data) if a.key == x.rule_key)
        until = turn + balance.geopolitics.licence.term_months - 1
        if active.end_turn is not None:
            until = min(until, active.end_turn)
        state = with_licence(
            state,
            replace(
                x,
                status="approved" if approved else "denied",
                until_turn=until if approved else None,
            ),
        )
        product = state.product(x.product_id)
        logs.append(
            inbox_item(
                turn,
                x.company_id,
                "licence_approved" if approved else "licence_denied",
                link_kind=PRODUCT_LINK,
                link_id=x.product_id,
                product=product.name if product else "a product",
                country=world.countries_of(data).country(x.country).label,
                rule=active.rule.title,
                until=format_turn(until),
            )
        )
    return state, logs
