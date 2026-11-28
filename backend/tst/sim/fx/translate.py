"""Translation (docs/formulas.md 64.4, ADR-0025 point 3): a regional price is set in local money, so
its US-cent value in month t is

    price at setting x index_t / index_s      (s the month it was set; rounded half to even)

and the month's revenue books at that price (phase 5, through `Effects.fx_price`). Local costs move
the same way (phase 6, `cost_entries`): an employee working from an office in another region costs
salary and benefits x (index_t / index_b - 1) more (b the month of hire or last raise, A), and
a lease abroad its rent x (index_t / index_opened - 1). Nothing is held in another currency:
revenue and costs are translated, not converted (ADR-0025 point 1).

Who translates: the player's companies from the start; rivals from `fx.applies_from` (their history
is already in reported dollars, point 4). A segment in the home region translates only when the home
region is not `fx.home` (a player headquartered outside North America). A company that sells and
spends only in North America books exactly as before (64.6 target 1): its indexes are 1.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.fx.models import PriceMark
from tst.sim.fx.rates import enabled, index_at
from tst.sim.geo.formulas import lease_rent_cents
from tst.sim.geo.offices import office_of
from tst.sim.hiring.formulas import benefits_cents, monthly_salary_cents
from tst.sim.ledger import CASH, RENT, SALARIES, LedgerEntry, LedgerLine
from tst.sim.money import round_half_even
from tst.sim.products.models import SELLING
from tst.sim.state import CompanyState, GameState

type Key = tuple[int, str, str]  # (product id, region, segment)


def translates(company: CompanyState | None, turn: int, balance: Balance) -> bool:
    if company is None:
        return False
    return company.is_player or turn >= balance.fx.start_turn


def translated(price: int, now: int, then: int) -> int:
    """price x now / then, rounded half to even (exact integers)."""
    if now == then:
        return price
    return round_half_even(price * now, then)


def _segments(state: GameState, home: str) -> Iterable[tuple[int, int, str, str, int | None]]:
    """(company id, product id, region, segment, price) of every selling product's segments."""
    for p in state.products:
        if p.status not in SELLING:
            continue
        for s in state.segments_of(p.id):
            yield p.company_id, p.id, home, s.segment, s.price_cents
        for rs in state.regional_segments_of(p.id):
            yield p.company_id, p.id, rs.region, rs.segment, rs.price_cents


def update_marks(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Phase 5, before the markets: every translating segment's mark is its price and the month
    it was set (a new or changed price is marked this month)."""
    if not enabled(data):
        return state
    xb = balance.fx
    home = home_region_of(state, balance, data)
    from tst.sim.media.ads import engine_priced

    old = {(m.product_id, m.region, m.segment): m for m in state.fx.marks}
    marks: list[PriceMark] = []
    companies = {c.id: c for c in state.companies}
    engine: dict[int, bool] = {}
    for cid, pid, region, seg, price in _segments(state, home):
        if price is None or region == xb.home:
            continue
        if not translates(companies.get(cid), state.turn, balance):
            continue
        if pid not in engine:
            p = state.product(pid)
            engine[pid] = p is not None and engine_priced(state, p, balance)
        m = old.get((pid, region, seg))
        # an engine-set price is already in US cents this month: re-marked every month
        if m is None or m.price_cents != price or (engine[pid] and m.turn != state.turn):
            m = PriceMark(pid, region, seg, price, state.turn)
        marks.append(m)
    marks.sort(key=lambda m: (m.product_id, m.region, m.segment))
    out = tuple(marks)
    if out == state.fx.marks:
        return state
    return replace(state, fx=replace(state.fx, marks=out))


def fx_prices(state: GameState, balance: Balance, data: GameData) -> dict[Key, int]:
    """The month's translated price of every marked segment whose index has moved since."""
    out: dict[Key, int] = {}
    if not enabled(data):
        return out
    now: dict[str, int] = {}
    for m in state.fx.marks:
        if m.region not in now:
            now[m.region] = index_at(state, m.region, state.turn, balance, data)
        then = index_at(state, m.region, m.turn, balance, data)
        price = translated(m.price_cents, now[m.region], then)
        if price != m.price_cents:
            out[(m.product_id, m.region, m.segment)] = max(1, price)
    return out


def booked_prices(state: GameState, balance: Balance, data: GameData) -> dict[Key, int]:
    """`fx_prices` once a state: the prices phase 5 books at, for what is a share of booked
    revenue (royalties, claims, store fees; M57r-A, review 10 item 10 and ruling 4)."""
    from tst.sim.state import derived

    return derived(
        state, ("fx_booked_prices", id(balance), id(data)), lambda: fx_prices(state, balance, data)
    )


def booked_price(
    state: GameState,
    product_id: int,
    region: str,
    segment: str,
    price: int,
    balance: Balance,
    data: GameData,
) -> int:
    """A segment's price as phase 5 books it this month: translated where its index moved."""
    prices = booked_prices(state, balance, data)
    return prices.get((product_id, region, segment), price) if prices else price


def _cost_basis(turn: int, last_raise: int | None) -> int:
    return turn if last_raise is None else max(turn, last_raise)


@dataclass(frozen=True, slots=True)
class LocalCosts:
    """A company's local costs in a region this month: as booked before translation, and the
    translation differences of its staff (salary and benefits) and its leases."""

    base_cents: int = 0
    staff_delta_cents: int = 0
    rent_delta_cents: int = 0

    @property
    def delta_cents(self) -> int:
        return self.staff_delta_cents + self.rent_delta_cents


def local_costs(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> dict[str, LocalCosts]:
    """Region -> its LocalCosts for the company's staff in offices abroad and its leases there
    (module docstring). Empty for a company whose staff and offices are all in `fx.home`."""
    xb = balance.fx
    out: dict[str, LocalCosts] = {}
    if not enabled(data):
        return out
    now: dict[str, int] = {}

    def index_now(region: str) -> int:
        if region not in now:
            now[region] = index_at(state, region, state.turn, balance, data)
        return now[region]

    for e in state.staff(company_id):
        office_id = office_of(state, e)
        office = state.office(office_id) if office_id is not None else None
        if office is None:
            continue
        region = data.city(office.city).region
        if region == xb.home:
            continue
        pay = monthly_salary_cents(e.salary_cents)
        cost = pay + benefits_cents(pay, balance.payroll)
        then = index_at(state, region, _cost_basis(e.start_turn, e.last_raise_turn), balance, data)
        row = out.get(region, LocalCosts())
        out[region] = replace(
            row,
            base_cents=row.base_cents + cost,
            staff_delta_cents=row.staff_delta_cents
            + translated(cost, index_now(region), then)
            - cost,
        )
    for o in state.company_offices(company_id):
        region = data.city(o.city).region
        if region == xb.home:
            continue
        rent = lease_rent_cents(o.seats, data.city(o.city).rent_index, balance)
        then = index_at(state, region, o.opened_turn, balance, data)
        row = out.get(region, LocalCosts())
        out[region] = replace(
            row,
            base_cents=row.base_cents + rent,
            rent_delta_cents=row.rent_delta_cents
            + translated(rent, index_now(region), then)
            - rent,
        )
    return out


def cost_entries(state: GameState, balance: Balance, data: GameData) -> list[LedgerEntry]:
    """Phase 6, after payroll: each player company's translation of its local costs (one entry a
    company: salaries and rent abroad up or down, cash the other way). Rivals' pools are paid at
    North American rates (15.1), so they have none (A)."""
    entries: list[LedgerEntry] = []
    if not enabled(data):
        return entries
    for company in state.companies:
        if not company.is_player:
            continue
        costs = local_costs(state, company.id, balance, data).values()
        staff = sum(c.staff_delta_cents for c in costs)
        rent = sum(c.rent_delta_cents for c in costs)
        if not staff and not rent:
            continue
        lines = [LedgerLine(a, v) for a, v in ((SALARIES, staff), (RENT, rent)) if v]
        entries.append(
            LedgerEntry(
                turn=state.turn,
                company_id=company.id,
                memo="Currency translation: local salaries and rent",
                lines=(*lines, LedgerLine(CASH, -(staff + rent))),
            )
        )
    return entries
