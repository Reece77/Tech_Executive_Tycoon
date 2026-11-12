"""Geopolitical events (docs/formulas.md 39.2-39.3), queued by the engine in phase 12 for the
next month (when the rule is announced, so nothing about it is known before).

**Who hears.** For each rule announced next month (and each détente, escalation and
listing), the player hears through one event:

- `geo_sales_hit_chips` / `geo_sales_hit` (critical) when the rule would restrict one of the
  group's products that has customers in a region with a destination country;
- `geo_supply_hit` (critical) when a group company in a destination buys a controlled
  commodity (it used some last month) or makes chips a controlled input feeds;
- `geo_rule_announced` (major) when the group is otherwise **touched**: it has unit-sale
  products, facilities other than data centres, mines or refineries;
- nothing otherwise (39.4 target 7: a software company plays exactly as before).

A `Notice` (turn, company, template, rule) is kept for each event; an event's {rule} is the
notice's, matched in id order among the month's events of the same template.

**Answers** (`geopolitics_step`): comply and absorb change nothing; licence requests licences
for every hit product and destination (free: the event is the request); variant launches the
hit chips' compliant variants (free); grey sells through distributors (listing risk); lobby
spends geopolitics.lobby.cents in the actor's region (6950) for lobby.influence points of M24
influence; accept changes nothing; appeal spends listing.appeal_cents and, with chance
listing.appeal_chance (stream `geopolitics` key (3, the company's stable key)), takes the
listing off.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.actions.hiring import Outcome
from tst.sim.commodities import costs
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import GeopoliticsRuleError
from tst.sim.events.models import GameEvent, QueuedEvent
from tst.sim.founder.models import Influence
from tst.sim.geopolitics import actions as ga
from tst.sim.geopolitics import listing, sales, world
from tst.sim.geopolitics import rules as gr
from tst.sim.geopolitics.config import RuleDef
from tst.sim.geopolitics.models import EntityListing, Notice
from tst.sim.geopolitics.rules import ActiveRule
from tst.sim.ledger import CASH, LOBBYING, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.state import (
    GameState,
    influence_of,
    with_influence,
    with_queued,
)

ANNOUNCED: Final = "geo_rule_announced"
SALES_HIT: Final = "geo_sales_hit"
CHIPS_HIT: Final = "geo_sales_hit_chips"
SUPPLY_HIT: Final = "geo_supply_hit"
DETENTE: Final = "geo_detente"
LISTED: Final = "geo_listed"
TEMPLATES: Final = (ANNOUNCED, SALES_HIT, CHIPS_HIT, SUPPLY_HIT, DETENTE, LISTED)
DETENTE_PREFIX: Final = "detente:"  # a notice's rule key for a détente
LISTING_PREFIX: Final = "listing:"  # a notice's rule key for a listing: listing:<actor>


# --- Who hears ------------------------------------------------------------------------------


def _would_restrict(
    state: GameState, rule: RuleDef, product_id: int, balance: Balance, data: GameData, turn: int
) -> list[str]:
    """Destination countries where a rule would restrict the product and it has customers."""
    product = state.product(product_id)
    if product is None or product.status not in ("live", "sunset", "development"):
        return []
    active = ActiveRule(rule, turn, None)
    if not sales.controls_product(active, product, balance, data):
        return []
    if not world.in_jurisdiction(state, state.company(product.company_id), rule, balance, data):
        return []
    dest = world.destination_countries(data, rule, turn)
    regions = {r.region for r in state.regional_segments_of(product_id) if r.customers > 0}
    if data.cities and any(s.customers > 0 for s in state.segments_of(product_id)):
        from tst.sim.geo.cities import home_region

        regions.add(home_region(state, balance, data))
    return sorted(
        c.key for r in regions for c in world.countries_of(data).of_region(r) if c.key in dest
    )


def sales_hits(
    state: GameState, rule: RuleDef, balance: Balance, data: GameData, turn: int
) -> list[tuple[int, str]]:
    """(product id, country) pairs the rule would close."""
    out: list[tuple[int, str]] = []
    for company in world.group(state):
        for product in state.company_products(company.id):
            out += [
                (product.id, c)
                for c in _would_restrict(state, rule, product.id, balance, data, turn)
            ]
    return out


def supply_hit(
    state: GameState, rule: RuleDef, balance: Balance, data: GameData, turn: int
) -> bool:
    goods = balance.geopolitics.goods
    dest = world.destination_countries(data, rule, turn)
    for company in world.group(state):
        if world.company_country(state, company, balance, data) not in dest:
            continue
        use = costs.company_use(state, company.id, balance, data) if state.production else {}
        for g in rule.goods:
            spec = goods[g]
            if spec.kind == "commodity" and use.get(spec.commodity or "", 0.0) > 0:
                return True
            if spec.kind == "input":
                for p in state.company_products(company.id):
                    if (
                        data.category(p.category).chip_type in spec.chip_types
                        and p.status == "live"
                    ):
                        return True
    return False


def touched(state: GameState, balance: Balance, data: GameData) -> bool:
    """The group has unit-sale products, facilities other than data centres, mines or
    refineries (module docstring)."""
    groups = {c.id for c in world.group(state)}
    for p in state.products:
        if p.company_id in groups and data.category(p.category).sells_units:
            return True
    centres = set(balance.power.paid_by)
    if any(f.company_id in groups and f.kind not in centres for f in state.facilities):
        return True
    return any(m.company_id in groups for m in state.mines) or any(
        r.company_id in groups for r in state.refineries
    )


def template_for(
    state: GameState, rule: RuleDef, balance: Balance, data: GameData, turn: int
) -> str | None:
    if not rule.news and rule.via is None:
        hits = sales_hits(state, rule, balance, data, turn)
        if hits:
            chips = any(
                ga.is_variant_product(p.category, balance, data)
                for pid, _ in hits
                if (p := state.product(pid)) is not None
            )
            return CHIPS_HIT if chips else SALES_HIT
        if supply_hit(state, rule, balance, data, turn):
            return SUPPLY_HIT
    return ANNOUNCED if touched(state, balance, data) else None


# --- Queueing -------------------------------------------------------------------------------


def queue(state: GameState, template: str, rule_key: str, due: int) -> GameState:
    company = state.player.id
    qid, ids = state.next_ids.take("queued")
    state = with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid, company_id=company, template_id=template, due_turn=due, source_event_id=None
        ),
    )
    return replace(
        state, geo_notices=(*state.geo_notices, Notice(due, company, template, rule_key))
    )


def announce(
    state: GameState,
    data: GameData,
    balance: Balance,
    arriving: list[ActiveRule],
    detentes: list[str],
    listings: list[EntityListing],
) -> GameState:
    """Queue next month's events (module docstring). `detentes`: notice keys of détentes."""
    due = state.turn + 1
    for a in arriving:
        template = template_for(state, a.rule, balance, data, max(due, a.start_turn))
        if template is not None:
            state = queue(state, template, a.key, due)
    if detentes and touched(state, balance, data):
        for key in detentes:
            state = queue(state, DETENTE, key, due)
    groups = {c.id for c in world.group(state)}
    for x in listings:
        if x.company_id in groups:
            state = queue(state, LISTED, f"{LISTING_PREFIX}{x.actor}", due)
    return state


# --- {rule} ---------------------------------------------------------------------------------


def notice_for(state: GameState, event: GameEvent) -> Notice | None:
    same = [
        n
        for n in state.geo_notices
        if n.turn == event.turn
        and n.company_id == event.company_id
        and n.template_id == event.template_id
    ]
    events = sorted(
        e.id
        for e in state.events
        if e.turn == event.turn
        and e.company_id == event.company_id
        and e.template_id == event.template_id
    )
    if not same:
        return None
    i = events.index(event.id) if event.id in events else 0
    return same[min(i, len(same) - 1)]


def rule_title(state: GameState, data: GameData, key: str) -> str:
    if key.startswith(LISTING_PREFIX):
        actor = key.removeprefix(LISTING_PREFIX)
        return f"{world.actor_label(data, actor)}'s entity list"
    if key.startswith(DETENTE_PREFIX):
        rule_key = key.removeprefix(DETENTE_PREFIX)
        detente = next((d for d in gr.controls_of(data).detentes if d.key == rule_key), None)
        if detente is not None:
            return detente.title
        return f"{gr.controls_of(data).rule(rule_key).title} is suspended for a year"
    return gr.controls_of(data).rule(key).title


def rule_names(state: GameState, data: GameData, event: GameEvent) -> dict[str, str]:
    notice = notice_for(state, event)
    if notice is None or not world.enabled(data):
        return {"rule": "the new rules"}
    return {"rule": rule_title(state, data, notice.rule_key)}


# --- Answers --------------------------------------------------------------------------------


def _lobby(
    state: GameState, company_id: int, region: str, balance: Balance, cents: int, why: str
) -> tuple[GameState, list[LedgerEntry]]:
    lb = balance.geopolitics.lobby
    record = influence_of(state, company_id, region) or Influence(company_id, region)
    state = with_influence(state, replace(record, value=min(100.0, record.value + lb.influence)))
    entry = LedgerEntry.transfer(
        turn=state.turn, company_id=company_id, memo=why, debit=LOBBYING, credit=CASH, amount=cents
    )
    return state, [entry] if cents > 0 else []


def geopolitics_step(
    state: GameState, event: GameEvent, step: str, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """An export-control event's answer (module docstring), applied by the engine."""
    notice = notice_for(state, event)
    if notice is None or not world.enabled(data):
        return state, [], []
    key = notice.rule_key
    company = event.company_id
    founder = state.founder_of(state.player.id)
    actor_id = founder.id if founder is not None else 0
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    if key.startswith(LISTING_PREFIX):
        actor = key.removeprefix(LISTING_PREFIX)
        if step == "appeal":
            lb = balance.geopolitics.listing
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=company,
                    memo="Entity-list appeal",
                    debit=LOBBYING,
                    credit=CASH,
                    amount=lb.appeal_cents,
                )
            )
            won = listing.appeal_won(state, company, balance)  # M23a: the stable key
            if won:
                state = replace(
                    state,
                    entity_listings=tuple(
                        x
                        for x in state.entity_listings
                        if not (x.company_id == company and x.actor == actor)
                    ),
                )
            logs.append(
                inbox_item(
                    state.turn,
                    company,
                    "listing_appeal_won" if won else "listing_appeal_lost",
                    link_kind="world",
                    link_id=company,
                    lister=world.actor_label(data, actor),
                )
            )
        return state, entries, logs
    if key.startswith(DETENTE_PREFIX):
        if step == "lobby":
            region = balance.geopolitics.actor_regions["us_aligned"]
            state, entries = _lobby(
                state,
                company,
                region,
                balance,
                balance.geopolitics.lobby.cents,
                "Lobbying: détente",
            )
        return state, entries, logs
    rule = gr.controls_of(data).rule(key)
    if step == "lobby":
        region = world.actor_region(data, balance, rule.actor)
        state, entries = _lobby(
            state,
            company,
            region,
            balance,
            balance.geopolitics.lobby.cents,
            f"Lobbying: {rule.title}",
        )
        return state, entries, logs
    hits = sales_hits(state, rule, balance, data, state.turn)
    for pid, country in hits:
        out: Outcome | None = None
        try:
            if step == "licence":
                out = ga.request_licence(
                    state, ga.RequestLicence(actor_id, pid, country), balance, data, free=True
                )
            elif step == "grey":
                out = ga.set_grey_route(
                    state, ga.SetGreyRoute(actor_id, pid, country), balance, data
                )
            elif step == "variant":
                product = state.product(pid)
                launched = any(v.product_id == pid and v.turn == state.turn for v in state.variants)
                if (
                    product is not None
                    and ga.is_variant_product(product.category, balance, data)
                    and not launched
                ):
                    out = ga.launch_variant(
                        state, ga.LaunchVariant(actor_id, pid), balance, data, free=True
                    )
        except GeopoliticsRuleError:  # a rule not yet in force, or a ban: nothing to request
            out = None
        if out is not None:
            state = out.state
            logs += list(out.log)
    return state, entries, logs


__all__ = ["TEMPLATES", "announce", "geopolitics_step", "rule_names"]
