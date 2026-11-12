"""The entity list (docs/formulas.md 39.3).

Each month (phase 12) every company of the player's group not yet listed by an actor risks it:

- **selling unlicensed** (a `grey` route under a biting rule): chance listing.grey_monthly a
  month, listed by the rule's actor;
- **ownership**: a company at least listing.owned_share owned by a company the actor listed
  (its group parent, M16) is listed at once while an `affiliates` rule of that actor bites,
  else with chance listing.owned_monthly a month.

A listed company gets no controlled inputs from the actor (supply.py: no wafers from foundries
in its jurisdiction). Stream `geopolitics` (id 55) key (2, the company's stable key): two
uniforms a month (grey, ownership), drawn whenever the company is eligible for either. An appeal
draws on key (3, the stable key) (M23a, Codex review 5 finding 8: `company_key`, never the
database id, which an unrelated company founded earlier moves).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.geopolitics import rules as gr
from tst.sim.geopolitics import world
from tst.sim.geopolitics.draws import APPEAL, LISTING, geo_draws
from tst.sim.geopolitics.models import EntityListing
from tst.sim.rivals.models import player_key
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def company_key(state: GameState, company_id: int) -> tuple[int, ...]:
    """A group company's stable key for its draws (ADR-0013; M15r's `player_key`): a founded
    subsidiary's (SUBSIDIARY_KEY, ordinal), the first company's id."""
    company = state.company(company_id)
    return player_key(company.id, company.rival_key)


def appeal_won(state: GameState, company_id: int, balance: Balance) -> bool:
    """An entity-list appeal's draw (39.3): listing.appeal_chance on stream `geopolitics` key
    (3, the stable key), seeded by the save and the month."""
    gen = geo_draws(
        RngFactory(state.save_meta.master_seed), state.turn, APPEAL, *company_key(state, company_id)
    )
    return float(gen.random()) < balance.geopolitics.listing.appeal_chance


def listed(state: GameState, company_id: int, actor: str) -> bool:
    return any(x.company_id == company_id and x.actor == actor for x in state.entity_listings)


def affiliates_rule(state: GameState, data: GameData, actor: str) -> bool:
    return any(
        a.rule.actor == actor and world.AFFILIATES in a.rule.countries
        for a in gr.in_force(state, data)
        if not a.rule.news
    )


def grey_actors(state: GameState, company_id: int, data: GameData) -> list[str]:
    biting = {a.key: a for a in gr.biting(state, data)}
    actors: list[str] = []
    for x in state.licences:
        if x.company_id == company_id and x.status == "grey" and x.rule_key in biting:
            actor = biting[x.rule_key].rule.actor
            if actor not in actors:
                actors.append(actor)
    return actors


def owner_actors(state: GameState, company_id: int, balance: Balance) -> list[str]:
    company = state.company(company_id)
    actors: list[str] = []
    for owner in world.owners(state, company, balance.geopolitics.listing.owned_share):
        for x in state.entity_listings:
            if x.company_id == owner.id and x.actor not in actors:
                actors.append(x.actor)
    return actors


def listing_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[EntityListing]]:
    """The month's new listings (module docstring), by company id."""
    lb = balance.geopolitics.listing
    new: list[EntityListing] = []
    turn = state.turn
    for company in sorted(world.group(state), key=lambda c: c.id):
        grey = [a for a in grey_actors(state, company.id, data) if not listed(state, company.id, a)]
        owned = [
            a for a in owner_actors(state, company.id, balance) if not listed(state, company.id, a)
        ]
        if not grey and not owned:
            continue
        key = company_key(state, company.id)
        u_grey, u_owned = (float(x) for x in geo_draws(rng, turn, LISTING, *key).random(2))
        if grey and u_grey < lb.grey_monthly:
            new.append(EntityListing(company.id, grey[0], turn, "sold controlled goods unlicensed"))
            continue
        for actor in owned:
            if affiliates_rule(state, data, actor) or u_owned < lb.owned_monthly:
                new.append(EntityListing(company.id, actor, turn, "owned by a listed company"))
                break
    if new:
        state = replace(state, entity_listings=(*state.entity_listings, *new))
    return state, new
