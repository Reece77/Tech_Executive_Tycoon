"""Video and music streaming (docs/formulas.md 65.3).

**Catalogue value.** A video line's catalogue value is, for each released title of its company on
the service (window `own`), the title's audience x its kind's revenue a viewer (its revenue
equivalent, tst.sim.media.titles) x exp(-months since release / `recency_months`), plus each licence
in force: its fee a year x `licence_value` x media.yaml's licence availability that year. A rival's
is its line's revenue a year x `rival_content_share` x the series kind's `revenue_mult` x
`recency_months` / 12 (the steady state of that spend), plus walked leads' titles (decaying the
same way). Relative engagement r = value / the median live video line's value; its appeal is x
r ** `appeal_k` and its churn x r ** -`churn_k`, each clamped to its range: the leader's lower
churn follows its catalogue, not a constant.

**Ad tiers.** From media.yaml's `ad_tier_from` a player's video line may run an ad tier:
`ad_tier_take` of its subscribers pay `ad_tier_price` of the price (so it books 1 - take x (1 -
price share) of its revenue, and buyers weigh a price that much lower) and watch ads: they sell
impressions in the ad market (tst.sim.media.ads), booked to 4080 here.

**Music.** A music line pays `music_payout` of its revenue to rights holders (5160) each month.

**Licences.** A licence's fee a year is paid by twelfths (5170).
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from statistics import median
from typing import Final

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.facilities.config import month_to_turn
from tst.sim.geo.models import RegionalSegment
from tst.sim.ledger import CASH, LedgerEntry
from tst.sim.media import ads
from tst.sim.media.config import KindBalance
from tst.sim.media.data import MONTHS, TINY, end_year_at, file, selling
from tst.sim.media.models import Title
from tst.sim.media.titles import OPERATIONS, OWN, revenue_per_viewer_cents
from tst.sim.money import exact, round_half_even, times
from tst.sim.products.models import Product, ProductSegment
from tst.sim.state import GameState
from tst.sim.vehicles.config import interp

AD_REVENUE: Final = "4080_revenue_advertising"
ROYALTIES: Final = "5160_content_royalties"


def title_value_cents(kind: KindBalance, balance: Balance) -> int:
    """A typical title's revenue equivalent (a walked lead's next title at a rival)."""
    return times(kind.typical_budget_cents, balance.media.scale, kind.revenue_mult)


def rows(
    state: GameState, product: Product, home: str
) -> list[tuple[ProductSegment | RegionalSegment, str]]:
    return [
        *((s, home) for s in state.segments_of(product.id)),
        *((rs, rs.region) for rs in state.regional_segments_of(product.id)),
    ]


def customers(state: GameState, product: Product) -> float:
    return sum(s.customers for s in state.segments_of(product.id)) + sum(
        s.customers for s in state.regional_segments_of(product.id)
    )


def monthly_revenue_cents(state: GameState, product: Product) -> int:
    """Customers x price this month (as phase 5 books it, before an ad tier's share)."""
    total = 0
    rows: list[ProductSegment | RegionalSegment] = [
        *state.segments_of(product.id),
        *state.regional_segments_of(product.id),
    ]
    for s in rows:
        if s.price_cents is not None:
            total += times(s.price_cents, s.customers)
    return total


def recency(age_months: int, balance: Balance) -> float:
    return float(dmath.exp(-max(0, age_months) / balance.media.streaming_service.recency_months))


def own_titles(state: GameState, product: Product) -> list[Title]:
    return [
        t
        for t in state.media.titles
        if t.company_id == product.company_id
        and t.stage == "released"
        and t.window == OWN
        and t.kind != "game"
        and (t.service_product_id in (None, product.id))
    ]


def title_catalogue_value(title: Title, state: GameState, balance: Balance) -> float:
    if title.released_turn is None or title.audience is None:
        return 0.0
    kind = balance.media.kind(title.kind)
    unit = float(revenue_per_viewer_cents(kind, balance))
    return title.audience * unit * recency(state.turn - title.released_turn, balance)


def availability(state: GameState, data: GameData) -> float:
    return interp(file(data).licence_availability, end_year_at(state.turn))


def catalogue_value(state: GameState, product: Product, balance: Balance, data: GameData) -> float:
    """A video line's catalogue value now (module docstring; cents, estimate)."""
    sb = balance.media.streaming_service
    company = state.company(product.company_id)
    value = 0.0
    if company is not None and not company.is_player:
        yearly = monthly_revenue_cents(state, product) * MONTHS
        # money-exact: ratio (a multiplier, not money)
        share = sb.rival_content_share * balance.media.kind("series").revenue_mult
        value += yearly * share * sb.recency_months / MONTHS  # money-exact: estimate
        for b in state.media.rival_bonus:
            if b.company_id == product.company_id:
                value += b.value_cents * recency(
                    state.turn - b.turn, balance
                )  # money-exact: estimate
        return value
    for t in own_titles(state, product):
        value += title_catalogue_value(t, state, balance)
    avail = availability(state, data)
    for lic in state.media.licences:
        if lic.product_id == product.id and lic.from_turn <= state.turn < lic.to_turn:
            value += lic.fee_cents * sb.licence_value * avail  # money-exact: estimate
    return value


def video_lines(state: GameState, balance: Balance) -> list[Product]:
    """Live video lines with subscribers, and the player's own however small."""
    out = []
    for p in state.products:
        if p.category != balance.media.streaming or not selling(p):
            continue
        company = state.company(p.company_id)
        if customers(state, p) > TINY or (company is not None and company.is_player):
            out.append(p)
    return out


def engagement(state: GameState, balance: Balance, data: GameData) -> dict[int, float]:
    """Every live video line's relative engagement r (module docstring)."""
    lines = video_lines(state, balance)
    values = {p.id: catalogue_value(state, p, balance, data) for p in lines}
    positive = [v for v in values.values() if v > 0]
    if not positive:
        return {}
    mid = median(positive)
    return {pid: max(v, TINY) / mid for pid, v in values.items()}


def multipliers(r: float, balance: Balance) -> tuple[float, float]:
    """(appeal, churn) multipliers for relative engagement r."""
    sb = balance.media.streaming_service
    appeal = float(dmath.pow(r, sb.appeal_k))
    churn = float(dmath.pow(r, -sb.churn_k))
    return (
        min(sb.appeal_range.hi, max(sb.appeal_range.lo, appeal)),
        min(sb.churn_range.hi, max(sb.churn_range.lo, churn)),
    )


def ad_tier_open(state: GameState, data: GameData) -> bool:
    return state.turn >= month_to_turn(file(data).ad_tier_from)


def ad_tier_on(product: Product, state: GameState, data: GameData) -> bool:
    s = state.media.setting(product.id)
    return s is not None and s.ad_tier and ad_tier_open(state, data)


def paid_share(balance: Balance) -> float:
    """The share of a line's subscription revenue booked with an ad tier."""
    sb = balance.media.streaming_service
    # money-exact: ratio: a score, share or weight, not money
    return 1.0 - sb.ad_tier_take * (1.0 - sb.ad_tier_price)


def ad_revenue_cents(state: GameState, product: Product, balance: Balance, data: GameData) -> int:
    """An ad-tier line's ad revenue this month (exact where it is posted)."""
    home = home_region_of(state, balance, data)
    total = Fraction()
    for seg, region in rows(state, product, home):
        if seg.customers <= 0:
            continue
        cpm = ads.cpm_cents(state, region, balance, data)
        users = ads.ad_users(product, region, seg.customers, state, balance)
        per = ads.revenue_per_user(product, region, cpm, state, balance, data)
        total += exact(users) * exact(per)
    return round(total)


def licence_month_cents(fee_cents: int, months_in: int) -> int:
    """A yearly licence's month `months_in` (0 first): the difference of consecutive rounded
    cumulative entitlements, so a year books exactly the fee (M57r-A, review 10 item 8: a 7-cent
    licence once collected 12 cents a year)."""
    return round_half_even(fee_cents * (months_in + 1), MONTHS) - round_half_even(
        fee_cents * months_in, MONTHS
    )


def licence_fees_cents(state: GameState, product_id: int) -> int:
    total = 0
    for lic in state.media.licences:
        if lic.product_id == product_id and lic.from_turn <= state.turn < lic.to_turn:
            total += licence_month_cents(lic.fee_cents, state.turn - lic.from_turn)
    return total


def month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], dict[int, tuple[int, int, int]]]:
    """After phase 5's markets: ad tiers' ad revenue, music payouts, licence fees. Returns the
    entries and, by line, (ad revenue, licence fees, royalties) for its service month."""
    entries: list[LedgerEntry] = []
    out: dict[int, tuple[int, int, int]] = {}
    mb = balance.media
    ledger = {c.id for c in state.ledger_companies()}
    for p in state.products:
        if p.company_id not in ledger or not selling(p):
            continue
        if p.category == mb.music:
            payout = times(monthly_revenue_cents(state, p), mb.streaming_service.music_payout)
            if payout:
                out[p.id] = (0, 0, payout)
                entries.append(
                    LedgerEntry.transfer(
                        turn=state.turn,
                        company_id=p.company_id,
                        memo=f"Rights holders' royalties: {p.name}",
                        debit=ROYALTIES,
                        credit=CASH,
                        amount=payout,
                    )
                )
        if p.category != mb.streaming:
            continue
        ad = ad_revenue_cents(state, p, balance, data) if ad_tier_on(p, state, data) else 0
        if ad:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=p.company_id,
                    memo=f"Advertising revenue: {p.name}",
                    debit=CASH,
                    credit=AD_REVENUE,
                    amount=ad,
                )
            )
        fees = licence_fees_cents(state, p.id)
        if fees:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=p.company_id,
                    memo=f"Licensed titles: {p.name}",
                    debit=OPERATIONS,
                    credit=CASH,
                    amount=fees,
                )
            )
        if ad or fees:
            out[p.id] = (ad, fees, 0)
    return state, entries, out


def attribute_revenue(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Each own-window title's share of its service's revenue this month, by catalogue value
    (shown; nothing booked)."""
    titles = list(state.media.titles)
    changed = False
    for p in state.products:
        if p.category != balance.media.streaming or not selling(p):
            continue
        company = state.company(p.company_id)
        if company is None or not company.is_player:
            continue
        mine = own_titles(state, p)
        values = {t.id: title_catalogue_value(t, state, balance) for t in mine}
        total = sum(values.values())
        if total <= 0:
            continue
        revenue = monthly_revenue_cents(state, p)
        for i, t in enumerate(titles):
            if t.id in values:
                share = times(revenue, values[t.id] / total)  # money-exact: ratio
                titles[i] = replace(t, attributed_cents=t.attributed_cents + share)
                changed = True
    if not changed:
        return state
    return replace(state, media=replace(state.media, titles=tuple(titles)))
