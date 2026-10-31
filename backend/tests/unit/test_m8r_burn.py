"""M8r finding 7 (Codex review 1, P3): burn is net cash used before financing (formulas.md
14.1): operating plus investing cash flow, never investor or loan money. A month with $10,000
of operating outflow and a $100,000 SAFE stores a burn of $10,000. Money the month already
spent before Continue (an event paid by answering it) counts too."""

from __future__ import annotations

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.decisions import Decisions
from tst.sim.ledger import CASH, GENERAL_ADMIN, LedgerEntry, apply_entries
from tst.sim.rng import RngFactory
from tst.sim.turn import TurnContext, snapshot_and_month_end_report

OPEX, SAFE = 1_000_000, 10_000_000
SAFES = "2600_safes"


def _burn(loaded: LoadedData, entries: tuple[LedgerEntry, ...], **prior: int) -> int:
    state = fresh_game(loaded)
    opening = {(1, CASH): 50_000_000}
    extra = {"prior_flow": {1: prior["prior"]}} if prior else {}
    ctx = TurnContext(
        state=state,
        decisions=Decisions(),
        rng=RngFactory(1),
        balance=loaded.balance,
        data=loaded.game_data,
        opening_balances=opening,
        balances=dict(opening),
        **extra,  # type: ignore[arg-type]
    ).post(*entries)
    out = snapshot_and_month_end_report(ctx)
    assert out.snapshot is not None
    return out.snapshot.for_company(1).monthly_burn_cents


def _entry(debit: str, credit: str, amount: int, memo: str) -> LedgerEntry:
    return LedgerEntry.transfer(
        turn=0, company_id=1, memo=memo, debit=debit, credit=credit, amount=amount
    )


def test_a_safe_does_not_hide_the_burn(loaded: LoadedData) -> None:
    entries = (
        _entry(GENERAL_ADMIN, CASH, OPEX, "Costs"),
        _entry(CASH, SAFES, SAFE, "SAFE"),
    )
    assert _burn(loaded, entries) == OPEX


def test_no_burn_when_operations_bring_cash_in(loaded: LoadedData) -> None:
    assert _burn(loaded, (_entry(CASH, "4000_revenue_subscriptions", OPEX, "Revenue"),)) == 0


def test_money_spent_before_continue_counts(loaded: LoadedData) -> None:
    """An event paid by answering it was posted before the turn: the repository passes the
    month's cash flow before financing so far."""
    entries = (_entry(GENERAL_ADMIN, CASH, OPEX, "Costs"),)
    assert _burn(loaded, entries, prior=-250_000) == OPEX + 250_000


def test_apply_entries_still_moves_cash(loaded: LoadedData) -> None:
    balances = apply_entries({(1, CASH): 0}, (_entry(CASH, SAFES, SAFE, "SAFE"),))
    assert balances[(1, CASH)] == SAFE
