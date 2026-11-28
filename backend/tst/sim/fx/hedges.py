"""Currency forwards (docs/formulas.md 64.4, ADR-0025 point 5).

A forward sells `N` of a region's money (N in US cents at today's spot index S_0) for delivery in m
months at the forward index

    F = S_0 x ((1 + r_home) / (1 + r_region)) ** (m / 12) x (1 - spread_bp / 10,000)

(covered interest parity, rates from `rates.policy_rate`; the bank's spread against the seller).
Its fair value in month t is N x (F - S_t) / S_0 (undiscounted, A), recomputed each month and shown
on the Currency screen. At settlement (month m) the value is N x (F - S_m) / S_0 exactly: it settles
in cash and posts to the currency gain or loss line (4940 / 4945, below the operating result) in
that month (ADR-0025 point 5: hedge accounting is not modelled, and nothing is booked before
settlement, M54 decision 10).

A **hedging programme** is a layered rolling hedge (64.6 target 5): each month after the markets,
for each foreign region and each of the next `term_months` months, a forward on share / term of the
month's net revenue (revenue less local costs), so each month is covered by forwards bought over
the year before it (R: large tech groups layer their hedges over a year, the dossier). The CFO
delegate (40) may run one up to `fx.cfo_limit_share`.
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


def mark_and_settle(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], dict[tuple[int, str], int]]:
    """Every open forward's fair value this month (shown); those due settle in cash and post
    their gain or loss. Returns the settled gains by (company, region)."""
    entries: list[LedgerEntry] = []
    settled: dict[tuple[int, str], int] = {}
    fx = state.fx
    if not any(h.status == "open" for h in fx.hedges):
        return state, entries, settled
    spots: dict[str, int] = {}
    hedges: list[FxHedge] = []
    gains: dict[int, int] = {}
    losses: dict[int, int] = {}
    for h in fx.hedges:
        if h.status != "open":
            hedges.append(h)
            continue
        if h.region not in spots:
            spots[h.region] = index_at(state, h.region, state.turn, balance, data)
        value = value_cents(h, spots[h.region])
        if h.settle_turn <= state.turn:
            book = gains if value > 0 else losses  # M57r-A (item 12): never netted
            book[h.company_id] = book.get(h.company_id, 0) + value
            key = (h.company_id, h.region)
            settled[key] = settled.get(key, 0) + value
            hedges.append(replace(h, status="settled", value_cents=0, settled_cents=value))
        else:
            hedges.append(replace(h, value_cents=value))
    for company_id in sorted(set(gains) | set(losses)):
        gain, loss = gains.get(company_id, 0), losses.get(company_id, 0)
        lines = [LedgerLine(CASH, gain + loss)] if gain + loss else []
        if gain:
            lines.append(LedgerLine(FX_GAINS, -gain))
        if loss:
            lines.append(LedgerLine(FX_LOSSES, -loss))
        if gain or loss:
            entries.append(
                LedgerEntry(
                    turn=state.turn,
                    company_id=company_id,
                    memo="Currency forwards settled",
                    lines=tuple(lines),
                )
            )
    return replace(state, fx=replace(fx, hedges=tuple(hedges))), entries, settled


def net_revenue(state: GameState, company_id: int, region: str) -> int:
    """The company's net revenue in a foreign region in the last month recorded (revenue less
    local costs): this month's after the markets, last month's between turns."""
    row = next(
        (
            m
            for m in reversed(state.fx.months)
            if m.company_id == company_id and m.region == region and m.turn <= state.turn
        ),
        None,
    )
    latest = max((m.turn for m in state.fx.months if m.company_id == company_id), default=None)
    if row is not None and row.turn != latest:
        return 0  # nothing earned there in the last month recorded
    return 0 if row is None else row.revenue_cents - row.cost_cents


def exposure_cents(state: GameState, company_id: int, region: str) -> int:
    """The next 12 months' net revenue in the region at this month's rate (positive only)."""
    return max(0, net_revenue(state, company_id, region)) * MONTHS


def open_notional(state: GameState, company_id: int, region: str) -> int:
    return sum(h.notional_cents for h in state.fx.open_hedges(company_id) if h.region == region)


def programme_month(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Each programme's forwards for the month (module docstring): a layered rolling hedge. For
    each foreign region with net revenue this month, one forward for each of the next
    `term_months` months, each on share / term of the month's net revenue, so a month's revenue
    is covered, once the layers are built, by forwards bought over the year before it."""
    for p in state.fx.programmes:
        for region in data.region_keys:
            if region == balance.fx.home:
                continue
            net = net_revenue(state, p.company_id, region)
            layer = round_half_even(
                net * round(p.share * BP_DENOMINATOR), BP_DENOMINATOR * p.term_months
            )
            if layer <= 0:
                continue
            for months in range(1, p.term_months + 1):
                state, _ = buy(
                    state, p.company_id, region, layer, months, balance, data, programme=True
                )
    return state


def prune(state: GameState, balance: Balance) -> GameState:
    """Settled forwards are kept `fx.history_months` after settlement (the Currency screen)."""
    keep = balance.fx.history_months
    kept = tuple(
        h for h in state.fx.hedges if h.status == "open" or h.settle_turn > state.turn - keep
    )
    if len(kept) == len(state.fx.hedges):
        return state
    return replace(state, fx=replace(state.fx, hedges=kept))


_ = FxMonth
