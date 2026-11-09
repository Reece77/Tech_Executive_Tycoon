"""The World screen's read model (M22, formulas.md 39). Only rules announced by the save's month
appear (rules.visible); seeded tension, escalations and détentes exist in the state only from
the month they happen. Exposure numbers are the engine's (sim.geopolitics)."""

from __future__ import annotations

from tst.api.schemas.geopolitics import (
    CountryOut,
    LicenceOut,
    ListingOut,
    ProductExposureOut,
    RegionAccessOut,
    RuleOut,
    SiteOut,
    SupplyExposureOut,
    TariffOut,
    TensionPointOut,
    VariantOut,
    WorldOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.commodities import costs
from tst.sim.geopolitics import actions as ga
from tst.sim.geopolitics import rules as gr
from tst.sim.geopolitics import sales, supply, tariffs, tension, world
from tst.sim.state import GameState

HISTORY_MONTHS = 180  # tunable-exempt: tension months the screen charts (15 years)


def _label(d: LoadedData, key: str) -> str:
    if world.is_country(d.game_data, key):
        return world.countries_of(d.game_data).country(key).label
    return world.BLOC_LABELS.get(key, key.replace("_", " "))


def rule_out(state: GameState, a: gr.ActiveRule, data: LoadedData) -> RuleOut:
    d = data.game_data
    turn = state.turn
    sus = gr.suspension(state, d, a.key, turn)
    if sus is not None and a.start_turn <= turn:
        status = "suspended"
    elif turn < a.start_turn:
        status = "coming"
    elif a.end_turn is not None and turn > a.end_turn:
        status = "ended"
    else:
        status = "in_force"
    goods = data.balance.geopolitics.goods
    r = a.rule
    return RuleOut(
        key=r.key,
        title=r.title,
        actor=r.actor,
        actor_label=world.actor_label(d, r.actor),
        goods=[goods[g].label for g in r.goods],
        destinations=[_label(data, x) for x in r.countries] + list(r.entities),
        regime=r.regime,
        approval=r.approval if r.regime == "licence" else None,
        quota=r.quota if r.regime == "quota" else None,
        threshold=r.threshold,
        status=status,
        month=format_turn(a.start_turn),
        announced=format_turn(gr.announced_turn(a)),
        end=format_turn(a.end_turn) if a.end_turn is not None else None,
        suspended_until=format_turn(sus[1]) if sus is not None else None,
        effect="news" if r.news else ("m19" if r.via else "applies"),
        tag=r.tag,
        source=r.source,
        seeded=a.seeded,
    )


def world_out(state: GameState, data: LoadedData) -> WorldOut:
    b, d = data.balance, data.game_data
    if not world.enabled(d):
        return WorldOut(
            turn=state.turn,
            tension=0.0,
            tension_history=[],
            countries=[],
            rules=[],
            licences=[],
            variants=[],
            listings=[],
            products=[],
            supply=[],
            sites=[],
            tariffs=[],
            tool_licensable=[],
        )
    turn = state.turn
    countries = world.countries_of(d)
    history = [
        TensionPointOut(
            turn=t,
            label=format_turn(t),
            value=tension.tension_at(state, d, t),
            shock=next((m.shock for m in state.tension if m.turn == t), "none"),
        )
        for t in range(max(0, turn - HISTORY_MONTHS), turn + 1)
    ]
    rules = [rule_out(state, a, data) for a in gr.visible(state, d)]
    rules.sort(key=lambda r: (r.status != "in_force", r.status != "coming", r.month), reverse=False)
    group = {c.id: c for c in world.group(state)}
    names = {c.id: c.name for c in state.companies}
    licences = []
    for x in state.licences:
        if x.company_id not in group:
            continue
        product = state.product(x.product_id)
        active = next((a for a in gr.all_rules(state, d) if a.key == x.rule_key), None)
        licences.append(
            LicenceOut(
                id=x.id,
                company_id=x.company_id,
                product_id=x.product_id,
                product=product.name if product else "Chipmaking tools",
                rule_key=x.rule_key,
                rule=active.rule.title if active else x.rule_key,
                country=x.country,
                country_label=countries.country(x.country).label,
                status=x.status,
                requested=format_turn(x.requested_turn),
                decision=format_turn(x.decide_turn),
                until=format_turn(x.until_turn) if x.until_turn is not None else None,
            )
        )
    biting = gr.biting(state, d)
    variants = []
    for v in state.variants:
        product = state.product(v.product_id)
        if product is None or product.company_id not in group:
            continue
        voided = [
            a.rule.title
            for a in biting
            if sales.controls_product(a, product, b, d)
            and not sales.variant_open(state, v.product_id, a)
        ]
        variants.append(
            VariantOut(
                product_id=v.product_id,
                product=product.name,
                launched=format_turn(v.turn),
                voided_by=voided,
            )
        )
    listings = [
        ListingOut(
            company_id=x.company_id,
            company=names.get(x.company_id, ""),
            actor_label=world.actor_label(d, x.actor),
            since=format_turn(x.turn),
            reason=x.reason,
        )
        for x in state.entity_listings
        if x.company_id in group
    ]
    products = []
    for company in group.values():
        for p in state.company_products(company.id):
            if p.status not in ("live", "sunset", "development"):
                continue
            regions = [
                RegionAccessOut(region=r, blocked=a.blocked, variant=a.variant)
                for r in d.region_keys
                if not (a := sales.access(state, p, r, b, d)).free
            ]
            restrict = sales.restricting(state, p, b, d)
            restricted = sorted(
                {c for a in restrict for c in world.destination_countries(d, a.rule, turn)}
            )
            licensable = [c for c in restricted if ga.licence_rules(state, p.id, c, b, d)]
            tariff = tariffs.product_tariff_cents(state, p, b, d)
            is_chip = ga.is_variant_product(p.category, b, d)
            if not regions and not restricted and not tariff:
                continue
            products.append(
                ProductExposureOut(
                    product_id=p.id,
                    product=p.name,
                    company_id=company.id,
                    regions=regions,
                    licensable=licensable,
                    restricted=restricted,
                    variant_possible=is_chip and bool(restrict),
                    has_variant=any(v.product_id == p.id for v in state.variants),
                    tariff_cents=tariff,
                )
            )
    supply_out = []
    for company in group.values():
        use = costs.company_use(state, company.id, b, d) if state.production else {}
        for _key, good in b.geopolitics.goods.items():
            if good.kind != "commodity" or good.commodity is None:
                continue
            ex = supply.exposure(
                state, company.id, good.commodity, b, d, use.get(good.commodity, 0.0)
            )
            if ex.rule_key is None or (ex.share <= 0 and not use.get(good.commodity)):
                continue
            active = next((a for a in biting if a.key == ex.rule_key), None)
            supply_out.append(
                SupplyExposureOut(
                    company_id=company.id,
                    company=company.name,
                    good=good.commodity,
                    good_label=good.label,
                    exposed=ex.share,
                    allocation=ex.allocation_factor,
                    price_premium=ex.share * ex.premium,
                    rule=active.rule.title if active else None,
                )
            )
    lp = b.geopolitics.local_partner
    sites = []
    for company in group.values():
        country = world.company_country(state, company, b, d)
        site = next((s for s in state.sites if s.kind == "company" and s.id == company.id), None)
        sites.append(
            SiteOut(
                company_id=company.id,
                company=company.name,
                country=country,
                country_label=countries.country(country).label,
                bloc=world.bloc_of(d, country, turn),
                local_partner=bool(site and site.local_partner),
                partner_needed=country in lp.countries,
            )
        )
    tariff_out = []
    if d.tariffs is not None:
        for t in d.tariffs.schedules:
            rate = t.rate_at(turn)
            if rate > 0:
                tariff_out.append(
                    TariffOut(
                        key=t.key,
                        title=t.title,
                        origin=_label(data, t.origin),
                        market=_label(data, t.market),
                        goods=list(t.goods),
                        rate=rate,
                        tag=t.tag,
                    )
                )
    return WorldOut(
        turn=turn,
        tension=tension.tension_at(state, d, turn),
        tension_history=history,
        countries=[
            CountryOut(
                key=c.key,
                label=c.label,
                region=c.region,
                bloc=c.bloc_at(turn),
                demand_share=c.demand_share,
            )
            for c in countries.countries
        ],
        rules=rules,
        licences=licences,
        variants=variants,
        listings=listings,
        products=products,
        supply=supply_out,
        sites=sites,
        tariffs=tariff_out,
        tool_licensable=_tool_countries(state, data),
    )


def _tool_countries(state: GameState, data: LoadedData) -> list[str]:
    """Destinations of biting licence-regime tool rules (M21 merge, fabs.py)."""
    d = data.game_data
    if d.nodes is None:
        return []
    from tst.sim.geopolitics import fabs

    out: set[str] = set()
    for a in gr.biting(state, d):
        if a.rule.regime == "licence" and {fabs.EUV, fabs.EQUIPMENT} & set(a.rule.goods):
            out |= world.destination_countries(d, a.rule, state.turn)
    return sorted(out)
