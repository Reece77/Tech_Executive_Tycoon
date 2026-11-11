"""The Mines screen's read model (M19, formulas.md 35). Every number comes from what has been
revealed: the feasibility study's estimates and ranges, the revised cost once revised, months
already mined (their output and reconciled grade), costs and sales, and public data. Nothing
reads a mine's hidden_* fields (the overrun before revision, the deposit's tonnage, grade and
recovery), so two mines with the same revealed history look the same (the differential test
in tests/integration/test_api_mining.py)."""

from __future__ import annotations

import math

from tst.api import howto
from tst.api.schemas.mining import (
    MineDealOut,
    MineMonthOut,
    MineOut,
    MineQuoteOut,
    MinesOut,
    MiningCompanyOut,
    RegionEventOut,
    RegionRiskOut,
    RivalBidOut,
    RivalMinerOut,
    TransferAssetOut,
    UnitOptionOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.errors import SimError
from tst.sim.exploration import pipeline as xp
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.mining import formulas as mf
from tst.sim.mining import phase as mp
from tst.sim.mining import prices, risk
from tst.sim.mining.actions import mine_name, quote
from tst.sim.mining.config import SAFETY
from tst.sim.mining.models import Mine
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, holding_of

MT = 1e6
EVENT_MONTHS = 24  # months of region events the screen lists
ROLES = {"operating": "operating", "holding": "holding"}


def _commodity_label(data: LoadedData, key: str | None) -> str:
    geo = data.game_data.geology
    if key is None or geo is None:
        return "Minerals"
    return geo.commodity(key).label


def _region_of(state: GameState, company_id: int, data: LoadedData) -> str | None:
    city = state.company(company_id).hq_city
    return next((c.region for c in data.game_data.cities if c.key == city), None)


def companies_out(
    state: GameState, balances: LedgerBalances, data: LoadedData
) -> list[MiningCompanyOut]:
    held = holding_of(state)
    out = []
    for c in xp.explorers(state):
        role = (
            "operating"
            if c.id == state.player.id
            else ("holding" if held is not None and c.id == held.company_id else "subsidiary")
        )
        out.append(
            MiningCompanyOut(
                id=c.id,
                name=c.name,
                role=role,
                region=_region_of(state, c.id, data),
                cash_cents=account_balance(balances, c.id, CASH),
            )
        )
    return out


def _reserves(state: GameState, mine: Mine) -> tuple[float | None, float | None]:
    """The resource estimate's range of product left: estimated ore (low, high) less the ore
    mined, at the design grade and recovery. Never the truth."""
    project = next((p for p in state.projects if p.id == mine.project_id), None)
    if project is None or project.est_tonnage_center is None or project.est_tonnage_hw is None:
        return None, None
    per_mt = MT * mine.design_grade * mine.design_recovery
    lo = math.exp(project.est_tonnage_center - project.est_tonnage_hw) - mine.ore_mined_mt
    hi = math.exp(project.est_tonnage_center + project.est_tonnage_hw) - mine.ore_mined_mt
    return max(0.0, lo) * per_mt, max(0.0, hi) * per_mt


def _open_event(mine: Mine) -> str | None:
    if mine.accident_turn is not None:
        return "accident"
    if mine.takeover_turn is not None:
        return "takeover"
    if mine.crash_turn is not None:
        return "crash"
    return None


def mine_out(state: GameState, mine: Mine, data: LoadedData) -> MineOut:
    b, d = data.balance, data.game_data
    mb = b.mining
    team = mp.crew(state, mine, b)
    facility = state.facility(mine.id)
    spot = prices.spot_usd_t(state, mine.commodity, d, b)
    last = next((m for m in reversed(mine.history) if m.output_t > 0), None)
    lo, hi = _reserves(state, mine)
    over = mb.overrun[mine.level]
    months = mine.ready_turn - mine.ordered_turn
    copper = mine.commodity == "copper"
    expected = mp.would_be_cost_usd_t(state, mine, b, d)
    return MineOut(
        id=mine.id,
        name=mine_name(mine, d),
        company_id=mine.company_id,
        company_name=state.company(mine.company_id).name,
        project_id=mine.project_id,
        region=mine.region,
        region_label=d.region(mine.region).label,
        commodity=mine.commodity,
        commodity_label=_commodity_label(data, mine.commodity),
        subtype=mine.subtype,
        subtype_label=mb.subtypes[mine.subtype].label,
        status=mine.status,
        level=mine.level,
        capacity_t=mine.capacity_t,
        ordered_label=format_turn(mine.ordered_turn),
        ready_label=format_turn(mine.ready_turn),
        construction_months=months,
        construction_done=min(months, max(0, state.turn - mine.ordered_turn)),
        estimate_cents=mine.estimate_cents,
        overrun_low=over.lo,
        overrun_high=over.hi,
        revised_cents=mine.revised_cents,  # None until revised: the overrun stays hidden
        capex_paid_cents=mine.capex_paid_cents,
        book_cents=mine.book_cents,
        reclamation_owed_cents=mine.aro_cents - mine.aro_paid_cents,
        reclamation_provisioned_cents=mine.aro_cents,
        product_t=mine.product_t,
        reserves_low_t=lo,
        reserves_high_t=hi,
        last_output_t=mine.history[-1].output_t if mine.history else None,
        last_grade=last.grade if last else None,
        design_grade=mine.design_grade,
        price_usd_t=spot,
        price_usd_lb=mf.usd_per_lb(spot) if copper else None,
        cost_usd_t=last.cost_usd_t if last else None,
        cost_usd_lb=mf.usd_per_lb(last.cost_usd_t) if last and copper else None,
        expected_cost_usd_t=expected,
        staff=team.staff,
        staff_needed=team.needed,
        coverage=team.coverage,
        unit_id=facility.unit_id if facility else None,
        safety=mine.safety,
        buyer_id=mine.buyer_id,
        buyer_name=state.company(mine.buyer_id).name if mine.buyer_id is not None else None,
        price_kind=mine.price_kind,
        margin=mine.margin,
        state_share=mine.state_share,
        ban_until_label=(
            format_turn(mine.ban_until)
            if mine.ban_until is not None and mine.ban_until >= state.turn
            else None
        ),
        below_cost_months=mine.below_months,
        accidents=mine.accidents,
        open_event=_open_event(mine),
        arbitration_label=(
            format_turn(mine.arbitration_due) if mine.arbitration_due is not None else None
        ),
        closed_label=format_turn(mine.closed_turn) if mine.closed_turn is not None else None,
        close_reason=mine.close_reason,
        history=[
            MineMonthOut(
                turn=m.turn,
                label=format_turn(m.turn),
                output_t=m.output_t,
                grade=m.grade,
                price_usd_t=m.price_usd_t,
                cost_usd_t=m.cost_usd_t,
                revenue_cents=m.revenue_cents,
                margin_cents=m.margin_cents,
            )
            for m in mine.history
        ],
        deals=[
            MineDealOut(
                id=x.id,
                kind=x.kind,
                buyer=x.buyer,
                signed_label=format_turn(x.signed_turn),
                end_label=format_turn(x.end_turn),
                volume_t_year=x.volume_t_year,
                floor_usd_t=x.floor_usd_t,
                ceiling_usd_t=x.ceiling_usd_t,
                delivered_t=x.delivered_t,
                running=x.running(state.turn),
            )
            for x in state.mine_deals
            if x.mine_id == mine.id
        ],
    )


def quotes_out(state: GameState, data: LoadedData) -> list[MineQuoteOut]:
    """Permitted projects of the group without a mine, with what a build would be."""
    b, d = data.balance, data.game_data
    group = {c.id for c in xp.explorers(state)}
    built = {m.project_id for m in state.mines if m.status != "closed"}
    out = []
    for p in sorted(state.projects, key=lambda p: p.id):
        if p.company_id not in group or p.status != "permitted" or p.id in built:
            continue
        try:
            q = quote(state, p, None, b, d)
        except SimError as exc:
            out.append(
                MineQuoteOut(
                    project_id=p.id,
                    label=xp.label_of(p),
                    company_id=p.company_id,
                    company_name=state.company(p.company_id).name,
                    commodity=p.commodity or "",
                    commodity_label=_commodity_label(data, p.commodity),
                    region=p.region,
                    subtype="",
                    subtype_label="",
                    level=p.level or "",
                    design_t=0,
                    capacity_low_t=0,
                    capacity_high_t=0,
                    estimate_cents=0,
                    capex_scale=b.mining.capex_scale,
                    construction_low=0,
                    construction_high=0,
                    overrun_low=0,
                    overrun_high=0,
                    staff_needed=0,
                    npv_low_cents=p.npv_lo_cents,
                    npv_mid_cents=p.npv_mid_cents,
                    npv_high_cents=p.npv_hi_cents,
                    allowed=False,
                    reason=str(exc),
                    how=howto.mine_quote_how(str(exc)),
                )
            )
            continue
        out.append(
            MineQuoteOut(
                project_id=p.id,
                label=xp.label_of(p),
                company_id=p.company_id,
                company_name=state.company(p.company_id).name,
                commodity=p.commodity or "",
                commodity_label=_commodity_label(data, p.commodity),
                region=p.region,
                subtype=q.subtype,
                subtype_label=b.mining.subtypes[q.subtype].label,
                level=p.level or "",
                design_t=q.design_t,
                capacity_low_t=q.capacity_lo_t,
                capacity_high_t=q.capacity_hi_t,
                estimate_cents=q.estimate_cents,
                capex_scale=b.mining.capex_scale,
                construction_low=q.construction_lo,
                construction_high=q.construction_hi,
                overrun_low=q.overrun_lo,
                overrun_high=q.overrun_hi,
                staff_needed=q.staff_needed,
                npv_low_cents=p.npv_lo_cents,
                npv_mid_cents=p.npv_mid_cents,
                npv_high_cents=p.npv_hi_cents,
                allowed=True,
                reason="",
                how="",
            )
        )
    return out


def assets_out(state: GameState, data: LoadedData) -> list[TransferAssetOut]:
    b = data.balance
    group = {c.id for c in xp.explorers(state)}
    out = []
    built = {m.project_id for m in state.mines if m.is_open}
    for p in sorted(state.projects, key=lambda p: p.id):
        if p.company_id in group and p.status in ("active", "permitted") and p.id not in built:
            out.append(
                TransferAssetOut(
                    kind="project",
                    id=p.id,
                    label=xp.label_of(p) + (" (permitted)" if p.status == "permitted" else ""),
                    company_id=p.company_id,
                    company_name=state.company(p.company_id).name,
                    book_cents=0,
                )
            )
    for f in sorted(state.facilities, key=lambda f: f.id):
        if f.company_id not in group or f.status == "closed":
            continue
        mine = state.mine(f.id)
        label = (
            mine_name(mine, data.game_data)
            if mine is not None
            else f"{b.facility.kinds[f.kind].label} #{f.id}"
        )
        out.append(
            TransferAssetOut(
                kind="facility",
                id=f.id,
                label=label,
                company_id=f.company_id,
                company_name=state.company(f.company_id).name,
                book_cents=mine.book_cents if mine is not None else f.book_value_cents,
            )
        )
    return out


def units_out(state: GameState, data: LoadedData) -> list[UnitOptionOut]:
    roles = set(data.balance.facility.kinds["mine"].staff_roles)
    group = {c.id for c in xp.explorers(state)}
    out = []
    for u in state.units:
        if u.company_id not in group or u.status != "active":
            continue
        engineers = sum(
            1
            for e in state.staff(u.company_id)
            if e.unit_id == u.id and e.role in roles and e.status == "active"
        )
        staffs = next((f.id for f in state.facilities if f.unit_id == u.id), None)
        out.append(
            UnitOptionOut(
                id=u.id,
                name=u.name,
                company_name=state.company(u.company_id).name,
                mining_engineers=engineers,
                staffs=staffs,
            )
        )
    return out


def bids_out(state: GameState, data: LoadedData) -> list[RivalBidOut]:
    out = []
    names = {
        s.key: s.name
        for s in (data.game_data.suppliers.suppliers if data.game_data.suppliers else ())
    }
    for bid in state.rival_bids:
        if bid.status != "open":
            continue
        if bid.project_id is not None:
            asset = xp.label_of(xp.project_of(state, bid.project_id))
        else:
            m = state.mine(bid.mine_id or 0)
            asset = mine_name(m, data.game_data) if m is not None else "a mine"
        out.append(
            RivalBidOut(
                id=bid.id,
                bidder=names.get(bid.supplier, bid.supplier),
                asset=asset,
                project_id=bid.project_id,
                mine_id=bid.mine_id,
                cents=bid.cents,
                expires_label=format_turn(bid.expires_turn),
            )
        )
    return out


def events_out(state: GameState, data: LoadedData) -> list[RegionEventOut]:
    """History to the current month (the last EVENT_MONTHS seeded months after 2025)."""
    b, d = data.balance, data.game_data
    if d.nationalization is None:
        return []
    rng = RngFactory(state.save_meta.master_seed)
    found = [
        risk.RegionEvent(e.turn, e.region, e.commodity, e.kind, e.months, e.title, False)
        for e in d.nationalization.events
        if e.turn <= state.turn
    ]
    start = max(d.nationalization.last_turn + 1, state.turn - EVENT_MONTHS + 1)
    for t in range(start, state.turn + 1):
        found += risk.region_events(rng, t, b, d)
    return [
        RegionEventOut(
            turn=e.turn,
            label=format_turn(e.turn),
            region=e.region,
            region_label=d.region(e.region).label,
            commodity=e.commodity,
            kind=e.kind,
            months=e.months,
            title=e.title,
            seeded=e.seeded,
        )
        for e in sorted(found, key=lambda e: (-e.turn, e.region))
    ]


def rivals_out(state: GameState, data: LoadedData) -> list[RivalMinerOut]:
    b, d = data.balance, data.game_data
    rng = RngFactory(state.save_meta.master_seed)
    return [
        RivalMinerOut(
            supplier=r.supplier,
            name=r.name,
            commodity=r.commodity,
            commodity_label=_commodity_label(data, r.commodity),
            region=r.region,
            region_label=d.region(r.region).label,
            start_share=r.start_share,
            capacity_share=r.capacity_share,
            output_share=r.output_share,
        )
        for r in risk.rival_capacity(rng, state.turn, state, b, d)
    ]


def mines_out(state: GameState, balances: LedgerBalances, data: LoadedData) -> MinesOut:
    b, d = data.balance, data.game_data
    mb = b.mining
    group = {c.id for c in xp.explorers(state)}
    return MinesOut(
        turn_label=format_turn(state.turn),
        group_stage=max(c.stage for c in xp.explorers(state)),
        found_min_stage=mb.found.min_stage,
        found_how=howto.stage_how(
            mb.found.min_stage,
            max(c.stage for c in xp.explorers(state)),
            "founding a subsidiary",
        ),
        found_min_cents=mb.found.min_cents,
        found_energy=mb.found.energy,
        build_energy=mb.build_energy,
        companies=companies_out(state, balances, data),
        mines=[mine_out(state, m, data) for m in state.mines if m.company_id in group],
        quotes=quotes_out(state, data),
        assets=assets_out(state, data),
        units=units_out(state, data),
        bids=bids_out(state, data),
        events=events_out(state, data),
        regions=[
            RegionRiskOut(
                key=r.key,
                label=r.label,
                royalty_rate=r.royalty_rate,
                resource_nationalism=r.resource_nationalism,
            )
            for r in d.regions
        ],
        rivals=rivals_out(state, data),
        transfer_kinds=list(mb.transfer_kinds),
        safety_levels=list(SAFETY),
        contract_months=[round(mb.sale.contract_months.lo), round(mb.sale.contract_months.hi)],
        offtake_years=[round(mb.sale.offtake_years.lo), round(mb.sale.offtake_years.hi)],
    )
