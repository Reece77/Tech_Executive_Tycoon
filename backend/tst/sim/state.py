"""Immutable game state. Cash is never a field: it is derived from ledger balances (ADR-0003)."""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.money import Cents


@dataclass(frozen=True, slots=True)
class SaveMeta:
    name: str
    master_seed: int
    scenario_id: str
    difficulty: str


@dataclass(frozen=True, slots=True)
class CompanyState:
    id: int
    name: str
    is_player: bool
    stage: int  # spec section 3: 0 solo founder .. 5 conglomerate
    founded_turn: int


@dataclass(frozen=True, slots=True)
class GameState:
    save_meta: SaveMeta
    turn: int  # the next turn to be played; 0 = January 2010
    companies: tuple[CompanyState, ...]  # sorted by id

    def company(self, company_id: int) -> CompanyState:
        for company in self.companies:
            if company.id == company_id:
                return company
        raise KeyError(company_id)

    @property
    def player(self) -> CompanyState:
        for company in self.companies:
            if company.is_player:
                return company
        raise LookupError("game state has no player company")


def company_cash(balances: LedgerBalances, company_id: int) -> Cents:
    """Cash for a company is the balance of its 1000_cash account."""
    return account_balance(balances, company_id, CASH)
