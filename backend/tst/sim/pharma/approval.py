"""Approval, regulators and exclusivity (docs/formulas.md 55.3), and coverage by HTA (55.4).

A programme that has read out Phase III (or Phase II under accelerated approval, in the US for
oncology and rare disease at a strong estimate) is filed with a drug regulator. At filing the
review's months are drawn from the regulator's standard or priority range (priority when the
efficacy estimate is `approval.priority_margin` above the standard of care, or the indication is
orphan, or with breakthrough designation), and whether an advisory committee meets (the FDA's
`adcom_share`). The committee meets half way and votes (a negative vote's chance falls with the
estimate); at the due month the decision is drawn:

    p = sigmoid(logit(T_area,submission) + w x (estimate - soc) / sd - adcom_weight if negative)

x `resubmit_factor` for a resubmission. Approved: the drug is authorised in the regulator's part
of its region and the other regions register it by reliance within drawn months (M41's rule);
where prices go through health-technology assessment, an HTA decides in drawn months whether
the list price is within the value cap (coverage reuses 50.4: without it, sales reach only
`medical.coverage.no_coverage_share`). Refused: a complete response letter; the company may file
again.

Exclusivity dates are pharma.data.loe_turn (patents, Hatch-Waxman, data, orphan, the EU's 8+2+1)."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.ledger import CASH, RESEARCH, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.pharma import data as pd
from tst.sim.pharma import draws
from tst.sim.pharma import pipeline as pl
from tst.sim.pharma.models import Authorisation, Drug, Hta, Programme, Review
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

HALF: Final = 2  # tunable-exempt: the committee meets half way through the review


def can_file(p: Programme, data: GameData, balance: Balance, regulator: str) -> str | None:
    """Why the programme cannot be filed with the regulator now, or None."""
    if p.status not in ("ready", "marketed"):
        return "only a programme that has read out its trials can be filed"
    if p.stage == "phase3" or p.stage in ("submission", "approved"):
        return None
    if (
        p.stage == "phase2"
        and regulator == pd.us_regulator(data).key
        and accelerated_ok(p, data, balance)
    ):
        return None
    return "file after Phase III (or Phase II under accelerated approval)"


def accelerated_ok(p: Programme, data: GameData, balance: Balance) -> bool:
    ab = balance.pharma.approval
    if p.area not in ab.accelerated_areas or p.obs_n == 0:
        return False
    rev = pd.review_def(data, pd.us_regulator(data).key)
    if rev.accelerated_from is None:
        return False
    return p.obs_eff - pd.indication(data, p.indication).soc >= ab.accelerated_margin


def _priority(p: Programme, turn: int, data: GameData, balance: Balance, regulator: str) -> bool:
    rev = pd.review_def(data, regulator)
    if rev.priority_months is None or (
        rev.priority_from is not None and turn < month_to_turn(rev.priority_from)
    ):
        return False
    ind = pd.indication(data, p.indication)
    margin = p.obs_eff - ind.soc >= balance.pharma.approval.priority_margin
    return margin or ind.orphan or p.breakthrough


def file(
    state: GameState,
    p: Programme,
    regulator: str,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LogItem]]:
    """A marketing application (NDA/BLA, MAA, ...) with a drug regulator (55.3)."""
    from tst.sim.errors import PharmaRuleError

    if regulator not in {r.key for r in pd.regulators(data)}:
        raise PharmaRuleError(f"no drug regulator {regulator!r}")
    if (why := can_file(p, data, balance, regulator)) is not None:
        raise PharmaRuleError(why)
    if any(
        r.programme_id == p.id and r.regulator == regulator and r.status in ("review", "approved")
        for r in state.pharma_reviews
    ):
        raise PharmaRuleError("already filed with that regulator")
    turn = state.turn
    rev = pd.review_def(data, regulator)
    rid = max((r.id for r in state.pharma_reviews), default=0) + 1
    before = sum(
        1 for r in state.pharma_reviews if r.programme_id == p.id and r.regulator == regulator
    )
    g = draws.gen(rng, turn, draws.REVIEW, rid, draws.LENGTH)
    priority = _priority(p, turn, data, balance, regulator)
    if before:
        lo, hi = pd.file(data).approval.crl_resubmit_months
    else:
        lo, hi = rev.priority_months if priority and rev.priority_months else rev.standard_months
    months = round(lo + (hi - lo) * float(g.random()))
    adcom = before == 0 and float(g.random()) < rev.adcom_share
    review = Review(
        id=rid,
        programme_id=p.id,
        regulator=regulator,
        application=rev.application,
        filed_turn=turn,
        due_turn=turn + max(1, months),
        priority=priority,
        adcom=adcom,
        adcom_turn=turn + max(1, months // HALF) if adcom else None,
        resubmission=before,
    )
    state = replace(state, pharma_reviews=(*state.pharma_reviews, review))
    p2 = p
    if p.stage in ("phase2", "phase3"):
        accelerated = p.stage == "phase2"
        p2 = replace(p2, stage="submission", status="ready", accelerated=accelerated)
    if regulator == pd.us_regulator(data).key and p2.filed_turn is None:
        p2 = replace(p2, filed_turn=turn)
    state = pl.with_programme(state, p2)
    log = inbox_item(
        turn,
        p.company_id,
        "pharma_filed",
        link_kind="pharma",
        link_id=p.id,
        name=p.name,
        regulator=pd.regulator(data, regulator).name,
        application=rev.application,
    )
    return state, [log]


def review_range(data: GameData, regulator: str, priority: bool) -> tuple[float, float]:
    """The months shown for a review (never its drawn due month, 55.7)."""
    rev = pd.review_def(data, regulator)
    if priority and rev.priority_months is not None:
        return rev.priority_months
    return rev.standard_months


def approve_chance(p: Programme, review: Review, balance: Balance, data: GameData) -> float:
    """The decision's chance from the public estimate (the regulator sees the data)."""
    ab = balance.pharma.approval
    ind = pd.indication(data, p.indication)
    x = pl.logit(pd.area(data, p.area).transitions.submission)
    x += ab.efficacy_weight * (p.obs_eff - ind.soc) / balance.pharma.efficacy.sd
    if review.adcom_positive is False:
        x -= ab.adcom_weight
    c = pl.sigmoid(x)
    if review.resubmission:
        c *= ab.resubmit_factor
    lo, hi = balance.pharma.readout.bounds
    return min(hi, max(lo, c))


def _authorise(
    state: GameState,
    p: Programme,
    regulator: str,
    rng: RngFactory,
    review_id: int,
    balance: Balance,
    data: GameData,
) -> GameState:
    turn = state.turn
    reg = pd.regulator(data, regulator)
    rows = [Authorisation(p.id, regulator, reg.region, turn)]
    if regulator in (pd.us_regulator(data).key, pd.eu_regulator(data).key):
        lo, hi = pd.file(data).approval.reliance_months
        for i, region in enumerate(data.region_keys):
            if pd.reliance_share(data, region) <= 0:
                continue
            if any(
                a.programme_id == p.id and a.authority == pd.RELY + region
                for a in state.pharma_authorisations
            ):
                continue
            g = draws.gen(rng, turn, draws.REVIEW, review_id, draws.RELIANCE + i)
            months = round(lo + (hi - lo) * float(g.random()))
            rows.append(Authorisation(p.id, pd.RELY + region, region, turn + months))
    state = replace(state, pharma_authorisations=(*state.pharma_authorisations, *rows))
    state = _request_hta(state, p, rows, rng, data)
    if p.status != "marketed":
        ind = pd.indication(data, p.indication)
        drug = Drug(p.id, round(ind.price_year * pd.CENTS), 1.0, turn)
        state = replace(state, pharma_drugs=(*state.pharma_drugs, drug))
        p = replace(
            p,
            stage="approved",
            status="marketed",
            approved_turn=p.approved_turn if p.approved_turn is not None else turn,
        )
        if p.accelerated:  # the confirmatory Phase III starts now (55.3)
            patients = pl.stage_patients("phase3", "standard", data)
            months = pl.stage_months(p, "phase3", "standard", balance, data)
            p = replace(
                p,
                confirm_start=turn,
                confirm_due=turn + months,
                confirm_cost=pl.stage_cost_cents(p, "phase3", patients, months, balance, data),
            )
        state = pl.with_programme(state, p)
    return state


def _request_hta(
    state: GameState, p: Programme, rows: list[Authorisation], rng: RngFactory, data: GameData
) -> GameState:
    pricing = pd.file(data).pricing
    lo, hi = pricing.hta_months
    new: list[Hta] = []
    for a in rows:
        if not pricing.region(a.region).hta:
            continue
        if any(h.programme_id == p.id and h.region == a.region for h in (*state.pharma_hta, *new)):
            continue
        g = draws.gen(rng, state.turn, draws.HTA, p.id, data.region_index(a.region))
        months = round(lo + (hi - lo) * float(g.random()))
        new.append(Hta(p.id, a.region, state.turn, max(a.from_turn, state.turn) + months))
    return replace(state, pharma_hta=(*state.pharma_hta, *new)) if new else state


def value_cap_cents(p: Programme, region: str, balance: Balance, data: GameData) -> float:
    """The HTA's value cap on the US list price (55.4): the indication's reference list x (1 +
    value_premium x (estimate - soc) / sd) x (1 + hta_max_premium)."""
    ind = pd.indication(data, p.indication)
    db = balance.pharma.demand
    # money-exact: ratio: a score, share or weight, not money
    value = 1 + db.value_premium * (p.obs_eff - ind.soc) / balance.pharma.efficacy.sd
    # money-exact: rate: a unit price in float cents, rounded where posted
    cap = ind.price_year * pd.CENTS * max(0.0, value)
    # money-exact: rate: a unit price in float cents, rounded where posted
    return cap * (1 + pd.file(data).pricing.hta_max_premium)


def covered(state: GameState, programme_id: int, region: str, data: GameData) -> bool:
    """Reimbursed in the region: no HTA there, or its decision covered the drug."""
    if not pd.file(data).pricing.region(region).hta:
        return True
    return any(
        h.programme_id == programme_id and h.region == region and h.status == "covered"
        for h in state.pharma_hta
    )


def month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Committees meet, reviews decide, HTAs decide, and confirmatory trials read out."""
    logs: list[LogItem] = []
    turn = state.turn
    for review in sorted(state.pharma_reviews, key=lambda r: r.id):
        if review.status != "review":
            continue
        p = next(q for q in state.pharma_programmes if q.id == review.programme_id)
        reg_name = pd.regulator(data, review.regulator).name
        if review.adcom and review.adcom_turn == turn and review.adcom_positive is None:
            g = draws.gen(rng, turn, draws.REVIEW, review.id, draws.ADCOM)
            ab = balance.pharma.approval
            ind = pd.indication(data, p.indication)
            neg = (
                ab.adcom_negative
                * pl.sigmoid(-(p.obs_eff - ind.soc) / balance.pharma.efficacy.sd)
                * HALF
            )
            positive = float(g.random()) >= min(1.0, neg)
            review = replace(review, adcom_positive=positive)
            state = _with_review(state, review)
            logs.append(
                inbox_item(
                    turn,
                    p.company_id,
                    "pharma_adcom_positive" if positive else "pharma_adcom_negative",
                    link_kind="pharma",
                    link_id=p.id,
                    name=p.name,
                    regulator=reg_name,
                )
            )
        if turn < review.due_turn or pd.held(state, p.company_id, review.regulator):
            continue
        g = draws.gen(rng, turn, draws.REVIEW, review.id, draws.DECISION)
        ok = float(g.random()) < approve_chance(p, review, balance, data)
        review = replace(review, status="approved" if ok else "crl", decided_turn=turn)
        state = _with_review(state, review)
        if ok:
            state = _authorise(state, p, review.regulator, rng, review.id, balance, data)
        logs.append(
            inbox_item(
                turn,
                p.company_id,
                "pharma_approved" if ok else "pharma_crl",
                link_kind="pharma",
                link_id=p.id,
                name=p.name,
                regulator=reg_name,
            )
        )
    state, more = _hta_month(state, balance, data)
    logs += more
    state, entries, more = _confirmatory(state, rng, balance, data)
    return state, entries, logs + more


def _with_review(state: GameState, review: Review) -> GameState:
    return replace(
        state,
        pharma_reviews=tuple(review if r.id == review.id else r for r in state.pharma_reviews),
    )


def _hta_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    logs: list[LogItem] = []
    rows = list(state.pharma_hta)
    for i, h in enumerate(rows):
        if h.status != "pending" or state.turn < h.due_turn:
            continue
        drug = next((d for d in state.pharma_drugs if d.programme_id == h.programme_id), None)
        p = next(q for q in state.pharma_programmes if q.id == h.programme_id)
        ok = drug is not None and drug.list_cents <= value_cap_cents(p, h.region, balance, data)
        rows[i] = replace(h, status="covered" if ok else "refused", decided_turn=state.turn)
        logs.append(
            inbox_item(
                state.turn,
                p.company_id,
                "pharma_hta_covered" if ok else "pharma_hta_refused",
                link_kind="pharma",
                link_id=p.id,
                name=p.name,
                region=h.region,
            )
        )
    return replace(state, pharma_hta=tuple(rows)), logs


def reprice_hta(state: GameState, p: Programme, balance: Balance, data: GameData) -> GameState:
    """A refused HTA is asked again (in the HTA's shortest months) after a price change."""
    lo, _ = pd.file(data).pricing.hta_months
    rows = tuple(
        replace(h, status="pending", due_turn=state.turn + round(lo), decided_turn=None)
        if h.programme_id == p.id and h.status == "refused"
        else h
        for h in state.pharma_hta
    )
    return replace(state, pharma_hta=rows)


def _confirmatory(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Accelerated approval (55.3): the confirmatory Phase III (started at approval, standard
    design) spends to its planned end and reads out; a failure withdraws the US approval."""
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    us = pd.us_regulator(data).key
    turn = state.turn
    for p in sorted(state.pharma_programmes, key=lambda q: q.id):
        due = p.confirm_due
        if due is None:
            continue
        months = max(1, due - p.confirm_start)
        left = p.confirm_cost - p.confirm_spent
        amount = left if turn >= due - 1 else min(left, p.confirm_cost // months)
        if amount > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=p.company_id,
                    memo=f"{p.name}: confirmatory Phase III",
                    debit=RESEARCH,
                    credit=CASH,
                    amount=amount,
                )
            )
            p = replace(p, confirm_spent=p.confirm_spent + amount)
        if turn < due:
            state = pl.with_programme(state, p)
            continue
        g = draws.gen(rng, turn, draws.READOUT, p.id, pd.stage_index("approved"), p.attempt)
        ok = float(g.random()) < pl.chance(p, "phase3", "standard", balance, data)
        p = replace(p, confirm_due=None, accelerated=False)
        if not ok:
            rows = tuple(
                a
                for a in state.pharma_authorisations
                if not (a.programme_id == p.id and a.authority == us)
            )
            state = replace(state, pharma_authorisations=rows)
        state = pl.with_programme(state, p)
        logs.append(
            inbox_item(
                turn,
                p.company_id,
                "pharma_confirmed" if ok else "pharma_withdrawn",
                link_kind="pharma",
                link_id=p.id,
                name=p.name,
            )
        )
    return state, entries, logs
