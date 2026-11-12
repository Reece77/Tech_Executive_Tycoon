"""The Group screen's record and its subsidiaries' voices (M23c, playtest 5).

- **Capital actions** (31.5): every stake sale, carve-out, spin-off and buyout the group made:
  its date, proceeds, ownership before and after, the non-controlling interest it left, and the
  value it created on the owner's books (the equity line of its entry: what the sale fetched
  over the investment it gave up, or the premium a buyout paid over the minority's book). Read
  from the ledger entries the engine posted and the ownership rebases, never recomputed.
- **Quarterly updates**: each subsidiary's CEO reports the quarter in their own words from
  public numbers (revenue, operating margin, cash, the mandate's last review) and ends with a
  question; the player's advice re-sets the mandate through the existing mandate action.

Display only: nothing here is a rule, and nothing reads a hidden value."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from tst.api.schemas.group import AdviceOut, CapitalActionOut, SubsidiaryUpdateOut
from tst.api.views import person_name
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.group.models import FULL_STAKE_BP, Ownership
from tst.sim.group.subsidiaries import is_subsidiary
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerBalances, account_balance
from tst.sim.mna import valuation
from tst.sim.press.names import rival_ceo_id
from tst.sim.state import GameState, mandate_of

QUARTER: Final = 3  # tunable-exempt: months a quarter
# The memos tst.sim.group.capital posts, and the kind each one is.
MEMOS: Final = (
    ("Sold ", "stake_sale"),
    ("Carve-out of ", "carve_out"),
    ("Spin-off of ", "spin_off"),
    ("Bought out the minorities of ", "buyout"),
)
KIND_LABELS: Final = {
    "stake_sale": "Stake sale",
    "carve_out": "Carve-out",
    "spin_off": "Spin-off",
    "buyout": "Buyout",
}

LedgerRow = tuple[int, int, str, dict[str, int]]  # (turn, company_id, memo, account -> cents)


def _kind(memo: str) -> tuple[str, str] | None:
    """(kind, company name) of a capital-action memo, else None."""
    for prefix, kind in MEMOS:
        if memo.startswith(prefix):
            rest = memo[len(prefix) :]
            if kind == "stake_sale":  # "Sold 30% of Name"
                _, _, rest = rest.partition(" of ")
            return kind, rest
    return None


def _ownership(state: GameState, company_id: int, turn: int) -> Ownership | None:
    """The group's holding of the company that the action at `turn` changed."""
    found = [o for o in state.ownerships if o.company_id == company_id and o.from_turn <= turn]
    found.sort(key=lambda o: (o.to_turn is None, o.to_turn or 0, o.id))
    for o in found:
        if o.to_turn is None or o.to_turn >= turn:
            return o
    return found[-1] if found else None


def _step(o: Ownership, turn: int, nth: int) -> tuple[int, int, int]:
    """(stake before, stake after, book equity after) of the `nth` stake change at `turn`:
    several actions in one month each add a rebase, in the order they were taken. Equity
    accounts are credit-normal (the stored balance is debit positive)."""
    stakes = [(o.from_turn, o.stake_bp, o.equity_cents), *((t, s, e) for t, s, _, e in o.rebases)]
    at = [i for i, (t, _, _) in enumerate(stakes) if t == turn and i > 0]
    if nth < len(at):
        i = at[nth]
        return stakes[i - 1][1], stakes[i][1], -stakes[i][2]
    stake, _, equity = o.basis(turn)
    return o.stake_at(turn - 1), stake, -equity


def capital_history(
    state: GameState, rows: Iterable[LedgerRow], balances: LedgerBalances, data: LoadedData
) -> list[CapitalActionOut]:
    by_name = {c.name: c.id for c in state.companies}
    seen: dict[tuple[int, int], int] = {}  # (company, turn) -> stake changes already read
    out = []
    for turn, owner_id, memo, lines in rows:
        parsed = _kind(memo)
        if parsed is None:
            continue
        kind, name = parsed
        cid = by_name.get(name)
        if cid is None:
            continue
        o = _ownership(state, cid, turn)
        before, after, equity = FULL_STAKE_BP, FULL_STAKE_BP, 0
        if kind == "spin_off":
            if o is not None:
                before, equity = o.stake_at(turn), -o.basis(turn)[2]
            after = next(
                (s.stake_bp for s in state.stakes if s.company_id == cid and s.from_turn == turn),
                0,
            )
        elif o is not None:
            nth = seen.get((cid, turn), 0)
            seen[(cid, turn)] = nth + 1
            before, after, equity = _step(o, turn, nth)
        nci = 0 if kind == "spin_off" else round(equity * (FULL_STAKE_BP - after) / FULL_STAKE_BP)
        proceeds = lines.get(CASH, 0)
        created = -lines.get(COMMON_EQUITY, 0)
        if kind == "buyout":
            # the premium over the minority's share of book equity (negative: value paid away)
            minority_book = round(equity * (FULL_STAKE_BP - before) / FULL_STAKE_BP)
            created = minority_book + proceeds  # proceeds is the (negative) price paid
        cap = valuation.market_cap_cents(state, cid, balances, data.balance, data.game_data)
        alive = state.company(cid).alive
        out.append(
            CapitalActionOut(
                turn=turn,
                date_label=format_turn(turn),
                kind=kind,
                kind_label=KIND_LABELS[kind],
                company_id=cid,
                company=name,
                owner=state.company(owner_id).name,
                proceeds_cents=proceeds,
                stake_before_bp=before,
                stake_after_bp=after,
                nci_cents=nci,
                value_created_cents=created,
                value_note=_note(kind, created),
                market_cap_now_cents=cap if alive else None,
                stake_value_now_cents=round(cap * after / FULL_STAKE_BP)
                if cap is not None and alive
                else None,
            )
        )
    out.reverse()  # newest first (rows come in posting order)
    return out


def _note(kind: str, created: int) -> str:
    if kind == "spin_off":
        return "the investment given to shareholders (a distribution, not a loss)"
    if kind == "buyout":
        return (
            "paid over the minority's book value"
            if created < 0
            else "bought below the minority's book value"
        )
    return (
        "the sale fetched more than the book value it gave up"
        if created >= 0
        else "the sale fetched less than the book value it gave up"
    )


# --- Quarterly updates ---------------------------------------------------------------------

ADVICE: Final = (
    ("grow", "Push for growth: spend to win share"),
    ("margin", "Tighten up: protect the margin"),
    ("return_cash", "Send cash back to the group"),
)


def _sum(xs: tuple[int, ...] | list[int]) -> int:
    return sum(xs)


def _pct(x: float) -> str:
    return f"{x * 100:+.0f}%"


def _voice(ceo: str, company: str, revenue: int, prior: int, margin: float | None) -> str:
    """The CEO's opening line, from the quarter's numbers (plain, first person)."""
    if prior <= 0 and revenue <= 0:
        return f"{company} has no revenue yet; we are still building."
    if prior <= 0:
        return f"{company} booked its first revenue this quarter."
    change = revenue / prior - 1
    if change > 0.1:
        tone = f"A strong quarter: revenue is up {_pct(change)} on the last."
    elif change < -0.1:
        tone = f"A hard quarter, I won't dress it up: revenue is down {_pct(change)} on the last."
    else:
        tone = f"A steady quarter: revenue moved {_pct(change)} on the last."
    if margin is not None:
        tone += f" Operating margin {margin * 100:.0f}%."
    return tone


def subsidiary_updates(
    state: GameState, balances: LedgerBalances, data: LoadedData
) -> list[SubsidiaryUpdateOut]:
    """One update a quarter per subsidiary run by its own CEO: the latest quarter's numbers."""
    from tst.sim.state import group_members, listed_id

    out = []
    root = listed_id(state)
    for m in group_members(state, root):
        cid = m.company_id
        if m.end is not None or not is_subsidiary(state, cid):
            continue
        company = state.company(cid)
        if not company.alive:
            continue
        ceo_id = rival_ceo_id(state, cid)
        ceo = person_name(state.person(ceo_id)) if ceo_id is not None else "The CEO"
        mrr = company.mrr_history
        revenue = _sum(mrr[-QUARTER:])
        prior = _sum(mrr[-2 * QUARTER : -QUARTER])
        ops = company.op_history[-QUARTER:]
        margin = sum(ops) / revenue if revenue > 0 and ops else None
        cash = account_balance(balances, cid, CASH)
        mandate = mandate_of(state, cid)
        lines = [_voice(ceo, company.name, revenue, prior, margin)]
        lines.append(f"We hold {_money(cash)} in cash.")
        if mandate is not None:
            words = {"grow": "growth", "margin": "margin", "return_cash": "returning cash"}
            lines.append(f"Our mandate is {words.get(mandate.kind, mandate.kind)}.")
            if mandate.last_result:
                lines.append(f"At the last review we {mandate.last_result}.")
            question = _question(mandate.kind, margin, cash, revenue, prior)
        else:
            question = "We have no mandate yet. What should we focus on?"
        quarter_end = state.turn - (state.turn + 1) % QUARTER
        out.append(
            SubsidiaryUpdateOut(
                company_id=cid,
                company=company.name,
                ceo=ceo,
                quarter_label=format_turn(max(0, quarter_end)),
                revenue_cents=revenue,
                prior_revenue_cents=prior,
                operating_margin=margin,
                cash_cents=cash,
                mandate=mandate.kind if mandate is not None else None,
                capex_limit_cents=mandate.capex_limit_cents if mandate is not None else 0,
                categories=list(mandate.categories) if mandate is not None else [],
                regions=list(mandate.regions) if mandate is not None else [],
                body=" ".join(lines),
                question=question,
                advice=[
                    AdviceOut(
                        mandate=k, label=label, current=mandate is not None and k == mandate.kind
                    )
                    for k, label in ADVICE
                ],
                advice_energy=data.balance.group.mandate.energy,
            )
        )
    return out


def _question(kind: str, margin: float | None, cash: int, revenue: int, prior: int) -> str:
    if margin is not None and margin < 0 and kind == "grow":
        return "We are losing money to grow. Do we keep pushing, or tighten up?"
    if kind == "return_cash" and revenue < prior:
        return "Sales are slipping while we send cash up. Should we reinvest instead?"
    if kind == "margin" and revenue > prior:
        return "Demand is there. Do we hold the margin, or spend to grow faster?"
    if cash <= 0:
        return "Cash is tight. Should we focus on margin?"
    return "Where would you like us to lean next quarter?"


def _money(cents: int) -> str:
    from tst.sim.money import format_money

    return format_money(cents)
