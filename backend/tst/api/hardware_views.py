"""The Hardware screen and the product BOM and manufacturing panels for the API (M12b,
formulas.md 26.5).

Display only: every number comes from the sim's formulas or last month's production rows.
Indexes are shown up to the month the player is in (M12a's components view); a plant's yield
is shown but never the staff's skill behind it (ADR-0007).
"""

from __future__ import annotations

from tst.api import commodity_views
from tst.api.facility_views import Stored, components_out
from tst.api.schemas.hardware import (
    BomLineOut,
    ChipOut,
    CmOut,
    HardwareOut,
    ManufacturingOut,
    OptionOut,
    PlantOut,
    ProductionContractOut,
    SourceOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.chips import chips
from tst.sim.facilities import formulas as ff
from tst.sim.facilities import goods, lifecycle
from tst.sim.facilities.models import Facility
from tst.sim.geo.models import RegionalSegment
from tst.sim.hardware import cm_market, production
from tst.sim.hardware.models import ProductionContract
from tst.sim.money import exact
from tst.sim.products.models import SELLING, Product, ProductSegment
from tst.sim.state import GameState

HARDWARE_GOODS = ("device_bom", "server_bom", "equipment", "foundry_wafer")


def _plant_cost(f: Facility, data: LoadedData) -> tuple[int, int | None]:
    """(fixed + depreciation a month, last month's cost per good unit)."""
    b = data.balance
    kind = b.facility.kinds[f.kind]
    dep = (
        ff.monthly_depreciation_cents(f.capex_cents, kind.life_months) if f.status == "live" else 0
    )
    fixed = kind.fixed_opex_cents + dep if f.status == "live" else 0
    run = f.run_units + f.sold_units
    good = run * f.yield_rate
    per = round((fixed + kind.variable_cents * run) / good) if good > 0 else None
    return fixed, per


def plant_out(state: GameState, f: Facility, data: LoadedData) -> PlantOut:
    b, d = data.balance, data.game_data
    kind = b.facility.kinds[f.kind]
    turn = state.turn
    building = turn < f.ready_turn
    live = f.live_capacity(turn)
    staffing = lifecycle.staffing(state, f, b)
    fixed, per = _plant_cost(f, data)
    unit = state.unit(f.unit_id) if f.unit_id is not None else None
    used = f.run_units + f.sold_units
    fee = b.hardware.bom[next(iter(b.hardware.bom))].contract_fee_cents
    return PlantOut(
        facility_id=f.id,
        name=lifecycle.facility_name(f, b, d),
        city=f.city,
        city_label=d.city(f.city).label if f.city and d.has_city(f.city) else None,
        status="building" if building else f.status,
        since=format_turn(f.ordered_turn if building else f.ready_turn),
        units=f.capacity,
        live_units=live,
        own_use=f.run_units,
        sold_use=f.sold_units,
        utilization=used / live if live else 0.0,
        plant_yield=None if building else production.plant_yield_of(f, b),
        staff=staffing.staff,
        staff_needed=staffing.needed,
        coverage=staffing.coverage,
        unit_id=f.unit_id,
        unit_name=unit.name if unit else None,
        monthly_cost_cents=fixed,
        cost_per_good_unit_cents=per,
        contract_fee_cents=fee,
        book_value_cents=f.book_value_cents,
        capex_cents=f.capex_cents,
        build_progress=(turn - f.ordered_turn) / kind.build_months if building else None,
        ready=format_turn(f.ready_turn),
        sale_value_cents=round(exact(f.book_value_cents) * exact(b.facility.sale_share)),
    )


def _supplier_label(c: ProductionContract, data: LoadedData) -> str:
    b = data.balance
    if c.kind == "assembly":
        return b.hardware.contract.manufacturers[c.supplier].label
    return b.chips.contract.foundries[c.supplier].label


def contract_out(
    state: GameState, c: ProductionContract, data: LoadedData
) -> ProductionContractOut:
    d = data.game_data
    product = state.product(c.product_id)
    return ProductionContractOut(
        contract_id=c.id,
        kind=c.kind,
        product_id=c.product_id,
        product_name=product.name if product else f"Product {c.product_id}",
        supplier=c.supplier,
        supplier_label=_supplier_label(c, data),
        city_label=d.city(c.city).label if c.city and d.has_city(c.city) else None,
        units=c.units,
        price_cents=round(c.price_cents),
        signed=format_turn(c.signed_turn),
        ends=format_turn(c.end_turn),
        status=c.status,
        delivered=c.delivered,
        used=c.used,
        take_or_pay_cents=c.charged_cents,
    )


def _assembly_cents(state: GameState, product: Product, data: LoadedData) -> tuple[float, str]:
    """A unit's assembly: last month's mix of plants and contracts, else the first running
    contract's fee, else a Shenzhen contract manufacturer's."""
    b = data.balance
    row = state.production_of(product.id)
    contracts = production.assembly_contracts(state, product.id)
    plants = production.live_plants(state, product.company_id, b)
    if row is not None and row.units > 0:
        per_plant = [p for f in plants if (p := _plant_cost(f, data)[1]) is not None]
        plant_unit = sum(per_plant) / len(per_plant) if per_plant else 0.0
        fees = sum(c.used * c.price_cents for c in contracts)
        fixed = plant_unit * row.plant_units
        total = (fees + fixed) / row.units
        detail = f"{row.plant_units:,.0f} from your plants, {row.contract_units:,.0f} on contracts"
        return total, detail
    if contracts:
        c = contracts[0]
        return c.price_cents, f"{_supplier_label(c, data)}'s fee a unit"
    fee = b.hardware.bom[product.category].contract_fee_cents
    return float(fee), "A Shenzhen contract manufacturer's fee a unit"


def manufacturing_out(state: GameState, product: Product, data: LoadedData) -> ManufacturingOut:
    b, d = data.balance, data.game_data
    category = d.category(product.category)
    if not category.sells_units:  # software: nothing to make, an empty panel
        return ManufacturingOut(
            product_id=product.id,
            name=product.name,
            category=product.category,
            category_label=category.label,
            chip_type=None,
            chip_label=None,
            lines=[],
            unit_cost_cents=0,
            price_cents=None,
            gross_margin=None,
            chip_source=None,
            sources=[],
            units_sold=0.0,
            units_lost=0.0,
            internal_units=0.0,
            cogs_cents=0,
            can_launch_source=True,
            sells_units=False,
        )
    row = state.production_of(product.id)
    lines: list[BomLineOut] = []
    chip_source = None
    sources: list[SourceOut] = []
    if category.chip_type is not None:
        chip_type = category.chip_type
        t = b.chips.types[chip_type]
        y = chips.chip_yield(state, product.company_id, b, d)
        wafer = chips.wafer_cents(state, product, b, d)
        lines = [
            BomLineOut(
                line="Wafer",
                detail=f"{format_cents(wafer)} a wafer / ({t.per_wafer} chips x {y:.0%} yield)",
                cents=round(wafer / (t.per_wafer * y)),
            ),
            BomLineOut(line="Packaging and test", detail="A chip", cents=b.chips.packaging_cents),
        ]
        for c in chips.wafer_contracts(state, product.id):
            sources.append(
                SourceOut(
                    source="contract",
                    label=f"{_supplier_label(c, data)}: {c.units:,} wafers a month",
                    units=c.used * t.per_wafer * y,
                    available=c.delivered * t.per_wafer * y,
                )
            )
        has_source = bool(chips.wafer_contracts(state, product.id))
        per_chip = t.wafer_cents / (t.per_wafer * y)
        commodity_lines = commodity_views.cost_lines(
            state, product.company_id, b.chips.good, per_chip, data
        )
    else:
        bom = b.hardware.bom[product.category]
        chip_type = bom.chip_type
        index = goods.index_now(state, bom.good, d)
        good_label = d.components.good(bom.good).label.lower() if d.components else bom.good
        commodity_lines = commodity_views.cost_lines(
            state, product.company_id, bom.good, bom.base_cents, data
        )
        with_mix = " with its commodities at spot" if commodity_lines else ""
        lines.append(
            BomLineOut(
                line="Bill of materials",
                detail=(
                    f"{format_cents(bom.base_cents)} x the {good_label} index {index:.2f}{with_mix}"
                ),
                cents=round(production.unit_bom_cents(state, product, b, d)),
            )
        )
        own = chips.own_chip_product(state, product.company_id, chip_type, d)
        if own is not None:
            chip_cents = chips.unit_cost_cents(state, own, b, d)
            chip_source = f"Your own {own.name}, at cost"
        else:
            chip_cents = float(chips.bought_price_cents(d, b, chip_type))
            chip_source = "Bought at the market price"
        lines.append(BomLineOut(line="Chip", detail=chip_source, cents=round(chip_cents)))
        assembly, detail = _assembly_cents(state, product, data)
        lines.append(BomLineOut(line="Assembly", detail=detail, cents=round(assembly)))
        for f in production.live_plants(state, product.company_id, b):
            sources.append(
                SourceOut(
                    source="plant",
                    label=lifecycle.facility_name(f, b, d),
                    units=row.plant_units if row else 0.0,
                    available=production.runnable(state, f, b) * production.plant_yield_of(f, b),
                )
            )
        for c in production.assembly_contracts(state, product.id):
            sources.append(
                SourceOut(
                    source="contract",
                    label=f"{_supplier_label(c, data)}: {c.units:,} a month",
                    units=c.used,
                    available=c.delivered or float(c.units),
                )
            )
        has_source = production.has_source(state, product, b, d)
    unit_cost = sum(line.cents for line in lines)
    segs = state.segments_of(product.id)
    price = next((s.price_cents for s in segs if s.price_cents is not None), None)
    margin = (price - unit_cost) / price if price else None
    return ManufacturingOut(
        product_id=product.id,
        name=product.name,
        category=product.category,
        category_label=category.label,
        chip_type=chip_type,
        chip_label=b.chips.types[chip_type].label,
        lines=lines,
        unit_cost_cents=unit_cost,
        price_cents=price,
        gross_margin=margin,
        chip_source=chip_source,
        sources=sources,
        units_sold=row.units if row else 0.0,
        units_lost=row.lost_units if row else 0.0,
        internal_units=row.internal_units if row else 0.0,
        cogs_cents=row.cogs_cents if row else 0,
        can_launch_source=has_source,
        commodity_lines=commodity_lines,
    )


def format_cents(cents: float) -> str:
    return f"${cents / 100:,.2f}"


def chip_out(state: GameState, product: Product, data: LoadedData) -> ChipOut:
    b, d = data.balance, data.game_data
    chip_type = d.category(product.category).chip_type
    assert chip_type is not None
    t = b.chips.types[chip_type]
    row = state.production_of(product.id)
    factor = None
    if chip_type == b.chips.gpu_capex.chip_type and product.status == "live":
        factor = chips.gpu_capex_factor(state, product.company_id, b, d)
    return ChipOut(
        product_id=product.id,
        name=product.name,
        chip_type=chip_type,
        chip_label=t.label,
        status=product.status,
        chip_yield=chips.chip_yield(state, product.company_id, b, d),
        unit_cost_cents=round(chips.unit_cost_cents(state, product, b, d)),
        market_price_cents=chips.bought_price_cents(d, b, chip_type),
        per_wafer=t.per_wafer,
        wafers=sum(c.units for c in chips.wafer_contracts(state, product.id)),
        made=(row.units + row.internal_units) if row else 0.0,
        internal_units=row.internal_units if row else 0.0,
        market_units=row.units if row else 0.0,
        gpu_capex_factor=factor,
    )


def cm_out(state: GameState, data: LoadedData) -> CmOut:
    b, d = data.balance, data.game_data
    company = state.player.id
    product = cm_market.cm_product(state, company, b)
    plants = [f for f in state.company_facilities(company) if f.kind == b.hardware.plant_kind]
    spare = sum(production.spare_units(state, company, None, b).values())
    spare -= sum(f.run_units for f in production.live_plants(state, company, b))
    if product is None:
        return CmOut(
            started=False,
            can_start=bool(plants),
            product_id=None,
            customers=0.0,
            units_sold=0.0,
            spare_units=max(0.0, spare),
            revenue_cents=0,
            quality=None,
        )
    upc = {m.segment: m.units_per_customer for m in d.category(product.category).markets}
    rows: list[ProductSegment | RegionalSegment] = [
        *state.segments_of(product.id),
        *state.regional_segments_of(product.id),
    ]
    return CmOut(
        started=True,
        can_start=False,
        product_id=product.id,
        customers=sum(r.customers for r in rows),
        units_sold=sum(r.customers * upc[r.segment] for r in rows),
        spare_units=max(0.0, spare),
        revenue_cents=round(sum(r.customers * (r.price_cents or 0) for r in rows)),
        quality=cm_market.plant_quality(state, company, b),
    )


def hardware_out(state: GameState, data: LoadedData, stored: Stored) -> HardwareOut:
    b, d = data.balance, data.game_data
    company = state.player.id
    unit_products = [
        p
        for p in state.company_products(company)
        if p.status != "retired" and d.category(p.category).sells_units
    ]
    plants = [
        f
        for f in sorted(state.company_facilities(company), key=lambda f: f.id)
        if f.kind == b.hardware.plant_kind
    ]
    kind = b.facility.kinds[b.hardware.plant_kind]
    contracts = [c for c in state.production_contracts if c.company_id == company]
    return HardwareOut(
        turn_label=format_turn(state.turn),
        products=[manufacturing_out(state, p, data) for p in unit_products],
        plants=[plant_out(state, f, data) for f in plants],
        contracts=[contract_out(state, c, data) for c in contracts],
        chips=[chip_out(state, p, data) for p in unit_products if d.category(p.category).chip_type],
        cm=cm_out(state, data),
        components=[c for c in components_out(state, data, stored) if c.good in HARDWARE_GOODS],
        manufacturers=[
            OptionOut(key=k, label=m.label) for k, m in b.hardware.contract.manufacturers.items()
        ],
        foundries=[OptionOut(key=k, label=f.label) for k, f in b.chips.contract.foundries.items()],
        cities=[OptionOut(key=c.key, label=c.label) for c in d.cities],
        cheap_city=b.hardware.contract.cheap_city,
        plant_sizes=list(kind.sizes or b.facility.sizes),
        contract_months=[int(b.hardware.contract.months.lo), int(b.hardware.contract.months.hi)],
        wafer_months=[int(b.chips.contract.months.lo), int(b.chips.contract.months.hi)],
        contract_take_or_pay=b.hardware.contract.take_or_pay,
        wafer_take_or_pay=b.chips.contract.take_or_pay,
        contract_energy=b.hardware.contract.energy,
        wafer_energy=b.chips.contract.energy,
        build_energy=b.facility.build_energy,
        plant_capex_per_unit_cents=ff.capex_cents(
            1, kind.capex_per_unit_cents, goods.index_now(state, kind.input_good, d)
        ),
        plant_build_months=kind.build_months,
        plant_staff_per=round(kind.staff_per),
    )


def selling(product: Product) -> bool:
    return product.status in SELLING
