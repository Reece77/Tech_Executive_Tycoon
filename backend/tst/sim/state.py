"""Immutable game state. Cash is never a field: it is derived from ledger balances (ADR-0003)."""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.money import Cents
from tst.sim.people.models import Employment, Person, RevealState


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
    people: tuple[Person, ...] = ()  # sorted by id
    employments: tuple[Employment, ...] = ()  # sorted by id
    reveals: tuple[RevealState, ...] = ()  # sorted by (observer_company_id, person_id)

    def company(self, company_id: int) -> CompanyState:
        for company in self.companies:
            if company.id == company_id:
                return company
        raise KeyError(company_id)

    def person(self, person_id: int) -> Person:
        for person in self.people:
            if person.id == person_id:
                return person
        raise KeyError(person_id)

    def staff(self, company_id: int) -> tuple[Employment, ...]:
        """Active and notice employments of a company, by employment id."""
        return tuple(
            e for e in self.employments if e.company_id == company_id and e.counts_as_staff
        )

    def reveal(self, observer_company_id: int, person_id: int) -> RevealState | None:
        for rev in self.reveals:
            if rev.observer_company_id == observer_company_id and rev.person_id == person_id:
                return rev
        return None

    @property
    def player(self) -> CompanyState:
        for company in self.companies:
            if company.is_player:
                return company
        raise LookupError("game state has no player company")


def company_cash(balances: LedgerBalances, company_id: int) -> Cents:
    """Cash for a company is the balance of its 1000_cash account."""
    return account_balance(balances, company_id, CASH)
