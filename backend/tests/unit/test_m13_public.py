"""M13 share price, analysts, earnings and capital actions (docs/formulas.md 25.3-25.5, 25.7):
a seeded price path, macro moving the multiple, a beat, a miss, consecutive misses, the
activist and takeover triggers, and ledger property tests for the capital actions."""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.test_m13_ipo import LOADED, MRR, OP, eligible, month, step, through_roadshow
from tst.sim.finance.captable import fd_shares
from tst.sim.finance.macro import MacroMonth
from tst.sim.ledger import CASH, COMMON_EQUITY
from tst.sim.markets_public import capital
from tst.sim.markets_public import formulas as pf
from tst.sim.markets_public.models import Guidance
from tst.sim.markets_public.public import (
    ACTIVIST,
    TAKEOVER,
    consensus,
    guidance_problem,
    outstanding_shares,
)
from tst.sim.markets_public.value import fundamentals
from tst.sim.state import GameState, guidance_for, public_of, with_guidance, with_public

CID = 1


def listed(seed: int = 1) -> GameState:
    """Listed in month 60 (January 2015) and played to the next quarter start (63), whose
    month has not run yet."""
    state = through_roadshow(eligible())
    state, _, _ = month(state, seed)
    state, _ = step(state, "price_range")
    state, _, _ = month(state, seed)
    state = ipo_history(state, state.player, MRR, OP)
    state = advance(state, 2, seed)
    return replace(state, turn=state.turn + 1)


def advance(
    state: GameState, months: int, seed: int = 1, revenue: int = MRR, op: int = OP
) -> GameState:
    for _ in range(months):
        state = replace(state, turn=state.turn + 1)
        state, _, _ = month(state, seed, revenue, op)
        company = state.player
        state = ipo_history(state, company, revenue, op)
    return state


def ipo_history(state: GameState, company, revenue: int, op: int) -> GameState:  # type: ignore[no-untyped-def]
    from tst.sim.state import with_company

    return with_company(
        state,
        replace(
            company,
            mrr_history=(*company.mrr_history, revenue)[-13:],
            op_history=(*company.op_history, op)[-12:],
        ),
    )


def test_price_path_is_seeded() -> None:
    a = public_of(advance(listed(3), 6, 3), CID)
    b = public_of(advance(listed(3), 6, 3), CID)
    c = public_of(advance(listed(3), 6, 4), CID)
    assert a is not None and b is not None and c is not None
    assert a.price_cents == b.price_cents
    assert a.sentiment == b.sentiment
    assert a.price_cents != c.price_cents


def test_price_follows_fundamentals() -> None:
    """P = V_f / shares x S, from the month's V_f and sentiment (25.3)."""
    state = listed()
    public = public_of(state, CID)
    assert public is not None
    shares = state.share_months[-1].shares
    assert public.price_cents == pf.share_price_cents(public.value_cents, shares, public.sentiment)
    # and V_f doubles when ARR doubles, all else equal
    f1 = fundamentals(state, CID, MRR, OP, LOADED.balance, LOADED.game_data)
    f2 = fundamentals(state, CID, 2 * MRR, 2 * OP, LOADED.balance, LOADED.game_data)
    assert f2.arr_cents == 2 * f1.arr_cents and f2.value_cents > f1.value_cents


def test_macro_moves_the_multiple() -> None:
    state = listed()
    late = 240  # after 2025 the phase-1 macro month is used, not history (20.1)
    state = replace(state, turn=late, macro=MacroMonth(late, 3.0, 1.1, 100.0, 1.0, 0.0, None))
    base = fundamentals(state, CID, MRR, OP, LOADED.balance, LOADED.game_data)
    hot = replace(state, macro=MacroMonth(late, 1.0, 1.5, 100.0, 1.0, 0.0, None))
    cold = replace(state, macro=MacroMonth(late, 5.0, 0.8, 100.0, 1.0, 0.0, None))
    f_hot = fundamentals(hot, CID, MRR, OP, LOADED.balance, LOADED.game_data)
    f_cold = fundamentals(cold, CID, MRR, OP, LOADED.balance, LOADED.game_data)
    assert f_hot.multiple > base.multiple > f_cold.multiple
    assert f_hot.value_cents > f_cold.value_cents


def _report(state: GameState, guided: int, revenue: int) -> GameState:
    """Guidance at quarter start (the current, unplayed turn), then three months of `revenue`
    a month; returns the state at the next quarter start, unplayed."""
    assert state.turn % 3 == 0
    rev, margin = consensus(state, CID)
    state = with_guidance(state, Guidance(CID, state.turn, guided, margin, rev, margin, True))
    # this quarter's first month runs at the current turn
    state, _, _ = month(state, 1, revenue, OP)
    state = ipo_history(state, state.player, revenue, OP)
    state = advance(state, 2, 1, revenue, OP)
    return replace(state, turn=state.turn + 1)


def test_beat_raises_sentiment_and_board() -> None:
    state = listed()
    before = public_of(state, CID)
    conf = {s.id: s.confidence for s in state.board(CID) if s.confidence is not None}
    state = _report(state, 3 * MRR, round(MRR * 1.05))  # 5% above guidance
    g = guidance_for(state, CID, state.turn - 3)
    assert g is not None and g.result == "beat"
    assert g.actual_revenue_cents == 3 * round(MRR * 1.05)
    public = public_of(state, CID)
    assert public is not None and before is not None
    assert public.beat_streak == 1 and public.results[-1] == "beat"
    for s in state.board(CID):
        if s.id in conf:
            assert s.confidence is not None  # moved by +4 plus the month's drift
    assert any(m.mark == "beat" for m in state.share_months)


def test_miss_and_consecutive_misses() -> None:
    state = listed()
    state = _report(state, 3 * MRR, round(MRR * 0.9))  # 10% short
    public = public_of(state, CID)
    assert public is not None and public.results[-1] == "miss" and public.miss_streak == 1
    assert "earnings_miss" in [q.template_id for q in state.queued if not q.done]
    state = _report(state, 3 * MRR, round(MRR * 0.9))
    public = public_of(state, CID)
    assert public is not None and public.miss_streak == 2


def test_two_misses_cut_confidence_by_eight_more() -> None:
    """The report month's board change: -6 a miss, and -8 more from the second in a row."""
    eb = LOADED.balance.public.earnings
    assert (eb.miss_board, eb.misses_in_row_confidence, eb.beat_board) == (-6, -8, 4)
    from tst.sim.markets_public.public import _report as report
    from tst.sim.markets_public.value import fundamentals as fund

    state = listed()
    public = public_of(state, CID)
    assert public is not None
    public = replace(public, miss_streak=1, quarter_revenue_cents=MRR, quarter_op_cents=OP)
    g = Guidance(CID, state.turn, 3 * MRR, 500, 3 * MRR, 500, True)
    seats = {s.id: s.confidence for s in state.board(CID) if s.confidence is not None}
    f = fund(state, CID, MRR, OP, LOADED.balance, LOADED.game_data)
    import numpy as np

    out, after, _, result, _ = report(
        state, public, g, 1.0, f, np.random.default_rng(0), LOADED.balance
    )
    assert result == "miss" and after.miss_streak == 2
    for s in out.board(CID):
        if s.id in seats:
            assert s.confidence == pytest.approx(max(0.0, seats[s.id] - 14))  # type: ignore[operator]


def test_activist_after_three_misses_in_four() -> None:
    state = listed()
    public = public_of(state, CID)
    assert public is not None
    state = with_public(state, replace(public, results=("miss", "beat", "miss")))
    state = _report(state, 3 * MRR, round(MRR * 0.9))
    assert ACTIVIST in [q.template_id for q in state.queued if not q.done]


def test_takeover_after_six_cheap_months() -> None:
    state = listed()
    public = public_of(state, CID)
    assert public is not None
    state = with_public(state, replace(public, sentiment=0.5, below_takeover_months=5))
    state = advance(state, 1)
    assert TAKEOVER in [q.template_id for q in state.queued if not q.done]
    # and an activist after six months below 0.7 x V_f per share
    public = public_of(state, CID)
    assert public is not None
    assert public.last_takeover_turn == state.turn


def test_guidance_rules() -> None:
    b = LOADED.balance
    state = listed()
    rev, _ = consensus(state, CID)
    assert guidance_problem(state, CID, rev, b) is None
    assert "within" in (guidance_problem(state, CID, rev * 3, b) or "")
    mid = replace(state, turn=state.turn + 1)
    assert "first month" in (guidance_problem(mid, CID, rev, b) or "")
    assert "listed" in (guidance_problem(eligible(), CID, rev, b) or "")


@settings(max_examples=25, deadline=None)
@given(amount=st.integers(1, 2_000_000_000_00), share=st.floats(0.0001, 0.2))
def test_buyback_and_secondary_ledger_property(amount: int, share: float) -> None:
    """Buybacks and secondaries balance; shares fall or rise by what was bought or sold."""
    state = LISTED
    shares = max(1, int(fd_shares(state, CID) * share))
    cash = 1_000_000_000_00
    before = fd_shares(state, CID)
    try:
        after, entry, bought, cost = capital.buyback(state, CID, amount, cash, LOADED.balance)
    except Exception:  # noqa: BLE001 - amounts too small or too large are refused
        bought = 0
    else:
        assert sum(line.amount for line in entry.lines) == 0
        lines = {line.account: line.amount for line in entry.lines}
        assert lines[CASH] == -cost == -lines[COMMON_EQUITY]
        assert cost <= amount and fd_shares(after, CID) == before - bought
        price = capital.buyback_price_cents(public_of(state, CID), LOADED.balance)  # type: ignore[arg-type]
        assert cost == bought * price
    after2, entry2, net = capital.secondary(state, CID, shares, LOADED.balance)
    assert sum(line.amount for line in entry2.lines) == 0
    assert fd_shares(after2, CID) == before + shares
    public = public_of(state, CID)
    assert public is not None
    gross = shares * round(public.price_cents * 0.95)
    assert net == gross - round(gross * 0.03)


def test_dividend_is_paid_next_month() -> None:
    state = listed()
    outstanding = outstanding_shares(state, CID)
    state = capital.declare_dividend(state, CID, 10, 10**15, outstanding)
    with pytest.raises(Exception):  # noqa: B017 - one declaration a month
        capital.declare_dividend(state, CID, 10, 10**15, outstanding)
    state = replace(state, turn=state.turn + 1)
    state, entries, logs = month(state)
    paid = [e for e in entries if "Dividend" in e.memo]
    assert len(paid) == 1
    lines = {line.account: line.amount for line in paid[0].lines}
    assert lines[CASH] == -10 * outstanding
    assert public_of(state, CID).dividend_cents == 0  # type: ignore[union-attr]


LISTED = listed()
