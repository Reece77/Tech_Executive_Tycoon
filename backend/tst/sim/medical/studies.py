"""Clinical studies (docs/formulas.md 50.3): feasibility, pivotal and post-market.

A study's design (patients, months to readout, cost) is chosen at its start and shown; its cost
is spent evenly each month to the readout (6500 research). At the readout the result is drawn
(stream `medical` (0, study id)) with a chance from the kind's base, the device's quality and
the evidence already in hand, shown only as a range (`medical.study.shown_band`) before. A
success adds the kind's evidence strength; a failure costs a redesign and its months."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import MedicalRuleError
from tst.sim.ledger import CASH, RESEARCH, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.medical import data as md
from tst.sim.medical import draws
from tst.sim.medical.config import StudyKind
from tst.sim.medical.models import Design, Study
from tst.sim.money import times
from tst.sim.products.models import Product
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

QUALITY_MID = 50  # tunable-exempt: quality's midpoint (0-100)


def running(state: GameState, product_id: int) -> Study | None:
    return next(
        (s for s in state.med_studies if s.product_id == product_id and s.status == "running"),
        None,
    )


def patients_range(
    kind: StudyKind, product: Product, state: GameState, data: GameData
) -> tuple[int, int]:
    """Enrolment a study of this kind may choose: the data's range (De Novo's pivotal studies
    are smaller, medical.yaml)."""
    st = md.file(data).studies
    if kind == "pivotal":
        use = md.use_of(state, product, data)
        if use is not None and md.us_class(use, state.turn) != "III":
            return st.de_novo_pivotal_patients
    return st.kinds[kind].patients


def design_study(
    kind: StudyKind, patients: int, product: Product, state: GameState, data: GameData
) -> tuple[int, int]:
    """(months to readout, cost in cents) for a study of `patients`: months rise with enrolment
    across the kind's range."""
    st = md.file(data).studies
    k = st.kinds[kind]
    lo, hi = patients_range(kind, product, state, data)
    share = 0.0 if hi == lo else (patients - lo) / (hi - lo)
    months = round(k.months[0] + share * (k.months[1] - k.months[0]))
    cost = patients * st.cost_per_patient_cents[product.category]
    return months, cost


def chance(
    state: GameState, product: Product, kind: StudyKind, balance: Balance, data: GameData
) -> float:
    sb = balance.medical.study
    design = md.design_of(state, product.id)
    ev = design.evidence if design is not None else 0.0
    base = md.file(data).studies.kinds[kind].success
    p = base + sb.quality_weight * (product.quality - QUALITY_MID) + sb.evidence_weight * ev
    return min(sb.bounds[1], max(sb.bounds[0], p))


def shown_chance(
    state: GameState, product: Product, kind: StudyKind, balance: Balance, data: GameData
) -> tuple[float, float]:
    """The range the screen shows (50.7): never the draw."""
    p = chance(state, product, kind, balance, data)
    band = balance.medical.study.shown_band
    return max(0.0, round(p - band, 2)), min(1.0, round(p + band, 2))


def start(
    state: GameState, product: Product, kind: StudyKind, patients: int | None, data: GameData
) -> tuple[GameState, list[LogItem]]:
    design = md.design_of(state, product.id)
    if not md.is_medical(product, data):
        raise MedicalRuleError("not a medical device")
    if design is None:
        raise MedicalRuleError("choose the device's intended use first")
    if running(state, product.id) is not None:
        raise MedicalRuleError("a study of this device is already running")
    if design.redesign_until > state.turn:
        raise MedicalRuleError("the device is being redesigned after a failed study")
    if product.status == "retired":
        raise MedicalRuleError("the product is retired")
    lo, hi = patients_range(kind, product, state, data)
    n = patients if patients is not None else (lo + hi) // 2
    if not lo <= n <= hi:
        raise MedicalRuleError(f"a {kind.replace('_', '-')} study enrols {lo}-{hi} patients")
    months, cost = design_study(kind, n, product, state, data)
    sid = max((s.id for s in state.med_studies), default=0) + 1
    study = Study(
        id=sid,
        company_id=product.company_id,
        product_id=product.id,
        kind=kind,
        patients=n,
        start_turn=state.turn,
        due_turn=state.turn + months,
        cost_cents=cost,
    )
    state = replace(state, med_studies=(*state.med_studies, study))
    log = inbox_item(
        state.turn,
        product.company_id,
        "medical_study_started",
        link_kind="medical",
        link_id=product.id,
        product=product.name,
        kind=kind.replace("_", "-"),
        patients=n,
        months=months,
        cost_cents=cost,
    )
    return state, [log]


def month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    turn = state.turn
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for s in state.med_studies:
        if s.status != "running":
            continue
        product = state.product(s.product_id)
        months_left = max(1, s.due_turn - turn + 1)
        spend = (
            (s.cost_cents - s.spent_cents) // months_left
            if turn < s.due_turn
            else s.cost_cents - s.spent_cents
        )
        if spend > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=s.company_id,
                    memo=f"Clinical study {s.id}: {product.name if product else s.product_id}",
                    debit=RESEARCH,
                    credit=CASH,
                    amount=spend,
                )
            )
        s2 = replace(s, spent_cents=s.spent_cents + spend)
        if turn >= s.due_turn and product is not None:
            p = chance(state, product, s.kind, balance, data)
            ok = bool(draws.gen(rng, turn, draws.STUDY, s.id).random() < p)
            s2 = replace(s2, status="succeeded" if ok else "failed", read_turn=turn)
            state = _read_out(state, s2, ok, balance, data)
            if not ok:
                redesign = times(s.cost_cents, balance.medical.study.redesign_cost_share)
                if redesign > 0:
                    entries.append(
                        LedgerEntry.transfer(
                            turn=turn,
                            company_id=s.company_id,
                            memo=f"Redesign after study {s.id}: {product.name}",
                            debit=RESEARCH,
                            credit=CASH,
                            amount=redesign,
                        )
                    )
            logs.append(
                inbox_item(
                    turn,
                    s.company_id,
                    "medical_study_met" if ok else "medical_study_missed",
                    link_kind="medical",
                    link_id=product.id,
                    product=product.name,
                    kind=s.kind.replace("_", "-"),
                    patients=s.patients,
                )
            )
        state = replace(
            state, med_studies=tuple(s2 if x.id == s.id else x for x in state.med_studies)
        )
    return state, entries, logs


def _read_out(state: GameState, s: Study, ok: bool, balance: Balance, data: GameData) -> GameState:
    k = md.file(data).studies.kinds[s.kind]

    def change(d: Design) -> Design:
        if d.product_id != s.product_id:
            return d
        if ok:
            return replace(d, evidence=min(1.0, d.evidence + k.evidence))
        return replace(d, redesign_until=state.turn + balance.medical.study.redesign_months)

    return replace(state, med_designs=tuple(change(d) for d in state.med_designs))
