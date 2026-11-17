"""Manufacturing quality, inspections, recalls and surveillance (docs/formulas.md 50.5).

- **Quality systems** are a plant setting (low, standard, high; medical.yaml): a monthly cost
  for each assembly plant of a company that makes medical devices (6985), a defect multiplier on
  recalls and a multiplier on inspection findings. A device made under contract runs the data's
  contract level; software runs standard.
- **Inspections:** each month a health regulator may inspect a company with devices cleared
  there (its yearly chance / 12 x its strictness, M34's helper), and the finding is drawn
  (stream `medical` (2, company id, regulator index)): observations, a warning letter (holds that
  regulator's decisions, costs brand), an import ban or a consent decree (stop sales in its part;
  a decree also pays `consent_fine_share` of a year's medical revenue, 6970 fines).
- **Recalls:** each month a marketed device may have a defect signal (its yearly chance / 12 x
  the quality level's defect x installed units' weight), drawn with its class and whether
  surveillance caught it early (one class lower) on (3, product id). A recall costs the field
  action (installed units x price x the class's share, 6980), lawsuits for class I, brand, and
  stops new sales for the class's months; a class I recall is a critical event and may bring a
  for-cause inspection.
- **Surveillance** is a product's monthly cost (6985) while it sells."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import QueuedEvent
from tst.sim.geo.models import RegionalSegment
from tst.sim.ledger import CASH, FINES, QUALITY_REGULATORY, RECALLS, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.medical import data as md
from tst.sim.medical import draws
from tst.sim.medical.config import FINDINGS, RECALL_CLASSES, Finding, QualityLevel, RecallClass
from tst.sim.medical.models import Inspection, PlantQuality, Recall
from tst.sim.money import times
from tst.sim.products.models import Product, ProductSegment
from tst.sim.regulation import data as rdata
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_product, with_queued

CLASS_I_RECALL: Final = "medical_class_i_recall"  # tunable-exempt: event template id
MONTHS: Final = 12  # tunable-exempt: calendar
SELLING: Final = ("live", "sunset")
STOPS: Final = ("import_ban", "consent_decree")


def plant_level(state: GameState, facility_id: int) -> QualityLevel:
    return next((q.level for q in state.plant_quality if q.facility_id == facility_id), "standard")


def plants(state: GameState, company_id: int, balance: Balance) -> list[int]:
    kind = balance.hardware.plant_kind
    return [
        f.id
        for f in state.company_facilities(company_id)
        if f.kind == kind and f.status != "closed"
    ]


def product_level(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> QualityLevel:
    """The quality level a device is made at: its company's worst plant's, else the contract
    manufacturer's (medical.yaml); software: standard."""
    sub = md.subcategory(data, product.category)
    if sub is not None and sub.software:
        return "standard"
    own = plants(state, product.company_id, balance)
    if not own:
        return md.file(data).quality.contract_level
    order = ("low", "standard", "high")
    return min((plant_level(state, f) for f in own), key=order.index)


def installed(state: GameState, product: Product, data: GameData) -> float:
    """Installed units: customers x units per customer, home and abroad."""
    cat = data.category(product.category)
    total = 0.0
    for seg in state.segments_of(product.id):
        total += seg.customers * cat.market(seg.segment).units_per_customer
    for rseg in state.regional_segments_of(product.id):
        total += rseg.customers * cat.market(rseg.segment).units_per_customer
    return total


def unit_price(state: GameState, product: Product, data: GameData) -> int:
    cat = data.category(product.category)
    prices = [s.price_cents for s in state.segments_of(product.id) if s.price_cents is not None]
    if prices:
        return max(prices)
    return max(m.reference_price_cents for m in cat.markets)


def yearly_revenue(state: GameState, product: Product, data: GameData) -> int:
    """A device's revenue a year at its installed base (for a consent decree's payment)."""
    cat = data.category(product.category)
    sub = md.subcategory(data, product.category)
    total = 0.0
    rows: list[ProductSegment | RegionalSegment] = [
        *state.segments_of(product.id),
        *state.regional_segments_of(product.id),
    ]
    for seg in rows:
        m = cat.market(seg.segment)
        price = seg.price_cents or m.reference_price_cents
        upc = m.units_per_customer
        if cat.sells_units:
            reps = m.replacement_months or MONTHS
            total += seg.customers * upc * price * MONTHS / reps  # money-exact: estimate
        else:
            total += seg.customers * price * MONTHS  # money-exact: estimate
        if sub is not None:
            total += seg.customers * upc * sub.consumables_cents * MONTHS  # money-exact: estimate
    return round(total)


def stopped_parts(state: GameState, company_id: int) -> set[str]:
    """Regulators whose import ban or consent decree stops the company's sales now."""
    return {
        i.regulator
        for i in state.med_inspections
        if i.company_id == company_id and i.finding in STOPS and i.until_turn > state.turn
    }


def blocked(state: GameState, product_id: int) -> bool:
    return any(r.product_id == product_id and r.block_until > state.turn for r in state.med_recalls)


# --- costs ----------------------------------------------------------------------------------


def cost_entries(state: GameState, balance: Balance, data: GameData) -> list[LedgerEntry]:
    entries: list[LedgerEntry] = []
    mf = md.file(data)
    for company_id in sorted(md.medical_companies(state)):
        for fid in plants(state, company_id, balance):
            level = plant_level(state, fid)
            cents = mf.quality.levels[level].cents_month
            if cents:
                entries.append(
                    LedgerEntry.transfer(
                        turn=state.turn,
                        company_id=company_id,
                        memo=f"Quality system ({mf.quality.levels[level].label}): plant {fid}",
                        debit=QUALITY_REGULATORY,
                        credit=CASH,
                        amount=cents,
                    )
                )
    cents = balance.medical.recall.surveillance_cents
    for d in state.med_designs:
        product = state.product(d.product_id)
        if d.surveillance and cents and product is not None and product.status in SELLING:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=product.company_id,
                    memo=f"Post-market surveillance: {product.name}",
                    debit=QUALITY_REGULATORY,
                    credit=CASH,
                    amount=cents,
                )
            )
    return entries


def set_level(state: GameState, facility_id: int, level: QualityLevel) -> GameState:
    rest = tuple(q for q in state.plant_quality if q.facility_id != facility_id)
    return replace(state, plant_quality=(*rest, PlantQuality(facility_id, level)))


# --- inspections ----------------------------------------------------------------------------


def _finding(u: float, mult: float, data: GameData) -> Finding:
    out = md.file(data).inspections.outcomes
    edge = 0.0
    for f in reversed(FINDINGS):  # the gravest first
        edge += out[f] * mult
        if u < edge:
            return f
    return "none"


def inspect(
    state: GameState,
    company_id: int,
    regulator: str,
    u: float,
    balance: Balance,
    data: GameData,
    for_cause: bool = False,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """One inspection with its finding drawn from `u` (50.5)."""
    ib = balance.medical.inspection
    products = [
        p
        for p in state.company_products(company_id)
        if md.is_medical(p, data) and md.cleared(state, p.id, regulator, state.turn)
    ]
    if not products:
        return state, [], []
    order = ("low", "standard", "high")
    level = min((product_level(state, p, balance, data) for p in products), key=order.index)
    cause = balance.medical.inspection.for_cause_mult if for_cause else 1.0
    mult = md.file(data).quality.levels[level].inspection * cause
    finding = _finding(u, mult, data)
    turn = state.turn
    until = turn
    fine = 0
    if finding == "warning_letter":
        until = turn + balance.medical.review.warning_hold_months
        for p in products:
            state = with_product(state, replace(p, brand=max(0.0, p.brand - ib.warning_brand_hit)))
    elif finding == "import_ban":
        until = turn + ib.import_ban_months
    elif finding == "consent_decree":
        until = turn + ib.consent_decree_months
        fine = times(sum(yearly_revenue(state, p, data) for p in products), ib.consent_fine_share)
    iid = max((i.id for i in state.med_inspections), default=0) + 1
    rec = Inspection(iid, company_id, regulator, turn, finding, until, fine, for_cause)
    state = replace(state, med_inspections=(*state.med_inspections, rec))
    entries = []
    if fine > 0:
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=company_id,
                memo=f"Consent decree: {md.regulator(data, regulator).name}",
                debit=FINES,
                credit=CASH,
                amount=fine,
            )
        )
    log = inbox_item(
        turn,
        company_id,
        f"medical_inspection_{finding}",
        link_kind="medical",
        regulator=md.regulator(data, regulator).name,
        months=max(0, until - turn),
        fine_cents=fine,
    )
    return state, entries, [log]


def inspections_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    chance = md.file(data).inspections.chance_year / MONTHS
    for company_id in sorted(md.medical_companies(state)):
        for i, reg in enumerate(md.health_regulators(data)):
            if not any(
                c.authority == reg.key and c.from_turn <= state.turn
                for c in state.med_clearances
                if (p := state.product(c.product_id)) is not None and p.company_id == company_id
            ):
                continue
            g = draws.gen(rng, state.turn, draws.INSPECTION, company_id, i)
            if g.random() >= chance * rdata.strictness(reg, state.turn):
                continue
            state, e, lg = inspect(state, company_id, reg.key, float(g.random()), balance, data)
            entries += e
            logs += lg
    return state, entries, logs


# --- recalls --------------------------------------------------------------------------------


def recall_chance(state: GameState, product: Product, balance: Balance, data: GameData) -> float:
    mf = md.file(data)
    level = product_level(state, product, balance, data)
    units = installed(state, product, data)
    weight = 1 + balance.medical.recall.install_weight * dmath.log10(1 + units)
    return mf.recalls.chance_year / MONTHS * mf.quality.levels[level].defect * weight


def _klass(u: float, data: GameData) -> RecallClass:
    edge = 0.0
    classes = md.file(data).recalls.classes
    for k in RECALL_CLASSES:
        edge += classes[k]
        if u < edge:
            return k
    return "II"


def recall(
    state: GameState,
    product: Product,
    klass: RecallClass,
    early: bool,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], list[LogItem], Recall]:
    rb = balance.medical.recall
    mf = md.file(data)
    if early and klass != "III":
        klass = "II" if klass == "I" else "III"
    units = round(installed(state, product, data))
    field = times(unit_price(state, product, data), units, mf.recalls.cost_share[klass])
    cost = field + (times(field, rb.lawsuit_share) if klass == "I" else 0)
    turn = state.turn
    rid = max((r.id for r in state.med_recalls), default=0) + 1
    rec = Recall(
        rid,
        product.company_id,
        product.id,
        turn,
        klass,
        units,
        cost,
        early,
        turn + rb.block_months[klass],
    )
    state = replace(state, med_recalls=(*state.med_recalls, rec))
    state = with_product(
        state, replace(product, brand=max(0.0, product.brand - rb.brand_hit[klass]))
    )
    if klass == "I":
        hit = balance.medical.adoption.recall_hit
        state = replace(
            state,
            med_adoption=tuple(
                replace(a, share=a.share * (1 - hit)) if a.product_id == product.id else a
                for a in state.med_adoption
            ),
        )
    entries = []
    if cost > 0:
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=product.company_id,
                memo=f"Class {klass} recall: {product.name}",
                debit=RECALLS,
                credit=CASH,
                amount=cost,
            )
        )
    logs = [
        inbox_item(
            turn,
            product.company_id,
            "medical_recall",
            link_kind="medical",
            link_id=product.id,
            product=product.name,
            klass=klass,
            units=units,
            cost_cents=cost,
            early="caught early by surveillance" if early else "reported by users",
        )
    ]
    return state, entries, logs, rec


def recalls_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for d in sorted(state.med_designs, key=lambda x: x.product_id):
        product = state.product(d.product_id)
        if product is None or product.status not in SELLING or installed(state, product, data) < 1:
            continue
        g = draws.gen(rng, state.turn, draws.PRODUCT, product.id)
        if g.random() >= recall_chance(state, product, balance, data):
            continue
        klass = _klass(float(g.random()), data)
        early = d.surveillance and bool(g.random() < balance.medical.recall.caught_early)
        state, e, lg, rec = recall(state, product, klass, early, balance, data)
        entries += e
        logs += lg
        if rec.klass == "I":
            state = queue_class_i(state, product)
            if g.random() < balance.medical.recall.inspect_after_class_i and md.cleared(
                state, product.id, md.FDA, state.turn
            ):
                state, e, lg = inspect(
                    state, product.company_id, md.FDA, float(g.random()), balance, data, True
                )
                entries += e
                logs += lg
    return state, entries, logs


def queue_class_i(state: GameState, product: Product) -> GameState:
    if product.company_id != state.player.id:
        return state
    qid, ids = state.next_ids.take("queued")
    return with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid,
            company_id=product.company_id,
            template_id=CLASS_I_RECALL,
            due_turn=state.turn + 1,
            source_event_id=None,
            product_id=product.id,
        ),
    )
