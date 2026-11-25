"""The conglomerate view's figures (M43 sub-task 2): a group's revenue, gross margin, operating
profit, capital employed and capital spending by industry, by company and by year, derived from
the ledger. Like the division statements (18.1) they add no state and move no cash; the view is
read-only and every figure is one the player's own books show.

- **Industries** (`conglomerate.industries`): a product category, a facility kind, power plants,
  mines and a few revenue accounts (foundry, energy, materials) each belong to one industry.
- **Lines:** a ledger line is the industry's when its memo names one of the company's products,
  facilities, plants or mines (the longest name it contains), or when its revenue account is
  listed. Every other operating line of the company is **shared**: it is split across the
  company's industries by their external revenue that year (largest remainders, so cents add
  up). A company with no industry revenue that year (a holding company) keeps its shared lines
  as **corporate**.
- **Revenue** is external: intercompany sales and purchases (31.6) are left out of the
  industries and kept in each company's own row, so industries add up to the group.
- **Capital employed** at a year end is the company's assets (less its investment in group
  companies, whose own capital counts) less its liabilities other than debt and SAFEs. A
  facility's, plant's or mine's book value (the asset lines that name it) is its industry's;
  the rest is split as shared lines are.
- **Capital spending** each year: additions to property, mineral properties and tool stock by
  industry (corporate when no industry is named, an office fit-out), the cash deals paid
  (acquisitions, stakes, venture rounds, minorities), and the listed entity's dividends and
  buybacks.
"""

from __future__ import annotations

import itertools
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from tst.sim.group.conglomerate_config import ConglomerateBalance

REVENUE_PREFIX: Final = "4"
COST_OF_REVENUE_PREFIX: Final = "5"
OPERATING_COST_PREFIX: Final = "6"
INTERCOMPANY_SALES: Final = "4300_intercompany_sales"
INTERCOMPANY: Final = frozenset({INTERCOMPANY_SALES, "5900_intercompany_purchases"})
# below the operating line (31.3, 31.1): associates, fair-value marks, disposals, outside holders
BELOW_OPERATING: Final = frozenset(
    {
        "4910_share_of_associates",
        "4920_fair_value_gains",
        "4930_gain_on_disposal",
        "4990_nci_share_of_profit",
    }
)
DEBT: Final = frozenset({"2500_debt", "2600_safes"})
CAPEX: Final = frozenset(
    {"1500_ppe", "1520_mineral_properties", "1530_tool_inventory", "1540_spectrum_licences"}
)  # M53: spectrum is a network's investment
FIXED: Final = CAPEX | {"1510_accumulated_depreciation"}  # book values a memo can name
IN_GROUP: Final = "1810_investment_subsidiaries"  # a parent's claim on a member: counted once
RETURNED_MEMOS: Final = ("Dividend:", "Buyback:")  # the listed entity's own (25.5)
CASH: Final = "1000_cash"
# the cash a deal pays (28.3, 31.3, 31.4): acquisitions, stakes, venture rounds, minorities
DEAL_MEMOS: Final = (
    "Acquisition of",
    "Venture investment in",
    "Shares of",
    "Bought out the minorities of",
)
EQUITY_PREFIX: Final = "3"
CORPORATE: Final = "corporate"  # the key of a company's unshared lines (no industry revenue)


@dataclass(frozen=True, slots=True)
class LineSum:
    """The ledger lines of one company, year, account and memo, summed (debit positive)."""

    company_id: int
    year: int
    account: str
    memo: str
    cents: int


@dataclass(slots=True)
class Figures:
    revenue: int = 0
    cost_of_revenue: int = 0
    operating_costs: int = 0
    capital_employed: int = 0  # at the year end
    capex: int = 0

    @property
    def gross_profit(self) -> int:
        return self.revenue - self.cost_of_revenue

    @property
    def operating_profit(self) -> int:
        return self.gross_profit - self.operating_costs

    @property
    def gross_margin(self) -> float | None:
        # money-exact: ratio: a margin shown as a percentage, never posted
        return self.gross_profit / self.revenue if self.revenue > 0 else None

    @property
    def operating_margin(self) -> float | None:
        # money-exact: ratio: a margin shown as a percentage, never posted
        return self.operating_profit / self.revenue if self.revenue > 0 else None

    @property
    def return_on_capital(self) -> float | None:
        if self.capital_employed <= 0:
            return None
        return self.operating_profit / self.capital_employed

    def add(self, other: Figures) -> None:
        self.revenue += other.revenue
        self.cost_of_revenue += other.cost_of_revenue
        self.operating_costs += other.operating_costs
        self.capital_employed += other.capital_employed
        self.capex += other.capex


@dataclass(slots=True)
class Uses:
    """Where a year's capital went."""

    capex: dict[str, int] = field(default_factory=dict)  # by industry (or CORPORATE)
    stakes: int = 0  # acquisitions, stakes and goodwill
    returned: int = 0  # dividends and buybacks


@dataclass(frozen=True, slots=True)
class Books:
    """Every figure of the view, by (year, company, industry); industry CORPORATE for the lines
    of a company that had no industry revenue that year. `company` holds each company's own
    year with its intercompany lines (its statement as a company)."""

    cells: Mapping[tuple[int, int, str], Figures]
    company: Mapping[tuple[int, int], Figures]
    uses: Mapping[int, Uses]
    years: tuple[int, ...]
    intercompany: Mapping[tuple[int, int], int] = field(default_factory=dict)  # its sales

    def by_industry(self, year: int) -> dict[str, Figures]:
        out: dict[str, Figures] = defaultdict(Figures)
        for (y, _, industry), f in self.cells.items():
            if y == year:
                out[industry].add(f)
        return dict(out)

    def group(self, year: int) -> Figures:
        total = Figures()
        for f in self.by_industry(year).values():
            total.add(f)
        return total


def industry_maps(
    config: ConglomerateBalance,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], str, str]:
    """(category -> industry, facility kind -> industry, account -> industry, plants', mines')."""
    categories = {c: i.key for i in config.industries for c in i.categories}
    kinds = {k: i.key for i in config.industries for k in i.facility_kinds}
    accounts = {a: i.key for i in config.industries for a in i.accounts}
    plants = next(i.key for i in config.industries if i.plants)
    mines = next(i.key for i in config.industries if i.mines)
    return categories, kinds, accounts, plants, mines


class Namer:
    """The industry a memo names, from each company's names (longest match, cached)."""

    def __init__(self, names: Mapping[int, Mapping[str, str]]) -> None:
        self._names = {
            cid: sorted(by.items(), key=lambda kv: (-len(kv[0]), kv[0]))
            for cid, by in names.items()
        }
        self._cache: dict[tuple[int, str], str | None] = {}

    def industry(self, company_id: int, memo: str) -> str | None:
        key = (company_id, memo)
        if key not in self._cache:
            self._cache[key] = next(
                (ind for name, ind in self._names.get(company_id, ()) if name and name in memo),
                None,
            )
        return self._cache[key]


def split(total: int, weights: Mapping[str, int]) -> dict[str, int]:
    """`total` cents in proportion to positive `weights`, largest remainders (sums exactly)."""
    pos = {k: w for k, w in weights.items() if w > 0}
    whole = sum(pos.values())
    if not pos or whole <= 0:
        return {}
    sign = -1 if total < 0 else 1
    amount = abs(total)
    floors = {k: amount * w // whole for k, w in pos.items()}
    left = amount - sum(floors.values())
    order = sorted(pos, key=lambda k: (-(amount * pos[k] % whole), k))
    for k in order[:left]:
        floors[k] += 1
    return {k: sign * v for k, v in floors.items()}


def _operating(account: str) -> bool:
    return (
        account[0] in (REVENUE_PREFIX, COST_OF_REVENUE_PREFIX, OPERATING_COST_PREFIX)
        and account not in BELOW_OPERATING
    )


def _put(f: Figures, account: str, cents: int) -> None:
    if account[0] == REVENUE_PREFIX:
        f.revenue -= cents  # revenue is a credit
    elif account[0] == COST_OF_REVENUE_PREFIX:
        f.cost_of_revenue += cents
    else:
        f.operating_costs += cents


def books(
    lines: Iterable[LineSum],
    names: Mapping[int, Mapping[str, str]],
    types: Mapping[str, str],
    config: ConglomerateBalance,
    interest_prefix: str,
    tax_prefix: str,
    root: int | None = None,
) -> Books:
    """The view's figures from the group companies' summed ledger lines. `names` maps each
    company's product, facility, plant and mine names to their industries; `types` each
    account's type. Interest and tax accounts (`interest_prefix`, `tax_prefix`) sit below the
    operating line (14.1, 20.3). Dividends and buybacks count as returned only for `root` (the
    listed entity; every company when None): a subsidiary's go to its parent."""
    _, _, accounts, _, _ = industry_maps(config)
    namer = Namer(names)
    by_year: dict[tuple[int, int], list[LineSum]] = defaultdict(list)
    for line in lines:
        by_year[(line.company_id, line.year)].append(line)
    years = tuple(sorted({y for _, y in by_year}))
    companies = sorted({c for c, _ in by_year})
    returns = set(companies) if root is None else {root}
    cells: dict[tuple[int, int, str], Figures] = {}
    company: dict[tuple[int, int], Figures] = {}
    uses: dict[int, Uses] = defaultdict(Uses)
    internal: dict[tuple[int, int], int] = defaultdict(int)
    for cid in companies:
        own_capital: dict[str, int] = defaultdict(int)  # cumulative book value by industry
        capital_total = 0  # cumulative capital employed
        for year in years:
            mine = by_year.get((cid, year), [])
            direct: dict[str, Figures] = defaultdict(Figures)
            shared: list[LineSum] = []
            own = Figures()
            for line in mine:
                acct, cents = line.account, line.cents
                kind = types.get(acct, "")
                if kind == "asset":
                    if acct != IN_GROUP:
                        capital_total += cents
                    ind = namer.industry(cid, line.memo) if acct in FIXED else None
                    if ind is not None:
                        own_capital[ind] += cents
                    if acct in CAPEX and cents > 0:
                        bucket = ind or CORPORATE
                        uses[year].capex[bucket] = uses[year].capex.get(bucket, 0) + cents
                        if ind is not None:
                            direct[ind].capex += cents
                    elif acct == CASH and cents < 0 and line.memo.startswith(DEAL_MEMOS):
                        uses[year].stakes -= cents
                    continue
                if kind == "liability":
                    if acct not in DEBT:
                        capital_total += cents  # a liability's credit lowers capital employed
                    continue
                if acct.startswith(EQUITY_PREFIX):
                    if cents > 0 and line.memo.startswith(RETURNED_MEMOS) and cid in returns:
                        uses[year].returned += cents
                    continue
                if acct.startswith((interest_prefix, tax_prefix)) or not _operating(acct):
                    continue
                _put(own, acct, cents)
                if acct in INTERCOMPANY:
                    if acct == INTERCOMPANY_SALES:
                        internal[(cid, year)] -= cents
                    continue
                ind = accounts.get(acct) or namer.industry(cid, line.memo)
                if ind is None:
                    shared.append(line)
                else:
                    _put(direct[ind], acct, cents)
            own.capital_employed = capital_total
            company[(cid, year)] = own
            weights = {k: f.revenue for k, f in direct.items()}
            if not any(w > 0 for w in weights.values()):
                corp = direct[CORPORATE]
                for line in shared:
                    _put(corp, line.account, line.cents)
            else:
                pooled: dict[str, int] = defaultdict(int)
                for line in shared:
                    pooled[line.account] += line.cents
                for acct, cents in sorted(pooled.items()):
                    for k, part in split(cents, weights).items():
                        _put(direct[k], acct, part)
            rest = capital_total - sum(own_capital.values())
            parts = split(rest, weights) if any(w > 0 for w in weights.values()) else {}
            for k, v in own_capital.items():
                direct[k].capital_employed += v
            if parts:
                for k, part in parts.items():
                    direct[k].capital_employed += part
            elif rest:
                direct[CORPORATE].capital_employed += rest
            for k, f in direct.items():
                cells[(year, cid, k)] = f
    return Books(
        cells=cells, company=company, uses=dict(uses), years=years, intercompany=dict(internal)
    )


def growth(revenues: Sequence[int]) -> list[float]:
    """Year-on-year revenue growth, where the earlier year had revenue."""
    return [b / a - 1 for a, b in itertools.pairwise(revenues) if a > 0]


def risk_word(revenues: Sequence[int], config: ConglomerateBalance) -> str:
    """The spread (population standard deviation) of the last `risk_years` of growth, as a
    word; "new" with under two years of growth."""
    g = growth(revenues)[-config.risk_years :]
    if len(g) < 2:  # tunable-exempt: a spread needs two values
        return "new"
    spread = statistics.pstdev(g)
    return next((w.word for w in config.risk_words if spread < w.below), config.risk_top_word)
