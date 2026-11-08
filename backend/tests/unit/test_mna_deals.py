"""M14 sub-tasks 3-4 (formulas.md 28.2-28.4): diligence, offers, counters, tenders, closing
with goodwill, and antitrust. Property tests: the ledger balances through closing (cash,
stock and mixed consideration) and the cap table sums to 100% after a stock deal."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game, with_product
from tests.unit.test_hiring_phases import Game
from tests.unit.test_m13_public import listed
from tst.loader import LoadedData
from tst.sim.errors import MnaRuleError
from tst.sim.finance.captable import fd_shares
from tst.sim.ledger import (
    CASH,
    COMMON_EQUITY,
    GENERAL_ADMIN,
    GOODWILL,
    INVESTMENT_SUBSIDIARIES,
    apply_entries,
)
from tst.sim.mna import antitrust, deals
from tst.sim.mna import formulas as mf
from tst.sim.mna.antitrust import AcceptRemedy
from tst.sim.mna.deals import BidForCompany, StartDiligence
from tst.sim.mna.models import Deal
from tst.sim.state import GameState, public_of

BIG = 50_000_000_000_00  # $50B in cents
MID = "mid_market"


def _id(state: GameState, name: str) -> int:
    return next(c.id for c in state.companies if c.name == name)


def _game(loaded: LoadedData, state: GameState | None = None) -> Game:
    game = Game(loaded, state or fresh_game(loaded), cash=BIG)
    return game


def _founder(game: Game) -> int:
    founder = game.state.founder_of(1)
    assert founder is not None
    return founder.id


def _energy(game: Game) -> None:
    from tst.sim.state import with_person_state

    ps = game.state.person_state(_founder(game))
    game.state = with_person_state(game.state, replace(ps, energy=100))


def _true_reservation(game: Game, target: int) -> int:
    b, d = game.loaded.balance, game.loaded.game_data
    return deals.reservation_cents(game.state, target, game.balances, b, d)


def _reservation(game: Game, target: int) -> int:
    """A price the target accepts at the first offer: above any anchored first counter
    (M15b negotiation: reservation x at most 1.30 x (1 + 3 sd))."""
    return 2 * _true_reservation(game, target)


def _title(game: Game) -> str:
    return str(dict(game.action_logs[-1].params)["title"])


def test_negotiation_runs_rounds_toward_the_reservation(loaded: LoadedData) -> None:
    """Playtest 3 addendum 9: an anchored first counter, then each round half the gap closer,
    for mna.max_rounds rounds; then an offer below the final counter ends talks."""
    mb = loaded.balance.mna
    game = _game(loaded)
    zoho = _id(game.state, "Zoho")
    res = _true_reservation(game, zoho)
    counters = []
    for _ in range(mb.max_rounds):
        _energy(game)
        last = counters[-1] if counters else res
        game.act(BidForCompany(_founder(game), zoho, round(last * 0.95), mode="brand"))
        assert "counters at" in _title(game), _title(game)
        counters.append(game.state.target_files[0].counter_cents)
    assert counters == sorted(counters, reverse=True)  # each round lower
    assert all(c >= res for c in counters)  # never below the reservation
    assert counters[0] >= res * min(mb.counter_anchor.values()) * 0.85  # anchored above it
    assert all(str(res) not in str(i.params) for i in game.action_logs)
    _energy(game)
    game.act(BidForCompany(_founder(game), zoho, round(counters[-1] * 0.95), mode="brand"))
    assert "ended talks" in _title(game)
    _energy(game)
    with pytest.raises(MnaRuleError, match="closed for now"):
        game.act(BidForCompany(_founder(game), zoho, res * 3, mode="brand"))


def test_two_lowballs_end_talks_and_the_counter_as_shown_buys(loaded: LoadedData) -> None:
    mb = loaded.balance.mna
    game = _game(loaded)
    zoho = _id(game.state, "Zoho")
    res = _true_reservation(game, zoho)
    _energy(game)
    game.act(BidForCompany(_founder(game), zoho, res // 4, mode="brand"))
    shown = game.state.target_files[0].counter_cents
    assert shown is not None
    for strike in range(1, mb.strikes + 1):
        _energy(game)
        game.act(BidForCompany(_founder(game), zoho, round(shown * mb.lowball) - 100, mode="brand"))
        assert ("ended talks" in _title(game)) == (strike == mb.strikes)
    # a fresh game: bidding the counter as shown is accepted, at no less than the reservation
    game = _game(loaded)
    _energy(game)
    game.act(BidForCompany(_founder(game), zoho, res // 4, mode="brand"))
    shown = game.state.target_files[0].counter_cents
    assert shown is not None and shown >= res
    _energy(game)
    game.act(BidForCompany(_founder(game), zoho, shown, mode="brand"))
    assert game.state.deals and game.state.deals[0].price_cents == shown


def test_no_run_of_offers_reveals_the_reservation(loaded: LoadedData) -> None:
    """Differential: two targets whose reservations differ by less than the counters'
    rounding answer the same offers with the same counters, so the counters cannot pin the
    reservation down."""
    from tst.sim.mna import formulas as mf

    mb = loaded.balance.mna
    for res in (183_456_789_00, 9_876_543_21, 412_000_000):
        twin = res + res // 1000  # 0.1% apart
        for anchor in mb.counter_anchor.values():
            a = mf.first_counter_exact(res, anchor, 0.3, mb)
            b = mf.first_counter_exact(twin, anchor, 0.3, mb)
            shown_a, shown_b = [mf.shown_counter(a)], [mf.shown_counter(b)]
            for _ in range(mb.max_rounds - 1):
                a, b = mf.next_counter_exact(a, res), mf.next_counter_exact(b, twin)
                shown_a.append(mf.shown_counter(a))
                shown_b.append(mf.shown_counter(b))
            same = sum(x == y for x, y in zip(shown_a, shown_b, strict=True))
            assert same >= len(shown_a) - 1, (res, anchor, shown_a, shown_b)
            assert all(s >= res for s in shown_a)  # a shown counter never undercuts it


def test_an_accepted_offer_closes_next_month_with_goodwill(loaded: LoadedData) -> None:
    game = _game(loaded)
    zoho = _id(game.state, "Zoho")
    price = _reservation(game, zoho)
    equity = sum(a for _, a in deals.net_assets(game.balances, zoho, loaded.game_data))
    _energy(game)
    game.act(BidForCompany(_founder(game), zoho, price, mode="brand"))
    (deal,) = game.state.deals
    assert deal.status == "accepted" and deal.close_turn == game.state.turn + 1
    cash = game.cash
    game.turn()
    (deal,) = game.state.deals
    assert deal.status == "closed"
    assert game.state.company(zoho).parent_id == 1  # a kept brand
    # book equity at closing (after the month) sits in 1810; the rest is goodwill
    assert game.balances[(1, GOODWILL)] + game.balances[(1, INVESTMENT_SUBSIDIARIES)] == price
    assert game.balances[(1, INVESTMENT_SUBSIDIARIES)] == pytest.approx(equity, rel=0.2)
    assert cash - game.cash >= price  # the price went out (plus the month's costs)
    (acquisition,) = game.state.acquisitions
    assert acquisition.mode == "brand" and acquisition.price_cents == price


def test_diligence_costs_and_reveals_after_two_months(loaded: LoadedData) -> None:
    game = _game(loaded)
    target = _id(game.state, "Evernote")
    _energy(game)
    game.act(StartDiligence(_founder(game), target))
    assert game.balances[(1, GENERAL_ADMIN)] >= loaded.balance.mna.diligence.min_cents
    assert deals.known_problems(game.state, 1, target) == ()  # nothing before it is done
    game.turn()
    found = game.state.target_files[0]
    assert not found.diligenced
    game.turn()
    found = game.state.target_files[0]
    assert found.diligenced
    assert deals.known_problems(game.state, 1, target) == found.problems
    _energy(game)
    with pytest.raises(MnaRuleError, match="already done"):
        game.act(StartDiligence(_founder(game), target))


def test_problems_are_fixed_per_target(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    b = loaded.balance
    every = [deals.problems_of(state, c.id, b) for c in state.rivals()]
    assert every == [deals.problems_of(state, c.id, b) for c in state.rivals()]
    share = sum(len(p) for p in every) / (len(every) * 3)
    assert 0 < share < 0.4  # about mna.problems.p (0.15)


def test_listed_board_and_failed_tender(loaded: LoadedData) -> None:
    game = _game(loaded)
    salesforce = _id(game.state, "Salesforce")
    b, d = loaded.balance, loaded.game_data
    cap = deals.estimate_cents(game.state, 1, salesforce, game.balances, b, d)
    _energy(game)
    game.act(BidForCompany(_founder(game), salesforce, cap, mode="brand"))  # no premium: no
    assert "rejected" in str(dict(game.action_logs[-1].params)["title"])
    bar = game.state.target_files[0].board_bar
    assert bar is not None and "0.3" not in str(game.action_logs[-1].params)
    _energy(game)
    game.act(
        BidForCompany(_founder(game), salesforce, round(cap * 1.1), hostile=True, mode="brand")
    )
    assert "failed" in str(dict(game.action_logs[-1].params)["title"])  # chance 0 at 10%
    fee = mf.tender_fee_cents(round(cap * 1.1), b.mna.tender)
    assert game.balances[(1, GENERAL_ADMIN)] == fee
    _energy(game)
    with pytest.raises(MnaRuleError, match="closed for now"):
        game.act(BidForCompany(_founder(game), salesforce, cap * 3, mode="brand"))


def test_stock_needs_a_listing_and_cash_must_cover_the_cash_part(loaded: LoadedData) -> None:
    game = Game(loaded, fresh_game(loaded), cash=1_000_00)
    zoho = _id(game.state, "Zoho")
    _energy(game)
    with pytest.raises(MnaRuleError, match="listed"):
        game.act(BidForCompany(_founder(game), zoho, 10**12, cash_share=0.5))
    with pytest.raises(MnaRuleError, match="cash part"):
        game.act(BidForCompany(_founder(game), zoho, 10**12))


# --- Closing: ledger and cap table (property tests) ---------------------------------------


def _listed_with_target(loaded: LoadedData) -> tuple[GameState, int]:
    state = listed()
    return state, next(c.id for c in state.rivals() if c.name == "Zoho")


@settings(max_examples=40, deadline=None)
@given(
    price=st.integers(min_value=1_00, max_value=10**13),
    cash_share=st.sampled_from([0.0, 0.25, 0.5, 1.0, 0.545, 0.105, 0.333, 0.999]),
    mode=st.sampled_from(["brand", "integrate"]),
    target_cash=st.integers(min_value=0, max_value=10**12),
    target_debt=st.integers(min_value=0, max_value=10**11),
)
def test_closing_entries_balance(
    loaded: LoadedData,
    price: int,
    cash_share: float,
    mode: str,
    target_cash: int,
    target_debt: int,
) -> None:
    state, target = _listed_with_target(loaded)
    balances = {(target, CASH): target_cash, (target, "2500_debt"): -target_debt}
    deal = Deal(1, 1, target, price, cash_share, state.turn, mode=mode)  # type: ignore[arg-type]
    entries = deals.closing_entries(state, deal, balances, loaded.game_data)
    after = apply_entries(balances, entries)
    for company in (1, target):
        assert sum(v for (c, _), v in after.items() if c == company) == sum(
            v for (c, _), v in balances.items() if c == company
        )
    cash_part = round(Fraction(price) * Fraction(repr(cash_share)))  # rational reference (M15r)
    assert after.get((1, CASH), 0) - balances.get((1, CASH), 0) == (
        -cash_part + (target_cash if mode == "integrate" else 0)
    )
    assert after.get((1, COMMON_EQUITY), 0) == -(price - cash_part)
    equity = target_cash - target_debt
    assert after.get((1, GOODWILL), 0) == price - equity
    if mode == "integrate":
        assert all(
            v == 0 for (c, a), v in after.items() if c == target and a in (CASH, "2500_debt")
        )


@settings(max_examples=25, deadline=None)
@given(price=st.integers(min_value=1_000_00, max_value=10**13), cash_share=st.floats(0, 0.99))
def test_a_stock_deal_keeps_the_cap_table_whole(
    loaded: LoadedData, price: int, cash_share: float
) -> None:
    state, target = _listed_with_target(loaded)
    public = public_of(state, 1)
    assert public is not None
    before = fd_shares(state, 1)
    deal = Deal(1, 1, target, price, cash_share, state.turn)
    after = deals.issue_shares(state, deal)
    stock = price - round(Fraction(price) * Fraction(repr(cash_share)))  # rational (M15r)
    issued = fd_shares(after, 1) - before
    assert issued == max(1, round(Fraction(stock, public.price_cents)))
    entries = after.company_cap(1)
    total = sum(e.shares for e in entries)
    assert total == fd_shares(after, 1)
    assert sum(e.shares / total for e in entries) == pytest.approx(1.0)


# --- Antitrust (28.4) ---------------------------------------------------------------------


def _overlap(loaded: LoadedData, mine: float, segment: str = "smb") -> tuple[Game, int]:
    """The player sells B2B SaaS in `segment` with `mine` customers next to Zoho's."""
    state = with_product(fresh_game(loaded), prices={segment: 4000}, customers={segment: mine})
    return _game(loaded, state), _id(state, "Zoho")


def test_over_half_is_blocked_until_a_remedy(loaded: LoadedData) -> None:
    game, zoho = _overlap(loaded, 10**7)  # a dominant SMB product
    share, market = antitrust.combined_share(game.state, 1, zoho, loaded.balance, loaded.game_data)
    assert share >= loaded.balance.antitrust.block and market is not None
    _energy(game)
    game.act(BidForCompany(_founder(game), zoho, _reservation(game, zoho), mode="brand"))
    (deal,) = game.state.deals
    assert deal.status == "blocked" and deal.remedy_product_id is not None
    game.turn()
    assert game.state.deals[0].status == "blocked"  # never closes without a remedy
    divested = deal.remedy_product_id
    game.act(AcceptRemedy(_founder(game), deal.id))
    product = game.state.product(divested)
    assert product is not None and product.company_id not in (1, zoho)


def test_the_acquirer_may_divest_its_own_product_instead(loaded: LoadedData) -> None:
    """M15b (an M14 follow-up): the acquirer's own overlapping product is the other remedy;
    divesting it unlinks the acquirer's teams from it."""
    game, zoho = _overlap(loaded, 10**7)
    _energy(game)
    game.act(BidForCompany(_founder(game), zoho, _reservation(game, zoho), mode="brand"))
    (deal,) = game.state.deals
    mine = deal.own_remedy_product_id
    assert deal.status == "blocked" and mine is not None
    assert game.state.product(mine).company_id == 1  # type: ignore[union-attr]
    game.act(AcceptRemedy(_founder(game), deal.id, own=True))
    assert game.state.product(mine).company_id not in (1, zoho)  # type: ignore[union-attr]
    assert game.state.player.root_product_id != mine
    assert all(u.product_id != mine for u in game.state.units if u.company_id == 1)
    after = game.state.deals[0]
    assert after.status != "blocked"  # its share went with it


def _at_share(loaded: LoadedData, target_share: float) -> tuple[Game, int]:
    """The player's mid-market product sized so the combined share with Zoho (about 32% of
    North American mid-market) is `target_share`."""
    game, zoho = _overlap(loaded, 0.0, MID)
    b, d = loaded.balance, loaded.game_data
    owners = antitrust.customers_by_market(game.state, b, d)[("b2b_saas", MID, "north_america")]
    total, z = sum(owners.values()), owners[zoho]
    mine = (target_share * total - z) / (1 - target_share)
    return _overlap(loaded, mine, MID)


def test_a_review_is_seeded(loaded: LoadedData) -> None:
    """At 42%: a review whose length (3-6 months) and outcome draw come from stream mna on
    the target's stable key, so the same seed gives the same review."""
    b = loaded.balance
    outcomes = []
    for _ in range(2):
        game, zoho = _at_share(loaded, 0.42)
        share, _ = antitrust.combined_share(game.state, 1, zoho, b, loaded.game_data)
        assert share == pytest.approx(0.42, abs=0.005)
        deal = Deal(1, 1, zoho, 10**10, 1.0, game.state.turn, close_turn=game.state.turn + 1)
        screened, _ = antitrust.screen(game.state, deal, game.rng, b, loaded.game_data)
        assert screened.status == "review" and screened.close_turn is None
        lo, hi = b.antitrust.review_months
        assert screened.review_end_turn is not None
        assert lo <= screened.review_end_turn - game.state.turn <= hi
        outcomes.append((screened.review_end_turn, screened.blocked_draw))
    assert outcomes[0] == outcomes[1]


def test_below_the_review_line_is_cleared(loaded: LoadedData) -> None:
    game, zoho = _at_share(loaded, 0.34)  # Zoho alone holds about 32%: 0.30 would not overlap
    deal = Deal(1, 1, zoho, 10**10, 1.0, game.state.turn, close_turn=game.state.turn + 1)
    screened, _ = antitrust.screen(game.state, deal, game.rng, loaded.balance, loaded.game_data)
    assert screened.status == "accepted" and screened.close_turn == game.state.turn + 1
    assert screened.combined_share == pytest.approx(0.34, abs=0.005)


def test_targets_over_the_staff_limit_cannot_integrate(loaded: LoadedData) -> None:
    """2026-11-05: integration needs at most integration.max_staff staff (Zoho has more)."""
    game = _game(loaded)
    zoho = _id(game.state, "Zoho")
    _energy(game)
    with pytest.raises(MnaRuleError, match="too big to integrate"):
        game.act(BidForCompany(_founder(game), zoho, _reservation(game, zoho)))


# --- The lane merge with M14b (29.1, 29.4) ---------------------------------------------------


def test_an_agreed_deal_raises_an_acquisition_press_moment(loaded: LoadedData) -> None:
    game = _game(loaded)
    zoho = _id(game.state, "Zoho")
    _energy(game)
    game.act(BidForCompany(_founder(game), zoho, _reservation(game, zoho), mode="brand"))
    (moment,) = (m for m in game.state.press_moments if m.trigger == "acquisition")
    assert moment.company_id == 1 and moment.turn == game.state.turn


def test_a_hostile_bid_feeds_the_feud_win_or_lose(loaded: LoadedData) -> None:
    from tst.sim.state import feud_of

    game = _game(loaded)
    salesforce = _id(game.state, "Salesforce")
    b, d = loaded.balance, loaded.game_data
    cap = deals.estimate_cents(game.state, 1, salesforce, game.balances, b, d)
    _energy(game)
    game.act(
        BidForCompany(_founder(game), salesforce, round(cap * 1.1), hostile=True, mode="brand")
    )
    assert "failed" in str(dict(game.action_logs[-1].params)["title"])
    feud = feud_of(game.state, 1, salesforce)
    assert feud is not None and feud.score == b.feud.hostile_bid
    assert feud.causes[-1][2] == "you made a hostile bid"
    assert not any(m.trigger == "acquisition" for m in game.state.press_moments)


# --- Reece's playtest 3: every agreed deal's screening result in the inbox -------------------


def _note(logs: list) -> tuple[str, str]:  # type: ignore[type-arg]
    (note,) = (i for i in logs if str(dict(i.params).get("title", "")).startswith("Antitrust:"))
    params = dict(note.params)
    return str(params["title"]), str(params["detail"])


@pytest.mark.parametrize(
    ("share", "status", "words"),
    [
        (None, "accepted", "Cleared: no overlapping market"),
        (0.34, "accepted", "under the 35% review line"),  # Zoho alone holds about 32%
        (0.42, "review", "regulators review it"),
        (0.99, "blocked", "accept the remedy: divest Zoho CRM"),
    ],
)
def test_every_screening_result_is_a_note(
    loaded: LoadedData, share: float | None, status: str, words: str
) -> None:
    game, zoho = (_game(loaded), 0) if share is None else _at_share(loaded, share)
    if share is None:
        zoho = _id(game.state, "Zoho")  # the player sells nothing: no common market
    deal = Deal(1, 1, zoho, 10**10, 1.0, game.state.turn, close_turn=game.state.turn + 1)
    screened, logs = antitrust.screen(game.state, deal, game.rng, loaded.balance, loaded.game_data)
    title, detail = _note(logs)
    assert screened.status == status and words in detail
    assert "Zoho" in title
    if status == "review":  # never the review's block probability or its drawn outcome
        assert str(round(screened.blocked_draw or 0, 2)) not in detail and "chance" not in detail


def test_a_blocked_offer_says_so_in_its_title(loaded: LoadedData) -> None:
    """The playtest's pt-block: the deal was blocked, but its answer led with "Deal agreed"."""
    game, zoho = _overlap(loaded, 10**7)
    _energy(game)
    game.act(BidForCompany(_founder(game), zoho, _reservation(game, zoho), mode="brand"))
    titles = [str(dict(i.params)["title"]) for i in game.action_logs]
    assert "Deal agreed, but blocked by antitrust: Zoho" in titles
    assert "Antitrust: the deal for Zoho is blocked" in titles


def test_rivals_deals_send_the_player_no_screening_note(loaded: LoadedData) -> None:
    game, zoho = _overlap(loaded, 10**7)
    rival = next(c.id for c in game.state.companies if c.is_rival and c.id != zoho)
    deal = Deal(1, rival, zoho, 10**10, 1.0, game.state.turn, close_turn=game.state.turn + 1)
    _, logs = antitrust.screen(game.state, deal, game.rng, loaded.balance, loaded.game_data)
    assert logs == []


def test_closing_resets_the_feud_with_the_target(loaded: LoadedData) -> None:
    from tst.sim.rivals.characters import add_feud
    from tst.sim.state import feud_of

    game = _game(loaded)
    zoho = _id(game.state, "Zoho")
    game.state = add_feud(game.state, 1, zoho, 40, "test", loaded.balance)
    _energy(game)
    game.act(BidForCompany(_founder(game), zoho, _reservation(game, zoho), mode="brand"))
    game.turn()
    feud = feud_of(game.state, 1, zoho)
    assert game.state.company(zoho).parent_id == 1 and feud is not None and feud.score == 0
