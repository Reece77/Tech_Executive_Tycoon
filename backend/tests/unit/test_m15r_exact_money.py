"""M15r (Codex review 4 finding 8): M&A money is exact. A deal's cash and stock split, and the
other M&A price helpers, match rational half-to-even references, including half-cent cases a
binary float rounds the wrong way (0.545 of 100 cents is 54.5: 54, not 55)."""

from __future__ import annotations

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.test_mna_deals import _listed_with_target
from tst.loader import LoadedData
from tst.sim.ledger import CASH, COMMON_EQUITY
from tst.sim.mna import closing, deals
from tst.sim.mna import formulas as mf
from tst.sim.mna.models import Deal
from tst.sim.rng import RngFactory
from tst.sim.state import public_of


def ref(amount: int, share: str) -> int:
    """The rational reference: amount x share (as written), rounded half to even once."""
    return round(Fraction(amount) * Fraction(share))


HALF_CENTS = [(100, "0.545"), (100_000_000_100, "0.545"), (10**12 + 300, "0.105")]


def test_the_cash_part_rounds_once_and_exactly(loaded: LoadedData) -> None:
    state, target = _listed_with_target(loaded)
    for price, share in HALF_CENTS:
        cash = ref(price, share)
        deal = Deal(1, 1, target, price, float(share), state.turn, mode="brand")
        (entry,) = deals.closing_entries(state, deal, {}, loaded.game_data)
        lines = {x.account: x.amount for x in entry.lines}
        assert (lines[CASH], lines.get(COMMON_EQUITY, 0)) == (-cash, -(price - cash)), price
        assert deals.cash_part_cents(price, float(share)) == cash
        assert deals.cash_part_cents(100, 0.545) == 54 and ref(100, "0.545") == 54


def test_issuance_uses_the_same_split(loaded: LoadedData) -> None:
    state, target = _listed_with_target(loaded)
    public = public_of(state, 1)
    assert public is not None
    price = 100_000_000_100
    deal = Deal(1, 1, target, price, 0.545, state.turn)
    issued = sum(e.shares for e in deals.issue_shares(state, deal).company_cap(1)) - sum(
        e.shares for e in state.company_cap(1)
    )
    assert issued == max(1, round(Fraction(price - ref(price, "0.545"), public.price_cents)))


def test_a_closing_with_exactly_the_cash_part_on_hand_closes(loaded: LoadedData) -> None:
    """Validation and closing check the same exact cash part: 54 cents on hand pays 0.545 of
    100 cents (a float said 55 and abandoned the deal)."""
    state, target = _listed_with_target(loaded)
    deal = Deal(1, 1, target, 100, 0.545, state.turn, status="accepted", mode="brand")
    balances = {(1, CASH): 54}
    after, posted, _ = closing.close_deal(
        state, deal, RngFactory(1), balances, loaded.balance, loaded.game_data
    )
    assert next(d for d in after.deals if d.id == 1).status == "closed"
    assert (
        sum(x.amount for e in posted if e.company_id == 1 for x in e.lines if x.account == CASH)
        == -54
    )


@settings(max_examples=200, deadline=None)
@given(price=st.integers(min_value=1, max_value=10**14), permille=st.integers(0, 1000))
def test_any_split_matches_the_rational_reference(price: int, permille: int) -> None:
    share = permille / 1000
    assert deals.cash_part_cents(price, share) == round(Fraction(price) * Fraction(permille, 1000))


def test_price_helpers_are_exact(loaded: LoadedData) -> None:
    """A reservation at V x (1 + p): $64.7B at p = 0.35 is 8,729,910,343,480.5 cents, which
    a float rounds up."""
    mb = loaded.balance.mna
    value = 6_466_600_254_430
    assert mf.reservation_cents(value, 0.35, False, mb) == ref(value, "1.35")
    assert mf.diligence_cost_cents(10**13 + 100, mb) == max(
        mb.diligence.min_cents,
        round(Fraction(10**13 + 100) * Fraction(mb.diligence.cost_bp, 10_000)),
    )
