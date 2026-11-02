"""The shared facility lifecycle (docs/formulas.md 22.2, 22.4; ADR-0020 2): order a build,
pay capex as it is built, go live (partly late in a shortage), depreciate, staff, operate,
close or sell. Kind-specific numbers come from `balance.facility.kinds`; nothing here is
specific to data centres except the kinds' data.

Every function takes the company from the facility or a `company_id`; nothing assumes one
player company (ADR-0020 1).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction

from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities import formulas as ff
from tst.sim.facilities import goods
from tst.sim.facilities.config import FacilityKindDef
from tst.sim.facilities.models import Facility, SupplyContract
from tst.sim.ledger import (
    ACCUMULATED_DEPRECIATION,
    CASH,
    COMPUTE,
    DEPRECIATION,
    GENERAL_ADMIN,
    PPE,
    LedgerEntry,
    LedgerLine,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import Cents, exact
from tst.sim.people.models import Employment
from tst.sim.state import GameState, with_contract, with_facility


def kind_of(facility: Facility, balance: Balance) -> FacilityKindDef:
    return balance.facility.kinds[facility.kind]


def facility_name(facility: Facility, balance: Balance, data: GameData) -> str:
    """'General data centre #3, North America'."""
    region = data.region(facility.region).label
    return f"{kind_of(facility, balance).label} #{facility.id}, {region}"


# --- Ordering a build (22.2, 22.4) -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BuildQuote:
    """What a build would cost and when it would finish, as the Build dialog shows it."""

    kind: str
    region: str
    capacity: int
    index: float  # the input good's index the capex is priced at
    capex_cents: Cents
    monthly_capex_cents: Cents
    build_months: int
    allocation: float
    on_time: int
    late: int
    late_months: int
    staff_needed: int
    contract_id: int | None
    contracted: int  # units the contract covers (100% allocation, locked price)


def usable_contract(
    state: GameState, company_id: int, good: str, contract_id: int | None
) -> SupplyContract | None:
    """The contract a build draws on: the one named, or none. It must be the company's own,
    active, for the build's input good, and running this month."""
    if contract_id is None:
        return None
    c = state.contract(contract_id)
    if (
        c is None
        or c.company_id != company_id
        or c.status != "active"
        or c.good != good
        or not c.signed_turn <= state.turn <= c.end_turn
        or c.remaining <= 0
    ):
        return None
    return c


def quote(
    state: GameState,
    company_id: int,
    kind_key: str,
    region: str,
    capacity: int,
    balance: Balance,
    data: GameData,
    contract_id: int | None = None,
) -> BuildQuote:
    """Capex at this month's index (the contract's for the units it covers), the build time,
    and what allocation leaves late (22.2, 22.4)."""
    kind = balance.facility.kinds[kind_key]
    month = goods.current(state, kind.input_good, data)
    contract = usable_contract(state, company_id, kind.input_good, contract_id)
    contracted = min(capacity, contract.remaining) if contract else 0
    rest = capacity - contracted
    capex = ff.capex_cents(rest, kind.capex_per_unit_cents, month.index)
    if contract is not None:
        capex += ff.capex_cents(contracted, kind.capex_per_unit_cents, contract.index)
    rest_on_time, late, months = ff.allocation_split(
        rest, month.allocation, balance.supply.delay_step
    )
    index = float(Fraction(capex, max(1, capacity * kind.capex_per_unit_cents)))
    return BuildQuote(
        kind=kind_key,
        region=region,
        capacity=capacity,
        index=index,
        capex_cents=capex,
        monthly_capex_cents=round(Fraction(capex, kind.build_months)),
        build_months=kind.build_months,
        allocation=month.allocation,
        on_time=contracted + rest_on_time,
        late=late,
        late_months=months,
        staff_needed=ff.staff_needed(capacity, kind.staff_per),
        contract_id=contract.id if contract else None,
        contracted=contracted,
    )


def order_build(state: GameState, company_id: int, q: BuildQuote) -> tuple[GameState, Facility]:
    """A new facility from a quote; the contract's volume is drawn down."""
    facility_id, ids = state.next_ids.take("facility")
    state = replace(state, next_ids=ids)
    ready = state.turn + q.build_months
    facility = Facility(
        id=facility_id,
        company_id=company_id,
        kind=q.kind,
        region=q.region,
        capacity=q.capacity,
        on_time=q.on_time,
        ordered_turn=state.turn,
        ready_turn=ready,
        late_turn=ready + q.late_months,
        capex_cents=q.capex_cents,
        input_index=q.index,
        contract_id=q.contract_id,
    )
    if q.contract_id is not None:
        contract = state.contract(q.contract_id)
        assert contract is not None
        state = with_contract(state, replace(contract, used=contract.used + q.contracted))
    return with_facility(state, facility), facility


# --- Staff and reliability (22.2) ------------------------------------------------------------


def staff_of(state: GameState, facility: Facility, balance: Balance) -> list[Employment]:
    """Infrastructure people (the kind's roles) in the unit assigned to the facility."""
    if facility.unit_id is None:
        return []
    roles = set(kind_of(facility, balance).staff_roles)
    return [
        e
        for e in state.staff(facility.company_id)
        if e.unit_id == facility.unit_id and e.role in roles and e.status == "active"
    ]


@dataclass(frozen=True, slots=True)
class Staffing:
    staff: int
    needed: int
    coverage: float
    mean_skill: float  # true value: engine only, never sent to the API (ADR-0007)
    reliability: float


def staffing(state: GameState, facility: Facility, balance: Balance) -> Staffing:
    """c_f = min(1, staff / need) and rel = 100 c_f (0.7 + 0.3 s / 20) (22.2), for the
    capacity the facility is built for."""
    kind = kind_of(facility, balance)
    people = staff_of(state, facility, balance)
    needed = ff.staff_needed(facility.capacity, kind.staff_per)
    cover = ff.coverage(len(people), needed)
    skills = [state.person(e.person_id).skills[kind.staff_skill] for e in people]
    mean = sum(skills) / len(skills) if skills else 0.0
    fb = balance.facility
    rel = ff.reliability(cover, mean, fb.reliability_floor, fb.reliability_skill)
    return Staffing(len(people), needed, cover, mean, rel)


def mean_reliability(state: GameState, company_id: int, balance: Balance) -> float | None:
    """Reliability across the company's live facilities, weighted by live capacity: its
    Cloud hosting product's quality (22.3)."""
    live = [
        (f.live_capacity(state.turn), staffing(state, f, balance).reliability)
        for f in state.company_facilities(company_id)
        if f.live_capacity(state.turn) > 0
    ]
    total = sum(c for c, _ in live)
    return sum(c * r for c, r in live) / total if total else None


# --- The month (phase 4) ---------------------------------------------------------------------


def _months_paid(facility: Facility, turn: int) -> int:
    return turn - facility.ordered_turn


def facility_month(
    state: GameState, facility: Facility, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """One facility's month: a capex payment while building (to 1500_ppe), going live, and
    depreciation from completion (6700 against 1510). Operating cost posts with phase 6's
    monthly costs (`operating_lines`)."""
    turn = state.turn
    kind = kind_of(facility, balance)
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    name = facility_name(facility, balance, data)
    company = facility.company_id
    if facility.status == "building" and turn < facility.ready_turn:
        pay = ff.capex_payment_cents(
            facility.capex_cents,
            kind.build_months,
            facility.capex_paid_cents,
            _months_paid(facility, turn),
        )
        if pay:
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=company,
                    memo=f"Capex: {name}",
                    debit=PPE,
                    credit=CASH,
                    amount=pay,
                )
            )
            facility = replace(facility, capex_paid_cents=facility.capex_paid_cents + pay)
    if facility.status == "building" and turn >= facility.ready_turn:
        facility = replace(facility, status="live")
        late = facility.capacity - facility.on_time
        logs.append(
            inbox_item(
                turn,
                company,
                "facility_live",
                facility=name,
                units=f"{facility.on_time:,} {kind.unit}",
                later=(
                    f" The other {late:,} {kind.unit} arrive by {format_turn(facility.late_turn)}:"
                    " the components were short."
                    if late
                    else ""
                ),
            )
        )
    if facility.status == "live":
        total = ff.cumulative_depreciation_cents(
            facility.capex_paid_cents,
            facility.capacity,
            facility.on_time,
            facility.ready_turn,
            facility.late_turn,
            kind.life_months,
            turn,
        )
        charge = total - facility.depreciated_cents
        if charge > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=company,
                    memo=f"Depreciation: {name}",
                    debit=DEPRECIATION,
                    credit=ACCUMULATED_DEPRECIATION,
                    amount=charge,
                )
            )
            facility = replace(facility, depreciated_cents=total)
    return with_facility(state, facility), entries, logs


def operating_cents(facility: Facility, turn: int, balance: Balance) -> Cents:
    """Live units x the kind's operating cost per unit a month (22.2)."""
    return facility.live_capacity(turn) * kind_of(facility, balance).opex_per_unit_cents


def operating_lines(
    state: GameState, company_id: int, balance: Balance
) -> list[tuple[str, str, Cents, int | None]]:
    """Phase 6's line for facilities' operating costs (memo, account, amount, division):
    corporate, with compute (22.2)."""
    total = sum(
        operating_cents(f, state.turn, balance) for f in state.company_facilities(company_id)
    )
    return [("Data centre operations", COMPUTE, total, None)] if total else []


# --- Contracts (22.4) ------------------------------------------------------------------------


def settle_contracts(
    state: GameState, balance: Balance, data: GameData | None = None
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """A contract whose last month has passed settles: take-or-pay charges its unused
    volume's share of value (22.4), to general and administrative."""
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for c in state.contracts:
        if c.status != "active" or state.turn <= c.end_turn:
            continue
        charge = round(c.remaining * exact(c.unit_value_cents) * exact(balance.supply.take_or_pay))
        if charge:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=c.company_id,
                    memo=f"Take-or-pay: {c.remaining:,} unused units of a {c.good} contract",
                    debit=GENERAL_ADMIN,
                    credit=CASH,
                    amount=charge,
                )
            )
        state = with_contract(state, replace(c, status="settled", settled_cents=charge))
        good = c.good
        if data is not None and data.components is not None:
            good = data.components.good(c.good).label
        logs.append(
            inbox_item(
                state.turn,
                c.company_id,
                "contract_settled",
                good=good,
                used=f"{c.used:,}",
                volume=f"{c.volume:,}",
                charge_cents=charge,
            )
        )
    return state, entries, logs


# --- Closing or selling (22.2) ---------------------------------------------------------------


def sell(
    state: GameState, facility: Facility, balance: Balance, data: GameData
) -> tuple[GameState, LedgerEntry | None, Cents]:
    """Sell at `sale_share` of book value (22.2): cash in, the accumulated depreciation and
    cost out, the rest a loss in 6700. Unpaid capex of a site still building is cancelled.
    Staff stay in their unit."""
    proceeds = round(exact(facility.book_value_cents) * exact(balance.facility.sale_share))
    loss = facility.book_value_cents - proceeds
    lines = [
        LedgerLine(CASH, proceeds),
        LedgerLine(ACCUMULATED_DEPRECIATION, facility.depreciated_cents),
        LedgerLine(DEPRECIATION, loss),
        LedgerLine(PPE, -facility.capex_paid_cents),
    ]
    lines = [line for line in lines if line.amount]
    entry = None
    if lines:
        entry = LedgerEntry(
            turn=state.turn,
            company_id=facility.company_id,
            memo=f"Sale: {facility_name(facility, balance, data)}",
            lines=tuple(lines),
        )
    closed = replace(facility, status="closed", closed_turn=state.turn, unit_id=None)
    return with_facility(state, closed), entry, proceeds
