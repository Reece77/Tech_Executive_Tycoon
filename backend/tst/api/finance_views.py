"""Build finance responses (M4a) from the state, the ledger and the sim's formulas.

Everything shown is allowed by formulas.md 14.9. V_base, a firm's bias and the SAFE
acceptance probability stay inside: the SAFE dialog gets only the hint band.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction

from tst.api.schemas.finance import (
    BalanceSheetOut,
    BoardOut,
    CapTableOut,
    CashFlowOut,
    DilutionLineOut,
    DirectorOut,
    FinanceSummaryOut,
    GrantOut,
    HolderOut,
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
)
from tst.api.views import STAGE_LABELS, person_name
from tst.loader import LoadedData
from tst.sim.calendar import MONTHS_PER_YEAR, format_turn, turn_to_ym
from tst.sim.data_models import AccountType
from tst.sim.errors import FinanceRuleError
from tst.sim.finance import formulas as f
from tst.sim.finance import statements as fs
from tst.sim.finance.board import average_confidence
from tst.sim.finance.captable import fd_shares, last_round, share_price, unallocated
from tst.sim.finance.fundraising import (
    arr_cents,
    base_value,
    next_series,
    plan_close,
    safe_fraction,
    series_problem,
)
from tst.sim.finance.models import POOL_NAME, SAFE_HOLDERS, SERIES_LABELS, FundingRound, TermSheet
from tst.sim.finance.options import pool_left_bp
from tst.sim.hiring.formulas import energy_cost
from tst.sim.money import Cents
from tst.sim.state import GameState

OPTIONS_HOLDER = "Employee options"
PRICE_DECIMALS = 5

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
                        gross_margin_cents=pnl.gross_margin,
                        operating_expenses=_lines(pnl.operating_expenses, names),
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
                    ),
                    balance_sheet=BalanceSheetOut(
                        assets=_lines(sheet.assets, names),
                        total_assets_cents=sheet.total_assets,
                        liabilities=_lines(sheet.liabilities, names),
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


def captable_out(state: GameState, names: Mapping[int, str], data: LoadedData) -> CapTableOut:
    """`names` gives the names of grant holders who may have left (not in the live state)."""
    company = state.player.id
    fd = fd_shares(state, company)
    holders = [
        HolderOut(
            holder=_holder_name(state, e.holder_kind, e.person_id, e.firm, e.name, data),
            holder_kind=e.holder_kind,
            share_class=e.share_class,
            shares=e.shares,
            fraction=e.shares / fd if fd else 0.0,
            person_id=e.person_id,
            firm=e.firm,
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
        grants=[
            GrantOut(
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
            )
            for g in grants
        ],
    )


# --- Rounds and SAFEs ------------------------------------------------------------------------


def _sheet_out(sheet: TermSheet, data: LoadedData) -> TermSheetOut:
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
        term_sheets=[_sheet_out(t, data) for t in state.sheets_of(rnd.id)],
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
            open_turns=data.balance.finance.round.open_turns,
        ),
    )


def safes_out(state: GameState, data: LoadedData) -> SafesOut:
    company = state.player.id
    sb = data.balance.finance.safe
    safes = sorted(state.company_safes(company), key=lambda s: -s.id)
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
            )
            for s in safes
        ],
        min_cents=sb.min_cents,
        max_cents=sb.max_cents,
        open=any(s.status == "pending" for s in safes),
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
    )


# --- Board and summary -----------------------------------------------------------------------


def board_out(state: GameState, data: LoadedData) -> BoardOut:
    company = state.player.id
    bb = data.balance.board
    seats = state.board(company)
    avg = average_confidence(state, company)
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
    )


def summary_out(state: GameState, cash_cents: Cents, data: LoadedData) -> FinanceSummaryOut:
    company = state.player
    burn = fs.projected_net_burn(state, company.id, data.balance, data.game_data)
    runway = fs.projected_runway(state, company.id, cash_cents, data.balance, data.game_data)
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
    )
