"""M36 (formulas.md 45.2, 45.6; acceptance): the personal book, the cap table and the estate
balance through divorce, gifts, the trust and estate tax. Every personal entry balances, an
account's total across the people involved is unchanged by a transfer, and shares only move
between holders (fully diluted shares never change)."""

from __future__ import annotations

from collections import Counter
from functools import cache

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.conftest import DATA_DIR
from tests.m36_helpers import family_game, hire_child, with_cash
from tst.balance.game import Game
from tst.loader import LoadedData, load_all
from tst.sim.family import estate, rules
from tst.sim.family.divorce import divorce
from tst.sim.finance.captable import fd_shares
from tst.sim.founder.personal import book_balances
from tst.sim.state import GameState, family_partner, listed_id

SETTINGS = settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@cache
def _data() -> LoadedData:
    return load_all(DATA_DIR)


@cache
def _base(seed: int) -> Game:
    game = family_game(_data(), seed, age=60, child_ages=(30, 27))
    for k in rules.children(game.state):
        hire_child(game, k.person_id)
    return game


def _people(state: GameState) -> set[int]:
    return {e.person_id for e in state.personal_book}


def _account_totals(state: GameState) -> Counter[str]:
    out: Counter[str] = Counter()
    for pid in _people(state):
        out.update(book_balances(state.personal_book, pid))
    return out


def _assert_books(before: GameState, after: GameState, moved: set[str]) -> None:
    for e in after.personal_book:
        assert sum(line.amount for line in e.lines) == 0
    a, b = _account_totals(before), _account_totals(after)
    for account in moved:  # a transfer changes no account's total across the books
        assert a[account] == b[account], account


def _assert_cap(before: GameState, after: GameState) -> None:
    for company in before.companies:
        assert fd_shares(before, company.id) == fd_shares(after, company.id)
        held = sum(e.shares for e in after.company_cap(company.id))
        assert held == sum(e.shares for e in before.company_cap(company.id))
        assert all(e.shares >= 0 for e in after.company_cap(company.id))


@SETTINGS
@given(seed=st.sampled_from([1, 2, 3]), cash=st.integers(0, 10**12))
def test_divorce_balances_the_books_and_the_cap_table(seed: int, cash: int) -> None:
    game = _base(seed)
    head = game.founder_id
    state = with_cash(game.state, head, cash)
    partner = family_partner(state)
    assert partner is not None
    after, _ = divorce(state, partner, _data().balance)
    _assert_books(state, after, {"9100_personal_cash", "9130_family_office"})
    _assert_cap(state, after)
    cid = listed_id(state)
    from tst.sim.finance.captable import person_shares

    total = person_shares(state, cid, head)
    assert person_shares(after, cid, head) + person_shares(after, cid, partner.person_id) == total
    assert cash_after(after, partner.person_id) + cash_after(after, head) == cash


def cash_after(state: GameState, pid: int) -> int:
    return book_balances(state.personal_book, pid).get("9100_personal_cash", 0)


@SETTINGS
@given(
    seed=st.sampled_from([1, 2, 3]),
    share=st.floats(0.01, 0.9),
    trust=st.floats(0.0, 0.9),
    cash=st.integers(10**9, 10**13),
)
def test_gifts_trust_and_estate_tax_balance(
    seed: int, share: float, trust: float, cash: int
) -> None:
    data = _data()
    game = _base(seed)
    head = game.founder_id
    heir = rules.children(game.state)[0].person_id
    state = with_cash(game.state, head, cash)
    cid = listed_id(state)
    from tst.sim.finance.captable import person_shares

    held = person_shares(state, cid, head)
    gift = max(1, int(held * share))
    s1, _ = estate.gift_shares(state, heir, gift, game.balances, data.balance, data.game_data)
    _assert_cap(state, s1)
    _assert_books(state, s1, set())
    rest = person_shares(s1, cid, head)
    if int(rest * trust) > 0:
        s2, _ = estate.fund_trust(s1, int(rest * trust), data.balance)
    else:
        s2 = s1
    _assert_cap(s1, s2)
    bp = rules.family_bp(s2)
    assert bp == rules.family_bp(state)  # gifts and the trust keep shares in the family
    q = estate.quote(s2, head, game.balances, data.balance, data.game_data)
    s3, _ = estate.settle(s2, head, heir, game.balances, data.balance, data.game_data)
    _assert_cap(s2, s3)
    for e in s3.personal_book:
        assert sum(line.amount for line in e.lines) == 0
    # The tax left the books; the rest of the cash passed to the heir.
    before = cash_after(s2, head) + cash_after(s2, heir)
    proceeds = q.shares_to_sell * q.share_price_cents
    # M36r: the whole tax is paid (`min(tax, cash + proceeds)` encoded review 7 finding 5's gap)
    paid = q.tax_cents
    assert cash_after(s3, head) == 0
    assert cash_after(s3, heir) == before + proceeds - paid
    assert person_shares(s3, cid, head) == 0
