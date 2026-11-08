"""M16 sub-task 3 (formulas.md 31.2): forming a holding company on a real save. The new
company takes the listing, the cap table and the board; the operating company and both kept
brands become its subsidiaries; the group's consolidated statements balance; the warm and the
cold state agree."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tst.api import finance_views
from tst.db import repository
from tst.db.repository import ledger_balances, open_session, run_action, run_turn
from tst.db.state_io import load_state
from tst.loader import LoadedData
from tst.sim.errors import GroupRuleError
from tst.sim.finance.captable import fd_shares, person_shares
from tst.sim.group.holding import FormHolding, gate
from tst.sim.ledger import CASH
from tst.sim.state import (
    GameState,
    group_companies,
    group_members,
    holding_of,
    listed_id,
    owner_of,
    public_of,
)

TOOLS = Path(__file__).resolve().parents[3] / "tools"
FOUNDER = 1


def _load(path: Path) -> GameState:
    with open_session(path) as session:
        return load_state(session)


@dataclass(frozen=True)
class Formed:
    path: Path
    before: GameState
    after: GameState


@pytest.fixture(scope="module")
def formed(tmp_path_factory: pytest.TempPathFactory, loaded: LoadedData) -> Iterator[Formed]:
    sys.path.insert(0, str(TOOLS))
    from e2e_m16_save import eligible

    mp = pytest.MonkeyPatch()
    mp.setenv("TST_STATE_CACHE_CHECK", "1")
    path = eligible(tmp_path_factory.mktemp("m16"), "m16", loaded)
    before = _load(path)
    after = run_action(path, loaded, FormHolding(FOUNDER)).new_state
    yield Formed(path, before, after)
    mp.undo()


def test_the_gate_opens_with_a_listing_and_two_brands(formed: Formed, loaded: LoadedData) -> None:
    assert gate(formed.before, loaded.balance) == []
    assert len(group_companies(formed.before, 1)) == 3  # the company and its two brands
    assert gate(formed.after, loaded.balance) == ["a holding company is already formed"]
    with pytest.raises(GroupRuleError):
        run_action(formed.path, loaded, FormHolding(FOUNDER))


def test_the_holding_takes_the_listing_cap_table_and_board(formed: Formed) -> None:
    before, after = formed.before, formed.after
    held = holding_of(after)
    assert held is not None and held.operating_id == 1 and held.chair_id == FOUNDER
    hid = held.company_id
    assert after.company(hid).name == "Kestrel Holdings" and after.company(hid).stage == 5
    assert after.player.id == 1 and listed_id(after) == hid
    assert public_of(after, 1) is None
    public = public_of(after, hid)
    assert public is not None and public.price_cents == public_of(before, 1).price_cents  # type: ignore[union-attr]
    # every holder but the option pool swapped one for one
    founder_shares = person_shares(before, 1, FOUNDER)
    assert person_shares(after, hid, FOUNDER) == founder_shares > 0
    assert person_shares(after, 1, FOUNDER) == 0
    stake = [e for e in after.company_cap(1) if e.holder_kind == "group"]
    assert len(stake) == 1 and stake[0].name == "Kestrel Holdings"
    assert fd_shares(after, 1) == fd_shares(before, 1)
    assert after.board(hid) and not after.board(1)
    assert after.founder_of(hid) is not None and after.founder_of(hid).id == FOUNDER  # type: ignore[union-attr]


def test_the_operating_company_and_brands_are_its_subsidiaries(formed: Formed) -> None:
    after = formed.after
    hid = listed_id(after)
    brands = [c.id for c in group_companies(formed.before, 1)[1:]]
    assert {c.id for c in group_companies(after, hid)} == {hid, 1, *brands}
    for cid in (1, *brands):
        assert owner_of(after, cid) == hid and after.company(cid).parent_id == hid
    members = {m.company_id: m for m in group_members(after, hid)}
    assert all(members[c].depth == 1 and members[c].common_control for c in (1, *brands))


def test_the_group_plays_on_balanced_and_reloads_cold(formed: Formed, loaded: LoadedData) -> None:
    path = formed.path
    hid = listed_id(formed.after)
    for _ in range(3):
        run_turn(path, loaded)
    state = _load(path)
    assert holding_of(state) is not None
    public = public_of(state, hid)
    assert public is not None and public.price_cents > 0
    assert len(state.company(hid).mrr_history) >= 3 and state.company(hid).mrr_history[-1] > 0
    with open_session(path) as session:
        balances = ledger_balances(session)
        lines = repository.ledger_lines(session, hid)
        members = group_members(state, hid)
        books = {m.company_id: repository.ledger_lines(session, m.company_id) for m in members}
    out = finance_views.statements_out(
        state, lines, "month", loaded, [(m, books[m.company_id]) for m in members]
    )
    assert balances.get((hid, CASH), 0) >= 0  # the operating company pays up the office
    assert out.consolidated
    for p in out.periods:
        sheet = p.balance_sheet
        assert sheet.total_assets_cents == sheet.total_liabilities_and_equity_cents, p.label
    last = out.periods[-1]
    cash = sum(balances.get((c, CASH), 0) for c in (hid, *books))
    assert {x.account: x.amount_cents for x in last.balance_sheet.assets}[CASH] == cash


def test_a_spin_off_becomes_an_independent_listed_company(
    tmp_path: Path, loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    """31.5: the shares go to the holding company's shareholders; it trades as a listed rival;
    the group keeps 10% at fair value; the founder holds their part in their own name; the
    group's statements still balance and no longer consolidate it."""
    from tst.sim.group.capital import SpinOff
    from tst.sim.mna import valuation

    monkeypatch.setenv("TST_STATE_CACHE_CHECK", "1")
    sys.path.insert(0, str(TOOLS))
    from e2e_m16_save import formed as make_formed

    path = make_formed(tmp_path, "spin", loaded)
    state = _load(path)
    hid = listed_id(state)
    brand = next(c.id for c in group_companies(state, hid)[1:] if c.id != 1)
    with pytest.raises(GroupRuleError):
        run_action(path, loaded, SpinOff(FOUNDER, brand, keep_bp=2_500))  # 19.9% at most
    after = run_action(path, loaded, SpinOff(FOUNDER, brand, keep_bp=1_000)).new_state
    company = after.company(brand)
    assert company.parent_id is None and company.alive and not company.is_player
    assert valuation.is_listed(after, brand, loaded.game_data)
    assert brand not in {c.id for c in group_companies(after, hid)}
    (kept,) = [x for x in after.stakes if x.company_id == brand]
    assert kept.kind == "retained" and kept.stake_bp == 1_000 and kept.owner_id == hid
    (mine,) = [x for x in after.personal_stakes if x.company_id == brand]
    assert mine.person_id == FOUNDER and 0 < mine.stake_bp < 9_000
    run_turn(path, loaded)
    state = _load(path)
    cap = valuation.market_cap_cents(state, brand, {}, loaded.balance, loaded.game_data)
    assert cap is not None and cap > 0
    with open_session(path) as session:
        lines = repository.ledger_lines(session, hid)
        members = group_members(state, hid)
        books = {m.company_id: repository.ledger_lines(session, m.company_id) for m in members}
    out = finance_views.statements_out(
        state, lines, "month", loaded, [(m, books[m.company_id]) for m in members]
    )
    for p in out.periods:
        s = p.balance_sheet
        assert s.total_assets_cents == s.total_liabilities_and_equity_cents, p.label


def test_upgrading_to_0039_backfills_each_brands_holding(
    tmp_path: Path, loaded: LoadedData
) -> None:
    """Migration 0039 on a save from before M16: each kept brand gets an open holding from its
    closing by its parent, with the 1810 the parent posted at closing and the brand's equity
    then, as the engine records them."""
    from tst.db import migrate

    sys.path.insert(0, str(TOOLS))
    from e2e_m16_save import eligible

    path = eligible(tmp_path, "upgrade", loaded)
    recorded = {o.company_id: o for o in _load(path).ownerships}
    assert len(recorded) == 2
    migrate.downgrade(path, "0038_m15r")
    migrate.ensure_current(path)
    state = _load(path)
    upgraded = {o.company_id: o for o in state.ownerships}
    assert set(upgraded) == set(recorded)
    for cid, o in recorded.items():
        u = upgraded[cid]
        assert (u.owner_id, u.from_turn, u.to_turn) == (o.owner_id, o.from_turn, None)
        assert (u.book_cents, u.equity_cents) == (o.book_cents, o.equity_cents)
    assert gate(state, loaded.balance) == []


def test_the_saves_list_reads_a_save_with_a_holding_company(formed: Formed) -> None:
    """Two player companies in one save (the operating company and its holding): the saves
    index names the operating company (it was `.one()` and the saves list failed)."""
    from tst.db.repository import list_saves, summarize

    assert summarize(formed.path).company_name == "Kestrel"  # it raised: two rows for .one()
    (formed.path.parent / "index.json").unlink(missing_ok=True)  # rebuilt from the files
    saves = list_saves(formed.path.parent)
    assert [(s.slug, s.company_name) for s in saves] == [("m16", "Kestrel")]
