"""M16 sub-task 1 (formulas.md 31.1; Codex review 4 findings 2 and 3): group membership and
consolidation by period. Ownership history decides who was inside a group when; the ultimate
owner is found at any depth; a failed brand keeps its earlier periods and leaves with a
disposal; a sold parent brings its brands into the buyer's group."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

import pytest

from tests.helpers import fresh_game
from tests.unit.test_hiring_phases import Game, live
from tests.unit.test_mna_deals import BIG, _energy, _founder, _id, _reservation
from tst.loader import LoadedData
from tst.sim.actions import apply_action
from tst.sim.data_models import AccountType
from tst.sim.decisions import Decisions
from tst.sim.errors import GroupDataError
from tst.sim.finance import statements as fs
from tst.sim.finance.consolidation import Member, consolidated_lines
from tst.sim.finance.insolvency import fail_rival
from tst.sim.group.models import Ownership
from tst.sim.group.ownership import carrying_cents
from tst.sim.group.statements import members_input
from tst.sim.ledger import (
    CASH,
    COMMON_EQUITY,
    DISPOSAL,
    GOODWILL,
    INVESTMENT_SUBSIDIARIES,
    LedgerEntry,
    apply_entries,
)
from tst.sim.mna import antitrust
from tst.sim.mna.closing import settle
from tst.sim.mna.deals import BidForCompany
from tst.sim.mna.exit import buyer_of
from tst.sim.mna.models import Deal
from tst.sim.modes.serial import found_again
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    group_companies,
    group_members,
    owner_of,
    with_acquisition,
    with_company,
    with_ownership,
)
from tst.sim.turn import advance_turn

type Line = tuple[int, str, int]


def _types(loaded: LoadedData) -> dict[str, AccountType]:
    return {a.code: a.type for a in loaded.game_data.accounts}


# --- Codex review 4 finding 2, as reproduced: two brands, one fails --------------------------


def _codex_books() -> tuple[list[Line], list[Line], list[Line]]:
    """Codex's numbers: the parent raises 3,000 and pays 1,200 at turn 2 for two brands (800
    of investments, 400 of goodwill); each brand brought 400 of cash."""
    parent = [
        (0, CASH, 3000),
        (0, COMMON_EQUITY, -3000),
        (2, INVESTMENT_SUBSIDIARIES, 800),
        (2, GOODWILL, 400),
        (2, CASH, -1200),
    ]
    brand = [(0, CASH, 400), (0, COMMON_EQUITY, -400)]
    return parent, list(brand), list(brand)


def _sheet(lines: Sequence[Line], types: dict[str, AccountType], turn: int) -> fs.BalanceSheet:
    return fs.balance_sheet(lines, types, turn)


def test_codex_reproduction_a_failed_brand_keeps_earlier_statements(loaded: LoadedData) -> None:
    types = _types(loaded)
    parent, a, b = _codex_books()
    before = consolidated_lines(parent, [Member(a, 2), Member(b, 2)], types)
    sheet_before = _sheet(before, types, 2)
    assert sheet_before.total_assets == sheet_before.total_liabilities_and_equity == 3000
    # Brand A fails at turn 4 and is disposed of: its owner writes off its investment (400)
    # and the goodwill it paid for it (200).
    parent_after = [
        *parent,
        (4, INVESTMENT_SUBSIDIARIES, -400),
        (4, GOODWILL, -200),
        (4, DISPOSAL, 600),
    ]
    after = consolidated_lines(parent_after, [Member(a, 2, 4), Member(b, 2)], types)
    sheet = _sheet(after, types, 2)
    assert (sheet.total_assets, sheet.total_liabilities_and_equity) == (3000, 3000)
    assert sheet == sheet_before  # the historical turn-2 sheet does not move
    for turn in range(6):  # every turn balances: lines total zero, the sheet balances
        assert sum(x for t, _, x in after if t <= turn) == 0
        s = _sheet(after, types, turn)
        assert s.total_assets == s.total_liabilities_and_equity
    end = _sheet(after, types, 5)
    assert end.assets.get(CASH) == 3000 - 1200 + 400  # A's cash left with it
    assert end.assets.get(GOODWILL) == 200  # B's goodwill stays
    pnl = fs.profit_and_loss(after, types, 4, 4)
    assert pnl.other_gains == {DISPOSAL: -600}  # the loss: A's net assets and goodwill
    assert pnl.operating_result == 0 and pnl.net_result == -600


def test_without_ownership_dates_the_old_selection_was_unbalanced(loaded: LoadedData) -> None:
    """The bug as Codex saw it: dropping the failed brand from every period while removing
    the parent's whole 1810 leaves turn 2 at 2,600 assets against 3,000."""
    types = _types(loaded)
    parent, _a, b = _codex_books()
    old = consolidated_lines(parent, [Member(b, 2)], types)
    sheet = _sheet(old, types, 2)
    assert (sheet.total_assets, sheet.total_liabilities_and_equity) == (2600, 3000)


# --- Codex review 4 finding 3, as reproduced: a nested chain -----------------------------------


def _chain(loaded: LoadedData) -> tuple[GameState, int, int, int, int]:
    """Root 4 owns former player 1 (bought at turn 6), which owns brands 2 and 3 (turn 3)."""
    state = fresh_game(loaded)
    rivals = [c.id for c in state.companies if not c.is_player][:3]
    root, b2, b3 = rivals[0], rivals[1], rivals[2]
    for cid, owner, turn in ((b2, 1, 3), (b3, 1, 3), (1, root, 6)):
        state = with_company(state, replace(state.company(cid), parent_id=owner))
        state = with_ownership(state, Ownership(0, cid, owner, turn))
    return state, root, 1, b2, b3


def test_codex_reproduction_a_nested_chain_counts_under_its_root(loaded: LoadedData) -> None:
    state, root, mid, b2, b3 = _chain(loaded)
    assert [c.id for c in group_companies(state, root)] == [root, mid, *sorted((b2, b3))]
    assert owner_of(state, b2) == owner_of(state, b3) == owner_of(state, mid) == root
    assert antitrust.owner_of(state, b2) == root
    # by period: before the root bought the middle company, its brands were the middle's
    assert owner_of(state, b2, turn=4) == mid
    assert [c.id for c in group_companies(state, root, turn=4)] == [root]
    assert {c.id for c in group_companies(state, mid, turn=4)} == {mid, b2, b3}
    members = {m.company_id: m for m in group_members(state, root)}
    assert (members[mid].depth, members[b2].depth) == (1, 2)
    assert members[b2].start == members[mid].start == 6  # they entered with their owner


def test_antitrust_counts_every_company_under_the_ultimate_owner(loaded: LoadedData) -> None:
    state, root, mid, b2, b3 = _chain(loaded)
    owners = antitrust.customers_by_market(state, loaded.balance, loaded.game_data)
    buckets = {o for market in owners.values() for o in market}
    assert not buckets & {mid, b2, b3}  # nothing counts outside the root's bucket
    flat = fresh_game(loaded)
    by_company: dict[int, float] = {}
    for market in antitrust.customers_by_market(flat, loaded.balance, loaded.game_data).values():
        for o, n in market.items():
            by_company[o] = by_company.get(o, 0.0) + n
    grouped = sum(n for market in owners.values() for o, n in market.items() if o == root)
    expected = sum(by_company.get(c, 0.0) for c in (root, mid, b2, b3))
    assert grouped == pytest.approx(expected)


def test_an_ownership_cycle_is_a_data_error(loaded: LoadedData) -> None:
    state, root, mid, _b2, _b3 = _chain(loaded)
    state = with_ownership(state, Ownership(0, root, mid, 7))
    with pytest.raises(GroupDataError):
        owner_of(state, mid)
    with pytest.raises(GroupDataError):
        group_members(state, root)


def test_a_nested_group_consolidates_each_company_once_and_balances(loaded: LoadedData) -> None:
    """Three levels by hand: root R buys A at turn 5 (A then owns B, bought at turn 2 for its
    book 300, and B has earned 100 since). The group replaces A's investment in B by B's net
    assets; B's profit before turn 5 is goodwill to the group, not its income."""
    types = _types(loaded)
    b = [
        (0, CASH, 300),
        (0, COMMON_EQUITY, -300),
        (4, CASH, 100),
        (4, "4000_revenue_subscriptions", -100),
        (7, CASH, 50),
        (7, "4000_revenue_subscriptions", -50),
    ]
    a = [
        (0, CASH, 1000),
        (0, COMMON_EQUITY, -1000),
        (2, INVESTMENT_SUBSIDIARIES, 300),
        (2, CASH, -300),
    ]
    r = [
        (0, CASH, 5000),
        (0, COMMON_EQUITY, -5000),
        (5, INVESTMENT_SUBSIDIARIES, 1000),  # A's book equity
        (5, GOODWILL, 200),
        (5, CASH, -1200),
    ]
    lines = consolidated_lines(
        r,
        [
            Member(a, 5, None, 5, 1000, -1000),
            Member(b, 5, None, 2, 300, -300),
        ],
        types,
    )
    for turn in range(9):
        assert sum(x for t, _, x in lines if t <= turn) == 0
        sheet = _sheet(lines, types, turn)
        assert sheet.total_assets == sheet.total_liabilities_and_equity
    sheet = _sheet(lines, types, 8)
    assert sheet.assets[CASH] == 5000 - 1200 + 700 + 400 + 50  # every company's cash once
    assert sheet.assets[GOODWILL] == 200 - 100  # B's pre-acquisition profit
    assert INVESTMENT_SUBSIDIARIES not in sheet.assets  # eliminated at every level
    assert fs.profit_and_loss(lines, types, 0, 8).total_revenue == 50  # only after turn 5


# --- Played through the engine -----------------------------------------------------------------


class Books(Game):
    """Game, keeping every ledger line by company: opening balances at turn 0 against equity."""

    def __init__(self, loaded: LoadedData, state: GameState, cash: int) -> None:
        super().__init__(loaded, state, cash=cash)
        self.lines: dict[int, list[Line]] = {}
        opening = dict(self.balances)
        for (cid, account), amount in opening.items():  # cash raised as equity, as new_game
            self.lines.setdefault(cid, []).extend(
                [(0, account, amount), (0, COMMON_EQUITY, -amount)]
            )
            key = (cid, COMMON_EQUITY)
            self.balances[key] = self.balances.get(key, 0) - amount

    def post(self, entries: Sequence[LedgerEntry]) -> None:
        for e in entries:
            self.lines.setdefault(e.company_id, []).extend(
                (e.turn, x.account, x.amount) for x in e.lines
            )
        self.balances = apply_entries(self.balances, entries)

    def act(self, action) -> None:  # type: ignore[no-untyped-def,override]
        self.seq += 1
        out = apply_action(
            self.state,
            action,
            self.rng,
            self.loaded.balance,
            self.loaded.game_data,
            self.balances,
            seq=self.seq,
        )
        self.state = out.new_state
        self.post(out.ledger_entries)

    def turn(self):  # type: ignore[no-untyped-def,override]
        result = advance_turn(
            self.state,
            Decisions(),
            self.rng,
            self.loaded.balance,
            self.loaded.game_data,
            self.balances,
        )
        self.post(result.ledger_entries)
        self.state = live(result.new_state)
        self.seq = 0
        return result

    def consolidated(self, root: int) -> list[Line]:
        members = members_input(group_members(self.state, root), self.lines)
        return consolidated_lines(self.lines.get(root, []), members, _types(self.loaded))


def _two_brands(loaded: LoadedData) -> tuple[Books, int, int]:
    game = Books(loaded, fresh_game(loaded, seed=3), cash=BIG)
    ids = []
    for name in ("Evernote", "GitHub"):
        target = _id(game.state, name)
        _energy(game)
        game.act(BidForCompany(_founder(game), target, _reservation(game, target), mode="brand"))  # type: ignore[arg-type]
        ids.append(target)
    game.turn()
    assert all(d.status == "closed" for d in game.state.deals)
    return game, ids[0], ids[1]


def _assert_balanced(game: Books, root: int) -> None:
    types = _types(game.loaded)
    lines = game.consolidated(root)
    for turn in range(game.state.turn):
        assert sum(x for t, _, x in lines if t <= turn) == 0, turn
        sheet = fs.balance_sheet(lines, types, turn)
        assert sheet.total_assets == sheet.total_liabilities_and_equity, turn


def test_a_brand_closing_records_its_holding(loaded: LoadedData) -> None:
    game, a, b = _two_brands(loaded)
    held = {o.company_id: o for o in game.state.ownerships}
    assert set(held) == {a, b}
    closed = {x.target_id: x.closed_turn for x in game.state.acquisitions}
    for cid, o in held.items():
        assert (o.owner_id, o.from_turn, o.to_turn) == (1, closed[cid], None)
    turn = next(iter(held.values())).from_turn
    posted = sum(x for t, acc, x in game.lines[1] if acc == INVESTMENT_SUBSIDIARIES and t == turn)
    assert sum(o.book_cents for o in held.values()) == posted  # the 1810 posted at closing


def test_a_failed_brand_leaves_with_a_disposal_and_history_stays(loaded: LoadedData) -> None:
    game, a, b = _two_brands(loaded)
    for _ in range(3):
        game.turn()
    types = _types(loaded)
    last = game.state.turn - 1
    sheets = {t: fs.balance_sheet(game.consolidated(1), types, t) for t in range(last + 1)}
    pnls = {t: fs.profit_and_loss(game.consolidated(1), types, t, t) for t in range(last + 1)}
    investment = game.balances[(1, INVESTMENT_SUBSIDIARIES)]
    state, _ = fail_rival(game.state, game.state.company(a), 1, 1)
    game.state = state
    game.turn()
    held = next(o for o in game.state.ownerships if o.company_id == a)
    assert (held.to_turn, held.end_reason) == (game.state.turn - 1, "failed")
    assert game.state.company(a).parent_id is None
    assert [c.id for c in group_companies(game.state, 1)] == [1, b]
    assert a in {c.id for c in group_companies(game.state, 1, turn=last)}  # its past stays
    # the parent wrote off its investment in A (and A's goodwill)
    assert game.balances[(1, INVESTMENT_SUBSIDIARIES)] < investment
    assert game.balances[(1, DISPOSAL)] > 0
    kept = next(o for o in game.state.ownerships if o.company_id == b)
    assert game.balances[(1, INVESTMENT_SUBSIDIARIES)] == carrying_cents(
        kept, game.balances, loaded.game_data
    )  # exactly B's investment is left
    lines = game.consolidated(1)
    for t in range(last + 1):  # earlier statements unchanged
        assert fs.balance_sheet(lines, types, t) == sheets[t], t
        assert fs.profit_and_loss(lines, types, t, t) == pnls[t], t
    _assert_balanced(game, 1)
    game.turn()  # nothing posts twice
    assert sum(1 for o in game.state.ownerships if o.company_id == a and o.to_turn) == 1
    _assert_balanced(game, 1)


def test_selling_a_parent_with_brands_brings_them_into_the_buyers_group(
    loaded: LoadedData,
) -> None:
    """Review 4's case: the player's company, owning two brands, is sold (the brand-closing
    path of a takeover sale) and the founder founds again. The brands count under the buyer
    for antitrust and enter its consolidated statements, which balance."""
    game, a, b = _two_brands(loaded)
    game.turn()
    state = game.state
    buyer = buyer_of(state)
    assert buyer is not None
    deal_id, ids = state.next_ids.take("deal")
    deal = Deal(
        id=deal_id,
        acquirer_id=buyer,
        target_id=1,
        price_cents=10_000_000_000_00,
        cash_share=1.0,
        made_turn=state.turn,
        status="closed",
        resolved_turn=state.turn,
        mode="brand",
    )
    game.balances[(buyer, CASH)] = game.balances.get((buyer, CASH), 0) + 20_000_000_000_00
    game.balances[(buyer, COMMON_EQUITY)] -= 20_000_000_000_00
    game.lines.setdefault(buyer, []).extend(
        [(0, CASH, 20_000_000_000_00), (0, COMMON_EQUITY, -20_000_000_000_00)]
    )
    state, entries, acquisition = settle(
        replace(state, next_ids=ids), deal, (), game.balances, loaded.balance, loaded.game_data
    )
    state = with_acquisition(state, acquisition)
    state = replace(state, save_meta=replace(state.save_meta, game_state="exit"))
    game.post(entries)
    state, started, _ = found_again(
        state, "Second Act", 0, RngFactory(3), loaded.balance, loaded.game_data
    )
    game.state = state
    game.post(started)
    assert [c.id for c in group_companies(state, buyer)] == [buyer, 1, *sorted((a, b))]
    assert owner_of(state, a) == owner_of(state, b) == buyer
    owners = antitrust.customers_by_market(state, loaded.balance, loaded.game_data)
    assert not {o for m in owners.values() for o in m} & {1, a, b}
    for _ in range(2):
        game.turn()
    _assert_balanced(game, buyer)
    sheet = fs.balance_sheet(game.consolidated(buyer), _types(loaded), game.state.turn - 1)
    assert INVESTMENT_SUBSIDIARIES not in sheet.assets or sheet.assets[INVESTMENT_SUBSIDIARIES] == 0
