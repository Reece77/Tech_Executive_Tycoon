"""The commodity planning view (M23c, playtest 5: "Only last month's use is shown; wants a
planning view: need next year, which products drive it, offtake cover").

For each commodity the company uses: the next 12 months' need at this month's production
(the same use per unit as the engine's commodity cost, tst.sim.commodities.costs), which
products drive it, and how much the running contracts and offtakes and the group's own supply
cover, month by month as deals end. Display only: a projection at the current run rate, not a
forecast of demand, and no hidden value."""

from __future__ import annotations

from typing import Final

from tst.api.schemas.commodities import (
    CommodityPlanDriverOut,
    CommodityPlanMonthOut,
    CommodityPlanOut,
    CommodityPlansOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.commodities import costs
from tst.sim.state import GameState, group_members, listed_id

MONTHS: Final = 12  # tunable-exempt: the planning horizon the brief names
EPS: Final = 1e-9
KG_A_T: Final = 1000.0


def _product_use(
    state: GameState, company_id: int, data: LoadedData
) -> dict[str, dict[int, float]]:
    """good -> product id -> volume units a month, at the production month's output (the
    engine's company_use, split by product)."""
    from tst.sim.chips import chips

    b, d = data.balance, data.game_data
    out: dict[str, dict[int, float]] = {}
    for row in state.production:
        if row.company_id != company_id:
            continue
        product = state.product(row.product_id)
        if product is None:
            continue
        if chips.is_chip(product, d):
            mix = costs.mix_of(b.chips.good, b)
            if mix is None:
                continue
            t = chips.type_of(product, d, b)
            y = chips.chip_yield(state, company_id, b, d)
            wafers = (row.units + row.internal_units) / max(EPS, t.per_wafer * y)
            per = costs.use_per_unit(t.wafer_cents, mix, d)
            for g, q in per.items():
                out.setdefault(g, {})[product.id] = out.get(g, {}).get(product.id, 0.0) + wafers * q
            continue
        bom = b.hardware.bom.get(product.category)
        mix = costs.mix_of(bom.good, b) if bom else None
        if bom is None or mix is None:
            continue
        for g, q in costs.use_per_unit(bom.base_cents, mix, d).items():
            out.setdefault(g, {})[product.id] = out.get(g, {}).get(product.id, 0.0) + row.units * q
    return out


def _group(state: GameState) -> set[int]:
    root = listed_id(state)
    return {root, state.player.id, *(m.company_id for m in group_members(state, root))}


def _own_supply(state: GameState, company_id: int, good: str) -> float:
    """What the group's own plants supplied the company of the good in the completed month.
    M23r (Codex review 6 finding 6): between turns `state.turn` is the next month to play and
    the settled lots carry the month just played (ADR-0014 2), as the production rows that the
    demand reads do; the plan's buyer is `company_id`, its sellers any plant of the group."""
    group = _group(state)
    done = state.turn - 1
    return sum(
        s.volume
        for s in state.own_supply
        if s.good == good and s.turn == done and s.buyer_id == company_id and s.seller_id in group
    )


def _mine_output(state: GameState, good: str, volume_unit: str) -> float:
    """The group's mines' latest monthly output of the good, in its volume unit."""
    group = _group(state)
    total = 0.0
    for m in state.mines:
        if m.company_id in group and m.commodity == good and m.status == "producing" and m.history:
            total += m.history[-1].output_t
    return total * (KG_A_T if volume_unit == "kg" else 1.0)


def commodity_plans(state: GameState, company_id: int, data: LoadedData) -> CommodityPlansOut:
    d = data.game_data
    assert d.commodities is not None
    use = _product_use(state, company_id, data)
    names = {p.id: p.name for p in state.products}
    plans = []
    for g in d.commodities.goods:
        by_product = use.get(g.key, {})
        need_month = sum(by_product.values())
        deals = [
            x
            for x in state.commodity_deals
            if x.company_id == company_id and x.good == g.key and x.status == "active"
        ]
        own = _own_supply(state, company_id, g.key)
        mined = _mine_output(state, g.key, g.volume_unit)
        if need_month <= EPS and not deals and own <= EPS and mined <= EPS:
            continue
        months = []
        for i in range(1, MONTHS + 1):
            turn = state.turn + i
            covered = sum(x.monthly_volume for x in deals if x.signed_turn <= turn <= x.end_turn)
            months.append(
                CommodityPlanMonthOut(
                    turn=turn,
                    label=format_turn(turn),
                    required=need_month,
                    deals=covered,
                    own=own,
                    gap=max(0.0, need_month - covered - own),
                )
            )
        need = need_month * MONTHS
        dealt = sum(m.deals for m in months)
        owned = own * MONTHS
        plans.append(
            CommodityPlanOut(
                good=g.key,
                label=g.label,
                volume_unit=g.volume_unit,
                need_month=need_month,
                need_12m=need,
                deals_12m=dealt,
                own_12m=owned,
                mines_12m=mined * MONTHS,
                cover=min(1.0, (dealt + owned) / need) if need > EPS else None,
                gap_12m=max(0.0, need - dealt - owned),
                drivers=[
                    CommodityPlanDriverOut(
                        product_id=pid,
                        name=names.get(pid, f"#{pid}"),
                        need_month=v,
                        share=v / need_month if need_month > EPS else 0.0,
                    )
                    for pid, v in sorted(by_product.items(), key=lambda kv: -kv[1])
                ],
                deals_ending=[
                    format_turn(x.end_turn) for x in deals if x.end_turn < state.turn + MONTHS
                ],
                months=months,
            )
        )
    plans.sort(key=lambda p: -p.need_12m)
    return CommodityPlansOut(turn_label=format_turn(state.turn), months=MONTHS, plans=plans)
