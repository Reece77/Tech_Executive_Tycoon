"""Commodity contracts and offtake agreements (docs/formulas.md 33.3, 33.4).

**Spot** buying is automatic: a unit's commodities are in its cost at this month's spot
prices (costs.py). A deal changes what the company pays for the volume it covers:

- each month a running deal **takes** up to its monthly volume (x the good's allocation unless
  protected: a prepaid offtake, or signed before the shortage began) from the company's use,
  deals in id order;
- the **hedge**: the cost of goods moves by `taken x (deal price - spot)` in dollars, where the
  deal price is the contract's fixed price or the offtake's collar (`price_for`); it posts to
  `5000_cogs` against cash (a credit when the deal is cheaper);
- **take-or-pay**: an offtake pays each month for `take_or_pay x its deliverable volume`
  taken or not (the shortfall at the deal price, `6900`); a contract pays
  `commodity.contract_take_or_pay` of its unused volume's value when it ends (as M12a's);
- **prepayment** (offtakes, at signing, to `1200_prepaid`): drawn against each month's
  purchases (the taken volume and any take-or-pay at the deal price) until spent; whatever is
  left when the deal ends or breaches comes back in cash (M17 decision);
- **breach**: in a month when spot is at least `breach.spot_over_ceiling` x the ceiling, a
  supplier breaks the offtake with chance `(1 - reliability) x breach.monthly_scale` (stream
  `commodity`, key (2, deal_id)); a supplier past its `until` month breaches at once.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from tst.sim.calendar import format_turn
from tst.sim.commodities import commodity, costs
from tst.sim.commodities.models import CommodityDeal
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import CommodityRuleError
from tst.sim.ledger import CASH, COGS, GENERAL_ADMIN, PREPAID, LedgerEntry, LedgerLine
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import Cents, times
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_commodity_deal

BREACH_KEY = 2  # tunable-exempt: stream key family for breaches (2, deal_id)
MONTHS_PER_YEAR = 12  # tunable-exempt: calendar
CENTS = 100  # tunable-exempt: cents a dollar
EPS = 1e-9  # tunable-exempt: float tolerance on volumes


def usd_per_unit(good: str, data: GameData) -> float:
    assert data.commodities is not None
    return data.commodities.good(good).usd_per_unit


def value_cents(volume: float, price: float, good: str, data: GameData) -> float:
    """Volume units at a price in the good's unit, in cents."""
    return volume * price * usd_per_unit(good, data) * CENTS


def spot_price(state: GameState, good: str, data: GameData, balance: Balance) -> float:
    return commodity.price(state, good, state.turn, data, balance)


# --- Quotes and signing ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DealQuote:
    good: str
    supplier: str | None
    months: int
    volume_year: float
    price: float  # the signing price (spot now), in the good's unit
    floor: float
    ceiling: float
    year_value_cents: Cents  # a year's volume at the signing price
    prepaid_cents: Cents


def _check_good(good: str, data: GameData) -> None:
    if data.commodities is None or good not in {g.key for g in data.commodities.goods}:
        raise CommodityRuleError(f"unknown commodity {good!r}")


def contract_quote(
    state: GameState, good: str, months: int, volume_year: float, balance: Balance, data: GameData
) -> DealQuote:
    """A fixed-price commodity contract (33.3, as M12a's: 6-36 months, take-or-pay)."""
    _check_good(good, data)
    cb = balance.commodity
    if not cb.contract_months.lo <= months <= cb.contract_months.hi:
        raise CommodityRuleError(
            f"a contract runs {cb.contract_months.lo:g} to {cb.contract_months.hi:g} months"
        )
    if volume_year <= 0:
        raise CommodityRuleError("a contract needs a volume")
    price = spot_price(state, good, data, balance)
    return DealQuote(
        good=good,
        supplier=None,
        months=months,
        volume_year=volume_year,
        price=price,
        floor=price,
        ceiling=price,
        year_value_cents=round(value_cents(volume_year, price, good, data)),
        prepaid_cents=0,
    )


def offtake_quote(
    state: GameState,
    good: str,
    supplier: str,
    years: int,
    volume_year: float,
    prepay: float,
    balance: Balance,
    data: GameData,
) -> DealQuote:
    """An offtake (33.3): 3-10 years with a named supplier, the collar at the signing price
    x (1 -/+ offtake.collar), prepayment up to offtake.prepay_max of year 1's value."""
    _check_good(good, data)
    ob = balance.offtake
    assert data.suppliers is not None
    s = data.suppliers.supplier(supplier)
    if s is None:
        raise CommodityRuleError(f"unknown supplier {supplier!r}")
    if not s.sells(good, state.turn):
        raise CommodityRuleError(f"{s.name} does not sell {good} in {format_turn(state.turn)}")
    if not ob.years.lo <= years <= ob.years.hi:
        raise CommodityRuleError(f"an offtake runs {ob.years.lo:g} to {ob.years.hi:g} years")
    if volume_year <= 0:
        raise CommodityRuleError("an offtake needs a volume")
    if not 0 <= prepay <= ob.prepay_max + EPS:
        raise CommodityRuleError(f"prepayment is at most {ob.prepay_max:.0%} of year 1's value")
    price = spot_price(state, good, data, balance)
    year = round(value_cents(volume_year, price, good, data))
    return DealQuote(
        good=good,
        supplier=supplier,
        months=years * MONTHS_PER_YEAR,
        volume_year=volume_year,
        price=price,
        floor=price * (1 - ob.collar),
        ceiling=price * (1 + ob.collar),
        year_value_cents=year,
        prepaid_cents=times(year, prepay),  # M23a: exact (Codex review 5 finding 10)
    )


def deal_from_quote(state: GameState, deal_id: int, company_id: int, q: DealQuote) -> CommodityDeal:
    return CommodityDeal(
        id=deal_id,
        company_id=company_id,
        kind="contract" if q.supplier is None else "offtake",
        good=q.good,
        supplier=q.supplier,
        signed_turn=state.turn,
        end_turn=state.turn + q.months - 1,
        volume_year=q.volume_year,
        signing_price=q.price,
        floor=q.floor,
        ceiling=q.ceiling,
        prepaid_cents=q.prepaid_cents,
        prepaid_left_cents=q.prepaid_cents,
        last_price=q.price,
    )


def next_deal_id(state: GameState) -> int:
    return max((d.id for d in state.commodity_deals), default=0) + 1


# --- The month's books -----------------------------------------------------------------------


def _entry(
    turn: int, company: int, memo: str, amount: Cents, debit: str, credit: str
) -> LedgerEntry:
    return LedgerEntry(
        turn=turn,
        company_id=company,
        memo=memo,
        lines=(LedgerLine(debit, amount), LedgerLine(credit, -amount)),
    )


def name_of(deal: CommodityDeal, data: GameData) -> str:
    assert data.commodities is not None
    label = data.commodities.good(deal.good).label
    if deal.supplier and data.suppliers is not None:
        s = data.suppliers.supplier(deal.supplier)
        return f"{label} offtake with {s.name if s else deal.supplier}"
    return f"{label} contract"


def _draw(
    state: GameState, deal: CommodityDeal, cents: float
) -> tuple[CommodityDeal, list[LedgerEntry]]:
    """Purchases funded from the prepayment: cash back against 1200 up to what is left."""
    amount = min(deal.prepaid_left_cents, round(cents))
    if amount <= 0:
        return deal, []
    memo = f"Prepayment drawn: {deal.good}"
    entry = _entry(state.turn, deal.company_id, memo, amount, CASH, PREPAID)
    return replace(deal, prepaid_left_cents=deal.prepaid_left_cents - amount), [entry]


def _close(
    state: GameState, deal: CommodityDeal, status: str, balance: Balance, data: GameData
) -> tuple[CommodityDeal, list[LedgerEntry], list[LogItem]]:
    """A deal ends (or breaches): a contract's take-or-pay on its unused volume, and any
    prepayment left comes back."""
    entries: list[LedgerEntry] = []
    charge = 0
    if deal.kind == "contract" and status == "ended":
        months = deal.end_turn - deal.signed_turn + 1
        unused = max(0.0, deal.monthly_volume * months - deal.taken)
        charge = round(
            value_cents(unused, deal.signing_price, deal.good, data)
            * balance.commodity.contract_take_or_pay
        )
        if charge > 0:
            memo = f"Take-or-pay: unused {name_of(deal, data)}"
            entries.append(_entry(state.turn, deal.company_id, memo, charge, GENERAL_ADMIN, CASH))
    if deal.prepaid_left_cents > 0:
        memo = f"Prepayment returned: {name_of(deal, data)}"
        entries.append(
            _entry(state.turn, deal.company_id, memo, deal.prepaid_left_cents, CASH, PREPAID)
        )
    closed = replace(
        deal,
        status="breached" if status == "breached" else "ended",
        prepaid_left_cents=0,
        charged_cents=deal.charged_cents + charge,
        closed_turn=state.turn,
    )
    kind = "offtake_breached" if status == "breached" else "commodity_deal_ended"
    log = inbox_item(
        state.turn,
        deal.company_id,
        kind,
        deal=name_of(deal, data),
        taken=f"{deal.taken:,.1f}",
        hedge_cents=deal.hedge_cents,
        charge_cents=charge,
    )
    return closed, entries, [log]


def start_of_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Phase 4: deals past their end close; suppliers past their window, or breaking under a
    severe shock, breach (module docstring). Deals in id order."""
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    ob = balance.offtake
    for deal in state.commodity_deals:
        if deal.status != "active":
            continue
        status = None
        if state.turn > deal.end_turn:
            status = "ended"
        elif deal.kind == "offtake" and deal.supplier and data.suppliers is not None:
            s = data.suppliers.supplier(deal.supplier)
            _, until = s.window(deal.good) if s else (0, None)
            if s is None or (until is not None and state.turn > until):
                status = "breached"
            else:
                spot = spot_price(state, deal.good, data, balance)
                if spot >= deal.ceiling * ob.breach.spot_over_ceiling:
                    u = float(commodity.generator(rng, state.turn, BREACH_KEY, deal.id).random())
                    if u < (1 - s.reliability) * ob.breach.monthly_scale:
                        status = "breached"
        if status is None:
            continue
        closed, more, notes = _close(state, deal, status, balance, data)
        state = with_commodity_deal(state, closed)
        entries += more
        logs += notes
    return state, entries, logs


def settle_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry]]:
    """Phase 5, after production: each running deal's take, hedge, take-or-pay and prepayment
    draw (module docstring)."""
    if not any(d.status == "active" for d in state.commodity_deals):
        return state, []
    entries: list[LedgerEntry] = []
    uses: dict[int, dict[str, float]] = {}
    top = balance.offtake.take_or_pay
    for deal in state.commodity_deals:
        if not deal.running(state.turn):
            continue
        if deal.company_id not in uses:
            uses[deal.company_id] = costs.company_use(state, deal.company_id, balance, data)
        use = uses[deal.company_id]
        month = commodity.current(state, deal.good, data)
        start = month.shock_turn if month.allocation < 1 else None
        share = 1.0 if costs.protected(deal, start) else month.allocation
        deliverable = deal.monthly_volume * share
        taken = min(use.get(deal.good, 0.0), deliverable)
        use[deal.good] = use.get(deal.good, 0.0) - taken
        spot = spot_price(state, deal.good, data, balance)
        price = deal.price_for(spot)
        hedge = round(value_cents(taken, price - spot, deal.good, data))
        if hedge:
            memo = f"Cost of goods: {name_of(deal, data)} against spot"
            entries.append(_entry(state.turn, deal.company_id, memo, hedge, COGS, CASH))
        charge = 0
        if deal.kind == "offtake":
            short = max(0.0, top * deliverable - taken)
            charge = round(value_cents(short, price, deal.good, data))
            if charge > 0:
                memo = f"Take-or-pay: {name_of(deal, data)}"
                entries.append(
                    _entry(state.turn, deal.company_id, memo, charge, GENERAL_ADMIN, CASH)
                )
        deal = replace(
            deal,
            taken=deal.taken + taken,
            last_taken=taken,
            last_price=price,
            hedge_cents=deal.hedge_cents - hedge,
            charged_cents=deal.charged_cents + charge,
        )
        if deal.prepaid_left_cents > 0:
            deal, more = _draw(state, deal, value_cents(taken, price, deal.good, data) + charge)
            entries += more
        state = with_commodity_deal(state, deal)
    return state, entries
