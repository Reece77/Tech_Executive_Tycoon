"""Stakes the group does not control (docs/formulas.md 31.3): the equity method for 20-50%
and fair value for under 20%, on the owner's own books.

- Each month an associate's carrying amount (1820) moves by the owner's share of the
  company's operating result that month, against 4910.
- Each December a financial investment (1830) is marked to fair value against 4920: the
  stake x the market cap for a listed company, else x the midpoint of its displayed value
  range (28.1; never the hidden value, 31.10)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from fractions import Fraction

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.group import formulas as gf
from tst.sim.group.models import FULL_STAKE_BP, Stake
from tst.sim.ledger import (
    ASSOCIATES,
    ASSOCIATES_PROFIT,
    FAIR_VALUE,
    FINANCIAL_INVESTMENTS,
    LedgerBalances,
    LedgerEntry,
)
from tst.sim.mna import valuation
from tst.sim.state import GameState, with_stake

DECEMBER = 11  # tunable-exempt: calendar month index (turn % 12) of December


def account_of(stake: Stake, balance: Balance) -> str:
    return (
        ASSOCIATES if gf.treatment(stake.stake_bp, balance) == "equity" else FINANCIAL_INVESTMENTS
    )


def fair_value_cents(
    state: GameState, stake: Stake, balances: LedgerBalances, balance: Balance, data: GameData
) -> int:
    """The stake's fair value (31.3): its share of the market cap if listed, else of the
    displayed value range's midpoint (28.1)."""
    cid = stake.company_id
    cap = valuation.market_cap_cents(state, cid, balances, balance, data)
    if cap is None:
        low, high = valuation.value_range_cents(state, cid, balances, balance, data)
        cap = (low + high) // 2
    return round(Fraction(stake.stake_bp, FULL_STAKE_BP) * cap)


def stakes_month(
    state: GameState,
    balances: LedgerBalances,
    operating: Mapping[int, int],
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[LedgerEntry, ...]]:
    """Phase 7 (31.3): associates' share of the month's operating result; in December, fair
    value for stakes under 20%. `operating` holds each company's operating result this month."""
    entries: list[LedgerEntry] = []
    december = state.turn % MONTHS_PER_YEAR == DECEMBER
    for stake in [x for x in state.stakes if x.is_open]:
        name = state.company(stake.company_id).name
        if gf.treatment(stake.stake_bp, balance) == "equity":
            share = round(
                Fraction(stake.stake_bp, FULL_STAKE_BP) * operating.get(stake.company_id, 0)
            )
            if share:
                entries.append(
                    LedgerEntry.transfer(
                        turn=state.turn,
                        company_id=stake.owner_id,
                        memo=f"Share of {name}'s result",
                        debit=ASSOCIATES,
                        credit=ASSOCIATES_PROFIT,
                        amount=share,
                    )
                )
                state = with_stake(
                    state, replace(stake, carrying_cents=stake.carrying_cents + share)
                )
        elif december and state.company(stake.company_id).alive:
            fair = fair_value_cents(state, stake, balances, balance, data)
            moved = fair - stake.carrying_cents
            if moved:
                entries.append(
                    LedgerEntry.transfer(
                        turn=state.turn,
                        company_id=stake.owner_id,
                        memo=f"Fair value of {name}",
                        debit=FINANCIAL_INVESTMENTS,
                        credit=FAIR_VALUE,
                        amount=moved,
                    )
                )
                state = with_stake(state, replace(stake, carrying_cents=fair))
    return state, tuple(entries)
