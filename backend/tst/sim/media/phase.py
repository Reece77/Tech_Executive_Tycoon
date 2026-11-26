"""Media's place in the turn (docs/formulas.md 65).

- **New game** (`new_game`): the media markets' demand and history for the first month, and each
  media incumbent's opening capital.
- **Phase 5** before the markets (`open_month`): the history's dated openings (M43r), the ad
  market's calibration at `media.start` and ad-funded lines' prices; (`with_effects`): catalogue
  engagement (video), ad tiers, network effects, formats, moderation and bans (social); after the
  markets (`after_sales`): titles' production, release, revenue and amortisation, ad tiers' ad
  revenue, music payouts, licences, moderation, fines, laws' deadlines, and the player's service
  months.
- **Phase 9** (`demand_month`): growth draws, the regions' draws (strikes, laws, fines), the lead
  pool, deals' ends, seeded format eras and rivals' moves, divest-or-ban laws, demand, the history's
  pin and the ad market's month.

A save without the media markets (made before M55) does nothing here, and a company without media
plays exactly as before (65.8 target 1).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.log import LogItem
from tst.sim.media import ads, demand, history, social, streaming, talent, titles
from tst.sim.media.data import enabled, is_media_rival, selling
from tst.sim.media.models import PaidBack, ServiceMonth
from tst.sim.money import times
from tst.sim.platforms.phase import NO_EFFECTS, Effects
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

STRONG: Final = "strong"  # tunable-exempt: a moderation level


def new_game(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...]]:
    if not enabled(state, balance, data):
        return state, ()
    state = demand.set_demand(state, balance, data)
    state = history.pin(state, balance, data)
    entries = []
    cash = balance.media.rival_cash_cents
    for company in state.rivals():
        if cash > 0 and is_media_rival(company, data):
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=company.id,
                    memo="Opening capital of the media business",
                    debit=CASH,
                    credit=COMMON_EQUITY,
                    amount=cash,
                )
            )
    return state, tuple(entries)


def open_month(state: GameState, balance: Balance, data: GameData) -> GameState:
    if not enabled(state, balance, data):
        return state
    state = history.pin(state, balance, data, openings_only=True)
    state = ads.calibrate(state, balance, data)  # once, at media.start (65.1)
    return ads.set_prices(state, balance, data)


def _regions(state: GameState, product_id: int, home: str) -> list[str]:
    out = [home] if state.segments_of(product_id) else []
    return out + [rs.region for rs in state.regional_segments_of(product_id)]


def with_effects(
    base: Effects | None, state: GameState, balance: Balance, data: GameData
) -> Effects | None:
    """Module docstring: video lines' engagement and ad tiers, social lines' network effects,
    formats, moderation and bans."""
    if not enabled(state, balance, data):
        return base
    mb = balance.media
    b = base if base is not None else NO_EFFECTS
    appeal = dict(b.appeal_mult)
    churn = dict(b.churn_mult)
    share = dict(b.revenue_share)
    cut = dict(b.price_cut)
    home = home_region_of(state, balance, data)
    touched = False
    r = streaming.engagement(state, balance, data)
    for p in state.products:
        if not selling(p):
            continue
        regions = _regions(state, p.id, home)
        if p.category == mb.streaming and p.id in r:
            a, c = streaming.multipliers(r[p.id], balance)
            for region in regions:
                appeal[(p.id, region)] = appeal.get((p.id, region), 1.0) * a
            churn[p.id] = churn.get(p.id, 1.0) * c
            touched = True
            if streaming.ad_tier_on(p, state, data):
                sb = mb.streaming_service
                share[p.id] = share.get(p.id, 1.0) * streaming.paid_share(balance)
                for seg, region in streaming.rows(state, p, home):
                    if seg.price_cents is not None:
                        # money-exact: rate (cents off the price buyers weigh, as M38's subsidy)
                        off = seg.price_cents * sb.ad_tier_take * (1 - sb.ad_tier_price)
                        cut[(p.id, region)] = cut.get((p.id, region), 0.0) + off
        elif p.category == mb.social:
            fmt, _ = social.format_mult(p, state, balance, data)
            s = state.media.setting(p.id)
            strong = mb.social_network.strong_appeal if s and s.moderation == STRONG else 1.0
            shares = social.shares(state, p, balance, data)
            worst = 1.0
            for region in regions:
                a, c = social.network_mults(shares.get(region, 0.0), balance)
                gate = 0.0 if social.banned(state, p.id, region) else 1.0
                appeal[(p.id, region)] = appeal.get((p.id, region), 1.0) * a * fmt * strong * gate
                worst = max(worst, c)
            if regions:
                largest = max(regions, key=lambda x: shares.get(x, 0.0))
                worst = social.network_mults(shares.get(largest, 0.0), balance)[1]
            churn[p.id] = churn.get(p.id, 1.0) * worst
            touched = True
    if not touched:
        return base
    return replace(b, appeal_mult=appeal, churn_mult=churn, revenue_share=share, price_cut=cut)


def _service_months(
    state: GameState,
    spent: dict[int, int],
    extra: dict[int, tuple[int, int, int]],
    costs: dict[int, int],
    balance: Balance,
    data: GameData,
) -> GameState:
    """The player's media lines' months (shown; 65.8 target 3's cash)."""
    mb = balance.media
    player = state.player.id
    rows = []
    paid_back = list(state.media.paid_back)
    r = streaming.engagement(state, balance, data)
    for p in state.company_products(player):
        if p.category not in mb.categories or p.category == mb.games:
            continue
        if not selling(p) and state.media.last_month(p.id) is None:
            continue
        ad, fees, _ = extra.get(p.id, (0, 0, 0))
        revenue = streaming.monthly_revenue_cents(state, p)
        if p.category == mb.streaming and streaming.ad_tier_on(p, state, data):
            revenue = times(revenue, streaming.paid_share(balance))
        content = fees + sum(
            v
            for tid, v in spent.items()
            if (t := state.media.title(tid)) is not None and t.service_product_id == p.id
        )
        cost = costs.get(p.id, 0) + p.marketing_budget_cents
        for seg, _ in streaming.rows(state, p, ""):
            cost += times(data.category(p.category).markets[0].hosting_cents, seg.customers)
        last = state.media.last_month(p.id)
        before = last.cash_cents if last is not None else 0
        cash = before + revenue + ad - content - cost
        if cash >= 0 and before < 0 and not any(x.product_id == p.id for x in paid_back):
            paid_back.append(PaidBack(p.id, state.turn))
        shares = social.shares(state, p, balance, data) if p.category == mb.social else {}
        top = max(shares.values(), default=0.0)
        advantage = (
            social.format_mult(p, state, balance, data)[1] if p.category == mb.social else False
        )
        churn = streaming.multipliers(r[p.id], balance)[1] if p.id in r else 1.0
        rows.append(
            ServiceMonth(
                turn=state.turn,
                product_id=p.id,
                customers=streaming.customers(state, p),
                revenue_cents=revenue,
                ad_revenue_cents=ad,
                content_cents=content,
                costs_cents=cost,
                cash_cents=cash,
                engagement=r.get(p.id, 0.0),
                churn_mult=churn,
                share=top,
                advantage=advantage,
            )
        )
    if not rows and not state.media.months:
        return state
    keep = mb.history_months
    kept = tuple(m for m in state.media.months if m.turn > state.turn - keep)
    media = replace(state.media, months=(*kept, *rows), paid_back=tuple(paid_back))
    return replace(state, media=media)


def after_sales(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not enabled(state, balance, data):
        return state, [], []
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    before = {t.id: t.spent_cents for t in state.media.titles}
    state, more, more_logs = titles.month(state, rng, balance, data)
    entries += more
    logs += more_logs
    spent = {t.id: t.spent_cents - before.get(t.id, 0) for t in state.media.titles}
    state, more, extra = streaming.month(state, balance, data)
    entries += more
    state, more, more_logs, costs = social.month(state, balance, data)
    entries += more
    logs += more_logs
    state = streaming.attribute_revenue(state, balance, data)
    for pid, (_, _, royalties) in extra.items():
        costs[pid] = costs.get(pid, 0) + royalties
    player = state.player.id
    if any(p.category in balance.media.categories for p in state.company_products(player)):
        state = _service_months(state, spent, extra, costs, balance, data)
    return state, entries, logs


def demand_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    if not enabled(state, balance, data):
        return state, []
    logs: list[LogItem] = []
    state = demand.draw_growth(state, rng, balance, data)
    state = ads.ad_growth_month(state, rng, balance)
    state = talent.region_year_month(state, rng, balance, data)
    state = talent.pool_month(state, balance)
    state = talent.deals_month(state)
    state = talent.left_month(state)
    state, more = social.era_month(state, rng, balance, data)
    logs += more
    state, more = social.laws_month(state, balance, data)
    logs += more
    state = demand.set_demand(state, balance, data)
    state = history.pin(state, balance, data)
    return ads.market_month(state, balance, data), logs
