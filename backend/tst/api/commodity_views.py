"""The Market screen's Commodities tab and the product cost breakdown (M17, formulas.md 33).

What the API may show: prices, indexes and allocation from history and from months already
played, never a month after the one the player is in (`facility_views.current_turn`, M12r's
rule for M12a's goods: commodities share it); deals, suppliers and the company's own use.
"""

from __future__ import annotations

from tst.api.facility_views import Stored, current_turn
from tst.api.schemas.commodities import (
    CommoditiesOut,
    CommodityCostLineOut,
    CommodityOut,
    DealOut,
    PowerOut,
    PricePointOut,
    SupplierGoodOut,
    SupplierOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.commodities import commodity, costs, offtake
from tst.sim.facilities.models import GoodMonth
from tst.sim.state import GameState

MONTHS_PER_YEAR = 12


def month_at(
    good: str, turn: int, state: GameState, data: LoadedData, stored: Stored
) -> GoodMonth | None:
    """A commodity's or region's power month from history or from the months already played,
    never ahead (as facility_views.month_at)."""
    d = data.game_data
    if turn > current_turn(state, data) or turn < 0:
        return None
    history = commodity.history_of(d, good)
    known = commodity.history_month(history, good, turn, commodity.mean_of(d, good))
    if known is not None:
        return known
    return stored.get((good, turn)) or next(
        (g for g in state.supply if g.good == good and g.turn == turn), None
    )


def _history(good: str, state: GameState, data: LoadedData, stored: Stored) -> list[PricePointOut]:
    d, b = data.game_data, data.balance
    now = current_turn(state, data)
    mult = 1.0 if commodity.is_power(good) else commodity.price_multiple(good, b)
    mean = commodity.mean_of(d, good)
    out = []
    for t in range(max(0, now - b.commodity.history_months), now + 1):
        m = month_at(good, t, state, data, stored)
        if m is not None:
            out.append(
                PricePointOut(
                    turn=t,
                    label=format_turn(t),
                    price=m.index * mean * mult,
                    index=m.index,
                    allocation=m.allocation,
                )
            )
    return out


def _now(good: str, state: GameState, data: LoadedData, stored: Stored) -> GoodMonth:
    return month_at(good, current_turn(state, data), state, data, stored) or commodity.current(
        state, good, data.game_data
    )


def _note(month: GoodMonth, turn: int) -> str:
    if month.allocation < 1:
        return f"Short: spot buyers get {month.allocation:.0%}"
    if month.in_shock(turn) and month.shock_kind:
        return f"{month.shock_kind.replace('_', ' ').capitalize()} running"
    return "Full allocation"


def deal_out(state: GameState, deal_id: int, data: LoadedData) -> DealOut:
    d, b = data.game_data, data.balance
    deal = next(x for x in state.commodity_deals if x.id == deal_id)
    assert d.commodities is not None
    supplier = d.suppliers.supplier(deal.supplier) if d.suppliers and deal.supplier else None
    spot = commodity.current(state, deal.good, d).index * commodity.mean_of(d, deal.good)
    spot *= commodity.price_multiple(deal.good, b)
    return DealOut(
        deal_id=deal.id,
        kind=deal.kind,
        good=deal.good,
        good_label=d.commodities.good(deal.good).label,
        supplier=deal.supplier,
        supplier_name=supplier.name if supplier else None,
        signed=format_turn(deal.signed_turn),
        ends=format_turn(deal.end_turn),
        volume_year=deal.volume_year,
        signing_price=deal.signing_price,
        floor=deal.floor,
        ceiling=deal.ceiling,
        price_now=deal.price_for(spot),
        prepaid_cents=deal.prepaid_cents,
        prepaid_left_cents=deal.prepaid_left_cents,
        status=deal.status,
        taken=deal.taken,
        last_taken=deal.last_taken,
        hedge_cents=deal.hedge_cents,
        charged_cents=deal.charged_cents,
    )


def commodities_out(
    state: GameState, data: LoadedData, stored: Stored, company_id: int
) -> CommoditiesOut:
    d, b = data.game_data, data.balance
    assert d.commodities is not None and d.suppliers is not None
    now = current_turn(state, data)
    use = costs.company_use(state, company_id, b, d)
    goods = []
    for g in d.commodities.goods:
        month = _now(g.key, state, data, stored)
        mult = commodity.price_multiple(g.key, b)
        mean = commodity.mean_of(d, g.key)
        year_ago = month_at(g.key, max(0, now - MONTHS_PER_YEAR), state, data, stored)
        goods.append(
            CommodityOut(
                good=g.key,
                label=g.label,
                unit=g.unit,
                volume_unit=g.volume_unit,
                price=month.index * mean * mult,
                index=month.index,
                change_12m=month.index / year_ago.index - 1 if year_ago else 0.0,
                allocation=month.allocation,
                long_run=commodity.history_of(d, g.key).long_run * mult,
                top_country=g.top_country,
                top_share=g.top_share,
                note=_note(month, now),
                use_month=use.get(g.key, 0.0),
                history=_history(g.key, state, data, stored),
            )
        )
    power = [
        PowerOut(
            region=r.key,
            label=r.label,
            index=_now(commodity.power_key(r.key), state, data, stored).index,
            history=_history(commodity.power_key(r.key), state, data, stored),
        )
        for r in d.regions
    ]
    deals = [
        deal_out(state, x.id, data)
        for x in sorted(state.commodity_deals, key=lambda x: (x.status != "active", -x.id))
        if x.company_id == company_id
    ]
    suppliers = []
    for s in d.suppliers.suppliers:
        lo, hi = s.window()
        if (hi is not None and hi < state.turn - MONTHS_PER_YEAR) or lo > state.turn:
            continue  # not yet founded, or gone more than a year
        rev = s.revenue_2010
        suppliers.append(
            SupplierOut(
                key=s.key,
                name=s.name,
                region=s.region,
                region_label=d.region(s.region).label,
                listing=s.listing,
                reliability=s.reliability,
                goods=[
                    SupplierGoodOut(
                        good=k,
                        label=d.commodities.good(k).label,
                        share=v.share,
                        open=s.sells(k, state.turn),
                    )
                    for k, v in s.goods.items()
                ],
                revenue_2010_usd_m=rev.usd_m if rev else None,
                revenue_note=f"{rev.as_printed} ({rev.tag})" if rev else None,
            )
        )
    ob, cb = b.offtake, b.commodity
    return CommoditiesOut(
        goods=goods,
        power=power,
        deals=deals,
        suppliers=suppliers,
        collar=ob.collar,
        prepay_max=ob.prepay_max,
        offtake_years=[int(ob.years.lo), int(ob.years.hi)],
        contract_months=[int(cb.contract_months.lo), int(cb.contract_months.hi)],
        offtake_take_or_pay=ob.take_or_pay,
        contract_take_or_pay=cb.contract_take_or_pay,
        offtake_energy=ob.energy,
        contract_energy=cb.contract_energy,
    )


def cost_lines(
    state: GameState, company_id: int, cost_good: str, base_cents: float, data: LoadedData
) -> list[CommodityCostLineOut]:
    """A unit's commodity lines (33.2) with what the company's deals do to each: the share of
    last month's use its running deals cover, at their price this month."""
    d, b = data.game_data, data.balance
    if d.commodities is None:
        return []
    _, lines = costs.unit_lines(state, cost_good, base_cents, d, b)
    use = costs.company_use(state, company_id, b, d)
    out = []
    for line in lines:
        running = [
            x
            for x in state.commodity_deals
            if x.company_id == company_id and x.good == line.good and x.running(state.turn)
        ]
        spot = offtake.spot_price(state, line.good, d, b)
        volume = sum(x.monthly_volume for x in running)
        used = use.get(line.good, 0.0)
        share = min(1.0, volume / used) if used > 0 else (1.0 if volume else 0.0)
        if running and spot > 0:
            paid = sum(x.monthly_volume * x.price_for(spot) for x in running) / volume
            deal = line.cents * (share * paid / spot + (1 - share))
        else:
            deal = line.cents
        out.append(
            CommodityCostLineOut(
                good=line.good,
                label=d.commodities.good(line.good).label,
                weight=line.weight,
                index=line.index,
                spot_cents=line.cents,
                hedged_share=share,
                deal_cents=deal,
            )
        )
    return out
