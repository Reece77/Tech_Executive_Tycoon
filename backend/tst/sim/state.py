"""Immutable game state. Cash is never a field: it is derived from ledger balances (ADR-0003)."""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from tst.sim.events.models import GameEvent, QueuedEvent, Storyline
from tst.sim.finance.macro import MacroMonth
from tst.sim.finance.models import (
    BoardSeat,
    CapEntry,
    FundingRound,
    GameOutcome,
    Loan,
    OptionGrant,
    Safe,
    TermSheet,
)
from tst.sim.geo.models import Office, ProductRegion, RegionalMarket, RegionalSegment
from tst.sim.hiring.models import Candidate, NextIds, Offer, PersonState, Search
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.money import Cents
from tst.sim.org.models import ExecSeat, HiringPlan, OrgUnit, WorkPolicy
from tst.sim.people.models import Employment, Person, RevealState
from tst.sim.people.relationships import Relationship
from tst.sim.products.models import MarketSegment, Product, ProductSegment
from tst.sim.rivals.models import (
    FreeAgent,
    PoachApproach,
    RivalEffect,
    RivalMove,
    SegmentShare,
    WorkforcePool,
)


@dataclass(frozen=True, slots=True)
class SaveMeta:
    name: str
    master_seed: int
    scenario_id: str
    difficulty: str
    game_state: GameOutcome = "active"  # ADR-0018 section 4
    ended_turn: int | None = None


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
    mrr_history: tuple[int, ...] = ()  # MRR at the last month ends, oldest first (M4, 14.3)
    insolvent_months: int = 0  # consecutive month ends with cash < 0 after phase 7 (14.7)
    # (stage, turn) each time a stage was reached, oldest first; new games start with the
    # starting stage at the founding turn; saves from before M4b may lack earlier stages (M4b)
    stage_history: tuple[tuple[int, int], ...] = ()
    # Rivals (M5, formulas.md 15): personality key; the builder pool's skill d and the
    # margin its staff is sized for (incumbents); startups are founded in play.
    personality: str | None = None
    builder_skill: float | None = None
    target_margin_bp: int | None = None
    is_startup: bool = False
    failed_turn: int | None = None  # a rival that went bankrupt (15.1, 14.7)
    last_raise_turn: int | None = None  # a startup's last funding attempt (15.4)
    # M10 (20.3): the player's operating result and burn at the last month ends, oldest
    # first, for covenants and the bank loan's gate.
    op_history: tuple[int, ...] = ()
    burn_history: tuple[int, ...] = ()
    hq_city: str | None = None  # cities.yaml key; None = geo.default_hq_city (M9, 19.1)

    @property
    def is_rival(self) -> bool:
        return not self.is_player

    @property
    def alive(self) -> bool:
        return self.failed_turn is None


def reach_stage(company: CompanyState, stage: int, turn: int) -> CompanyState:
    """The company at `stage`, recording the turn it got there (M4b)."""
    if stage == company.stage:
        return company
    return replace(company, stage=stage, stage_history=(*company.stage_history, (stage, turn)))


def stage_since(company: CompanyState) -> int | None:
    """The turn the current stage was reached; None when a pre-M4b save did not record it."""
    for stage, turn in reversed(company.stage_history):
        if stage == company.stage:
            return turn
    return None


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
    cap_entries: tuple[CapEntry, ...] = ()  # sorted by id (M4)
    grants: tuple[OptionGrant, ...] = ()  # every option grant, sorted by id (M4)
    safes: tuple[Safe, ...] = ()  # every SAFE and bridge, sorted by id (M4)
    rounds: tuple[FundingRound, ...] = ()  # every priced round, sorted by id (M4)
    term_sheets: tuple[TermSheet, ...] = ()  # every term sheet, sorted by id (M4)
    seats: tuple[BoardSeat, ...] = ()  # board seats, sorted by id (M4)
    pools: tuple[WorkforcePool, ...] = ()  # rival workforce pools, by (company_id, function) (M5)
    rival_effects: tuple[RivalEffect, ...] = ()  # running effects, sorted by id (M5)
    rival_moves: tuple[RivalMove, ...] = ()  # the last 24 months of rival moves, by id (M5)
    approaches: tuple[PoachApproach, ...] = ()  # pending approaches, sorted by id (M5)
    segment_shares: tuple[SegmentShare, ...] = ()  # by (product_id, segment) (M5)
    free_agents: tuple[FreeAgent, ...] = ()  # available free agents, by person id (M6.0)
    relationships: tuple[Relationship, ...] = ()  # the player's pairs, by (a, b) (M6, 16.7)
    events: tuple[GameEvent, ...] = ()  # the last 24 months' events and any open, by id (M6)
    storylines: tuple[Storyline, ...] = ()  # active storylines, by id (M6, 16.6)
    queued: tuple[QueuedEvent, ...] = ()  # follow-ups not yet shown, by id (M6, 16.3)
    exec_seats: tuple[ExecSeat, ...] = ()  # seats ever filled, by (company_id, seat) (M8, 18.3)
    macro: MacroMonth | None = None  # the indicators phase 1 last set (M10, 20.1)
    loans: tuple[Loan, ...] = ()  # every loan, sorted by id (M10, 20.3)
    # M9 (19.2, 19.5): open offices by id; other regions' markets by (category, segment,
    # region); products' launches there by (product_id, region); their segments there by
    # (product_id, region, segment). The home region stays in markets and product_segments.
    offices: tuple[Office, ...] = ()
    regional_markets: tuple[RegionalMarket, ...] = ()
    product_regions: tuple[ProductRegion, ...] = ()
    regional_segments: tuple[RegionalSegment, ...] = ()
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

    # --- Finance (M4) ----------------------------------------------------------------------

    @property
    def ended(self) -> bool:
        """The game is over (ADR-0018 section 4)."""
        return self.save_meta.game_state != "active"

    def company_cap(self, company_id: int) -> tuple[CapEntry, ...]:
        return tuple(e for e in self.cap_entries if e.company_id == company_id)

    def company_grants(self, company_id: int) -> tuple[OptionGrant, ...]:
        return tuple(g for g in self.grants if g.company_id == company_id)

    def grant_for(self, employment_id: int) -> OptionGrant | None:
        for g in self.grants:
            if g.employment_id == employment_id:
                return g
        return None

    def company_safes(self, company_id: int) -> tuple[Safe, ...]:
        return tuple(s for s in self.safes if s.company_id == company_id)

    def safe(self, safe_id: int) -> Safe | None:
        for s in self.safes:
            if s.id == safe_id:
                return s
        return None

    def company_rounds(self, company_id: int) -> tuple[FundingRound, ...]:
        return tuple(r for r in self.rounds if r.company_id == company_id)

    def funding_round(self, round_id: int) -> FundingRound | None:
        for r in self.rounds:
            if r.id == round_id:
                return r
        return None

    def sheets_of(self, round_id: int) -> tuple[TermSheet, ...]:
        return tuple(t for t in self.term_sheets if t.round_id == round_id)

    def term_sheet(self, sheet_id: int) -> TermSheet | None:
        for t in self.term_sheets:
            if t.id == sheet_id:
                return t
        return None

    def company_loans(self, company_id: int) -> tuple[Loan, ...]:
        return tuple(x for x in self.loans if x.company_id == company_id)

    def loan(self, loan_id: int) -> Loan | None:
        return next((x for x in self.loans if x.id == loan_id), None)

    def board(self, company_id: int) -> tuple[BoardSeat, ...]:
        return tuple(s for s in self.seats if s.company_id == company_id)

    def ledger_companies(self) -> tuple[CompanyState, ...]:
        """Companies with books: the player and every rival still in business (M5, 15.1)."""
        return tuple(c for c in self.companies if c.is_player or c.failed_turn is None)

    def company_pools(self, company_id: int) -> tuple[WorkforcePool, ...]:
        return tuple(p for p in self.pools if p.company_id == company_id)

    def rivals(self) -> tuple[CompanyState, ...]:
        """Rival companies still in business (M5)."""
        return tuple(c for c in self.companies if not c.is_player and c.failed_turn is None)

    def event(self, event_id: int) -> GameEvent | None:
        return next((e for e in self.events if e.id == event_id), None)

    def open_events(self, company_id: int) -> tuple[GameEvent, ...]:
        """Events shown this month or earlier that are not answered yet."""
        return tuple(
            e
            for e in self.events
            if e.company_id == company_id and e.is_open and e.turn <= self.turn
        )

    def storyline(self, storyline_id: int) -> Storyline | None:
        return next((s for s in self.storylines if s.id == storyline_id), None)

    def relationship_map(self) -> dict[tuple[int, int], Relationship]:
        return {r.key: r for r in self.relationships}

    def relationships_of(self, person_id: int) -> tuple[Relationship, ...]:
        return tuple(r for r in self.relationships if person_id in r.key)

    def seat_holder(self, company_id: int, seat: str) -> int | None:
        for s in self.exec_seats:
            if s.company_id == company_id and s.seat == seat:
                return s.person_id
        return None

    def seat_of(self, person_id: int) -> str | None:
        """The seat a person holds, if any (M8)."""
        for s in self.exec_seats:
            if s.person_id == person_id:
                return s.seat
        return None

    # --- Geography (M9) -------------------------------------------------------------------

    def office(self, office_id: int) -> Office | None:
        return next((o for o in self.offices if o.id == office_id), None)

    def company_offices(self, company_id: int) -> tuple[Office, ...]:
        return tuple(o for o in self.offices if o.company_id == company_id and o.status == "open")

    def regional_market(self, category: str, segment: str, region: str) -> RegionalMarket | None:
        for m in self.regional_markets:
            if (m.category, m.segment, m.region) == (category, segment, region):
                return m
        return None

    def regions_of(self, product_id: int) -> tuple[ProductRegion, ...]:
        return tuple(r for r in self.product_regions if r.product_id == product_id)

    def product_region(self, product_id: int, region: str) -> ProductRegion | None:
        for r in self.product_regions:
            if r.product_id == product_id and r.region == region:
                return r
        return None

    def regional_segments_of(
        self, product_id: int, region: str | None = None
    ) -> tuple[RegionalSegment, ...]:
        return tuple(
            s
            for s in self.regional_segments
            if s.product_id == product_id and (region is None or s.region == region)
        )

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
    """`items` (sorted by key, keys unique) with `item` replacing the one with its key, or
    inserted in order. A binary search instead of a re-sort: phases update people one at a
    time (M6 sub-task 0)."""
    k = key(item)
    i = bisect_left(items, k, key=key)
    if i < len(items) and key(items[i]) == k:
        return (*items[:i], item, *items[i + 1 :])
    return (*items[:i], item, *items[i:])


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


def with_cap_entry(state: GameState, entry: CapEntry) -> GameState:
    return replace(state, cap_entries=_upsert(state.cap_entries, entry, lambda e: e.id))


def with_grant(state: GameState, grant: OptionGrant) -> GameState:
    return replace(state, grants=_upsert(state.grants, grant, lambda g: g.id))


def with_safe(state: GameState, safe: Safe) -> GameState:
    return replace(state, safes=_upsert(state.safes, safe, lambda s: s.id))


def with_round(state: GameState, funding_round: FundingRound) -> GameState:
    return replace(state, rounds=_upsert(state.rounds, funding_round, lambda r: r.id))


def with_term_sheet(state: GameState, sheet: TermSheet) -> GameState:
    return replace(state, term_sheets=_upsert(state.term_sheets, sheet, lambda t: t.id))


def with_pool(state: GameState, pool: WorkforcePool) -> GameState:
    return replace(state, pools=_upsert(state.pools, pool, lambda p: (p.company_id, p.function)))


def with_rival_effect(state: GameState, effect: RivalEffect) -> GameState:
    return replace(state, rival_effects=_upsert(state.rival_effects, effect, lambda e: e.id))


def with_rival_move(state: GameState, move: RivalMove) -> GameState:
    return replace(state, rival_moves=_upsert(state.rival_moves, move, lambda m: m.id))


def with_approach(state: GameState, approach: PoachApproach) -> GameState:
    return replace(state, approaches=_upsert(state.approaches, approach, lambda a: a.id))


def with_free_agent(state: GameState, agent: FreeAgent) -> GameState:
    return replace(state, free_agents=_upsert(state.free_agents, agent, lambda a: a.person_id))


def with_event(state: GameState, event: GameEvent) -> GameState:
    return replace(state, events=_upsert(state.events, event, lambda e: e.id))


def with_storyline(state: GameState, story: Storyline) -> GameState:
    return replace(state, storylines=_upsert(state.storylines, story, lambda s: s.id))


def with_queued(state: GameState, queued: QueuedEvent) -> GameState:
    return replace(state, queued=_upsert(state.queued, queued, lambda q: q.id))


def with_relationship(state: GameState, rel: Relationship) -> GameState:
    return replace(state, relationships=_upsert(state.relationships, rel, lambda r: r.key))


def with_segment_share(state: GameState, share: SegmentShare) -> GameState:
    return replace(
        state,
        segment_shares=_upsert(state.segment_shares, share, lambda s: (s.product_id, s.segment)),
    )


def with_loan(state: GameState, loan: Loan) -> GameState:
    return replace(state, loans=_upsert(state.loans, loan, lambda x: x.id))


def with_seat(state: GameState, seat: BoardSeat) -> GameState:
    return replace(state, seats=_upsert(state.seats, seat, lambda s: s.id))


def with_person_state(state: GameState, person_state: PersonState) -> GameState:
    return replace(
        state, person_states=_upsert(state.person_states, person_state, lambda p: p.person_id)
    )


def with_exec_seat(state: GameState, seat: ExecSeat) -> GameState:
    return replace(
        state, exec_seats=_upsert(state.exec_seats, seat, lambda s: (s.company_id, s.seat))
    )


def with_office(state: GameState, office: Office) -> GameState:
    return replace(state, offices=_upsert(state.offices, office, lambda o: o.id))


def with_regional_market(state: GameState, market: RegionalMarket) -> GameState:
    return replace(
        state,
        regional_markets=_upsert(
            state.regional_markets, market, lambda m: (m.category, m.segment, m.region)
        ),
    )


def with_product_region(state: GameState, region: ProductRegion) -> GameState:
    return replace(
        state,
        product_regions=_upsert(state.product_regions, region, lambda r: (r.product_id, r.region)),
    )


def with_regional_segment(state: GameState, seg: RegionalSegment) -> GameState:
    return replace(
        state,
        regional_segments=_upsert(
            state.regional_segments, seg, lambda s: (s.product_id, s.region, s.segment)
        ),
    )
