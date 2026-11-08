"""Becoming a holding company (docs/formulas.md 31.2, M16, stage 5).

The gate: listed, and two or more subsidiaries or group revenue of `group.stage5_revenue_cents`
a year. Forming one (energy 20, fees of 0.1% of market cap): a new company "<Name> Holdings"
takes the listing, the cap table (every holder but the operating company's option pool) and the
board; the founder is its Chair and keeps working at the operating company. The operating
company and every kept brand become its 100% subsidiaries; shareholders swap one for one.

Its books: at forming, it holds the operating company at book (1810 against 3000, the swapped
shares), and the operating company passes it its brands (their 1810 and goodwill) as a
distribution. Each month its group office costs `group.office_monthly_cents`; the operating
company pays up what it needs, and it funds the operating company out of its own cash if that
falls below zero (mirror sweeps, 28.5)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import GroupRuleError, InvalidActionError
from tst.sim.finance.captable import fd_shares
from tst.sim.finance.models import CapEntry
from tst.sim.group.models import Holding, Ownership
from tst.sim.group.ownership import book_cents, carrying_cents, equity_cents, goodwill_of
from tst.sim.ledger import (
    CASH,
    COMMON_EQUITY,
    GENERAL_ADMIN,
    GOODWILL,
    INVESTMENT_SUBSIDIARIES,
    LedgerBalances,
    LedgerEntry,
    LedgerLine,
    account_balance,
    apply_entries,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import exact, format_money
from tst.sim.products.phases import projected_revenue
from tst.sim.rivals.models import HOLDING_KEY
from tst.sim.state import (
    CompanyState,
    GameState,
    group_companies,
    holding_of,
    owner_at,
    public_of,
    reach_stage,
    with_company,
    with_holding,
    with_ownership,
)

HOLDING_STAGE = 5  # tunable-exempt: spec section 3, stage 5 conglomerate
MONTHS_A_YEAR = 12  # tunable-exempt: calendar
SUFFIX = " Holdings"  # tunable-exempt: the holding company's name (31.2)
GROUP_LINK: Final = "group"
FUNDING = "Funding for"


@dataclass(frozen=True, slots=True)
class FormHolding:
    """Form the holding company over the player's listed company (31.2)."""

    actor_id: int
    kind: Literal["form_holding"] = "form_holding"


def subsidiaries_now(state: GameState, company_id: int) -> tuple[CompanyState, ...]:
    """The company's subsidiaries now, at any depth (31.1)."""
    return group_companies(state, company_id)[1:]


def group_revenue_year_cents(state: GameState, company_id: int) -> int:
    """The group's revenue a year at its current customers and prices: 12 x this month's
    (31.2's gate; M16 decision: the run rate, as stages 2-3 read ARR)."""
    return MONTHS_A_YEAR * sum(
        projected_revenue(state, c.id) for c in group_companies(state, company_id)
    )


def gate(state: GameState, balance: Balance) -> list[str]:
    """What still stands between the player and a holding company (31.2): empty when it can
    be formed. Public words only."""
    gb = balance.group
    player = state.player
    if holding_of(state) is not None:
        return ["a holding company is already formed"]
    reasons = []
    if public_of(state, player.id) is None:
        reasons.append("the company must be listed")
    subs = len(subsidiaries_now(state, player.id))
    revenue = group_revenue_year_cents(state, player.id)
    if subs < gb.stage5_subsidiaries and revenue < gb.stage5_revenue_cents:
        reasons.append(
            f"it needs {gb.stage5_subsidiaries} subsidiaries (it has {subs}) or group revenue "
            f"of {format_money(gb.stage5_revenue_cents)} a year (it has {format_money(revenue)})"
        )
    return reasons


def form_fee_cents(state: GameState, balance: Balance) -> int:
    """0.1% of the market cap at the last month end (31.2)."""
    player = state.player.id
    public = public_of(state, player)
    if public is None:
        return 0
    return round(exact(balance.group.form_fee) * public.price_cents * fd_shares(state, player))


def form(
    state: GameState,
    action: FormHolding,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    player = state.player
    founder = state.founder_of(player.id)
    if founder is None or founder.id != action.actor_id:
        raise InvalidActionError("only the founder can form a holding company")
    reasons = gate(state, balance)
    if reasons:
        raise GroupRuleError("you cannot form a holding company yet: " + "; ".join(reasons))
    state = spend_energy(
        state, action.actor_id, action.kind, balance, cost=balance.group.form_energy
    )
    turn = state.turn
    entries: list[LedgerEntry] = []
    fee = form_fee_cents(state, balance)
    if fee > 0:
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=player.id,
                memo="Legal fees: forming the holding company",
                debit=GENERAL_ADMIN,
                credit=CASH,
                amount=fee,
            )
        )
    books = apply_entries(balances, entries)
    hid = max(c.id for c in state.companies) + 1
    holding = CompanyState(
        id=hid,
        name=f"{player.name}{SUFFIX}",
        is_player=True,
        stage=HOLDING_STAGE,
        founded_turn=turn,
        stage_history=((HOLDING_STAGE, turn),),
        mission=player.mission,
        hq_city=player.hq_city,
        # a stable identity for its streams, never the database id (ADR-0013)
        rival_key=(HOLDING_KEY, len(state.holdings)),
    )
    state = replace(state, companies=(*state.companies, holding))
    state = with_holding(state, Holding(hid, player.id, turn, founder.id))
    # The holding company holds the operating company at book: its shareholders' shares
    # swap one for one, so its paid-in equity is the operating company's net assets.
    book = book_cents(books, player.id, data)
    entries.append(
        LedgerEntry(
            turn,
            hid,
            f"Formed over {player.name}",
            (LedgerLine(INVESTMENT_SUBSIDIARIES, book), LedgerLine(COMMON_EQUITY, -book)),
        )
        if book
        else LedgerEntry(turn, hid, f"Formed over {player.name}", (LedgerLine(CASH, 0),) * 2)
    )
    state = with_ownership(
        state,
        Ownership(
            id=0,
            company_id=player.id,
            owner_id=hid,
            from_turn=turn,
            book_cents=book,
            equity_cents=equity_cents(books, player.id, data),
            common_control=True,
        ),
    )
    state = with_company(state, replace(state.company(player.id), parent_id=hid))
    # The kept brands pass to the holding company with their investment and goodwill.
    for brand in [c for c in state.companies if c.parent_id == player.id]:
        held = owner_at(state, brand.id)
        if held is None:
            continue
        carrying = carrying_cents(held, books, data) if held.id else 0
        goodwill = goodwill_of(state, held) if held.id else 0
        moved = carrying + goodwill
        if moved:
            entries.append(
                LedgerEntry(
                    turn,
                    player.id,
                    f"{brand.name} passed to {holding.name}",
                    tuple(
                        x
                        for x in (
                            LedgerLine(COMMON_EQUITY, moved),
                            LedgerLine(INVESTMENT_SUBSIDIARIES, -carrying),
                            LedgerLine(GOODWILL, -goodwill),
                        )
                        if x.amount
                    ),
                )
            )
            entries.append(
                LedgerEntry(
                    turn,
                    hid,
                    f"{brand.name} from {player.name}",
                    tuple(
                        x
                        for x in (
                            LedgerLine(INVESTMENT_SUBSIDIARIES, carrying - moved),
                            LedgerLine(GOODWILL, goodwill),
                        )
                        if x.amount
                    )
                    or (LedgerLine(GOODWILL, 0),) * 2,
                )
            )
        if held.id:
            state = with_ownership(state, replace(held, to_turn=turn, end_reason="transferred"))
        state = with_ownership(
            state,
            Ownership(
                id=0,
                company_id=brand.id,
                owner_id=hid,
                from_turn=turn,
                book_cents=carrying,
                equity_cents=equity_cents(books, brand.id, data),
                goodwill_cents=goodwill,
                common_control=True,
            ),
        )
        state = with_company(state, replace(state.company(brand.id), parent_id=hid))
    state = _move_listing(state, player.id, hid, holding.name, turn)
    state = with_company(state, reach_stage(state.company(hid), HOLDING_STAGE, turn))
    log = inbox_item(
        turn,
        player.id,
        "holding_formed",
        link_kind=GROUP_LINK,
        name=holding.name,
        subsidiaries=len(subsidiaries_now(state, hid)),
        fee_cents=fee,
    )
    return Outcome(state, tuple(e for e in entries if any(x.amount for x in e.lines)), (log,))


def _move_listing(state: GameState, old: int, new: int, name: str, turn: int) -> GameState:
    """The listing (its market state), its guidance, the board and every holder but the
    option pool move to the holding company; the operating company's cap table becomes the
    holding company's stake beside its option pool and grants (31.2, 31.4)."""
    # The IPO chain's record stays the operating company's history (its IPO, 25.2).
    state = replace(
        state,
        public_companies=tuple(
            replace(p, company_id=new) if p.company_id == old else p for p in state.public_companies
        ),
        guidance=tuple(
            replace(g, company_id=new) if g.company_id == old else g for g in state.guidance
        ),
        seats=tuple(replace(s, company_id=new) if s.company_id == old else s for s in state.seats),
    )
    moved = [e for e in state.company_cap(old) if e.holder_kind != "pool"]
    shares = sum(e.shares for e in moved)
    ids = {e.id for e in moved}
    entry_id = max((e.id for e in state.cap_entries), default=0) + 1
    stake = CapEntry(
        id=entry_id,
        company_id=old,
        holder_kind="group",
        share_class="common",
        shares=shares,
        acquired_turn=turn,
        name=name,
    )
    state = replace(
        state,
        cap_entries=(
            *(replace(e, company_id=new) if e.id in ids else e for e in state.cap_entries),
            stake,
        ),
    )
    return state


# --- Every month ---------------------------------------------------------------------------


def holding_month(
    state: GameState, balances: LedgerBalances, balance: Balance
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """Phase 7 before brands' sweeps (31.2): the group office's cost, the holding company
    funding its operating company out of its own cash when that is below zero, and the
    operating company paying up what the holding company needs to stay above zero."""
    held = holding_of(state)
    if held is None:
        return state, (), ()
    hid, op, turn = held.company_id, held.operating_id, state.turn
    entries: list[LedgerEntry] = []
    office = balance.group.office_monthly_cents
    if office > 0:
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=hid,
                memo="Group office",
                debit=GENERAL_ADMIN,
                credit=CASH,
                amount=office,
            )
        )
    books = apply_entries(balances, entries)
    mine, theirs = account_balance(books, hid, CASH), account_balance(books, op, CASH)
    name, op_name = state.company(hid).name, state.company(op).name
    if theirs < 0 < mine:  # the holding company funds its operating company (28.5)
        amount = min(mine, -theirs)
        entries += _mirror(turn, hid, op, amount, f"{FUNDING} {op_name}", f"Funding from {name}")
    elif mine < 0 < theirs:  # the operating company pays up what the holding company needs
        amount = min(theirs, -mine)
        entries += _mirror(turn, op, hid, amount, f"Paid up to {name}", f"Paid up by {op_name}")
    return state, tuple(entries), ()


def _mirror(
    turn: int, payer: int, payee: int, amount: int, out_memo: str, in_memo: str
) -> list[LedgerEntry]:
    """Cash between the holding company and its 100%-owned operating company (28.5): the
    parent's funding raises its investment and the subsidiary's equity; the subsidiary paying
    up lowers both. `payer` is the holding company when the memo is a funding."""
    if out_memo.startswith(FUNDING):
        payer_lines = (INVESTMENT_SUBSIDIARIES, CASH)
        payee_lines = (CASH, COMMON_EQUITY)
    else:
        payer_lines = (COMMON_EQUITY, CASH)
        payee_lines = (CASH, INVESTMENT_SUBSIDIARIES)
    return [
        LedgerEntry.transfer(
            turn=turn,
            company_id=payer,
            memo=out_memo,
            debit=payer_lines[0],
            credit=payer_lines[1],
            amount=amount,
        ),
        LedgerEntry.transfer(
            turn=turn,
            company_id=payee,
            memo=in_memo,
            debit=payee_lines[0],
            credit=payee_lines[1],
            amount=amount,
        ),
    ]
