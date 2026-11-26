"""Social networks (docs/formulas.md 65.5).

**Network effect.** A social line's share of a region's users is its users there over the region's
internet users (x 10^6 x scale). Its appeal there is x (share / `share_ref`) ** `network_k` and its
churn x (`share_ref` / share) ** `churn_k`, each clamped to its range: under `share_ref` a network
is worth less to each user than its rivals and loses them.

**Format eras.** media.yaml's dated formats (feed, photos, stories, short video), then seeded eras
from `media.start` every `format_every` years (stream media (3, 0, year)). A line on the newest
format within `advantage_years` of its arrival has appeal x `format_advantage`; a line an era behind
the newest x `old_format` (per era). A player's network is on the format it was set to (or, unset,
the newest when it was made); switching (Social screen) costs `switch_quality_cut` of its quality.
A rival network moves to a seeded era `rival_adopt_years` after it arrives (stream media (5,
product id, year)).

**Moderation.** A line pays `moderation_cents` a user a month x its level's multiplier, x
`dsa_mult` in Europe from `dsa_from` (5170). Light moderation in Europe from then risks a fine each
January (`light_fine_chance`, the region's draw) of `fine_share` of the region's revenue a year
(6970); strong moderation's appeal is x `strong_appeal`.

**Divest or ban.** From `media.start`, each January, a player's network with at least
`divest_min_share` of a region's users, whose company's home bloc differs from the region's main
country's, may face a law (`divest_chance`, the region's draw): divest by `divest_notice_months`
(sell the region's users for `divest_revenue_mult` years of its revenue there, 4930) or be banned
there at the deadline (its users there leave; it cannot sell there again). ByteDance's US law of
April 2024 is history (media.yaml) and changes nothing.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Final

from tst.sim import dmath
from tst.sim.calendar import format_turn, turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.facilities.config import month_to_turn
from tst.sim.geo.models import RegionalSegment
from tst.sim.ledger import CASH, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.media import draws
from tst.sim.media.config import MILLION
from tst.sim.media.data import MONTHS, TINY, file, selling
from tst.sim.media.demand import internet_users
from tst.sim.media.models import DivestLaw, RivalFormat, WorldDraw
from tst.sim.media.titles import OPERATIONS
from tst.sim.money import exact, times
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_segments

FINES: Final = "6970_fines"
GAIN: Final = "4930_gain_on_disposal"
ERA = "era"  # tunable-exempt: WorldDraw kinds
FINE = "fine"
LAW = "law"
EUROPE = "europe"  # tunable-exempt: the DSA's region
LIGHT, STRONG = "light", "strong"  # tunable-exempt: moderation levels
JANUARY: Final = 1


def eras(state: GameState, data: GameData) -> list[tuple[str, int]]:
    """Every format era (key, its first month) that has arrived, oldest first."""
    out = [(f.key, f.turn) for f in file(data).formats if f.turn <= state.turn]
    out += [
        (d.key, int(d.value)) for d in state.media.draws if d.kind == ERA and d.value <= state.turn
    ]
    return sorted(out, key=lambda x: (x[1], x[0]))


def arrived_formats(state: GameState, data: GameData) -> tuple[str, ...]:
    return tuple(k for k, _ in eras(state, data))


def format_label(key: str, data: GameData, balance: Balance) -> str:
    f = next((x for x in file(data).formats if x.key == key), None)
    if f is not None:
        return f.label
    return key.replace("_", " ").capitalize()


def line_format(product: Product, state: GameState, data: GameData) -> str | None:
    company = state.company(product.company_id)
    if company is not None and not company.is_player:
        moved = [
            r
            for r in state.media.rival_formats
            if r.product_id == product.id and r.since_turn <= state.turn
        ]
        if moved:
            return moved[-1].format
        row = file(data).line(company.name, product.name)
        return row.format if row is not None else None
    s = state.media.setting(product.id)
    if s is not None and s.format is not None:
        return s.format
    made = [k for k, t in eras(state, data) if t <= product.created_turn]
    return made[-1] if made else (arrived_formats(state, data) or (None,))[0]


def format_mult(
    product: Product, state: GameState, balance: Balance, data: GameData
) -> tuple[float, bool]:
    """(appeal x, on the newest format within its window) (module docstring)."""
    sb = balance.media.social_network
    arrived = eras(state, data)
    mine = line_format(product, state, data)
    if not arrived or mine is None:
        return 1.0, False
    keys = [k for k, _ in arrived]
    newest, since = arrived[-1]
    if mine == newest:
        advantage = state.turn - since < sb.advantage_years * MONTHS
        return (sb.format_advantage if advantage else 1.0), advantage
    behind = len(keys) - 1 - keys.index(mine) if mine in keys else len(keys)
    return float(dmath.pow(sb.old_format, behind)), False


def region_users(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """A region's internet users in the game (x 10^6 x scale)."""
    return internet_users(state, region, balance, data) * MILLION * balance.media.scale


def _rows(
    state: GameState, product: Product, home: str
) -> list[tuple[ProductSegment | RegionalSegment, str]]:
    return [
        *((s, home) for s in state.segments_of(product.id)),
        *((rs, rs.region) for rs in state.regional_segments_of(product.id)),
    ]


def shares(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> dict[str, float]:
    """The line's share of each region's internet users."""
    home = home_region_of(state, balance, data)
    out: dict[str, float] = {}
    for seg, region in _rows(state, product, home):
        users = region_users(state, region, balance, data)
        out[region] = out.get(region, 0.0) + (seg.customers / users if users > 0 else 0.0)
    return out


def network_mults(share: float, balance: Balance) -> tuple[float, float]:
    """(appeal x, churn x) for a share of a region's users (module docstring)."""
    sb = balance.media.social_network
    s = max(share, TINY)
    appeal = float(dmath.pow(s / sb.share_ref, sb.network_k))
    churn = float(dmath.pow(sb.share_ref / s, sb.churn_k))
    return (
        min(sb.appeal_range.hi, max(sb.appeal_range.lo, appeal)),
        min(sb.churn_range.hi, max(sb.churn_range.lo, churn)),
    )


def banned(state: GameState, product_id: int, region: str) -> bool:
    return any(
        x.product_id == product_id and x.region == region and x.status in ("banned", "divested")
        for x in state.media.laws
    )


def era_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Each January from `media.start`: the next seeded era, drawn when none is pending (stream
    media (3, 0, year)); rival networks' moves to an era that has just arrived (stream media (5,
    product id, year))."""
    sb = balance.media.social_network
    year, month = turn_to_ym(state.turn)
    logs: list[LogItem] = []
    if state.turn < balance.media.start_turn:
        return state, logs
    media = state.media
    if month == JANUARY:
        pending = [d for d in media.draws if d.kind == ERA and d.value > state.turn]
        if not pending:
            latest = max(t for _, t in eras(state, data))
            g = draws.gen(rng, state.turn, draws.WORLD, draws.ERA, year)
            gap = sb.format_every.lo + (sb.format_every.hi - sb.format_every.lo) * float(g.random())
            when = max(state.turn + 1, latest + round(gap * MONTHS))
            n = len([d for d in media.draws if d.kind == ERA]) + 1
            names = sb.format_names
            key = names[(n - 1) % len(names)] if names else f"format_{n}"
            if any(d.kind == ERA and d.key == key for d in media.draws):
                key = f"{key}_{n}"
            media = replace(media, draws=(*media.draws, WorldDraw(ERA, year, key, float(when))))
    arrived = [d for d in media.draws if d.kind == ERA and int(d.value) == state.turn]
    for era in arrived:
        moves = list(media.rival_formats)
        for p in state.products:
            if p.category != balance.media.social or not selling(p):
                continue
            company = state.company(p.company_id)
            if company is None or company.is_player:
                if company is not None and company.is_player:
                    logs.append(
                        inbox_item(
                            state.turn,
                            company.id,
                            "media_format_era",
                            link_kind="product",
                            link_id=p.id,
                            format=format_label(era.key, data, balance),
                            product=p.name,
                        )
                    )
                continue
            g = draws.gen(rng, state.turn, draws.RIVAL, p.id, year)
            band = sb.rival_adopt_years
            delay = band.lo + (band.hi - band.lo) * float(g.random())
            moves.append(RivalFormat(p.id, era.key, state.turn + round(delay * MONTHS)))
        media = replace(media, rival_formats=tuple(moves))
    if media is state.media:
        return state, logs
    return replace(state, media=media), logs


def moderation_cents(product: Product, state: GameState, balance: Balance, data: GameData) -> int:
    """A social line's moderation this month (module docstring)."""
    sb = balance.media.social_network
    s = state.media.setting(product.id)
    level = s.moderation if s is not None else "standard"
    home = home_region_of(state, balance, data)
    dsa = state.turn >= month_to_turn(sb.dsa_from)
    total = Fraction()
    for seg, region in _rows(state, product, home):
        mult = sb.moderation_mult[level] * (sb.dsa_mult if dsa and region == EUROPE else 1.0)
        total += exact(seg.customers) * exact(sb.moderation_cents) * exact(mult)
    return round(total)


def region_revenue_cents(
    state: GameState, product: Product, region: str, balance: Balance, data: GameData
) -> int:
    home = home_region_of(state, balance, data)
    return sum(
        times(seg.price_cents, seg.customers)
        for seg, r in _rows(state, product, home)
        if r == region and seg.price_cents is not None
    )


def month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem], dict[int, int]]:
    """After phase 5: moderation, light moderation's fines, laws' deadlines. Also returns each
    line's moderation this month."""
    mb = balance.media
    costs: dict[int, int] = {}
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    ledger = {c.id for c in state.ledger_companies()}
    year, month_ = turn_to_ym(state.turn)
    for p in state.products:
        if p.category != mb.social or not selling(p) or p.company_id not in ledger:
            continue
        cost = moderation_cents(p, state, balance, data)
        costs[p.id] = cost
        if cost:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=p.company_id,
                    memo=f"Moderation: {p.name}",
                    debit=OPERATIONS,
                    credit=CASH,
                    amount=cost,
                )
            )
        company = state.company(p.company_id)
        s = state.media.setting(p.id)
        if (
            company is not None
            and company.is_player
            and month_ == JANUARY
            and s is not None
            and s.moderation == LIGHT
            and state.turn >= month_to_turn(mb.social_network.dsa_from)
        ):
            u = state.media.draw(FINE, year, EUROPE)
            if u is not None and u < mb.social_network.light_fine_chance:
                fine = times(
                    region_revenue_cents(state, p, EUROPE, balance, data),
                    MONTHS,
                    mb.social_network.fine_share,
                )
                if fine:
                    entries.append(
                        LedgerEntry.transfer(
                            turn=state.turn,
                            company_id=p.company_id,
                            memo=f"Digital Services Act fine: {p.name}",
                            debit=FINES,
                            credit=CASH,
                            amount=fine,
                        )
                    )
                    logs.append(
                        inbox_item(
                            state.turn,
                            p.company_id,
                            "media_dsa_fine",
                            link_kind="product",
                            link_id=p.id,
                            product=p.name,
                            fine_cents=fine,
                        )
                    )
    state, more = _deadlines(state, balance, data)
    return state, entries, logs + more, costs


def _clear_region(
    state: GameState, product_id: int, region: str, balance: Balance, data: GameData
) -> GameState:
    product = state.product(product_id)
    assert product is not None
    home = home_region_of(state, balance, data)
    rows: list[ProductSegment] = []
    regional: list[RegionalSegment] = []
    for seg, r in _rows(state, product, home):
        if r != region:
            continue
        if isinstance(seg, RegionalSegment):
            regional.append(replace(seg, customers=0.0))
        else:
            rows.append(replace(seg, customers=0.0))
    return with_segments(state, rows, regional)


def _deadlines(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    logs: list[LogItem] = []
    laws = list(state.media.laws)
    changed = False
    for i, law in enumerate(laws):
        if law.status != "pending" or state.turn < law.deadline_turn:
            continue
        product = state.product(law.product_id)
        laws[i] = replace(law, status="banned")
        changed = True
        state = _clear_region(state, law.product_id, law.region, balance, data)
        if product is not None:
            logs.append(
                inbox_item(
                    state.turn,
                    product.company_id,
                    "media_banned",
                    link_kind="product",
                    link_id=product.id,
                    product=product.name,
                    region=data.region(law.region).label,
                )
            )
    if changed:
        state = replace(state, media=replace(state.media, laws=tuple(laws)))
    return state, logs


def _home_bloc(state: GameState, company_id: int, balance: Balance, data: GameData) -> str | None:
    from tst.sim.geopolitics.world import bloc_of, company_country

    company = state.company(company_id)
    if company is None or data.countries is None:
        return None
    return bloc_of(data, company_country(state, company, balance, data), state.turn)


def _region_bloc(region: str, state: GameState, data: GameData) -> str | None:
    from tst.sim.geopolitics.world import bloc_of, countries_of

    if data.countries is None:
        return None
    return bloc_of(data, countries_of(data).default_of(region).key, state.turn)


def laws_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Each January from `media.start`: seeded divest-or-ban laws (module docstring)."""
    sb = balance.media.social_network
    year, month_ = turn_to_ym(state.turn)
    if state.turn < balance.media.start_turn or month_ != JANUARY:
        return state, []
    logs: list[LogItem] = []
    laws = list(state.media.laws)
    for p in state.products:
        if p.category != balance.media.social or not selling(p):
            continue
        company = state.company(p.company_id)
        if company is None or not company.is_player:
            continue
        mine = _home_bloc(state, p.company_id, balance, data)
        for region, share in sorted(shares(state, p, balance, data).items()):
            if share < sb.divest_min_share or banned(state, p.id, region):
                continue
            if any(x.product_id == p.id and x.region == region for x in laws):
                continue
            theirs = _region_bloc(region, state, data)
            if mine is None or theirs is None or mine == theirs:
                continue
            u = state.media.draw(LAW, year, region)
            if u is None or u >= sb.divest_chance:
                continue
            law = DivestLaw(
                id=max((x.id for x in laws), default=0) + 1,
                product_id=p.id,
                region=region,
                announced_turn=state.turn,
                deadline_turn=state.turn + sb.divest_notice_months,
            )
            laws.append(law)
            logs.append(
                inbox_item(
                    state.turn,
                    company.id,
                    "media_divest_law",
                    link_kind="product",
                    link_id=p.id,
                    product=p.name,
                    region=data.region(region).label,
                    deadline=format_turn(law.deadline_turn),
                )
            )
    if len(laws) == len(state.media.laws):
        return state, logs
    return replace(state, media=replace(state.media, laws=tuple(laws))), logs


def divest(
    state: GameState, company_id: int, law_id: int, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Sell a social line's users in a region a pending law names (module docstring)."""
    from tst.sim.errors import MediaRuleError

    law = next((x for x in state.media.laws if x.id == law_id), None)
    product = state.product(law.product_id) if law is not None else None
    if (
        law is None
        or product is None
        or product.company_id != company_id
        or law.status != "pending"
    ):
        raise MediaRuleError("no pending law to divest under")
    price = times(
        region_revenue_cents(state, product, law.region, balance, data),
        MONTHS,
        balance.media.social_network.divest_revenue_mult,
    )
    state = _clear_region(state, product.id, law.region, balance, data)
    laws = tuple(replace(x, status="divested") if x.id == law_id else x for x in state.media.laws)
    state = replace(state, media=replace(state.media, laws=laws))
    entries = []
    if price:
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=company_id,
                memo=f"Divested {product.name} in {data.region(law.region).label}",
                debit=CASH,
                credit=GAIN,
                amount=price,
            )
        )
    return state, entries, []
