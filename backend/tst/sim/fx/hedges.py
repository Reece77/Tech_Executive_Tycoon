"""Currency forwards (docs/formulas.md 64.4, ADR-0025 point 5).

A forward sells `N` of a region's money (N in US cents at today's spot index S_0) for delivery in m
months at the forward index

    F = S_0 x ((1 + r_home) / (1 + r_region)) ** (m / 12) x (1 - spread_bp / 10,000)

(covered interest parity, rates from `rates.policy_rate`; the bank's spread against the seller).
Its fair value in month t is N x (F - S_t) / S_0 (undiscounted, A), booked each month: in the money
in 1340 and out of it in 2340, the month's change to the currency gain or loss line (4940 / 4945,
below the operating result). At settlement (month m) the value is N x (F - S_m) / S_0 exactly and
settles in cash. Hedge accounting is not modelled (ADR-0025 point 5).

A **hedging programme** buys, each month after the markets, a forward on `share` of the month's
net revenue in each foreign region (revenue less local costs), `term_months` ahead: a rolling hedge
(64.6 target 5). The CFO delegate (40) may run one up to `fx.cfo_limit_share`.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import FinservRuleError
from tst.sim.fx.config import MONTHS
from tst.sim.fx.models import FxHedge, FxMonth
from tst.sim.fx.rates import index_at, policy_rate
from tst.sim.ledger import CASH, LedgerEntry, LedgerLine
from tst.sim.money import BP_DENOMINATOR, round_half_even
from tst.sim.state import GameState

HEDGE_ASSETS = "1340_fx_hedge_assets"
HEDGE_LIABILITIES = "2340_fx_hedge_liabilities"
FX_GAINS = "4940_fx_gains"
FX_LOSSES = "4945_fx_losses"
PCT = 100  # tunable-exempt: % a year to a fraction


def forward_index(
    state: GameState, region: str, months: int, balance: Balance, data: GameData
) -> int:
    """F for a forward bought this month (module docstring), x INDEX_SCALE."""
    xb = balance.fx
    spot = index_at(state, region, state.turn, balance, data)
    home = policy_rate(state, xb.home, balance, data) / PCT
    there = policy_rate(state, region, balance, data) / PCT
    carry = dmath.pow((1.0 + home) / (1.0 + there), months / MONTHS)
    spread = 1.0 - xb.spread_bp[region] / BP_DENOMINATOR
    return max(1, round(spot * carry * spread))


def value_cents(h: FxHedge, spot: int) -> int:
    """N x (F - S) / S_0, rounded half to even (exact integers)."""
    return round_half_even(h.notional_cents * (h.forward_index - spot), h.spot_index)


def check_term(months: int, balance: Balance) -> None:
    t = balance.fx.term_months
    if not t.lo <= months <= t.hi:
        raise FinservRuleError(f"a forward runs {int(t.lo)}-{int(t.hi)} months")


def buy(
    state: GameState,
    company_id: int,
    region: str,
    notional_cents: int,
    months: int,
    balance: Balance,
    data: GameData,
    *,
    programme: bool = False,
) -> tuple[GameState, FxHedge]:
    """A forward on `notional_cents` of the region's money, `months` ahead (no cash moves now)."""
    if region == balance.fx.home or region not in data.region_keys:
        raise FinservRuleError("forwards are on a foreign region's money")
    if notional_cents <= 0:
        raise FinservRuleError("a forward's notional must be positive")
    check_term(months, balance)
    h = FxHedge(
        id=state.fx.next_hedge_id(),
        company_id=company_id,
        region=region,
        notional_cents=notional_cents,
        turn=state.turn,
        settle_turn=state.turn + months,
        spot_index=index_at(state, region, state.turn, balance, data),
        forward_index=forward_index(state, region, months, balance, data),
        programme=programme,
    )
    return replace(state, fx=replace(state.fx, hedges=(*state.fx.hedges, h))), h


def _split(values: list[int]) -> tuple[int, int]:
    """(assets, liabilities) of fair values: positives and negatives' magnitude."""
    return sum(v for v in values if v > 0), -sum(v for v in values if v < 0)


def mark_and_settle(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], dict[tuple[int, str], int]]:
    """Every open forward's fair value this month, booked by company; those due settle in cash.
    Returns the settled gains by (company, region)."""
    entries: list[LedgerEntry] = []
    settled: dict[tuple[int, str], int] = {}
    fx = state.fx
    if not any(h.status == "open" for h in fx.hedges):
        return state, entries, settled
    spots: dict[str, int] = {}
    hedges: list[FxHedge] = []
    by_company: dict[int, tuple[list[int], list[int], int]] = {}
    for h in fx.hedges:
        if h.status != "open":
            hedges.append(h)
            continue
        if h.region not in spots:
            spots[h.region] = index_at(state, h.region, state.turn, balance, data)
        new = value_cents(h, spots[h.region])
        before, after, cash = by_company.setdefault(h.company_id, ([], [], 0))
        before.append(h.value_cents)
        if h.settle_turn <= state.turn:
            after.append(0)
            by_company[h.company_id] = (before, after, cash + new)
            key = (h.company_id, h.region)
            settled[key] = settled.get(key, 0) + new
            hedges.append(replace(h, status="settled", value_cents=0, settled_cents=new))
        else:
            after.append(new)
            hedges.append(replace(h, value_cents=new))
    for company_id in sorted(by_company):
        before, after, cash = by_company[company_id]
        a0, l0 = _split(before)
        a1, l1 = _split(after)
        pnl = (a1 - l1 + cash) - (a0 - l0)
        lines = []
        if a1 != a0:
            lines.append(LedgerLine(HEDGE_ASSETS, a1 - a0))
        if l1 != l0:
            lines.append(LedgerLine(HEDGE_LIABILITIES, -(l1 - l0)))
        if cash:
            lines.append(LedgerLine(CASH, cash))
        if pnl > 0:
            lines.append(LedgerLine(FX_GAINS, -pnl))
        elif pnl < 0:
            lines.append(LedgerLine(FX_LOSSES, -pnl))
        if any(line.amount for line in lines):
            entries.append(
                LedgerEntry(
                    turn=state.turn,
                    company_id=company_id,
                    memo="Currency hedges: fair value and settlements",
                    lines=tuple(x for x in lines if x.amount),
                )
            )
    return replace(state, fx=replace(fx, hedges=tuple(hedges))), entries, settled


def net_revenue(state: GameState, company_id: int, region: str) -> int:
    """The company's net revenue in a foreign region last recorded (revenue less local costs)."""
    row = next(
        (
            m
            for m in reversed(state.fx.months)
            if m.company_id == company_id and m.region == region and m.turn == state.turn
        ),
        None,
    )
    return 0 if row is None else row.revenue_cents - row.cost_cents


def exposure_cents(state: GameState, company_id: int, region: str) -> int:
    """The next 12 months' net revenue in the region at this month's rate (positive only)."""
    return max(0, net_revenue(state, company_id, region)) * MONTHS


def open_notional(state: GameState, company_id: int, region: str) -> int:
    return sum(h.notional_cents for h in state.fx.open_hedges(company_id) if h.region == region)


def programme_month(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Each programme's forwards for the month (module docstring)."""
    for p in state.fx.programmes:
        for region in data.region_keys:
            if region == balance.fx.home:
                continue
            net = net_revenue(state, p.company_id, region)
            notional = round_half_even(net * round(p.share * BP_DENOMINATOR), BP_DENOMINATOR)
            if notional <= 0:
                continue
            state, _ = buy(
                state, p.company_id, region, notional, p.term_months, balance, data, programme=True
            )
    return state


_ = FxMonth
