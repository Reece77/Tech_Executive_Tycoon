"""Reimbursement and clinicians' adoption (docs/formulas.md 50.4).

Coverage: once a device is cleared in a region it may ask that region's payers for coverage.
The decision's month is drawn at the request (stream `medical` (3, product id, region index))
inside medical.yaml's range read by evidence (full evidence takes the low end; never shown), and
its outcome at that month with a chance from no evidence to full evidence. TCET: from its date, a
US device with a successful pivotal study on a novel route is decided in `tcet_months`.

Adoption: a clinician-led device's adoption in a region starts at `medical.adoption.seed` when it
is first cleared there and grows on a logistic curve, faster with evidence and with the
product's clinical education (6400 marketing a month a region)."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import MedicalRuleError
from tst.sim.facilities.config import month_to_turn
from tst.sim.ledger import CASH, MARKETING, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.medical import data as md
from tst.sim.medical import draws
from tst.sim.medical.models import Adoption, Coverage
from tst.sim.products.models import Product
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

NOVEL_ROUTES = ("de_novo", "pma")  # tunable-exempt: route keys TCET reads (medical.yaml)


def coverage_of(state: GameState, product_id: int, region: str) -> Coverage | None:
    return next(
        (c for c in state.med_coverage if c.product_id == product_id and c.region == region), None
    )


def covered(state: GameState, product_id: int, region: str) -> bool:
    c = coverage_of(state, product_id, region)
    return c is not None and c.status == "covered"


def adoption(state: GameState, product_id: int, region: str) -> float:
    return next(
        (a.share for a in state.med_adoption if a.product_id == product_id and a.region == region),
        0.0,
    )


def cleared_in(state: GameState, product_id: int, region: str, data: GameData) -> bool:
    return any(
        c.product_id == product_id and c.region == region and c.from_turn <= state.turn
        for c in state.med_clearances
    )


def window(state: GameState, product: Product, region: str, data: GameData) -> tuple[int, int]:
    """The months a coverage decision may take, as shown: the data's range narrowed by
    evidence (full evidence: the low end to a fifth of the way up)."""
    cov = md.file(data).coverage_in(region)
    design = md.design_of(state, product.id)
    ev = design.evidence if design is not None else 0.0
    if _tcet(state, product, region, data) and cov.tcet_months is not None:
        return cov.tcet_months, cov.tcet_months
    lo, hi = cov.months
    top = round(lo + (hi - lo) * (1 - 0.8 * ev))  # tunable-exempt: full evidence keeps a fifth
    return lo, max(lo, top)


def _tcet(state: GameState, product: Product, region: str, data: GameData) -> bool:
    mf = md.file(data)
    if region != md.regulator(data, md.FDA).region or state.turn < month_to_turn(
        mf.dates.tcet_from
    ):
        return False
    novel = any(
        s.product_id == product.id
        and s.regulator == md.FDA
        and s.status == "cleared"
        and s.route in NOVEL_ROUTES
        for s in state.med_submissions
    )
    pivotal = any(
        s.product_id == product.id and s.kind == "pivotal" and s.status == "succeeded"
        for s in state.med_studies
    )
    return novel and pivotal


def request(
    state: GameState, product: Product, region: str, rng: RngFactory, data: GameData
) -> tuple[GameState, list[LogItem]]:
    sub = md.subcategory(data, product.category)
    if sub is None:
        raise MedicalRuleError("not a medical device")
    if not sub.needs_coverage:
        raise MedicalRuleError(f"{sub.label} is paid for by its buyers, not by payers")
    if region not in data.region_keys:
        raise MedicalRuleError(f"unknown region {region}")
    if not cleared_in(state, product.id, region, data):
        raise MedicalRuleError("the device must be cleared in the region first")
    old = coverage_of(state, product.id, region)
    if old is not None and old.status in ("pending", "covered"):
        raise MedicalRuleError("coverage is already " + old.status)
    lo, hi = window(state, product, region, data)
    g = draws.gen(rng, state.turn, draws.PRODUCT, product.id, data.region_index(region))
    months = int(g.integers(lo, hi, endpoint=True))
    c = Coverage(product.id, region, state.turn, "pending", state.turn + months)
    rest = tuple(
        x for x in state.med_coverage if not (x.product_id == product.id and x.region == region)
    )
    state = replace(state, med_coverage=(*rest, c))
    cov = md.file(data).coverage_in(region)
    log = inbox_item(
        state.turn,
        product.company_id,
        "medical_coverage_asked",
        link_kind="medical",
        link_id=product.id,
        product=product.name,
        payer=cov.label,
        months=f"{lo}-{hi}",
    )
    return state, [log]


def approve_chance(state: GameState, product_id: int, region: str, data: GameData) -> float:
    lo, hi = md.file(data).coverage_in(region).approve
    design = md.design_of(state, product_id)
    ev = design.evidence if design is not None else 0.0
    return lo + (hi - lo) * ev


def month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    turn = state.turn
    logs: list[LogItem] = []
    entries: list[LedgerEntry] = []
    out: list[Coverage] = []
    for c in state.med_coverage:
        product = state.product(c.product_id)
        if c.status == "pending" and turn >= c.due_turn and product is not None:
            g = draws.gen(rng, turn, draws.PRODUCT, c.product_id, data.region_index(c.region))
            ok = bool(g.random() < approve_chance(state, c.product_id, c.region, data))
            c = replace(c, status="covered" if ok else "denied", decided_turn=turn)
            logs.append(
                inbox_item(
                    turn,
                    product.company_id,
                    "medical_covered" if ok else "medical_coverage_denied",
                    link_kind="medical",
                    link_id=product.id,
                    product=product.name,
                    payer=md.file(data).coverage_in(c.region).label,
                )
            )
        out.append(c)
    state = replace(state, med_coverage=tuple(out))
    # adoption (50.4)
    ab = balance.medical.adoption
    have = {(a.product_id, a.region): a for a in state.med_adoption}
    rows: list[Adoption] = []
    for d in state.med_designs:
        product = state.product(d.product_id)
        sub = md.subcategory(data, product.category) if product is not None else None
        if product is None or sub is None or not sub.clinicians or product.status == "retired":
            continue
        for region in data.region_keys:
            a = have.get((d.product_id, region))
            if a is None:
                if cleared_in(state, d.product_id, region, data):
                    rows.append(Adoption(d.product_id, region, ab.seed))
                continue
            training = min(1.0, d.training_cents / ab.training_full_cents)  # money-exact: ratio
            r = (
                ab.rate
                * (1 + ab.evidence_weight * d.evidence)
                * (1 + ab.training_weight * training)
            )
            share = min(1.0, a.share + r * a.share * (1 - a.share))
            rows.append(replace(a, share=share))
            if d.training_cents > 0 and product.status in ("live", "sunset"):
                entries.append(
                    LedgerEntry.transfer(
                        turn=turn,
                        company_id=product.company_id,
                        memo=f"Clinical education: {product.name} ({region.replace('_', ' ')})",
                        debit=MARKETING,
                        credit=CASH,
                        amount=d.training_cents,
                    )
                )
    state = replace(state, med_adoption=tuple(rows))
    return state, entries, logs
