"""Submissions and clearances (docs/formulas.md 50.2).

A filing draws its review's length (the route's window by date, x the regulator's drift after
2025) and whether the regulator will ask for more information (the route's chance, adding its
months) at filing, on stream `medical` (1, submission id, REVIEW); neither is shown, only the
range. At its month the outcome is drawn (DECISION) with the route's approval chance moved by the
product's quality and evidence. A clearance by a regulator starts the registrations of the
regions that rely on it (`medical.yaml` reliance), each drawn (RELIANCE + region index)."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import MedicalRuleError
from tst.sim.facilities.config import month_to_turn
from tst.sim.ledger import CASH, QUALITY_REGULATORY, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.medical import data as md
from tst.sim.medical import draws
from tst.sim.medical.config import RouteDef, UseDef
from tst.sim.medical.models import Clearance, Design, Submission
from tst.sim.products.models import Product
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

OPEN_STATUSES = ("review", "more_info")
QUALITY_MID = 50  # tunable-exempt: quality's midpoint (0-100)


def drift(state: GameState, regulator: str, turn: int) -> float:
    year = md.year_of(turn)
    return next(
        (d.factor for d in state.med_drift if d.regulator == regulator and d.year == year), 1.0
    )


def has_pivotal(state: GameState, product_id: int) -> bool:
    return any(
        s.product_id == product_id and s.kind == "pivotal" and s.status == "succeeded"
        for s in state.med_studies
    )


def pending(state: GameState, product_id: int, regulator: str) -> Submission | None:
    return next(
        (
            s
            for s in state.med_submissions
            if s.product_id == product_id and s.regulator == regulator and s.status in OPEN_STATUSES
        ),
        None,
    )


def why_not(
    state: GameState, product: Product, regulator: str, balance: Balance, data: GameData
) -> str | None:
    """Why the product cannot be filed with the regulator now, or None."""
    sub = md.subcategory(data, product.category)
    design = md.design_of(state, product.id)
    if sub is None:
        return "not a medical device"
    if design is None:
        return "choose the device's intended use first"
    if product.status == "retired":
        return "the product is retired"
    if regulator not in {r.key for r in md.health_regulators(data)}:
        return f"unknown regulator {regulator}"
    if pending(state, product.id, regulator) is not None:
        return "a submission is already under review there"
    use = sub.use(design.use)
    turn = state.turn
    if md.cleared(state, product.id, regulator, turn) and not _needs_update(
        state, product, design, regulator, balance, data
    ):
        return "already cleared there"
    need = data.category(product.category).launch_quality or 0
    if product.quality < need:
        return f"the device must reach quality {need:.0f} before review"
    if md.needs_pivotal(use, regulator, turn, data) and not has_pivotal(state, product.id):
        return "this route needs a successful pivotal study"
    return None


def _needs_update(
    state: GameState,
    product: Product,
    design: Design,
    regulator: str,
    balance: Balance,
    data: GameData,
) -> bool:
    """A SaMD update past its cleared features changes intended use: without a change control
    plan it needs a new US submission (50.2)."""
    sub = md.subcategory(data, product.category)
    if sub is None or not sub.software or regulator != md.FDA or design.pccp:
        return False
    return product.feature_points - design.cleared_features > balance.medical.review.update_features


def update_needed(state: GameState, product: Product, balance: Balance, data: GameData) -> bool:
    design = md.design_of(state, product.id)
    return design is not None and _needs_update(state, product, design, md.FDA, balance, data)


def shown_range(
    state: GameState, use: UseDef, route: RouteDef, pccp: bool, balance: Balance, data: GameData
) -> tuple[int, int]:
    lo, hi = md.shown_range(state, use, route, state.turn, data, pccp)
    extra = balance.medical.review.pccp_months if pccp else 0
    return lo + extra, hi + extra


def submit(
    state: GameState,
    product: Product,
    regulator: str,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if problem := why_not(state, product, regulator, balance, data):
        raise MedicalRuleError(problem)
    design = md.design_of(state, product.id)
    sub = md.subcategory(data, product.category)
    assert design is not None and sub is not None
    use = sub.use(design.use)
    turn = state.turn
    route = md.route_for(state, use, regulator, turn, data)
    pccp = design.pccp and sub.software and turn >= month_to_turn(md.file(data).dates.pccp_from)
    sid = max((s.id for s in state.med_submissions), default=0) + 1
    g = draws.gen(rng, turn, draws.SUBMISSION, sid, draws.REVIEW)
    lo, hi = md.window(state, use, route, turn, data)
    months = int(g.integers(lo, hi, endpoint=True))
    more = bool(g.random() < route.more_info.chance)
    extra = int(g.integers(route.more_info.months[0], route.more_info.months[1], endpoint=True))
    total = months + (extra if more else 0) + (balance.medical.review.pccp_months if pccp else 0)
    total = max(1, round(total * drift(state, regulator, turn)))
    s = Submission(
        id=sid,
        company_id=product.company_id,
        product_id=product.id,
        regulator=regulator,
        route=route.key,
        filed_turn=turn,
        due_turn=turn + total,
        more_info=more,
        info_turn=None,
        pccp=pccp,
    )
    state = replace(state, med_submissions=(*state.med_submissions, s))
    entries = []
    if route.fee_cents:
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=product.company_id,
                memo=f"{route.label} fee: {product.name}",
                debit=QUALITY_REGULATORY,
                credit=CASH,
                amount=route.fee_cents,
            )
        )
    shown = shown_range(state, use, route, pccp, balance, data)
    log = inbox_item(
        turn,
        product.company_id,
        "medical_filed",
        link_kind="medical",
        link_id=product.id,
        product=product.name,
        route=route.label,
        regulator=md.regulator(data, regulator).name,
        months=f"{shown[0]}-{shown[1]}",
    )
    return state, entries, [log]


def _hold(state: GameState, s: Submission) -> bool:
    """An open warning letter from the regulator holds its decisions (50.5)."""
    return any(
        i.company_id == s.company_id
        and i.regulator == s.regulator
        and i.finding == "warning_letter"
        and i.until_turn > state.turn
        for i in state.med_inspections
    )


def approve_chance(state: GameState, s: Submission, route: RouteDef, balance: Balance) -> float:
    rb = balance.medical.review
    product = state.product(s.product_id)
    design = md.design_of(state, s.product_id)
    q = product.quality if product is not None else 0.0
    ev = design.evidence if design is not None else 0.0
    p = route.approve + rb.quality_weight * (q - QUALITY_MID) + rb.evidence_weight * ev
    return min(rb.bounds[1], max(rb.bounds[0], p))


def decisions_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    turn = state.turn
    logs: list[LogItem] = []
    mf = md.file(data)
    for s in state.med_submissions:
        if s.status not in OPEN_STATUSES:
            continue
        product = state.product(s.product_id)
        if product is None or product.status == "retired":
            state = _put(state, replace(s, status="withdrawn", decided_turn=turn))
            continue
        route = mf.route(s.route)
        reg = md.regulator(data, s.regulator)
        info_at = s.filed_turn + max(1, (s.due_turn - s.filed_turn) // 2)
        if s.more_info and s.status == "review" and turn >= info_at:
            s = replace(s, status="more_info", info_turn=turn)
            state = _put(state, s)
            logs.append(
                inbox_item(
                    turn,
                    s.company_id,
                    "medical_more_info",
                    link_kind="medical",
                    link_id=product.id,
                    product=product.name,
                    regulator=reg.name,
                )
            )
        if turn < s.due_turn or _hold(state, s):
            continue
        g = draws.gen(rng, turn, draws.SUBMISSION, s.id, draws.DECISION)
        ok = bool(g.random() < approve_chance(state, s, route, balance))
        s = replace(s, status="cleared" if ok else "refused", decided_turn=turn)
        state = _put(state, s)
        if ok:
            state = _clear(state, s, product, rng, data)
        logs.append(
            inbox_item(
                turn,
                s.company_id,
                "medical_cleared" if ok else "medical_refused",
                link_kind="medical",
                link_id=product.id,
                product=product.name,
                route=route.label,
                regulator=reg.name,
                months=turn - s.filed_turn,
            )
        )
    return state, logs


def _put(state: GameState, s: Submission) -> GameState:
    return replace(
        state, med_submissions=tuple(s if x.id == s.id else x for x in state.med_submissions)
    )


def _clear(
    state: GameState, s: Submission, product: Product, rng: RngFactory, data: GameData
) -> GameState:
    turn = state.turn
    reg = md.regulator(data, s.regulator)
    keep = [
        c
        for c in state.med_clearances
        if not (c.product_id == s.product_id and c.authority == s.regulator)
    ]
    keep.append(Clearance(s.product_id, s.regulator, reg.region, turn, s.route, s.id))
    have = {c.authority for c in keep if c.product_id == s.product_id}
    for rel in md.file(data).reliance:
        auth = md.RELY + rel.region
        if s.regulator not in rel.relies_on or auth in have:
            continue
        g = draws.gen(
            rng, turn, draws.SUBMISSION, s.id, draws.RELIANCE + data.region_index(rel.region)
        )
        months = int(g.integers(rel.months[0], rel.months[1], endpoint=True))
        keep.append(Clearance(s.product_id, auth, rel.region, turn + months, "reliance", s.id))
        have.add(auth)
    state = replace(state, med_clearances=tuple(keep))
    if s.regulator == md.FDA:
        designs = tuple(
            replace(d, cleared_features=product.feature_points) if d.product_id == product.id else d
            for d in state.med_designs
        )
        state = replace(state, med_designs=designs)
    return state
