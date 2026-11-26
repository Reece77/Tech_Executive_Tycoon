"""The media screens' view (M55, docs/formulas.md 65): the player's titles, creative leads, leads on
offer, services, games and networks, from public figures and the player's own records.

Hidden values (the brief's hidden-value test, tests/integration/test_m55_media_api.py): a lead's
`ego` and `loyalty` are never read here; creative and vision are shown as ranges
(tst.sim.media.talent.shown_range); a title's audience, expected audience and quality are shown only
from its release (none is drawn or stored before); seeded eras, generations and strikes are shown
only once they come; markets' and ad spend's drawn growth is never shown."""

from __future__ import annotations

from tst.api.schemas.media import (
    AdMarketOut,
    ConsumerAppOut,
    FormatOut,
    GamesOut,
    GameTitleOut,
    GenerationOut,
    KindOut,
    LawOut,
    LeadOfferOut,
    LeadOut,
    LicenceOut,
    MediaScreenOut,
    NetworkOut,
    RangeOut,
    RegionCustomersOut,
    ServiceMonthOut,
    ServiceOut,
    SocialOut,
    StreamingOut,
    StudioOut,
    TitleOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.facilities.config import month_to_turn
from tst.sim.media import social, streaming, talent, titles
from tst.sim.media.data import enabled, file
from tst.sim.media.models import Title
from tst.sim.money import times
from tst.sim.products.models import Product
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def _person_name(state: GameState, person_id: int | None) -> str | None:
    if person_id is None:
        return None
    p = state.person(person_id)
    return f"{p.first_name} {p.last_name}"


def title_out(t: Title, state: GameState) -> TitleOut:
    released = t.stage == "released"
    lead = state.media.lead(t.lead_person_id) if t.lead_person_id is not None else None
    return TitleOut(
        id=t.id,
        name=t.name,
        kind=t.kind,
        genre=t.genre,
        stage=t.stage,
        budget_cents=t.budget_cents,
        spent_cents=t.spent_cents,
        book_cents=t.book_cents,
        amortised_cents=t.amortised_cents,
        written_off_cents=t.written_off_cents,
        lead_person_id=t.lead_person_id,
        lead_name=_person_name(state, t.lead_person_id),
        lead_walked=t.walked_turn is not None
        or (lead is not None and lead.company_id != t.company_id and t.stage == "development"),
        months_done=t.months_done,
        dev_months=t.dev_months,
        release=format_turn(t.released_turn if t.released_turn is not None else t.release_turn),
        greenlit=format_turn(t.greenlit_turn),
        overrules=t.overrules,
        cuts=t.cuts,
        moves=t.moves,
        window=t.window,
        platforms=list(t.platforms),
        monetisation=t.monetisation,
        live_service=t.live_service,
        store=t.store,
        sequel_of=t.sequel_of,
        audience=t.audience if released else None,
        expected=t.expected if released else None,
        quality=t.quality if released else None,
        revenue_cents=t.revenue_cents,
        attributed_cents=t.attributed_cents,
        players=t.players if released else 0.0,
        earned_back=released and t.revenue_cents + t.attributed_cents >= t.spent_cents,
    )


def _studio(state: GameState, data: LoadedData) -> StudioOut:
    b, d = data.balance, data.game_data
    player = state.player.id
    mine = [t for t in state.media.titles if t.company_id == player]
    busy = {t.lead_person_id for t in mine if t.stage == "development"}
    leads = []
    for x in state.media.leads:
        if x.company_id != player:
            continue
        person = state.person(x.person_id)
        job = state.employment_of(x.person_id)
        c = talent.shown_range(x.creative, x.creative_off, x.titles, b)
        v = talent.shown_range(x.vision, x.vision_off, x.titles, b)
        morale = state.person_state(x.person_id).morale
        leads.append(
            LeadOut(
                person_id=x.person_id,
                name=f"{person.first_name} {person.last_name}",
                level=job.level if job is not None else (person.level or ""),
                creative=RangeOut(lo=c[0], hi=c[1]),
                vision=RangeOut(lo=v[0], hi=v[1]),
                reputation=round(x.reputation, 2),
                fee_cents=x.fee_cents,
                deal_to=format_turn(x.deal_to) if x.deal_to is not None else None,
                titles=x.titles,
                morale=round(morale) if morale is not None else None,
                busy=x.person_id in busy,
            )
        )
    rng = RngFactory(state.save_meta.master_seed)
    offers = []
    tb = b.media.talent
    for o in state.media.offers:
        if o.status != "open":
            continue
        cand = talent.candidate(o, rng, b, d)
        c = talent.shown_range(cand.creative, cand.creative_off, 0, b)
        v = talent.shown_range(cand.vision, cand.vision_off, 0, b)
        offers.append(
            LeadOfferOut(
                year=o.year,
                n=o.n,
                name=f"{cand.person.first_name} {cand.person.last_name}",
                level=cand.person.level or "",
                region=d.region(cand.person.region).label,
                creative=RangeOut(lo=c[0], hi=c[1]),
                vision=RangeOut(lo=v[0], hi=v[1]),
                fee_cents=talent.fee_cents(cand.creative, cand.vision, 0.0, b),
                upfront_share=tb.upfront_share,
                expires=format_turn(o.turn + tb.pool_months),
            )
        )
    kinds = []
    for key, k in b.media.kinds.items():
        typical = titles.typical_budget_cents(k, b)
        kinds.append(
            KindOut(
                key=key,
                typical_budget_cents=typical,
                min_budget_cents=times(typical, k.min_budget_share),
                max_budget_cents=times(typical, k.max_budget_mult),
                dev_months=k.dev_months,
            )
        )
    value = 0.0
    for t in mine:
        if t.stage == "released" and t.window == titles.OWN:
            value += streaming.title_catalogue_value(t, state, b)
    return StudioOut(
        slate=[title_out(t, state) for t in mine if t.stage == "development"],
        released=[title_out(t, state) for t in mine if t.stage == "released"],
        catalogue_book_cents=sum(t.book_cents for t in mine),
        catalogue_value_cents=round(value),
        leads=leads,
        offers=offers,
        kinds=kinds,
        strikes=[d.region(r).label for r in talent.strikes_now(state, d)],
        deal_years=[int(tb.deal_years.lo), int(tb.deal_years.hi)],
    )


def _regions(
    state: GameState, p: Product, balance: Balance, data: GameData
) -> list[RegionCustomersOut]:
    home = home_region_of(state, balance, data)
    markets = {(m.category, home): m.addressable for m in state.markets}
    markets |= {(m.category, m.region): m.addressable for m in state.regional_markets}
    out = []
    for seg, region in streaming.rows(state, p, home):
        market = markets.get((p.category, region), 0.0)
        if p.category == balance.media.social:
            base = social.region_users(state, region, balance, data)
        else:
            base = market
        out.append(
            RegionCustomersOut(
                region=region,
                label=data.region(region).label,
                customers=seg.customers,
                price_cents=seg.price_cents,
                market=market,
                share=seg.customers / base if base > 0 else 0.0,
            )
        )
    return out


def _service(state: GameState, p: Product, data: LoadedData) -> ServiceOut:
    b, d = data.balance, data.game_data
    months = [m for m in state.media.months if m.product_id == p.id]
    last = months[-1] if months else None
    pb = next((x.turn for x in state.media.paid_back if x.product_id == p.id), None)
    return ServiceOut(
        product_id=p.id,
        name=p.name,
        category=p.category,
        status=p.status,
        regions=_regions(state, p, b, d),
        customers=streaming.customers(state, p),
        churn_mult=last.churn_mult if last is not None else 1.0,
        engagement=last.engagement if last is not None else 0.0,
        ad_tier=streaming.ad_tier_on(p, state, d),
        ad_revenue_cents=last.ad_revenue_cents if last is not None else 0,
        content_cents=last.content_cents if last is not None else 0,
        cash_cents=last.cash_cents if last is not None else 0,
        paid_back=format_turn(pb) if pb is not None else None,
        months=[
            ServiceMonthOut(
                month=format_turn(m.turn),
                customers=m.customers,
                revenue_cents=m.revenue_cents,
                ad_revenue_cents=m.ad_revenue_cents,
                content_cents=m.content_cents,
                costs_cents=m.costs_cents,
                cash_cents=m.cash_cents,
            )
            for m in months
        ],
        licences=[
            LicenceOut(
                id=x.id,
                fee_cents=x.fee_cents,
                from_month=format_turn(x.from_turn),
                to_month=format_turn(x.to_turn),
            )
            for x in state.media.licences
            if x.product_id == p.id
        ],
    )


def _streaming(state: GameState, data: LoadedData) -> StreamingOut:
    b, d = data.balance, data.game_data
    cats = (b.media.streaming, b.media.music)
    lines = [p for p in state.company_products(state.player.id) if p.category in cats]
    sb = b.media.streaming_service
    return StreamingOut(
        services=[_service(state, p, data) for p in lines if p.status != "retired"],
        ad_tier_open=streaming.ad_tier_open(state, d),
        ad_tier_from=format_turn(month_to_turn(file(d).ad_tier_from)),
        music_payout=sb.music_payout,
        licence_years=[int(sb.licence_years.lo), int(sb.licence_years.hi)],
    )


def _games(state: GameState, data: LoadedData) -> GamesOut:
    b, d = data.balance, data.game_data
    gb = b.media.game_titles
    mine = [t for t in state.media.titles if t.company_id == state.player.id and t.kind == "game"]
    gens = [
        GenerationOut(key=g.key, label=g.label, month=format_turn(g.turn))
        for g in file(d).console_generations
        if g.turn <= state.turn
    ]
    gens += [
        GenerationOut(
            key=x.key, label=x.key.replace("_", " ").capitalize(), month=format_turn(int(x.value))
        )
        for x in state.media.draws
        if x.kind == "generation" and x.value <= state.turn
    ]
    sf = file(d).store_fees
    return GamesOut(
        titles=[
            GameTitleOut(
                title=title_out(t, state),
                decay=(gb.live_decay if t.live_service else gb.decay)
                if t.monetisation == titles.F2P
                else 0.0,
            )
            for t in mine
        ],
        generations=gens,
        store_fee=sf.default,
        epic_fee=sf.epic,
        epic_open=state.turn >= month_to_turn(sf.epic_from),
    )


def _social(state: GameState, data: LoadedData) -> SocialOut:
    b, d = data.balance, data.game_data
    mb = b.media
    networks = []
    for p in state.company_products(state.player.id):
        if p.category != mb.social or p.status == "retired":
            continue
        s = state.media.setting(p.id)
        fmt = social.line_format(p, state, d)
        shares = social.shares(state, p, b, d)
        top = max(shares.values(), default=0.0)
        networks.append(
            NetworkOut(
                product_id=p.id,
                name=p.name,
                status=p.status,
                regions=_regions(state, p, b, d),
                users=streaming.customers(state, p),
                format=fmt,
                format_label=social.format_label(fmt, d, b) if fmt is not None else None,
                advantage=social.format_mult(p, state, b, d)[1],
                network_effect=social.network_mults(top, b)[0],
                ad_load=s.ad_load if s is not None else 1.0,
                moderation=s.moderation if s is not None else "standard",
                ad_revenue_cents=streaming.monthly_revenue_cents(state, p),
                laws=[
                    LawOut(
                        id=x.id,
                        region=x.region,
                        label=d.region(x.region).label,
                        announced=format_turn(x.announced_turn),
                        deadline=format_turn(x.deadline_turn),
                        status=x.status,
                    )
                    for x in state.media.laws
                    if x.product_id == p.id
                ],
            )
        )
    last = max((m.turn for m in state.media.ad_months), default=None)
    ads = [
        AdMarketOut(
            region=m.region,
            label=d.region(m.region).label,
            spend_cents=m.spend_cents,
            digital_cents=m.digital_cents,
            impressions_m=m.impressions_m,
            cpm_cents=m.cpm_cents,
        )
        for m in state.media.ad_months
        if m.turn == last
    ]
    apps = [
        ConsumerAppOut(
            product_id=p.id,
            name=p.name,
            ad_pricing=bool((s := state.media.setting(p.id)) and s.ad_pricing),
        )
        for p in state.company_products(state.player.id)
        if p.category == mb.consumer_apps and p.status != "retired"
    ]
    return SocialOut(
        networks=networks,
        formats=[
            FormatOut(key=k, label=social.format_label(k, d, b), month=format_turn(t))
            for k, t in social.eras(state, d)
        ],
        ads=ads,
        consumer_apps=apps,
        ad_pricing_open=state.turn >= month_to_turn(mb.ads.consumer_apps_from),
        load_range=[mb.ads.load_range.lo, mb.ads.load_range.hi],
    )


def media_out(state: GameState, data: LoadedData) -> MediaScreenOut:
    if not enabled(state, data.balance, data.game_data):
        empty = MediaScreenOut(
            studio=StudioOut(
                slate=[],
                released=[],
                catalogue_book_cents=0,
                catalogue_value_cents=0,
                leads=[],
                offers=[],
                kinds=[],
                strikes=[],
                deal_years=[],
            ),
            streaming=StreamingOut(
                services=[],
                ad_tier_open=False,
                ad_tier_from="",
                music_payout=0.0,
                licence_years=[],
            ),
            games=GamesOut(titles=[], generations=[], store_fee=0.0, epic_fee=0.0, epic_open=False),
            social=SocialOut(
                networks=[],
                formats=[],
                ads=[],
                consumer_apps=[],
                ad_pricing_open=False,
                load_range=[],
            ),
        )
        return empty
    return MediaScreenOut(
        studio=_studio(state, data),
        streaming=_streaming(state, data),
        games=_games(state, data),
        social=_social(state, data),
    )
