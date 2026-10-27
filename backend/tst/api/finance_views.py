"""Build finance responses (M4a) from the state, the ledger and the sim's formulas.

Everything shown is allowed by formulas.md 14.9. V_base, a firm's bias and the SAFE
acceptance probability stay inside: the SAFE dialog gets only the hint band.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from fractions import Fraction

from tst.api.schemas.finance import (
    BalanceSheetOut,
    BoardMeetingOut,
    BoardOut,
    CapTableOut,
    CashFlowOut,
    DilutionLineOut,
    DirectorOut,
    FinanceSummaryOut,
    GameOverDirectorOut,
    GameOverOut,
    GrantOut,
    HolderOut,
    OwnershipEventOut,
    ProfitAndLossOut,
    RoundOut,
    RoundPreviewOut,
    RoundsOut,
    SafeHintOut,
    SafeOut,
    SafesOut,
    SeriesGuideOut,
    StatementLineOut,
    StatementPeriodOut,
    StatementsOut,
    TermSheetOut,
    TimelineItemOut,
)
from tst.api.schemas.saves import FundingTileOut
from tst.api.views import STAGE_LABELS, person_name
from tst.db.inbox import InboxMessage
from tst.loader import LoadedData
from tst.sim.calendar import MONTHS_PER_YEAR, format_turn, turn_to_ym
from tst.sim.data_models import AccountType, FinanceBalance
from tst.sim.errors import FinanceRuleError
from tst.sim.finance import formulas as f
from tst.sim.finance import statements as fs
from tst.sim.finance.board import actual_growth, average_confidence, next_meeting_turn
from tst.sim.finance.captable import (
    closed_rounds,
    fd_shares,
    last_round,
    open_round,
    person_shares,
    share_price,
    unallocated,
)
from tst.sim.finance.fundraising import (
    arr_cents,
    base_value,
    next_series,
    plan_close,
    safe_fraction,
    series_problem,
)
from tst.sim.finance.insolvency import bridge_amount
from tst.sim.finance.models import (
    POOL_NAME,
    SAFE_HOLDERS,
    SERIES_LABELS,
    BoardSeat,
    FundingRound,
    OptionGrant,
    Safe,
    TermSheet,
)
from tst.sim.finance.options import at_cliff, next_vesting, pool_left_bp
from tst.sim.hiring.formulas import energy_cost
from tst.sim.money import Cents
from tst.sim.snapshot import CompanySnapshot
from tst.sim.state import GameState

OPTIONS_HOLDER = "Employee options"
PRICE_DECIMALS = 5
MILLION = 1_000_000
TREND_MIN_POINTS = 2  # month ends needed before a board trend means anything
SAFE_BLOCKED = "Not while a priced round is open."

type Lines = Sequence[tuple[int, str, Cents]]


def dollars(price_cents: Fraction | None) -> str:
    """Cents per share as a decimal string of dollars: 48.936... -> "0.48936"."""
    if price_cents is None:
        return "0"
    return f"{float(price_cents) / 100:.{PRICE_DECIMALS}f}"


# --- Statements ------------------------------------------------------------------------------


def _lines(amounts: Mapping[str, Cents], names: Mapping[str, str]) -> list[StatementLineOut]:
    return [
        StatementLineOut(account=code, label=names.get(code, code), amount_cents=amount)
        for code, amount in sorted(amounts.items())
        if amount
    ]


def _label(period: fs.Period, first: int) -> str:
    year, month = turn_to_ym(first)
    if period == "month":
        return format_turn(first)
    if period == "quarter":
        return f"Q{(month - 1) // fs.QUARTER_MONTHS + 1} {year}"
    return str(year)


def statements_out(
    state: GameState, lines: Lines, period: fs.Period, data: LoadedData
) -> StatementsOut:
    """Every closed month, quarter or year from January 2010, oldest first."""
    types: dict[str, AccountType] = {a.code: a.type for a in data.game_data.accounts}
    names = {a.code: a.name for a in data.game_data.accounts}
    last_closed = state.turn - 1
    periods = []
    if last_closed >= 0:
        size = {"month": 1, "quarter": fs.QUARTER_MONTHS, "year": MONTHS_PER_YEAR}[period]
        for first, last in fs.period_bounds(period, last_closed):
            pnl = fs.profit_and_loss(lines, types, first, last)
            flow = fs.cash_flow(lines, types, first, last)
            sheet = fs.balance_sheet(lines, types, last)
            periods.append(
                StatementPeriodOut(
                    label=_label(period, first),
                    first_turn=first,
                    last_turn=last,
                    complete=last - first + 1 == size,
                    profit_and_loss=ProfitAndLossOut(
                        revenue=_lines(pnl.revenue, names),
                        total_revenue_cents=pnl.total_revenue,
                        cost_of_revenue=_lines(pnl.cost_of_revenue, names),
                        total_cost_of_revenue_cents=sum(pnl.cost_of_revenue.values()),
                        gross_margin_cents=pnl.gross_margin,
                        operating_expenses=_lines(pnl.operating_expenses, names),
                        total_operating_expenses_cents=sum(pnl.operating_expenses.values()),
                        operating_result_cents=pnl.operating_result,
                        interest_cents=pnl.interest,
                        tax_cents=pnl.tax,
                        net_result_cents=pnl.net_result,
                    ),
                    cash_flow=CashFlowOut(
                        operating_cents=flow.operating,
                        investing_cents=flow.investing,
                        financing_cents=flow.financing,
                        change_in_cash_cents=flow.change_in_cash,
                        burn_cents=max(0, -flow.operating),
                    ),
                    balance_sheet=BalanceSheetOut(
                        assets=_lines(sheet.assets, names),
                        total_assets_cents=sheet.total_assets,
                        liabilities=_lines(sheet.liabilities, names),
                        total_liabilities_cents=sum(sheet.liabilities.values()),
                        paid_in_equity=_lines(sheet.paid_in_equity, names),
                        accumulated_result_cents=sheet.accumulated_result,
                        total_liabilities_and_equity_cents=sheet.total_liabilities_and_equity,
                    ),
                )
            )
    return StatementsOut(period=period, periods=periods)


# --- Cap table -------------------------------------------------------------------------------


def _holder_name(
    state: GameState,
    kind: str,
    person_id: int | None,
    firm: str | None,
    name: str | None,
    data: LoadedData,
) -> str:
    if kind == "person" and person_id is not None:
        return person_name(state.person(person_id))
    if kind == "firm" and firm is not None:
        return data.game_data.firm(firm).name
    return name or "Unknown holder"


def _money_short(cents: int) -> str:
    """$500,000 or $2M / $18.3M: amounts in event labels."""
    dollars_ = cents / 100
    if dollars_ < MILLION:
        return f"${dollars_:,.0f}"
    return f"${dollars_ / MILLION:.1f}".removesuffix(".0") + "M"


def ownership_history(state: GameState, data: LoadedData) -> list[OwnershipEventOut]:
    """The founder's share of FD after each SAFE and priced round, oldest first (M4b). A SAFE
    changes nothing until it converts; a round's FD after is FD_pre + N (14.5)."""
    company = state.player.id
    founder = state.founder_of(company)
    if founder is None:
        return []
    shares = person_shares(state, company, founder.id)
    rounds = sorted(closed_rounds(state, company), key=lambda r: (r.closed_turn or 0, r.id))
    founded = state.player.founded_turn
    first = rounds[0] if rounds else None
    start_fd = (
        first.fd_before
        if first is not None and first.closed_turn == founded and first.fd_before
        else data.balance.finance.initial_fd_shares
    )
    events: list[tuple[int, int, OwnershipEventOut]] = []
    events.append(
        (
            founded,
            0,
            OwnershipEventOut(
                turn=founded,
                date_label=format_turn(founded),
                event="founded",
                label="Founded",
                founder_fraction=shares / start_fd,
            ),
        )
    )
    for rnd in rounds:
        if rnd.closed_turn is None or rnd.fd_pre is None or rnd.new_shares is None:
            continue
        pre = rnd.pre_money_cents or 0
        amount = rnd.amount_cents or 0
        lead = data.game_data.firm(rnd.lead_firm).name if rnd.lead_firm else None
        label = f"{SERIES_LABELS[rnd.series]}, {_money_short(amount)} at {_money_short(pre)} pre"
        events.append(
            (
                rnd.closed_turn,
                2,
                OwnershipEventOut(
                    turn=rnd.closed_turn,
                    date_label=format_turn(rnd.closed_turn),
                    event="round",
                    label=f"{label} ({lead})" if lead else label,
                    founder_fraction=shares / (rnd.fd_pre + rnd.new_shares),
                ),
            )
        )
    for safe in state.company_safes(company):
        if safe.status not in ("outstanding", "converted"):
            continue
        turn = safe.resolved_turn if safe.resolved_turn is not None else safe.raised_turn
        name = "Bridge SAFE" if safe.kind == "bridge" else "SAFE"
        events.append(
            (
                turn,
                1,
                OwnershipEventOut(
                    turn=turn,
                    date_label=format_turn(turn),
                    event="safe",
                    label=f"{name}, {_money_short(safe.amount_cents)} at a "
                    f"{_money_short(safe.cap_cents)} cap",
                    founder_fraction=0.0,  # filled below: unchanged until it converts
                    pending=safe.status == "outstanding",
                ),
            )
        )
    events.sort(key=lambda e: (e[0], e[1]))
    out: list[OwnershipEventOut] = []
    for _, _, event in events:
        if event.event == "safe":
            event = event.model_copy(update={"founder_fraction": out[-1].founder_fraction})
        out.append(event)
    return out


def _grant_out(
    g: OptionGrant,
    names: Mapping[int, str],
    staff: set[int],
    fd: int,
    state: GameState,
    fb: FinanceBalance,
) -> GrantOut:
    nxt = next_vesting(g, state.turn, fb)
    return GrantOut(
        person_id=g.person_id,
        name=names.get(g.person_id, f"Person {g.person_id}"),
        on_staff=g.employment_id in staff,
        granted=g.granted,
        vested=g.vested,
        unvested=g.unvested,
        forfeited=g.forfeited,
        start_turn=g.start_turn,
        start_label=format_turn(g.start_turn),
        fraction=g.outstanding / fd if fd else 0.0,
        next_vest_turn=nxt[0] if nxt else None,
        next_vest_label=format_turn(nxt[0]) if nxt else None,
        next_vest_shares=nxt[1] if nxt else 0,
        next_vest_is_cliff=nxt is not None and at_cliff(g, nxt[0], fb),
    )


def grant_out(state: GameState, employment_id: int, name: str, data: LoadedData) -> GrantOut | None:
    """One employee's grant for the profile's contract panel (M4b)."""
    grant = state.grant_for(employment_id)
    if grant is None:
        return None
    staff = {e.id for e in state.staff(state.player.id)}
    fd = fd_shares(state, state.player.id)
    return _grant_out(grant, {grant.person_id: name}, staff, fd, state, data.balance.finance)


def captable_out(state: GameState, names: Mapping[int, str], data: LoadedData) -> CapTableOut:
    """`names` gives the names of grant holders who may have left (not in the live state)."""
    company = state.player.id
    fd = fd_shares(state, company)
    founder = state.founder_of(company)
    founder_id = founder.id if founder is not None else None
    holders = [
        HolderOut(
            holder=_holder_name(state, e.holder_kind, e.person_id, e.firm, e.name, data),
            holder_kind=e.holder_kind,
            share_class=e.share_class,
            shares=e.shares,
            fraction=e.shares / fd if fd else 0.0,
            person_id=e.person_id,
            firm=e.firm,
            is_founder=e.holder_kind == "person" and e.person_id == founder_id,
        )
        for e in state.company_cap(company)
    ]
    grants = state.company_grants(company)
    granted = sum(g.outstanding for g in grants)
    if granted:
        holders.append(
            HolderOut(
                holder=OPTIONS_HOLDER,
                holder_kind="options",
                share_class="option_pool",
                shares=granted,
                fraction=granted / fd if fd else 0.0,
            )
        )
    holders.sort(key=lambda h: (-h.shares, h.holder))
    staff = {e.id for e in state.staff(company)}
    fb = data.balance.finance
    latest = last_round(state, company)
    own = person_shares(state, company, founder_id) if founder_id is not None else 0
    return CapTableOut(
        fd_shares=fd,
        share_price_dollars=dollars(share_price(state, company))
        if last_round(state, company)
        else "0",
        holders=holders,
        granted_options=granted,
        vested_options=sum(g.vested for g in grants),
        unallocated_options=unallocated(state, company),
        pool_left_bp=pool_left_bp(state, company),
        grants=[_grant_out(g, names, staff, fd, state, fb) for g in grants],
        vesting_months=fb.vesting_months,
        cliff_months=fb.cliff_months,
        founder_shares=own,
        founder_fraction=own / fd if fd else 0.0,
        last_round_label=SERIES_LABELS[latest.series] if latest else None,
        last_round_date_label=format_turn(latest.closed_turn)
        if latest and latest.closed_turn is not None
        else None,
        post_money_cents=latest.post_money_cents if latest else None,
        ownership_history=ownership_history(state, data),
    )


# --- Rounds and SAFEs ------------------------------------------------------------------------


def _founder_after(state: GameState, sheet: TermSheet, data: LoadedData) -> float | None:
    """The founder's share of FD if `sheet` closes now, by the closing function (14.5)."""
    company = state.player.id
    founder = state.founder_of(company)
    if founder is None or sheet.status != "offered":
        return None
    try:
        plan = plan_close(state, company, sheet.pre_money_cents, sheet.amount_cents, data.balance)
    except FinanceRuleError:
        return None
    return person_shares(state, company, founder.id) / plan.closing.fd_after


def _sheet_out(state: GameState, sheet: TermSheet, data: LoadedData) -> TermSheetOut:
    return TermSheetOut(
        sheet_id=sheet.id,
        round_id=sheet.round_id,
        firm=sheet.firm,
        firm_name=data.game_data.firm(sheet.firm).name,
        pre_money_cents=sheet.pre_money_cents,
        amount_cents=sheet.amount_cents,
        post_money_cents=sheet.pre_money_cents + sheet.amount_cents,
        status=sheet.status,
        expires_turn=sheet.expires_turn,
        expires_label=format_turn(sheet.expires_turn),
        founder_fraction_after=_founder_after(state, sheet, data),
    )


def _round_out(state: GameState, rnd: FundingRound, data: LoadedData) -> RoundOut:
    return RoundOut(
        round_id=rnd.id,
        series=rnd.series,
        series_label=SERIES_LABELS[rnd.series],
        status=rnd.status,
        target_cents=rnd.target_cents,
        opened_turn=rnd.opened_turn,
        opened_label=format_turn(rnd.opened_turn),
        expires_turn=rnd.expires_turn,
        expires_label=format_turn(rnd.expires_turn),
        lead_firm=rnd.lead_firm,
        lead_name=data.game_data.firm(rnd.lead_firm).name if rnd.lead_firm else None,
        pre_money_cents=rnd.pre_money_cents,
        amount_cents=rnd.amount_cents,
        post_money_cents=rnd.post_money_cents,
        share_price_dollars=dollars(rnd.price) if rnd.price is not None else None,
        pool_shares=rnd.pool_shares,
        safe_shares=rnd.safe_shares,
        new_shares=rnd.new_shares,
        down_round=rnd.down_round,
        closed_turn=rnd.closed_turn,
        closed_label=format_turn(rnd.closed_turn) if rnd.closed_turn is not None else None,
        term_sheets=[_sheet_out(state, t, data) for t in state.sheets_of(rnd.id)],
        firms_asked=sum(1 for firm in data.game_data.investors if rnd.series in firm.series),
    )


def rounds_out(state: GameState, data: LoadedData) -> RoundsOut:
    company = state.player.id
    series = next_series(state, company)
    problem = (
        series_problem(state, company, series or "", data.balance)
        if series
        else ("there is no round after Series B until v2")
    )
    typical = data.balance.finance.round.typical_cents.get(series) if series else None
    return RoundsOut(
        rounds=[
            _round_out(state, r, data)
            for r in sorted(state.company_rounds(company), key=lambda r: -r.id)
        ],
        next=SeriesGuideOut(
            series=series,
            series_label=SERIES_LABELS[series] if series else None,
            allowed=problem is None,
            problem=problem,
            typical_min_cents=int(typical.lo) if typical else None,
            typical_max_cents=int(typical.hi) if typical else None,
            arr_cents=arr_cents(state, company, data.balance),
            gate_arr_cents=data.balance.finance.round.gate_arr_cents.get(series)
            if series
            else None,
            open_turns=data.balance.finance.round.open_turns,
            energy_cost=energy_cost("start_round", data.balance),
        ),
    )


def safes_out(state: GameState, cash_cents: Cents, data: LoadedData) -> SafesOut:
    """An open bridge offer shows the amount it would be if accepted today (14.7, M4b)."""
    company = state.player.id
    sb = data.balance.finance.safe
    safes = [
        replace(
            s, amount_cents=bridge_amount(state, company, cash_cents, data.balance, data.game_data)
        )
        if s.kind == "bridge" and s.status == "offered"
        else s
        for s in sorted(state.company_safes(company), key=lambda s: -s.id)
    ]
    return SafesOut(
        safes=[
            SafeOut(
                safe_id=s.id,
                kind=s.kind,
                amount_cents=s.amount_cents,
                cap_cents=s.cap_cents,
                status=s.status,
                raised_turn=s.raised_turn,
                raised_label=format_turn(s.raised_turn),
                expires_turn=s.expires_turn,
                expires_label=format_turn(s.expires_turn) if s.expires_turn is not None else None,
                fraction=s.amount_cents / s.cap_cents,
                converted_round_id=s.converted_round_id,
            )
            for s in safes
        ],
        min_cents=sb.min_cents,
        max_cents=sb.max_cents,
        open=any(s.status == "pending" for s in safes),
        blocked=SAFE_BLOCKED if open_round(state, company) is not None else None,
        energy_cost=energy_cost("raise_safe", data.balance),
    )


def safe_hint_out(
    state: GameState, amount_cents: int, cap_cents: int, data: LoadedData
) -> SafeHintOut:
    """The hint band and the rule checks; V_base itself never leaves this function."""
    sb = data.balance.finance.safe
    company = state.player.id
    problems = []
    if not sb.min_cents <= amount_cents <= sb.max_cents:
        problems.append(f"a SAFE raises ${sb.min_cents // 100:,} to ${sb.max_cents // 100:,}")
    if cap_cents <= 0:
        problems.append("a valuation cap must be a positive amount")
        return SafeHintOut(
            hint="unlikely",
            fraction=0.0,
            problems=problems,
            energy_cost=energy_cost("raise_safe", data.balance),
        )
    claimed = safe_fraction(state, company) + Fraction(amount_cents, cap_cents)
    if claimed >= Fraction(sb.max_fraction).limit_denominator():
        problems.append("the cap is too low: outstanding SAFEs would claim too much of the company")
    if any(s.status == "pending" for s in state.company_safes(company)):
        problems.append("a SAFE raise is already open")
    hint = f.safe_hint(base_value(state, company, data.balance, data.game_data), cap_cents, sb)
    return SafeHintOut(
        hint=hint,
        fraction=amount_cents / cap_cents,
        problems=problems,
        energy_cost=energy_cost("raise_safe", data.balance),
    )


def round_preview_out(state: GameState, sheet: TermSheet, data: LoadedData) -> RoundPreviewOut:
    """Each holder's shares and percentage before and after accepting `sheet` (14.5)."""
    company = state.player.id
    rnd = state.funding_round(sheet.round_id)
    if rnd is None:
        raise FinanceRuleError(f"no round {sheet.round_id}")
    plan = plan_close(state, company, sheet.pre_money_cents, sheet.amount_cents, data.balance)
    c = plan.closing
    before = captable_out(state, {}, data)
    after_fd = c.fd_after
    lines: list[DilutionLineOut] = []
    for h in before.holders:
        added = c.pool_shares if h.holder_kind == "pool" else 0
        lines.append(
            DilutionLineOut(
                holder=h.holder if h.holder_kind != "pool" else POOL_NAME,
                share_class=h.share_class,
                shares_before=h.shares,
                shares_after=h.shares + added,
                fraction_before=h.fraction,
                fraction_after=(h.shares + added) / after_fd,
                holder_kind=h.holder_kind,
                is_founder=h.is_founder,
            )
        )
    if c.safe_shares:
        lines.append(
            DilutionLineOut(
                holder=SAFE_HOLDERS,
                share_class="safe_conversion",
                shares_before=0,
                shares_after=c.safe_shares,
                fraction_before=0.0,
                fraction_after=c.safe_shares / after_fd,
                holder_kind="group",
                new=True,
            )
        )
    lines.append(
        DilutionLineOut(
            holder=data.game_data.firm(sheet.firm).name,
            share_class=f"preferred_{rnd.series}",
            shares_before=0,
            shares_after=c.new_shares,
            fraction_before=0.0,
            fraction_after=c.new_shares / after_fd,
            holder_kind="firm",
            new=True,
        )
    )
    previous = last_round(state, company)
    rb = data.balance.finance.round
    seats = data.balance.board.seats[rnd.series]
    return RoundPreviewOut(
        sheet_id=sheet.id,
        firm_name=data.game_data.firm(sheet.firm).name,
        pre_money_cents=sheet.pre_money_cents,
        amount_cents=sheet.amount_cents,
        post_money_cents=sheet.pre_money_cents + sheet.amount_cents,
        share_price_dollars=dollars(c.price),
        pool_top_up=c.pool_shares,
        safe_conversion=c.safe_shares,
        new_shares=c.new_shares,
        fd_before=plan.fd_before,
        fd_after=after_fd,
        fees_cents=f.round_fee_cents(sheet.amount_cents, rb.fee_min_cents, rb.fee_bp),
        down_round=previous is not None and previous.price is not None and c.price < previous.price,
        lines=lines,
        board_after={
            "common": seats.common,
            "investor": seats.investor,
            "independent": seats.independent,
        },
        founder_keeps_tie=2 * (seats.investor + seats.independent)
        <= seats.common + seats.investor + seats.independent,
        energy_cost=energy_cost("accept_term_sheet", data.balance),
        series_label=SERIES_LABELS[rnd.series],
    )


# --- Board and summary -----------------------------------------------------------------------


def _trend(seats: Sequence[BoardSeat], trend_points: float) -> tuple[str | None, float | None]:
    """rising, steady or slipping: the voting directors' average now against the oldest
    month end every one of them has in their history."""
    histories = [s.history for s in seats if s.confidence is not None and s.history]
    if not histories:
        return None, None
    span = min(len(h) for h in histories)
    if span < TREND_MIN_POINTS:
        return "steady", None
    start = sum(h[-span] for h in histories) / len(histories)
    end = sum(h[-1] for h in histories) / len(histories)
    if end - start >= trend_points:
        return "rising", start
    if start - end >= trend_points:
        return "slipping", start
    return "steady", start


def board_out(
    state: GameState,
    data: LoadedData,
    meetings: Sequence[InboxMessage] = (),
    warnings: Sequence[InboxMessage] = (),
) -> BoardOut:
    """`meetings` and `warnings` are the board_meeting and board_warning inbox items, newest
    first; the newest meeting is the last one shown."""
    company = state.player.id
    bb = data.balance.board
    seats = state.board(company)
    avg = average_confidence(state, company)
    latest = last_round(state, company)
    founder = state.founder_of(company)
    kinds = {k: sum(1 for s in seats if s.kind == k) for k in ("common", "investor", "independent")}
    trend, trend_from = _trend(seats, bb.trend_points)
    last_meeting = None
    if meetings:
        m = meetings[0]
        warning = next((w for w in warnings if w.turn == m.turn), None)
        last_meeting = BoardMeetingOut(
            turn=m.turn,
            date_label=format_turn(m.turn),
            title=m.title,
            body=m.body,
            previous_title=meetings[1].title if len(meetings) > 1 else None,
            warning_body=warning.body if warning else None,
        )
    return BoardOut(
        directors=[
            DirectorOut(
                seat_id=s.id,
                kind=s.kind,
                person_id=s.person_id,
                name=person_name(state.person(s.person_id)),
                firm=s.firm,
                firm_name=data.game_data.firm(s.firm).name if s.firm else None,
                confidence=s.confidence,
                label=f.confidence_label(s.confidence, bb) if s.confidence is not None else None,
                months_below=s.months_below,
                seated_label=format_turn(s.seated_turn),
                is_founder=founder is not None and s.person_id == founder.id,
                history=list(s.history),
            )
            for s in seats
        ],
        average_confidence=avg,
        label=f.confidence_label(avg, bb) if avg is not None else None,
        warning_below=bb.warning_below,
        removal_below=bb.removal_below,
        removal_months=bb.removal_months,
        votes_to_remove=sum(1 for s in seats if s.votes and s.months_below >= bb.removal_months),
        seats=len(seats),
        seats_by_kind=kinds,
        removal_possible=2 * (kinds["investor"] + kinds["independent"]) > len(seats),
        trend=trend,
        trend_from=trend_from,
        expected_growth=bb.expected_growth[latest.series] if latest else None,
        actual_growth=actual_growth(state, company, data.balance) if latest else None,
        last_round_label=SERIES_LABELS[latest.series] if latest else None,
        next_meeting_label=format_turn(next_meeting_turn(state.turn, bb)) if seats else None,
        last_meeting=last_meeting,
    )


# --- Funding tile and game over (M4b) --------------------------------------------------------

FINANCE_TEMPLATES = (
    "safe_filled",
    "safe_declined",
    "term_sheets_arrived",
    "no_term_sheets",
    "round_lapsed",
    "round_closed",
    "board_meeting",
    "board_warning",
    "founder_removed",
    "insolvent",
    "bridge_offered",
    "bridge_lapsed",
    "bridge_funded",
    "bankrupt",
    "stage_from_funding",
)
CRITICAL_TEMPLATES = ("insolvent", "bankrupt", "founder_removed", "board_warning", "bridge_lapsed")
TIMELINE_MONTHS = 6  # the game over screen's "last six months"


def funding_tile(state: GameState, data: LoadedData) -> FundingTileOut:
    """The Overview's funding tile: last round, post-money, founder ownership, board mood."""
    company = state.player.id
    latest = last_round(state, company)
    founder = state.founder_of(company)
    fd = fd_shares(state, company)
    own = person_shares(state, company, founder.id) if founder is not None else 0
    avg = average_confidence(state, company)
    return FundingTileOut(
        last_round_label=SERIES_LABELS[latest.series] if latest else None,
        last_round_date_label=format_turn(latest.closed_turn)
        if latest and latest.closed_turn is not None
        else None,
        post_money_cents=latest.post_money_cents if latest else None,
        founder_fraction=own / fd if fd else 0.0,
        board_label=f.confidence_label(avg, data.balance.board) if avg is not None else None,
        board_confidence=avg,
        safes_outstanding=sum(1 for s in state.company_safes(company) if s.status == "outstanding"),
    )


def _a(label: str) -> str:
    return f"an {label}" if label[:1].lower() in "aeiou" else f"a {label}"


def funding_summary(state: GameState) -> str | None:
    """'after a SAFE and a seed': the money raised, in words; None without outside money."""
    company = state.player.id
    safes = [s for s in state.company_safes(company) if s.status in ("outstanding", "converted")]
    parts = []
    plain = sum(1 for s in safes if s.kind == "safe")
    bridges = len(safes) - plain
    if plain:
        parts.append("a SAFE" if plain == 1 else f"{plain} SAFEs")
    if bridges:
        parts.append("a bridge" if bridges == 1 else f"{bridges} bridges")
    for rnd in sorted(closed_rounds(state, company), key=lambda r: (r.closed_turn or 0, r.id)):
        parts.append("a seed" if rnd.series == "seed" else _a(SERIES_LABELS[rnd.series]))
    if not parts:
        return None
    words = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    return f"after {words}"


def game_over_out(
    state: GameState,
    cash_cents: Cents,
    snapshots: Sequence[tuple[int, CompanySnapshot]],
    news: Sequence[InboxMessage],
    data: LoadedData,
) -> GameOverOut:
    """How the game ended (ADR-0018). `snapshots` are every month end, oldest first; `news`
    the finance inbox items of the last months, newest first."""
    company = state.player
    meta = state.save_meta
    ended = meta.ended_turn
    last = ended if ended is not None else state.turn - 1
    final = snapshots[-1][1] if snapshots else None
    live = [p for p in state.company_products(company.id) if p.status == "live"]
    customers = sum(s.customers for p in live for s in state.segments_of(p.id))
    fd = fd_shares(state, company.id)
    founder = state.founder_of(company.id)
    own = person_shares(state, company.id, founder.id) if founder is not None else 0
    since = None
    bridge = None
    if meta.game_state == "bankrupt" and ended is not None:
        since = ended - max(company.insolvent_months, 1) + 1
        bridge = next(
            (
                s
                for s in state.company_safes(company.id)
                if s.kind == "bridge" and s.raised_turn >= since
            ),
            None,
        )
    bb = data.balance.board
    first_news = last - TIMELINE_MONTHS + 1
    return GameOverOut(
        game_state=meta.game_state,
        company_name=company.name,
        ended_turn=ended,
        ended_label=format_turn(ended) if ended is not None else None,
        founded_label=format_turn(company.founded_turn),
        months_lasted=max(last - company.founded_turn + 1, 0),
        cash_cents=cash_cents,
        arr_cents=final.arr_cents if final else 0,
        live_products=len(live),
        customers=round(customers),
        peak_headcount=max((s.headcount for _, s in snapshots), default=0),
        final_headcount=final.headcount if final else len(state.staff(company.id)),
        founder_fraction=own / fd if fd else 0.0,
        funding_summary=funding_summary(state),
        insolvent_from_label=format_turn(since) if since is not None else None,
        bridge_offered_cents=bridge.amount_cents if bridge else None,
        # Not accepted by the last turn it was open (at bankruptcy it has not formally lapsed yet).
        bridge_lapsed=bridge is not None and bridge.status in ("offered", "lapsed"),
        timeline=[
            TimelineItemOut(
                turn=m.turn,
                date_label=format_turn(m.turn),
                template=m.template,
                title=m.title,
                critical=m.template in CRITICAL_TEMPLATES,
            )
            for m in sorted(news, key=lambda m: (m.turn, m.id))
            if m.turn >= first_news
        ],
        directors=[
            GameOverDirectorOut(
                name=person_name(state.person(s.person_id)),
                firm_name=data.game_data.firm(s.firm).name if s.firm else None,
                kind=s.kind,
                confidence=s.confidence,
                history=list(s.history),
                voted=s.votes and s.months_below >= bb.removal_months,
            )
            for s in state.board(company.id)
            if s.votes
        ],
    )


def open_bridge(state: GameState) -> Safe | None:
    """A bridge offer the player can still accept this turn (14.7)."""
    for s in state.company_safes(state.player.id):
        if s.kind == "bridge" and s.status == "offered" and state.turn <= (s.expires_turn or 0):
            return s
    return None


def summary_out(state: GameState, cash_cents: Cents, data: LoadedData) -> FinanceSummaryOut:
    company = state.player
    burn = fs.projected_net_burn(state, company.id, data.balance, data.game_data)
    runway = fs.projected_runway(state, company.id, cash_cents, data.balance, data.game_data)
    bridge = open_bridge(state)
    return FinanceSummaryOut(
        cash_cents=cash_cents,
        projected_net_burn_cents=burn,
        runway_months=runway,
        profitable=burn <= 0,
        insolvent_months=company.insolvent_months,
        game_state=state.save_meta.game_state,
        ended_turn=state.save_meta.ended_turn,
        stage=company.stage,
        stage_label=STAGE_LABELS.get(company.stage, f"Stage {company.stage}"),
        open_bridge_id=bridge.id if bridge else None,
        open_bridge_amount_cents=bridge_amount(
            state, company.id, cash_cents, data.balance, data.game_data
        )
        if bridge
        else None,
        open_bridge_expires_label=format_turn(bridge.expires_turn)
        if bridge and bridge.expires_turn is not None
        else None,
        bridge_energy=energy_cost("accept_bridge", data.balance),
    )
