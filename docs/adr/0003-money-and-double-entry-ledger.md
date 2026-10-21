# ADR-0003: Money as integer cents; double-entry ledger

- Status: Accepted
- Date: 2026-10-20
- Spec sections: §10, §15

## Context

The game needs a P&L, balance sheet, cash flow statement, and cap table that always reconcile, across subsidiaries later. Floating-point money drifts, and single-entry cash changes cannot produce a balance sheet.

## Decision

- All money is `int` cents (USD). Type alias `Cents = int` in `tst/sim/money.py`. Helpers: `cents(dollars: str | int)`, `pct_of(amount: Cents, basis_points: int) -> Cents` (round half to even).
- Percentages and rates in balance data are expressed in basis points (`int`) where they multiply money.
- Every change to any account is a `LedgerEntry` with two or more `LedgerLine`s whose signed amounts sum to zero:

  ```python
  @dataclass(frozen=True, slots=True)
  class LedgerLine:
      account: AccountCode  # e.g. "1000_cash", "6000_salaries"
      amount: Cents         # debit positive, credit negative

  @dataclass(frozen=True, slots=True)
  class LedgerEntry:
      turn: int
      company_id: int
      memo: str
      lines: tuple[LedgerLine, ...]
  ```

- A minimal chart of accounts lives in `backend/data/accounts.yaml` (cash, receivables, prepaid, PP&E, payables, accrued payroll, debt, SAFEs, common and preferred equity, revenue lines, COGS, salaries, benefits, rent, compute, marketing, R&D, G&A, interest, tax).
- Company cash shown anywhere is derived from the ledger balance of `1000_cash`, cached per turn in `turn_snapshot`, never stored as a mutable field that code updates directly.

## Consequences

- Statements are queries over ledger lines, so they reconcile by construction.
- Property test: for every entry, `sum(line.amount) == 0`; for every turn, assets = liabilities + equity.
- Intercompany transactions (v3) work naturally with per-entity books.

## Alternatives considered

- `Decimal`: correct but slower and easy to mix with floats by mistake.
- Single cash field updated in place: simple, but cannot produce a balance sheet and hides bugs.
