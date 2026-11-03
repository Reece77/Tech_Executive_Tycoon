"""Phase 7 for public companies (docs/formulas.md 25.2-25.5, 25.7): the IPO chain's demand
draw and listing, then each listed company's month: a declared dividend is paid, the quarter's
guidance defaults to the consensus, sentiment moves (stream `market_sentiment`, key
(company_id,)), earnings are reported at quarter end, analysts rate, and activists and
takeover interest trigger. Companies with no listing cost nothing here."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

import numpy as np

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.finance import macro
from tst.sim.finance.board import _add_seat, average_confidence
from tst.sim.ledger import CASH, COMMON_EQUITY, GENERAL_ADMIN, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.markets_public import capital, ipo
from tst.sim.markets_public import formulas as pf
from tst.sim.markets_public.models import Analyst, Guidance, PublicCompany, ShareMonth
from tst.sim.markets_public.value import (
    MONTHS_A_YEAR,
    Fundamentals,
    fundamentals,
    growth_of,
)
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    ceo_of,
    guidance_for,
    listing_of,
    player_companies,
    public_of,
    with_ceo,
    with_guidance,
    with_public,
    with_seat,
    with_share_month,
)

EARNINGS_MISS = "earnings_miss"
ACTIVIST = "activist_stake"
TAKEOVER = "takeover_bid"
CEO_VOTE = "ceo_vote"
RESULTS_KEPT = 8  # tunable-exempt: two years of reports, enough for any trigger window
QUARTER = ipo.QUARTER_MONTHS


def outstanding_shares(state: GameState, company_id: int) -> int:
    """Issued shares (the unallocated pool and unexercised options are not): dividends."""
    return sum(e.shares for e in state.company_cap(company_id) if e.holder_kind != "pool")


def public_float(state: GameState, company_id: int) -> int:
    return sum(
        e.shares
        for e in state.company_cap(company_id)
        if e.holder_kind == "group" and e.name == ipo.PUBLIC_HOLDERS
    )


# --- Consensus (25.4) ------------------------------------------------------------------------


def consensus(state: GameState, company_id: int) -> tuple[int, int]:
    """The analysts' consensus for the quarter that starts now, from the last month ends: the
    last quarter's revenue grown at the trailing trend, and the trailing year's margin (bp)."""
    company = state.company(company_id)
    history = company.mrr_history
    last_quarter = sum(history[-QUARTER:])
    if len(history) > 1:
        g = growth_of(replace(company, mrr_history=history[:-1]), history[-1])
    else:
        g = 0.0
    quarterly = (1 + max(g, -0.99)) ** (QUARTER / MONTHS_A_YEAR) - 1  # tunable-exempt: guard
    revenue = round(last_quarter * (1 + quarterly))
    ops = company.op_history[-MONTHS_A_YEAR:]
    revs = history[-len(ops) :] if ops else ()
    margin = pf.margin_bp(sum(ops), sum(revs)) if ops else 0
    return revenue, margin


def guidance_problem(
    state: GameState, company_id: int, revenue_cents: int, balance: Balance
) -> str | None:
    """Why guidance cannot be set now (25.4): only once listed, in a quarter's first month,
    for that quarter, and near enough to the consensus."""
    public = public_of(state, company_id)
    if public is None:
        return "only a listed company gives guidance"
    if state.turn % QUARTER:
        return "guidance is set in a quarter's first month"
    if state.turn <= public.listed_turn:
        return "guidance starts with the first full quarter after listing"
    base, _ = consensus(state, company_id)
    band = balance.public.earnings.guidance_band
    if base > 0 and not base * (1 - band) <= revenue_cents <= base * (1 + band):
        return f"guided revenue must lie within {band:.0%} of the consensus"
    if revenue_cents <= 0:
        return "guided revenue must be positive"
    return None


# --- The phase ---------------------------------------------------------------------------------


def public_month(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    revenue: Mapping[int, int],
    op: Mapping[int, int],
    cash: Mapping[int, int],
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for company in player_companies(state):
        cid = company.id
        listing = listing_of(state, cid)
        public = public_of(state, cid)
        if public is None and (listing is None or not listing.active):
            continue
        f = fundamentals(state, cid, revenue.get(cid, 0), op.get(cid, 0), balance, data)
        if public is None and listing is not None:
            if ipo.roadshow_done(listing) and listing.demand is None:
                climate = macro.venture_climate(state, data)
                d = ipo.draw_demand(rng, state.turn, cid, climate, balance)
                state = ipo.open_pricing(state, cid, f, d, balance, data)
            elif listing.status == "priced":
                gen = rng.stream(state.turn, "market_sentiment", cid)
                state, posted, logged = ipo.list_company(state, cid, f, gen, rng, balance, data)
                entries += posted
                logs += logged
            continue
        assert public is not None
        gen = rng.stream(state.turn, "market_sentiment", cid)
        state, public, posted, logged = _pending(
            state, public, cash.get(cid, 0), rng, balance, data
        )
        entries += posted
        logs += logged
        f = fundamentals(state, cid, revenue.get(cid, 0), op.get(cid, 0), balance, data)
        state, posted, logged = _listed_month(
            state, public, f, revenue.get(cid, 0), op.get(cid, 0), gen, balance
        )
        entries += posted
        logs += logged
    return state, tuple(entries), tuple(logs)


def _listed_month(
    state: GameState,
    public: PublicCompany,
    f: Fundamentals,
    revenue: int,
    op: int,
    gen: np.random.Generator,
    balance: Balance,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    pb = balance.public
    cid, turn = public.company_id, state.turn
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    z = float(gen.standard_normal())  # the month's sentiment shock, drawn first
    if public.dividend_cents > 0:  # 25.5: declared last month, paid now
        total = public.dividend_cents * outstanding_shares(state, cid)
        if total > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=cid,
                    memo=f"Dividend: ${public.dividend_cents / pf.PCT:,.2f} a share",
                    debit=COMMON_EQUITY,
                    credit=CASH,
                    amount=total,
                )
            )
            logs.append(inbox_item(turn, cid, "dividend_paid", amount_cents=total))
        public = replace(public, dividend_cents=0)
    start = ipo.quarter_start(turn)
    if turn == start:  # a new quarter: its guidance defaults to the consensus (25.4)
        public = replace(public, quarter_revenue_cents=0, quarter_op_cents=0)
        if guidance_for(state, cid, start) is None:
            rev, margin = consensus(state, cid)
            state = with_guidance(state, Guidance(cid, start, rev, margin, rev, margin, False))
    public = replace(
        public,
        quarter_revenue_cents=public.quarter_revenue_cents + revenue,
        quarter_op_cents=public.quarter_op_cents + op,
    )
    sentiment = pf.sentiment_step(public.sentiment, z, pb.sentiment)
    shares = f.shares
    per_share = f.per_share_cents
    mark = ""
    g = guidance_for(state, cid, start)
    if turn == start + QUARTER - 1 and g is not None and not g.reported:
        state, public, sentiment, mark, report_logs = _report(
            state, public, g, sentiment, f, gen, balance
        )
        logs += report_logs
    price = pf.share_price_cents(f.value_cents, shares, sentiment)
    analysts = tuple(
        replace(a, rating=pf.rating(a.target_cents, price, pb.analysts)) for a in public.analysts
    )
    public = replace(
        public, sentiment=sentiment, price_cents=price, value_cents=f.value_cents, analysts=analysts
    )
    if mark:
        g2 = guidance_for(state, cid, start)
        assert g2 is not None
        state = with_guidance(state, replace(g2, price_after_cents=price))
    state, public, trigger_logs = _triggers(state, public, per_share, balance)
    logs += trigger_logs
    state, public = _lapse_investor_seats(state, public, balance)
    state = with_public(state, public)
    state = with_share_month(state, ShareMonth(cid, turn, price, shares, mark))
    keep = turn - pb.history_months
    state = replace(state, share_months=tuple(m for m in state.share_months if m.turn > keep))
    state, ceo_logs = _ceo_board(state, cid, balance)
    logs += ceo_logs
    return state, entries, logs


def _report(
    state: GameState,
    public: PublicCompany,
    g: Guidance,
    sentiment: float,
    f: Fundamentals,
    gen: np.random.Generator,
    balance: Balance,
) -> tuple[GameState, PublicCompany, float, str, list[LogItem]]:
    """The quarter's report against guidance (25.4, 25.7)."""
    eb = balance.public.earnings
    cid, turn = public.company_id, state.turn
    actual = public.quarter_revenue_cents
    margin = pf.margin_bp(public.quarter_op_cents, actual)
    s = pf.surprise(actual, g.revenue_cents)
    sm = pf.margin_surprise_points(margin, g.margin_bp)
    jump = pf.earnings_jump(s, sm, eb)
    result = pf.result_of(s, eb)
    sentiment = sentiment * (1 + jump)
    beats = public.beat_streak + 1 if result == "beat" else 0
    misses = public.miss_streak + 1 if result == "miss" else 0
    if result == "beat" and beats % eb.beat_streak == 0:
        sentiment += eb.beat_streak_sentiment
    sentiment = balance.public.sentiment.bounds.clamp(sentiment)
    board = {"beat": eb.beat_board, "miss": eb.miss_board, "inline": 0.0}[result]
    if result == "miss" and misses >= eb.misses_in_row:
        board += eb.misses_in_row_confidence
    if board:
        for seat in state.board(cid):
            if seat.confidence is not None:
                value = max(0.0, min(float(pf.PCT), seat.confidence + board))
                state = with_seat(state, replace(seat, confidence=value))
    ab = balance.public.analysts
    cap = public.price_cents * f.shares
    per_share = f.per_share_cents
    analysts = []
    for i in range(pf.analyst_count(cap, ab)):  # targets refresh after each report (25.3)
        target = max(1, round(per_share * (1 + ab.target_sd * float(gen.standard_normal()))))
        analysts.append(Analyst(i, target, "hold"))  # rated below, against the new price
    public = replace(
        public,
        beat_streak=beats,
        miss_streak=misses,
        results=(*public.results, result)[-RESULTS_KEPT:],
        analysts=tuple(analysts),
    )
    state = with_guidance(
        state,
        replace(
            g,
            actual_revenue_cents=actual,
            actual_margin_bp=margin,
            result=result,
            price_before_cents=public.price_cents,
        ),
    )
    logs = [
        inbox_item(
            turn,
            cid,
            "earnings_report",
            link_kind="finance",
            result=result,
            actual_cents=actual,
            guided_cents=g.revenue_cents,
            surprise=f"{s:+.1%}",
            margin=f"{margin / pf.PCT:.1f}%",
            guided_margin=f"{g.margin_bp / pf.PCT:.1f}%",
        )
    ]
    if result == "miss":
        state = ipo.queue_public(state, cid, EARNINGS_MISS, turn + 1)
    return state, public, sentiment, result, logs


def _triggers(
    state: GameState, public: PublicCompany, per_share: int, balance: Balance
) -> tuple[GameState, PublicCompany, list[LogItem]]:
    """Activists and takeover interest (25.4). The thresholds are never shown (25.8)."""
    pb = balance.public
    at, tt = pb.activist_trigger, pb.takeover_trigger
    turn, cid = state.turn, public.company_id
    price = public.price_cents
    below = public.below_value_months + 1 if price < at.value_share * per_share else 0
    cheap = public.below_takeover_months + 1 if price < tt.value_share * per_share else 0
    public = replace(public, below_value_months=below, below_takeover_months=cheap)
    recent = public.results[-(at.window_quarters or 1) :]
    misses = sum(1 for r in recent if r == "miss")
    if (below >= at.months or (at.misses is not None and misses >= at.misses)) and (
        public.last_activist_turn is None or turn - public.last_activist_turn >= at.gap_months
    ):
        state = ipo.queue_public(state, cid, ACTIVIST, turn + 1)
        public = replace(public, last_activist_turn=turn, below_value_months=0)
    if cheap >= tt.months and (
        public.last_takeover_turn is None or turn - public.last_takeover_turn >= tt.gap_months
    ):
        state = ipo.queue_public(state, cid, TAKEOVER, turn + 1)
        public = replace(public, last_takeover_turn=turn, below_takeover_months=0)
    return state, public, []


def _lapse_investor_seats(
    state: GameState, public: PublicCompany, balance: Balance
) -> tuple[GameState, PublicCompany]:
    """One investor seat lapses each year after listing as funds sell (25.7): its director
    stays on as an independent, without the fund's patience (M13 decision)."""
    due = (state.turn - public.listed_turn) // balance.public.board.investor_lapse_months
    while public.lapsed_seats < due:
        seats = [s for s in state.board(public.company_id) if s.kind == "investor"]
        if not seats:
            break
        seat = min(seats, key=lambda s: (s.seated_turn, s.id))
        state = with_seat(state, replace(seat, kind="independent", firm=None))
        public = replace(public, lapsed_seats=public.lapsed_seats + 1)
    return state, public


def _ceo_board(
    state: GameState, company_id: int, balance: Balance
) -> tuple[GameState, list[LogItem]]:
    """With confidence below 30 for 3 months, directors may vote to replace the CEO: an event
    (25.6)."""
    ceo = ceo_of(state, company_id)
    if ceo is None:
        return state, []
    rb = balance.ceo.replace
    avg = average_confidence(state, company_id)
    low = ceo.low_months + 1 if avg is not None and avg < rb.below else 0
    if low >= rb.months:
        state = ipo.queue_public(state, company_id, CEO_VOTE, state.turn + 1)
        low = 0
    return with_ceo(state, replace(ceo, low_months=low)), []


# --- Event choices (25.4, 25.6) ----------------------------------------------------------------


def apply_public_step(
    state: GameState, company_id: int, step: str, balance: Balance
) -> tuple[GameState, list[LogItem]]:
    """An activist, takeover or CEO-vote choice. Those that need cash or a draw wait for the
    next phase 7 (`pending`)."""
    public = public_of(state, company_id)
    logs: list[LogItem] = []
    if step in ("activist_seat", "activist_buyback", "activist_fight") and public is not None:
        state = with_public(state, replace(public, pending=(*public.pending, step)))
    elif step == "takeover_talks" and public is not None:
        tb = balance.public.takeover
        bounds = balance.public.sentiment.bounds
        sentiment = bounds.clamp(public.sentiment * (1 + tb.premium * tb.talks_share))
        state = with_public(state, replace(public, sentiment=sentiment))
    elif step == "ceo_replace":
        ceo = ceo_of(state, company_id)
        if ceo is not None:
            state = with_ceo(state, replace(ceo, ended_turn=state.turn, end_reason="replaced"))
            person = state.person(ceo.person_id)
            logs.append(
                inbox_item(
                    state.turn,
                    company_id,
                    "ceo_replaced",
                    name=f"{person.first_name} {person.last_name}",
                )
            )
    elif step == "ceo_keep":
        ceo = ceo_of(state, company_id)
        if ceo is not None:
            state = with_ceo(state, replace(ceo, low_months=0))
    # takeover_reject: the template's board effect is all (acquisitions are M14)
    return state, logs


def _pending(
    state: GameState,
    public: PublicCompany,
    cash: int,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, PublicCompany, list[LedgerEntry], list[LogItem]]:
    """Activist choices taken last month (25.4): a seat, a buyback or a proxy fight."""
    if not public.pending:
        return state, public, [], []
    ab = balance.public.activist
    cid = public.company_id
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for step in public.pending:
        if step == "activist_seat":
            for _ in range(ab.board_seats):
                state = _add_seat(state, cid, "investor", rng, balance, data, round_id=None)
        elif step == "activist_buyback":
            amount = round(max(cash, 0) * ab.buyback_cash_share)
            try:
                state, posted, shares, cost = capital.buyback(state, cid, amount, cash, balance)
            except InvalidActionError:
                continue
            entries.append(posted)
            cash -= cost
            logs.append(
                inbox_item(state.turn, cid, "buyback_done", shares=shares, amount_cents=cost)
            )
        elif step == "activist_fight":
            cost = round(max(cash, 0) * ab.settle_cash_share)
            if cost > 0:
                entries.append(
                    LedgerEntry.transfer(
                        turn=state.turn,
                        company_id=cid,
                        memo="Proxy fight: advisers and solicitation",
                        debit=GENERAL_ADMIN,
                        credit=CASH,
                        amount=cost,
                    )
                )
                cash -= cost
    public = replace(public_of(state, cid) or public, pending=())
    return with_public(state, public), public, entries, logs
