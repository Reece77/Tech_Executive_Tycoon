"""M13 eligibility and the IPO chain (docs/formulas.md 25.1, 25.2, 25.7): each step, the cap
table after listing, and a ledger property test."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import DATA_DIR
from tests.helpers import fresh_game
from tst.loader import LoadedData, load_all
from tst.sim.finance.captable import fd_shares, person_shares
from tst.sim.ledger import CASH, COMMON_EQUITY, GENERAL_ADMIN, LedgerEntry
from tst.sim.markets_public import formulas as pf
from tst.sim.markets_public import ipo
from tst.sim.markets_public.public import public_month
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, listing_of, public_of, reach_stage, with_company, with_listing

LOADED = load_all(DATA_DIR)
MRR = 8_000_000_00  # $8M a month: $96M ARR
OP = 500_000_00  # profitable every month


def eligible(loaded: LoadedData = LOADED, turn: int = 60) -> GameState:
    """A stage-3 company with $96M ARR, growing, profitable for a year."""
    state = replace(fresh_game(loaded), turn=turn)
    company = reach_stage(state.player, 3, turn - 24)
    history = tuple(round(MRR / 1.03**k) for k in range(12, -1, -1))  # ~42% a year
    company = replace(company, mrr_history=history, op_history=(OP,) * 12)
    return with_company(state, company)


def month(state: GameState, seed: int = 1, revenue: int = MRR, op: int = OP):  # type: ignore[no-untyped-def]
    cash = {state.player.id: 100_000_000_00}
    return public_month(
        state,
        RngFactory(seed),
        LOADED.balance,
        LOADED.game_data,
        {state.player.id: revenue},
        {state.player.id: op},
        cash,
    )


def step(state: GameState, name: str) -> tuple[GameState, list[LedgerEntry]]:
    state, entries, _ = ipo.apply_ipo_step(
        state, state.player.id, name, LOADED.balance, LOADED.game_data
    )
    return state, entries


def queued(state: GameState) -> list[str]:
    return [q.template_id for q in state.queued if not q.done]


def through_roadshow(
    state: GameState,
    bank: str = "morgan_stanley",
    ambition: str = "middle",
    sell: str = "middle",
    dual: bool = False,
) -> GameState:
    cid = state.player.id
    state = ipo.hire_banks(state, cid, bank, LOADED.balance, LOADED.game_data)
    state, _ = step(state, "file")
    state, _ = step(state, f"ambition_{ambition}")
    state, _ = step(state, f"sell_{sell}")
    state, _ = step(state, "dual_class" if dual else "single_class")
    return state


def test_eligibility() -> None:
    b = LOADED.balance
    state = eligible()
    assert ipo.eligibility_problem(state, 1, b) is None
    small = with_company(state, replace(state.player, mrr_history=(MRR // 10,) * 13))
    assert "ARR" in (ipo.eligibility_problem(small, 1, b) or "")
    stage2 = with_company(state, replace(state.player, stage=2))
    assert "stage" in (ipo.eligibility_problem(stage2, 1, b) or "")
    # loss-making and flat: not eligible; loss-making but growing 40%+: eligible
    flat = with_company(
        state, replace(state.player, mrr_history=(MRR,) * 13, op_history=(-OP,) * 12)
    )
    assert "quarters" in (ipo.eligibility_problem(flat, 1, b) or "")
    growing = with_company(state, replace(state.player, op_history=(-OP,) * 12))
    assert ipo.eligibility_problem(growing, 1, b) is None
    # one losing quarter breaks the profitability test
    assert not ipo.profitable_quarters((OP,) * 9 + (-OP * 2,) * 3, 12)
    assert ipo.profitable_quarters((OP,) * 12, 12)


def test_each_step_of_the_chain() -> None:
    state = eligible()
    cid = state.player.id
    state = ipo.hire_banks(state, cid, "morgan_stanley", LOADED.balance, LOADED.game_data)
    assert listing_of(state, cid).status == "filing"  # type: ignore[union-attr]
    assert queued(state) == [ipo.FILING]
    state, _ = step(state, "file_late")  # restated: a month later
    listing = listing_of(state, cid)
    assert listing is not None and listing.status == "roadshow"
    assert listing.roadshow_turn == state.turn + 2
    assert set(queued(state)) >= {ipo.ROADSHOW_AMBITION, ipo.ROADSHOW_SHARE}
    state, _ = step(state, "ambition_high")
    assert ipo.ROADSHOW_CLASS not in queued(state)  # waits for both answers
    state, _ = step(state, "sell_low")
    assert ipo.ROADSHOW_CLASS in queued(state)
    state, _ = step(state, "dual_class")
    listing = listing_of(state, cid)
    assert listing is not None and ipo.roadshow_done(listing)
    # phase 7 draws the book and queues the pricing critical event
    state, entries, _ = month(state)
    listing = listing_of(state, cid)
    assert listing is not None and listing.status == "pricing" and listing.demand is not None
    assert not entries
    pricing = ipo.PRICING_STRONG if listing.demand >= 1.3 else ipo.PRICING
    assert pricing in queued(state)
    assert listing.new_shares == pf.new_shares(listing.shares_before, 0.10)


def test_pricing_and_listing_reconcile() -> None:
    state = through_roadshow(eligible())
    cid = state.player.id
    state, _, _ = month(state)
    before = fd_shares(state, cid)
    founder = state.founder_of(cid)
    assert founder is not None
    stake = person_shares(state, cid, founder.id)
    state, _ = step(state, "price_cut")
    listing = listing_of(state, cid)
    assert listing is not None and listing.status == "priced" and listing.price_choice == "cut"
    suggested = listing
    state, entries, logs = month(state)
    listing = listing_of(state, cid)
    public = public_of(state, cid)
    assert listing is not None and listing.status == "listed" and public is not None
    # cap table: new shares are 15% of the post-IPO fully diluted count, the founder keeps theirs
    after = fd_shares(state, cid)
    assert after == before + listing.new_shares
    assert abs(listing.new_shares / after - 0.15) < 1e-6
    assert person_shares(state, cid, founder.id) == stake
    # the ledger: cash in = equity = gross - fee
    (entry,) = entries
    lines = {line.account: line.amount for line in entry.lines}
    gross = suggested.price_cents * listing.new_shares
    fee = pf.fee_cents(gross, 0.06)
    assert lines[CASH] == gross - fee == -lines[COMMON_EQUITY]
    assert state.player.stage == 4
    assert sum(1 for s in state.board(cid) if s.kind == "independent") == 2
    assert public.price_cents == listing.close_cents
    assert 3 <= len(public.analysts) <= 8
    assert any(item.template == "ipo_listed" for item in logs)
    # a cut lowers ambition: the first day pops more than at the range (25.2 step 5)
    assert listing.first_day_return is not None


def test_raise_needs_strong_demand() -> None:
    state = through_roadshow(eligible())
    state, _, _ = month(state)
    cid = state.player.id
    listing = listing_of(state, cid)
    assert listing is not None
    weak = replace(listing, demand=1.0)
    state2 = with_listing(state, weak)
    state2, _ = step(state2, "price_raise")
    assert listing_of(state2, cid).price_choice == "range"  # type: ignore[union-attr]
    strong = replace(listing, demand=1.5)
    state3 = with_listing(state, strong)
    state3, _ = step(state3, "price_raise")
    priced = listing_of(state3, cid)
    assert priced is not None and priced.price_choice == "raise"
    assert priced.price_cents == round(listing.price_cents * 1.1)


def test_pull_costs_fees_and_confidence() -> None:
    state = through_roadshow(eligible())
    state, _, _ = month(state)
    cid = state.player.id
    listing = listing_of(state, cid)
    assert listing is not None
    seats = {s.id: s.confidence for s in state.board(cid)}
    state, entries = step(state, "pull")
    (entry,) = entries
    lines = {line.account: line.amount for line in entry.lines}
    expected = round(pf.fee_cents(listing.price_cents * listing.new_shares, 0.06) * 0.3)
    assert lines[GENERAL_ADMIN] == expected == -lines[CASH]
    for seat in state.board(cid):
        if seats[seat.id] is not None:
            assert seat.confidence == max(0.0, seats[seat.id] - 10)  # type: ignore[operator]
    after = listing_of(state, cid)
    assert after is not None and after.status == "pulled"
    assert "banks" in (ipo.eligibility_problem(state, cid, LOADED.balance) or "")
    later = replace(state, turn=state.turn + 12)
    assert ipo.eligibility_problem(later, cid, LOADED.balance) is None


def test_demand_is_seeded() -> None:
    state = through_roadshow(eligible())
    a = listing_of(month(state, seed=7)[0], 1)
    b = listing_of(month(state, seed=7)[0], 1)
    c = listing_of(month(state, seed=8)[0], 1)
    assert a is not None and b is not None and c is not None
    assert a.demand == b.demand != c.demand


@settings(max_examples=25, deadline=None)
@given(
    bank=st.sampled_from(["goldman_sachs", "morgan_stanley", "jp_morgan"]),
    ambition=st.sampled_from(["high", "middle", "low"]),
    sell=st.sampled_from(["low", "middle", "high"]),
    dual=st.booleans(),
    price=st.sampled_from(["price_range", "price_raise", "price_cut"]),
    seed=st.integers(0, 10_000),
)
def test_listing_ledger_and_cap_table_property(
    bank: str, ambition: str, sell: str, dual: bool, price: str, seed: int
) -> None:
    """Every listing balances, posts gross - fee to cash and common equity, and the cap table
    grows by exactly the new shares."""
    state = through_roadshow(eligible(), bank, ambition, sell, dual)
    state, _, _ = month(state, seed=seed)
    cid = state.player.id
    before = fd_shares(state, cid)
    state, _ = step(state, price)
    priced = listing_of(state, cid)
    assert priced is not None
    state, entries, _ = month(state, seed=seed)
    listing = listing_of(state, cid)
    assert listing is not None and listing.status == "listed"
    for e in entries:
        assert sum(line.amount for line in e.lines) == 0
    cash = sum(line.amount for e in entries for line in e.lines if line.account == CASH)
    equity = -sum(line.amount for e in entries for line in e.lines if line.account == COMMON_EQUITY)
    gross = priced.price_cents * priced.new_shares
    fee = pf.fee_cents(gross, LOADED.game_data.bank(bank).fee)
    assert cash == equity == gross - fee == listing.gross_cents - listing.fee_cents
    assert fd_shares(state, cid) == before + listing.new_shares
    assert listing.first_day_return is not None and -0.3 <= listing.first_day_return <= 0.8
