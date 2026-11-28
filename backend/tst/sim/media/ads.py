"""The advertising market (docs/formulas.md 65.1).

**Spend.** A region's ad spend a year follows media.yaml to 2025 (GroupM, regional shares), then
grows by a rate drawn each January within `ads.growth_after` (stream media (3, 3, year)) x
(consumer confidence / 100) ** `confidence_exponent`. Digital's share follows the data, then closes
`digital_approach` of the gap to `digital_ceiling` a year. In the game: x `media.scale`, a month.

**Impressions.** Ad-funded lines (every social line, a player's streaming line with an ad tier, a
player's consumer app that opted into ad pricing from 2026) sell impressions a user a month:

    hours[category] x ad_load x impressions_per_hour x targeting / 1000 x the price a thousand

Targeting = `targeting_base` + `targeting_quality_weight` x quality / 100, cut by each privacy rule
in force in the region (App Tracking Transparency only on iOS's share of the region, and not on a
company's own platform's users).

**The price a thousand.** Before `media.start` it is media.yaml's social ARPU over a reference
line's impressions (quality `REFERENCE_QUALITY`, load 1), so a social line's revenue a user follows
the data. From then it follows the region's digital spend over the impressions all sellers offer:
cpm = December 2025's x (digital / digital then) x (impressions then / impressions now), recorded
once (`AdRef`), so the price is continuous across 2026.

A social line's price is its revenue a user (set before phase 5's markets, every month): the player
does not price a social network; its ad load is its lever.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim import dmath
from tst.sim.calendar import END_YEAR_2008_READ, turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.finance.macro import confidence_factor, now
from tst.sim.geo.models import RegionalSegment
from tst.sim.media import draws
from tst.sim.media.config import PrivacyDef
from tst.sim.media.data import LAST_YEAR, MONTHS, TINY, end_year_at, file, in_history, selling
from tst.sim.media.models import AdMonth, AdRef, WorldDraw
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_segments
from tst.sim.vehicles.config import interp as _interp


def interp(points: dict[int, float], year: float) -> float:
    """M50b: a year-end series, floored at 2008 from January 2008's read (2007.08)."""
    return _interp(points, year, END_YEAR_2008_READ)


THOUSAND: Final = 1000  # tunable-exempt: a price a thousand impressions
MILLION_F: Final = 1e6  # tunable-exempt: impressions shown in millions
REFERENCE_QUALITY: Final = (
    68.0  # tunable-exempt: Facebook Feed's quality (incumbents.yaml), the data's ARPU
)
AD_GROWTH = "ad_growth"  # tunable-exempt: a WorldDraw kind
SOCIAL, STREAMING, APPS = "social", "streaming", "consumer_apps"  # tunable-exempt: ads.hours keys


def spend_year_cents(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """A region's ad spend a year now (2010 cents, real)."""
    f = file(data).ads
    if in_history(state.turn, balance):
        return f.spend_at(end_year_at(state.turn), region)
    out = f.spend_at(float(LAST_YEAR), region)
    start = balance.media.start_turn
    for turn in range(start, state.turn + 1):
        year = turn_to_ym(turn)[0]
        rate = state.media.draw(AD_GROWTH, year)
        if rate is None:
            rate = balance.media.ads.growth_after.lo
        out *= float(dmath.pow(1.0 + rate, 1.0 / MONTHS))
    conf = confidence_factor(now(state, data).confidence, balance.media.ads.confidence_exponent)
    return out * conf


def digital_share(state: GameState, balance: Balance, data: GameData) -> float:
    f = file(data).ads
    if in_history(state.turn, balance):
        return f.digital_at(end_year_at(state.turn))
    ab = balance.media.ads
    years = (state.turn - balance.media.start_turn + 1) / MONTHS
    gap = ab.digital_ceiling - f.digital_at(float(LAST_YEAR))
    return ab.digital_ceiling - gap * float(dmath.pow(1.0 - ab.digital_approach, years))


def digital_month_cents(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """A region's digital ad spend a month in the game (x scale)."""
    year = spend_year_cents(state, region, balance, data)
    return year * digital_share(state, balance, data) / MONTHS * balance.media.scale


IOS_KEY: Final = "ios"  # platforms.yaml's iOS (ATT applies on its users)


def _privacy_cut(rule: PrivacyDef, region: str, exposed: float) -> float:
    """A rule's cut to a line's targeting: the rule's cut x the share of its impressions
    delivered where the rule bites (M57r-A, review 10 item 15)."""
    if region not in rule.regions:
        return 0.0
    return rule.cut * max(0.0, min(1.0, exposed))


def _ios_users(state: GameState, company_id: int | None, region: str, data: GameData) -> float:
    """The share of the region's device users on iOS not owned by the company: M31's share in the
    game (media.yaml's fixed share before M31's platforms exist)."""
    ios = [p for p in state.platforms if p.key == IOS_KEY]
    if not ios:
        return file(data).ads.ios_share.get(region, 0.0)
    ids = {p.id for p in ios if company_id is None or p.owner_id != company_id}
    return sum(
        r.users for r in state.platform_regions if r.region == region and r.platform_id in ids
    )


def own_platform_share(state: GameState, company_id: int, region: str) -> float:
    """The share of a region's device users on the company's own platforms (65.1: not cut)."""
    owned = {p.id for p in state.platforms if p.owner_id == company_id and p.kind == "device"}
    if not owned:
        return 0.0
    return sum(
        r.users for r in state.platform_regions if r.region == region and r.platform_id in owned
    )


def targeting(
    quality: float,
    company_id: int | None,
    region: str,
    state: GameState,
    balance: Balance,
    data: GameData,
) -> float:
    """A line's targeting quality in a region (module docstring)."""
    ab = balance.media.ads
    base = ab.targeting_base + ab.targeting_quality_weight * quality / 100
    own = own_platform_share(state, company_id, region) if company_id is not None else 0.0
    out = base
    ios: float | None = None
    for rule in file(data).ads.privacy:
        if state.turn >= rule.turn:
            if rule.ios_only:  # ATT: impressions on iOS users the company does not own
                if ios is None:
                    ios = _ios_users(state, company_id, region, data)
                exposed = ios
            else:  # a regional rule (GDPR, DSA): every impression but on its own platforms
                exposed = 1.0 - own
            out *= 1.0 - _privacy_cut(rule, region, exposed)
    return out


def _history_cpm(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """The price a thousand that gives the reference line the data's ARPU (cents, real)."""
    ab = balance.media.ads
    arpu_month = interp(file(data).arpu_cents[region], end_year_at(state.turn)) / MONTHS
    per_user = ab.hours[SOCIAL] * ab.ad_load[SOCIAL] * ab.impressions_per_hour / THOUSAND
    ref = targeting(REFERENCE_QUALITY, None, region, state, balance, data)
    return arpu_month / (per_user * ref)  # money-exact: rate


def cpm_cents(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """The price a thousand impressions in a region now (module docstring; real cents)."""
    if in_history(state.turn, balance):
        return _history_cpm(state, region, balance, data)
    ref = next((r for r in state.media.ad_refs if r.region == region), None)
    if ref is None:
        return _history_cpm(state, region, balance, data)
    digital = digital_month_cents(state, region, balance, data)
    offered = impressions_m(state, region, balance, data)
    # money-exact: rate (a price a thousand, rounded where an amount is posted)
    cpm = ref.cpm_cents * digital / max(ref.digital_cents, TINY)
    return cpm * ref.impressions_m / max(offered, TINY)  # money-exact: rate


def _category_key(product: Product, balance: Balance) -> str | None:
    mb = balance.media
    if product.category == mb.social:
        return SOCIAL
    if product.category == mb.streaming:
        return STREAMING
    if product.category == mb.consumer_apps:
        return APPS
    return None


def ad_mult(product: Product, state: GameState, balance: Balance, data: GameData) -> float:
    """A line's ad load x its arpu_mult (a rival social line's data multiplier) (65.1)."""
    kind = _category_key(product, balance)
    if kind is None:
        return 0.0
    ab = balance.media.ads
    s = state.media.setting(product.id)
    load = ab.ad_load[kind] * (s.ad_load if s is not None and kind == SOCIAL else 1.0)
    company = state.company(product.company_id)
    if company is not None and not company.is_player and kind == SOCIAL:
        row = file(data).line(company.name, product.name)
        load *= row.arpu_mult if row is not None else 1.0
    return load


def sells_ads(product: Product, state: GameState, balance: Balance) -> bool:
    """An ad-funded line now (module docstring)."""
    if not selling(product):
        return False
    mb = balance.media
    if product.category == mb.social:
        return True
    s = state.media.setting(product.id)
    if s is None:
        return False
    if product.category == mb.streaming:
        return s.ad_tier
    return product.category == mb.consumer_apps and s.ad_pricing


def ad_users(
    product: Product, region: str, segment_customers: float, state: GameState, balance: Balance
) -> float:
    """The users who see a line's ads: a streaming line's ad-tier take."""
    if product.category == balance.media.streaming:
        return segment_customers * balance.media.streaming_service.ad_tier_take
    return segment_customers


def revenue_per_user(
    product: Product, region: str, cpm: float, state: GameState, balance: Balance, data: GameData
) -> float:
    """A line's ad revenue a user a month in a region (real cents; module docstring)."""
    kind = _category_key(product, balance)
    if kind is None:
        return 0.0
    ab = balance.media.ads
    t = targeting(product.quality, product.company_id, region, state, balance, data)
    imps = ab.hours[kind] * ad_mult(product, state, balance, data) * ab.impressions_per_hour
    return imps * t / THOUSAND * cpm  # money-exact: rate


def _rows(
    state: GameState, product: Product, home: str
) -> list[tuple[ProductSegment | RegionalSegment, str]]:
    return [
        *((s, home) for s in state.segments_of(product.id)),
        *((rs, rs.region) for rs in state.regional_segments_of(product.id)),
    ]


def impressions_m(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """Targeting-weighted impressions offered in a region a month (millions)."""
    ab = balance.media.ads
    home = home_region_of(state, balance, data)
    total = 0.0
    for p in state.products:
        if not sells_ads(p, state, balance):
            continue
        kind = _category_key(p, balance)
        assert kind is not None
        for seg, r in _rows(state, p, home):
            if r != region or seg.customers <= 0:
                continue
            users = ad_users(p, r, seg.customers, state, balance)
            t = targeting(p.quality, p.company_id, r, state, balance, data)
            total += (
                users
                * ab.hours[kind]
                * ad_mult(p, state, balance, data)
                * ab.impressions_per_hour
                * t
            )
    return total / MILLION_F


def ad_growth_month(state: GameState, rng: RngFactory, balance: Balance) -> GameState:
    """Each January from `media.start`: ad spend's growth for the year (stream media (3, 3,
    year); hidden)."""
    year, month = turn_to_ym(state.turn)
    if state.turn < balance.media.start_turn or month != 1:
        return state
    if state.media.draw(AD_GROWTH, year) is not None:
        return state
    band = balance.media.ads.growth_after
    g = draws.gen(rng, state.turn, draws.WORLD, draws.ADS, year)
    row = WorldDraw(AD_GROWTH, year, "", float(band.lo + (band.hi - band.lo) * g.random()))
    return replace(state, media=replace(state.media, draws=(*state.media.draws, row)))


def calibrate(state: GameState, balance: Balance, data: GameData) -> GameState:
    """From `media.start`: each region's reference market, once, at the first month anyone sells
    ads there (module docstring). At `media.start` the reference is the December 2025 market at
    the history's price. A region nobody sells ads in yet (a Sandbox without rivals, a custom start
    without the social incumbents) keeps the history's price until a seller arrives, then
    calibrates at digital spend / the impressions offered, capped at the history's price (M57r-A,
    review 10 item 14: a reference of 1e-9 impressions priced every line at the 1-cent floor)."""
    if state.turn < balance.media.start_turn:
        return state
    have = {r.region for r in state.media.ad_refs}
    missing = [r for r in data.region_keys if r not in have]
    if not missing:
        return state
    refs = list(state.media.ad_refs)
    for region in missing:
        offered = impressions_m(state, region, balance, data)
        if offered <= TINY:
            continue
        digital = digital_month_cents(state, region, balance, data)
        cpm = _history_cpm(state, region, balance, data)
        if state.turn > balance.media.start_turn:
            # money-exact: rate (a price a thousand from the month's spend)
            cpm = min(cpm, digital / (offered * THOUSAND))
        refs.append(
            AdRef(region=region, impressions_m=offered, cpm_cents=cpm, digital_cents=digital)
        )
    if len(refs) == len(state.media.ad_refs):
        return state
    refs.sort(key=lambda r: data.region_keys.index(r.region))
    return replace(state, media=replace(state.media, ad_refs=tuple(refs)))


def set_prices(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Every social line's price, and a consumer app's with ad pricing, is its ad revenue a user
    (module docstring): a player's always, a rival's from `media.start` (history.pin sets it
    before). In the game's cents a user (prices are real; customers carry the scale)."""
    history = in_history(state.turn, balance)
    mb = balance.media
    home = home_region_of(state, balance, data)
    cpm = {r: cpm_cents(state, r, balance, data) for r in data.region_keys}
    rows: list[ProductSegment] = []
    regional: list[RegionalSegment] = []
    for p in state.products:
        if not selling(p) and p.status != "in_development":
            continue
        company = state.company(p.company_id)
        if company is None:
            continue
        social = p.category == mb.social
        s = state.media.setting(p.id)
        apps = p.category == mb.consumer_apps and s is not None and s.ad_pricing
        if not (social or apps):
            continue
        if history and social and not company.is_player:
            continue  # history.pin's
        for seg, region in _rows(state, p, home):
            if seg.price_cents is None and not company.is_player:
                continue  # not yet open (history.pin opens it)
            price = max(1, round(revenue_per_user(p, region, cpm[region], state, balance, data)))
            if price == seg.price_cents:
                continue
            if isinstance(seg, RegionalSegment):
                regional.append(replace(seg, price_cents=price))
            else:
                rows.append(replace(seg, price_cents=price))
    if not rows and not regional:
        return state
    return with_segments(state, rows, regional)


def engine_priced(state: GameState, product: Product, balance: Balance) -> bool:
    """A line whose price the engine sets each month in US cents from the ad market (a social
    line, an ad-priced app): translation never applies to it (M57r-A, review 10 item 10)."""
    mb = balance.media
    if product.category == mb.social:
        return True
    s = state.media.setting(product.id)
    return product.category == mb.consumer_apps and s is not None and s.ad_pricing


def market_month(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Phase 9: each region's ad market this month (shown, kept `history_months`)."""
    out = []
    for region in data.region_keys:
        # money-exact: display (a month's spend, shown; rounded once where stored)
        spend = spend_year_cents(state, region, balance, data) / MONTHS * balance.media.scale
        out.append(
            AdMonth(
                turn=state.turn,
                region=region,
                spend_cents=round(spend),
                digital_cents=round(digital_month_cents(state, region, balance, data)),
                impressions_m=impressions_m(state, region, balance, data),
                cpm_cents=cpm_cents(state, region, balance, data),
            )
        )
    keep = balance.media.history_months
    kept = tuple(m for m in state.media.ad_months if m.turn > state.turn - keep)
    return replace(state, media=replace(state.media, ad_months=(*kept, *out)))
