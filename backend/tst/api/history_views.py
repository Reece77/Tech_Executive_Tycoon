"""History (docs/formulas.md 17.2; M7b): the timeline, month lines, charts, storylines and the
hall of fame, built from stored rows only. Everything here is what the player could see:
names, titles, choices, KPIs and shown ratings (displayed-range midpoints), never a true
value (ADR-0007)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tst.api.schemas.history import (
    BiggestRoundOut,
    ChartsOut,
    FirstOut,
    HallOfFameOut,
    HistoryRowOut,
    KpiPointOut,
    NamedOut,
    PeakOut,
    PersonRecordOut,
    ProductPointOut,
    ProductRecordOut,
    ProductSeriesOut,
    RivalOutlastedOut,
    StorylineHistoryOut,
    StoryStepOut,
    TimelineOut,
)
from tst.db.models import (
    CompanyRow,
    DecisionLogRow,
    EmploymentRow,
    EventRow,
    FundingRoundRow,
    InboxItemRow,
    OrgUnitRow,
    PersonRatingLogRow,
    PersonRow,
    ProductMonthRow,
    ProductRow,
    StorylineRow,
    TurnSnapshotRow,
)
from tst.db.repository import DELEGATE_SOURCE, PLAYER_SOURCE
from tst.db.state_io import has_table
from tst.loader import LoadedData
from tst.sim.calendar import format_turn, turn_to_ym
from tst.sim.money import format_money

CATEGORIES = ("people", "products", "finance", "rivals", "events")
SOURCES = ("player", "delegate", "default")
TOP = 5  # people in each hall-of-fame list (17.2)
ARR_FIRST_MILLION_CENTS = 100_000_000  # "first $1M ARR" (17.2)
ENTERPRISE = "enterprise"  # the segment of "first enterprise customer"

# Inbox kinds the timeline shows (17.2: hire, departure, launch, round, board, rival news),
# by category. Month-end shows as the month lines.
INBOX_CATEGORY: dict[str, str] = {
    "offer_accepted": "people",
    "resigned": "people",
    "retired": "people",
    "employee_left": "people",
    "poach_accepted": "people",
    "culture_carrier_left": "people",
    "product_launched": "products",
    "first_customer": "products",
    "arr_milestone": "products",
    "round_closed": "finance",
    "safe_filled": "finance",
    "bridge_funded": "finance",
    "stage_from_funding": "finance",
    "board_meeting": "finance",
    "board_warning": "finance",
    "founder_removed": "finance",
    "bankrupt": "finance",
    "market_news": "rivals",
    "rival_failed": "rivals",
    "rival_approach": "rivals",
    "poach_declined": "rivals",
    # M8: divisions and the executive team (entrants arrive as market news)
    "division_created": "people",
    "exec_appointed": "people",
    "exec_removed": "people",
    "exec_left": "people",
    # M10: loans, breaches and a called loan (rounds C and D are round_closed)
    "loan_signed": "finance",
    "loan_repaid": "finance",
    "covenant_breached": "finance",
    "loan_called": "finance",
    # M9: offices and regional launches
    "office_leased": "people",
    "office_closed": "people",
    "region_launched": "products",
    "region_live": "products",
    # M10c: executives' quarterly reports and proposals (24.1, 24.3)
    "exec_report": "people",
    "exec_proposal": "finance",
    # M12a: data centres, contracts, Cloud hosting and outages (22.6)
    "facility_ordered": "products",
    "facility_live": "products",
    "facility_sold": "products",
    "contract_signed": "finance",
    "contract_settled": "finance",
    "cloud_started": "products",
    "outage_hit": "products",
    # M11: era milestones, licences and research leaks (21.4, 21.5)
    "era_arrived": "products",
    "license_in": "products",
    "license_out": "products",
    "research_leak": "people",
}
PRODUCT_KINDS = frozenset(
    {
        "create_product",
        "set_price",
        "add_segment",
        "assign_unit",
        "unassign_unit",
        "set_marketing",
        "launch_product",
        "sunset_product",
        "cancel_product",
        "launch_in_region",  # M9
        "set_regional_price",
        "build_facility",  # M12a
        "sell_facility",
        "staff_facility",
        "sell_capacity",
        "start_project",  # M11
        "stop_project",
        "set_project_budget",
        "license_in",
        "license_out",
    }
)
FINANCE_KINDS = frozenset(
    {
        "raise_safe",
        "start_round",
        "accept_term_sheet",
        "accept_bridge",
        "name_nominee",
        "take_loan",  # M10
        "repay_loan",
        "sign_contract",  # M12a
    }
)
END_REASONS = {
    "resigned": "resigned",
    "poached": "poached",
    "fired": "fired",
    "retired": "retired",
    "company_failed": "the company failed",
}


def year_of(turn: int) -> int:
    return turn_to_ym(turn)[0]


def short_money(cents: int) -> str:
    """$1.2M, $640k, $900: month lines and charts' captions."""
    dollars = cents / 100
    sign = "-" if dollars < 0 else ""
    d = abs(dollars)
    if d >= 1_000_000:
        return f"{sign}${d / 1_000_000:.1f}M"
    if d >= 1_000:
        return f"{sign}${d / 1_000:.0f}k"
    return f"{sign}${d:.0f}"


@dataclass(frozen=True, slots=True)
class _Names:
    people: dict[int, str]
    products: dict[int, str]
    units: dict[int, str]
    companies: dict[int, str]

    def person(self, pid: Any) -> str:
        return self.people.get(int(pid), "someone") if pid is not None else "someone"

    def product(self, pid: Any) -> str:
        return self.products.get(int(pid), "a product") if pid is not None else "a product"

    def unit(self, uid: Any) -> str:
        return self.units.get(int(uid), "a unit") if uid is not None else "the company"


def _names(session: Session) -> _Names:
    people = {
        int(i): f"{f} {last}"
        for i, f, last in session.execute(
            select(PersonRow.id, PersonRow.first_name, PersonRow.last_name)
        )
    }
    products = {int(i): n for i, n in session.execute(select(ProductRow.id, ProductRow.name))}
    units = {int(i): n for i, n in session.execute(select(OrgUnitRow.id, OrgUnitRow.name))}
    companies = {int(i): n for i, n in session.execute(select(CompanyRow.id, CompanyRow.name))}
    return _Names(people, products, units, companies)


def _role(key: Any, data: LoadedData) -> str:
    try:
        return data.game_data.role(str(key)).label
    except KeyError:
        return str(key).replace("_", " ")


@dataclass(frozen=True, slots=True)
class _Entry:
    turn: int
    order: int  # within a month, newest first
    row: HistoryRowOut


def _domain(key: Any, data: LoadedData) -> str:
    """A research domain's label (M11); the key if the data no longer has it."""
    from tst.sim.research.levels import domain_def

    try:
        return domain_def(data.game_data, str(key)).label
    except (KeyError, AssertionError):
        return str(key)


def _describe(
    kind: str, p: dict[str, Any], names: _Names, data: LoadedData
) -> tuple[str, str, int | None, int | None]:
    """(category, what happened, person id, product id) for one logged action."""
    person = p.get("person_id", p.get("candidate_id"))
    product = p.get("product_id")
    who = names.person(person)
    prod = names.product(product)
    texts: dict[str, str] = {
        "open_search": f"Opened a {str(p.get('channel', '')).replace('_', ' ')} search for "
        f"{_role(p.get('role'), data)}",
        "close_search": "Closed a search",
        "interview": f"Interviewed {who}",
        "reference_check": f"Checked {who}'s references",
        "make_offer": f"Offered {who} {format_money(int(p.get('salary_cents', 0)))} a year",
        "withdraw_offer": "Withdrew an offer",
        "fire": f"Fired {who}",
        "create_unit": f"Created the {p.get('unit_kind', 'unit')} {p.get('name', '')}".strip(),
        "dissolve_unit": f"Dissolved {names.unit(p.get('unit_id'))}",
        "move_unit": f"Moved {names.unit(p.get('unit_id'))}",
        "rename_unit": f"Renamed a unit to {p.get('name', '')}",
        "set_leader": f"Made {who} the leader of {names.unit(p.get('unit_id'))}"
        if person is not None
        else f"Removed the leader of {names.unit(p.get('unit_id'))}",
        "move_person": f"Moved {who} to {names.unit(p.get('unit_id'))}",
        "set_policy": f"Set {names.unit(p.get('unit_id'))} to {p.get('policy') or 'inherit'} work",
        "give_raise": f"Raised {who}'s salary to {format_money(int(p.get('salary_cents', 0)))}",
        "promote": f"Promoted {who}",
        "create_plan": f"Started a hiring plan for {_role(p.get('role'), data)}",
        "update_plan": "Changed a hiring plan",
        "close_plan": "Closed a hiring plan",
        "scout": f"Scouted the market for {_role(p.get('role'), data)}",
        "scout_search": "Scouted a search's candidates",
        "create_product": f"Started building {p.get('name', 'a product')}",
        "set_price": f"Set {prod}'s {str(p.get('segment', '')).replace('_', ' ')} price to "
        f"{format_money(int(p.get('price_cents', 0)))}",
        "add_segment": f"Took {prod} into {str(p.get('segment', '')).replace('_', ' ')}",
        "assign_unit": f"Put {names.unit(p.get('unit_id'))} on {prod}",
        "unassign_unit": f"Took {names.unit(p.get('unit_id'))} off its product",
        "set_marketing": f"Set {prod}'s marketing to "
        f"{format_money(int(p.get('budget_cents', 0)))} a month",
        "launch_product": f"Launched {prod}",
        "sunset_product": f"Sunset {prod}",
        "cancel_product": f"Cancelled {prod}",
        "raise_safe": f"Raised a SAFE: {format_money(int(p.get('amount_cents', 0)))} at a "
        f"{format_money(int(p.get('cap_cents', 0)))} cap",
        "start_round": f"Started a {p.get('series', '')} round for "
        f"{format_money(int(p.get('target_cents', 0)))}",
        "accept_term_sheet": "Accepted a term sheet",
        "accept_bridge": "Accepted a bridge from your investors",
        "name_nominee": f"Named {who} to the board",
        "take_loan": f"Signed {str(p.get('instrument', 'a loan')).replace('_', ' ')} for "
        f"{format_money(int(p.get('amount_cents', 0)))}",
        "repay_loan": "Repaid a loan early",
        # M10c (24.1): authority and the answers to executives' proposals
        "set_authority": f"{'Gave' if p.get('enabled') else 'Withdrew'} the "
        f"{str(p.get('seat', '')).upper()}'s authority",
        "answer_proposal": f"{'Approved' if p.get('approve') else 'Declined'} an executive's "
        "proposal",
        # M11 (21.3, 21.5): research projects and licences
        "start_project": f"Put {names.unit(p.get('unit_id'))} on "
        f"{_domain(p.get('domain'), data)} research",
        "stop_project": "Stopped a research project",
        "set_project_budget": "Changed a research budget"
        if p.get("budget_cents") is not None
        else "Funded a research project in full",
        "license_in": f"Licensed {_domain(p.get('domain'), data)} know-how in",
        "license_out": f"Licensed {_domain(p.get('domain'), data)} know-how out",
    }
    text = texts.get(kind, kind.replace("_", " ").capitalize())
    category = (
        "products" if kind in PRODUCT_KINDS else "finance" if kind in FINANCE_KINDS else "people"
    )
    return category, text, int(person) if person is not None else None, product


def _row(
    *,
    key: str,
    turn: int,
    category: str,
    title: str,
    names: _Names,
    detail: str | None = None,
    source: str | None = None,
    actor: str | None = None,
    person_id: int | None = None,
    product_id: int | None = None,
    event_id: int | None = None,
) -> HistoryRowOut:
    return HistoryRowOut(
        key=key,
        kind="entry",
        turn=turn,
        date_label=format_turn(turn),
        category=category,
        title=title,
        detail=detail,
        source=source,
        actor=actor,
        person_id=person_id,
        person_name=names.people.get(person_id) if person_id is not None else None,
        product_id=product_id,
        product_name=names.products.get(product_id) if product_id is not None else None,
        event_id=event_id,
    )


def _entries(session: Session, company: int, names: _Names, data: LoadedData) -> list[_Entry]:
    out: list[_Entry] = []
    if has_table(session, EventRow):
        for ev in session.scalars(
            select(EventRow).where(
                EventRow.company_id == company, EventRow.status.in_(("answered", "auto"))
            )
        ):
            choice = next((c for c in ev.choices if c.get("key") == ev.chosen), None)
            label = choice.get("label") if choice else ev.chosen
            auto = ev.status == "auto"
            people = list(ev.person_ids or [])
            out.append(
                _Entry(
                    ev.resolved_turn if ev.resolved_turn is not None else ev.turn,
                    ev.id,
                    _row(
                        key=f"event-{ev.id}",
                        turn=ev.resolved_turn if ev.resolved_turn is not None else ev.turn,
                        category="events",
                        title=ev.title or ev.template_id.replace("_", " "),
                        detail=f"Chose: {label}" if label else None,
                        source="default" if auto else "player",
                        actor="Default (at Continue)" if auto else "You",
                        person_id=int(people[0]) if people else None,
                        product_id=ev.product_id,
                        event_id=ev.id,
                        names=names,
                    ),
                )
            )
    for d in session.scalars(
        select(DecisionLogRow).where(
            DecisionLogRow.company_id == company,
            DecisionLogRow.source.in_((PLAYER_SOURCE, DELEGATE_SOURCE)),
            DecisionLogRow.seq.is_not(None),
            DecisionLogRow.kind != "choose_event",
            DecisionLogRow.kind != "new_game",
        )
    ):
        category, text, person, product = _describe(d.kind, dict(d.payload), names, data)
        delegate = d.source == DELEGATE_SOURCE
        out.append(
            _Entry(
                d.turn,
                d.id,
                _row(
                    key=f"decision-{d.id}",
                    turn=d.turn,
                    category=category,
                    title=text,
                    source="delegate" if delegate else "player",
                    actor=names.person(d.actor_id) if delegate else "You",
                    person_id=person,
                    product_id=product,
                    names=names,
                ),
            )
        )
    for m in session.scalars(
        select(InboxItemRow).where(
            InboxItemRow.company_id == company, InboxItemRow.template.in_(list(INBOX_CATEGORY))
        )
    ):
        person = m.link_id if m.link_kind in ("person", "candidate") else None
        product = m.link_id if m.link_kind == "product" else None
        out.append(
            _Entry(
                m.turn,
                m.id,
                _row(
                    key=f"inbox-{m.id}",
                    turn=m.turn,
                    category=INBOX_CATEGORY[m.template],
                    title=m.title,
                    detail=m.body,
                    person_id=person,
                    product_id=product,
                    names=names,
                ),
            )
        )
    return out


def _month_lines(session: Session, company: int) -> dict[int, HistoryRowOut]:
    snaps = [
        (r.turn, r.kpis)
        for r in session.scalars(
            select(TurnSnapshotRow)
            .where(TurnSnapshotRow.company_id == company)
            .order_by(TurnSnapshotRow.turn)
        )
    ]
    lines: dict[int, HistoryRowOut] = {}
    prev: dict[str, Any] | None = None
    for turn, k in snaps:
        arr = int(k.get("arr_cents", 0))
        parts = [format_turn(turn)]
        growth = ""
        if prev is not None and int(prev.get("arr_cents", 0)) > 0:
            change = (arr - int(prev["arr_cents"])) / int(prev["arr_cents"])
            growth = f" ({change:+.0%})"
        parts.append(f"ARR {short_money(arr)}{growth}")
        parts.append(f"cash {short_money(int(k.get('cash_cents', 0)))}")
        staff = int(k.get("headcount", 0))
        delta = staff - int(prev.get("headcount", 0)) if prev is not None else 0
        parts.append(f"{staff} staff" + (f" ({delta:+d})" if delta else ""))
        morale = k.get("avg_morale")
        if morale is not None:
            parts.append(f"morale {float(morale):.0f}")
        lines[turn] = HistoryRowOut(
            key=f"month-{turn}",
            kind="month",
            turn=turn,
            date_label=format_turn(turn),
            category=None,
            title=" · ".join(parts),
        )
        prev = k
    return lines


def _matches(row: HistoryRowOut, search: str) -> bool:
    hay = " ".join(
        x for x in (row.title, row.detail, row.actor, row.person_name, row.product_name) if x
    ).lower()
    return search in hay


def timeline(
    session: Session,
    company: int,
    data: LoadedData,
    *,
    search: str = "",
    year: int | None = None,
    category: str | None = None,
    source: str | None = None,
    person_id: int | None = None,
    product_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> TimelineOut:
    """Entries and month lines, newest first; filters keep entries, and month lines stay
    for the months that still have one (all months when nothing filters)."""
    names = _names(session)
    entries = _entries(session, company, names, data)
    months = _month_lines(session, company)
    people = sorted({e.row.person_id for e in entries if e.row.person_id is not None})
    products = sorted({e.row.product_id for e in entries if e.row.product_id is not None})
    years = sorted({year_of(e.turn) for e in entries} | {year_of(t) for t in months}, reverse=True)
    q = search.strip().lower()
    kept = [
        e
        for e in entries
        if (year is None or year_of(e.turn) == year)
        and (category is None or e.row.category == category)
        and (source is None or e.row.source == source)
        and (person_id is None or e.row.person_id == person_id)
        and (product_id is None or e.row.product_id == product_id)
        and (not q or _matches(e.row, q))
    ]
    filtering = bool(q) or any(v is not None for v in (category, source, person_id, product_id))
    shown_months = {e.turn for e in kept} if filtering else set(months)
    rows: list[tuple[int, int, int, HistoryRowOut]] = [(e.turn, 0, e.order, e.row) for e in kept]
    rows += [
        (t, 1, 0, line)
        for t, line in months.items()
        if t in shown_months and (year is None or year_of(t) == year)
    ]
    rows.sort(key=lambda r: (r[0], r[1], r[2]), reverse=True)
    return TimelineOut(
        total=len(rows),
        offset=offset,
        rows=[r[3] for r in rows[offset : offset + limit]],
        years=years,
        people=[NamedOut(id=p, name=names.people.get(p, "someone")) for p in people],
        products=[NamedOut(id=p, name=names.products.get(p, "a product")) for p in products],
    )


# --- Charts ---------------------------------------------------------------------------------

KPI_KEYS = (
    "cash_cents",
    "monthly_burn_cents",
    "payroll_cents",
    "headcount",
    "avg_morale",
    "mrr_cents",
    "arr_cents",
    "founder_bp",
    "board_confidence",
)


def charts(session: Session, company: int) -> ChartsOut:
    kpis = [
        KpiPointOut(
            turn=r.turn,
            date_label=format_turn(r.turn),
            **{k: r.kpis.get(k) for k in KPI_KEYS},
        )
        for r in session.scalars(
            select(TurnSnapshotRow)
            .where(TurnSnapshotRow.company_id == company)
            .order_by(TurnSnapshotRow.turn)
        )
    ]
    own = {
        int(i): n
        for i, n in session.execute(
            select(ProductRow.id, ProductRow.name).where(ProductRow.company_id == company)
        )
    }
    by_product: dict[int, dict[int, list[float]]] = defaultdict(dict)
    if own:
        for m in session.scalars(
            select(ProductMonthRow)
            .where(ProductMonthRow.product_id.in_(list(own)))
            .order_by(ProductMonthRow.turn)
        ):
            point = by_product[m.product_id].setdefault(m.turn, [0.0, 0.0])
            point[0] += m.revenue_cents
            point[1] += m.customers
    return ChartsOut(
        kpis=kpis,
        products=[
            ProductSeriesOut(
                product_id=pid,
                name=own[pid],
                points=[
                    ProductPointOut(
                        turn=t,
                        date_label=format_turn(t),
                        mrr_cents=int(v[0]),
                        customers=round(v[1]),
                    )
                    for t, v in sorted(by_product[pid].items())
                ],
            )
            for pid in sorted(by_product)
        ],
    )


# --- Storylines -----------------------------------------------------------------------------


def storylines(session: Session, company: int) -> list[StorylineHistoryOut]:
    if not has_table(session, StorylineRow):
        return []
    events: dict[int, list[EventRow]] = defaultdict(list)
    for ev in session.scalars(
        select(EventRow)
        .where(EventRow.company_id == company, EventRow.storyline_id.is_not(None))
        .order_by(EventRow.turn, EventRow.id)
    ):
        events[int(ev.storyline_id or 0)].append(ev)
    out = []
    for s in session.scalars(
        select(StorylineRow).where(StorylineRow.company_id == company).order_by(StorylineRow.id)
    ):
        steps = []
        for ev in events.get(s.id, []):
            choice = next((c for c in ev.choices if c.get("key") == ev.chosen), None)
            steps.append(
                StoryStepOut(
                    turn=ev.turn,
                    date_label=format_turn(ev.turn),
                    title=ev.title or ev.template_id.replace("_", " "),
                    choice=choice.get("label") if choice else ev.chosen,
                    by="Default (at Continue)"
                    if ev.status == "auto"
                    else "You"
                    if ev.status == "answered"
                    else None,
                    event_id=ev.id,
                )
            )
        out.append(
            StorylineHistoryOut(
                storyline_id=s.id,
                title=s.title,
                status=s.status,
                started_turn=s.started_turn,
                started_label=format_turn(s.started_turn),
                ended_label=format_turn(s.ended_turn) if s.ended_turn is not None else None,
                summary=s.summary,
                steps=steps,
            )
        )
    out.sort(key=lambda s: (s.status != "active", -s.storyline_id))
    return out


# --- Hall of fame ---------------------------------------------------------------------------


def _first(label: str, turn: int | None, detail: str | None = None) -> FirstOut:
    return FirstOut(
        label=label,
        turn=turn,
        date_label=format_turn(turn) if turn is not None else None,
        detail=detail,
    )


def _ratings(session: Session, ids: Iterable[int]) -> dict[int, list[tuple[int, float]]]:
    out: dict[int, list[tuple[int, float]]] = defaultdict(list)
    ids = list(ids)
    if not ids or not has_table(session, PersonRatingLogRow):
        return out
    for r in session.scalars(
        select(PersonRatingLogRow)
        .where(PersonRatingLogRow.person_id.in_(ids))
        .order_by(PersonRatingLogRow.turn)
    ):
        out[r.person_id].append((r.turn, r.rating))
    return out


def hall_of_fame(session: Session, company: int, turn_now: int, data: LoadedData) -> HallOfFameOut:
    names = _names(session)
    snaps = [
        (r.turn, r.kpis)
        for r in session.scalars(
            select(TurnSnapshotRow)
            .where(TurnSnapshotRow.company_id == company)
            .order_by(TurnSnapshotRow.turn)
        )
    ]

    def peak(key: str) -> PeakOut | None:
        best = max(snaps, key=lambda s: (s[1].get(key, 0), -s[0]), default=None)
        if best is None or not best[1].get(key):
            return None
        return PeakOut(value=int(best[1][key]), turn=best[0], date_label=format_turn(best[0]))

    rounds = list(
        session.scalars(
            select(FundingRoundRow).where(
                FundingRoundRow.company_id == company, FundingRoundRow.status == "closed"
            )
        )
    )
    big = max(rounds, key=lambda r: (r.amount_cents or 0, -(r.closed_turn or 0)), default=None)
    biggest = (
        BiggestRoundOut(
            series=big.series,
            amount_cents=int(big.amount_cents or 0),
            lead=data.game_data.firm(big.lead_firm).name if big.lead_firm else None,
            turn=int(big.closed_turn or 0),
            date_label=format_turn(int(big.closed_turn or 0)),
        )
        if big is not None
        else None
    )

    own_products = list(session.scalars(select(ProductRow).where(ProductRow.company_id == company)))
    own_ids = [p.id for p in own_products]
    months = (
        list(
            session.scalars(
                select(ProductMonthRow)
                .where(ProductMonthRow.product_id.in_(own_ids))
                .order_by(ProductMonthRow.turn)
            )
        )
        if own_ids
        else []
    )
    launches = [p for p in own_products if p.launched_turn is not None]
    first_launch = min(launches, key=lambda p: p.launched_turn or 0, default=None)
    paying = [m for m in months if m.customers > 0 and m.revenue_cents > 0]
    first_paying = paying[0] if paying else None
    enterprise = next((m for m in paying if m.segment == ENTERPRISE), None)
    million = next(
        (t for t, k in snaps if int(k.get("arr_cents", 0)) >= ARR_FIRST_MILLION_CENTS), None
    )
    first_round = min(rounds, key=lambda r: r.closed_turn or 0, default=None)
    firsts = [
        _first(
            "First launch",
            first_launch.launched_turn if first_launch else None,
            first_launch.name if first_launch else None,
        ),
        _first(
            "First paying customer",
            first_paying.turn if first_paying else None,
            names.product(first_paying.product_id) if first_paying else None,
        ),
        _first(
            "First enterprise customer",
            enterprise.turn if enterprise else None,
            names.product(enterprise.product_id) if enterprise else None,
        ),
        _first("First $1M ARR", million),
        _first(
            "First round closed",
            first_round.closed_turn if first_round else None,
            first_round.series if first_round else None,
        ),
    ]

    founders = {
        int(i) for i in session.scalars(select(PersonRow.id).where(PersonRow.is_founder.is_(True)))
    }
    jobs = [
        e
        for e in session.scalars(select(EmploymentRow).where(EmploymentRow.company_id == company))
        if e.person_id not in founders and e.status != "offer"
    ]
    ratings = _ratings(session, {e.person_id for e in jobs})

    def tenure(e: EmploymentRow) -> int:
        end = e.end_turn if e.status == "ended" and e.end_turn is not None else turn_now
        return max(end - e.start_turn, 0)

    def record(e: EmploymentRow, value: float, extra: str | None = None) -> PersonRecordOut:
        return PersonRecordOut(
            person_id=e.person_id,
            name=names.person(e.person_id),
            role=_role(e.role, data),
            current=e.status != "ended",
            months=tenure(e),
            value=round(value, 1),
            detail=extra,
        )

    longest = sorted(jobs, key=lambda e: (-tenure(e), e.person_id))[:TOP]
    rises = []
    for e in jobs:
        logged = [r for t, r in ratings.get(e.person_id, []) if t >= e.start_turn]
        if len(logged) >= 2:
            rises.append((logged[-1] - logged[0], e, logged[0], logged[-1]))
    rises.sort(key=lambda r: (-r[0], r[1].person_id))
    later = {
        (e.person_id, e.start_turn): e
        for e in session.scalars(select(EmploymentRow).where(EmploymentRow.company_id != company))
    }
    departed = []
    for e in jobs:
        if e.status != "ended":
            continue
        logged = [r for t, r in ratings.get(e.person_id, []) if t >= e.start_turn]
        if not logged:
            continue
        reason = END_REASONS.get(e.end_reason or "", e.end_reason or "left")
        if e.end_reason == "poached" and e.end_turn is not None:
            rival = next(
                (
                    j
                    for (pid, start), j in later.items()
                    if pid == e.person_id and start >= e.end_turn - 1
                ),
                None,
            )
            if rival is not None:
                reason = f"poached by {names.companies.get(rival.company_id, 'a rival')}"
        departed.append((logged[-1], e, reason))
    departed.sort(key=lambda d: (-d[0], d[1].person_id))

    best_mrr: dict[int, int] = defaultdict(int)
    best_quality: dict[int, float] = defaultdict(float)
    per_turn: dict[tuple[int, int], int] = defaultdict(int)
    for m in months:
        per_turn[(m.product_id, m.turn)] += m.revenue_cents
        best_quality[m.product_id] = max(best_quality[m.product_id], m.quality)
    for (pid, _), mrr in per_turn.items():
        best_mrr[pid] = max(best_mrr[pid], mrr)
    top_mrr = max(best_mrr.items(), key=lambda kv: (kv[1], -kv[0]), default=None)
    top_quality = max(best_quality.items(), key=lambda kv: (kv[1], -kv[0]), default=None)

    outlasted = _outlasted(session, company, names)
    return HallOfFameOut(
        peak_arr=peak("arr_cents"),
        peak_headcount=peak("headcount"),
        biggest_round=biggest,
        firsts=firsts,
        longest_serving=[record(e, tenure(e)) for e in longest],
        best_hires=[
            record(e, rise, f"{start:.1f} → {end:.1f}") for rise, e, start, end in rises[:TOP]
        ],
        notable_departures=[record(e, r, reason) for r, e, reason in departed[:TOP]],
        best_product_mrr=ProductRecordOut(
            product_id=top_mrr[0], name=names.product(top_mrr[0]), value=float(top_mrr[1])
        )
        if top_mrr and top_mrr[1] > 0
        else None,
        best_product_quality=ProductRecordOut(
            product_id=top_quality[0],
            name=names.product(top_quality[0]),
            value=round(top_quality[1], 1),
        )
        if top_quality
        else None,
        rivals_outlasted=outlasted,
    )


def _outlasted(session: Session, company: int, names: _Names) -> list[RivalOutlastedOut]:
    """Rival startups that failed while the player sold in one of their segments."""
    failed = list(
        session.scalars(
            select(CompanyRow).where(
                CompanyRow.is_startup.is_(True), CompanyRow.failed_turn.is_not(None)
            )
        )
    )
    if not failed:
        return []
    products = {p.id: p for p in session.scalars(select(ProductRow))}
    sold: dict[tuple[str, str], list[int]] = defaultdict(list)  # (category, segment) -> turns
    rival_markets: dict[int, set[tuple[str, str]]] = defaultdict(set)
    for m in session.scalars(select(ProductMonthRow)):
        product = products.get(m.product_id)
        if product is None:
            continue
        market = (product.category, m.segment)
        if product.company_id == company and m.customers > 0:
            sold[market].append(m.turn)
        else:
            rival_markets[product.company_id].add(market)
    out = []
    for rival in failed:
        turn = int(rival.failed_turn or 0)
        shared = [
            market
            for market in rival_markets.get(rival.id, set())
            if any(t <= turn for t in sold.get(market, []))
        ]
        if shared:
            category, segment = sorted(shared)[0]
            out.append(
                RivalOutlastedOut(
                    name=rival.name,
                    turn=turn,
                    date_label=format_turn(turn),
                    market=f"{category.replace('_', ' ')} · {segment.replace('_', ' ')}",
                )
            )
    return sorted(out, key=lambda r: r.turn)
