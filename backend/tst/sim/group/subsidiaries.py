"""Subsidiaries as companies (docs/formulas.md 31.4): mandates, the December review of each
subsidiary's CEO, a replacement after two misses, capital requests to the group, and boards.

- A **mandate** (energy 3) sets what the CEO runs the company for, and the brand directive it
  decides under (grow -> grow, return cash -> harvest, margin -> defend; tst.sim.mna.style),
  and how many months of costs it keeps before its cash goes up (31.4 money).
- Each **December** its board scores the CEO: grow on revenue growth over the year, margin on
  the year's operating margin, return cash on what it paid up over the year against its
  profit. Two misses in a row bring a replacement proposal.
- Each quarter its CEO may ask the group for capital (stream `group`), judged against the
  mandate: a grow mandate's request fits; the others' fit only when cash is short.
- Its **board** (derived): parent nominees, independents, and one seat per
  `group.seat_per_stake` held by minorities."""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, spend_energy
from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import GroupRuleError, InvalidActionError
from tst.sim.group import formulas as gf
from tst.sim.group.config import MANDATES
from tst.sim.group.models import FULL_STAKE_BP, GroupPitch, Mandate, MandateKind
from tst.sim.group.ownership import equity_cents
from tst.sim.ledger import (
    CASH,
    COMMON_EQUITY,
    INVESTMENT_SUBSIDIARIES,
    LedgerBalances,
    LedgerEntry,
    account_balance,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import exact
from tst.sim.press.names import rival_ceo_id
from tst.sim.rivals.models import player_key
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    group_companies,
    listed_id,
    mandate_of,
    owner_at,
    owner_of,
    with_employment,
    with_group_pitch,
    with_mandate,
)

DECEMBER = 11  # tunable-exempt: turn % 12 of December
QUARTER = 3  # tunable-exempt: months a quarter
PARENT_SEATS = 3  # tunable-exempt: parent nominees on a subsidiary's board (31.4)
INDEPENDENT_SEATS = 2  # tunable-exempt: independents on a subsidiary's board (31.4)
GROUP_LINK: Final = "group"
PITCH_TAG = 1  # tunable-exempt: stream group sub-key of a capital request's draw
REVIEW_MET, REVIEW_MISSED = "group_review_met", "group_review_missed"
REVIEW_PROPOSAL = "group_review_proposal"


@dataclass(frozen=True, slots=True)
class SetMandate:
    """Energy 3 (31.4): what a subsidiary's CEO runs it for."""

    actor_id: int
    company_id: int
    mandate: MandateKind
    capex_limit_cents: int = 0
    categories: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    kind: Literal["set_mandate"] = "set_mandate"


@dataclass(frozen=True, slots=True)
class ReplaceSubsidiaryCeo:
    """Accept the board's proposal: the CEO goes, the next leader takes over (31.4)."""

    actor_id: int
    company_id: int
    kind: Literal["replace_subsidiary_ceo"] = "replace_subsidiary_ceo"


@dataclass(frozen=True, slots=True)
class AnswerGroupPitch:
    """Approve or decline a subsidiary CEO's capital request (31.4)."""

    actor_id: int
    pitch_id: int
    approve: bool
    kind: Literal["answer_group_pitch"] = "answer_group_pitch"


def is_subsidiary(state: GameState, company_id: int) -> bool:
    """One of the player's group's companies run by its own CEO: not the listed root, not
    the operating company the player runs."""
    root = listed_id(state)
    if company_id in (root, state.player.id):
        return False
    try:
        company = state.company(company_id)
    except KeyError:
        return False
    return company.alive and owner_of(state, company_id) == root


def subsidiaries(state: GameState) -> list[int]:
    return [c.id for c in group_companies(state, listed_id(state)) if is_subsidiary(state, c.id)]


def board_seats(state: GameState, company_id: int, balance: Balance) -> tuple[int, int, int]:
    """(parent nominees, independents, minority seats) (31.4)."""
    held = owner_at(state, company_id)
    minority = FULL_STAKE_BP - (held.stake_at() if held is not None else FULL_STAKE_BP)
    return PARENT_SEATS, INDEPENDENT_SEATS, gf.minority_seats(minority, balance)


def set_mandate(
    state: GameState, action: SetMandate, balance: Balance, data: GameData, balances: LedgerBalances
) -> Outcome:
    if action.mandate not in MANDATES:
        raise GroupRuleError(f"a mandate is one of {', '.join(MANDATES)}")
    if not is_subsidiary(state, action.company_id):
        raise GroupRuleError("only a subsidiary run by its own CEO takes a mandate")
    if action.capex_limit_cents < 0:
        raise GroupRuleError("a capex limit cannot be negative")
    for c in action.categories:
        data.category(c)  # KeyError for an unknown category
    for r in action.regions:
        data.region(r)
    state = spend_energy(
        state, action.actor_id, action.kind, balance, cost=balance.group.mandate.energy
    )
    old = mandate_of(state, action.company_id)
    mandate = Mandate(
        company_id=action.company_id,
        kind=action.mandate,
        set_turn=state.turn,
        capex_limit_cents=action.capex_limit_cents,
        categories=action.categories,
        regions=action.regions,
        misses=0 if old is None or old.kind != action.mandate else old.misses,
        last_review_turn=old.last_review_turn if old is not None else None,
        last_result=old.last_result if old is not None else "",
        equity_cents=(
            old.equity_cents if old is not None else equity_cents(balances, action.company_id, data)
        ),
    )
    return Outcome(with_mandate(state, mandate))


def replace_ceo(state: GameState, action: ReplaceSubsidiaryCeo) -> Outcome:
    mandate = mandate_of(state, action.company_id)
    if mandate is None or not mandate.proposal:
        raise GroupRuleError("the board has not proposed a new CEO")
    ceo = rival_ceo_id(state, action.company_id)
    if ceo is not None:
        job = next(e for e in state.staff(action.company_id) if e.person_id == ceo)
        state = with_employment(
            state, replace(job, status="ended", end_turn=state.turn, end_reason="fired")
        )
    state = with_mandate(state, replace(mandate, misses=0, proposal=False))
    name = state.company(action.company_id).name
    log = inbox_item(
        state.turn, state.player.id, "group_ceo_replaced", link_kind=GROUP_LINK, company=name
    )
    return Outcome(state, (), (log,))


def answer_pitch(state: GameState, action: AnswerGroupPitch, balances: LedgerBalances) -> Outcome:
    pitch = next((p for p in state.group_pitches if p.id == action.pitch_id), None)
    if pitch is None or pitch.status != "pending":
        raise InvalidActionError(f"request {action.pitch_id} is not waiting for an answer")
    status: Literal["approved", "declined"] = "approved" if action.approve else "declined"
    state = with_group_pitch(state, replace(pitch, status=status, resolved_turn=state.turn))
    if not action.approve:
        return Outcome(state)
    held = owner_at(state, pitch.company_id)
    if held is None:
        raise GroupRuleError("that company is no longer the group's")
    owner = held.owner_id
    if account_balance(balances, owner, CASH) < pitch.amount_cents:
        raise GroupRuleError(f"{state.company(owner).name} does not have the cash")
    name = state.company(pitch.company_id).name
    entries = (
        LedgerEntry.transfer(
            turn=state.turn,
            company_id=owner,
            memo=f"Capital for {name}",
            debit=INVESTMENT_SUBSIDIARIES,
            credit=CASH,
            amount=pitch.amount_cents,
        ),
        LedgerEntry.transfer(
            turn=state.turn,
            company_id=pitch.company_id,
            memo=f"Capital from {state.company(owner).name}",
            debit=CASH,
            credit=COMMON_EQUITY,
            amount=pitch.amount_cents,
        ),
    )
    return Outcome(state, entries)


# --- December reviews and quarterly requests -------------------------------------------------


def _year(state: GameState, company_id: int) -> tuple[int, int, int]:
    """(revenue a year ago, revenue over the year, operating result over the year)."""
    company = state.company(company_id)
    mrr = company.mrr_history
    ops = company.op_history[-MONTHS_PER_YEAR:]
    then = mrr[-MONTHS_PER_YEAR - 1] if len(mrr) > MONTHS_PER_YEAR else 0
    return then, sum(mrr[-MONTHS_PER_YEAR:]), sum(ops)


def review(
    state: GameState, mandate: Mandate, balances: LedgerBalances, balance: Balance, data: GameData
) -> tuple[Mandate, bool, str]:
    """The board's score (31.4): (the mandate updated, met, the measure in words)."""
    mb = balance.group.mandate
    cid = mandate.company_id
    then, revenue, op = _year(state, cid)
    now = state.company(cid).mrr_history[-1] if state.company(cid).mrr_history else 0
    paid = equity_cents(balances, cid, data) - mandate.equity_cents  # debit: paid up
    if mandate.kind == "grow":
        growth = now / then - 1 if then > 0 else 0.0
        met, words = (
            growth >= mb.grow_target,
            f"revenue growth {growth:.0%} (target {mb.grow_target:.0%})",
        )
    elif mandate.kind == "margin":
        margin = op / revenue if revenue > 0 else 0.0
        met, words = (
            margin >= mb.margin_target,
            f"operating margin {margin:.0%} (target {mb.margin_target:.0%})",
        )
    else:
        payout = paid / op if op > 0 else 0.0
        met, words = (
            payout >= mb.payout_target,
            f"payout {payout:.0%} of profit (target {mb.payout_target:.0%})",
        )
    misses = 0 if met else mandate.misses + 1
    updated = replace(
        mandate,
        misses=misses,
        last_review_turn=state.turn,
        last_result=("met: " if met else "missed: ") + words,
        equity_cents=equity_cents(balances, cid, data),
        proposal=mandate.proposal or misses >= mb.review_misses,
    )
    return updated, met, words


def group_month(
    state: GameState, rng: RngFactory, balances: LedgerBalances, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Phase 7 (31.4): December reviews of every subsidiary under a mandate, and each quarter
    a capital request from a subsidiary CEO who draws one."""
    logs: list[LogItem] = []
    if not state.mandates:
        return state, ()
    mb = balance.group.mandate
    december = state.turn % MONTHS_PER_YEAR == DECEMBER
    for cid in subsidiaries(state):
        mandate = mandate_of(state, cid)
        name = state.company(cid).name
        if mandate is not None and december:
            updated, met, words = review(state, mandate, balances, balance, data)
            state = with_mandate(state, updated)
            proposed = updated.proposal and not mandate.proposal
            logs.append(
                inbox_item(
                    state.turn,
                    state.player.id,
                    "group_review_proposal"
                    if proposed
                    else ("group_review_met" if met else "group_review_missed"),
                    link_kind=GROUP_LINK,
                    company=name,
                    measure=words,
                    misses=updated.misses,
                )
            )
        if mandate is None or state.turn % QUARTER != 0:
            continue
        if any(p.company_id == cid and p.status == "pending" for p in state.group_pitches):
            continue
        company = state.company(cid)
        gen = rng.stream(state.turn, "group", *player_key(cid, company.rival_key), PITCH_TAG)
        if float(gen.random()) >= mb.pitch_chance:
            continue
        from tst.sim.mna.deals import monthly_costs_cents

        costs = monthly_costs_cents(state, cid, balance, data)
        amount = round(exact(mb.pitch_months) * costs)
        if mandate.capex_limit_cents:
            amount = min(amount, mandate.capex_limit_cents)
        ceo = rival_ceo_id(state, cid)
        if amount <= 0 or ceo is None:
            continue
        short = account_balance(balances, cid, CASH) < costs
        fits = mandate.kind == "grow" or short
        state = with_group_pitch(state, GroupPitch(0, cid, ceo, state.turn, amount, fits))
        logs.append(
            inbox_item(
                state.turn,
                state.player.id,
                "group_pitch",
                link_kind=GROUP_LINK,
                company=name,
                amount_cents=amount,
                fit="fits its mandate" if fits else "does not fit its mandate",
            )
        )
    # a request not answered by the next quarter lapses
    for p in state.group_pitches:
        if p.status == "pending" and state.turn - p.turn >= QUARTER:
            state = with_group_pitch(state, replace(p, status="lapsed", resolved_turn=state.turn))
    return state, tuple(logs)


def keep_months(state: GameState, company_id: int, balance: Balance) -> float | None:
    """Months of costs a subsidiary under a mandate keeps before its cash goes up (31.4);
    None without a mandate (M14's mna.sweep_months)."""
    mandate = mandate_of(state, company_id)
    return balance.group.mandate.keep_months(mandate.kind) if mandate is not None else None


def stake_of(state: GameState, company_id: int) -> Fraction:
    held = owner_at(state, company_id)
    return Fraction(held.stake_at() if held is not None else FULL_STAKE_BP, FULL_STAKE_BP)
