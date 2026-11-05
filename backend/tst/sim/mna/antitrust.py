"""Antitrust's market-share test (docs/formulas.md 28.4, M14 sub-task 4): the highest
combined customer share of the acquirer's group and the target in any category, segment and
region where both sell. Below 0.35 a deal is cleared; up to 0.50 it is reviewed for 3-6
months and then blocked with probability (S_c - 0.35) / 0.15 x strictness(year); from 0.50
it is blocked unless the acquirer accepts a remedy: divesting the target's overlapping
product to the rival with the next-largest share there. Rivals' deals use the same test."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Literal

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import MnaRuleError
from tst.sim.facilities.compute import home_region_of
from tst.sim.log import LogItem, inbox_item
from tst.sim.mna import formulas as mf
from tst.sim.mna.draws import mna_draws
from tst.sim.mna.models import Deal
from tst.sim.products.models import SELLING
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_deal, with_product

FIRST_YEAR = 2010  # tunable-exempt: turn 0 is January 2010
MONTHS_A_YEAR = 12  # tunable-exempt: calendar
REVIEW_TAG = 5  # tunable-exempt: stream mna sub-key of a review's length and outcome

type Market = tuple[str, str, str]  # (category, segment, region)


@dataclass(frozen=True, slots=True)
class AcceptRemedy:
    """Divest the target's overlapping product in the blocking market, then screen again
    (28.4)."""

    actor_id: int
    deal_id: int
    kind: Literal["accept_remedy"] = "accept_remedy"


def owner_of(state: GameState, company_id: int) -> int:
    """The group a company's customers count for: a kept brand's parent (28.4, 28.5)."""
    parent = state.company(company_id).parent_id
    return parent if parent is not None else company_id


def customers_by_market(
    state: GameState, balance: Balance, data: GameData, without: frozenset[int] = frozenset()
) -> dict[Market, dict[int, float]]:
    """Every selling product's customers by market and owning group, home and abroad."""
    home = home_region_of(state, balance, data)
    out: dict[Market, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for product in state.products:
        if product.status not in SELLING or product.id in without:
            continue
        company = state.company(product.company_id)
        if not company.alive:
            continue
        owner = owner_of(state, company.id)
        for s in state.segments_of(product.id):
            out[(product.category, s.segment, home)][owner] += s.customers
        for r in state.regional_segments_of(product.id):
            out[(product.category, r.segment, r.region)][owner] += r.customers
    return out


def combined_share(
    state: GameState,
    acquirer_id: int,
    target_id: int,
    balance: Balance,
    data: GameData,
    without: frozenset[int] = frozenset(),
) -> tuple[float, Market | None]:
    """The highest S_c over markets where both sell, and that market (28.4)."""
    acquirer = owner_of(state, acquirer_id)
    best: tuple[float, Market | None] = (0.0, None)
    for market, owners in sorted(customers_by_market(state, balance, data, without).items()):
        mine, theirs = owners.get(acquirer, 0.0), owners.get(target_id, 0.0)
        total = sum(owners.values())
        if mine <= 0 or theirs <= 0 or total <= 0:
            continue
        share = (mine + theirs) / total
        if share > best[0]:
            best = (share, market)
    return best


def _label(market: Market | None) -> str:
    return "/".join(market) if market is not None else ""


def _remedy_product(state: GameState, target_id: int, market: Market) -> int | None:
    category, segment, _ = market
    for product in state.company_products(target_id):
        if product.category != category or product.status not in SELLING:
            continue
        if any(s.segment == segment for s in state.segments_of(product.id)) or any(
            r.segment == segment for r in state.regional_segments_of(product.id)
        ):
            return product.id
    return None


def screen(
    state: GameState, deal: Deal, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[Deal, list[LogItem]]:
    """A newly agreed deal's antitrust status (28.4): cleared (it closes as agreed), under
    review with its hidden outcome drawn now (stream mna, the target's key), or blocked with
    the remedy named."""
    from tst.sim.mna.deals import key_of

    ab = balance.antitrust
    share, market = combined_share(state, deal.acquirer_id, deal.target_id, balance, data)
    deal = replace(deal, combined_share=share, market=_label(market))
    outcome = mf.antitrust_outcome(share, ab)
    if outcome == "cleared" or market is None:
        return deal, []
    if outcome == "review":
        gen = mna_draws(rng, state.turn, *key_of(state, deal.target_id), REVIEW_TAG)
        lo, hi = ab.review_months
        months = int(gen.integers(lo, hi + 1))
        u = float(gen.random())
        deal = replace(
            deal,
            status="review",
            review_end_turn=state.turn + months,
            close_turn=None,
            blocked_draw=u,
        )
        return deal, []
    remedy = _remedy_product(state, deal.target_id, market)
    return replace(deal, status="blocked", close_turn=None, remedy_product_id=remedy), []


def review_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Phase 7: reviews that have run their months end: blocked if the drawn uniform is
    below the block probability (28.4), else the deal closes this month."""
    logs: list[LogItem] = []
    year = FIRST_YEAR + state.turn // MONTHS_A_YEAR
    for deal in state.deals:
        if deal.status != "review" or deal.review_end_turn is None:
            continue
        if state.turn + 1 < deal.review_end_turn:  # ends at the end of its last month
            continue
        p = mf.block_probability(deal.combined_share, year, balance.antitrust)
        name = state.company(deal.target_id).name
        if deal.blocked_draw is not None and deal.blocked_draw < p:
            deal = replace(deal, status="refused", resolved_turn=state.turn)
            text = f"Regulators blocked the deal for {name} after their review."
        else:
            deal = replace(deal, status="accepted", close_turn=state.turn + 1)
            text = f"Regulators cleared the deal for {name}; it closes this month."
        state = with_deal(state, deal)
        if state.company(deal.acquirer_id).is_player:
            logs.append(_news(state, deal, "Antitrust review over", text))
    return state, logs


def accept_remedy(
    state: GameState,
    action: AcceptRemedy,
    acquirer_id: int,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LogItem]]:
    """Divest the remedy product to the rival with the next-largest share in that market,
    with its customers, then screen the deal again (28.4)."""
    deal = next((d for d in state.deals if d.id == action.deal_id), None)
    if deal is None or deal.acquirer_id != acquirer_id or deal.status != "blocked":
        raise MnaRuleError(f"deal {action.deal_id} has no remedy to accept")
    if deal.remedy_product_id is None:
        raise MnaRuleError("no product can be divested to clear this deal")
    product = state.product(deal.remedy_product_id)
    assert product is not None
    market = tuple(deal.market.split("/"))
    owners = customers_by_market(state, balance, data).get(market, {})  # type: ignore[arg-type]
    excluded = {owner_of(state, acquirer_id), deal.target_id}
    buyers = sorted(
        ((c, -n) for c, n in owners.items() if c not in excluded and n > 0),
        key=lambda x: (x[1], x[0]),
    )
    if not buyers:
        raise MnaRuleError("no other company sells there to take the divested product")
    buyer = buyers[0][0]
    state = with_product(state, replace(product, company_id=buyer))
    rescreened, logs = screen(state, replace(deal, status="accepted"), rng, balance, data)
    if rescreened.status == "accepted":
        rescreened = replace(rescreened, close_turn=state.turn + balance.mna.closing_months)
    state = with_deal(state, rescreened)
    text = (
        f"{product.name} goes to {state.company(buyer).name} with its customers. "
        f"Combined share now {rescreened.combined_share:.0%}."
    )
    return state, [_news(state, rescreened, "Remedy accepted", text), *logs]


def _news(state: GameState, deal: Deal, title: str, detail: str) -> LogItem:
    return inbox_item(
        state.turn,
        deal.acquirer_id,
        "deal_update",
        link_kind="rival",
        link_id=deal.target_id,
        title=title,
        detail=detail,
    )
