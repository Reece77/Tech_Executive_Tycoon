"""The Platforms screen's data (M31, docs/formulas.md 44.10). Public facts only: users, fee
schedules, rules and catalogue indexes as published; the player's own platforms exactly
(developer share, goodwill, settings); rivals' developer shares as a 5-point range. Never a
review chance or draw (none is stored), a rival's plan or a seeded future rule."""

from __future__ import annotations

from typing import Final

from tst.api.schemas.platforms import (
    AppFeeOut,
    AppProductOut,
    DeviceLineOut,
    FeeScheduleOut,
    ListingOut,
    PlatformOut,
    PlatformRegionOut,
    PlatformSettingsOut,
    PlatformsOut,
    RegulatedPathOut,
    StandardOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.geopolitics import world
from tst.sim.modes.models import world_start_turn
from tst.sim.platforms import data as pdata
from tst.sim.platforms import formulas as pf
from tst.sim.platforms.actions import DEVELOPER_CATEGORIES
from tst.sim.platforms.fees import fees_due
from tst.sim.platforms.phase import by_region, device_catalogue_points, leader_catalogue
from tst.sim.products.models import SELLING
from tst.sim.state import GameState

BAND: Final = 0.05  # tunable-exempt: rivals' developer shares shown within 5 points
RULE_WORDS: Final = {
    "alt_payments": "alternative payments allowed",
    "anti_steering_banned": "links to pay outside allowed",
    "side_loading": "other app stores allowed",
}
ACTION_WORDS: Final = {
    "rejected_update": "update rejected",
    "fee_dispute": "fee dispute",
    "removal": "removed",
}


def _range(x: float) -> list[float]:
    lo = max(0.0, round((x - BAND / 2) / BAND) * BAND)
    return [round(lo, 4), round(min(1.0, lo + BAND), 4)]


def _store(state: GameState, platform_id: int) -> str:
    p = state.platform(platform_id)
    return p.store if p is not None else "?"


def _labels(data: LoadedData) -> dict[str, str]:
    return {r.key: r.label for r in data.game_data.regions}


def _part_label(part: str) -> str:
    if part.startswith("store:"):
        return part.removeprefix("store:")
    return {"eu": "EU", "united_states": "United States"}.get(part, part.replace("_", " ").title())


def platforms_out(state: GameState, data: LoadedData) -> PlatformsOut:
    b, d = data.balance, data.game_data
    pb = b.platforms
    labels = _labels(data)
    if not pdata.enabled(d) or not state.platforms:
        return PlatformsOut(
            started=False,
            fees_posting=False,
            platforms=[],
            device_lines=[],
            apps=[],
            standards=[],
            open_products=[],
            developer_candidates=[],
            appeal_odds=list(pb.review.appeal_odds),
            own_fee_range=list(pb.own_fee_range),
        )
    group = {c.id for c in world.group(state)}
    rows = by_region(state)
    turn = state.turn
    platforms = []
    for p in state.platforms:
        own = p.owner_id in group
        regions = []
        for region in p.regions:
            row = rows.get(region, {}).get(p.id)
            if row is None:
                continue
            here = rows.get(region, {})
            lead = leader_catalogue(here, state, p.kind)
            sched = pdata.schedule(p, region, turn, b, d, state.rival_stores)
            rules = [
                RULE_WORDS[k] for k in RULE_WORDS if pdata.rule_active(d, p, region, k, turn) > 0
            ]
            regions.append(
                PlatformRegionOut(
                    region=region,
                    label=labels.get(region, region),
                    users=round(row.users, 4),
                    developer_share=round(row.dev_share, 4) if own else None,
                    developer_range=_range(row.dev_share),
                    catalogue_index=round(pf.catalogue_index(row.catalogue, lead), 1),
                    goodwill=round(row.goodwill, 3) if own else None,
                    fees=FeeScheduleOut(
                        standard=sched.standard,
                        small_rate=sched.small_rate,
                        small_threshold_cents=sched.small_threshold_cents,
                        subscription_rate=sched.sub_rate,
                        subscription_after_year=sched.sub_after_year,
                        regulated=[
                            RegulatedPathOut(label=_part_label(part), share=round(s, 4), rate=r)
                            for part, s, r in sched.regulated
                        ],
                    ),
                    rules=rules,
                    side_loading=round(pdata.allows_side_loading(d, p, region, turn), 3),
                    rival_stores=[
                        s.name
                        for s in state.rival_stores
                        if s.platform_id == p.id and s.region == region
                    ],
                )
            )
        counts = pdata.file(d).app_counts.get(p.key, {})
        known = [y for y in counts if y <= pdata.year_of(turn)]
        platforms.append(
            PlatformOut(
                platform_id=p.id,
                key=p.key,
                name=p.name,
                store=p.store,
                kind=p.kind,
                owner_label=p.owner_label,
                owner_company_id=p.owner_id,
                own=own,
                historical=p.historical,
                launched_label=format_turn(p.launched_turn)
                if p.launched_turn > world_start_turn(state.mode)
                else None,
                ended_label=format_turn(p.ended_turn) if p.ended_turn is not None else None,
                open_source=p.open_turn is not None and p.open_turn <= turn,
                licensable=p.licensable,
                product_id=p.product_id,
                app_count_thousands=counts[max(known)] if known else None,
                regions=regions,
                settings=PlatformSettingsOut(
                    fee=p.fee if p.fee is not None else 0.30,  # tunable-exempt: the default
                    strictness=p.strictness,
                    self_pref=p.self_pref,
                    anti_steering=p.anti_steering,
                    side_loading=p.side_loading,
                    licence_cents=p.licence_cents,
                )
                if own
                else None,
            )
        )
    lines = []
    for run in state.device_runs:
        product = state.product(run.product_id)
        if product is None or product.company_id not in group or product.status == "retired":
            continue
        current = state.platform(run.platform_id)
        previous = state.platform(run.previous_id) if run.previous_id is not None else None
        lines.append(
            DeviceLineOut(
                product_id=product.id,
                name=product.name,
                platform_id=run.platform_id,
                platform_name=current.name if current else "?",
                previous_name=previous.name if previous else None,
                previous_share=round(run.previous_share, 3),
                catalogue_points={
                    r: round(device_catalogue_points(state, product.id, r, b), 1)
                    for r in d.region_keys
                }
                if not pdata.in_history(turn, d)
                else {},
            )
        )
    due = fees_due(state, b, d) if turn >= pb.fees_turn else {}
    apps = []
    for product in state.products:
        if product.company_id not in group or product.status not in SELLING:
            continue
        if product.category not in pb.app_categories:
            continue
        fee_rows = [
            AppFeeOut(
                platform_id=plat,
                platform_name=_store(state, plat),
                region=region,
                region_label=labels.get(region, region),
                cents=cents,
            )
            for (pid, plat, _owner, region), cents in sorted(due.items())
            if pid == product.id
        ]
        listings = [
            ListingOut(
                platform_id=x.platform_id,
                platform_name=_store(state, x.platform_id),
                region=x.region,
                region_label=labels.get(x.region, x.region),
                status=x.status,
                since_label=format_turn(x.since_turn),
                answer_label=format_turn(x.until_turn) if x.until_turn is not None else None,
            )
            for x in state.platform_listings
            if x.product_id == product.id and x.status != "listed"
        ]
        actions = [
            f"{format_turn(r.turn)}: {ACTION_WORDS[r.action]} by {_store(state, r.platform_id)}"
            for r in state.platform_reviews
            if r.product_id == product.id
        ]
        apps.append(
            AppProductOut(
                product_id=product.id,
                name=product.name,
                category=product.category,
                steering=product.id in state.steering_products,
                fees=fee_rows,
                fees_total_cents=sum(f.cents for f in fee_rows),
                listings=listings,
                recent_actions=actions,
            )
        )
    standards = []
    for s in state.standards:
        losers = [
            ps.product_id
            for ps in state.product_standards
            if ps.standard_id == s.id
            and s.winner is not None
            and ps.format != s.winner
            and (q := state.product(ps.product_id)) is not None
            and q.company_id in group
        ]
        standards.append(
            StandardOut(
                standard_id=s.id,
                label=s.label,
                category=s.category,
                formats=list(s.formats),
                adoption=round(s.adoption, 3),
                winner=s.winner,
                tipped_label=format_turn(s.tipped_turn) if s.tipped_turn is not None else None,
                historical=s.historical,
                yours_on_loser=losers,
            )
        )
    founded = {p.product_id for p in state.platforms if p.product_id is not None}
    return PlatformsOut(
        started=not pdata.in_history(turn, d),
        fees_posting=turn >= pb.fees_turn,
        platforms=platforms,
        device_lines=lines,
        apps=apps,
        standards=standards,
        open_products=[o.product_id for o in state.open_sources if o.closed_turn is None],
        developer_candidates=[
            p.id
            for p in state.products
            if p.company_id in group
            and p.category in DEVELOPER_CATEGORIES
            and p.status in SELLING
            and p.id not in founded
        ],
        appeal_odds=list(pb.review.appeal_odds),
        own_fee_range=list(pb.own_fee_range),
    )
