"""Insolvency, bridges and bankruptcy (docs/formulas.md 14.7, ADR-0018), and stages from
funding (14.8).

Phase 7, after the month's costs: an accepted bridge posts; an offer past its last turn
lapses; then if cash is below zero the company is insolvent (a critical note), existing
investors may offer one bridge per insolvency, and the third consecutive month ends the game.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from tst.sim.calendar import format_turn
from tst.sim.data_models import SERIES, Balance, GameData
from tst.sim.finance.board import average_confidence
from tst.sim.finance.captable import closed_rounds, last_round
from tst.sim.finance.fundraising import FINANCE_LINK, safe_entries
from tst.sim.finance.models import SERIES_LABELS, Safe
from tst.sim.finance.statements import projected_net_burn
from tst.sim.ledger import CASH, AccountCode, LedgerEntry, account_balance
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import Cents
from tst.sim.state import (
    CompanyState,
    GameState,
    reach_stage,
    with_company,
    with_employment,
    with_pool,
    with_product,
    with_product_segment,
    with_safe,
)

STAGE_LABELS = {2: "venture-backed", 3: "scale-up"}  # tunable-exempt: spec section 3 names


def post_bridges(
    state: GameState, balance: Balance
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """Accepted bridges' money arrives; offers past their last turn lapse."""
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for safe in state.safes:
        if safe.kind != "bridge":
            continue
        params = {"amount_cents": safe.amount_cents, "cap_cents": safe.cap_cents}
        if safe.status == "accepted":
            safe = replace(safe, status="outstanding", resolved_turn=state.turn)
            state = with_safe(state, safe)
            entries += safe_entries(state, safe, balance, "Bridge SAFE")
            logs.append(
                inbox_item(
                    state.turn, safe.company_id, "bridge_funded", link_kind=FINANCE_LINK, **params
                )
            )
        elif safe.status == "offered" and (safe.expires_turn or 0) < state.turn:
            state = with_safe(state, replace(safe, status="lapsed", resolved_turn=state.turn))
            logs.append(
                inbox_item(
                    state.turn, safe.company_id, "bridge_lapsed", link_kind=FINANCE_LINK, **params
                )
            )
    return state, tuple(entries), tuple(logs)


def bridge_amount(
    state: GameState, company_id: int, cash: Cents, balance: Balance, data: GameData
) -> Cents:
    """M4b (14.7): burn_months x this month's projected net burn, plus whatever gets cash back
    to zero. Computed when the bridge is accepted, so one taken in the last month of grace
    still clears the deficit; an offer shows what it would be today."""
    burn = projected_net_burn(state, company_id, balance, data)
    return round(balance.bankruptcy.bridge_burn_months * max(burn, 0)) + max(0, -cash)


def insolvency(
    state: GameState,
    balances: Mapping[tuple[int, AccountCode], Cents],
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Cash below zero at the end of phase 7: insolvency notes, a bridge offer, bankruptcy."""
    bk = balance.bankruptcy
    logs: list[LogItem] = []
    for company in state.ledger_companies():
        cash = account_balance(balances, company.id, CASH)
        if cash >= 0:
            if company.insolvent_months:
                state = with_company(state, replace(company, insolvent_months=0))
            continue
        months = company.insolvent_months + 1
        state = with_company(state, replace(company, insolvent_months=months))
        if not company.is_player:  # a rival fails after the same months; no bridges (15.1)
            if months >= bk.months:
                state, failed = fail_rival(state, state.company(company.id))
                logs += failed
            continue
        logs.append(
            inbox_item(
                state.turn,
                company.id,
                "insolvent",
                link_kind=FINANCE_LINK,
                cash_cents=cash,
                needed_cents=-cash,
                month=months,
            )
        )
        if months >= bk.months:
            state = replace(
                state,
                save_meta=replace(state.save_meta, game_state="bankrupt", ended_turn=state.turn),
            )
            logs.append(inbox_item(state.turn, company.id, "bankrupt", months=bk.months))
            continue
        avg = average_confidence(state, company.id)
        latest = last_round(state, company.id)
        since = state.turn - months + 1  # the turn this insolvency began
        offered = any(
            s.kind == "bridge" and s.raised_turn >= since for s in state.company_safes(company.id)
        )
        post = latest.post_money_cents if latest is not None else None
        if avg is None or avg < bk.bridge_min_confidence or offered or post is None:
            continue
        amount = bridge_amount(state, company.id, cash, balance, data)
        cap = round(bk.bridge_cap_of_post * post)
        safe_id, ids = state.next_ids.take("safe")
        expires = state.turn + bk.bridge_open_turns
        state = with_safe(
            replace(state, next_ids=ids),
            Safe(
                id=safe_id,
                company_id=company.id,
                kind="bridge",
                amount_cents=amount,
                cap_cents=cap,
                status="offered",
                raised_turn=state.turn,
                expires_turn=expires,
            ),
        )
        logs.append(
            inbox_item(
                state.turn,
                company.id,
                "bridge_offered",
                link_kind=FINANCE_LINK,
                link_id=safe_id,
                amount_cents=amount,
                cap_cents=cap,
                deadline=format_turn(expires),
            )
        )
    return state, tuple(logs)


def funding_stages(state: GameState, balance: Balance) -> tuple[GameState, tuple[LogItem, ...]]:
    """Phase 10 (14.8): from stage 1, a closed seed reaches stage 2 and a closed Series B
    stage 3, as ARR does (11.11). Stages only rise."""
    logs: list[LogItem] = []
    for company in state.ledger_companies():
        if company.stage < 1:
            continue
        done = {r.series for r in closed_rounds(state, company.id)}
        stage = company.stage
        reached = None
        for gate, series in sorted(balance.stages.funding.items()):
            later = SERIES[SERIES.index(series) :]
            if stage < gate and any(s in done for s in later):
                stage, reached = gate, series
        if reached is None:
            continue
        state = with_company(state, reach_stage(company, stage, state.turn))
        logs.append(
            inbox_item(
                state.turn,
                company.id,
                "stage_from_funding",
                stage_label=STAGE_LABELS.get(stage, f"stage {stage}"),
                series=SERIES_LABELS[reached],
                company=company.name,
            )
        )
    return state, tuple(logs)


def fail_rival(state: GameState, company: CompanyState) -> tuple[GameState, list[LogItem]]:
    """A rival bankrupt for bankruptcy.months month ends (15.1): its products retire and their
    customers return to the unserved pool, its staff are released, its pools empty."""
    state = with_company(state, replace(company, failed_turn=state.turn))
    for product in state.company_products(company.id):
        if product.status == "retired":
            continue
        for seg in state.segments_of(product.id):
            state = with_product_segment(state, replace(seg, customers=0.0))
        state = with_product(state, replace(product, status="retired", retired_turn=state.turn))
    for e in state.staff(company.id):
        state = with_employment(
            state, replace(e, status="ended", end_turn=state.turn, end_reason="company_failed")
        )
    for pool in state.company_pools(company.id):
        state = with_pool(state, replace(pool, headcount=0.0))
    return state, [inbox_item(state.turn, company.id, "rival_failed", company=company.name)]
