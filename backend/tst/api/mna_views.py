"""Read models for mergers and acquisitions (M14, formulas.md 28.8). Targets are listed by
name, never by value, and nothing here reads a reservation, a board's bar, a tender's chance,
a block probability or a problem before diligence."""

from __future__ import annotations

import math

from tst.api.schemas.mna import (
    AcquisitionOut,
    DealOut,
    MnaOut,
    SubsidiaryOut,
    TargetOut,
    TargetPersonOut,
    TargetProductOut,
)
from tst.loader import LoadedData
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.mna import deals, valuation
from tst.sim.mna import formulas as mf
from tst.sim.mna.draws import fixed_draws
from tst.sim.mna.models import Acquisition
from tst.sim.products.models import SELLING
from tst.sim.products.phases import current_feature
from tst.sim.state import GameState, public_of, target_file

PRODUCT_TAG = 6  # stream mna sub-key of a product's revealed ranges (after diligence)


def _product_range(
    state: GameState, target: int, pid: int, value: float, half: float
) -> tuple[int, int]:
    company = state.company(target)
    from tst.sim.rivals.models import stream_key

    u = float(
        fixed_draws(
            state.save_meta.master_seed, *stream_key(target, company.rival_key), PRODUCT_TAG, pid
        ).random()
    )
    offset = (u - mf.CENTRE) * half
    return max(0, math.floor(value + offset - half)), min(100, math.ceil(value + offset + half))


def target_out(
    state: GameState,
    company_id: int,
    balances: LedgerBalances,
    data: LoadedData,
    observer: int,
) -> TargetOut:
    b, g = data.balance, data.game_data
    company = state.company(company_id)
    found = target_file(state, observer, company_id)
    diligenced = found is not None and found.diligenced
    listed = valuation.is_listed(state, company_id, g)
    cap = valuation.market_cap_cents(state, company_id, balances, b, g) if listed else None
    low = high = None
    if not listed:
        low, high = valuation.value_range_cents(
            state, company_id, balances, b, g, diligenced=diligenced
        )
    estimate = deals.estimate_cents(state, observer, company_id, balances, b, g)
    products = []
    half = b.mna.diligence.product_range
    for p in state.company_products(company_id):
        if p.status not in SELLING and p.status != "in_development":
            continue
        q = f = None
        if diligenced:
            q = _product_range(state, company_id, p.id, p.quality, half)
            f = _product_range(state, company_id, p.id + 1, current_feature(p, g, state.turn), half)
        products.append(
            TargetProductOut(
                product_id=p.id,
                name=p.name,
                category=g.category(p.category).label,
                quality_low=q[0] if q else None,
                quality_high=q[1] if q else None,
                feature_low=f[0] if f else None,
                feature_high=f[1] if f else None,
            )
        )
    people = []
    if diligenced:
        for e in sorted(state.staff(company_id), key=lambda e: e.id):
            person = state.person(e.person_id)
            people.append(
                TargetPersonOut(
                    person_id=person.id,
                    name=f"{person.first_name} {person.last_name}",
                    role=g.role(e.role).label,
                )
            )
    blocked = None
    if found is not None and found.blocked_until is not None and state.turn < found.blocked_until:
        blocked = found.blocked_until - state.turn
    deal = deals.open_deal(state, company_id)
    from tst.sim.mna.integration import can_integrate

    allowed = can_integrate(state, company_id, b)
    status = (
        "done"
        if diligenced
        else ("under_way" if found and found.diligence_turn is not None else "none")
    )
    categories = sorted({g.category(p.category).label for p in state.company_products(company_id)})
    return TargetOut(
        company_id=company_id,
        name=company.name,
        kind="startup" if company.is_startup else "incumbent",
        listed=listed,
        market_cap_cents=cap,
        value_low_cents=low,
        value_high_cents=high,
        categories=categories,
        diligence=status,
        diligence_cost_cents=mf.diligence_cost_cents(estimate, b.mna),
        findings=list(found.problems) if diligenced and found is not None else [],
        products=products,
        people=people,
        counter_cents=found.counter_cents if found is not None else None,
        talks_closed_months=blocked,
        open_deal_id=deal.id if deal is not None else None,
        integrate_allowed=allowed,
        integrate_note=None
        if allowed
        else f"More than {b.integration.max_staff} staff: too big to integrate. Keep it as a "
        "brand; its key people can still move to you.",
    )


def targets(state: GameState) -> list[int]:
    """Every company that can be bought: independent rivals in business, by name."""
    return [
        c.id for c in sorted(state.rivals(), key=lambda c: (c.name, c.id)) if c.parent_id is None
    ]


def _deal_out(state: GameState, d: object) -> DealOut:
    from tst.sim.mna.models import Deal

    assert isinstance(d, Deal)
    remedy = state.product(d.remedy_product_id) if d.remedy_product_id is not None else None
    return DealOut(
        deal_id=d.id,
        target_id=d.target_id,
        target_name=state.company(d.target_id).name,
        price_cents=d.price_cents,
        cash_share=d.cash_share,
        status=d.status,
        hostile=d.hostile,
        mode=d.mode,
        made_turn=d.made_turn,
        close_turn=d.close_turn,
        review_end_turn=d.review_end_turn,
        combined_share=d.combined_share,
        market=d.market,
        remedy_product=remedy.name if remedy is not None and d.status == "blocked" else None,
    )


def _acquisition_out(state: GameState, a: Acquisition, data: LoadedData) -> AcquisitionOut:
    left = max(0, a.closed_turn + data.balance.integration.months - state.turn)
    return AcquisitionOut(
        deal_id=a.deal_id,
        company_id=a.target_id,
        name=state.company(a.target_id).name,
        mode=a.mode,
        closed_turn=a.closed_turn,
        price_cents=a.price_cents,
        directive=a.directive,
        key_people=a.key_people,
        pool_kept=a.pool_kept,
        let_go=a.let_go,
        departed=a.departed,
        problems=list(a.problems),
        clash_months_left=left,
        cost_before_cents=a.cost_before_cents,
        unit_ids=list(a.unit_ids),
        flagged=state.turn < a.closed_turn + data.balance.mna.acquired_flag_months,
    )


def mna_out(state: GameState, balances: LedgerBalances, data: LoadedData) -> MnaOut:
    player = state.player.id
    subsidiaries = []
    for c in state.companies:
        if c.parent_id != player or not c.alive:
            continue
        acq = next(a for a in reversed(state.acquisitions) if a.target_id == c.id)
        subsidiaries.append(
            SubsidiaryOut(
                company_id=c.id,
                name=c.name,
                directive=acq.directive,
                mrr_cents=c.mrr_history[-1] if c.mrr_history else 0,
                cash_cents=account_balance(balances, c.id, CASH),
                staff=len(state.staff(c.id)),
            )
        )
    return MnaOut(
        targets=[target_out(state, cid, balances, data, player) for cid in targets(state)],
        deals=[_deal_out(state, d) for d in state.deals if d.acquirer_id == player],
        acquisitions=[
            _acquisition_out(state, a, data) for a in state.acquisitions if a.acquirer_id == player
        ],
        subsidiaries=subsidiaries,
        listed=public_of(state, player) is not None,
    )
