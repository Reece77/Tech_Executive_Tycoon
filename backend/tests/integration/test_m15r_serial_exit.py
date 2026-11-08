"""M15r (Codex review 4, findings 1 and 4): a sale after a takeover bid settles the buyer's
side once, through the brand-closing path, and the delisting persists. Played on a real save:
accept the bid, found again, advance, then reload cold and reconcile every ledger."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import select

from tst.db.models import LedgerEntryRow, PublicCompanyRow, ShareMonthRow
from tst.db.repository import ledger_balances, open_session, run_action, run_turn
from tst.db.state_io import live_view, load_state
from tst.loader import LoadedData
from tst.sim.actions.events import ChooseEvent
from tst.sim.ledger import CASH, GOODWILL, INVESTMENT_SUBSIDIARIES
from tst.sim.mna.exit import buyer_of, sale_of
from tst.sim.modes.serial import FoundAgain, proceeds_cents
from tst.sim.state import GameState, ceo_of, public_of

TOOLS = Path(__file__).resolve().parents[3] / "tools"
OLD = 1  # the player's first company


@dataclass(frozen=True)
class Played:
    path: Path
    before: GameState  # the month the bid is open, before accepting it
    sold: GameState  # after accepting
    warm: GameState  # after founding again, as the action returned it
    opening: dict[tuple[int, str], int]  # ledger balances before accepting


def _exit_offer(save_dir: Path, loaded: LoadedData) -> Path:
    sys.path.insert(0, str(TOOLS))
    from e2e_m14_save import exit_offer

    return exit_offer(save_dir, "m15r", loaded)


def _load(path: Path) -> GameState:
    with open_session(path) as session:
        return load_state(session)


def _balances(path: Path) -> dict[tuple[int, str], int]:
    with open_session(path) as session:
        return ledger_balances(session)


@pytest.fixture
def played(tmp_path: Path, loaded: LoadedData, monkeypatch: pytest.MonkeyPatch) -> Iterator[Played]:
    monkeypatch.setenv("TST_STATE_CACHE_CHECK", "1")
    path = _exit_offer(tmp_path, loaded)
    before = _load(path)
    opening = _balances(path)
    founder = before.founder_of(OLD)
    assert founder is not None
    (offer,) = [e for e in before.open_events(OLD) if e.template_id == "takeover_offer"]
    sold = run_action(path, loaded, ChooseEvent(founder.id, offer.id, "A")).new_state
    assert sold.save_meta.game_state == "exit"
    warm = run_action(path, loaded, FoundAgain(founder.id, "Second Act")).new_state
    yield Played(path, before, sold, warm, opening)


def _entries(path: Path, company_id: int, memo: str) -> list[LedgerEntryRow]:
    with open_session(path) as session:
        rows = session.scalars(
            select(LedgerEntryRow).where(
                LedgerEntryRow.company_id == company_id, LedgerEntryRow.memo == memo
            )
        ).all()
        for row in rows:
            _ = row.lines  # load the lines while the session is open
        return list(rows)


def test_the_buyer_pays_once_and_every_ledger_reconciles(
    played: Played, loaded: LoadedData
) -> None:
    sale = sale_of(played.sold, OLD)
    assert sale is not None
    buyer, price = sale.acquirer_id, sale.price_cents
    name = played.before.company(OLD).name
    for _ in range(2):
        run_turn(played.path, loaded)
    cold = _load(played.path)
    after = _balances(played.path)

    # one acquisition entry for the buyer: the price out of cash, the brand's book equity in
    # 1810 and the rest goodwill (28.3, 28.5's brand closing)
    (entry,) = _entries(played.path, buyer, f"Acquisition of {name}")
    lines = {line.account_code: line.amount_cents for line in entry.lines}
    assert lines[CASH] == -price
    assert lines.get(INVESTMENT_SUBSIDIARIES, 0) + lines.get(GOODWILL, 0) == price
    assert sum(lines.values()) == 0
    types = {a.code: a.type for a in loaded.game_data.accounts}
    equity = sum(
        amount
        for (cid, code), amount in played.opening.items()
        if cid == OLD and types[code] in ("asset", "liability")
    )
    assert lines.get(INVESTMENT_SUBSIDIARIES, 0) == equity

    # the acquisition record, persisted, and the brand is the buyer's
    (acquisition,) = [a for a in cold.acquisitions if a.target_id == OLD]
    assert (acquisition.deal_id, acquisition.acquirer_id) == (sale.id, buyer)
    assert acquisition.mode == "brand" and acquisition.price_cents == price
    assert cold.company(OLD).parent_id == buyer and not cold.company(OLD).is_player

    # the seller's own cash is untouched by a share sale; the new venture holds the proceeds
    assert _entries(played.path, OLD, f"Sold to {cold.company(buyer).name}") == []
    new = cold.player.id
    (start,) = _entries(played.path, new, "Starting cash from your exit")
    assert {x.account_code: x.amount_cents for x in start.lines}[CASH] == proceeds_cents(
        played.sold, OLD
    )

    # every entry in the save balances, and the buyer's books show the payment
    with open_session(played.path) as session:
        for row in session.scalars(select(LedgerEntryRow)):
            assert sum(x.amount_cents for x in row.lines) == 0, row.memo
    assert after[(buyer, GOODWILL)] - played.opening.get((buyer, GOODWILL), 0) == lines.get(
        GOODWILL, 0
    )


def test_a_buyer_that_cannot_pay_is_refused(loaded: LoadedData) -> None:
    from tests.unit.test_m13_public import listed
    from tst.sim.markets_public.public import apply_public_step

    state = listed()
    buyer = buyer_of(state)
    assert buyer is not None
    poor = {(buyer, CASH): 1_000_00}  # $1,000: far short of the price
    sold, entries, logs = apply_public_step(
        state, OLD, "takeover_accept", loaded.balance, loaded.game_data, poor
    )
    assert not sold.ended and sale_of(sold, OLD) is None and entries == []
    assert sold.acquisitions == state.acquisitions
    (item,) = logs
    assert item.template == "deal_update" and dict(item.params)["title"] == "The sale fell through"


def test_the_delisting_persists(played: Played) -> None:
    assert public_of(played.before, OLD) is not None
    assert public_of(played.warm, OLD) is None
    cold = _load(played.path)
    assert public_of(cold, OLD) is None and ceo_of(cold, OLD) is None
    assert cold == live_view(played.warm)  # warm and cold agree after the committed action
    assert cold.player.rival_key == (4, 1)  # the new venture's stable key persists (finding 9)
    with open_session(played.path) as session:
        assert session.get(PublicCompanyRow, OLD) is None
        months = session.scalars(select(ShareMonthRow).where(ShareMonthRow.company_id == OLD))
        assert list(months)  # the share-price history stays
