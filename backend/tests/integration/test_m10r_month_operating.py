"""M10r finding 1 through a save: a lender's fee posted before Continue (as answering the
lender event posts it) is interest. The stored operating month equals the P&L of every line
the month posted, and the repository's month so far classifies by account (14.1, 20.3)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from tests.helpers import fund_save
from tst.db import repository
from tst.db.mappers import entry_to_row
from tst.db.models import LedgerEntryRow, LedgerLineRow
from tst.loader import LoadedData
from tst.sim.finance.statements import profit_and_loss
from tst.sim.ledger import CASH, GENERAL_ADMIN, INTEREST, LedgerEntry

FEE, COSTS = 1_000_000, 250_000


def test_a_fee_before_continue_stays_below_operating(loaded: LoadedData, tmp_path: Path) -> None:
    path = repository.create_save(
        "fee", 42, "garage_bootstrap", company_name="Kestrel", data=loaded, save_dir=tmp_path
    )
    fund_save(path, 100_000_000)
    with repository.open_session(path) as session:
        turn = repository.load_state(session).turn
    fee = LedgerEntry.transfer(
        turn=turn, company_id=1, memo="Event: waiver", debit=INTEREST, credit=CASH, amount=FEE
    )
    cost = LedgerEntry.transfer(
        turn=turn, company_id=1, memo="Event: costs", debit=GENERAL_ADMIN, credit=CASH, amount=COSTS
    )
    with repository.open_session(path) as session, session.begin():
        session.add(entry_to_row(fee))
        session.add(entry_to_row(cost))
    with repository.open_session(path) as session:
        assert repository.month_operating_so_far(session, turn, loaded)[1] == -COSTS
        assert repository.month_flow_so_far(session, turn, loaded)[1] < -COSTS  # burn: both
    repository.run_turn(path, loaded)
    types = {a.code: a.type for a in loaded.game_data.accounts}
    with repository.open_session(path) as session:
        rows = session.execute(
            select(LedgerLineRow.account_code, LedgerLineRow.amount_cents)
            .join(LedgerLineRow.entry)
            .where(LedgerEntryRow.turn == turn, LedgerEntryRow.company_id == 1)
        ).all()
        state = repository.load_state(session)
    pnl = profit_and_loss([(turn, str(a), int(m)) for a, m in rows], types, turn, turn)
    assert pnl.interest >= FEE
    assert state.player.op_history[-1] == pnl.operating_result
