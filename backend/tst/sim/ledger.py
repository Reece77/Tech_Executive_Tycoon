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

PERSONAL_DIGIT: Final = "9"  # M24 (32.2): personal-book codes; never in a company entry

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
DEBT: Final = "2500_debt"  # loans' principal owed (M10, 20.3)
INTEREST: Final = "7000_interest"  # interest and lenders' fees (M10, 20.3)
PPE: Final = "1500_ppe"  # facilities' capex as built (M12a, 22.2)
ACCUMULATED_DEPRECIATION: Final = "1510_accumulated_depreciation"  # contra-asset (M12a)
DEPRECIATION: Final = "6700_depreciation"  # facilities' depreciation and losses on sale (M12a)
RESEARCH: Final = "6500_research_development"  # localization (M9, 19.5); research (M11, 21.3)
LICENSE_REVENUE: Final = "4100_revenue_licenses"  # licence prices and royalties (M11, 21.5)
COGS: Final = "5000_cogs"  # hardware: bills of materials, chips and assembly at sale (M12b, 26.2)
GOODWILL: Final = "1800_goodwill"  # price - the target's book equity at closing (M14, 28.3)
INVESTMENT_SUBSIDIARIES: Final = "1810_investment_subsidiaries"  # kept brands (M14, 28.5)
LOBBYING: Final = "6950_lobbying"  # a company's lobbying by region (M24, 32.5)
DISPOSAL: Final = "4930_gain_on_disposal"  # a subsidiary leaving the group (M16, 31.1)
ASSOCIATES: Final = "1820_investment_associates"  # 20-50% stakes, equity method (M16, 31.3)
FINANCIAL_INVESTMENTS: Final = "1830_financial_investments"  # under 20%, fair value (M16, 31.3)
NCI: Final = "3500_non_controlling_interest"  # outside holders of subsidiaries (M16, 31.3)
ASSOCIATES_PROFIT: Final = "4910_share_of_associates"  # the group's share (M16, 31.3)
FAIR_VALUE: Final = "4920_fair_value_gains"  # December marks of financial investments (M16)
INTERCOMPANY_SALES: Final = "4300_intercompany_sales"  # at the transfer price (M16, 31.6)
INTERCOMPANY_PURCHASES: Final = "5900_intercompany_purchases"  # the other side (M16, 31.6)
NCI_SHARE: Final = "4990_nci_share_of_profit"  # outsiders' share, consolidated only (M16, 31.3)
PREPAID: Final = "1200_prepaid"  # offtake prepayments not yet drawn (M17, 33.3)
EXPLORATION: Final = "6600_exploration"  # exploration spending, expensed (M18, 34.2)
MATERIALS_SALES: Final = "4410_materials_sales"  # refined goods sold at spot or contract (M20)
FOUNDRY_SALES: Final = "4420_foundry_sales"  # own fabs' spare starts sold as slots (M21, 38.2)
MINERAL_PROPERTIES: Final = "1520_mineral_properties"  # mines' capitalized cost (M19, 35.2)
ARO: Final = "2610_asset_retirement_obligation"  # mines' reclamation provision (M19, 35.3)
COMMODITY_REVENUE: Final = "4400_revenue_commodities"  # mines' sales (M19, 35.3)
DEPLETION: Final = "6750_depletion"  # units-of-production depletion (M19, 35.3)
TARIFFS: Final = "5100_tariffs"  # tariffs on goods crossing blocs (M22, 39.3)
LOCAL_PARTNER_SHARE: Final = "5110_local_partner_share"  # a local partner's share (M22, 39.3)
ROYALTIES: Final = "6960_royalties"  # host governments' royalties, state shares (M19, 35.3)
ENGINE_ACCOUNTS: Final = (
    DEBT,
    INTEREST,
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
    PPE,
    ACCUMULATED_DEPRECIATION,
    DEPRECIATION,
    LICENSE_REVENUE,
    GOODWILL,
    INVESTMENT_SUBSIDIARIES,
    LOBBYING,
    DISPOSAL,
    ASSOCIATES,
    FINANCIAL_INVESTMENTS,
    NCI,
    ASSOCIATES_PROFIT,
    FAIR_VALUE,
    NCI_SHARE,
    INTERCOMPANY_SALES,
    INTERCOMPANY_PURCHASES,
    PREPAID,
    EXPLORATION,
    MATERIALS_SALES,
    FOUNDRY_SALES,
    MINERAL_PROPERTIES,
    ARO,
    COMMODITY_REVENUE,
    DEPLETION,
    ROYALTIES,
    TARIFFS,
    LOCAL_PARTNER_SHARE,
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
            if line.account[0] == PERSONAL_DIGIT:  # M24 (32.2): the founder's book is apart
                raise UnbalancedEntryError(
                    f"entry {self.memo!r}: {line.account} is a personal account, not a company's"
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
