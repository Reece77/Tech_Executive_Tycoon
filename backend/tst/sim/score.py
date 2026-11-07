"""The company score (docs/formulas.md 30.1, M15b): a public 0-1,000 rating of any company,
from value, growth, profitability, market leadership and reputation. Computed live for the
API and snapshotted every December and at a game's end; the snapshots give the 3-year growth.

Inputs are public: market cap or V_f (28.1), reported revenue and operating result, market
shares from customers, products' brand and the company's credibility. Never a hidden value."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import LedgerBalances
from tst.sim.modes.models import CompanyScore
from tst.sim.products.models import SELLING
from tst.sim.state import GameState, credibility_of

MONTHS_A_YEAR: Final = 12  # tunable-exempt: calendar
DECEMBER: Final = 11  # tunable-exempt: calendar (turn % 12)
CENTS: Final = 100  # tunable-exempt: cents in a dollar
YEARS_BACK: Final = 3  # tunable-exempt: 30.1 defines growth as the trailing 3-year CAGR

type Market = tuple[str, str, str]  # (category, segment, region)


def score_points(
    value_dollars: float,
    growth: float,
    profit: float,
    leadership: float,
    reputation: float,
    balance: Balance,
) -> float:
    """30.1: 400 x (log10(max(V, $1M)) - 6) / 6 (clamped 0-400) + 200 G + 150 P + 150 L
    + 100 R, the weights and the value scale from balance.score."""
    sb = balance.score
    decades = math.log10(max(value_dollars, sb.value_floor_dollars)) - math.log10(
        sb.value_floor_dollars
    )
    value_part = sb.weight_value * min(max(decades / sb.value_span_decades, 0.0), 1.0)
    return (
        value_part
        + sb.weight_growth * growth
        + sb.weight_profit * profit
        + sb.weight_leadership * leadership
        + sb.weight_reputation * reputation
    )


def growth_part(cagr: float, balance: Balance) -> float:
    """G = clamp(CAGR / score.growth_full, 0, 1)."""
    return min(max(cagr / balance.score.growth_full, 0.0), 1.0)


def profit_part(margin: float, balance: Balance) -> float:
    """P = clamp((margin - score.margin_floor) / score.margin_span, 0, 1)."""
    sb = balance.score
    return min(max((margin - sb.margin_floor) / sb.margin_span, 0.0), 1.0)


def trailing_revenue_cents(state: GameState, company_id: int) -> int:
    """Revenue over the last 12 completed months (MRR at each month end)."""
    return sum(state.company(company_id).mrr_history[-MONTHS_A_YEAR:])


def cagr(state: GameState, company_id: int) -> float:
    """Trailing 3-year revenue CAGR, from the December snapshot 3 years back (or the oldest
    one at least a year back, over its years); 0 with no history. A start from no revenue
    to some counts as full growth."""
    now = trailing_revenue_cents(state, company_id)
    past = [
        s
        for s in state.scores
        if s.company_id == company_id and s.turn <= state.turn - MONTHS_A_YEAR
    ]
    if not past:
        return 0.0
    target = state.turn - YEARS_BACK * MONTHS_A_YEAR
    then = max((s for s in past if s.turn <= target), key=lambda s: s.turn, default=None)
    if then is None:
        then = min(past, key=lambda s: s.turn)
    years = (state.turn - then.turn) / MONTHS_A_YEAR
    if then.revenue_cents <= 0:
        return math.inf if now > 0 else 0.0
    if now <= 0:
        return -1.0
    return float((now / then.revenue_cents) ** (1 / years) - 1)


def trailing_margin(state: GameState, company_id: int) -> float | None:
    """Operating result over revenue for the last 12 completed months (as many as there are);
    None without revenue."""
    company = state.company(company_id)
    n = min(len(company.op_history), len(company.mrr_history), MONTHS_A_YEAR)
    if n == 0:
        return None
    revenue = sum(company.mrr_history[-n:])
    if revenue <= 0:
        return None
    return sum(company.op_history[-n:]) / revenue


def market_revenue(
    state: GameState, data: GameData, balance: Balance
) -> dict[Market, dict[int, float]]:
    """Each market's monthly revenue by company, from customers and public prices; a
    product's home-market segments sell in the home region (as antitrust counts them)."""
    from tst.sim.facilities.compute import home_region_of

    home = home_region_of(state, balance, data)
    out: dict[Market, dict[int, float]] = {}
    for product in state.products:
        if product.status not in SELLING or not state.company(product.company_id).alive:
            continue
        for s in state.segments_of(product.id):
            by = out.setdefault((product.category, s.segment, home), {})
            by[product.company_id] = by.get(product.company_id, 0.0) + s.customers * (
                s.price_cents or 0
            )
        for r in state.regional_segments_of(product.id):
            by = out.setdefault((product.category, r.segment, r.region), {})
            by[product.company_id] = by.get(product.company_id, 0.0) + r.customers * (
                r.price_cents or 0
            )
    return out


def leadership_part(company_id: int, markets: dict[Market, dict[int, float]]) -> float:
    """L: the revenue-weighted share of the company's markets where it holds the largest
    share (ties count for each tied leader)."""
    total = led = 0.0
    for by in markets.values():
        mine = by.get(company_id, 0.0)
        if mine <= 0:
            continue
        size = sum(by.values())
        total += size
        if mine >= max(by.values()):
            led += size
    return led / total if total > 0 else 0.0


def reputation_part(state: GameState, company_id: int, balance: Balance) -> float:
    """R = (mean brand of its selling products + credibility) / 200; a company without a
    credibility record stands at press.cred_start."""
    brands = [p.brand for p in state.company_products(company_id) if p.status in SELLING]
    brand = sum(brands) / len(brands) if brands else 0.0
    cred = credibility_of(state, company_id)
    credibility = cred.value if cred is not None else float(balance.press.cred_start)
    return min(max((brand + credibility) / balance.score.reputation_span, 0.0), 1.0)


def company_score(
    state: GameState,
    company_id: int,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
    markets: dict[Market, dict[int, float]] | None = None,
) -> CompanyScore:
    """The score now (30.1), from public inputs only: a listed company's market cap, else the
    midpoint of its displayed value range (28.1), the estimate anyone sees, never V_f itself."""
    from tst.sim.mna import formulas as mf
    from tst.sim.mna import valuation

    value = valuation.market_cap_cents(state, company_id, balances, balance, data)
    if value is None:
        value = mf.midpoint_cents(
            valuation.value_range_cents(state, company_id, balances, balance, data)
        )
    g = growth_part(cagr(state, company_id), balance)
    margin = trailing_margin(state, company_id)
    p = profit_part(margin, balance) if margin is not None else 0.0
    markets = markets if markets is not None else market_revenue(state, data, balance)
    lead = leadership_part(company_id, markets)
    rep = reputation_part(state, company_id, balance)
    points = score_points(value / CENTS, g, p, lead, rep, balance)
    return CompanyScore(
        company_id=company_id,
        turn=state.turn,
        score=round(points),
        value_cents=value,
        growth=g,
        profit=p,
        leadership=lead,
        reputation=rep,
        revenue_cents=trailing_revenue_cents(state, company_id),
    )


def snapshot_scores(
    state: GameState, balances: LedgerBalances, balance: Balance, data: GameData
) -> GameState:
    """Every December and in the month a game ends, each company in business is scored and
    the scores kept (the growth part reads them back)."""
    ended = state.save_meta.game_state != "active"
    if state.turn % MONTHS_A_YEAR != DECEMBER and not ended:
        return state
    if any(s.turn == state.turn for s in state.scores):
        return state
    markets = market_revenue(state, data, balance)
    new = tuple(
        company_score(state, c.id, balances, balance, data, markets)
        for c in state.ledger_companies()
        if c.alive
    )
    return replace(state, scores=(*state.scores, *new))


def latest_score(state: GameState, company_id: int) -> CompanyScore | None:
    """The company's last snapshot (December or game end)."""
    return max(
        (s for s in state.scores if s.company_id == company_id), key=lambda s: s.turn, default=None
    )
