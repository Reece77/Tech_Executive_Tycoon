"""M26 the founder's life, part 2 (docs/formulas.md 37): stake arithmetic and dilution,
joining rounds and backing a network founder, outcomes, conflicts of interest, public shares,
own-company windows and filings, insider trading (a seeded test of investigations), the
family office's monthly return and the market index, net worth and the legacy term. Property
tests: the personal book and each startup's books balance, a stake never exceeds 100%, and
company books never touch a personal account."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import DATA_DIR
from tests.helpers import fresh_game
from tests.unit.test_m13_public import LISTED
from tst.loader import load_all
from tst.sim.actions import (
    BackStartup,
    FormFamilyOffice,
    JoinRound,
    MoveFamilyOffice,
    TradeShares,
    apply_action,
)
from tst.sim.errors import InvalidActionError
from tst.sim.finance.captable import person_shares
from tst.sim.founder import angel, family_office, investing, personal, shares, wealth
from tst.sim.founder.investing_models import (
    STAKE_FULL,
    AngelStake,
    PersonalTrade,
    StartupRound,
)
from tst.sim.founder.models import (
    ANGEL,
    DIVIDENDS,
    FAMILY_OFFICE,
    GAINS,
    LOSSES,
    PERSONAL_ACCOUNTS,
    PUBLIC_SHARES,
)
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.mna.models import Deal, TargetFile
from tst.sim.mna.valuation import is_listed
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    angel_stake_of,
    holding_in,
    with_angel_stake,
    with_company,
    with_deal,
    with_startup_round,
    with_target_file,
    with_trade,
)

LOADED = load_all(DATA_DIR)
B, D = LOADED.balance, LOADED.game_data
CID = 1
MILLION = 100_000_000  # cents
BIG = {(CID, CASH): 10**13}


def _fid(state: GameState) -> int:
    founder = state.founder_of(CID)
    assert founder is not None
    return founder.id


def _act(state: GameState, action: object, balances: dict | None = None) -> GameState:  # type: ignore[type-arg]
    return apply_action(  # type: ignore[arg-type]
        state, action, RngFactory(1), B, D, balances or BIG, seq=1
    ).new_state


def _rich(state: GameState, cents: int = 100 * MILLION) -> GameState:
    return personal.credit(state, _fid(state), cents, "exit")


def _startup(state: GameState, raised: int = 2 * MILLION) -> tuple[GameState, int]:
    """A rival startup with a round closed last month."""
    company = next(c for c in state.companies if not c.is_player)
    cid = max(c.id for c in state.companies) + 1
    startup = replace(
        company, id=cid, name="Testco", is_startup=True, rival_key=(9, 0, 0), parent_id=None
    )
    state = with_company(state, startup)
    record = StartupRound(1, cid, state.turn - 1, raised, angel.post_money(raised, B), "funded")
    return with_startup_round(state, record), cid


# --- 37.2 Stake arithmetic -------------------------------------------------------------------


def test_post_money_and_seed_stake() -> None:
    assert angel.post_money(2 * MILLION, B) == round(2 * MILLION / B.angel.round_dilution)
    lo, hi = B.angel.seed_stake
    assert angel.seed_stake(B.angel.min_cheque_cents, B) == lo
    assert angel.seed_stake(B.angel.seed_full_cents, B) == hi
    assert angel.seed_stake(10 * B.angel.seed_full_cents, B) == hi
    mid = (B.angel.min_cheque_cents + B.angel.seed_full_cents) // 2
    assert lo < angel.seed_stake(mid, B) < hi


def test_joining_a_round_extends_it_at_its_price() -> None:
    state = _rich(fresh_game(LOADED))
    state, cid = _startup(state)
    fid = _fid(state)
    cheque = MILLION // 2
    after = _act(state, JoinRound(fid, cid, cheque))
    stake = angel_stake_of(after, fid, cid)
    assert stake is not None
    post = angel.post_money(2 * MILLION, B) + cheque
    assert stake.stake_ppm == cheque * STAKE_FULL // post
    assert stake.last_post_cents == post
    assert personal.cash_cents(after, fid) == 100 * MILLION - cheque
    book = personal.book_balances(after.personal_book, fid)
    assert book[ANGEL] == cheque
    # a second cheque keeps the first pro rata
    again = _act(after, JoinRound(fid, cid, cheque))
    second = angel_stake_of(again, fid, cid)
    assert second is not None and second.id == stake.id
    kept = stake.stake_ppm * post // (post + cheque)
    assert second.stake_ppm == kept + cheque * STAKE_FULL // (post + cheque)


def test_joining_needs_an_open_round_cash_and_size() -> None:
    state, cid = _startup(_rich(fresh_game(LOADED)))
    fid = _fid(state)
    with pytest.raises(InvalidActionError):  # bigger than the round
        _act(state, JoinRound(fid, cid, 3 * MILLION))
    with pytest.raises(InvalidActionError):  # below the minimum
        _act(state, JoinRound(fid, cid, 100))
    poor = _startup(fresh_game(LOADED))[0]
    with pytest.raises(InvalidActionError):
        _act(poor, JoinRound(_fid(poor), cid, MILLION))
    later = replace(state, turn=state.turn + 5)
    with pytest.raises(InvalidActionError):  # the window has passed
        _act(later, JoinRound(fid, cid, MILLION))


def test_a_join_posts_balanced_entries_in_both_books() -> None:
    state, cid = _startup(_rich(fresh_game(LOADED)))
    fid = _fid(state)
    out = apply_action(state, JoinRound(fid, cid, MILLION), RngFactory(1), B, D, BIG, seq=1)
    (entry,) = out.ledger_entries
    assert entry.company_id == cid
    assert {line.account for line in entry.lines} == {CASH, COMMON_EQUITY}
    assert sum(line.amount for line in entry.lines) == 0
    for e in out.new_state.personal_book:
        assert sum(line.amount for line in e.lines) == 0


@settings(max_examples=80, deadline=None)
@given(
    st.lists(
        st.tuples(st.sampled_from(("join", "round")), st.integers(1, 2_000_000_000)),
        min_size=1,
        max_size=25,
    )
)
def test_a_stake_never_exceeds_the_whole_company(ops: list[tuple[str, int]]) -> None:
    """Cheques and later rounds in any order: the stake stays in (0, 100%], and the personal
    book balances with 9110 equal to the cheques written."""
    state, cid = _startup(_rich(fresh_game(LOADED), 10**13))
    fid = _fid(state)
    written = 0
    for kind, cents in ops:
        if kind == "join":
            last = angel.latest_round(state, cid)
            rnd = angel.open_round(state, cid, B)
            if rnd is None or last is None or rnd.raised_cents < B.angel.round_min_cents:
                continue
            cents = max(B.angel.round_min_cents, min(cents, rnd.raised_cents))
            state = _act(state, JoinRound(fid, cid, cents))
            written += cents
        else:
            raised = cents
            state, record = angel.record_round(
                state, cid, raised, angel.post_money(raised, B), "funded"
            )
            state, _ = angel.stakes_month(state, [record], B, D)
        stake = angel_stake_of(state, fid, cid)
        if stake is not None:
            assert 0 <= stake.stake_ppm <= STAKE_FULL
    book = personal.book_balances(state.personal_book, fid)
    assert sum(book.values()) == 0
    assert book.get(ANGEL, 0) == written
    assert all(line.account in PERSONAL_ACCOUNTS for e in state.personal_book for line in e.lines)


def test_a_later_round_dilutes_by_its_share() -> None:
    state, cid = _startup(_rich(fresh_game(LOADED)))
    fid = _fid(state)
    state = _act(state, JoinRound(fid, cid, MILLION))
    before = angel_stake_of(state, fid, cid)
    assert before is not None
    state, record = angel.record_round(state, cid, 5 * MILLION, 25 * MILLION, "funded")
    state, _ = angel.stakes_month(state, [record], B, D)
    after = angel_stake_of(state, fid, cid)
    assert after is not None
    assert after.stake_ppm == before.stake_ppm * 20 // 25  # x (1 - round_dilution)
    assert after.last_post_cents == 25 * MILLION
    assert wealth.stake_value_cents(after) == after.stake_ppm * 25 * MILLION // STAKE_FULL


# --- 37.2 Outcomes ---------------------------------------------------------------------------


def _held(cheque: int = MILLION) -> tuple[GameState, int, AngelStake]:
    state, cid = _startup(_rich(fresh_game(LOADED)))
    state = _act(state, JoinRound(_fid(state), cid, cheque))
    stake = angel_stake_of(state, _fid(state), cid)
    assert stake is not None
    return state, cid, stake


def test_an_acquisition_pays_stake_times_price() -> None:
    state, cid, stake = _held()
    price = 40 * MILLION
    deal = Deal(1, 2, cid, price, 1.0, state.turn, status="closed", resolved_turn=state.turn)
    state, logs = angel.stakes_month(with_deal(state, deal), [], B, D)
    done = next(s for s in state.angel_stakes if s.id == stake.id)
    proceeds = stake.stake_ppm * price // STAKE_FULL
    assert done.status == "acquired" and done.proceeds_cents == proceeds
    book = personal.book_balances(state.personal_book, _fid(state))
    assert book.get(ANGEL, 0) == 0
    assert -book.get(GAINS, 0) == proceeds - MILLION
    assert personal.cash_cents(state, _fid(state)) == 100 * MILLION - MILLION + proceeds
    assert any(i.template == "angel_exit" for i in logs)


def test_a_failure_is_written_off() -> None:
    state, cid, stake = _held()
    company = state.company(cid)
    state = with_company(state, replace(company, failed_turn=state.turn))
    state, _ = angel.stakes_month(state, [], B, D)
    done = next(s for s in state.angel_stakes if s.id == stake.id)
    assert done.status == "failed"
    book = personal.book_balances(state.personal_book, _fid(state))
    assert book.get(ANGEL, 0) == 0 and book[LOSSES] == MILLION


def test_the_players_own_deal_raises_a_conflict() -> None:
    state, cid, stake = _held()
    deal = Deal(1, CID, cid, 40 * MILLION, 1.0, state.turn)
    state, _ = angel.stakes_month(with_deal(state, deal), [], B, D)
    raised = next(s for s in state.angel_stakes if s.id == stake.id)
    assert raised.coi_turn == state.turn
    assert any(q.template_id == angel.CONFLICT_TEMPLATE for q in state.queued)


def test_concealing_is_found_by_a_seeded_draw() -> None:
    state, _, stake = _held()
    state = with_angel_stake(state, replace(stake, coi_turn=state.turn))
    rng = RngFactory(state.save_meta.master_seed)
    a = angel.answer_conflict(state, "conceal", rng, B)
    b = angel.answer_conflict(state, "conceal", rng, B)
    assert a.angel_stakes == b.angel_stakes
    disclosed = angel.answer_conflict(state, "disclose", rng, B)
    assert disclosed.angel_stakes[0].coi_found_turn is None
    # across stake ids about coi_found_p are found
    found = 0
    for i in range(1, 201):
        s = with_angel_stake(state, replace(stake, id=i, coi_turn=state.turn))
        s = replace(s, angel_stakes=tuple(x for x in s.angel_stakes if x.id == i))
        out = angel.answer_conflict(s, "conceal", rng, B)
        found += out.angel_stakes[0].coi_found_turn is not None
    assert abs(found / 200 - B.personal.coi_found_p) < 0.12


# --- 37.2 Backing a network founder ------------------------------------------------------------


def _with_leaver(state: GameState) -> tuple[GameState, int]:
    from tst.sim.people.models import Employment
    from tst.sim.state import with_employment

    person = next(p for p in state.people if not p.is_founder)
    emp_id = max(e.id for e in state.employments) + 1
    ended = Employment(
        emp_id, person.id, CID, "software_engineer", "mid", 100, 0, 0, 1, "ended", "resigned"
    )
    state = replace(
        state, employments=tuple(e for e in state.employments if e.person_id != person.id)
    )
    from tst.sim.founder.investing_models import NetworkEntry
    from tst.sim.state import with_network

    state = with_employment(state, ended)
    return with_network(state, [NetworkEntry(person.id, 0)], B.angel.network_size), person.id


def test_backing_a_former_employee() -> None:
    state, pid = _with_leaver(_rich(fresh_game(LOADED)))
    assert pid in {p.id for p in angel.network(state)}
    fid = _fid(state)
    cheque = 2 * MILLION
    category = next(
        c.key for c in D.categories if not (c.capacity_market or c.sells_units or c.assembly_market)
    )
    out = apply_action(
        state, BackStartup(fid, pid, category, cheque), RngFactory(1), B, D, BIG, seq=1
    )
    after = out.new_state
    stake = after.angel_stakes[-1]
    assert stake.backed and stake.cost_cents == cheque
    assert stake.stake_ppm == round(angel.seed_stake(cheque, B) * STAKE_FULL)
    startup = after.company(stake.company_id)
    assert startup.is_startup and startup.alive
    job = after.employment_of(pid)
    assert job is not None and job.company_id == startup.id and job.level == "exec"
    cash = sum(
        line.amount
        for e in out.ledger_entries
        if e.company_id == startup.id
        for line in e.lines
        if line.account == CASH
    )
    assert cash == cheque
    lo, hi = B.angel.team
    assert lo + 1 <= len(after.staff(startup.id)) <= hi + 1
    with pytest.raises(InvalidActionError):  # not in the network
        _act(state, BackStartup(fid, fid, category, cheque))
    with pytest.raises(InvalidActionError):  # below the minimum cheque
        _act(state, BackStartup(fid, pid, category, MILLION // 10))


# --- 37.3 Public shares ------------------------------------------------------------------------


def _listed_rival(state: GameState) -> int:
    return next(c.id for c in state.companies if not c.is_player and is_listed(state, c.id, D))


def test_buying_and_selling_a_listed_rival() -> None:
    state = _rich(fresh_game(LOADED))
    fid = _fid(state)
    rid = _listed_rival(state)
    price = wealth.share_price_cents(state, rid, BIG, B, D)
    assert price is not None and price >= 1
    n = 1000
    out = apply_action(state, TradeShares(fid, rid, "buy", n), RngFactory(1), B, D, BIG, seq=1)
    assert out.ledger_entries == ()  # the company's books do not move
    after = out.new_state
    held = holding_in(after, fid, rid)
    cost = round(n * price * B.personal.trade_cost)
    assert held is not None and held.shares == n and held.cost_cents == n * price + cost
    assert personal.cash_cents(after, fid) == 100 * MILLION - n * price - cost
    sold = _act(after, TradeShares(fid, rid, "sell", n))
    book = personal.book_balances(sold.personal_book, fid)
    assert book.get(PUBLIC_SHARES, 0) == 0
    assert sum(book.values()) == 0
    with pytest.raises(InvalidActionError):
        _act(sold, TradeShares(fid, rid, "sell", 1))


def test_own_company_trades_move_the_cap_table_and_respect_the_window() -> None:
    state = _rich(LISTED, 10**12)
    fid = _fid(state)
    open_turn = state.turn - state.turn % 3  # a quarter's first month
    state = replace(state, turn=open_turn)
    held = person_shares(state, CID, fid)
    after = _act(state, TradeShares(fid, CID, "buy", 100))
    assert person_shares(after, CID, fid) == held + 100
    closed = replace(state, turn=open_turn + 2)
    with pytest.raises(InvalidActionError):
        _act(closed, TradeShares(fid, CID, "buy", 100))


def test_a_large_own_sale_is_a_public_filing() -> None:
    from tst.sim.markets_public.public import outstanding_shares

    state = _rich(LISTED, 10**12)
    fid = _fid(state)
    state = replace(state, turn=state.turn - state.turn % 3)
    big = int(outstanding_shares(state, CID) * B.personal.filing_share) + 1
    big = min(big, person_shares(state, CID, fid))
    sentiment = state.public_companies[0].sentiment
    after = _act(state, TradeShares(fid, CID, "sell", big))
    assert after.personal_trades[-1].filed
    assert after.public_companies[0].sentiment == pytest.approx(
        sentiment + B.personal.filing_sentiment
    )
    assert any(q.template_id == shares.FILING_TEMPLATE for q in after.queued)


def test_a_trade_ahead_of_a_deal_in_preparation_is_sensitive() -> None:
    state = _rich(fresh_game(LOADED))
    fid = _fid(state)
    rid = _listed_rival(state)
    state = with_target_file(state, TargetFile(CID, rid, diligence_turn=state.turn))
    after = _act(state, TradeShares(fid, rid, "buy", 10))
    assert after.personal_trades[-1].sensitive_target_id == rid
    plain = _act(_rich(fresh_game(LOADED)), TradeShares(fid, rid, "buy", 10))
    assert plain.personal_trades[-1].sensitive_target_id is None


def _sensitive(state: GameState, trade_id: int, rid: int) -> GameState:
    return with_trade(
        state,
        PersonalTrade(
            trade_id, _fid(state), rid, state.turn, "buy", 10, 100, 1, sensitive_target_id=rid
        ),
    )


def test_investigations_are_seeded_and_near_sec_p() -> None:
    state = fresh_game(LOADED)
    rid = _listed_rival(state)
    deal = Deal(1, CID, rid, 10 * MILLION, 1.0, state.turn)
    state = with_deal(state, deal)
    investigated = 0
    n = 200
    for i in range(1, n + 1):
        s = _sensitive(replace(state, personal_trades=()), i, rid)
        a, _ = shares.trades_month(s, RngFactory(7), BIG, B, D)
        b, _ = shares.trades_month(s, RngFactory(7), BIG, B, D)
        assert a.personal_trades == b.personal_trades
        t = a.personal_trades[0]
        assert t.resolved and t.risk == B.personal.risk_per_trade and t.public_turn == state.turn
        if t.investigate_turn is not None:
            investigated += 1
            assert state.turn < t.investigate_turn <= state.turn + B.personal.investigation_months
    assert abs(investigated / n - B.personal.sec_p) < 0.1


def test_a_window_without_news_clears() -> None:
    state = fresh_game(LOADED)
    rid = _listed_rival(state)
    s = _sensitive(state, 1, rid)
    later = replace(s, turn=s.turn + B.personal.insider_months + 1)
    out, _ = shares.trades_month(later, RngFactory(7), BIG, B, D)
    t = out.personal_trades[0]
    assert t.resolved and t.risk == 0 and t.investigate_turn is None


def test_a_finding_fines_and_hits_the_board() -> None:
    from tst.sim.state import credibility_of

    state = _rich(LISTED, 10 * MILLION)
    fid = _fid(state)
    t = PersonalTrade(1, fid, CID, state.turn, "buy", 10, 100, 1, gain_cents=MILLION)
    before = credibility_of(state, CID)
    after, logs = shares.finding(state, t, B)
    due = MILLION * (1 + B.personal.fine_mult)
    assert personal.cash_cents(after, fid) == 10 * MILLION - due
    cred = credibility_of(after, CID)
    assert cred is not None
    assert cred.value < (before.value if before is not None else 100)
    assert any(i.template == "insider_finding" for i in logs)
    for a, b in zip(state.board(CID), after.board(CID), strict=True):
        if a.confidence is not None:
            assert b.confidence == max(0.0, a.confidence + B.personal.finding_board)


def test_rival_dividends_on_the_founders_shares() -> None:
    state = _rich(fresh_game(LOADED))
    fid = _fid(state)
    rid = _listed_rival(state)
    state = with_company(state, replace(state.company(rid), op_history=(MILLION,) * 3))
    state = _act(state, TradeShares(fid, rid, "buy", 1_000_000))
    quarter_end = replace(state, turn=2)
    after, entries, logs = shares.dividends_month(quarter_end, BIG, B, D)
    (entry,) = entries
    assert entry.company_id == rid
    got = personal.book_balances(after.personal_book, fid)[DIVIDENDS]
    assert -got == entry.lines[0].amount > 0
    assert logs[0].template == "dividend_received"
    _, none, _ = shares.dividends_month(state, BIG, B, D)
    assert none == []


# --- 37.4 The family office ------------------------------------------------------------------


def test_monthly_return_formula() -> None:
    fb = B.family_office
    r = family_office.monthly_return(0.02, 0.001, 14, 0.5, "balanced", B)
    m = fb.mandates["balanced"]
    expect = m.index * 0.02 + (1 - m.index) * 0.001 + fb.alpha * 4 + m.vol * 0.5 - fb.fee / 12
    assert r == pytest.approx(expect)


def test_forming_needs_wealth_and_moving_money() -> None:
    poor = fresh_game(LOADED)
    with pytest.raises(InvalidActionError):
        _act(poor, FormFamilyOffice(_fid(poor), "balanced"))
    state = _rich(fresh_game(LOADED), B.family_office.min_cents)
    fid = _fid(state)
    state = _act(state, FormFamilyOffice(fid, "balanced"))
    office = state.family_offices[0]
    assert office.mandate == "balanced"
    manager = state.person(office.manager_id)
    assert 1 <= manager.skills["finance"] <= 20
    assert state.reveal(CID, manager.id) is not None
    state = _act(state, MoveFamilyOffice(fid, 10 * MILLION))
    assert wealth.family_office_cents(state, fid) == 10 * MILLION
    state = _act(state, MoveFamilyOffice(fid, -4 * MILLION))
    assert wealth.family_office_cents(state, fid) == 6 * MILLION
    with pytest.raises(InvalidActionError):
        _act(state, MoveFamilyOffice(fid, -7 * MILLION))
    book = personal.book_balances(state.personal_book, fid)
    assert book[FAMILY_OFFICE] == 6 * MILLION and sum(book.values()) == 0


def test_office_month_posts_its_return() -> None:
    state = _rich(fresh_game(LOADED), B.family_office.min_cents)
    fid = _fid(state)
    state = _act(state, FormFamilyOffice(fid, "aggressive"))
    state = _act(state, MoveFamilyOffice(fid, 10 * MILLION))
    state = family_office.index_month(state, BIG, B, D)
    after, _ = family_office.office_month(state, RngFactory(4), B, D)
    (turn, r) = after.family_offices[0].returns[-1]
    assert turn == state.turn
    held = wealth.family_office_cents(after, fid)
    assert held == 10 * MILLION + round(10 * MILLION * r)


def test_the_index_is_value_weighted() -> None:
    state = fresh_game(LOADED)
    one = family_office.index_month(state, BIG, B, D)
    assert one.market_index[-1].level == 1.0 and one.market_index[-1].caps
    caps = dict(one.market_index[-1].caps)
    bumped = tuple((cid, cap * 2 if i == 0 else cap) for i, (cid, cap) in enumerate(caps.items()))
    first = next(iter(caps))
    prev = replace(one.market_index[-1], caps=bumped)
    two = replace(one, market_index=(prev,), turn=one.turn + 1)
    two = family_office.index_month(two, BIG, B, D)
    total = sum(caps.values())
    expect = total / (total + caps[first]) - 1
    assert two.market_index[-1].month_return == pytest.approx(expect)


# --- 37.5 Net worth and legacy ---------------------------------------------------------------


def test_net_worth_parts() -> None:
    state, _, stake = _held()
    fid = _fid(state)
    point = wealth.net_worth(state, fid, BIG, B, D)
    assert point.cash_cents == 99 * MILLION
    assert point.angel_cents == wealth.stake_value_cents(stake)
    assert point.total_cents == (
        point.cash_cents
        + point.angel_cents
        + point.public_cents
        + point.family_office_cents
        + point.own_stake_cents
    )


def test_legacy_wealth_term() -> None:
    assert wealth.legacy_wealth(0, B) == 0
    assert wealth.legacy_wealth(-5, B) == 0
    assert wealth.legacy_wealth(9 * MILLION, B) == pytest.approx(25 * math.log10(1 + 9))
    assert wealth.legacy_wealth(999 * MILLION, B) == pytest.approx(75)


# --- 37.6 target 5: nothing else moves ---------------------------------------------------------


def test_a_founder_who_never_invests_posts_nothing() -> None:
    state = fresh_game(LOADED)
    out, entries, logs = investing.investing_month(state, (), RngFactory(3), BIG, B, D)
    assert entries == () and logs == ()
    assert out.personal_book == state.personal_book
    assert out.angel_stakes == () and out.personal_trades == () and out.family_offices == ()
    assert len(out.wealth_points) == 1 and len(out.market_index) == 1


def test_rounds_are_recorded_from_the_months_entries() -> None:
    state, cid = _startup(fresh_game(LOADED))
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=cid,
        memo="Funding round",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=3 * MILLION,
    )
    out, rounds = angel.record_month_rounds(state, (entry,), B)
    assert rounds[0].raised_cents == 3 * MILLION
    assert rounds[0].post_cents == angel.post_money(3 * MILLION, B)
    assert rounds[0].source == "funded"
    assert angel.open_round(out, cid, B) == rounds[0]


def test_leavers_join_the_network_and_it_is_capped() -> None:
    from tst.sim.people.models import Employment
    from tst.sim.state import with_employment

    state = fresh_game(LOADED)
    others = [p for p in state.people if not p.is_founder][:3]
    base = max(e.id for e in state.employments) + 1
    for i, p in enumerate(others):
        job = Employment(
            base + i,
            p.id,
            CID,
            "software_engineer",
            "mid",
            100,
            0,
            0,
            state.turn,
            "ended",
            "resigned" if i else "retired",
        )
        state = with_employment(state, job)
    out = angel.network_month(state, B)
    assert {e.person_id for e in out.network} == {p.id for p in others[1:]}  # not the retired
    small = B.model_copy(update={"angel": B.angel.model_copy(update={"network_size": 1})})
    assert len(angel.network_month(state, small).network) == 1


def test_a_venture_round_dilutes_the_founders_stake() -> None:
    state, cid, stake = _held()
    state, _ = angel.record_round(state, cid, 2 * MILLION, 8 * MILLION, "venture")
    state, _ = angel.stakes_month(state, [], B, D)
    after = angel_stake_of(state, _fid(state), cid)
    assert after is not None
    assert after.stake_ppm == stake.stake_ppm * 6 // 8
    assert after.last_post_cents == 8 * MILLION
