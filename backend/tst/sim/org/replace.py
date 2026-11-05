"""Replace's quick fill (docs/formulas.md 29.5, M14b): in phase 12, right after the batches,
a Replace plan's recruiter interviews the batch it brought and offers to the best, so the
offer is answered at the next Continue: one month (recruit.normal_months x replace_speed,
rounded) sooner than a normal plan, which interviews and offers the month after."""

from __future__ import annotations

from collections.abc import Mapping

from tst.sim.actions import Interview, MakeOffer
from tst.sim.data_models import Balance, GameData
from tst.sim.hiring.recruit import skip_months
from tst.sim.ledger import AccountCode, LedgerEntry
from tst.sim.log import LogItem
from tst.sim.money import Cents
from tst.sim.org.delegates import DelegateRun, plan_offer_salary, ranked_candidates, still_needed
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def replace_offers(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    plans = [p for p in state.plans if p.replace_of is not None and p.status == "active"]
    if not plans or skip_months(balance) < 1:
        return state, (), ()
    run = DelegateRun(state=state, balances=dict(balances), rng=rng, balance=balance, data=data)
    for plan in sorted(plans, key=lambda p: p.id):
        if still_needed(run.state, plan) <= 0:
            continue
        searches = {s.id for s in run.state.searches if s.plan_id == plan.id}
        fresh = [
            c
            for c in ranked_candidates(run.state, plan.company_id, plan.role, data, plan.focus)
            if c.search_id in searches and c.created_turn == run.state.turn
        ]
        for c in fresh:  # the recruiter screens the batch it brought
            if c.interviewed_turn is None:
                run.attempt(plan.company_id, Interview(plan.owner_id, c.person_id))
        ranked = [
            c
            for c in ranked_candidates(run.state, plan.company_id, plan.role, data, plan.focus)
            if c.search_id in searches and c.interviewed_turn is not None
        ]
        for c in ranked:
            if run.state.pending_offer_for(c.person_id) is not None:
                continue
            ask = run.state.person(c.person_id).salary_expectation_cents or 0
            offer = MakeOffer(
                plan.owner_id,
                c.person_id,
                plan_offer_salary(ask, plan.ratio_bp),
                plan.equity_bp,
                plan_id=plan.id,
            )
            if run.attempt(plan.company_id, offer):
                break
    return run.state, tuple(run.entries), tuple(run.logs)
