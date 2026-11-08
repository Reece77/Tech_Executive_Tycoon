"""Immutable game state. Cash is never a field: it is derived from ledger balances (ADR-0003)."""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from operator import attrgetter
from types import MappingProxyType
from typing import Any, Final

from tst.sim.events.models import GameEvent, Modifier, QueuedEvent, Storyline
from tst.sim.facilities.models import Facility, GoodMonth, Outage, SupplyContract
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
from tst.sim.founder.models import Foundation, FounderLife, Influence, PersonalEntry
from tst.sim.geo.models import (
    MarketingSplit,
    Office,
    ProductRegion,
    RegionalMarket,
    RegionalSegment,
)
from tst.sim.hardware.models import ProductionContract, ProductionMonth
from tst.sim.hiring.models import Candidate, NextIds, Offer, PersonState, Search
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.markets_public.models import (
    Ceo,
    CeoDecision,
    Guidance,
    Listing,
    PublicCompany,
    ShareMonth,
)
from tst.sim.mna.models import AcquiredPerson, Acquisition, Deal, RivalListing, TargetFile
from tst.sim.modes.models import CompanyScore, GameMode, QuarterMark, Ranking, Venture
from tst.sim.money import Cents
from tst.sim.org.models import (
    Authority,
    ExecDecision,
    ExecSeat,
    HiringPlan,
    OrgUnit,
    Pitch,
    PitchPolicy,
    Proposal,
    WorkPolicy,
)
from tst.sim.people.models import Employment, Person, RevealState
from tst.sim.people.relationships import Relationship
from tst.sim.press.models import (
    Credibility,
    Departure,
    Feud,
    PressMoment,
    Promise,
    Statement,
)
from tst.sim.products.models import MarketSegment, Product, ProductSegment
from tst.sim.research.models import (
    EraArrival,
    EraWindow,
    License,
    ResearchLead,
    ResearchProject,
)
from tst.sim.rivals.models import (
    FreeAgent,
    PoachApproach,
    RivalEffect,
    RivalMove,
    SegmentShare,
    WorkforcePool,
)

_ID = attrgetter("id")  # sort key of id-sorted collections (C speed for bisect)


# relationship_map's memo: the tuple is kept with its map, so an id is never reused while cached
_REL_MAPS: dict[int, tuple[tuple[Relationship, ...], Mapping[tuple[int, int], Relationship]]] = {}
_REL_MAPS_KEPT: Final = 4  # tunable-exempt: memo size (the turn's old and new tuples)


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
    # A rival's stable identity for its RNG keys (ADR-0013 amendment, M12a): (0, index) for
    # an incumbent and (1, index) for a scheduled entrant, by position in incumbents.yaml or
    # entrants.yaml; (2, category_index, n) for the nth startup founded in a category.
    # Empty for the player and for rivals of saves made before M12a (keyed by company id).
    rival_key: tuple[int, ...] = ()
    # M14 (28.5, ADR-0020): the company that owns this one as a kept brand; None otherwise
    parent_id: int | None = None
    # M15a (formulas.md 30.7 V5): a rival startup's first month of its current run below
    # rivals.startup.small_staff people; None while it has that many
    small_since_turn: int | None = None

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
    modifiers: tuple[Modifier, ...] = ()  # event modifiers still running, by id (M10b, 23.2)
    exec_seats: tuple[ExecSeat, ...] = ()  # seats ever filled, by (company_id, seat) (M8, 18.3)
    # M10c (24): authority by (company_id, seat); decisions of the last months and proposals
    authorities: tuple[Authority, ...] = ()
    exec_decisions: tuple[ExecDecision, ...] = ()
    proposals: tuple[Proposal, ...] = ()
    pitches: tuple[Pitch, ...] = ()  # M13b (27.1): pending and recent pitches, by id
    pitch_policies: tuple[PitchPolicy, ...] = ()  # M13b: by company_id
    macro: MacroMonth | None = None  # the indicators phase 1 last set (M10, 20.1)
    loans: tuple[Loan, ...] = ()  # every loan, sorted by id (M10, 20.3)
    # M9 (19.2, 19.5): open offices by id; other regions' markets by (category, segment,
    # region); products' launches there by (product_id, region); their segments there by
    # (product_id, region, segment). The home region stays in markets and product_segments.
    offices: tuple[Office, ...] = ()
    regional_markets: tuple[RegionalMarket, ...] = ()
    product_regions: tuple[ProductRegion, ...] = ()
    # M10b (23.5): marketing budget split by region, by (product_id, region)
    marketing_splits: tuple[MarketingSplit, ...] = ()
    regional_segments: tuple[RegionalSegment, ...] = ()
    # M12a (22): facilities that are not closed, by id; each market good's latest month, in
    # components_history.yaml order (empty before phase 4 first runs); component contracts
    # active or settled in the last 24 months, by id; outages of the last 24 months, by id.
    facilities: tuple[Facility, ...] = ()
    supply: tuple[GoodMonth, ...] = ()
    contracts: tuple[SupplyContract, ...] = ()
    outages: tuple[Outage, ...] = ()
    # M11 (21): leads by (company_id, domain); projects (active, and stopped ones of the last
    # months) and licences by id; arrived eras by key.
    research_leads: tuple[ResearchLead, ...] = ()
    research_projects: tuple[ResearchProject, ...] = ()
    era_arrivals: tuple[EraArrival, ...] = ()
    era_windows: tuple[EraWindow, ...] = ()  # M13b (27.3): player first movers' windows
    licenses: tuple[License, ...] = ()
    # M12b (26.2, 26.3): contract-manufacturing and wafer contracts (active, and ended ones of
    # the last 24 months) by id; the last phase 5's production by product id.
    production_contracts: tuple[ProductionContract, ...] = ()
    production: tuple[ProductionMonth, ...] = ()
    # M13 (25): each company's IPO chain and its listed state, by company id; guidance by
    # (company_id, quarter_turn); month-end share prices of the last public.history_months, by
    # (company_id, turn); CEOs serving or ended lately, and their recent decisions, by id.
    listings: tuple[Listing, ...] = ()
    public_companies: tuple[PublicCompany, ...] = ()
    guidance: tuple[Guidance, ...] = ()
    share_months: tuple[ShareMonth, ...] = ()
    ceos: tuple[Ceo, ...] = ()
    ceo_decisions: tuple[CeoDecision, ...] = ()
    # M14 (28): listed rivals' sentiment by company id; what each acquirer knows of each
    # target by (acquirer_id, target_id); deals by id; closed acquisitions by deal id; acquired
    # key people during culture clash by person id.
    rival_listings: tuple[RivalListing, ...] = ()
    target_files: tuple[TargetFile, ...] = ()
    deals: tuple[Deal, ...] = ()
    acquisitions: tuple[Acquisition, ...] = ()
    acquired_people: tuple[AcquiredPerson, ...] = ()
    # M14b (29): press moments (pending, queued, or answered in the last 12 months) and every
    # promise, by id; credibility by company id; the player's feuds by (company_id, rival_id);
    # rival CEOs' statements of the last 24 months, by id.
    press_moments: tuple[PressMoment, ...] = ()
    promises: tuple[Promise, ...] = ()
    credibility: tuple[Credibility, ...] = ()
    feuds: tuple[Feud, ...] = ()
    statements: tuple[Statement, ...] = ()
    departures: tuple[Departure, ...] = ()  # resignations and poaches lately, by person id
    # M15b (30.1): company scores each December and at a game's end, oldest first
    scores: tuple[CompanyScore, ...] = ()
    mode: GameMode | None = None  # M15b (30.2-30.3): Sandbox or a scenario; None: a campaign
    rankings: tuple[Ranking, ...] = ()  # M15b (30.4): every January's lists, oldest first
    quarter_marks: tuple[QuarterMark, ...] = ()  # M15b: products at the last reports, by id
    ventures: tuple[Venture, ...] = ()  # M15b addendum 10: the player's sold companies
    # M24 (32): founders' lives by person id; every personal-book entry, oldest first (never
    # in a company's books); foundations by person id; influence by (company_id, region).
    founder_lives: tuple[FounderLife, ...] = ()
    personal_book: tuple[PersonalEntry, ...] = ()
    foundations: tuple[Foundation, ...] = ()
    influence: tuple[Influence, ...] = ()
    next_ids: NextIds = field(default_factory=NextIds)

    def company(self, company_id: int) -> CompanyState:
        for company in self.companies:
            if company.id == company_id:
                return company
        raise KeyError(company_id)

    def person(self, person_id: int) -> Person:
        """By binary search: `people` is kept sorted by id (`with_person`); the scan after a
        miss only matters for a hand-built, unsorted tuple."""
        people = self.people
        i = bisect_left(people, person_id, key=_ID)
        if i < len(people) and people[i].id == person_id:
            return people[i]
        for person in people:
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

    def authority(self, company_id: int, seat: str) -> Authority | None:
        """A seat's authority record (M10c, 24.1); None if never given."""
        return next(
            (a for a in self.authorities if a.company_id == company_id and a.seat == seat), None
        )

    def pending_pitches(self, company_id: int) -> tuple[Pitch, ...]:
        """Pitches waiting for the founder's answer (27.1, M13b)."""
        return tuple(
            p for p in self.pitches if p.company_id == company_id and p.status == "pending"
        )

    def pitch(self, pitch_id: int) -> Pitch | None:
        return next((p for p in self.pitches if p.id == pitch_id), None)

    def pitch_policy(self, company_id: int) -> PitchPolicy:
        return next(
            (p for p in self.pitch_policies if p.company_id == company_id),
            PitchPolicy(company_id),
        )

    def pending_proposals(self, company_id: int) -> tuple[Proposal, ...]:
        return tuple(
            p for p in self.proposals if p.company_id == company_id and p.status == "pending"
        )

    def open_events(self, company_id: int) -> tuple[GameEvent, ...]:
        """Events shown this month or earlier that are not answered yet."""
        return tuple(
            e
            for e in self.events
            if e.company_id == company_id and e.is_open and e.turn <= self.turn
        )

    def storyline(self, storyline_id: int) -> Storyline | None:
        return next((s for s in self.storylines if s.id == storyline_id), None)

    def relationship_map(self) -> Mapping[tuple[int, int], Relationship]:
        """The pairs by key, built once per relationships tuple (read-only; M14 turn time:
        morale, events and the phase all ask, and a 200-person unit has 18,000 pairs)."""
        rels = self.relationships
        hit = _REL_MAPS.get(id(rels))
        if hit is not None and hit[0] is rels:
            return hit[1]
        built = MappingProxyType({r.key: r for r in rels})
        if len(_REL_MAPS) >= _REL_MAPS_KEPT:
            _REL_MAPS.pop(next(iter(_REL_MAPS)))
        _REL_MAPS[id(rels)] = (rels, built)
        return built

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

    # --- Facilities (M12a) ------------------------------------------------------------------

    def facility(self, facility_id: int) -> Facility | None:
        return next((f for f in self.facilities if f.id == facility_id), None)

    def company_facilities(self, company_id: int) -> tuple[Facility, ...]:
        return tuple(
            f for f in self.facilities if f.company_id == company_id and f.status != "closed"
        )

    def contract(self, contract_id: int) -> SupplyContract | None:
        return next((c for c in self.contracts if c.id == contract_id), None)

    def company_contracts(self, company_id: int) -> tuple[SupplyContract, ...]:
        return tuple(c for c in self.contracts if c.company_id == company_id)

    def production_contract(self, contract_id: int) -> ProductionContract | None:
        return next((c for c in self.production_contracts if c.id == contract_id), None)

    def product_contracts(self, product_id: int) -> tuple[ProductionContract, ...]:
        return tuple(c for c in self.production_contracts if c.product_id == product_id)

    def production_of(self, product_id: int) -> ProductionMonth | None:
        return next((p for p in self.production if p.product_id == product_id), None)

    def good_month(self, good: str) -> GoodMonth | None:
        return next((g for g in self.supply if g.good == good), None)

    # --- Research (M11) ---------------------------------------------------------------------

    def research_lead(self, company_id: int, domain: str) -> float:
        for r in self.research_leads:
            if r.company_id == company_id and r.domain == domain:
                return r.lead
        return 0.0

    def research_project(self, project_id: int) -> ResearchProject | None:
        return next((p for p in self.research_projects if p.id == project_id), None)

    def active_projects(self, company_id: int | None = None) -> tuple[ResearchProject, ...]:
        return tuple(
            p
            for p in self.research_projects
            if p.is_active and (company_id is None or p.company_id == company_id)
        )

    def unit_project(self, unit_id: int) -> ResearchProject | None:
        """The active project an org unit works on, if any (a unit does one thing, 11.3)."""
        return next(
            (p for p in self.research_projects if p.is_active and p.unit_id == unit_id), None
        )

    def era_arrival(self, key: str) -> EraArrival | None:
        return next((a for a in self.era_arrivals if a.key == key), None)

    @property
    def player(self) -> CompanyState:
        for company in self.companies:
            if company.is_player:
                return company
        raise LookupError("game state has no player company")


def group_companies(state: GameState, parent_id: int) -> tuple[CompanyState, ...]:
    """A parent and the kept brands it owns (M14, 28.5; ADR-0020): consolidation iterates
    these. M16 extends this to deeper groups."""
    parent = state.company(parent_id)
    return (parent, *(c for c in state.companies if c.parent_id == parent_id and c.alive))


def player_companies(state: GameState) -> tuple[CompanyState, ...]:
    """The companies the player controls (ADR-0020): the player's single company until M16,
    when it returns the group. New code uses this wherever "the player" is meant."""
    return (state.player,)


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


def with_marketing_split(
    state: GameState, product_id: int, shares: tuple[MarketingSplit, ...]
) -> GameState:
    """Replace a product's marketing split by region (23.5); () returns it to the default."""
    rest = tuple(m for m in state.marketing_splits if m.product_id != product_id)
    return replace(
        state,
        marketing_splits=tuple(sorted((*rest, *shares), key=lambda m: (m.product_id, m.region))),
    )


def with_authority(state: GameState, authority: Authority) -> GameState:
    return replace(
        state,
        authorities=_upsert(state.authorities, authority, lambda a: (a.company_id, a.seat)),
    )


def with_exec_decision(state: GameState, decision: ExecDecision) -> GameState:
    return replace(state, exec_decisions=_upsert(state.exec_decisions, decision, lambda d: d.id))


def with_pitch(state: GameState, pitch: Pitch) -> GameState:
    return replace(state, pitches=_upsert(state.pitches, pitch, lambda p: p.id))


def with_pitch_policy(state: GameState, policy: PitchPolicy) -> GameState:
    return replace(
        state, pitch_policies=_upsert(state.pitch_policies, policy, lambda p: p.company_id)
    )


def with_proposal(state: GameState, proposal: Proposal) -> GameState:
    return replace(state, proposals=_upsert(state.proposals, proposal, lambda p: p.id))


def with_modifier(state: GameState, modifier: Modifier) -> GameState:
    return replace(state, modifiers=_upsert(state.modifiers, modifier, lambda m: m.id))


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


def with_person_states(state: GameState, person_states: list[PersonState]) -> GameState:
    """`with_person_state` for many at once: one rebuild (M14 turn time)."""
    if not person_states:
        return state
    return replace(
        state,
        person_states=_upsert_many(state.person_states, person_states, lambda p: p.person_id),
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


def _upsert_many[T](items: tuple[T, ...], new: list[T], key: Callable[[T], Any]) -> tuple[T, ...]:
    """`items` (sorted by key, keys unique) with every item of `new` upserted: one rebuild."""
    if not new:
        return items
    out = list(items)
    for item in new:
        k = key(item)
        i = bisect_left(out, k, key=key)
        if i < len(out) and key(out[i]) == k:
            out[i] = item
        else:
            out.insert(i, item)
    return tuple(out)


def with_segments(
    state: GameState,
    home: list[ProductSegment],
    regional: list[RegionalSegment],
) -> GameState:
    """Many product segments (home and other regions) in one state update (M12b: the market
    phase writes a whole market segment at once)."""
    if not home and not regional:
        return state
    return replace(
        state,
        product_segments=_upsert_many(
            state.product_segments, home, lambda s: (s.product_id, s.segment)
        ),
        regional_segments=_upsert_many(
            state.regional_segments, regional, lambda s: (s.product_id, s.region, s.segment)
        ),
    )


def with_regional_segment(state: GameState, seg: RegionalSegment) -> GameState:
    return replace(
        state,
        regional_segments=_upsert(
            state.regional_segments, seg, lambda s: (s.product_id, s.region, s.segment)
        ),
    )


def with_facility(state: GameState, facility: Facility) -> GameState:
    return replace(state, facilities=_upsert(state.facilities, facility, lambda f: f.id))


def with_contract(state: GameState, contract: SupplyContract) -> GameState:
    return replace(state, contracts=_upsert(state.contracts, contract, lambda c: c.id))


def with_production_contract(state: GameState, contract: ProductionContract) -> GameState:
    return replace(
        state,
        production_contracts=_upsert(state.production_contracts, contract, lambda c: c.id),
    )


def with_outage(state: GameState, outage: Outage) -> GameState:
    return replace(state, outages=_upsert(state.outages, outage, lambda o: o.id))


def with_research_lead(state: GameState, lead: ResearchLead) -> GameState:
    return replace(
        state,
        research_leads=_upsert(state.research_leads, lead, lambda r: (r.company_id, r.domain)),
    )


def with_research_project(state: GameState, project: ResearchProject) -> GameState:
    return replace(
        state, research_projects=_upsert(state.research_projects, project, lambda p: p.id)
    )


def with_era_window(state: GameState, window: EraWindow) -> GameState:
    return replace(
        state,
        era_windows=_upsert(state.era_windows, window, lambda w: (w.era_key, w.company_id)),
    )


def with_era_arrival(state: GameState, arrival: EraArrival) -> GameState:
    return replace(state, era_arrivals=_upsert(state.era_arrivals, arrival, lambda a: a.key))


def with_license(state: GameState, licence: License) -> GameState:
    return replace(state, licenses=_upsert(state.licenses, licence, lambda x: x.id))


# --- M13 (formulas.md 25) ----------------------------------------------------------------------


def listing_of(state: GameState, company_id: int) -> Listing | None:
    return next((x for x in state.listings if x.company_id == company_id), None)


def public_of(state: GameState, company_id: int) -> PublicCompany | None:
    return next((x for x in state.public_companies if x.company_id == company_id), None)


def ceo_of(state: GameState, company_id: int) -> Ceo | None:
    """The company's serving CEO, if one was appointed (25.6)."""
    return next((c for c in state.ceos if c.company_id == company_id and c.active), None)


def guidance_for(state: GameState, company_id: int, quarter_turn: int) -> Guidance | None:
    return next(
        (
            g
            for g in state.guidance
            if g.company_id == company_id and g.quarter_turn == quarter_turn
        ),
        None,
    )


def with_listing(state: GameState, listing: Listing) -> GameState:
    return replace(state, listings=_upsert(state.listings, listing, lambda x: x.company_id))


def with_public(state: GameState, public: PublicCompany) -> GameState:
    return replace(
        state, public_companies=_upsert(state.public_companies, public, lambda x: x.company_id)
    )


def with_guidance(state: GameState, guidance: Guidance) -> GameState:
    return replace(
        state,
        guidance=_upsert(state.guidance, guidance, lambda g: (g.company_id, g.quarter_turn)),
    )


def with_share_month(state: GameState, month: ShareMonth) -> GameState:
    return replace(
        state, share_months=_upsert(state.share_months, month, lambda m: (m.company_id, m.turn))
    )


def with_ceo(state: GameState, ceo: Ceo) -> GameState:
    return replace(state, ceos=_upsert(state.ceos, ceo, lambda c: c.id))


def with_ceo_decision(state: GameState, decision: CeoDecision) -> GameState:
    return replace(state, ceo_decisions=_upsert(state.ceo_decisions, decision, lambda d: d.id))


# --- M14 (28): mergers and acquisitions ----------------------------------------------------


def with_rival_listing(state: GameState, listing: RivalListing) -> GameState:
    return replace(
        state, rival_listings=_upsert(state.rival_listings, listing, lambda x: x.company_id)
    )


def with_target_file(state: GameState, file: TargetFile) -> GameState:
    return replace(
        state,
        target_files=_upsert(state.target_files, file, lambda f: (f.acquirer_id, f.target_id)),
    )


def with_deal(state: GameState, deal: Deal) -> GameState:
    return replace(state, deals=_upsert(state.deals, deal, lambda d: d.id))


def with_acquisition(state: GameState, acquisition: Acquisition) -> GameState:
    return replace(
        state, acquisitions=_upsert(state.acquisitions, acquisition, lambda a: a.deal_id)
    )


def with_acquired_person(state: GameState, person: AcquiredPerson) -> GameState:
    return replace(
        state, acquired_people=_upsert(state.acquired_people, person, lambda p: p.person_id)
    )


def without_acquired_person(state: GameState, person_id: int) -> GameState:
    return replace(
        state, acquired_people=tuple(p for p in state.acquired_people if p.person_id != person_id)
    )


def target_file(state: GameState, acquirer_id: int, target_id: int) -> TargetFile | None:
    return next(
        (f for f in state.target_files if (f.acquirer_id, f.target_id) == (acquirer_id, target_id)),
        None,
    )


def rival_listing(state: GameState, company_id: int) -> RivalListing | None:
    return next((x for x in state.rival_listings if x.company_id == company_id), None)


# --- M14b (formulas.md 29) ---------------------------------------------------------------------


def credibility_of(state: GameState, company_id: int) -> Credibility | None:
    return next((c for c in state.credibility if c.company_id == company_id), None)


def feud_of(state: GameState, company_id: int, rival_id: int) -> Feud | None:
    return next(
        (f for f in state.feuds if f.company_id == company_id and f.rival_id == rival_id), None
    )


def with_press_moment(state: GameState, moment: PressMoment) -> GameState:
    return replace(state, press_moments=_upsert(state.press_moments, moment, lambda m: m.id))


def with_promise(state: GameState, promise: Promise) -> GameState:
    return replace(state, promises=_upsert(state.promises, promise, lambda p: p.id))


def life_of(state: GameState, person_id: int) -> FounderLife | None:
    """A founder's life record (M24, 32.1); None before their first month."""
    i = bisect_left(state.founder_lives, person_id, key=attrgetter("person_id"))
    lives = state.founder_lives
    return lives[i] if i < len(lives) and lives[i].person_id == person_id else None


def with_life(state: GameState, life: FounderLife) -> GameState:
    return replace(state, founder_lives=_upsert(state.founder_lives, life, attrgetter("person_id")))


def foundation_of(state: GameState, person_id: int) -> Foundation | None:
    return next((f for f in state.foundations if f.person_id == person_id), None)


def with_foundation(state: GameState, foundation: Foundation) -> GameState:
    return replace(
        state, foundations=_upsert(state.foundations, foundation, attrgetter("person_id"))
    )


def influence_of(state: GameState, company_id: int, region: str) -> Influence | None:
    return next(
        (i for i in state.influence if i.company_id == company_id and i.region == region), None
    )


def with_influence(state: GameState, record: Influence) -> GameState:
    return replace(
        state, influence=_upsert(state.influence, record, lambda i: (i.company_id, i.region))
    )


def with_personal_entries(state: GameState, *entries: PersonalEntry) -> GameState:
    return replace(state, personal_book=(*state.personal_book, *entries)) if entries else state


def with_credibility(state: GameState, cred: Credibility) -> GameState:
    return replace(state, credibility=_upsert(state.credibility, cred, lambda c: c.company_id))


def with_feud(state: GameState, feud: Feud) -> GameState:
    return replace(state, feuds=_upsert(state.feuds, feud, lambda f: (f.company_id, f.rival_id)))


def with_statement(state: GameState, statement: Statement) -> GameState:
    return replace(state, statements=_upsert(state.statements, statement, lambda s: s.id))
