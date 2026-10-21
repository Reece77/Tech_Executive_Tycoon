# ADR-0012: Turn function signature

- Status: Accepted. Amends the signature in ADR-0002 §1; the rest of ADR-0002 stands.
- Date: 2026-10-20
- Spec sections: §4, §14

## Context

ADR-0002 gave `advance_turn` four inputs and a result of `(new_state, ledger_entries, log_items, event_requests)`. The M0 brief added a `ledger_balances` input and a `snapshot` output. Claude Code asked which to follow. Both additions are needed:

- Cash is derived from the ledger (ADR-0003), and the pure sim cannot query the database, so the caller must pass in account balances.
- The month-end KPI snapshot (ADR-0004 §6) is computed by the sim and persisted by the caller.
- Event requests are still needed from M6 onward.

## Decision

```python
LedgerBalances = Mapping[tuple[int, AccountCode], Cents]   # (company_id, account) -> balance at start of turn

@dataclass(frozen=True, slots=True)
class TurnResult:
    new_state: GameState
    ledger_entries: tuple[LedgerEntry, ...]
    log_items: tuple[LogItem, ...]
    snapshot: TurnSnapshot                   # per-company KPIs for turn_snapshot
    event_requests: tuple[EventRequest, ...] # always empty until M6

def advance_turn(
    state: GameState,
    decisions: Decisions,
    rng: RngFactory,
    balance: Balance,
    ledger_balances: LedgerBalances,
) -> TurnResult: ...
```

- The caller (`tst.db.run_turn`) supplies `ledger_balances` from the database at the start of the turn.
- Inside the turn, phases that need cash use the starting balances plus the entries posted earlier in the same turn (a running in-memory total), never a database read.
- In M0, `EventRequest` is an empty frozen dataclass and phase 12 returns no requests.
- `GameData` (seed data, ADR-0008) joins the inputs in M1a as a sixth argument, `data: GameData`, placed after `balance`.

## Consequences

- The M0 brief and ADR-0002 now agree with this ADR.
- Adding a field to `TurnResult` later requires amending this ADR.

## Alternatives considered

- Store cash on `CompanyState`: contradicts ADR-0003 (cash is derived from the ledger).
- Let the sim read balances from a repository interface: breaks purity (ADR-0002).
