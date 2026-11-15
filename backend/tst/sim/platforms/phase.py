"""The platforms month (docs/formulas.md 44.1-44.3; ADR-0021 2), in the market phase before
product demand reads it.

In order: the first month materialises the historical platforms (any turn); every device line
gets a platform; users are set (to 2025: the data's shares, with any own platform's devices
taken out first; from 2026: the installed base, below); then each region's developers, their
attention shares, catalogues and goodwill.

**Users from 2026 (44.1, 44.3).** A platform's users in a region are its in-game devices'
customers (device lines on it, as a share of the region's device users, the devices market's
addressable customers) plus its share `rest` of the devices not modelled in the game. The rest
replaces each month at the devices' replacement pace: `stay` of each platform's replacers stay
(lock-in, falling behind the catalogue leader), the others choose afresh by users x (catalogue /
leader)^rest_tilt among platforms open to OEMs (not ended; an own OS only once licensed). In the
first computed month `rest` is set so users equal December 2025's data.

**Effects** (from 2026 only, so 2010-2025 demand is main's): a device's feature score gains its
platform's catalogue points (44.3) and loses a losing standard's penalty (44.7); an owner's own
apps gain appeal on its platform with self-preferencing (44.5); a developer platform's base
product churns less with its catalogue (44.3); an open-sourced product books only its paid tier
(44.6).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.geo.cities import home_region
from tst.sim.platforms import data as pdata
from tst.sim.platforms import draws
from tst.sim.platforms import formulas as pf
from tst.sim.platforms.models import DeviceRun, Platform, PlatformRegion
from tst.sim.products.models import SELLING, Product
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

BIG_SELLER: Final = 10**12  # tunable-exempt: a seller far over any small-business threshold
TINY: Final = 1e-12  # tunable-exempt: shares below this count as none
HALF: Final = 0.5  # tunable-exempt: the reference holds half the developers (M31 decision)
MIN_REPLACEMENT: Final = 1  # tunable-exempt: categories.yaml always gives devices a cycle


# --- Helpers ---------------------------------------------------------------------------------


def home_of(state: GameState, balance: Balance, data: GameData) -> str | None:
    """The region every company's home-segment customers are in (19.5): the player's HQ's."""
    if not data.cities:
        return data.region_keys[0] if data.region_keys else None
    return home_region(state, balance, data)


def customers_in(state: GameState, product: Product, region: str, home: str | None) -> float:
    rows = [r.customers for r in state.regional_segments_of(product.id, region)]
    if region == home:
        rows += [s.customers for s in state.segments_of(product.id)]
    return sum(rows)


def addressable_in(
    state: GameState, category: str, data: GameData, region: str, home: str | None
) -> float:
    total = 0.0
    for m in data.category(category).markets:
        market = (
            state.market(category, m.segment)
            if region == home
            else state.regional_market(category, m.segment, region)
        )
        if market is not None:
            total += market.addressable
    return total


def live_in(platform: Platform, region: str, turn: int) -> bool:
    return (
        region in platform.regions
        and platform.launched_turn <= turn
        and (platform.ended_turn is None or turn < platform.ended_turn)
    )


def regions_of(state: GameState, platform_id: int) -> dict[str, PlatformRegion]:
    return {r.region: r for r in state.platform_regions if r.platform_id == platform_id}


def by_region(state: GameState) -> dict[str, dict[int, PlatformRegion]]:
    out: dict[str, dict[int, PlatformRegion]] = {}
    for r in state.platform_regions:
        out.setdefault(r.region, {})[r.platform_id] = r
    return out


def run_split(
    state: GameState, run: DeviceRun, region: str, rows: Mapping[int, PlatformRegion]
) -> dict[int, float]:
    """A device line's customers by platform in a region: an Android line's split between its
    two stores by their users (China's stores in East Asia, 44.1), and devices sold before a
    switch still on the old platform."""

    def android(pid: int) -> dict[int, float]:
        p = state.platform(pid)
        if p is None or p.key not in pdata.ANDROID_FAMILY:
            return {pid: 1.0}
        family = [q for q in state.platforms if q.key in pdata.ANDROID_FAMILY and q.id in rows]
        total = sum(rows[q.id].users for q in family)
        if total <= TINY:
            return {pid: 1.0}
        return {q.id: rows[q.id].users / total for q in family}

    out: dict[int, float] = {}
    for pid, w in (
        (run.platform_id, 1 - run.previous_share),
        (run.previous_id, run.previous_share),
    ):
        if pid is None or w <= 0:
            continue
        for q, s in android(pid).items():
            out[q] = out.get(q, 0.0) + w * s
    return out


def ingame_users(
    state: GameState,
    balance: Balance,
    data: GameData,
    region: str,
    rows: Mapping[int, PlatformRegion],
) -> tuple[dict[int, float], float]:
    """In-game device lines' customers by platform, as shares of the region's device users."""
    home = home_of(state, balance, data)
    base = addressable_in(state, pdata.DEVICES, data, region, home)
    out: dict[int, float] = {}
    if base <= 0:
        return out, 0.0
    for run in state.device_runs:
        product = state.product(run.product_id)
        if product is None or product.status not in SELLING:
            continue
        c = customers_in(state, product, region, home) / base
        if c <= 0:
            continue
        for pid, w in run_split(state, run, region, rows).items():
            out[pid] = out.get(pid, 0.0) + c * w
    total = sum(out.values())
    if total > 1:
        out = {p: v / total for p, v in out.items()}
        total = 1.0
    return out, total


def leader_catalogue(
    rows: Mapping[int, PlatformRegion], state: GameState, kind: str = "device"
) -> float:
    return max(
        (
            r.catalogue
            for pid, r in rows.items()
            if (p := state.platform(pid)) is not None and p.kind == kind
        ),
        default=0.0,
    )


def platform_fee(
    state: GameState, platform: Platform, region: str, balance: Balance, data: GameData
) -> float:
    """The fee developers weigh (44.2): a large seller's effective fee on consumer apps."""
    sched = pdata.schedule(platform, region, state.turn, balance, data, state.rival_stores)
    return pdata.fee_for(sched, "consumer_apps", BIG_SELLER, False, balance)


def tools_of(platform: Platform, balance: Balance) -> float:
    lo, hi = balance.platforms.tools
    bonus = (
        balance.platforms.open_source.tools_gain
        if platform.open_turn is not None and not platform.historical
        else 0.0
    )
    return pf.clamp(platform.tools + bonus, lo, hi)


# --- Users -------------------------------------------------------------------------------------


def _history_users(state: GameState, balance: Balance, data: GameData) -> GameState:
    """To 2025 (44.1): the data's year shares; an own platform's devices first."""
    rows = by_region(state)
    out = []
    for region in data.region_keys:
        shares = pdata.data_shares(data, region, state.turn)
        here = rows.get(region, {})
        ingame, _ = ingame_users(state, balance, data, region, here)
        own = {
            pid: u
            for pid, u in ingame.items()
            if (p := state.platform(pid)) is not None and not p.historical
        }
        scale = max(0.0, 1 - sum(own.values()))
        for pid, row in here.items():
            p = state.platform(pid)
            assert p is not None
            users = own.get(pid, 0.0) if not p.historical else shares.get(p.key, 0.0) * scale
            out.append(replace(row, users=users))
    return replace(state, platform_regions=tuple(out))


def _computed_users(state: GameState, balance: Balance, data: GameData) -> GameState:
    pb = balance.platforms
    turn = state.turn
    rows = by_region(state)
    out = []
    devices = data.category(pdata.DEVICES)
    replacement = float(devices.market("consumer").replacement_months or MIN_REPLACEMENT)
    for region in data.region_keys:
        here = rows.get(region, {})
        device_ids = [
            pid for pid in here if (p := state.platform(pid)) is not None and p.kind == "device"
        ]
        ingame, covered = ingame_users(state, balance, data, region, here)
        rest = {pid: here[pid].rest for pid in device_ids}
        if sum(rest.values()) <= TINY:  # the first computed month: match December 2025
            gap = {}
            for pid in device_ids:
                p = state.platform(pid)
                assert p is not None
                ok = live_in(p, region, turn)
                gap[pid] = max(0.0, here[pid].users - ingame.get(pid, 0.0)) if ok else 0.0
            total = sum(gap.values())
            rest = {pid: g / total for pid, g in gap.items()} if total > 0 else gap
        leader = leader_catalogue(here, state)
        stay: dict[int, float] = {}
        weights: dict[int, float] = {}
        for pid in device_ids:
            p = state.platform(pid)
            assert p is not None
            index = pf.catalogue_index(here[pid].catalogue, leader)
            stay[pid] = pf.stay_probability(index, pb) if live_in(p, region, turn) else 0.0
            if not live_in(p, region, turn):
                continue
            if not p.historical and p.licence_cents is None:
                continue  # an own OS reaches the rest of the market only through licensees
            base = rest.get(pid, 0.0) if p.historical else max(rest.get(pid, 0.0), here[pid].users)
            tilt = (here[pid].catalogue / leader) ** pb.rest_tilt if leader > 0 else 1.0
            licence = 1.0
            if not p.historical and p.licence_cents is not None:
                lo, hi = pb.licence_factor
                # money-exact: ratio
                licence = pf.clamp((pb.android_licence_cents + 1) / (p.licence_cents + 1), lo, hi)
            weights[pid] = base * tilt * licence
        rest = pf.replace_users(rest, stay, weights, replacement)
        for pid in device_ids:
            users = ingame.get(pid, 0.0) + (1 - covered) * rest.get(pid, 0.0)
            out.append(replace(here[pid], users=users, rest=rest.get(pid, 0.0)))
        for pid, row in here.items():
            if pid not in device_ids:
                out.append(row)
    state = replace(state, platform_regions=tuple(out))
    return _developer_platform_users(state, balance, data)


def _developer_platform_users(state: GameState, balance: Balance, data: GameData) -> GameState:
    """A developer platform's users: its base product's share of its category's customers."""
    home = home_of(state, balance, data)
    out = []
    for row in state.platform_regions:
        p = state.platform(row.platform_id)
        if p is None or p.kind != "developer" or p.product_id is None:
            out.append(row)
            continue
        product = state.product(p.product_id)
        if product is None or product.status not in SELLING:
            out.append(replace(row, users=0.0))
            continue
        base = addressable_in(state, product.category, data, row.region, home)
        users = customers_in(state, product, row.region, home) / base if base > 0 else 0.0
        out.append(replace(row, users=min(1.0, users)))
    return replace(state, platform_regions=tuple(out))


# --- Developers, catalogue, goodwill (44.2, 44.5) ---------------------------------------------


def _goodwill_target(
    state: GameState, platform: Platform, region: str, balance: Balance, data: GameData
) -> float:
    pb = balance.platforms
    lo, hi = pb.goodwill
    sched = pdata.schedule(platform, region, state.turn, balance, data, state.rival_stores)
    target = 1 - pb.goodwill_fee * (sched.standard - 0.30)  # tunable-exempt: the 2008 norm
    target -= pb.goodwill_self_pref[platform.self_pref]
    target -= pb.review.player_goodwill[platform.strictness] if not platform.historical else 0.0
    if platform.open_turn is not None and not platform.historical:
        target += pb.open_source.goodwill_gain
    return pf.clamp(target, lo, hi)


def _developers(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    pb = balance.platforms
    turn = state.turn
    computed = not pdata.in_history(turn, data)
    weights = pdata.region_weights(data)
    world = pdata.developers(data, balance, turn)
    rows = by_region(state)
    out = []
    for r_index, region in enumerate(data.region_keys):
        here = rows.get(region, {})
        devs = world * weights.get(region, 0.0)
        device = {
            pid: row
            for pid, row in here.items()
            if (p := state.platform(pid)) is not None and p.kind == "device"
        }
        attract: dict[int, float] = {}
        for pid, row in device.items():
            p = state.platform(pid)
            assert p is not None
            if not live_in(p, region, turn):
                attract[pid] = 0.0
                continue
            a = pf.attractiveness(
                row.users,
                platform_fee(state, p, region, balance, data),
                tools_of(p, balance),
                row.goodwill,
                pb,
            )
            if computed and pb.dev_noise_sd > 0:
                noise = float(
                    draws.gen(rng, turn, draws.NOISE, pid, r_index).normal(0, pb.dev_noise_sd)
                )
                a *= max(0.0, 1 + noise)
            attract[pid] = a
        shares = pf.next_dev_shares(
            {pid: row.dev_share for pid, row in device.items()}, attract, pb
        )
        for pid, row in here.items():
            p = state.platform(pid)
            assert p is not None
            if p.kind == "device":
                share = shares.get(pid, 0.0)
                months = (
                    pf.developer_months(share, row.users, pb) if live_in(p, region, turn) else 0.0
                )
            else:  # a developer platform against the rest of its category (44.2)
                a = pf.attractiveness(
                    row.users,
                    platform_fee(state, p, region, balance, data),
                    tools_of(p, balance),
                    row.goodwill,
                    pb,
                )
                rest = pf.attractiveness(max(0.0, 1 - row.users), 0.0, 1.0, 1.0, pb)
                aim = a / (a + rest) if a + rest > 0 else 0.0
                share = pb.dev_inertia * row.dev_share + (1 - pb.dev_inertia) * aim
                months = pf.developer_months(share, row.users, pb)
            catalogue = pf.next_catalogue(row.catalogue, devs, months, pb)
            g = row.goodwill
            if computed:
                g += pb.goodwill_speed * (_goodwill_target(state, p, region, balance, data) - g)
            out.append(replace(row, dev_share=share, catalogue=catalogue, goodwill=g))
    return replace(state, platform_regions=tuple(out))


def _decay_switches(state: GameState, data: GameData) -> GameState:
    """Devices sold before a switch are replaced at the market's pace (44.1)."""
    if not any(d.previous_share > 0 for d in state.device_runs):
        return state
    r = float(data.category(pdata.DEVICES).market("consumer").replacement_months or MIN_REPLACEMENT)
    runs = tuple(
        replace(d, previous_share=d.previous_share * (1 - 1 / r)) if d.previous_share > 0 else d
        for d in state.device_runs
    )
    return replace(state, device_runs=runs)


def platforms_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> GameState:
    if not pdata.enabled(data):
        return state
    state = pdata.materialise(state, balance, data)
    state = pdata.ensure_runs(state, data)
    state = _decay_switches(state, data)
    if pdata.in_history(state.turn, data):
        state = _history_users(state, balance, data)
    else:
        state = _computed_users(state, balance, data)
    return _developers(state, rng, balance, data)


# --- Effects on demand (from 2026) ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Effects:
    """What product demand reads from the platforms (module docstring). Keys: (product id,
    region)."""

    feature_bonus: Mapping[tuple[int, str], float] = field(default_factory=dict)
    appeal_mult: Mapping[tuple[int, str], float] = field(default_factory=dict)
    churn_mult: Mapping[int, float] = field(default_factory=dict)
    revenue_share: Mapping[int, float] = field(default_factory=dict)

    def bonus(self, product_id: int, region: str | None) -> float:
        return self.feature_bonus.get((product_id, region or ""), 0.0)

    def appeal(self, product_id: int, region: str | None) -> float:
        return self.appeal_mult.get((product_id, region or ""), 1.0)


NO_EFFECTS: Final = Effects()


def device_catalogue_points(
    state: GameState, product_id: int, region: str, balance: Balance
) -> float:
    """A device line's catalogue points in a region (44.3), by its platforms' users split."""
    run = state.device_run(product_id)
    rows = by_region(state).get(region, {})
    if run is None or not rows:
        return 0.0
    leader = leader_catalogue(rows, state)
    points = 0.0
    for pid, w in run_split(state, run, region, rows).items():
        row = rows.get(pid)
        if row is not None:
            points += w * pf.catalogue_points(row.catalogue, leader, balance.platforms)
    return points


def effects(state: GameState, balance: Balance, data: GameData) -> Effects:
    if not pdata.enabled(data) or not state.platforms or pdata.in_history(state.turn, data):
        return NO_EFFECTS
    from tst.sim.platforms import opensource, standards

    pb = balance.platforms
    bonus: dict[tuple[int, str], float] = {}
    appeal: dict[tuple[int, str], float] = {}
    churn: dict[int, float] = {}
    rows = by_region(state)
    for run in state.device_runs:
        product = state.product(run.product_id)
        if product is None or product.status not in SELLING:
            continue
        for region in data.region_keys:
            points = device_catalogue_points(state, run.product_id, region, balance)
            if points:
                bonus[(run.product_id, region)] = points
    for x in state.platform_listings:  # a removed app reaches none of the platform's users
        if x.status != "listed":
            row = rows.get(x.region, {}).get(x.platform_id)
            if row is not None:
                key = (x.product_id, x.region)
                appeal[key] = appeal.get(key, 1.0) * max(0.0, 1 - row.users)
    for (pid, region), penalty in standards.penalties(state, balance, data).items():
        bonus[(pid, region)] = bonus.get((pid, region), 0.0) - penalty
    for p in state.platforms:
        if p.owner_id is None or p.self_pref == "off":
            continue
        boost = pb.self_pref_share[p.self_pref]
        cats = _first_party(p, state, data, balance)
        for product in state.company_products(p.owner_id):
            if product.category not in cats or product.status not in SELLING:
                continue
            for region, row in regions_of(state, p.id).items():
                appeal[(product.id, region)] = appeal.get((product.id, region), 1.0) * (
                    1 + boost * row.users
                )
        if p.kind == "developer" and p.product_id is not None:
            index = max(
                (
                    pf.catalogue_index(
                        r.catalogue, developer_reference(state, balance, data, r.region)
                    )
                    for r in regions_of(state, p.id).values()
                ),
                default=0.0,
            )
            churn[p.product_id] = pf.dev_churn_factor(index, pb)
    return Effects(
        feature_bonus=bonus,
        appeal_mult=appeal,
        churn_mult=churn,
        revenue_share=opensource.revenue_shares(state, balance),
    )


def developer_reference(state: GameState, balance: Balance, data: GameData, region: str) -> float:
    """A developer platform's catalogue index is against a platform holding half of the region's
    developers at steady state (M31 decision: developer platforms have no named rivals)."""
    pb = balance.platforms
    devs = pdata.developers(data, balance, state.turn) * pdata.region_weights(data).get(region, 0.0)
    return (
        devs
        * (pb.multihome_share + (1 - pb.multihome_share) * HALF)
        / max(pb.catalogue_decay, TINY)
    )


def _first_party(p: Platform, state: GameState, data: GameData, balance: Balance) -> set[str]:
    """Categories the owner sells its own apps in on its platform (44.5)."""
    if p.historical:
        definition = pdata.file(data).platform(p.key)
        return {
            c
            for c, _ in definition.first_party.items()
            if (definition.first_party_from(c) or 0) <= state.turn
        }
    if p.owner_id is None:
        return set()
    from tst.sim.platforms.fees import app_category

    return {
        q.category
        for q in state.company_products(p.owner_id)
        if app_category(q.category, balance) and q.status in SELLING
    }


def first_party(p: Platform, state: GameState, data: GameData, balance: Balance) -> set[str]:
    return _first_party(p, state, data, balance)
