"""Countries, blocs and jurisdiction (docs/formulas.md 39.1).

- A **city** names its country (cities.yaml); a **facility** sits in its site's country, else
  its city's, else its region's default country; a **company** (a subsidiary) in its site's
  country, else its headquarters city's (the default HQ city when it has none).
- A country's **bloc** follows countries.yaml's history.
- A rule's **actor** is a country or a bloc; a company is in its **jurisdiction** when its
  country is the actor or sits in the actor bloc, or (a rule `by_ownership`) when a company
  owning at least half of it is (its group parent, M16).
- A **destination** list names countries, blocs, `all` (every country outside the actor's
  jurisdiction) and `affiliates` (companies owned >= 50% by a listed company: 39.3).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.models import Facility
from tst.sim.geopolitics.config import CountriesFile, RuleDef
from tst.sim.state import (
    CompanyState,
    GameState,
    group_companies,
    listed_id,
    owner_at,
    player_companies,
)

BLOC_LABELS: Final = {
    "us_aligned": "the US-aligned bloc",
    "china": "the China bloc",
    "non_aligned": "the non-aligned countries",
}
HALF: Final = 0.5  # tunable-exempt: by_ownership means at least half (39.3)
FULL_BP: Final = 10_000  # tunable-exempt: basis points in a whole stake
ALL = "all"  # tunable-exempt: export_controls.yaml destination word
AFFILIATES = "affiliates"  # tunable-exempt: export_controls.yaml destination word


def countries_of(data: GameData) -> CountriesFile:
    assert data.countries is not None
    return data.countries


def enabled(data: GameData) -> bool:
    """Whether M22's data is loaded (tests may load without it)."""
    return data.countries is not None and data.controls is not None


def group(state: GameState) -> tuple[CompanyState, ...]:
    """The player's group (M16, 31.1): the companies it runs and every company it owns,
    subsidiaries included. Export controls bind the group, not rivals (M22 decision)."""
    seen: dict[int, CompanyState] = {c.id: c for c in player_companies(state)}
    for c in group_companies(state, listed_id(state)):
        seen.setdefault(c.id, c)
    return tuple(sorted(seen.values(), key=lambda c: c.id))


def in_group(state: GameState, company_id: int) -> bool:
    return any(c.id == company_id for c in group(state))


def site_country(state: GameState, kind: str, item_id: int) -> str | None:
    for s in state.sites:
        if s.kind == kind and s.id == item_id:
            return s.country
    return None


def city_country(data: GameData, city: str) -> str:
    c = data.city(city).country
    if c is None:
        return countries_of(data).default_of(data.city(city).region).key
    return c


def company_country(
    state: GameState, company: CompanyState, balance: Balance, data: GameData
) -> str:
    explicit = site_country(state, "company", company.id)
    if explicit is not None:
        return explicit
    if company.is_rival:
        known = countries_of(data).rivals.get(company.name)
        if known is not None:
            return known
    return city_country(data, company.hq_city or balance.geo.default_hq_city)


def facility_country(state: GameState, facility: Facility, data: GameData) -> str:
    explicit = site_country(state, "facility", facility.id)
    if explicit is not None:
        return explicit
    if facility.city is not None:
        return city_country(data, facility.city)
    return countries_of(data).default_of(facility.region).key


def supplier_country(data: GameData, supplier: str, region: str | None = None) -> str | None:
    """A supplier's, maker's or foundry's country (countries.yaml sites), else its region's
    default."""
    countries = countries_of(data)
    if supplier in countries.sites:
        return countries.sites[supplier]
    return countries.default_of(region).key if region is not None else None


def bloc_of(data: GameData, country: str, turn: int) -> str:
    return countries_of(data).country(country).bloc_at(turn)


def is_country(data: GameData, name: str) -> bool:
    """A countries.yaml key: `china` is both a country and a bloc, and means the country."""
    return any(c.key == name for c in countries_of(data).countries)


def in_actor(data: GameData, actor: str, country: str, turn: int) -> bool:
    """`country` is the actor, or sits in the actor bloc this month."""
    if is_country(data, actor):
        return country == actor
    return bloc_of(data, country, turn) == actor


def destination_countries(data: GameData, rule: RuleDef, turn: int) -> frozenset[str]:
    """The countries a rule's destination list covers this month (entities and affiliates
    aside)."""
    countries = countries_of(data)
    out: set[str] = set()
    for d in rule.countries:
        if d == ALL:
            out |= {
                c.key for c in countries.countries if not in_actor(data, rule.actor, c.key, turn)
            }
        elif d == AFFILIATES:
            continue
        elif is_country(data, d):
            out.add(d)
        else:
            out |= {c.key for c in countries.countries if c.bloc_at(turn) == d}
    return frozenset(out)


def owners(state: GameState, company: CompanyState, share: float = HALF) -> Iterable[CompanyState]:
    """The companies owning at least `share` of `company` (M16's ownership records, up the
    chain while each holds that much), nearest first."""
    seen: set[int] = {company.id}
    current = company.id
    while True:
        holding = owner_at(state, current, state.turn)
        if holding is None or holding.owner_id in seen:
            return
        if holding.stake_at(state.turn) < share * FULL_BP:
            return
        seen.add(holding.owner_id)
        owner = state.company(holding.owner_id)
        yield owner
        current = owner.id


def in_jurisdiction(
    state: GameState, company: CompanyState, rule: RuleDef, balance: Balance, data: GameData
) -> bool:
    """Whether a rule binds `company` as a seller (module docstring)."""
    turn = state.turn
    if in_actor(data, rule.actor, company_country(state, company, balance, data), turn):
        return True
    if rule.by_ownership:
        return any(
            in_actor(data, rule.actor, company_country(state, o, balance, data), turn)
            for o in owners(state, company)
        )
    return False


def actor_region(data: GameData, balance: Balance, actor: str) -> str:
    """Where an actor's regulators sit, for M24's influence (39.3)."""
    if is_country(data, actor):
        return countries_of(data).country(actor).region
    return balance.geopolitics.actor_regions[actor]


def actor_label(data: GameData, actor: str) -> str:
    if is_country(data, actor):
        return countries_of(data).country(actor).label
    return BLOC_LABELS[actor]
