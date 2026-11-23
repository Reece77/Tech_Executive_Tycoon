"""M43r finding 4 (Codex review 9): the conglomerate view and the shareholder letter count a
subsidiary's lines only while the group held it (formulas.md 31.1).

A subsidiary bought, sold and bought again has two runs; a sale it booked between them belonged
to someone else and reaches neither the API's figures nor the letter's facts. Runs that overlap
(the operating and holding-company paths to one company) count each entry once."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from tst.db import repository
from tst.db.models import LedgerEntryRow, LedgerLineRow, SaveMetaRow
from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.group.models import Ownership
from tst.sim.ledger import CASH
from tst.sim.state import GameState

REVENUE = "4000_revenue_subscriptions"
INSIDE_2011 = 1_111_111
GAP_2012 = 987_654_321  # the distinctive sale while someone else held it
INSIDE_2013 = 3_333_333


def _setup(loaded: LoadedData, tmp_path: Path) -> tuple[Path, int]:
    path = create_save(
        "gaps", 5, "funded_spinout", company_name="Group Co", data=loaded, save_dir=tmp_path
    )
    sub: dict[str, int] = {}

    def change(state: GameState) -> GameState:
        rival = min(c.id for c in state.companies if not c.is_player)
        sub["id"] = rival
        held = (
            Ownership(
                9001, rival, state.player.id, ym_to_turn(2011, 1), ym_to_turn(2012, 1),
                end_reason="sold",
            ),
            Ownership(9002, rival, state.player.id, ym_to_turn(2013, 1)),
        )  # fmt: skip
        return replace(state, ownerships=(*state.ownerships, *held), turn=ym_to_turn(2014, 2))

    with open_session(path) as session, session.begin():
        before = load_state(session)
        after = change(before)
        sync_state(session, before, after)
        meta = session.get(SaveMetaRow, 1)
        assert meta is not None
        meta.current_turn = after.turn
        for turn, cents in (
            (ym_to_turn(2011, 6), INSIDE_2011),
            (ym_to_turn(2012, 6), GAP_2012),
            (ym_to_turn(2013, 6), INSIDE_2013),
        ):
            entry = LedgerEntryRow(turn=turn, company_id=sub["id"], memo="Revenue: Widgets")
            entry.lines = [
                LedgerLineRow(account_code=CASH, amount_cents=cents),
                LedgerLineRow(account_code=REVENUE, amount_cents=-cents),
            ]
            session.add(entry)
    repository._LAST.clear()
    return path, sub["id"]


def test_a_gap_in_ownership_reaches_neither_the_view_nor_the_letter(
    loaded: LoadedData, tmp_path: Path
) -> None:
    from tst.api.app import create_app  # the API's import order

    create_app()
    from tst.api import conglomerate_views
    from tst.db.conglomerate import read_books
    from tst.events import letter

    path, sub = _setup(loaded, tmp_path)
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        b, _ = read_books(session, state, loaded)
        out = conglomerate_views.conglomerate_out(session, state, loaded)
    own = {y: b.company.get((sub, y)) for y in (2011, 2012, 2013)}
    assert own[2011] is not None and own[2011].revenue == INSIDE_2011
    assert own[2012] is None or own[2012].revenue == 0  # held by someone else that year
    assert own[2013] is not None and own[2013].revenue == INSIDE_2013
    player = state.player.id

    def player_revenue(year: int) -> int:
        f = b.company.get((player, year))
        return f.revenue if f is not None else 0

    assert b.group(2012).revenue == player_revenue(2012)  # the gap's sale is not the group's
    assert b.group(2011).revenue == player_revenue(2011) + INSIDE_2011  # once, not twice
    assert out.year == 2013
    assert out.group.revenue_cents == player_revenue(2013) + INSIDE_2013
    assert str(GAP_2012) not in out.model_dump_json()
    names = conglomerate_views.labels(loaded)
    _, lines = letter.facts(state, b, 2012, names)
    _, prompt = letter.prompt("The founder", state.player.name, 2012, lines)
    gap_dollars = f"{GAP_2012 // 100:,}"
    assert gap_dollars not in prompt and gap_dollars[:5] not in prompt


def test_overlapping_runs_count_once() -> None:
    from tst.db.conglomerate import coalesce

    assert coalesce([(13, 25), (20, None)]) == ((13, None),)
    assert coalesce([(13, 25), (37, None)]) == ((13, 25), (37, None))
    assert coalesce([(37, 40), (13, 25), (25, 30)]) == ((13, 30), (37, 40))
    assert coalesce([(13, None), (2, 5)]) == ((2, 5), (13, None))
