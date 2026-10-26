"""Immutable game state. Cash is never a field: it is derived from ledger balances (ADR-0003)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from tst.sim.hiring.models import Candidate, NextIds, Offer, PersonState, Search
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.money import Cents
from tst.sim.org.models import HiringPlan, OrgUnit, WorkPolicy
from tst.sim.people.models import Employment, Person, RevealState
from tst.sim.products.models import MarketSegment, Product, ProductSegment


@dataclass(frozen=True, slots=True)
class SaveMeta:
    name: str
    master_seed: int
    scenario_id: str
    difficulty: str


@dataclass(frozen=True, slots=True)
class CompanyState:
    id: int
    name: str
    is_player: bool
    stage: int  # spec section 3: 0 solo founder .. 5 conglomerate
    founded_turn: int
    mission: tuple[str, ...] = ()  # two interests.yaml keys (formulas.md section 7)
    work_policy: WorkPolicy = "office"  # the company root's policy (formulas.md 13.9)
    root_product_id: int | None = None  # the product the root's members work on (11.3, M3)
    arr_milestone_cents: int = 0  # highest ARR milestone announced in the inbox (M3a)


@dataclass(frozen=True, slots=True)
class GameState:
    save_meta: SaveMeta
    turn: int  # the next turn to be played; 0 = January 2010
    companies: tuple[CompanyState, ...]  # sorted by id
    people: tuple[Person, ...] = ()  # sorted by id
    employments: tuple[Employment, ...] = ()  # sorted by id
    reveals: tuple[RevealState, ...] = ()  # sorted by (observer_company_id, person_id)
    searches: tuple[Search, ...] = ()  # open searches, sorted by id
    candidates: tuple[Candidate, ...] = ()  # open candidates, sorted by person id
    offers: tuple[Offer, ...] = ()  # pending offers, sorted by id
    person_states: tuple[PersonState, ...] = ()  # sorted by person id
    units: tuple[OrgUnit, ...] = ()  # active org units, sorted by id (M2)
    plans: tuple[HiringPlan, ...] = ()  # hiring plans that are not closed, sorted by id (M2)
    products: tuple[Product, ...] = ()  # products that are not retired, sorted by id (M3)
    product_segments: tuple[ProductSegment, ...] = ()  # sorted by (product_id, segment)
    markets: tuple[MarketSegment, ...] = ()  # sorted by (category, segment)
    next_ids: NextIds = field(default_factory=NextIds)

    def company(self, company_id: int) -> CompanyState:
        for company in self.companies:
            if company.id == company_id:
                return company
        raise KeyError(company_id)

    def person(self, person_id: int) -> Person:
        for person in self.people:
            if person.id == person_id:
                return person
        raise KeyError(person_id)

    def staff(self, company_id: int) -> tuple[Employment, ...]:
        """Active and notice employments of a company, by employment id."""
        return tuple(
            e for e in self.employments if e.company_id == company_id and e.counts_as_staff
        )

    def reveal(self, observer_company_id: int, person_id: int) -> RevealState | None:
        for rev in self.reveals:
            if rev.observer_company_id == observer_company_id and rev.person_id == person_id:
                return rev
        return None

    def employment_of(self, person_id: int) -> Employment | None:
        """The person's active or notice employment, if any."""
        for e in self.employments:
            if e.person_id == person_id and e.counts_as_staff:
                return e
        return None

    def founder_of(self, company_id: int) -> Person | None:
        for e in self.staff(company_id):
            person = self.person(e.person_id)
            if person.is_founder:
                return person
        return None

    def person_state(self, person_id: int) -> PersonState:
        for ps in self.person_states:
            if ps.person_id == person_id:
                return ps
        return PersonState(person_id=person_id)

    def candidate(self, person_id: int) -> Candidate | None:
        for c in self.candidates:
            if c.person_id == person_id:
                return c
        return None

    def open_candidates(self, company_id: int) -> tuple[Candidate, ...]:
        return tuple(
            c for c in self.candidates if c.company_id == company_id and c.status == "open"
        )

    def search(self, search_id: int) -> Search | None:
        for s in self.searches:
            if s.id == search_id:
                return s
        return None

    def open_searches(self, company_id: int) -> tuple[Search, ...]:
        return tuple(s for s in self.searches if s.company_id == company_id and s.status == "open")

    def offer(self, offer_id: int) -> Offer | None:
        for o in self.offers:
            if o.id == offer_id:
                return o
        return None

    def pending_offers(self, company_id: int) -> tuple[Offer, ...]:
        return tuple(o for o in self.offers if o.company_id == company_id and o.status == "pending")

    def pending_offers_all(self) -> tuple[Offer, ...]:
        return tuple(o for o in self.offers if o.status == "pending")

    def pending_offer_for(self, candidate_id: int) -> Offer | None:
        for o in self.offers:
            if o.candidate_id == candidate_id and o.status == "pending":
                return o
        return None

    def unit(self, unit_id: int) -> OrgUnit | None:
        for u in self.units:
            if u.id == unit_id:
                return u
        return None

    def active_units(self, company_id: int) -> tuple[OrgUnit, ...]:
        return tuple(u for u in self.units if u.company_id == company_id and u.status == "active")

    def plan(self, plan_id: int) -> HiringPlan | None:
        for p in self.plans:
            if p.id == plan_id:
                return p
        return None

    def live_plans(self, company_id: int) -> tuple[HiringPlan, ...]:
        return tuple(p for p in self.plans if p.company_id == company_id and p.status != "closed")

    def product(self, product_id: int) -> Product | None:
        for p in self.products:
            if p.id == product_id:
                return p
        return None

    def company_products(self, company_id: int) -> tuple[Product, ...]:
        return tuple(p for p in self.products if p.company_id == company_id)

    def segments_of(self, product_id: int) -> tuple[ProductSegment, ...]:
        return tuple(s for s in self.product_segments if s.product_id == product_id)

    def product_segment(self, product_id: int, segment: str) -> ProductSegment | None:
        for s in self.product_segments:
            if s.product_id == product_id and s.segment == segment:
                return s
        return None

    def market(self, category: str, segment: str) -> MarketSegment | None:
        for m in self.markets:
            if m.category == category and m.segment == segment:
                return m
        return None

    def ledger_companies(self) -> tuple[CompanyState, ...]:
        """Companies with books: the player. Incumbents have no ledger until M5 (ADR-0017)."""
        return tuple(c for c in self.companies if c.is_player)

    @property
    def player(self) -> CompanyState:
        for company in self.companies:
            if company.is_player:
                return company
        raise LookupError("game state has no player company")


def company_cash(balances: LedgerBalances, company_id: int) -> Cents:
    """Cash for a company is the balance of its 1000_cash account."""
    return account_balance(balances, company_id, CASH)


# --- Updating tuples by key (each returns a new GameState) -----------------------------------


def _upsert[T](items: tuple[T, ...], item: T, key: Callable[[T], Any]) -> tuple[T, ...]:
    k = key(item)
    out = [x for x in items if key(x) != k]
    out.append(item)
    return tuple(sorted(out, key=key))


def with_person(state: GameState, person: Person) -> GameState:
    return replace(state, people=_upsert(state.people, person, lambda p: p.id))


def with_company(state: GameState, company: CompanyState) -> GameState:
    return replace(state, companies=_upsert(state.companies, company, lambda c: c.id))


def with_employment(state: GameState, employment: Employment) -> GameState:
    return replace(state, employments=_upsert(state.employments, employment, lambda e: e.id))


def with_reveal(state: GameState, reveal: RevealState) -> GameState:
    return replace(
        state,
        reveals=_upsert(state.reveals, reveal, lambda r: (r.observer_company_id, r.person_id)),
    )


def with_search(state: GameState, search: Search) -> GameState:
    return replace(state, searches=_upsert(state.searches, search, lambda s: s.id))


def with_candidate(state: GameState, candidate: Candidate) -> GameState:
    return replace(state, candidates=_upsert(state.candidates, candidate, lambda c: c.person_id))


def with_offer(state: GameState, offer: Offer) -> GameState:
    return replace(state, offers=_upsert(state.offers, offer, lambda o: o.id))


def with_unit(state: GameState, unit: OrgUnit) -> GameState:
    return replace(state, units=_upsert(state.units, unit, lambda u: u.id))


def with_plan(state: GameState, plan: HiringPlan) -> GameState:
    return replace(state, plans=_upsert(state.plans, plan, lambda p: p.id))


def with_product(state: GameState, product: Product) -> GameState:
    return replace(state, products=_upsert(state.products, product, lambda p: p.id))


def with_product_segment(state: GameState, segment: ProductSegment) -> GameState:
    return replace(
        state,
        product_segments=_upsert(
            state.product_segments, segment, lambda s: (s.product_id, s.segment)
        ),
    )


def with_market(state: GameState, market: MarketSegment) -> GameState:
    return replace(state, markets=_upsert(state.markets, market, lambda m: (m.category, m.segment)))


def with_person_state(state: GameState, person_state: PersonState) -> GameState:
    return replace(
        state, person_states=_upsert(state.person_states, person_state, lambda p: p.person_id)
    )
