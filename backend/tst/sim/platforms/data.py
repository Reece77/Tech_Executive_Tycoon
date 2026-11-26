"""Platforms' data lookups (docs/formulas.md 44, platforms.yaml): historical shares, fee
schedules, dated rules and developers; and materialising the historical platforms."""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Final

from tst.sim import dmath
from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.modes.models import world_start_turn
from tst.sim.platforms import formulas as pf
from tst.sim.platforms.config import OTHER, PlatformsFile
from tst.sim.platforms.models import DeviceRun, Platform, PlatformRegion, RivalStore, Standard
from tst.sim.state import GameState

FIRST_YEAR: Final = 2010  # tunable-exempt: turn 0's year
DEVICES: Final = "devices"  # tunable-exempt: the device category platforms run on (44.1)
ANDROID: Final = "android_play"  # tunable-exempt: the default licensed platform (44.1)
ANDROID_FAMILY: Final = ("android_play", "android_china")  # tunable-exempt: one OS, two stores
OWN_ID_FROM: Final = 100  # tunable-exempt: ids of platforms founded in play start here
EVEN: Final = 0.5  # tunable-exempt: a contest not yet tipped starts even
CATALOGUE_START: Final = 12.0  # tunable-exempt: months of attention a platform starts with


def enabled(data: GameData) -> bool:
    return data.platforms is not None


def file(data: GameData) -> PlatformsFile:
    assert data.platforms is not None
    return data.platforms


def year_of(turn: int) -> int:
    return FIRST_YEAR + turn // MONTHS_PER_YEAR


def in_history(turn: int, data: GameData) -> bool:
    return turn <= file(data).history_end_turn


def data_shares(data: GameData, region: str, turn: int) -> dict[str, float]:
    """The region's user shares in the turn's year (44.1); the last year after the history."""
    years = file(data).user_shares[region]
    year = min(year_of(turn), max(years))
    return dict(years[max(y for y in years if y <= year)] if year not in years else years[year])


def region_weights(data: GameData) -> dict[str, float]:
    """Each region's share of developers: categories.yaml's market sizes (A, platforms.yaml)."""
    sizes = {m.region: m.size for m in data.region_markets} or {r: 1.0 for r in data.region_keys}
    total = sum(sizes.get(r, 0.0) for r in data.region_keys)
    return {r: sizes.get(r, 0.0) / total for r in data.region_keys}


def developers(data: GameData, balance: Balance, turn: int) -> float:
    """Professional developers worldwide, millions (platforms.yaml; linear between points)."""
    points = sorted(file(data).developers_by_year.items())
    t = year_of(turn) + (turn % MONTHS_PER_YEAR) / MONTHS_PER_YEAR
    if t <= points[0][0]:
        return points[0][1]
    for (y0, v0), (y1, v1) in pairwise(points):
        if y0 <= t <= y1:
            return v0 + (v1 - v0) * (t - y0) / (y1 - y0)
    last_year, last = points[-1]
    return float(last * dmath.pow(1 + balance.platforms.developer_growth, t - last_year))


# --- Fee schedules (44.4) ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Schedule:
    """A platform's schedule in a region at a turn: what the API shows and the fee uses."""

    standard: float
    small_rate: float | None = None
    small_threshold_cents: int | None = None
    sub_rate: float | None = None
    sub_after_year: bool = False
    regulated: tuple[tuple[str, float, float], ...] = ()  # (part, share of the region, rate)


def schedule(
    platform: Platform,
    region: str,
    turn: int,
    balance: Balance,
    data: GameData,
    stores: tuple[RivalStore, ...] = (),
) -> Schedule:
    pb = balance.platforms
    standard = 0.30 if not platform.historical else 0.0  # tunable-exempt: an own store's default
    small: tuple[float, int] | None = None
    sub: tuple[float, bool] | None = None
    regulated: dict[str, tuple[float, float]] = {}
    if platform.historical:
        for rule in file(data).fee_rules:
            if rule.platform != platform.key or rule.from_turn > turn:
                continue
            if rule.kind == "standard":
                standard = rule.rate
            elif rule.kind == "small_business":
                assert rule.threshold_cents is not None
                small = (rule.rate, rule.threshold_cents)
            elif rule.kind == "subscription":
                sub = (rule.rate, rule.after_year)
            elif rule.region == region and rule.part is not None:
                share = file(data).part_share(region, rule.part) * pb.alternative_share
                regulated[rule.part] = (share, rule.rate)
    if platform.fee is not None and not in_history(turn, data):
        standard = platform.fee
    for r_region, part, kind, from_turn, rate in platform.regulated:  # M34 (48.2)
        if r_region == region and kind == "fee_cap" and from_turn <= turn:
            standard = min(standard, rate)
        elif r_region == region and kind == "alt_payments" and from_turn <= turn:
            share = (file(data).part_share(region, part) if part else 1.0) * pb.alternative_share
            regulated.setdefault(part or region, (share, rate))
    for store in stores:  # alternative stores (44.8): a path on the side-loading share
        if (
            store.platform_id == platform.id
            and store.region == region
            and store.opened_turn <= turn
        ):
            share = allows_side_loading(data, platform, region, turn) * pb.alternative_share
            regulated[f"store:{store.name}"] = (share, store.rate)
    return Schedule(
        standard=standard,
        small_rate=small[0] if small else None,
        small_threshold_cents=small[1] if small else None,
        sub_rate=sub[0] if sub else None,
        sub_after_year=sub[1] if sub else False,
        regulated=tuple((part, s, r) for part, (s, r) in sorted(regulated.items())),
    )


def fee_for(
    sched: Schedule,
    category: str,
    seller_year_cents: int,
    steering: bool,
    balance: Balance,
) -> float:
    """The effective fee a seller pays (44.4) on its store revenue in a category."""
    app = balance.platforms.app_categories[category]
    small = (
        sched.small_threshold_cents is not None and seller_year_cents < sched.small_threshold_cents
    )
    regulated = [(share, rate) for _, share, rate in sched.regulated]
    if steering and regulated:  # a steering seller sends more through the outside path
        regulated = [
            (
                min(
                    1.0, share / balance.platforms.alternative_share * balance.platforms.steer_share
                ),
                rate,
            )
            for share, rate in regulated
        ]
    return pf.effective_fee(
        sched.standard,
        sched.small_rate,
        small,
        sched.sub_rate,
        sched.sub_after_year,
        app.subscription_share,
        app.renewal_share,
        regulated,
    )


def rule_active(data: GameData, platform: Platform, region: str, kind: str, turn: int) -> float:
    """The share of the region a dated rule of this kind covers for the platform (0 = none):
    platforms.yaml's for a historical platform, and regulators' duties (M34, 48.2) on any."""
    share = 0.0
    seen: set[str] = set()
    for r_region, part, r_kind, from_turn, _rate in platform.regulated:
        if r_region == region and r_kind == kind and from_turn <= turn and part not in seen:
            seen.add(part)
            share += file(data).part_share(region, part) if part else 1.0
    if not platform.historical:
        return min(1.0, share)
    for r in file(data).rules:
        if (
            r.kind == kind
            and r.region == region
            and platform.key in r.platforms
            and r.from_turn <= turn
        ):
            share += file(data).part_share(region, r.part)
    return min(1.0, share)


def allows_side_loading(data: GameData, platform: Platform, region: str, turn: int) -> float:
    """Share of the region where other stores may serve this platform's users (44.5, 44.8)."""
    if platform.side_loading:
        return 1.0
    return rule_active(data, platform, region, "side_loading", turn)


# --- Materialising (44.1) -----------------------------------------------------------------------


def historical_platforms_from_file(data: GameData) -> tuple[Platform, ...]:
    """The historical platforms with no owners resolved (the fee calibration's view)."""
    return _historical(data, {}, 0)


def historical_platforms(state: GameState, data: GameData) -> tuple[Platform, ...]:
    return _historical(data, {c.name: c.id for c in state.companies}, world_start_turn(state.mode))


def _historical(data: GameData, owners: dict[str, int], first: int) -> tuple[Platform, ...]:
    """`first` (M50): the world's first month; a store with no date ("before 2010") and an
    earlier open-source base count from it (turn 0 in a 2010 game, as before)."""
    out = []
    for i, p in enumerate(file(data).platforms):
        out.append(
            Platform(
                id=i,
                key=p.key,
                name=p.name,
                store=p.store,
                kind=p.kind,
                owner_id=owners.get(p.owner) if p.owner else None,
                owner_label=p.owner_label,
                regions=tuple(p.regions or data.region_keys),
                launched_turn=p.opened_turn if p.store_opened else first,
                ended_turn=p.ended_turn,
                licensable=p.licensable,
                side_loading=p.side_loading,
                open_turn=None if p.open_source is None else max(first, _turn(p.open_source)),
            )
        )
    return tuple(out)


def _turn(text: str) -> int:
    from tst.sim.facilities.config import month_to_turn

    return month_to_turn(text)


def default_platform(state: GameState, product_id: int, data: GameData) -> int:
    """A device line's platform without a choice: its company's own historical platform (Apple's
    iPhone on iOS), else Android (44.1)."""
    product = state.product(product_id)
    keys = {p.key: p.id for p in state.platforms}
    if product is not None:
        for p in state.platforms:
            if p.historical and p.owner_id == product.company_id and p.ended_turn is None:
                return p.id
    return keys[ANDROID]


def ensure_runs(state: GameState, data: GameData) -> GameState:
    """Every device line not retired has a platform (44.1)."""
    have = {d.product_id for d in state.device_runs}
    new = [
        DeviceRun(p.id, default_platform(state, p.id, data), state.turn)
        for p in state.products
        if p.category == DEVICES and p.status != "retired" and p.id not in have
    ]
    if not new:
        return state
    return replace(state, device_runs=(*state.device_runs, *new))


def materialise(state: GameState, balance: Balance, data: GameData) -> GameState:
    """The first platforms month (any turn: a new game or an older save): the historical
    platforms with the data's shares for the month, developers in proportion to users, and a
    catalogue of CATALOGUE_START months; the historical standards (44.7)."""
    if state.platforms or not enabled(data):
        return state
    platforms = historical_platforms(state, data)
    regions = []
    for region in data.region_keys:
        shares = data_shares(data, region, state.turn)
        live = [p for p in platforms if region in p.regions and p.launched_turn <= state.turn]
        total = sum(shares.get(p.key, 0.0) for p in live) or 1.0
        for p in platforms:
            if region not in p.regions:
                continue
            u = shares.get(p.key, 0.0)
            regions.append(
                PlatformRegion(
                    platform_id=p.id,
                    region=region,
                    users=u,
                    dev_share=u / total if p in live else 0.0,
                    catalogue=CATALOGUE_START * u,
                    goodwill=1.0,
                )
            )
    standards = []
    for i, s in enumerate(file(data).standards):
        keys = {p.key: p.id for p in platforms}
        tipped = _turn(s.tipped)
        done = tipped <= state.turn
        standards.append(
            Standard(
                id=i,
                key=s.key,
                category=s.category,
                label=s.label,
                formats=s.formats,
                sponsors=tuple(keys.get(s.sponsors.get(f, "")) for f in s.formats),  # type: ignore[arg-type]
                adoption=(1.0 if s.winner == s.formats[0] else 0.0) if done else EVEN,
                started_turn=world_start_turn(state.mode),  # M50: the world's first month
                winner=s.winner if done else None,
                tipped_turn=tipped if done else None,
                historical=True,
            )
        )
    state = replace(
        state, platforms=platforms, platform_regions=tuple(regions), standards=tuple(standards)
    )
    return ensure_runs(state, data)


def next_platform_id(state: GameState) -> int:
    return max([OWN_ID_FROM - 1, *(p.id for p in state.platforms)]) + 1


__all__ = ["OTHER", "enabled", "materialise", "schedule"]
