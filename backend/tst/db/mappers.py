"""Convert between ORM rows and sim dataclasses. The sim never sees ORM objects."""

from __future__ import annotations

from dataclasses import asdict, fields
from typing import Any, cast

from tst.db.models import (
    Base,
    BoardSeatHistoryRow,
    BoardSeatRow,
    CandidateRow,
    CapTableEntryRow,
    CompanyRow,
    DecisionLogRow,
    EmploymentRow,
    EventModifierRow,
    EventQueueRow,
    EventRow,
    FreeAgentRow,
    FundingRoundRow,
    HiringPlanRow,
    LedgerEntryRow,
    LedgerLineRow,
    LoanRow,
    MarketSegmentRow,
    OfferRow,
    OptionGrantRow,
    OrgUnitRow,
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
    PoachApproachRow,
    ProductMonthRow,
    ProductRow,
    ProductSegmentRow,
    RivalEffectRow,
    RivalMoveRow,
    RoundNomineeRow,
    SafeRow,
    SaveMetaRow,
    SearchRow,
    SegmentShareRow,
    StorylineRow,
    TermSheetRow,
    TurnLogRow,
    TurnSnapshotRow,
    WorkforcePoolRow,
)
from tst.sim.decisions import Decisions
from tst.sim.events.models import (
    Effect,
    EventChoice,
    GameEvent,
    Modifier,
    QueuedEvent,
    Storyline,
)
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
from tst.sim.hiring.models import (
    Candidate,
    CandidateStatus,
    Channel,
    NextIds,
    Offer,
    OfferStatus,
    PersonState,
    Search,
    SearchStatus,
)
from tst.sim.ledger import LedgerEntry, LedgerLine
from tst.sim.log import LogItem
from tst.sim.org.models import (
    HiringPlan,
    OrgUnit,
    PlanActivity,
    PlanChannel,
    PlanFocus,
    PlanStatus,
    UnitKind,
    UnitStatus,
    WorkPolicy,
)
from tst.sim.people.models import (
    PA_KEY,
    Employment,
    EmploymentStatus,
    EndReason,
    HiddenTraits,
    Person,
    Personality,
    RevealRecord,
    RevealState,
    Skills,
)
from tst.sim.products.models import (
    MarketSegment,
    Product,
    ProductMonth,
    ProductSegment,
    ProductStatus,
)
from tst.sim.rivals.models import (
    FreeAgent,
    PoachApproach,
    RivalEffect,
    RivalMove,
    SegmentShare,
    WorkforcePool,
)
from tst.sim.snapshot import CompanySnapshot, TurnSnapshot
from tst.sim.state import CompanyState, GameState, SaveMeta


def company_to_state(row: CompanyRow) -> CompanyState:
    return CompanyState(
        id=row.id,
        name=row.name,
        is_player=row.is_player,
        stage=row.stage,
        founded_turn=row.founded_turn,
        mission=tuple(row.mission or ()),
        work_policy=cast(WorkPolicy, row.work_policy),
        root_product_id=row.root_product_id,
        arr_milestone_cents=row.arr_milestone_cents,
        mrr_history=tuple(row.mrr_history or ()),
        insolvent_months=row.insolvent_months,
        stage_history=tuple((int(s), int(t)) for s, t in row.stage_history or ()),
        personality=row.personality,
        builder_skill=row.builder_skill,
        target_margin_bp=row.target_margin_bp,
        is_startup=row.is_startup,
        failed_turn=row.failed_turn,
        last_raise_turn=row.last_raise_turn,
    )


def company_to_row(company: CompanyState) -> CompanyRow:
    return CompanyRow(
        id=company.id,
        name=company.name,
        is_player=company.is_player,
        stage=company.stage,
        founded_turn=company.founded_turn,
        mission=list(company.mission),
        work_policy=company.work_policy,
        root_product_id=company.root_product_id,
        arr_milestone_cents=company.arr_milestone_cents,
        mrr_history=list(company.mrr_history),
        insolvent_months=company.insolvent_months,
        stage_history=[list(p) for p in company.stage_history],
        personality=company.personality,
        builder_skill=company.builder_skill,
        target_margin_bp=company.target_margin_bp,
        is_startup=company.is_startup,
        failed_turn=company.failed_turn,
        last_raise_turn=company.last_raise_turn,
    )


def update_company_row(row: CompanyRow, company: CompanyState) -> None:
    row.name = company.name
    row.is_player = company.is_player
    row.stage = company.stage
    row.founded_turn = company.founded_turn
    row.mission = list(company.mission)
    row.work_policy = company.work_policy
    row.root_product_id = company.root_product_id
    row.arr_milestone_cents = company.arr_milestone_cents
    row.mrr_history = list(company.mrr_history)
    row.insolvent_months = company.insolvent_months
    row.stage_history = [list(p) for p in company.stage_history]
    row.personality = company.personality
    row.builder_skill = company.builder_skill
    row.target_margin_bp = company.target_margin_bp
    row.is_startup = company.is_startup
    row.failed_turn = company.failed_turn
    row.last_raise_turn = company.last_raise_turn


def game_state_from_rows(
    meta: SaveMetaRow,
    companies: list[CompanyRow],
    people: tuple[Person, ...] = (),
    employments: tuple[Employment, ...] = (),
    reveals: tuple[RevealState, ...] = (),
) -> GameState:
    return GameState(
        save_meta=SaveMeta(
            name=meta.name,
            master_seed=meta.master_seed,
            scenario_id=meta.scenario_id,
            difficulty=meta.difficulty,
            game_state=cast(GameOutcome, meta.game_state),
            ended_turn=meta.ended_turn,
        ),
        turn=meta.current_turn,
        companies=tuple(company_to_state(r) for r in sorted(companies, key=lambda r: r.id)),
        people=tuple(sorted(people, key=lambda p: p.id)),
        employments=tuple(sorted(employments, key=lambda e: e.id)),
        reveals=tuple(sorted(reveals, key=lambda r: (r.observer_company_id, r.person_id))),
    )


def entry_to_row(entry: LedgerEntry) -> LedgerEntryRow:
    return LedgerEntryRow(
        turn=entry.turn,
        company_id=entry.company_id,
        memo=entry.memo,
        lines=[_line_row(ln) for ln in entry.lines],
    )


def _line_row(line: LedgerLine) -> LedgerLineRow:
    """A line's row; division_id is set only when there is one, so migration 0013 can still
    post lines on a save without the column (M8)."""
    if line.division_id is None:
        return LedgerLineRow(account_code=line.account, amount_cents=line.amount)
    return LedgerLineRow(
        account_code=line.account, amount_cents=line.amount, division_id=line.division_id
    )


def entry_from_row(row: LedgerEntryRow) -> LedgerEntry:
    return LedgerEntry(
        turn=row.turn,
        company_id=row.company_id,
        memo=row.memo,
        lines=tuple(LedgerLine(ln.account_code, ln.amount_cents) for ln in row.lines),
    )


def snapshot_to_rows(snapshot: TurnSnapshot) -> list[TurnSnapshotRow]:
    return [
        TurnSnapshotRow(turn=snapshot.turn, company_id=s.company_id, kpis=s.kpis())
        for s in snapshot.companies
    ]


def company_snapshot_from_row(row: TurnSnapshotRow) -> CompanySnapshot:
    kpis: dict[str, Any] = row.kpis
    return CompanySnapshot(
        company_id=row.company_id,
        cash_cents=int(kpis["cash_cents"]),
        monthly_burn_cents=int(kpis["monthly_burn_cents"]),
        headcount=int(kpis["headcount"]),
        payroll_cents=int(kpis.get("payroll_cents", 0)),
        avg_morale=kpis.get("avg_morale"),
        mrr_cents=int(kpis.get("mrr_cents", 0)),
        arr_cents=int(kpis.get("arr_cents", 0)),
        founder_bp=int(kpis.get("founder_bp", 0)),
        board_confidence=kpis.get("board_confidence"),
    )


def log_item_to_row(item: LogItem) -> TurnLogRow:
    return TurnLogRow(
        turn=item.turn, company_id=item.company_id, kind=item.kind, message=item.message
    )


def decisions_to_row(turn: int, company_id: int, decisions: Decisions) -> DecisionLogRow:
    return DecisionLogRow(
        turn=turn, company_id=company_id, kind="turn_decisions", payload=asdict(decisions), seq=None
    )


# --- People (M1a) ---------------------------------------------------------------------------


def person_to_rows(person: Person) -> list[Base]:
    """The person row and its attribute rows. Positions keep data-file order (ADR-0013)."""
    rows: list[Base] = [
        PersonRow(
            id=person.id,
            first_name=person.first_name,
            last_name=person.last_name,
            region=person.region,
            birth_turn=person.birth_turn,
            role=person.role,
            level=person.level,
            work_style=person.work_style,
            salary_expectation_cents=person.salary_expectation_cents,
            is_founder=person.is_founder,
        )
    ]
    pid = person.id
    rows += [
        PersonSkillRow(person_id=pid, skill=k, position=i, value=v)
        for i, (k, v) in enumerate(person.skills.items)
    ]
    rows += [
        PersonPersonalityRow(person_id=pid, trait=k, position=i, value=v)
        for i, (k, v) in enumerate(person.personality.items)
    ]
    hidden = [*person.hidden.items, (PA_KEY, person.potential_ability)]
    rows += [
        PersonHiddenRow(person_id=pid, trait=k, position=i, value=v)
        for i, (k, v) in enumerate(hidden)
    ]
    rows += [
        PersonInterestRow(person_id=pid, interest=k, position=i)
        for i, k in enumerate(person.interests)
    ]
    rows += [PersonTagRow(person_id=pid, tag=k, position=i) for i, k in enumerate(person.tags)]
    return rows


def person_from_rows(
    row: Any,
    skills: list[tuple[str, float]],
    personality: list[tuple[str, float]],
    hidden: list[tuple[str, float]],
    interests: list[str],
    tags: list[str],
) -> Person:
    """A person from its row and its child rows as (key, value) pairs already in position
    order (`state_io.load_people` orders them in SQL; M12b, speed)."""
    pa = next(v for k, v in hidden if k == PA_KEY)
    return Person(
        id=row.id,
        first_name=row.first_name,
        last_name=row.last_name,
        region=row.region,
        birth_turn=row.birth_turn,
        role=row.role,
        level=row.level,
        skills=Skills(tuple(skills)),
        personality=Personality(tuple(personality)),
        hidden=HiddenTraits(tuple((k, v) for k, v in hidden if k != PA_KEY)),
        potential_ability=pa,
        interests=tuple(interests),
        work_style=row.work_style,
        tags=tuple(tags),
        salary_expectation_cents=row.salary_expectation_cents,
        is_founder=row.is_founder,
    )


def employment_to_row(employment: Employment) -> EmploymentRow:
    return EmploymentRow(
        id=employment.id,
        person_id=employment.person_id,
        company_id=employment.company_id,
        role=employment.role,
        level=employment.level,
        salary_cents=employment.salary_cents,
        equity_bp=employment.equity_bp,
        start_turn=employment.start_turn,
        end_turn=employment.end_turn,
        status=employment.status,
        end_reason=employment.end_reason,
        unit_id=employment.unit_id,
        last_raise_turn=employment.last_raise_turn,
    )


def employment_from_row(row: EmploymentRow) -> Employment:
    return Employment(
        id=row.id,
        person_id=row.person_id,
        company_id=row.company_id,
        role=row.role,
        level=row.level,
        salary_cents=row.salary_cents,
        equity_bp=row.equity_bp,
        start_turn=row.start_turn,
        end_turn=row.end_turn,
        status=cast(EmploymentStatus, row.status),
        end_reason=cast(EndReason | None, row.end_reason),
        unit_id=row.unit_id,
        last_raise_turn=row.last_raise_turn,
    )


def reveal_to_rows(reveal: RevealState) -> list[Base]:
    key = {"person_id": reveal.person_id, "observer_company_id": reveal.observer_company_id}
    rows: list[Base] = [
        PersonRevealRow(
            **key,
            attribute=attr,
            position=i,
            hw=rec.hw,
            center_offset=rec.offset,
            last_updated_turn=rec.last_updated_turn,
        )
        for i, (attr, rec) in enumerate(reveal.attributes)
    ]
    if reveal.profile_revealed_turn is not None:
        rows.append(PersonProfileRevealRow(**key, revealed_turn=reveal.profile_revealed_turn))
    rows += [
        PersonTagRevealRow(**key, tag=tag, revealed_turn=turn) for tag, turn in reveal.revealed_tags
    ]
    return rows


def reveal_from_rows(
    observer_company_id: int,
    person_id: int,
    records: list[PersonRevealRow],
    profile: PersonProfileRevealRow | None,
    tags: list[PersonTagRevealRow],
) -> RevealState:
    return RevealState(
        observer_company_id=observer_company_id,
        person_id=person_id,
        attributes=tuple(
            (r.attribute, RevealRecord(r.hw, r.center_offset, r.last_updated_turn))
            for r in sorted(records, key=lambda r: r.position)
        ),
        profile_revealed_turn=None if profile is None else profile.revealed_turn,
        revealed_tags=tuple(
            (t.tag, t.revealed_turn) for t in sorted(tags, key=lambda t: (t.revealed_turn, t.tag))
        ),
    )


# --- Hiring (M1b) ---------------------------------------------------------------------------


def search_to_row(search: Search) -> SearchRow:
    return SearchRow(
        id=search.id,
        company_id=search.company_id,
        role=search.role,
        channel=search.channel,
        actor_id=search.actor_id,
        opened_turn=search.opened_turn,
        status=search.status,
        closed_turn=search.closed_turn,
        plan_id=search.plan_id,
        rival_id=search.rival_id,
    )


def search_from_row(row: SearchRow) -> Search:
    return Search(
        id=row.id,
        company_id=row.company_id,
        role=row.role,
        channel=cast(Channel, row.channel),
        actor_id=row.actor_id,
        opened_turn=row.opened_turn,
        status=cast(SearchStatus, row.status),
        closed_turn=row.closed_turn,
        plan_id=row.plan_id,
        rival_id=row.rival_id,
    )


def candidate_to_row(candidate: Candidate) -> CandidateRow:
    return CandidateRow(
        person_id=candidate.person_id,
        company_id=candidate.company_id,
        search_id=candidate.search_id,
        channel=candidate.channel,
        created_turn=candidate.created_turn,
        expires_turn=candidate.expires_turn,
        status=candidate.status,
        resolved_turn=candidate.resolved_turn,
        interviewed_turn=candidate.interviewed_turn,
    )


def candidate_from_row(row: CandidateRow) -> Candidate:
    return Candidate(
        person_id=row.person_id,
        company_id=row.company_id,
        search_id=row.search_id,
        channel=cast(Channel, row.channel),
        created_turn=row.created_turn,
        expires_turn=row.expires_turn,
        status=cast(CandidateStatus, row.status),
        resolved_turn=row.resolved_turn,
        interviewed_turn=row.interviewed_turn,
    )


def offer_to_row(offer: Offer) -> OfferRow:
    return OfferRow(
        id=offer.id,
        company_id=offer.company_id,
        candidate_id=offer.candidate_id,
        actor_id=offer.actor_id,
        salary_cents=offer.salary_cents,
        equity_bp=offer.equity_bp,
        made_turn=offer.made_turn,
        status=offer.status,
        resolved_turn=offer.resolved_turn,
        plan_id=offer.plan_id,
        unit_id=offer.unit_id,
    )


def offer_from_row(row: OfferRow) -> Offer:
    return Offer(
        id=row.id,
        company_id=row.company_id,
        candidate_id=row.candidate_id,
        actor_id=row.actor_id,
        salary_cents=row.salary_cents,
        equity_bp=row.equity_bp,
        made_turn=row.made_turn,
        status=cast(OfferStatus, row.status),
        resolved_turn=row.resolved_turn,
        plan_id=row.plan_id,
        unit_id=row.unit_id,
    )


def person_state_to_row(ps: PersonState) -> PersonStateRow:
    return PersonStateRow(
        person_id=ps.person_id,
        energy=None if ps.energy is None else float(ps.energy),
        stress=ps.stress,
        morale=ps.morale,
    )


def person_state_from_row(row: PersonStateRow) -> PersonState:
    return PersonState(
        person_id=row.person_id,
        energy=None if row.energy is None else int(row.energy),
        stress=row.stress,
        morale=row.morale,
    )


def next_ids_from_meta(meta: SaveMetaRow) -> NextIds:
    return NextIds(
        person=meta.next_person_id,
        search=meta.next_search_id,
        offer=meta.next_offer_id,
        employment=meta.next_employment_id,
        unit=meta.next_unit_id,
        plan=meta.next_plan_id,
        product=meta.next_product_id,
        cap_entry=meta.next_cap_entry_id,
        grant=meta.next_grant_id,
        safe=meta.next_safe_id,
        round=meta.next_round_id,
        term_sheet=meta.next_term_sheet_id,
        seat=meta.next_seat_id,
        rival_effect=meta.next_rival_effect_id,
        rival_move=meta.next_rival_move_id,
        approach=meta.next_approach_id,
        rival_person=meta.next_rival_person_id,
        rival_employment=meta.next_rival_employment_id,
    )


def next_ids_to_meta(meta: SaveMetaRow, ids: NextIds) -> None:
    meta.next_person_id = ids.person
    meta.next_search_id = ids.search
    meta.next_offer_id = ids.offer
    meta.next_employment_id = ids.employment
    meta.next_unit_id = ids.unit
    meta.next_plan_id = ids.plan
    meta.next_product_id = ids.product
    meta.next_cap_entry_id = ids.cap_entry
    meta.next_grant_id = ids.grant
    meta.next_safe_id = ids.safe
    meta.next_round_id = ids.round
    meta.next_term_sheet_id = ids.term_sheet
    meta.next_seat_id = ids.seat
    meta.next_rival_effect_id = ids.rival_effect
    meta.next_rival_move_id = ids.rival_move
    meta.next_approach_id = ids.approach
    meta.next_rival_person_id = ids.rival_person
    meta.next_rival_employment_id = ids.rival_employment


# --- Organization (M2a) ---------------------------------------------------------------------


def unit_to_row(unit: OrgUnit) -> OrgUnitRow:
    return OrgUnitRow(
        id=unit.id,
        company_id=unit.company_id,
        kind=unit.kind,
        name=unit.name,
        parent_id=unit.parent_id,
        leader_id=unit.leader_id,
        policy=unit.policy,
        created_turn=unit.created_turn,
        status=unit.status,
        dissolved_turn=unit.dissolved_turn,
        product_id=unit.product_id,
    )


def unit_from_row(row: OrgUnitRow) -> OrgUnit:
    return OrgUnit(
        id=row.id,
        company_id=row.company_id,
        kind=cast(UnitKind, row.kind),
        name=row.name,
        parent_id=row.parent_id,
        leader_id=row.leader_id,
        policy=cast(WorkPolicy | None, row.policy),
        created_turn=row.created_turn,
        status=cast(UnitStatus, row.status),
        dissolved_turn=row.dissolved_turn,
        product_id=row.product_id,
    )


def plan_to_row(plan: HiringPlan) -> HiringPlanRow:
    return HiringPlanRow(
        id=plan.id,
        company_id=plan.company_id,
        owner_id=plan.owner_id,
        unit_id=plan.unit_id,
        role=plan.role,
        target=plan.target,
        channel=plan.channel,
        ratio_bp=plan.ratio_bp,
        equity_bp=plan.equity_bp,
        created_turn=plan.created_turn,
        status=plan.status,
        hired=plan.hired,
        closed_turn=plan.closed_turn,
        last_activity=None if plan.last_activity is None else asdict(plan.last_activity),
        focus=plan.focus,
    )


def plan_from_row(row: HiringPlanRow) -> HiringPlan:
    activity = row.last_activity
    return HiringPlan(
        id=row.id,
        company_id=row.company_id,
        owner_id=row.owner_id,
        unit_id=row.unit_id,
        role=row.role,
        target=row.target,
        channel=cast(PlanChannel, row.channel),
        ratio_bp=row.ratio_bp,
        equity_bp=row.equity_bp,
        created_turn=row.created_turn,
        status=cast(PlanStatus, row.status),
        hired=row.hired,
        closed_turn=row.closed_turn,
        last_activity=None if activity is None else PlanActivity(**activity),
        focus=cast(PlanFocus, row.focus),
    )


# --- Products and markets (M3a) -------------------------------------------------------------


def product_to_row(product: Product) -> ProductRow:
    return ProductRow(
        id=product.id,
        company_id=product.company_id,
        category=product.category,
        name=product.name,
        status=product.status,
        quality=product.quality,
        feature_points=product.feature_points,
        brand=product.brand,
        marketing_budget_cents=product.marketing_budget_cents,
        created_turn=product.created_turn,
        launched_turn=product.launched_turn,
        sunset_turn=product.sunset_turn,
        retired_turn=product.retired_turn,
        held_feature=product.held_feature,
        first_customer_turn=product.first_customer_turn,
        rotting=product.rotting,
    )


def product_from_row(row: ProductRow) -> Product:
    return Product(
        id=row.id,
        company_id=row.company_id,
        category=row.category,
        name=row.name,
        status=cast(ProductStatus, row.status),
        quality=row.quality,
        feature_points=row.feature_points,
        brand=row.brand,
        marketing_budget_cents=row.marketing_budget_cents,
        created_turn=row.created_turn,
        launched_turn=row.launched_turn,
        sunset_turn=row.sunset_turn,
        retired_turn=row.retired_turn,
        held_feature=row.held_feature,
        first_customer_turn=row.first_customer_turn,
        rotting=row.rotting,
    )


def product_segment_to_row(seg: ProductSegment) -> ProductSegmentRow:
    return ProductSegmentRow(
        product_id=seg.product_id,
        segment=seg.segment,
        price_cents=seg.price_cents,
        customers=seg.customers,
        capacity_limited=seg.capacity_limited,
        added_turn=seg.added_turn,
    )


def product_segment_from_row(row: ProductSegmentRow) -> ProductSegment:
    return ProductSegment(
        product_id=row.product_id,
        segment=row.segment,
        price_cents=row.price_cents,
        customers=row.customers,
        capacity_limited=row.capacity_limited,
        added_turn=row.added_turn,
    )


def market_to_row(market: MarketSegment) -> MarketSegmentRow:
    return MarketSegmentRow(
        category=market.category, segment=market.segment, addressable=market.addressable
    )


def market_from_row(row: MarketSegmentRow) -> MarketSegment:
    return MarketSegment(category=row.category, segment=row.segment, addressable=row.addressable)


def product_month_to_row(month: ProductMonth) -> ProductMonthRow:
    return ProductMonthRow(**asdict(month))


def product_month_from_row(row: ProductMonthRow) -> ProductMonth:
    return ProductMonth(
        turn=row.turn,
        product_id=row.product_id,
        segment=row.segment,
        quality=row.quality,
        feature_score=row.feature_score,
        brand=row.brand,
        appeal=row.appeal,
        customers=row.customers,
        new=row.new,
        churned=row.churned,
        revenue_cents=row.revenue_cents,
    )


# --- Finance (M4): column names match the dataclass fields ------------------------------------

FINANCE_ROWS: dict[type[Any], type[Any]] = {
    CapEntry: CapTableEntryRow,
    OptionGrant: OptionGrantRow,
    Safe: SafeRow,
    FundingRound: FundingRoundRow,
    TermSheet: TermSheetRow,
    BoardSeat: BoardSeatRow,
    Loan: LoanRow,  # M10
}


def finance_to_row(item: Any) -> Any:
    """Any finance dataclass as its row (a seat's history goes to seat_history_row)."""
    values = asdict(item)
    if isinstance(item, BoardSeat):
        del values["history"]
    if isinstance(item, FundingRound):
        del values["nominee_id"]  # in round_nominee (M4c)
    return FINANCE_ROWS[type(item)](**values)


def finance_from_row[T](cls: type[T], row: Any, **extra: Any) -> T:
    """A finance dataclass from its row (status-like strings are trusted: the sim wrote them).
    `extra` fills fields stored elsewhere (a seat's history)."""
    names = [f.name for f in fields(cls) if f.name not in extra]  # type: ignore[arg-type]
    return cls(**{n: getattr(row, n) for n in names}, **extra)


def round_nominee_row(rnd: FundingRound) -> RoundNomineeRow:
    return RoundNomineeRow(round_id=rnd.id, person_id=rnd.nominee_id)


def seat_history_row(seat: BoardSeat) -> BoardSeatHistoryRow:
    return BoardSeatHistoryRow(seat_id=seat.id, history=list(seat.history))


# --- Rivals (M5) ----------------------------------------------------------------------------

RIVAL_ROWS: dict[type, type] = {
    WorkforcePool: WorkforcePoolRow,
    RivalEffect: RivalEffectRow,
    RivalMove: RivalMoveRow,
    PoachApproach: PoachApproachRow,
    SegmentShare: SegmentShareRow,
    FreeAgent: FreeAgentRow,
}


def rival_to_row(item: Any) -> Any:
    """Any rival dataclass as its row."""
    values = asdict(item)
    if isinstance(item, SegmentShare):
        values["history"] = list(item.history)
    return RIVAL_ROWS[type(item)](**values)


def rival_from_row[T](cls: type[T], row: Any) -> T:
    """A rival dataclass from its row (kinds and statuses are trusted: the sim wrote them)."""
    values = {f.name: getattr(row, f.name) for f in fields(cls)}  # type: ignore[arg-type]
    if cls is SegmentShare:
        values["history"] = tuple(float(v) for v in values["history"] or ())
    return cls(**values)


# --- Events (M6) ------------------------------------------------------------------------------


def event_to_row(event: GameEvent) -> EventRow:
    values = asdict(event)
    values["person_ids"] = list(event.person_ids)
    values["choices"] = [
        {
            "key": c.key,
            "label": c.label,
            "effects": [_effect_json(e) for e in c.effects],
            **({"do_nothing": True} if c.do_nothing else {}),
        }
        for c in event.choices
    ]
    return EventRow(**values)


def event_from_row(row: EventRow) -> GameEvent:
    values = {f.name: getattr(row, f.name) for f in fields(GameEvent)}
    values["person_ids"] = tuple(row.person_ids or ())
    values["choices"] = tuple(
        EventChoice(
            c["key"],
            c["label"],
            tuple(
                Effect(
                    e["type"],
                    e["target"],
                    float(e["value"]),
                    str(e.get("stat", "")),
                    int(e.get("months", 0)),
                )
                for e in c.get("effects", ())
            ),
            bool(c.get("do_nothing", False)),
        )
        for c in row.choices or ()
    )
    return GameEvent(**values)


def _effect_json(e: Effect) -> dict[str, Any]:
    """An effect in event.choices; a modifier adds its stat and months (M10b, 23.2)."""
    out: dict[str, Any] = {"type": e.type, "target": e.target, "value": e.value}
    if e.type == "modifier":
        out |= {"stat": e.stat, "months": e.months}
    elif e.type == "public_step":  # M13 (25)
        out |= {"stat": e.stat}
    return out


def storyline_to_row(story: Storyline) -> StorylineRow:
    values = asdict(story)
    values["person_ids"] = list(story.person_ids)
    return StorylineRow(**values)


def storyline_from_row(row: StorylineRow) -> Storyline:
    values = {f.name: getattr(row, f.name) for f in fields(Storyline)}
    values["person_ids"] = tuple(row.person_ids or ())
    return Storyline(**values)


def queued_to_row(queued: QueuedEvent) -> EventQueueRow:
    values = asdict(queued)
    values["person_ids"] = list(queued.person_ids)
    return EventQueueRow(**values)


def queued_from_row(row: EventQueueRow) -> QueuedEvent:
    values = {f.name: getattr(row, f.name) for f in fields(QueuedEvent)}
    values["person_ids"] = tuple(row.person_ids or ())
    return QueuedEvent(**values)


# --- Event modifiers (M10b, 23.2) -------------------------------------------------------------


def modifier_to_row(m: Modifier) -> EventModifierRow:
    return EventModifierRow(**asdict(m))


def modifier_from_row(row: EventModifierRow) -> Modifier:
    return Modifier(**{f.name: getattr(row, f.name) for f in fields(Modifier)})
