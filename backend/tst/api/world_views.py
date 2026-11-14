"""Views of the living world (M28, docs/formulas.md 41.7, 41.9): World news with its filters,
the chain companies by good, and the world section of a company page. Only public facts:
capacities, statuses, a facility's cost band (its third of the cost curve), listed companies'
financials or private ones' estimated ranges, deals, offtakes and news. Never a rival's
valuation of anyone, a cost position, a capex decision before its news, or a cycle's path."""

from __future__ import annotations

from typing import Final

from tst.api.schemas.world import (
    ChainGoodOut,
    ChainOut,
    ChainProducerOut,
    CompanyRefOut,
    ExecutiveOut,
    FinancialsOut,
    MoneyRangeOut,
    NamedOut,
    OfftakeOut,
    SubsidiaryOut,
    WorldCompanyOut,
    WorldDealOut,
    WorldFacilityOut,
    WorldNewsItemOut,
    WorldNewsOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.data_models import GameData
from tst.sim.ledger import LedgerBalances
from tst.sim.mna import formulas as mf
from tst.sim.mna import valuation
from tst.sim.state import CompanyState, GameState, owner_at
from tst.sim.world import data as wd
from tst.sim.world import query as wq
from tst.sim.world.config import FOUNDRY_GOOD
from tst.sim.world.models import ChainCompany, WorldNews

KIND_LABELS: Final[dict[str, str]] = {
    "deal": "Deal",
    "review": "Antitrust review",
    "blocked": "Deal blocked",
    "capacity": "New capacity",
    "built": "Capacity on line",
    "mothball": "Mothballed",
    "restart": "Restarted",
    "close": "Closed",
    "executive": "Executive move",
    "cycle": "Regional cycle",
    "spinoff": "Spin-off",
    "offtake": "Offtake",
    "china": "Chipmaking",
    "failure": "Failure",
    "bid": "Bid",
}
PRIVATE: Final = ("private", "state-owned")  # tunable-exempt: suppliers.yaml listings not traded
TIGHT, SLACK = 1.05, 0.95  # tunable-exempt: the words for a market's factor
MONTHS: Final = 12  # tunable-exempt: calendar
NEWS_ON_PAGE: Final = 12  # tunable-exempt: news items a company page shows


def _ref(state: GameState, company_id: int | None) -> CompanyRefOut | None:
    if company_id is None:
        return None
    return CompanyRefOut(company_id=company_id, name=state.company(company_id).name)


def _good(data: GameData, good: str | None) -> NamedOut | None:
    return None if good is None else NamedOut(key=good, label=wd.label(data, good))


def _region(data: GameData, region: str | None) -> NamedOut | None:
    return None if region is None else NamedOut(key=region, label=data.region(region).label)


def _country(data: GameData, country: str) -> str:
    assert data.countries is not None
    return data.countries.country(country).label


def unit(data: GameData, good: str) -> str:
    if good == FOUNDRY_GOOD:
        return "wafers"
    assert data.commodities is not None
    return data.commodities.good(good).volume_unit


def news_item(state: GameState, data: GameData, n: WorldNews) -> WorldNewsItemOut:
    return WorldNewsItemOut(
        news_id=n.id,
        turn=n.turn,
        date_label=format_turn(n.turn),
        kind=n.kind,
        kind_label=KIND_LABELS.get(n.kind, n.kind),
        message=n.message,
        company=_ref(state, n.company_id),
        other=_ref(state, n.other_id),
        region=_region(data, n.region),
        good=_good(data, n.good),
    )


def world_news(
    state: GameState,
    data: LoadedData,
    company: int | None = None,
    region: str | None = None,
    good: str | None = None,
    kind: str | None = None,
) -> WorldNewsOut:
    d = data.game_data
    items = list(reversed(state.world_news))
    named = sorted(
        {x for n in items for x in (n.company_id, n.other_id) if x is not None},
        key=lambda cid: state.company(cid).name,
    )
    regions = sorted({n.region for n in items if n.region})
    goods = sorted({n.good for n in items if n.good})
    kinds = sorted({n.kind for n in items})
    picked = [
        n
        for n in items
        if (company is None or company in (n.company_id, n.other_id))
        and (region is None or n.region == region)
        and (good is None or n.good == good)
        and (kind is None or n.kind == kind)
    ]
    return WorldNewsOut(
        started=wq.started(state),
        items=[news_item(state, d, n) for n in picked],
        companies=[r for r in (_ref(state, c) for c in named) if r is not None],
        regions=[r for r in (_region(d, x) for x in regions) if r is not None],
        goods=[g for g in (_good(d, x) for x in goods) if g is not None],
        kinds=[NamedOut(key=k, label=KIND_LABELS.get(k, k)) for k in kinds],
    )


def _market(factor: float) -> str:
    if factor > TIGHT:
        return "tight"
    if factor < SLACK:
        return "slack"
    return "balanced"


def chain(state: GameState, data: LoadedData) -> ChainOut:
    """The chain companies by good: capacity, output and utilisation (`tst world`)."""
    d = data.game_data
    if not wq.started(state) or not wd.has_world(d):
        return ChainOut(started=False, goods=[])
    out = []
    for g in wd.all_goods(d):
        w = wq.world_good(state, g)
        fs = [f for f in state.world_facilities if f.good == g]
        live = sum(f.capacity for f in fs if f.status == "live")
        producers = []
        for rec in state.chain_companies:
            mine = [f for f in fs if f.company_id == rec.company_id]
            if not mine:
                continue
            cap = sum(f.capacity for f in mine if f.status == "live")
            held = owner_at(state, rec.company_id)
            producers.append(
                ChainProducerOut(
                    company_id=rec.company_id,
                    name=state.company(rec.company_id).name,
                    country_label=_country(d, rec.country),
                    capacity_year=cap,
                    building=sum(f.capacity for f in mine if f.status == "building"),
                    mothballed=sum(f.capacity for f in mine if f.status == "mothballed"),
                    share=cap / live if live else 0.0,
                    owner=_ref(state, held.owner_id) if held else None,
                )
            )
        output = sum(f.output for f in fs if f.status == "live") * MONTHS
        out.append(
            ChainGoodOut(
                good=g,
                label=wd.label(d, g),
                unit=unit(d, g),
                capacity_year=live,
                output_year=output,
                utilisation=output / live if live else 0.0,
                market=_market(w.factor) if w else "balanced",
                producers=sorted(producers, key=lambda p: (-p.capacity_year, p.company_id)),
            )
        )
    return ChainOut(started=True, goods=out)


def _listed_chain(data: GameData, key: str) -> bool:
    if data.nodes is not None and any(f.key == key for f in data.nodes.foundries):
        return True
    s = data.suppliers.supplier(key) if data.suppliers else None
    return s is not None and not s.listing.lower().startswith(PRIVATE)


def _range(state: GameState, company: CompanyState, value: int, half: float) -> MoneyRangeOut:
    low, high = mf.displayed_range(
        mf.value_range_cents(value, valuation.range_draw(state, company), half)
    )
    return MoneyRangeOut(low_cents=low, high_cents=high)


def company_world(
    state: GameState, company: CompanyState, balances: LedgerBalances, data: LoadedData
) -> WorldCompanyOut | None:
    """The world section of a rival's company page (41.7); None before the world runs."""
    d, b = data.game_data, data.balance
    if not wq.started(state):
        return None
    rec = wq.chain_record(state, company.id)
    held = owner_at(state, company.id)
    mandate = next((m.kind for m in state.rival_mandates if m.company_id == company.id), None)
    subs = [
        SubsidiaryOut(
            company=CompanyRefOut(company_id=o.company_id, name=state.company(o.company_id).name),
            mandate=next(
                (m.kind for m in state.rival_mandates if m.company_id == o.company_id), "grow"
            ),
            since_label=format_turn(o.from_turn),
        )
        for o in state.ownerships
        if o.owner_id == company.id and o.is_open
    ]
    facilities = [
        WorldFacilityOut(
            facility_id=f.id,
            good=f.good,
            good_label=wd.label(d, f.good),
            country=f.country,
            country_label=_country(d, f.country),
            region=f.region,
            capacity_year=f.capacity,
            unit=unit(d, f.good),
            status=f.status,
            cost_band=wq.cost_band(f.cost),
            ready_label=format_turn(f.ready_turn) if f.status == "building" else None,
        )
        for f in wq.facilities_of(state, company.id)
    ]
    financials = None
    if rec is not None:
        revenue = rec.revenue_cents * MONTHS
        ebitda = sum(rec.ebitda) * MONTHS // len(rec.ebitda) if rec.ebitda else 0
        if _listed_chain(d, rec.key) and held is None and not rec.is_other:
            financials = FinancialsOut(
                listed=True,
                revenue_year_cents=revenue,
                ebitda_year_cents=ebitda,
                revenue_range=None,
                ebitda_range=None,
            )
        else:
            financials = FinancialsOut(
                listed=False,
                revenue_year_cents=None,
                ebitda_year_cents=None,
                revenue_range=_range(state, company, revenue, b.mna.range),
                ebitda_range=_range(state, company, max(0, ebitda), b.mna.range),
            )
    deals = [
        WorldDealOut(
            date_label=format_turn(x.agreed_turn),
            buyer=CompanyRefOut(company_id=x.buyer_id, name=state.company(x.buyer_id).name),
            target=CompanyRefOut(company_id=x.target_id, name=state.company(x.target_id).name),
            price_cents=x.price_cents,
            kind=x.kind,
            status=x.status,
        )
        for x in state.rival_deals
        if company.id in (x.buyer_id, x.target_id)
    ]
    offtakes = [
        OfftakeOut(
            buyer=CompanyRefOut(company_id=o.buyer_id, name=state.company(o.buyer_id).name),
            seller=CompanyRefOut(company_id=o.seller_id, name=state.company(o.seller_id).name),
            good_label=wd.label(d, o.good),
            volume=o.volume,
            unit=unit(d, o.good),
            ends_label=format_turn(o.end_turn),
        )
        for o in state.world_offtakes
        if company.id in (o.buyer_id, o.seller_id) and o.end_turn >= state.turn
    ]
    news = [
        news_item(state, d, n)
        for n in reversed(state.world_news)
        if company.id in (n.company_id, n.other_id)
    ][:NEWS_ON_PAGE]
    return WorldCompanyOut(
        kind="chain" if rec is not None else "tech",
        country_label=_country(d, rec.country) if rec is not None else None,
        owner=_ref(state, held.owner_id) if held is not None else None,
        subsidiaries=subs,
        mandate=mandate,
        executives=_executives(company, rec),
        facilities=facilities,
        financials=financials,
        deals=deals,
        offtakes=offtakes,
        news=news,
    )


def _executives(company: CompanyState, rec: ChainCompany | None) -> list[ExecutiveOut]:
    """A chain company's named executives, the CEO first (41.1); a tech rival's are its key
    people on the page already."""
    if rec is None:
        return []
    return [
        ExecutiveOut(
            role=role,
            name=name,
            since_label=format_turn(rec.ceo_since if i == 0 else company.founded_turn),
        )
        for i, (role, name) in enumerate(rec.executives)
    ]
