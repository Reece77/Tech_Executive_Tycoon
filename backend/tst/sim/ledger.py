"""Double-entry ledger (ADR-0003). Debits are positive, credits negative; every entry sums to 0."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final

from tst.sim.errors import UnbalancedEntryError
from tst.sim.money import Cents

type AccountCode = str
# (company_id, account) -> balance (ADR-0012).
type LedgerBalances = Mapping[tuple[int, AccountCode], Cents]

# Account codes the engine posts to. All must exist in data/accounts.yaml (checked by tests).
CASH: Final = "1000_cash"
COMMON_EQUITY: Final = "3000_common_equity"
PREFERRED_EQUITY: Final = "3100_preferred_equity"
GENERAL_ADMIN: Final = "6900_general_admin"
SALARIES: Final = "6000_salaries"
BENEFITS: Final = "6010_benefits"
RENT: Final = "6100_rent"
RECRUITING: Final = "6200_recruiting"
REVENUE_SUBSCRIPTIONS: Final = "4000_revenue_subscriptions"  # M3
COMPUTE: Final = "6300_compute"  # hosting (M3)
MARKETING: Final = "6400_marketing"  # M3
SAFES: Final = "2600_safes"  # SAFEs until they convert (M4)
OTHER_INCOME: Final = "4900_other_income"  # event cash gains (M6, 16.3)
RESEARCH: Final = "6500_research_development"  # localization (M9, 19.5)
ENGINE_ACCOUNTS: Final = (
    OTHER_INCOME,
    CASH,
    COMMON_EQUITY,
    PREFERRED_EQUITY,
    GENERAL_ADMIN,
    SALARIES,
    BENEFITS,
    RENT,
    RECRUITING,
    REVENUE_SUBSCRIPTIONS,
    COMPUTE,
    MARKETING,
    SAFES,
    RESEARCH,
)


@dataclass(frozen=True, slots=True)
class LedgerLine:
    account: AccountCode
    amount: Cents  # debit positive, credit negative
    division_id: int | None = None  # reporting dimension: None = corporate (M8, 18.1)


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    turn: int
    company_id: int
    memo: str
    lines: tuple[LedgerLine, ...]

    def __post_init__(self) -> None:
        if len(self.lines) < 2:
            raise UnbalancedEntryError(f"entry {self.memo!r} needs at least two lines")
        for line in self.lines:
            if isinstance(line.amount, bool) or not isinstance(line.amount, int):
                raise UnbalancedEntryError(
                    f"entry {self.memo!r}: amount for {line.account} must be int cents"
                )
        total = sum(line.amount for line in self.lines)
        if total != 0:
            raise UnbalancedEntryError(
                f"entry {self.memo!r} does not balance: lines sum to {total}"
            )

    @classmethod
    def transfer(
        cls,
        *,
        turn: int,
        company_id: int,
        memo: str,
        debit: AccountCode,
        credit: AccountCode,
        amount: Cents,
    ) -> LedgerEntry:
        """A two-line entry moving `amount` from the credit account to the debit account."""
        return cls(
            turn=turn,
            company_id=company_id,
            memo=memo,
            lines=(LedgerLine(debit, amount), LedgerLine(credit, -amount)),
        )


def apply_entries(
    balances: LedgerBalances, entries: Iterable[LedgerEntry]
) -> dict[tuple[int, AccountCode], Cents]:
    """Return a new balance mapping with the entries posted. The input is not modified."""
    result = dict(balances)
    for entry in entries:
        for line in entry.lines:
            key = (entry.company_id, line.account)
            result[key] = result.get(key, 0) + line.amount
    return result


def account_balance(balances: LedgerBalances, company_id: int, account: AccountCode) -> Cents:
    return balances.get((company_id, account), 0)
