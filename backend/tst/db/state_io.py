"""Load live GameState from a save and write back only what changed.

Live state only (M1b sweep rule 1): staff (active and notice employments), open candidates,
open searches, pending offers, active org units, hiring plans that are not closed, products
that are not retired with their segments, every market segment (M3), and the
people and knowledge records they need (including whoever made a pending offer and every
plan's owner, who may have left). Records that leave the live set keep their rows, with a
status, in the database.

`sync_state(old, new)` compares the state that was loaded with the state the sim returned
and writes inserts and in-place updates for the differences, so a turn costs time in
proportion to what happened, not to the size of the save.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, replace
from functools import cache
from typing import Any, cast

from sqlalchemy import Table, Update, and_, bindparam, delete, func, insert, inspect, select
from sqlalchemy.orm import Session

from tst.db.commodity_io import load_commodities, sync_commodities
from tst.db.exploration_io import load_exploration, sync_exploration
from tst.db.former import former_rows
from tst.db.founder_io import load_founder, sync_founder
from tst.db.group_io import load_group, sync_group
from tst.db.mappers import (
    candidate_from_row,
    candidate_to_row,
    company_to_row,
    employment_from_row,
    employment_to_row,
    event_from_row,
    event_to_row,
    finance_from_row,
    finance_to_row,
    game_state_from_rows,
    market_from_row,
    market_to_row,
    modifier_from_row,
    modifier_to_row,
    next_ids_from_meta,
    next_ids_to_meta,
    offer_from_row,
    offer_to_row,
    person_from_rows,
    person_state_from_row,
    person_state_to_row,
    person_to_rows,
    plan_from_row,
    plan_to_row,
    product_from_row,
    product_segment_from_row,
    product_segment_to_row,
    product_to_row,
    queued_from_row,
    queued_to_row,
    reveal_to_rows,
    rival_from_row,
    rival_to_row,
    round_nominee_row,
    search_from_row,
    search_to_row,
    seat_history_row,
    storyline_from_row,
    storyline_to_row,
    unit_from_row,
    unit_to_row,
)
from tst.db.mna_io import load_mna, sync_mna
from tst.db.models import (
    AuthorityRow,
    BoardSeatHistoryRow,
    BoardSeatRow,
    CandidateRelocationRow,
    CandidateRow,
    CapTableEntryRow,
    CeoDecisionRow,
    CeoRow,
    CompanyHqRow,
    CompanyRivalKeyRow,
    CompanyRow,
    CredibilityRow,
    DepartureRow,
    EmploymentRow,
    EraArrivalRow,
    EraWindowRow,
    EventModifierRow,
    EventQueueRow,
    EventRow,
    ExecDecisionRow,
    ExecSeatRow,
    FacilityOutageRow,
    FacilityRow,
    FeudRow,
    FinanceHistoryRow,
    FormerStaffRow,
    FreeAgentRow,
    FundingRoundRow,
    GuidanceRow,
    HiringPlanDetailRow,
    HiringPlanRow,
    LedgerEntryRow,
    LedgerLineRow,
    LicenseRow,
    ListingRow,
    LoanRow,
    MacroMonthRow,
    MarketingSplitRow,
    MarketSegmentRow,
    OfferRow,
    OfficeRow,
    OptionGrantRow,
    OrgUnitRow,
    PersonCityRow,
    PersonHiddenRow,
    PersonInterestRow,
    PersonPersonalityRow,
    PersonProfileRevealRow,
    PersonRevealRow,
    PersonRow,
    PersonSkillRow,
    PersonStateRow,
    PersonTagRevealRow,
    PersonTagRow,
    PitchPolicyRow,
    PitchRow,
    PoachApproachRow,
    PressMomentRow,
    ProductDivisionRow,
    ProductionContractRow,
    ProductionMonthRow,
    ProductRegionRow,
    ProductRow,
    ProductSegmentRow,
    PromiseRow,
    ProposalRow,
    PublicCompanyRow,
    RegionalMarketRow,
    RegionalSegmentRow,
    RelationshipRow,
    ResearchLeadRow,
    ResearchProjectRow,
    RivalEffectRow,
    RivalMoveRow,
    RoundNomineeRow,
    SafeRow,
    SaveMetaRow,
    SearchCityRow,
    SearchInterestRow,
    SearchLevelRow,
    SearchRow,
    SegmentShareRow,
    ShareMonthRow,
    StartupSmallRow,
    StatementRow,
    StorylineRow,
    SupplyContractRow,
    SupplyMonthRow,
    TermSheetRow,
    UnitOfficeRow,
    UnitServicesRow,
    WorkforcePoolRow,
)
from tst.db.modes_io import load_modes, sync_modes
from tst.sim.errors import SaveNotFoundError
from tst.sim.facilities.models import Facility, GoodMonth, Outage, SupplyContract
from tst.sim.finance.macro import MacroMonth
from tst.sim.finance.models import (
    BoardSeat,
    CapEntry,
    FundingRound,
    Loan,
    OptionGrant,
    Safe,
    TermSheet,
)
from tst.sim.geo.models import (
    MarketingSplit,
    Office,
    ProductRegion,
    RegionalMarket,
    RegionalSegment,
)
from tst.sim.hardware.models import ProductionContract, ProductionMonth
from tst.sim.hiring.models import NextIds
from tst.sim.ledger import LedgerEntry
from tst.sim.markets_public.models import (
    Analyst,
    Ceo,
    CeoDecision,
    Guidance,
    Listing,
    PublicCompany,
    ShareMonth,
)
from tst.sim.org.models import Authority, ExecDecision, ExecSeat, Pitch, PitchPolicy, Proposal
from tst.sim.people.models import Person, RevealRecord, RevealState
from tst.sim.people.relationships import Relationship
from tst.sim.press.models import (
    Credibility,
    Departure,
    Feud,
    PressMoment,
    Promise,
    Statement,
)
from tst.sim.press.moments import MEMORY as PRESS_MEMORY
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
from tst.sim.state import GameState

META_ID = 1
RIVAL_MOVE_MEMORY = 24  # months of rival moves loaded: news, cooldowns, stance (M5)
EVENT_MEMORY = 24  # months of events loaded: the director's longest cooldown (M6, 16.1)
STAFF_STATUSES = ("active", "notice")


def read_meta(session: Session) -> SaveMetaRow:
    meta = session.get(SaveMetaRow, META_ID)
    if meta is None:
        raise SaveNotFoundError("save file has no save_meta row")
    return meta


def _by_person[R](rows: Iterable[R]) -> dict[int, list[R]]:
    grouped: dict[int, list[R]] = defaultdict(list)
    for row in rows:
        grouped[row.person_id].append(row)  # type: ignore[attr-defined]
    return grouped


def _ordered_pairs(session: Session, model: Any, key: Any, value: Any, where: Any) -> Any:
    """A person child table as person id -> [(key, value)] in position order: one SQL ORDER
    BY instead of Row objects and a sort per person (M12b, speed)."""
    out: dict[int, list[Any]] = defaultdict(list)
    for pid, k, v in session.execute(
        select(model.person_id, key, value).where(where).order_by(model.person_id, model.position)
    ):
        out[pid].append((k, v))
    return out


def _ordered_keys(session: Session, model: Any, key: Any, where: Any) -> Any:
    """A person child table as person id -> [key] in position order (interests, tags)."""
    out: dict[int, list[Any]] = defaultdict(list)
    for pid, k in session.execute(
        select(model.person_id, key).where(where).order_by(model.person_id, model.position)
    ):
        out[pid].append(k)
    return out


def load_people(
    session: Session, ids: Iterable[int]
) -> tuple[tuple[Person, ...], tuple[RevealState, ...]]:
    """People and every company's knowledge of them, for the given person ids (load_state's
    live set; M7c's backfill of former staff)."""
    live_ids = sorted(set(ids))

    def in_live(column: Any) -> Any:
        return column.in_(live_ids)

    sk, pe, hi = PersonSkillRow, PersonPersonalityRow, PersonHiddenRow
    skills = _ordered_pairs(session, sk, sk.skill, sk.value, in_live(sk.person_id))
    personality = _ordered_pairs(session, pe, pe.trait, pe.value, in_live(pe.person_id))
    hidden = _ordered_pairs(session, hi, hi.trait, hi.value, in_live(hi.person_id))
    interests = _ordered_keys(
        session, PersonInterestRow, PersonInterestRow.interest, in_live(PersonInterestRow.person_id)
    )
    tags = _ordered_keys(session, PersonTagRow, PersonTagRow.tag, in_live(PersonTagRow.person_id))
    people = tuple(
        person_from_rows(
            row,
            skills[row.id],
            personality[row.id],
            hidden[row.id],
            interests[row.id],
            tags[row.id],
        )
        for row in _plain(  # plain rows (M12b, speed)
            session, select(PersonRow.__table__).where(in_live(PersonRow.id)).order_by(PersonRow.id)
        )
    )
    if has_table(session, PersonCityRow):  # M9 (19.1)
        cities = {
            r.person_id: r.city
            for r in _rows(session, PersonCityRow, in_live(PersonCityRow.person_id))
        }
        people = tuple(replace(p, city=cities.get(p.id)) for p in people)

    def key(row: Any) -> tuple[int, int]:
        return (row.observer_company_id, row.person_id)

    # Knowledge records as ordered tuples, built straight into RevealRecords: the largest
    # child table (about 35 rows a person a company), so no Row objects or per-person sorts
    # (M12b, speed; the same RevealStates as `reveal_from_rows`).
    r_ = PersonRevealRow
    attributes: dict[tuple[int, int], list[tuple[str, RevealRecord]]] = defaultdict(list)
    for o, pid, attribute, hw, offset, updated in session.execute(
        select(
            r_.observer_company_id,
            r_.person_id,
            r_.attribute,
            r_.hw,
            r_.center_offset,
            r_.last_updated_turn,
        )
        .where(in_live(r_.person_id))
        .order_by(r_.observer_company_id, r_.person_id, r_.position)
    ):
        attributes[(o, pid)].append((attribute, RevealRecord(hw, offset, updated)))
    profiles = {
        key(r): r
        for r in session.scalars(
            select(PersonProfileRevealRow).where(in_live(PersonProfileRevealRow.person_id))
        )
    }
    tag_reveals: dict[tuple[int, int], list[PersonTagRevealRow]] = defaultdict(list)
    for t in session.scalars(
        select(PersonTagRevealRow).where(in_live(PersonTagRevealRow.person_id))
    ):
        tag_reveals[key(t)].append(t)
    reveals = tuple(
        RevealState(
            observer_company_id=o,
            person_id=p,
            attributes=tuple(attributes[(o, p)]),
            profile_revealed_turn=None
            if (pr := profiles.get((o, p))) is None
            else pr.revealed_turn,
            revealed_tags=tuple(
                (t.tag, t.revealed_turn)
                for t in sorted(tag_reveals[(o, p)], key=lambda t: (t.revealed_turn, t.tag))
            ),
        )
        for o, p in sorted(attributes)
    )
    return people, reveals


def load_state(session: Session) -> GameState:
    meta = read_meta(session)
    companies = list(session.scalars(select(CompanyRow)))

    employments = [
        employment_from_row(r)
        for r in _plain(  # plain rows: no ORM object per row (M12b, speed)
            session,
            select(EmploymentRow.__table__)
            .where(EmploymentRow.status.in_(STAFF_STATUSES))
            .order_by(EmploymentRow.id),
        )
    ]
    candidates = [
        candidate_from_row(r)
        for r in session.scalars(
            select(CandidateRow)
            .where(CandidateRow.status == "open")
            .order_by(CandidateRow.person_id)
        )
    ]
    offers = [
        offer_from_row(r)
        for r in session.scalars(
            select(OfferRow).where(OfferRow.status == "pending").order_by(OfferRow.id)
        )
    ]
    plans = [
        plan_from_row(r)
        for r in session.scalars(
            select(HiringPlanRow).where(HiringPlanRow.status != "closed").order_by(HiringPlanRow.id)
        )
    ]
    nominees = {r.round_id: r.person_id for r in session.scalars(select(RoundNomineeRow))}
    histories = {
        r.seat_id: tuple(float(v) for v in r.history)
        for r in session.scalars(select(BoardSeatHistoryRow))
    }
    seats = tuple(
        finance_from_row(BoardSeat, r, history=histories.get(r.id, ()))
        for r in session.scalars(select(BoardSeatRow).order_by(BoardSeatRow.id))
    )
    free_agents = (
        tuple(
            rival_from_row(FreeAgent, r)
            for r in session.scalars(
                select(FreeAgentRow)
                .where(FreeAgentRow.status == "available")
                .order_by(FreeAgentRow.person_id)
            )
        )
        if has_table(session, FreeAgentRow)
        else ()
    )
    live_ids = sorted(
        {e.person_id for e in employments}
        | {c.person_id for c in candidates}
        | {o.actor_id for o in offers}
        | {p.owner_id for p in plans}
        | {s.person_id for s in seats if s.person_id is not None}
        | {a.person_id for a in free_agents}
    )

    people, reveals = load_people(session, live_ids)

    def in_live(column: Any) -> Any:
        return column.in_(live_ids)

    state = game_state_from_rows(meta, companies, people, tuple(employments), reveals)
    products = tuple(
        product_from_row(r)
        for r in session.scalars(
            select(ProductRow).where(ProductRow.status != "retired").order_by(ProductRow.id)
        )
    )
    m8 = has_table(session, ExecSeatRow)  # M8 side tables (0020_divisions)
    if m8:
        divisions = {
            r.product_id: r.division_id for r in session.scalars(select(ProductDivisionRow))
        }
        services = {r.unit_id: r.services for r in session.scalars(select(UnitServicesRow))}
        levels = {r.search_id: r.level for r in session.scalars(select(SearchLevelRow))}
        products = tuple(replace(p, division_id=divisions.get(p.id)) for p in products)
    else:
        services, levels = {}, {}
    product_ids = [p.id for p in products]
    state = replace(
        state,
        searches=tuple(
            replace(search_from_row(r), level=levels.get(r.id))
            for r in session.scalars(
                select(SearchRow).where(SearchRow.status == "open").order_by(SearchRow.id)
            )
        ),
        candidates=tuple(candidates),
        offers=tuple(offers),
        units=tuple(
            replace(unit_from_row(r), services=services.get(r.id))  # type: ignore[arg-type]
            for r in session.scalars(
                select(OrgUnitRow).where(OrgUnitRow.status == "active").order_by(OrgUnitRow.id)
            )
        ),
        plans=tuple(plans),
        products=products,
        product_segments=tuple(
            product_segment_from_row(r)
            for r in session.scalars(
                select(ProductSegmentRow)
                .where(ProductSegmentRow.product_id.in_(product_ids))
                .order_by(ProductSegmentRow.product_id, ProductSegmentRow.segment)
            )
        ),
        markets=tuple(
            market_from_row(r)
            for r in session.scalars(
                select(MarketSegmentRow).order_by(
                    MarketSegmentRow.category, MarketSegmentRow.segment
                )
            )
        ),
        person_states=tuple(
            person_state_from_row(r)
            for r in _plain(  # plain rows (M12b, speed)
                session,
                select(PersonStateRow.__table__)
                .where(in_live(PersonStateRow.person_id))
                .order_by(PersonStateRow.person_id),
            )
        ),
        cap_entries=_all(session, CapEntry, CapTableEntryRow),
        grants=_all(session, OptionGrant, OptionGrantRow),
        safes=_all(session, Safe, SafeRow),
        rounds=tuple(
            finance_from_row(FundingRound, r, nominee_id=nominees.get(r.id))
            for r in session.scalars(select(FundingRoundRow).order_by(FundingRoundRow.id))
        ),
        term_sheets=_all(session, TermSheet, TermSheetRow),
        seats=seats,
        pools=tuple(
            rival_from_row(WorkforcePool, r)
            for r in session.scalars(
                select(WorkforcePoolRow).order_by(
                    WorkforcePoolRow.company_id, WorkforcePoolRow.function
                )
            )
        ),
        rival_effects=tuple(
            rival_from_row(RivalEffect, r)
            for r in session.scalars(
                select(RivalEffectRow)
                .where(RivalEffectRow.end_turn >= meta.current_turn - 1)
                .order_by(RivalEffectRow.id)
            )
        ),
        rival_moves=tuple(
            rival_from_row(RivalMove, r)
            for r in session.scalars(
                select(RivalMoveRow)
                .where(RivalMoveRow.turn >= meta.current_turn - RIVAL_MOVE_MEMORY)
                .order_by(RivalMoveRow.id)
            )
        ),
        approaches=tuple(
            rival_from_row(PoachApproach, r)
            for r in session.scalars(
                select(PoachApproachRow)
                .where(PoachApproachRow.status.in_(("pending", "accepted")))
                .order_by(PoachApproachRow.id)
            )
        ),
        segment_shares=tuple(
            rival_from_row(SegmentShare, r)
            for r in session.scalars(
                select(SegmentShareRow)
                .where(SegmentShareRow.product_id.in_(product_ids))
                .order_by(SegmentShareRow.product_id, SegmentShareRow.segment)
            )
        ),
        free_agents=free_agents,
        **_event_state(session, meta.current_turn),
        relationships=(
            tuple(
                Relationship(r.person_id, r.other_person_id, r.value, r.start_value, r.since_turn)
                for r in session.scalars(
                    select(RelationshipRow).order_by(
                        RelationshipRow.person_id, RelationshipRow.other_person_id
                    )
                )
            )
            if has_table(session, RelationshipRow)
            else ()
        ),
        exec_seats=(
            tuple(
                ExecSeat(r.company_id, r.seat, r.person_id, r.since_turn)
                for r in session.scalars(
                    select(ExecSeatRow).order_by(ExecSeatRow.company_id, ExecSeatRow.seat)
                )
            )
            if m8
            else ()
        ),
        next_ids=_event_ids(session, next_ids_from_meta(meta)),
    )
    state = _load_m10(session, state)
    state = _load_exec(session, state)
    state = _load_pitches(session, state)
    state = load_mna(session, state, has_table)  # M14 (0034)
    state = load_modes(session, state, has_table)  # M15b (0035)
    state = load_founder(session, state, has_table)  # M24 (0037)
    state = load_group(session, state, has_table)  # M16 (0039)
    state = load_commodities(session, state, has_table)  # M17 (0041)
    state = load_exploration(session, state, has_table)  # M18 (0041)
    state = _load_facilities(session, state)
    state = _load_hardware(session, state)
    state = _load_public(session, state)
    state = _load_research(session, state)
    state = _load_geo(session, state, product_ids)
    state = _load_press(session, state)
    return _load_small(session, state)  # M15a (0036)


def _load_small(session: Session, state: GameState) -> GameState:
    """Rival startups' runs of small months (M15a, 0036)."""
    if not has_table(session, StartupSmallRow):
        return state
    since = {r.company_id: r.since_turn for r in session.scalars(select(StartupSmallRow))}
    if not since:
        return state
    return replace(
        state,
        companies=tuple(
            replace(c, small_since_turn=since[c.id]) if c.id in since else c
            for c in state.companies
        ),
    )


def _sync_small(session: Session, old: GameState, new: GameState) -> None:
    if not has_table(session, StartupSmallRow):
        return
    before = {c.id: c.small_since_turn for c in old.companies}
    for c in new.companies:
        if before.get(c.id) == c.small_since_turn:
            continue
        if c.small_since_turn is None:
            row = session.get(StartupSmallRow, c.id)
            if row is not None:
                session.delete(row)
        else:
            session.merge(StartupSmallRow(company_id=c.id, since_turn=c.small_since_turn))


RESEARCH_MEMORY = 24  # months of stopped projects loaded: last events and History (M11)


def _load_research(session: Session, state: GameState) -> GameState:
    """Leads, active and recent projects, arrived eras and licences (M11, 0028)."""
    if not has_table(session, ResearchLeadRow):
        return state

    def after(model: Any) -> int:
        return int(session.scalar(select(func.max(model.id))) or 0) + 1

    since = state.turn - RESEARCH_MEMORY
    return replace(
        state,
        research_leads=tuple(
            ResearchLead(r.company_id, r.domain, float(r.lead))
            for r in session.scalars(
                select(ResearchLeadRow).order_by(ResearchLeadRow.company_id, ResearchLeadRow.domain)
            )
        ),
        research_projects=tuple(
            ResearchProject(
                id=r.id,
                company_id=r.company_id,
                domain=r.domain,
                unit_id=r.unit_id,
                start_turn=r.start_turn,
                status=r.status,  # type: ignore[arg-type]
                budget_cents=r.budget_cents,
                end_turn=r.end_turn,
                recent=tuple(float(v) for v in r.recent or ()),
                gained=float(r.gained),
                last_event=r.last_event,  # type: ignore[arg-type]
                last_event_turn=r.last_event_turn,
            )
            for r in session.scalars(
                select(ResearchProjectRow)
                .where(
                    (ResearchProjectRow.status == "active") | (ResearchProjectRow.end_turn >= since)
                )
                .order_by(ResearchProjectRow.id)
            )
        ),
        era_arrivals=tuple(
            EraArrival(r.key, r.turn, r.company_id, r.months_early)
            for r in session.scalars(select(EraArrivalRow).order_by(EraArrivalRow.key))
        ),
        licenses=tuple(
            License(
                id=r.id,
                licensor_id=r.licensor_id,
                licensee_id=r.licensee_id,
                domain=r.domain,
                points=float(r.points),
                turn=r.turn,
                price_cents=r.price_cents,
                royalty_bp=r.royalty_bp,
                royalty_end_turn=r.royalty_end_turn,
            )
            for r in session.scalars(select(LicenseRow).order_by(LicenseRow.id))
        ),
        next_ids=replace(
            state.next_ids, research_project=after(ResearchProjectRow), license=after(LicenseRow)
        ),
    )


def _sync_research(session: Session, old: GameState, new: GameState) -> None:
    """Changed leads, projects, era arrivals and licences (M11). Leads only grow in number;
    a lead at 0 keeps its row."""
    if (old.research_leads, old.research_projects, old.era_arrivals, old.licenses) == (
        new.research_leads,
        new.research_projects,
        new.era_arrivals,
        new.licenses,
    ) or not has_table(session, ResearchLeadRow):
        return
    session.flush()
    for r in _changed(old.research_leads, new.research_leads, lambda r: (r.company_id, r.domain)):
        session.merge(ResearchLeadRow(company_id=r.company_id, domain=r.domain, lead=r.lead))
    for p in _changed(old.research_projects, new.research_projects, lambda p: p.id):
        session.merge(
            ResearchProjectRow(
                id=p.id,
                company_id=p.company_id,
                domain=p.domain,
                unit_id=p.unit_id,
                start_turn=p.start_turn,
                status=p.status,
                budget_cents=p.budget_cents,
                end_turn=p.end_turn,
                recent=list(p.recent),
                gained=p.gained,
                last_event=p.last_event,
                last_event_turn=p.last_event_turn,
            )
        )
    for a in _changed(old.era_arrivals, new.era_arrivals, lambda a: a.key):
        session.merge(
            EraArrivalRow(
                key=a.key, turn=a.turn, company_id=a.company_id, months_early=a.months_early
            )
        )
    for x in _changed(old.licenses, new.licenses, lambda x: x.id):
        session.merge(
            LicenseRow(
                id=x.id,
                licensor_id=x.licensor_id,
                licensee_id=x.licensee_id,
                domain=x.domain,
                points=x.points,
                turn=x.turn,
                price_cents=x.price_cents,
                royalty_bp=x.royalty_bp,
                royalty_end_turn=x.royalty_end_turn,
            )
        )


def _load_geo(session: Session, state: GameState, product_ids: list[int]) -> GameState:
    """M9 (19): HQ, offices, units' offices, searches' cities and regional markets."""
    if not has_table(session, RegionalSegmentRow):
        return state
    hq = {r.company_id: r.city for r in session.scalars(select(CompanyHqRow))}
    offices = tuple(
        Office(r.id, r.company_id, r.city, r.seats, r.opened_turn, r.status, r.closed_turn)  # type: ignore[arg-type]
        for r in session.scalars(
            select(OfficeRow).where(OfficeRow.status == "open").order_by(OfficeRow.id)
        )
    )
    unit_offices = {r.unit_id: r.office_id for r in session.scalars(select(UnitOfficeRow))}
    search_cities = {r.search_id: r.city for r in session.scalars(select(SearchCityRow))}
    open_ids = [c.person_id for c in state.candidates]
    relocations = {
        r.person_id: r.city
        for r in session.scalars(
            select(CandidateRelocationRow).where(CandidateRelocationRow.person_id.in_(open_ids))
        )
    }
    last_office = session.scalar(select(func.max(OfficeRow.id))) or 0
    return replace(
        state,
        companies=tuple(replace(c, hq_city=hq.get(c.id)) for c in state.companies),
        units=tuple(replace(u, office_id=unit_offices.get(u.id)) for u in state.units),
        searches=tuple(replace(s, city=search_cities.get(s.id)) for s in state.searches),
        candidates=tuple(
            replace(c, relocate_to=relocations.get(c.person_id)) for c in state.candidates
        ),
        offices=offices,
        regional_markets=tuple(
            RegionalMarket(r.category, r.segment, r.region, r.addressable)
            for r in session.scalars(
                select(RegionalMarketRow).order_by(
                    RegionalMarketRow.category, RegionalMarketRow.segment, RegionalMarketRow.region
                )
            )
        ),
        marketing_splits=tuple(
            MarketingSplit(r.product_id, r.region, r.share_bp)
            for r in session.scalars(
                select(MarketingSplitRow)
                .where(MarketingSplitRow.product_id.in_(product_ids))
                .order_by(MarketingSplitRow.product_id, MarketingSplitRow.region)
            )
        )
        if has_table(session, MarketingSplitRow)
        else (),
        product_regions=tuple(
            ProductRegion(r.product_id, r.region, r.launched_turn, r.live_turn)
            for r in session.scalars(
                select(ProductRegionRow)
                .where(ProductRegionRow.product_id.in_(product_ids))
                .order_by(ProductRegionRow.product_id, ProductRegionRow.region)
            )
        ),
        regional_segments=tuple(
            RegionalSegment(
                r.product_id,
                r.region,
                r.segment,
                r.price_cents,
                r.customers,
                r.capacity_limited,
                r.added_turn,
            )
            for r in session.execute(
                select(RegionalSegmentRow.__table__)
                .where(RegionalSegmentRow.product_id.in_(product_ids))
                .order_by(
                    RegionalSegmentRow.product_id,
                    RegionalSegmentRow.region,
                    RegionalSegmentRow.segment,
                )
            ).all()
        ),
        next_ids=replace(state.next_ids, office=last_office + 1),
    )


EXEC_MEMORY = 12  # months of executive decisions the state holds (exec_authority.memory_months)


def _load_exec(session: Session, state: GameState) -> GameState:
    """Authority, recent executive decisions and open or recent proposals (M10c, 0027)."""
    if not has_table(session, AuthorityRow):
        return state
    turn = state.turn

    def after(model: Any) -> int:
        return int(session.scalar(select(func.max(model.id))) or 0) + 1

    return replace(
        state,
        authorities=tuple(
            Authority(
                r.company_id,
                r.seat,
                bool(r.enabled),
                tuple(
                    sorted(
                        (k, tuple(v) if isinstance(v, list) else v)
                        for k, v in (r.guardrails or {}).items()
                    )
                ),
                r.since_turn,
                tuple((int(a[0]), str(a[1]), int(a[2])) for a in r.price_anchors or ()),
            )
            for r in session.scalars(
                select(AuthorityRow).order_by(AuthorityRow.company_id, AuthorityRow.seat)
            )
        ),
        exec_decisions=tuple(
            ExecDecision(r.id, r.company_id, r.seat, r.person_id, r.turn, r.text, bool(r.mistake))
            for r in session.scalars(
                select(ExecDecisionRow)
                .where(ExecDecisionRow.turn > turn - EXEC_MEMORY)
                .order_by(ExecDecisionRow.id)
            )
        ),
        proposals=tuple(
            Proposal(
                r.id,
                r.company_id,
                r.seat,
                r.person_id,
                r.turn,
                r.kind,  # type: ignore[arg-type]
                tuple(sorted((r.params or {}).items())),
                r.text,
                r.status,  # type: ignore[arg-type]
                r.resolved_turn,
            )
            for r in session.scalars(
                select(ProposalRow)
                .where((ProposalRow.status == "pending") | (ProposalRow.turn > turn - EXEC_MEMORY))
                .order_by(ProposalRow.id)
            )
        ),
        next_ids=replace(
            state.next_ids, exec_decision=after(ExecDecisionRow), proposal=after(ProposalRow)
        ),
    )


PITCH_FIELDS = tuple(f for f in Pitch.__dataclass_fields__ if f != "params")


def _load_pitches(session: Session, state: GameState) -> GameState:
    """Every pitch and the pitch settings (M13b, 0032)."""
    if not has_table(session, PitchRow):
        return state
    pitches = tuple(
        Pitch(
            params=tuple(sorted((r.params or {}).items())),
            **{f: getattr(r, f) for f in PITCH_FIELDS},
        )
        for r in session.scalars(select(PitchRow).order_by(PitchRow.id))
    )
    policies = tuple(
        PitchPolicy(r.company_id, r.auto_approve_cents, bool(r.stop_for_big))
        for r in session.scalars(select(PitchPolicyRow).order_by(PitchPolicyRow.company_id))
    )
    last = int(session.scalar(select(func.max(PitchRow.id))) or 0)
    windows = tuple(
        EraWindow(
            r.era_key,
            r.company_id,
            r.start_turn,
            tuple((int(p[0]), float(p[1]), int(p[2])) for p in r.products),
            float(r.trend),
            tuple((str(d[0]), float(d[1])) for d in r.demand),
            bool(r.reported),
        )
        for r in session.scalars(
            select(EraWindowRow).order_by(EraWindowRow.era_key, EraWindowRow.company_id)
        )
    )
    return replace(
        state,
        pitches=pitches,
        pitch_policies=policies,
        era_windows=windows,
        next_ids=replace(state.next_ids, pitch=last + 1),
    )


def _sync_pitches(session: Session, old: GameState, new: GameState) -> None:
    if (old.pitches, old.pitch_policies, old.era_windows) == (
        new.pitches,
        new.pitch_policies,
        new.era_windows,
    ) or not has_table(session, PitchRow):
        return
    for w in _changed(old.era_windows, new.era_windows, lambda w: (w.era_key, w.company_id)):
        session.merge(
            EraWindowRow(
                era_key=w.era_key,
                company_id=w.company_id,
                start_turn=w.start_turn,
                products=[list(p) for p in w.products],
                trend=w.trend,
                demand=[list(d) for d in w.demand],
                reported=w.reported,
            )
        )
    for p in _changed(old.pitches, new.pitches, lambda p: p.id):
        session.merge(PitchRow(params=dict(p.params), **{f: getattr(p, f) for f in PITCH_FIELDS}))
    for pol in _changed(old.pitch_policies, new.pitch_policies, lambda p: p.company_id):
        session.merge(
            PitchPolicyRow(
                company_id=pol.company_id,
                auto_approve_cents=pol.auto_approve_cents,
                stop_for_big=pol.stop_for_big,
            )
        )


def _sync_exec(session: Session, old: GameState, new: GameState) -> None:
    """Authority records, new decisions and changed proposals (M10c)."""
    if (old.authorities, old.exec_decisions, old.proposals) == (
        new.authorities,
        new.exec_decisions,
        new.proposals,
    ) or not has_table(session, AuthorityRow):
        return
    session.flush()
    for a in _changed(old.authorities, new.authorities, lambda a: (a.company_id, a.seat)):
        session.merge(
            AuthorityRow(
                company_id=a.company_id,
                seat=a.seat,
                enabled=a.enabled,
                guardrails={k: list(v) if isinstance(v, tuple) else v for k, v in a.guardrails},
                since_turn=a.since_turn,
                price_anchors=[list(x) for x in a.price_anchors],
            )
        )
    for d in _changed(old.exec_decisions, new.exec_decisions, lambda d: d.id):
        session.merge(
            ExecDecisionRow(
                id=d.id,
                company_id=d.company_id,
                seat=d.seat,
                person_id=d.person_id,
                turn=d.turn,
                text=d.text,
                mistake=d.mistake,
            )
        )
    for p in _changed(old.proposals, new.proposals, lambda p: p.id):
        session.merge(
            ProposalRow(
                id=p.id,
                company_id=p.company_id,
                seat=p.seat,
                person_id=p.person_id,
                turn=p.turn,
                kind=p.kind,
                params=dict(p.params),
                text=p.text,
                status=p.status,
                resolved_turn=p.resolved_turn,
            )
        )


# --- Facilities (M12a, 0028) -------------------------------------------------------------------

FACILITY_MEMORY = 24  # months of outages and settled contracts kept in the live state


def facility_from_row(r: FacilityRow) -> Facility:
    return Facility(
        id=r.id,
        company_id=r.company_id,
        kind=r.kind,
        region=r.region,
        capacity=r.capacity,
        on_time=r.on_time,
        ordered_turn=r.ordered_turn,
        ready_turn=r.ready_turn,
        late_turn=r.late_turn,
        capex_cents=r.capex_cents,
        input_index=r.input_index,
        capex_paid_cents=r.capex_paid_cents,
        depreciated_cents=r.depreciated_cents,
        status=r.status,  # type: ignore[arg-type]
        city=r.city,
        unit_id=r.unit_id,
        contract_id=r.contract_id,
        closed_turn=r.closed_turn,
        yield_rate=r.yield_rate,
        run_units=r.run_units,
        sold_units=r.sold_units,
    )


def facility_to_row(f: Facility) -> FacilityRow:
    return FacilityRow(**asdict(f))


def good_month_from_row(r: SupplyMonthRow) -> GoodMonth:
    return GoodMonth(
        good=r.good,
        turn=r.turn,
        index=r.price_index,
        allocation=r.allocation,
        base=r.base,
        change=r.change,
        shock_turn=r.shock_turn,
        shock_months=r.shock_months,
        shock_rise=r.shock_rise,
        shock_allocation=r.shock_allocation,
        shock_kind=r.shock_kind,
    )


def good_month_to_row(g: GoodMonth) -> SupplyMonthRow:
    fields = asdict(g)
    fields["price_index"] = fields.pop("index")
    return SupplyMonthRow(**fields)


def contract_from_row(r: SupplyContractRow) -> SupplyContract:
    return SupplyContract(
        id=r.id,
        company_id=r.company_id,
        good=r.good,
        index=r.price_index,
        signed_turn=r.signed_turn,
        end_turn=r.end_turn,
        volume=r.volume,
        unit_value_cents=r.unit_value_cents,
        used=r.used,
        status=r.status,  # type: ignore[arg-type]
        settled_cents=r.settled_cents,
    )


def contract_to_row(c: SupplyContract) -> SupplyContractRow:
    fields = asdict(c)
    fields["price_index"] = fields.pop("index")
    return SupplyContractRow(**fields)


def _load_facilities(session: Session, state: GameState) -> GameState:
    """Facilities that are not closed, each good's latest month, contracts active or settled
    lately and recent outages (M12a, 0028)."""
    if not has_table(session, FacilityRow):
        return state
    keys = {r.company_id: tuple(r.rival_key) for r in session.scalars(select(CompanyRivalKeyRow))}
    if keys:
        state = replace(
            state,
            companies=tuple(
                replace(c, rival_key=keys[c.id]) if c.id in keys else c for c in state.companies
            ),
        )
    turn = state.turn
    facilities = tuple(
        facility_from_row(r)
        for r in session.scalars(
            select(FacilityRow).where(FacilityRow.status != "closed").order_by(FacilityRow.id)
        )
    )
    latest: dict[str, GoodMonth] = {}
    # only months already played (M12r): a row at or after the save's turn is never loaded
    last_turn = session.scalar(
        select(func.max(SupplyMonthRow.turn)).where(SupplyMonthRow.turn < turn)
    )
    if last_turn is not None:
        for r in session.scalars(select(SupplyMonthRow).where(SupplyMonthRow.turn == last_turn)):
            latest[r.good] = good_month_from_row(r)
    contracts = tuple(
        contract_from_row(r)
        for r in session.scalars(
            select(SupplyContractRow)
            .where(
                (SupplyContractRow.status == "active")
                | (SupplyContractRow.end_turn >= turn - FACILITY_MEMORY)
            )
            .order_by(SupplyContractRow.id)
        )
    )
    outages = tuple(
        Outage(r.id, r.facility_id, r.company_id, r.turn, r.customers_lost)
        for r in session.scalars(
            select(FacilityOutageRow)
            .where(FacilityOutageRow.turn > turn - FACILITY_MEMORY)
            .order_by(FacilityOutageRow.id)
        )
    )

    def next_id(model: Any) -> int:
        return int(session.scalar(select(func.max(model.id))) or 0) + 1

    return replace(
        state,
        facilities=facilities,
        supply=tuple(latest[g] for g in sorted(latest, key=lambda g: _good_order(g))),
        contracts=contracts,
        outages=outages,
        next_ids=replace(
            state.next_ids,
            facility=next_id(FacilityRow),
            contract=next_id(SupplyContractRow),
            outage=next_id(FacilityOutageRow),
        ),
    )


def _load_hardware(session: Session, state: GameState) -> GameState:
    """Production contracts (active, and ended ones of the last months) and the last
    month's production (M12b, 0031)."""
    if not has_table(session, ProductionContractRow):
        return state
    turn = state.turn
    contracts = tuple(
        ProductionContract(
            id=r.id,
            company_id=r.company_id,
            product_id=r.product_id,
            kind=r.kind,  # type: ignore[arg-type]
            supplier=r.supplier,
            units=r.units,
            price_millicents=r.price_millicents,
            signed_turn=r.signed_turn,
            end_turn=r.end_turn,
            city=r.city,
            delivered=r.delivered,
            used=r.used,
            charged_cents=r.charged_cents,
            status=r.status,  # type: ignore[arg-type]
        )
        for r in session.scalars(
            select(ProductionContractRow)
            .where(
                (ProductionContractRow.status == "active")
                | (ProductionContractRow.end_turn >= turn - FACILITY_MEMORY)
            )
            .order_by(ProductionContractRow.id)
        )
    )
    last = session.scalar(select(func.max(ProductionMonthRow.turn)))
    production: tuple[ProductionMonth, ...] = ()
    if last is not None and last == turn - 1:
        production = tuple(
            ProductionMonth(
                **{
                    k: getattr(r, k)
                    for k in ProductionMonth.__dataclass_fields__  # same names as the columns
                }
            )
            for r in session.scalars(
                select(ProductionMonthRow)
                .where(ProductionMonthRow.turn == last)
                .order_by(ProductionMonthRow.product_id)
            )
        )
    nxt = int(session.scalar(select(func.max(ProductionContractRow.id))) or 0) + 1
    return replace(
        state,
        production_contracts=contracts,
        production=production,
        next_ids=replace(state.next_ids, production_contract=nxt),
    )


def _sync_hardware(session: Session, old: GameState, new: GameState) -> None:
    """Production contracts and the month's production rows (M12b)."""
    if not has_table(session, ProductionContractRow):
        return
    session.flush()
    for c in _changed(old.production_contracts, new.production_contracts, lambda c: c.id):
        session.merge(ProductionContractRow(**asdict(c)))
    before = set(old.production)
    _insert(session, (ProductionMonthRow(**asdict(p)) for p in new.production if p not in before))


def _good_order(good: str) -> tuple[int, str]:
    """Goods in components_history.yaml order (server, GPU, then M12b's device and server
    BOMs, equipment and foundry wafers), others after by key."""
    known = ("server", "gpu", "device_bom", "server_bom", "equipment", "foundry_wafer")
    return (known.index(good), good) if good in known else (len(known), good)


def _sync_facilities(session: Session, old: GameState, new: GameState) -> None:
    """Facilities, each good's month, contracts and outages (M12a)."""
    if not has_table(session, FacilityRow):
        return
    session.flush()
    before_keys = {c.id: c.rival_key for c in old.companies}
    for company in new.companies:
        if company.rival_key and before_keys.get(company.id) != company.rival_key:
            row = CompanyRivalKeyRow(company_id=company.id, rival_key=list(company.rival_key))
            session.merge(row)
    for f in _changed(old.facilities, new.facilities, lambda f: f.id):
        session.merge(facility_to_row(f))
    before = {(g.good, g.turn): g for g in old.supply}
    fresh = []
    for g in new.supply:
        if (g.good, g.turn) not in before:
            fresh.append(good_month_to_row(g))  # a new month: no row yet (M12b: bulk insert)
        elif before[(g.good, g.turn)] != g:
            session.merge(good_month_to_row(g))
    _insert(session, fresh)
    for c in _changed(old.contracts, new.contracts, lambda c: c.id):
        session.merge(contract_to_row(c))
    seen = {o.id for o in old.outages}
    for o in new.outages:
        if o.id not in seen:
            session.merge(FacilityOutageRow(**asdict(o)))


# --- Going public and the Chair (M13, 0030) ----------------------------------------------------

SHARE_HISTORY = 36  # month ends of share prices kept in the live state (public.history_months)
CEO_MEMORY = 12  # months of CEO decisions, and of ended CEOs, the state holds (ceo.memory_months)


def _ceo_live(ceo: Ceo, turn: int) -> bool:
    """Serving, or ended within the last CEO_MEMORY months."""
    return ceo.ended_turn is None or ceo.ended_turn > turn - CEO_MEMORY


def listing_from_row(r: ListingRow) -> Listing:
    return Listing(
        company_id=r.company_id,
        bank=r.bank,
        hired_turn=r.hired_turn,
        status=r.status,  # type: ignore[arg-type]
        filed_late=r.filed_late,
        roadshow_turn=r.roadshow_turn,
        ambition=r.ambition,
        share_choice=r.share_choice,
        dual_class=r.dual_class,
        demand=r.demand,
        price_choice=r.price_choice,  # type: ignore[arg-type]
        shares_before=r.shares_before,
        new_shares=r.new_shares,
        price_cents=r.price_cents,
        gross_cents=r.gross_cents,
        fee_cents=r.fee_cents,
        first_day_return=r.first_day_return,
        close_cents=r.close_cents,
        listed_turn=r.listed_turn,
        pulled_turn=r.pulled_turn,
        ticker=r.ticker,
    )


def public_from_row(r: PublicCompanyRow) -> PublicCompany:
    return PublicCompany(
        company_id=r.company_id,
        listed_turn=r.listed_turn,
        ticker=r.ticker,
        dual_class=r.dual_class,
        listing_price_cents=r.listing_price_cents,
        price_cents=r.price_cents,
        sentiment=r.sentiment,
        value_cents=r.value_cents,
        analysts=tuple(Analyst(int(i), int(t), rating) for i, t, rating in r.analysts),
        below_value_months=r.below_value_months,
        below_takeover_months=r.below_takeover_months,
        last_activist_turn=r.last_activist_turn,
        last_takeover_turn=r.last_takeover_turn,
        beat_streak=r.beat_streak,
        miss_streak=r.miss_streak,
        results=tuple(r.results),  # type: ignore[arg-type]
        quarter_revenue_cents=r.quarter_revenue_cents,
        quarter_op_cents=r.quarter_op_cents,
        dividend_cents=r.dividend_cents,
        lapsed_seats=r.lapsed_seats,
        pending=tuple(r.pending),
    )


def public_to_row(p: PublicCompany) -> PublicCompanyRow:
    fields = asdict(p)
    fields["analysts"] = [[a.index, a.target_cents, a.rating] for a in p.analysts]
    fields["results"] = list(p.results)
    fields["pending"] = list(p.pending)
    return PublicCompanyRow(**fields)


def guidance_from_row(r: GuidanceRow) -> Guidance:
    return Guidance(
        company_id=r.company_id,
        quarter_turn=r.quarter_turn,
        revenue_cents=r.revenue_cents,
        margin_bp=r.margin_bp,
        consensus_revenue_cents=r.consensus_revenue_cents,
        consensus_margin_bp=r.consensus_margin_bp,
        by_player=r.by_player,
        actual_revenue_cents=r.actual_revenue_cents,
        actual_margin_bp=r.actual_margin_bp,
        result=r.result,  # type: ignore[arg-type]
        price_before_cents=r.price_before_cents,
        price_after_cents=r.price_after_cents,
    )


def ceo_from_row(r: CeoRow) -> Ceo:
    return Ceo(
        id=r.id,
        company_id=r.company_id,
        person_id=r.person_id,
        since_turn=r.since_turn,
        scopes=tuple(r.scopes),
        ended_turn=r.ended_turn,
        end_reason=r.end_reason,
        low_months=r.low_months,
        price_anchors=tuple((int(p), str(s), int(c)) for p, s, c in r.price_anchors),
    )


def ceo_to_row(c: Ceo) -> CeoRow:
    fields = asdict(c)
    fields["scopes"] = list(c.scopes)
    fields["price_anchors"] = [list(a) for a in c.price_anchors]
    return CeoRow(**fields)


def ceo_decision_from_row(r: CeoDecisionRow) -> CeoDecision:
    return CeoDecision(
        id=r.id,
        company_id=r.company_id,
        person_id=r.person_id,
        turn=r.turn,
        scope=r.scope,
        text=r.text,
        mistake=r.mistake,
        undo=tuple((str(k), v) for k, v in r.undo),
        overridden_turn=r.overridden_turn,
    )


def ceo_decision_to_row(d: CeoDecision) -> CeoDecisionRow:
    fields = asdict(d)
    fields["undo"] = [[k, v] for k, v in d.undo]
    return CeoDecisionRow(**fields)


def _load_public(session: Session, state: GameState) -> GameState:
    """Listings, listed companies and all their guidance, the last SHARE_HISTORY month ends,
    CEOs serving or ended lately and their recent decisions (M13, 0030)."""
    if not has_table(session, ListingRow):
        return state
    turn = state.turn

    def next_id(model: Any) -> int:
        return int(session.scalar(select(func.max(model.id))) or 0) + 1

    return replace(
        state,
        listings=tuple(
            listing_from_row(r)
            for r in session.scalars(select(ListingRow).order_by(ListingRow.company_id))
        ),
        public_companies=tuple(
            public_from_row(r)
            for r in session.scalars(select(PublicCompanyRow).order_by(PublicCompanyRow.company_id))
        ),
        guidance=tuple(
            guidance_from_row(r)
            for r in session.scalars(
                select(GuidanceRow).order_by(GuidanceRow.company_id, GuidanceRow.quarter_turn)
            )
        ),
        share_months=tuple(
            ShareMonth(r.company_id, r.turn, r.price_cents, r.shares, r.mark)
            for r in session.scalars(
                select(ShareMonthRow)
                .where(ShareMonthRow.turn > turn - SHARE_HISTORY)
                .order_by(ShareMonthRow.company_id, ShareMonthRow.turn)
            )
        ),
        ceos=tuple(
            ceo_from_row(r)
            for r in session.scalars(
                select(CeoRow)
                .where(CeoRow.ended_turn.is_(None) | (CeoRow.ended_turn > turn - CEO_MEMORY))
                .order_by(CeoRow.id)
            )
        ),
        ceo_decisions=tuple(
            ceo_decision_from_row(r)
            for r in session.scalars(
                select(CeoDecisionRow)
                .where(CeoDecisionRow.turn > turn - CEO_MEMORY)
                .order_by(CeoDecisionRow.id)
            )
        ),
        next_ids=replace(state.next_ids, ceo=next_id(CeoRow), ceo_decision=next_id(CeoDecisionRow)),
    )


def _sync_public(session: Session, old: GameState, new: GameState) -> None:
    """Listings, listed companies, guidance, month ends, CEOs and their decisions (M13)."""
    if not has_table(session, ListingRow):
        return
    session.flush()
    for x in _changed(old.listings, new.listings, lambda x: x.company_id):
        session.merge(ListingRow(**asdict(x)))
    for p in _changed(old.public_companies, new.public_companies, lambda p: p.company_id):
        session.merge(public_to_row(p))
    # A delisting (a sale, M15b addendum 10) removes the current listed state; the share-price
    # history (share_month) stays (M15r, Codex review 4 finding 4).
    kept = {p.company_id for p in new.public_companies}
    gone = [p.company_id for p in old.public_companies if p.company_id not in kept]
    if gone:
        session.execute(delete(PublicCompanyRow).where(PublicCompanyRow.company_id.in_(gone)))
    for g in _changed(old.guidance, new.guidance, lambda g: (g.company_id, g.quarter_turn)):
        session.merge(GuidanceRow(**asdict(g)))
    for m in _changed(old.share_months, new.share_months, lambda m: (m.company_id, m.turn)):
        session.merge(ShareMonthRow(**asdict(m)))
    for c in _changed(old.ceos, new.ceos, lambda c: c.id):
        session.merge(ceo_to_row(c))
    for d in _changed(old.ceo_decisions, new.ceo_decisions, lambda d: d.id):
        session.merge(ceo_decision_to_row(d))


def _load_m10(session: Session, state: GameState) -> GameState:
    """The latest macro month, every loan, and the player's covenant history (M10, 0022)."""
    if not has_table(session, LoanRow):
        return state
    latest = session.scalars(select(MacroMonthRow).order_by(MacroMonthRow.turn.desc())).first()
    histories = {r.company_id: r for r in session.scalars(select(FinanceHistoryRow))}
    companies = tuple(
        replace(
            c,
            op_history=tuple(int(v) for v in histories[c.id].op_history),
            burn_history=tuple(int(v) for v in histories[c.id].burn_history),
        )
        if c.id in histories
        else c
        for c in state.companies
    )
    return replace(
        state,
        companies=companies,
        macro=macro_from_row(latest) if latest is not None else None,
        loans=_all(session, Loan, LoanRow),
        next_ids=replace(
            state.next_ids,
            loan=int(session.scalar(select(func.max(LoanRow.id))) or 0) + 1,
        ),
    )


def macro_from_row(row: MacroMonthRow) -> MacroMonth:
    return MacroMonth(
        turn=row.turn,
        base_rate=row.base_rate,
        climate=row.climate,
        confidence=row.confidence,
        ai_index=row.ai_index,
        ai_change=row.ai_change,
        downturn_turn=row.downturn_turn,
    )


def _sync_m10(session: Session, old: GameState, new: GameState) -> None:
    """The month's macro indicators, loans and the covenant history (M10)."""
    if not has_table(session, LoanRow):
        return
    session.flush()
    if new.macro is not None and new.macro != old.macro:
        session.merge(MacroMonthRow(**asdict(new.macro)))
    for loan in _changed(old.loans, new.loans, lambda x: x.id):
        session.merge(finance_to_row(loan))
    # one UPDATE for companies whose row exists (it does once a history was written: the
    # state loads it from there), a merge for the rest (M14: rivals record theirs monthly)
    before = {c.id: (c.op_history, c.burn_history) for c in old.companies}
    updates: list[dict[str, Any]] = []
    for c in new.companies:
        was = before.get(c.id)
        if not (c.op_history or c.burn_history) or was == (c.op_history, c.burn_history):
            continue
        row = {
            "company_id": c.id,
            "op_history": list(c.op_history),
            "burn_history": list(c.burn_history),
        }
        if was is not None and (was[0] or was[1]):
            updates.append(row)
        else:
            session.merge(FinanceHistoryRow(**row))
    _update_rows(session, FinanceHistoryRow, updates)


def _event_state(session: Session, turn: int) -> dict[str, Any]:
    """Events of the last 24 months and any still open, active storylines and follow-ups not
    yet queued (M6). Empty on a save whose migration 0016 has not run yet."""
    if not has_table(session, EventRow):
        return {}
    return {
        "events": tuple(
            event_from_row(r)
            for r in session.scalars(
                select(EventRow)
                .where(
                    (EventRow.turn > turn - EVENT_MEMORY) | EventRow.status.in_(("pending", "open"))
                )
                .order_by(EventRow.id)
            )
        ),
        "storylines": tuple(
            storyline_from_row(r)
            for r in session.scalars(
                select(StorylineRow)
                .where(StorylineRow.status == "active")
                .order_by(StorylineRow.id)
            )
        ),
        "queued": tuple(
            queued_from_row(r)
            for r in session.scalars(
                select(EventQueueRow)
                .where(EventQueueRow.done.is_(False))
                .order_by(EventQueueRow.id)
            )
        ),
        # M10b (23.2): modifiers still running; expired rows stay for history.
        "modifiers": tuple(
            modifier_from_row(r)
            for r in session.scalars(
                select(EventModifierRow)
                .where(EventModifierRow.end_turn > turn)
                .order_by(EventModifierRow.id)
            )
        )
        if has_table(session, EventModifierRow)
        else (),
    }


def _event_ids(session: Session, ids: NextIds) -> NextIds:
    """Event, storyline and queue ids continue from the largest stored (M6: not in
    save_meta, so an old save's migration 0013 never reads a column it lacks)."""
    if not has_table(session, EventRow):
        return ids

    def after(model: Any) -> int:
        return int(session.scalar(select(func.max(model.id))) or 0) + 1

    ids = replace(
        ids, event=after(EventRow), storyline=after(StorylineRow), queued=after(EventQueueRow)
    )
    if has_table(session, EventModifierRow):  # M10b
        ids = replace(ids, modifier=after(EventModifierRow))
    return ids


def has_table(session: Session, model: Any) -> bool:
    """Whether the save already has a table added or rebuilt after 0013, with the model's
    columns. Migration 0013 loads and syncs state through the current models, so on an
    older save it runs before later migrations have made their tables; those tables then
    read as empty and are not written (M6 sub-task 0)."""
    insp = inspect(session.connection())
    if not insp.has_table(model.__tablename__):
        return False
    have = {c["name"] for c in insp.get_columns(model.__tablename__)}
    return {c.name for c in model.__table__.columns} <= have


def _plain(session: Session, statement: Any) -> list[Any]:
    """A statement's plain rows (column attributes only): rows read like the ORM objects the
    mappers take, without building one per row (M12b: more rivals' people)."""
    return list(session.execute(statement).all())


def _rows(session: Session, model: Any, where: Any) -> list[Any]:
    """Plain rows (column attributes only) for a large child table: building ORM objects
    for every skill and knowledge record was most of a load's time once rivals had people
    (M5)."""
    return list(session.execute(select(model.__table__).where(where)).all())


def _all[T](session: Session, cls: type[T], row: Any) -> tuple[T, ...]:
    """Every row of a small finance table (M4), by id."""
    return tuple(finance_from_row(cls, r) for r in session.scalars(select(row).order_by(row.id)))


# --- Writing --------------------------------------------------------------------------------


def _changed[T](old: Iterable[T], new: Iterable[T], key: Any) -> list[T]:
    """Items of `new` that are new or differ from the item with the same key in `old`."""
    if old is new:
        return []
    before = {key(x): x for x in old}
    return [x for x in new if (o := before.get(key(x))) is not x and o != x]


def _write[T](session: Session, old: Iterable[T], new: Iterable[T], key: Any, to_row: Any) -> None:
    """Write the changed items of `new`: one bulk UPDATE by primary key for items that were in
    `old` (their rows exist), a merge for the rest. A merge per row costs a SELECT, which made
    every turn write rivals' people and shares one at a time (M6 sub-task 0)."""
    known = {key(x) for x in old}
    updates: list[dict[str, Any]] = []
    model: Any = None
    for item in _changed(old, new, key):
        row = to_row(item)
        if key(item) in known:
            model = type(row)
            updates.append({a.key: getattr(row, a.key) for a in model.__mapper__.column_attrs})
        else:
            session.merge(row)
    _update_rows(session, model, updates)


@cache
def _update_statement(model: Any, keys: tuple[str, ...]) -> Update:
    """UPDATE <table> SET <keys> WHERE <primary key>, with a bind parameter per attribute."""
    mapper = model.__mapper__
    pk = {mapper.get_property_by_column(c).key: c for c in mapper.primary_key}
    return (
        model.__table__.update()
        .where(and_(*(col == bindparam(f"b_{k}") for k, col in pk.items())))
        .values({mapper.columns[k].name: bindparam(f"b_{k}") for k in keys if k not in pk})
    )


def _update_rows(session: Session, model: Any, rows: list[dict[str, Any]]) -> None:
    """Bulk UPDATE by primary key as one Core executemany per set of attributes. The ORM's
    bulk UPDATE builds each row's parameters in Python and cost more than the SQL itself
    (M7a sub-task 0). `rows` are attribute -> value and include the primary key."""
    if not rows:
        return
    session.flush()  # a Core statement does not flush: rows it may reference come first
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row)].append(row)
    for keys, same in groups.items():
        names = tuple(f"b_{k}" for k in keys)  # once per group, not per row (M14 turn time)
        params = [dict(zip(names, row.values(), strict=True)) for row in same]
        session.execute(_update_statement(model, keys), params)


def _insert(session: Session, rows: Iterable[Any]) -> None:
    """Insert new rows with one executemany per table instead of the unit of work (a new
    save writes thousands of people's child rows; M6 sub-task 0). A column left None that
    has a default keeps its default."""
    by_model: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        model = type(row)
        by_model[model].append(
            {
                a.key: v
                for a in model.__mapper__.column_attrs
                if (v := getattr(row, a.key)) is not None
                or (a.columns[0].default is None and a.columns[0].server_default is None)
            }
        )
    for model, values in by_model.items():
        session.execute(insert(model), values)


def insert_rows(session: Session, rows: Iterable[Any]) -> None:
    """`_insert` for append-only rows of a turn (logs, months, snapshots): one executemany per
    table instead of the unit of work (M7a sub-task 0)."""
    session.flush()  # rows they reference come first
    _insert(session, rows)


def insert_entries(session: Session, entries: Iterable[LedgerEntry]) -> None:
    """Ledger entries and their lines as two executemanys, entry ids continuing from the
    largest stored (the unit of work inserted them one entry at a time; M7a sub-task 0)."""
    entries = list(entries)
    if not entries:
        return
    session.flush()
    first = int(session.scalar(select(func.max(LedgerEntryRow.id))) or 0) + 1
    session.execute(
        insert(cast(Table, LedgerEntryRow.__table__)),
        [
            {"id": first + i, "turn": e.turn, "company_id": e.company_id, "memo": e.memo}
            for i, e in enumerate(entries)
        ],
    )
    lines = [
        {"entry_id": first + i, "account_code": ln.account, "amount_cents": ln.amount}
        for i, e in enumerate(entries)
        for ln in e.lines
    ]
    divisions = [ln.division_id for e in entries for ln in e.lines]
    if any(d is not None for d in divisions):  # M8 (18.1); absent keeps pre-0020 saves working
        for line, division in zip(lines, divisions, strict=True):
            line["division_id"] = division
    session.execute(insert(cast(Table, LedgerLineRow.__table__)), lines)


def _sync_relationships(session: Session, old: GameState, new: GameState) -> None:
    """Pairs are written like other rows; pairs that ended are deleted in one executemany
    (16.7; M14 turn time: one DELETE each)."""
    if old.relationships is new.relationships:
        return
    if len(old.relationships) == len(new.relationships):  # the usual month: same pairs
        moved = [
            (o, n) for o, n in zip(old.relationships, new.relationships, strict=True) if o is not n
        ]
        if all(o.key == n.key for o, n in moved):
            _update_rows(session, RelationshipRow, [_rel_row(n) for o, n in moved if o != n])
            return
    before = old.relationship_map()
    ended = before.keys() - new.relationship_map().keys()
    if ended:
        session.flush()
        table = cast(Table, RelationshipRow.__table__)
        session.execute(
            delete(table).where(
                table.c.person_id == bindparam("b_a"),
                table.c.other_person_id == bindparam("b_b"),
            ),
            [{"b_a": a, "b_b": b} for a, b in sorted(ended)],
        )
    # changed pairs as plain parameter rows: an ORM row each cost more than the SQL (M14)
    updates: list[dict[str, Any]] = []
    inserts: list[dict[str, Any]] = []
    for r in new.relationships:
        o = before.get(r.key)
        if o is r or o == r:
            continue
        (inserts if o is None else updates).append(_rel_row(r))
    _update_rows(session, RelationshipRow, updates)
    if inserts:
        session.flush()
        session.execute(insert(RelationshipRow), inserts)


def _rel_row(r: Relationship) -> dict[str, Any]:
    return {
        "person_id": r.a,
        "other_person_id": r.b,
        "value": r.value,
        "start_value": r.start,
        "since_turn": r.since_turn,
    }


def _sync_reveal(
    session: Session,
    old: RevealState | None,
    new: RevealState,
    changed: list[dict[str, Any]],
) -> None:
    """Write one reveal; its changed attribute records go to `changed`, which the caller
    writes for every reveal at once (M7a: one UPDATE per reveal was a tenth of a turn)."""
    if old is None:
        _insert(session, reveal_to_rows(new))
        return
    base = {"person_id": new.person_id, "observer_company_id": new.observer_company_id}
    old_records = dict(old.attributes)
    changed += [
        {
            **base,
            "attribute": attr,
            "hw": rec.hw,
            "center_offset": rec.offset,
            "last_updated_turn": rec.last_updated_turn,
        }
        for attr, rec in new.attributes
        if old_records.get(attr) != rec
    ]
    if old.profile_revealed_turn is None and new.profile_revealed_turn is not None:
        session.add(PersonProfileRevealRow(**base, revealed_turn=new.profile_revealed_turn))
    known = {tag for tag, _ in old.revealed_tags}
    session.add_all(
        PersonTagRevealRow(**base, tag=tag, revealed_turn=turn)
        for tag, turn in new.revealed_tags
        if tag not in known
    )


def sync_state(session: Session, old: GameState | None, new: GameState) -> None:
    """Write the differences between `old` (as loaded, or None for a new save) and `new`."""
    old = old or GameState(save_meta=new.save_meta, turn=new.turn, companies=())

    _write(session, old.companies, new.companies, lambda c: c.id, company_to_row)
    session.flush()
    _write(session, old.products, new.products, lambda p: p.id, product_to_row)
    session.flush()
    _write(
        session,
        old.product_segments,
        new.product_segments,
        lambda s: (s.product_id, s.segment),
        product_segment_to_row,
    )
    _write(session, old.markets, new.markets, lambda m: (m.category, m.segment), market_to_row)

    old_people = {p.id: p for p in old.people}
    skill_updates: list[dict[str, Any]] = []
    asks: list[dict[str, Any]] = []  # a poached key person's new ask (M5, 15.6)
    added = [p for p in new.people if p.id not in old_people]
    rows = [person_to_rows(p) for p in added]
    session.add_all(r[0] for r in rows)  # person rows first: children reference them
    session.flush()
    _insert(session, (child for r in rows for child in r[1:]))
    for person in new.people:
        before = old_people.get(person.id)
        if (
            before is not None
            and before.salary_expectation_cents != person.salary_expectation_cents
        ):
            asks.append(
                {"id": person.id, "salary_expectation_cents": person.salary_expectation_cents}
            )
        if before is not None and before is not person and before != person:
            old_skills = before.skills.as_dict()
            skill_updates += [
                {"person_id": person.id, "skill": k, "value": v}
                for k, v in person.skills.items
                if old_skills[k] != v
            ]
    session.flush()
    _update_rows(session, PersonSkillRow, skill_updates)
    _update_rows(session, PersonRow, asks)

    # Units before employments and plans, which reference them; plans before offers.
    for unit in _changed(old.units, new.units, lambda u: u.id):
        session.merge(unit_to_row(unit))
    session.flush()
    for employment in _changed(old.employments, new.employments, lambda e: e.id):
        session.merge(employment_to_row(employment))
    for search in _changed(old.searches, new.searches, lambda s: s.id):
        session.merge(search_to_row(search))
    session.flush()
    for plan in _changed(old.plans, new.plans, lambda p: p.id):
        session.merge(plan_to_row(plan))
    session.flush()
    for candidate in _changed(old.candidates, new.candidates, lambda c: c.person_id):
        session.merge(candidate_to_row(candidate))
    for offer in _changed(old.offers, new.offers, lambda o: o.id):
        session.merge(offer_to_row(offer))
    _write(
        session, old.person_states, new.person_states, lambda p: p.person_id, person_state_to_row
    )

    old_reveals = {(r.observer_company_id, r.person_id): r for r in old.reveals}
    reveal_updates: list[dict[str, Any]] = []
    for reveal in new.reveals:
        known = old_reveals.get((reveal.observer_company_id, reveal.person_id))
        if known != reveal:
            _sync_reveal(session, known, reveal, reveal_updates)
    _update_rows(session, PersonRevealRow, reveal_updates)

    # Finance (M4): rounds before their term sheets.
    for items in (
        _changed(old.cap_entries, new.cap_entries, lambda e: e.id),
        _changed(old.grants, new.grants, lambda g: g.id),
        _changed(old.safes, new.safes, lambda s: s.id),
        _changed(old.rounds, new.rounds, lambda r: r.id),
        _changed(old.term_sheets, new.term_sheets, lambda t: t.id),
        _changed(old.seats, new.seats, lambda s: s.id),
    ):
        for item in items:
            session.merge(finance_to_row(item))
        session.flush()
    for seat in _changed(old.seats, new.seats, lambda s: s.id):
        session.merge(seat_history_row(seat))
    # A sold company's board goes with the sale (M15b addendum 10; M15r, Codex review 4
    # finding 4): seats removed from the state leave the save too.
    kept_seats = {s.id for s in new.seats}
    gone_seats = [s.id for s in old.seats if s.id not in kept_seats]
    if gone_seats:
        session.execute(
            delete(BoardSeatHistoryRow).where(BoardSeatHistoryRow.seat_id.in_(gone_seats))
        )
        session.execute(delete(BoardSeatRow).where(BoardSeatRow.id.in_(gone_seats)))
    for rnd in _changed(old.rounds, new.rounds, lambda r: r.id):
        session.merge(round_nominee_row(rnd))

    # Rivals (M5)
    for olds, news, rival_key in (
        (old.pools, new.pools, lambda p: (p.company_id, p.function)),
        (old.rival_effects, new.rival_effects, lambda e: e.id),
        (old.rival_moves, new.rival_moves, lambda m: m.id),
        (old.approaches, new.approaches, lambda a: a.id),
        (old.segment_shares, new.segment_shares, lambda s: (s.product_id, s.segment)),
        (old.free_agents, new.free_agents, lambda a: a.person_id),
    ):
        _write(session, olds, news, rival_key, rival_to_row)

    changed = (old.events, old.storylines, old.queued) != (new.events, new.storylines, new.queued)
    if changed and has_table(session, EventRow):
        # Storylines before the events that name them, events before their follow-ups.
        _write(session, old.storylines, new.storylines, lambda s: s.id, storyline_to_row)
        session.flush()
        _write(session, old.events, new.events, lambda e: e.id, event_to_row)
        session.flush()
        _write(session, old.queued, new.queued, lambda q: q.id, queued_to_row)
    if old.modifiers != new.modifiers and has_table(session, EventModifierRow):
        session.flush()  # after the events they name (M10b, 23.2)
        _write(session, old.modifiers, new.modifiers, lambda m: m.id, modifier_to_row)

    if old.relationships != new.relationships and has_table(session, RelationshipRow):
        _sync_relationships(session, old, new)
    _sync_m8(session, old, new)
    _sync_m10(session, old, new)
    _sync_geo(session, old, new)
    _sync_marketing(session, old, new)
    _sync_exec(session, old, new)
    _sync_pitches(session, old, new)
    sync_mna(session, old, new, has_table)  # M14 (0034)
    session.flush()
    sync_modes(session, old, new, has_table)  # M15b (0035)
    sync_founder(session, old, new, has_table)  # M24 (0037)
    sync_group(session, old, new, has_table)  # M16 (0039)
    sync_commodities(session, old, new, has_table)  # M17 (0041)
    sync_exploration(session, old, new, has_table)  # M18 (0041)
    _sync_facilities(session, old, new)
    _sync_hardware(session, old, new)
    _sync_public(session, old, new)
    _sync_research(session, old, new)
    _sync_press(session, old, new)
    session.flush()
    _sync_small(session, old, new)  # M15a (0036)
    if old.employments != new.employments and has_table(session, FormerStaffRow):
        session.flush()
        for row in former_rows(old, new):  # M7c: what the player knew when they left
            session.merge(row)

    if old.next_ids != new.next_ids:
        next_ids_to_meta(read_meta(session), new.next_ids)
    if (old.save_meta.game_state, old.save_meta.ended_turn) != (
        new.save_meta.game_state,
        new.save_meta.ended_turn,
    ):
        meta = read_meta(session)
        meta.game_state = new.save_meta.game_state
        meta.ended_turn = new.save_meta.ended_turn
    session.flush()


def _sync_m8(session: Session, old: GameState, new: GameState) -> None:
    """Divisions' services, products' divisions, exec-level searches and seats (M8)."""
    old_units = {u.id: u.services for u in old.units}
    old_products = {p.id: p.division_id for p in old.products}
    old_levels = {s.id: s.level for s in old.searches}
    rows: list[Any] = [
        UnitServicesRow(unit_id=u.id, services=u.services)
        for u in new.units
        if u.services is not None and old_units.get(u.id) != u.services
    ]
    rows += [
        ProductDivisionRow(product_id=p.id, division_id=p.division_id)
        for p in new.products
        if old_products.get(p.id) != p.division_id
    ]
    rows += [
        SearchLevelRow(search_id=s.id, level=s.level)
        for s in new.searches
        if s.level is not None and old_levels.get(s.id) != s.level
    ]
    rows += [
        ExecSeatRow(
            company_id=s.company_id, seat=s.seat, person_id=s.person_id, since_turn=s.since_turn
        )
        for s in _changed(old.exec_seats, new.exec_seats, lambda s: (s.company_id, s.seat))
    ]
    if not rows or not has_table(session, ExecSeatRow):
        return
    session.flush()
    for row in rows:
        session.merge(row)


def _sync_marketing(session: Session, old: GameState, new: GameState) -> None:
    """A product's marketing split is replaced whole when it changes (M10b, 23.5)."""
    if old.marketing_splits == new.marketing_splits or not has_table(session, MarketingSplitRow):
        return
    before: dict[int, list[MarketingSplit]] = {}
    after: dict[int, list[MarketingSplit]] = {}
    for m in old.marketing_splits:
        before.setdefault(m.product_id, []).append(m)
    for m in new.marketing_splits:
        after.setdefault(m.product_id, []).append(m)
    session.flush()
    for pid in sorted(set(before) | set(after)):
        if before.get(pid) == after.get(pid):
            continue
        session.execute(delete(MarketingSplitRow).where(MarketingSplitRow.product_id == pid))
        session.add_all(
            MarketingSplitRow(product_id=m.product_id, region=m.region, share_bp=m.share_bp)
            for m in after.get(pid, ())
        )


def _sync_geo(session: Session, old: GameState, new: GameState) -> None:
    """HQ, people's cities, offices, units' offices, searches' cities and regions (M9)."""
    old_people = {p.id: p.city for p in old.people}
    old_hq = {c.id: c.hq_city for c in old.companies}
    old_units = {u.id: u.office_id for u in old.units}
    old_cities = {s.id: s.city for s in old.searches}
    rows: list[Any] = [
        CompanyHqRow(company_id=c.id, city=c.hq_city)
        for c in new.companies
        if c.hq_city is not None and old_hq.get(c.id) != c.hq_city
    ]
    rows += [
        PersonCityRow(person_id=p.id, city=p.city)
        for p in new.people
        if p.city is not None and old_people.get(p.id) != p.city
    ]
    rows += [
        OfficeRow(
            id=o.id,
            company_id=o.company_id,
            city=o.city,
            seats=o.seats,
            opened_turn=o.opened_turn,
            status=o.status,
            closed_turn=o.closed_turn,
        )
        for o in _changed(old.offices, new.offices, lambda o: o.id)
    ]
    rows += [
        UnitOfficeRow(unit_id=u.id, office_id=u.office_id)
        for u in new.units
        if old_units.get(u.id) != u.office_id and (u.office_id is not None or u.id in old_units)
    ]
    old_moves = {c.person_id: c.relocate_to for c in old.candidates}
    rows += [
        CandidateRelocationRow(person_id=c.person_id, city=c.relocate_to)
        for c in new.candidates
        if c.relocate_to is not None and old_moves.get(c.person_id) != c.relocate_to
    ]
    rows += [
        SearchCityRow(search_id=s.id, city=s.city)
        for s in new.searches
        if s.city is not None and old_cities.get(s.id) != s.city
    ]
    markets_changed = bool(
        _changed(
            old.regional_markets, new.regional_markets, lambda m: (m.category, m.segment, m.region)
        )
    )
    rows += [
        ProductRegionRow(
            product_id=r.product_id,
            region=r.region,
            launched_turn=r.launched_turn,
            live_turn=r.live_turn,
        )
        for r in _changed(
            old.product_regions, new.product_regions, lambda r: (r.product_id, r.region)
        )
    ]
    segs = _changed(
        old.regional_segments, new.regional_segments, lambda s: (s.product_id, s.region, s.segment)
    )
    if not (rows or segs or markets_changed) or not has_table(session, RegionalSegmentRow):
        return
    session.flush()
    for row in rows:
        session.merge(row)
    # Every regional market grows every month: one bulk UPDATE, not a merge (a SELECT) per
    # row (M12b: six more categories made this most of a turn's write).
    _write(
        session,
        old.regional_markets,
        new.regional_markets,
        lambda m: (m.category, m.segment, m.region),
        lambda m: RegionalMarketRow(
            category=m.category, segment=m.segment, region=m.region, addressable=m.addressable
        ),
    )
    known = {(s.product_id, s.region, s.segment) for s in old.regional_segments}
    fresh = [s for s in segs if (s.product_id, s.region, s.segment) not in known]
    updates = [s for s in segs if (s.product_id, s.region, s.segment) in known]
    _insert(session, (_regional_segment_row(s) for s in fresh))
    _update_rows(
        session,
        RegionalSegmentRow,
        [
            {
                "product_id": s.product_id,
                "region": s.region,
                "segment": s.segment,
                "price_cents": s.price_cents,
                "customers": s.customers,
                "capacity_limited": s.capacity_limited,
            }
            for s in updates
        ],
    )


def _regional_segment_row(s: RegionalSegment) -> RegionalSegmentRow:
    return RegionalSegmentRow(
        product_id=s.product_id,
        region=s.region,
        segment=s.segment,
        price_cents=s.price_cents,
        customers=s.customers,
        capacity_limited=s.capacity_limited,
        added_turn=s.added_turn,
    )


# --- The founder in public (M14b, formulas.md 29; 0033) -------------------------------------

STATEMENT_MEMORY = 24  # months of rival CEOs' statements the state holds (29.4)
# months of departures the state holds: Replace's window (balance.yaml recruit.replace_window)
DEPARTURE_MEMORY = 3


def _moment_live(m: PressMoment, turn: int) -> bool:
    """Pending or queued, or raised within the last PRESS_MEMORY months (press.moments)."""
    return m.status in ("pending", "queued") or m.turn > turn - PRESS_MEMORY


def _causes(raw: Any) -> tuple[tuple[int, float, str], ...]:
    return tuple((int(c[0]), float(c[1]), str(c[2])) for c in raw)


def moment_from_row(r: Any) -> PressMoment:
    return PressMoment(
        id=r.id,
        company_id=r.company_id,
        trigger=r.trigger,
        turn=r.turn,
        status=r.status,
        event_turn=r.event_turn,
        product_id=r.product_id,
        rival_id=r.rival_id,
        facts=tuple((str(k), v) for k, v in r.facts),
        tone=r.tone,
        answered_turn=r.answered_turn,
        share_bp=r.share_bp,
        backfired=bool(r.backfired),
    )


def moment_to_row(m: PressMoment) -> PressMomentRow:
    fields = asdict(m)
    fields["facts"] = [[k, v] for k, v in m.facts]
    return PressMomentRow(**fields)


def promise_from_row(r: Any) -> Promise:
    return Promise(
        id=r.id,
        company_id=r.company_id,
        kind=r.kind,
        made_turn=r.made_turn,
        deadline_turn=r.deadline_turn,
        moment_id=r.moment_id,
        product_id=r.product_id,
        rival_product_id=r.rival_product_id,
        domain=r.domain,
        level=r.level,
        baseline=r.baseline,
        prices=tuple((str(k), int(v)) for k, v in r.prices),
        ambition=float(r.ambition),
        audience=float(r.audience),
        status=r.status,
        resolved_turn=r.resolved_turn,
        reminder_turn=r.reminder_turn,
    )


def promise_to_row(p: Promise) -> PromiseRow:
    fields = asdict(p)
    fields["prices"] = [[k, v] for k, v in p.prices]
    return PromiseRow(**fields)


def _load_press(session: Session, state: GameState) -> GameState:
    """Press moments pending, queued or raised in the last PRESS_MEMORY months, every promise,
    credibility, feuds, the last STATEMENT_MEMORY months of rival CEOs' statements, departures
    of the last DEPARTURE_MEMORY months, and the
    M14b hiring fields of the loaded searches and plans (M14b, 0033)."""
    if not has_table(session, PressMomentRow):
        return state
    turn = state.turn

    def next_id(model: Any) -> int:
        return int(session.scalar(select(func.max(model.id))) or 0) + 1

    interests = {r.search_id: r.interest for r in session.scalars(select(SearchInterestRow))}
    details = {r.plan_id: r for r in session.scalars(select(HiringPlanDetailRow))}

    def plan(p: Any) -> Any:
        d = details.get(p.id)
        if d is None:
            return p
        return replace(p, interest=d.interest, replace_of=d.replace_of, level=d.level)

    return replace(
        state,
        searches=tuple(replace(s, interest=interests.get(s.id)) for s in state.searches),
        plans=tuple(plan(p) for p in state.plans),
        press_moments=tuple(
            moment_from_row(r)
            for r in session.scalars(
                select(PressMomentRow)
                .where(
                    PressMomentRow.status.in_(("pending", "queued"))
                    | (PressMomentRow.turn > turn - PRESS_MEMORY)
                )
                .order_by(PressMomentRow.id)
            )
        ),
        promises=tuple(
            promise_from_row(r) for r in session.scalars(select(PromiseRow).order_by(PromiseRow.id))
        ),
        credibility=tuple(
            Credibility(
                r.company_id,
                float(r.value),
                _causes(r.history),
                r.fired_turn,
                r.fired,
                r.staff_start,
            )
            for r in session.scalars(select(CredibilityRow).order_by(CredibilityRow.company_id))
        ),
        feuds=tuple(
            Feud(r.company_id, r.rival_id, float(r.score), _causes(r.causes), r.rivalry_turn)
            for r in session.scalars(select(FeudRow).order_by(FeudRow.company_id, FeudRow.rival_id))
        ),
        statements=tuple(
            Statement(
                r.id, r.rival_id, r.person_id, r.turn, cast(Any, r.kind), r.text, r.product_id
            )
            for r in session.scalars(
                select(StatementRow)
                .where(StatementRow.turn > turn - STATEMENT_MEMORY)
                .order_by(StatementRow.id)
            )
        ),
        departures=tuple(
            Departure(
                r.person_id, r.company_id, r.role, r.level, r.unit_id, r.reason, r.turn, r.name
            )
            for r in session.scalars(
                select(DepartureRow)
                .where(DepartureRow.turn >= turn - DEPARTURE_MEMORY)
                .order_by(DepartureRow.person_id)
            )
        ),
        next_ids=replace(
            state.next_ids,
            press_moment=next_id(PressMomentRow),
            promise=next_id(PromiseRow),
            statement=next_id(StatementRow),
        ),
    )


def _sync_press(session: Session, old: GameState, new: GameState) -> None:
    """Press moments, promises, credibility, feuds, statements, departures, and the M14b fields of
    searches and plans (M14b). Runs after searches and plans are written: their side rows
    reference them."""
    if not has_table(session, PressMomentRow):
        return
    session.flush()
    for m in _changed(old.press_moments, new.press_moments, lambda m: m.id):
        session.merge(moment_to_row(m))
    for p in _changed(old.promises, new.promises, lambda p: p.id):
        session.merge(promise_to_row(p))
    for c in _changed(old.credibility, new.credibility, lambda c: c.company_id):
        session.merge(
            CredibilityRow(
                company_id=c.company_id,
                value=c.value,
                history=[list(h) for h in c.history],
                fired_turn=c.fired_turn,
                fired=c.fired,
                staff_start=c.staff_start,
            )
        )
    for f in _changed(old.feuds, new.feuds, lambda f: (f.company_id, f.rival_id)):
        session.merge(
            FeudRow(
                company_id=f.company_id,
                rival_id=f.rival_id,
                score=f.score,
                causes=[list(h) for h in f.causes],
                rivalry_turn=f.rivalry_turn,
            )
        )
    for s in _changed(old.statements, new.statements, lambda s: s.id):
        session.merge(StatementRow(**asdict(s)))
    for d in _changed(old.departures, new.departures, lambda d: d.person_id):
        session.merge(DepartureRow(**asdict(d)))
    old_interests = {s.id: s.interest for s in old.searches}
    for search in new.searches:
        if search.interest is not None and old_interests.get(search.id) != search.interest:
            session.merge(SearchInterestRow(search_id=search.id, interest=search.interest))
    old_details = {p.id: (p.interest, p.replace_of, p.level) for p in old.plans}
    for plan in new.plans:
        detail = (plan.interest, plan.replace_of, plan.level)
        if old_details.get(plan.id, (None, None, None)) != detail:
            session.merge(
                HiringPlanDetailRow(
                    plan_id=plan.id,
                    interest=plan.interest,
                    replace_of=plan.replace_of,
                    level=plan.level,
                )
            )


# --- The last state written, per save (M6 sub-task 0) -----------------------------------------


def live_view(state: GameState) -> GameState:
    """What `load_state` would return after `state` was written: the same live set, by the
    same rules (golden seed 1 runs with TST_STATE_CACHE_CHECK=1, which compares them)."""
    staff = tuple(e for e in state.employments if e.status in STAFF_STATUSES)
    candidates = tuple(c for c in state.candidates if c.status == "open")
    offers = tuple(o for o in state.offers if o.status == "pending")
    plans = tuple(p for p in state.plans if p.status != "closed")
    free_agents = tuple(a for a in state.free_agents if a.status == "available")
    live = (
        {e.person_id for e in staff}
        | {c.person_id for c in candidates}
        | {o.actor_id for o in offers}
        | {p.owner_id for p in plans}
        | {s.person_id for s in state.seats if s.person_id is not None}
        | {a.person_id for a in free_agents}
    )
    products = tuple(p for p in state.products if p.status != "retired")
    product_ids = {p.id for p in products}
    turn = state.turn
    return replace(
        state,
        people=tuple(p for p in state.people if p.id in live),
        employments=staff,
        reveals=tuple(r for r in state.reveals if r.person_id in live and r.attributes),
        searches=tuple(s for s in state.searches if s.status == "open"),
        candidates=candidates,
        offers=offers,
        units=tuple(u for u in state.units if u.status == "active"),
        plans=plans,
        products=products,
        product_segments=tuple(s for s in state.product_segments if s.product_id in product_ids),
        person_states=tuple(p for p in state.person_states if p.person_id in live),
        rival_effects=tuple(e for e in state.rival_effects if e.end_turn >= turn - 1),
        rival_moves=tuple(m for m in state.rival_moves if m.turn >= turn - RIVAL_MOVE_MEMORY),
        approaches=tuple(a for a in state.approaches if a.status in ("pending", "accepted")),
        segment_shares=tuple(s for s in state.segment_shares if s.product_id in product_ids),
        offices=tuple(o for o in state.offices if o.status == "open"),
        product_regions=tuple(r for r in state.product_regions if r.product_id in product_ids),
        marketing_splits=tuple(m for m in state.marketing_splits if m.product_id in product_ids),
        exec_decisions=tuple(d for d in state.exec_decisions if d.turn > turn - EXEC_MEMORY),
        proposals=tuple(
            p for p in state.proposals if p.status == "pending" or p.turn > turn - EXEC_MEMORY
        ),
        regional_segments=tuple(s for s in state.regional_segments if s.product_id in product_ids),
        research_projects=tuple(
            p
            for p in state.research_projects
            if p.is_active or (p.end_turn is not None and p.end_turn >= turn - RESEARCH_MEMORY)
        ),
        free_agents=free_agents,
        events=tuple(
            e
            for e in state.events
            if e.turn > turn - EVENT_MEMORY or e.status in ("pending", "open")
        ),
        storylines=tuple(s for s in state.storylines if s.status == "active"),
        queued=tuple(q for q in state.queued if not q.done),
        modifiers=tuple(m for m in state.modifiers if m.end_turn > state.turn),
        facilities=tuple(f for f in state.facilities if f.status != "closed"),  # M12a
        contracts=tuple(
            c
            for c in state.contracts
            if c.status == "active" or c.end_turn >= turn - FACILITY_MEMORY
        ),
        outages=tuple(o for o in state.outages if o.turn > turn - FACILITY_MEMORY),
        share_months=tuple(m for m in state.share_months if m.turn > turn - SHARE_HISTORY),  # M13
        ceos=tuple(c for c in state.ceos if _ceo_live(c, turn)),
        ceo_decisions=tuple(d for d in state.ceo_decisions if d.turn > turn - CEO_MEMORY),
        press_moments=tuple(m for m in state.press_moments if _moment_live(m, turn)),  # M14b
        statements=tuple(s for s in state.statements if s.turn > turn - STATEMENT_MEMORY),
        departures=tuple(d for d in state.departures if d.turn >= turn - DEPARTURE_MEMORY),
    )
