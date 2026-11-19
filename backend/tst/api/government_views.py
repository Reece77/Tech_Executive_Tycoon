"""Building the Government API's responses (M44, docs/formulas.md 57.7) from the state: tenders
from their announcement month, the player's own bids as score bands, awards and protests as
published, contracts, clearance statuses (never a pending one's due month or outcome) and
budgets to this year. Rivals' bids are never stored, so nothing here can show one."""

from __future__ import annotations

from typing import Final

from tst.api.schemas.government import (
    ClearanceOut,
    DefenceRecordOut,
    FacilityClearanceOut,
    FacilityOptionOut,
    GovBuyerOut,
    GovContractOut,
    GovernmentScreenOut,
    MyBidOut,
    RivalAwardOut,
    ScoreBandOut,
    StaffOptionOut,
    TenderOptionOut,
    TenderOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.facilities.lifecycle import facility_name
from tst.sim.government import awards
from tst.sim.government.data import (
    PCT,
    announced,
    area_of,
    budget_cents,
    company_bloc,
    domestic_countries,
    file,
    is_large,
    scale,
    year_of,
)
from tst.sim.government.models import Bid, Tender
from tst.sim.government.sourcing import HARDWARE_AREAS, LEVEL_LABEL, requirements
from tst.sim.money import exact
from tst.sim.state import GameState

LIVE_BIDS: Final = ("submitted", "won", "lost", "disqualified")


def _band(value: float, width: int) -> str:
    lo = int(min(PCT - width, max(0.0, value)) // width * width)
    return f"{lo}-{lo + width}"


def _bid_out(state: GameState, bid: Bid, tender: Tender, data: LoadedData) -> MyBidOut:
    b = data.balance
    width = b.government.bids.band
    product = state.product(bid.product_id)
    band = None
    if bid.terms is not None and bid.status in ("won", "lost"):
        band = ScoreBandOut(
            total=_band(bid.terms.total, width),
            price=_band(bid.terms.price, width),
            technical=_band(bid.terms.technical, width),
            past_performance=_band(bid.terms.past_performance, width),
        )
    can_protest = (
        bid.status in ("lost", "disqualified")
        and not bid.protested
        and tender.round == 0
        and tender.status == "awarded"
        and state.turn <= tender.award_turn + b.government.protests.window_months
    )
    return MyBidOut(
        id=bid.id,
        tender_id=bid.tender_id,
        product_id=bid.product_id,
        product=product.name if product is not None else "",
        price_cents=bid.price_cents,
        team=list(bid.team),
        month=format_turn(bid.turn),
        status=bid.status,
        band=band,
        score_floor=(
            int(min(PCT - width, max(0.0, bid.terms.total)) // width * width)
            if band is not None and bid.terms is not None
            else None
        ),
        reasons=list(bid.reasons),
        can_protest=can_protest,
    )


def tender_requirements(state: GameState, tender: Tender, data: LoadedData) -> list[str]:
    b, d = data.balance, data.game_data
    f = file(d)
    gov = f.government(tender.government)
    out = [f"bidders from {', '.join(x.replace('_', '-') for x in gov.open_to)} countries"]
    if tender.clearance != "none":
        need = b.government.clearances.required.get(tender.clearance, 0)
        out.append(
            f"{need} staff cleared at {LEVEL_LABEL[tender.clearance]} and a cleared facility"
        )
        if tender.area == "cloud":
            out.append(f"a data centre in {gov.label}")
    if tender.buyer == "defence" and gov.refuses:
        out.append(
            f"no defence work for {', '.join(x.replace('_', '-') for x in gov.refuses)} militaries"
        )
    if tender.area in HARDWARE_AREAS:
        for ban in f.bans:
            if tender.government in ban.governments and state.turn >= ban.start_turn:
                out.append(ban.label)
        for rule in f.domestic_content:
            if tender.government in rule.governments and tender.area in rule.areas:
                share = rule.share_at(state.turn)
                if share > 0:
                    where = ", ".join(domestic_countries(gov))
                    out.append(f"at least {share * PCT:.0f}% made in {where} (domestic content)")
    tf = f.trusted_foundry
    if tender.area == "chips" and tender.buyer == "defence" and tender.government in tf.governments:
        out.append("chips from a trusted foundry")
    return out


def _options(state: GameState, tender: Tender, data: LoadedData) -> list[TenderOptionOut]:
    b, d = data.balance, data.game_data
    player = state.player
    out = []
    for p in state.products:
        if p.company_id != player.id or p.status != "live" or area_of(p, d) != tender.area:
            continue
        unmet = requirements(state, player, p, tender, b, d)
        out.append(
            TenderOptionOut(
                product_id=p.id, product=p.name, quality=round(p.quality, 1), unmet=list(unmet)
            )
        )
    return out


def _tender_out(state: GameState, tender: Tender, data: LoadedData) -> TenderOut:
    f = file(data.game_data)
    gov = f.government(tender.government)
    bid = next(
        (
            x
            for x in state.gov_bids
            if x.tender_id == tender.id
            and x.company_id == state.player.id
            and x.status in LIVE_BIDS
        ),
        None,
    )
    protest = None
    if tender.status == "protested":
        p = next((x for x in reversed(state.protests) if x.tender_id == tender.id), None)
        protest = p.by if p is not None else None
    awarded = tender.status in ("awarded", "protested", "cancelled")
    open_now = tender.status == "open" and state.turn < tender.close_turn
    return TenderOut(
        id=tender.id,
        title=tender.title,
        government=tender.government,
        government_label=gov.label,
        area=tender.area,
        buyer=tender.buyer,
        contract=tender.contract,
        clearance=tender.clearance,
        value_cents=tender.value_cents,
        term_months=tender.term_months,
        base_months=tender.base_months,
        awards=tender.awards,
        large=is_large(tender, data.balance),
        announced=format_turn(tender.announce_turn),
        closes=format_turn(tender.close_turn),
        award_month=format_turn(tender.award_turn),
        status=tender.status,
        historical=bool(tender.key),
        winners=list(tender.winners) if awarded else [],
        winning_band=(
            _band(tender.winning_band, data.balance.government.bids.band)
            if awarded and tender.winning_band is not None
            else None
        ),
        protest_by=protest,
        requirements=tender_requirements(state, tender, data),
        options=_options(state, tender, data) if open_now else [],
        my_bid=_bid_out(state, bid, tender, data) if bid is not None else None,
    )


def government_out(state: GameState, data: LoadedData) -> GovernmentScreenOut:
    b, d = data.balance, data.game_data
    player = state.player
    month = format_turn(state.turn)
    if d.government is None:
        return GovernmentScreenOut(
            month=month,
            enabled=False,
            governments=[],
            tenders=[],
            contracts=[],
            clearances=[],
            facility_clearances=[],
            staff=[],
            facilities=[],
            rivals=[],
            record=DefenceRecordOut(
                awards=0,
                blocs=[],
                brand_lost=0,
                reactions=0,
                controlled_products=[],
                past_performance=0,
            ),
            clearance_cost_cents={},
            facility_cost_cents=0,
            protest_cost_cents=0,
        )
    f = file(d)
    turn = state.turn
    year = year_of(turn)
    shown = [t for t in state.tenders if announced(t, turn)]
    shown.sort(key=lambda t: (t.status != "open", -t.announce_turn, t.id))
    try:
        bloc = company_bloc(state, player, b, d)
    except (KeyError, StopIteration):
        bloc = ""
    governments = [
        GovBuyerOut(
            key=g.key,
            label=g.label,
            country=g.country,
            defence_cents_year=round(budget_cents(state, g, year, b, civil=False)),
            civil_cents_year=round(budget_cents(state, g, year, b, civil=True)),
            open_to=list(g.open_to),
            refuses=list(g.refuses),
            open_tenders=sum(1 for t in shown if t.government == g.key and t.status == "open"),
            you_may_bid=bloc in g.open_to,
        )
        for g in f.governments
    ]
    contracts = []
    for c in state.gov_contracts:
        if c.company_id != player.id:
            continue
        t = state.tender(c.tender_id)
        product = state.product(c.product_id)
        contracts.append(
            GovContractOut(
                id=c.id,
                tender_id=c.tender_id,
                title=t.title if t is not None else f"Contract {c.id}",
                government_label=f.government(c.government).label,
                area=c.area,
                buyer=c.buyer,
                contract=c.contract,
                product=product.name if product is not None else "",
                value_cents=c.value_cents,
                start=format_turn(c.start_turn),
                base_end=format_turn(c.base_end_turn),
                end=format_turn(c.end_turn),
                status=c.status,
                options=c.options,
                performance=round(c.performance, 1),
                revenue_cents=c.revenue_cents,
                cost_cents=c.cost_cents,
                month_revenue_cents=c.month.revenue_cents if c.month is not None else None,
                month_cost_cents=c.month.cost_cents if c.month is not None else None,
            )
        )
    clearances = []
    held: dict[int, str] = {}
    for cl in state.clearances:
        if cl.company_id != player.id:
            continue
        person = state.person(cl.person_id)
        if cl.status in ("pending", "cleared"):
            held[cl.person_id] = f"{LEVEL_LABEL[cl.level]} ({cl.status})"
        clearances.append(
            ClearanceOut(
                person_id=cl.person_id,
                name=f"{person.first_name} {person.last_name}",
                level=cl.level,
                status=cl.status,
                requested=format_turn(cl.requested_turn),
                decided=format_turn(cl.decided_turn) if cl.decided_turn is not None else None,
            )
        )
    facilities = {x.id: x for x in state.facilities if x.company_id == player.id}
    fcs = [
        FacilityClearanceOut(
            facility_id=x.facility_id,
            name=facility_name(facilities[x.facility_id], b, d)
            if x.facility_id in facilities
            else f"Facility {x.facility_id}",
            status=x.status,
            requested=format_turn(x.requested_turn),
        )
        for x in state.facility_clearances
        if x.company_id == player.id
    ]
    founder = state.founder_of(player.id)
    staff = []
    for e in state.staff(player.id):
        p = state.person(e.person_id)
        staff.append(
            StaffOptionOut(
                person_id=p.id,
                name=f"{p.first_name} {p.last_name}"
                + (" (founder)" if founder is not None and p.id == founder.id else ""),
                role=e.role,
                clearance=held.get(p.id),
            )
        )
    facility_options = [
        FacilityOptionOut(facility_id=x.id, name=facility_name(x, b, d), kind=x.kind)
        for x in facilities.values()
        if x.status != "closed"
    ]
    rivals: dict[str, RivalAwardOut] = {}
    for t in state.tenders:
        if t.status not in ("awarded", "protested") or not announced(t, turn):
            continue
        for name in t.winners:
            if name == player.name:
                continue
            r = rivals.get(name) or RivalAwardOut(name=name, awards=0, value_cents=0, areas=[])
            areas = r.areas if t.area in r.areas else [*r.areas, t.area]
            rivals[name] = RivalAwardOut(
                name=name,
                awards=r.awards + 1,
                value_cents=r.value_cents + t.value_cents // max(1, t.awards),
                areas=areas,
            )
    record = state.defence_record(player.id)
    controlled = [
        (state.product(c.product_id).name if state.product(c.product_id) else str(c.product_id))  # type: ignore[union-attr]
        for c in state.controlled_products
        if c.company_id == player.id
    ]
    m = scale(b)
    return GovernmentScreenOut(
        month=month,
        enabled=True,
        governments=governments,
        tenders=[_tender_out(state, t, data) for t in shown],
        contracts=contracts,
        clearances=clearances,
        facility_clearances=fcs,
        staff=staff,
        facilities=facility_options,
        rivals=sorted(rivals.values(), key=lambda r: -r.value_cents),
        record=DefenceRecordOut(
            awards=record.awards if record is not None else 0,
            blocs=list(record.blocs) if record is not None else [],
            brand_lost=round(sum(p for _, p in record.brand_lost), 1)
            if record is not None
            else 0.0,
            reactions=len(record.reactions) if record is not None else 0,
            controlled_products=controlled,
            past_performance=round(awards.past_performance(state, player.id, b), 1),
        ),
        clearance_cost_cents={
            k: round(exact(v.cost_cents) * exact(m)) for k, v in f.clearances.items()
        },
        facility_cost_cents=b.government.clearances.facility_cost_cents,
        protest_cost_cents=b.government.protests.cost_cents,
    )
