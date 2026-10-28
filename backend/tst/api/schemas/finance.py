"""Finance schemas (M4a, docs/formulas.md 14.9).

What the API may show: statements, the full cap table (holders, classes, shares, percentages,
vesting per employee), rounds and their terms, term sheets with each firm's quoted
valuation, board seats and directors, confidence as a label and a number, and the runway.
Never V_base, a firm's bias or valuation noise, or the SAFE acceptance probability; the SAFE
dialog gets only a hint band.

Money is integer cents. Share prices are fractions of a cent, so they travel as a decimal
string of dollars (e.g. "0.48936"), formatted, never computed, by the front end.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class StatementLineOut(BaseModel):
    account: str
    label: str
    amount_cents: int


class ProfitAndLossOut(BaseModel):
    revenue: list[StatementLineOut]
    total_revenue_cents: int
    cost_of_revenue: list[StatementLineOut] = Field(description="Hosting (6300) sits here")
    total_cost_of_revenue_cents: int
    gross_margin_cents: int
    operating_expenses: list[StatementLineOut]
    total_operating_expenses_cents: int
    operating_result_cents: int
    interest_cents: int
    tax_cents: int
    net_result_cents: int


class BalanceSheetOut(BaseModel):
    assets: list[StatementLineOut]
    total_assets_cents: int
    liabilities: list[StatementLineOut]
    total_liabilities_cents: int
    paid_in_equity: list[StatementLineOut]
    accumulated_result_cents: int = Field(description="Every past net result; no closing entries")
    total_liabilities_and_equity_cents: int


class CashFlowOut(BaseModel):
    operating_cents: int = Field(description="The net result: no accruals in v1")
    investing_cents: int
    financing_cents: int = Field(description="SAFEs and priced rounds")
    change_in_cash_cents: int
    burn_cents: int = Field(description="-(operating) when negative, else 0 (14.1)")


class StatementPeriodOut(BaseModel):
    label: str = Field(description="Jan 2010, Q1 2010 or 2010")
    first_turn: int
    last_turn: int
    complete: bool = Field(description="False for a period still in progress")
    profit_and_loss: ProfitAndLossOut
    cash_flow: CashFlowOut
    balance_sheet: BalanceSheetOut = Field(description="At the period's last closed month end")


class StatementsOut(BaseModel):
    period: str = Field(description="month | quarter | year")
    periods: list[StatementPeriodOut] = Field(description="Oldest first")


class HolderOut(BaseModel):
    holder: str = Field(description="Who holds the shares, by name")
    holder_kind: str = Field(description="person | firm | group | pool | options")
    share_class: str
    shares: int
    fraction: float = Field(description="Share of fully diluted shares, 0-1")
    person_id: int | None = None
    firm: str | None = None
    is_founder: bool = False


class OwnershipEventOut(BaseModel):
    """One step of "your ownership over time" (M4b)."""

    turn: int
    date_label: str
    event: str = Field(description="founded | safe | round")
    label: str = Field(description="e.g. 'Seed, $2M at $6M pre'")
    founder_fraction: float = Field(description="The founder's share of FD after the event")
    pending: bool = Field(
        default=False, description="A SAFE not yet converted: it dilutes at the next round"
    )


class GrantOut(BaseModel):
    person_id: int
    name: str
    on_staff: bool
    granted: int
    vested: int
    unvested: int
    forfeited: int
    start_turn: int
    start_label: str
    fraction: float = Field(description="Options held (granted - forfeited) over FD")
    next_vest_turn: int | None = Field(
        default=None, description="Month end that next vests more; null once fully vested"
    )
    next_vest_label: str | None = None
    next_vest_shares: int = 0
    next_vest_is_cliff: bool = Field(default=False, description="The next vesting is the cliff")


class CapTableOut(BaseModel):
    fd_shares: int
    share_price_dollars: str = Field(description="Latest priced round's price; '0' before any")
    holders: list[HolderOut] = Field(description="Largest first; options as one line")
    granted_options: int = Field(description="Options held by staff and former staff")
    vested_options: int
    unallocated_options: int
    pool_left_bp: int = Field(description="Unallocated less pending offers, in bp of FD")
    grants: list[GrantOut]
    vesting_months: int
    cliff_months: int
    founder_shares: int
    founder_fraction: float
    last_round_label: str | None = Field(description="Series of the latest priced round")
    last_round_date_label: str | None
    post_money_cents: int | None = Field(description="The latest priced round's post-money")
    ownership_history: list[OwnershipEventOut] = Field(description="Oldest first")


class TermSheetOut(BaseModel):
    sheet_id: int
    round_id: int
    firm: str
    firm_name: str
    pre_money_cents: int = Field(description="The firm's quoted pre-money valuation")
    amount_cents: int
    post_money_cents: int
    status: str
    expires_turn: int
    expires_label: str
    founder_fraction_after: float | None = Field(
        default=None, description="The founder's share of FD if this sheet closes (open sheets)"
    )


class RoundOut(BaseModel):
    round_id: int
    series: str
    series_label: str
    status: str
    target_cents: int
    opened_turn: int
    opened_label: str
    expires_turn: int
    expires_label: str
    lead_firm: str | None
    lead_name: str | None
    pre_money_cents: int | None
    amount_cents: int | None
    post_money_cents: int | None
    share_price_dollars: str | None
    pool_shares: int | None
    safe_shares: int | None
    new_shares: int | None
    down_round: bool
    closed_turn: int | None
    closed_label: str | None
    term_sheets: list[TermSheetOut]
    firms_asked: int = Field(description="Firms in investors.yaml that invest in this series")


class SeriesGuideOut(BaseModel):
    """The next round and whether it is allowed (14.5)."""

    series: str | None = Field(description="Null after Series B (Series C is v2)")
    series_label: str | None
    allowed: bool
    problem: str | None
    typical_min_cents: int | None
    typical_max_cents: int | None
    arr_cents: int = Field(description="ARR at the last month end")
    gate_arr_cents: int | None = Field(description="ARR the series needs; null for a seed")
    open_turns: int
    energy_cost: int


class RoundsOut(BaseModel):
    rounds: list[RoundOut] = Field(description="Newest first")
    next: SeriesGuideOut


class SafeOut(BaseModel):
    safe_id: int
    kind: str = Field(description="safe | bridge")
    amount_cents: int
    cap_cents: int = Field(description="Post-money valuation cap")
    status: str
    raised_turn: int
    raised_label: str
    expires_turn: int | None
    expires_label: str | None
    fraction: float = Field(description="amount / cap: what the holders get at the next round")
    converted_round_id: int | None = None


class SafesOut(BaseModel):
    safes: list[SafeOut] = Field(description="Newest first")
    min_cents: int
    max_cents: int
    open: bool = Field(description="A SAFE raise is waiting for investors' answers")
    blocked: str | None = Field(
        default=None, description="Why a SAFE cannot be raised now (a priced round is open)"
    )
    energy_cost: int


class SafeHintOut(BaseModel):
    """The SAFE dialog's band (14.9); never the probability."""

    hint: str = Field(description="likely | uncertain | unlikely")
    fraction: float = Field(description="amount / cap of the company the holders would get")
    problems: list[str]
    energy_cost: int


class DilutionLineOut(BaseModel):
    holder: str
    share_class: str
    shares_before: int
    shares_after: int
    fraction_before: float
    fraction_after: float
    holder_kind: str = Field(description="person | firm | group | pool | options")
    is_founder: bool = False
    new: bool = Field(default=False, description="A holder this round adds")


class RoundPreviewOut(BaseModel):
    """Accepting this term sheet: every holder before and after the close (14.5)."""

    sheet_id: int
    firm_name: str
    pre_money_cents: int
    amount_cents: int
    post_money_cents: int
    share_price_dollars: str
    pool_top_up: int = Field(description="X: new pool shares")
    safe_conversion: int = Field(description="C: shares the SAFE holders receive")
    new_shares: int = Field(description="N: the investor's new preferred shares")
    fd_before: int
    fd_after: int
    fees_cents: int
    down_round: bool
    lines: list[DilutionLineOut]
    board_after: dict[str, int] = Field(description="Seats by kind after the close")
    founder_keeps_tie: bool = Field(
        description="After the close the common seats are at least half: the founder cannot"
        " be removed (14.6)"
    )
    energy_cost: int
    series_label: str
    nominee_required: bool = Field(
        description="Accepting adds a common seat for the founder's nominee (M4c)"
    )
    nominee_choices: list[NomineeChoiceOut] = Field(
        description="Employees to choose from, most senior first; empty unless required (M4c)"
    )


class AcceptSheetIn(BaseModel):
    nominee_id: int | None = Field(
        default=None, description="The board nominee where the round adds a common seat (M4c)"
    )


class NomineeIn(BaseModel):
    person_id: int


class DirectorOut(BaseModel):
    seat_id: int
    kind: str = Field(description="common | investor | independent")
    person_id: int | None = Field(description="Null for an empty common seat (M4c)")
    name: str
    vacant: bool = Field(description="An empty common seat (M4c)")
    is_employee: bool = Field(
        description="The founder or a nominee on staff: opens the person's profile; anyone "
        "else opens the board-member card (M4c)",
    )
    firm: str | None
    firm_name: str | None
    confidence: float | None = Field(description="Null for common seats, which back the founder")
    label: str | None = Field(description="confident | watchful | losing patience")
    months_below: int
    seated_label: str
    is_founder: bool = False
    history: list[float] = Field(description="Confidence at the last month ends, oldest first")


class NomineeChoiceOut(BaseModel):
    """An employee who could take a common board seat (M4c)."""

    person_id: int
    name: str
    role_label: str
    level: str
    default: bool = Field(description="The most senior: the preselected choice")


class BoardMeetingOut(BaseModel):
    """The last quarterly board meeting, from the inbox (14.6)."""

    turn: int
    date_label: str
    title: str
    body: str
    previous_title: str | None = Field(description="The meeting before, for the change")
    warning_body: str | None = Field(description="The formal warning given at this meeting")


class BoardOut(BaseModel):
    directors: list[DirectorOut]
    average_confidence: float | None
    label: str | None
    warning_below: float
    removal_below: float
    removal_months: int
    votes_to_remove: int = Field(description="Directors below the threshold long enough")
    seats: int
    seats_by_kind: dict[str, int]
    removal_possible: bool = Field(
        description="Investor and independent seats are a majority (after Series B)"
    )
    trend: str | None = Field(
        description="rising | steady | slipping: the average over the last month ends"
    )
    trend_from: float | None = Field(description="The average confidence the trend starts at")
    expected_growth: float | None = Field(
        description="Annual MRR growth the board expects after the last round"
    )
    actual_growth: float | None = Field(
        description="Annualized 6-month MRR growth; null with under 6 months of revenue"
    )
    last_round_label: str | None
    next_meeting_label: str | None
    last_meeting: BoardMeetingOut | None
    nominee_energy: int = Field(description="Energy to name a nominee to an empty seat (M4c)")
    nominee_choices: list[NomineeChoiceOut] = Field(
        description="Employees who could take a common seat, most senior first (M4c)"
    )


class TimelineItemOut(BaseModel):
    turn: int
    date_label: str
    template: str
    title: str
    critical: bool = Field(description="Insolvency, bankruptcy, removal and warnings")


class FinanceSummaryOut(BaseModel):
    cash_cents: int
    projected_net_burn_cents: int = Field(description="This month's costs minus revenue")
    runway_months: int | None = Field(description="Null means profitable")
    profitable: bool
    insolvent_months: int
    game_state: str = Field(description="active | bankrupt | founder_removed")
    ended_turn: int | None
    stage: int
    stage_label: str
    open_bridge_id: int | None = Field(description="A bridge offer that can still be accepted")
    open_bridge_amount_cents: int | None = Field(
        description="What the open bridge would raise if accepted now"
    )
    open_bridge_expires_label: str | None
    bridge_energy: int


class GameOverDirectorOut(BaseModel):
    name: str
    firm_name: str | None
    kind: str
    confidence: float | None
    history: list[float]
    voted: bool = Field(description="Below the threshold long enough to vote for removal")


class GameOverOut(BaseModel):
    """How the game ended (ADR-0018), for the game over screen."""

    game_state: str = Field(description="active | bankrupt | founder_removed")
    company_name: str
    ended_turn: int | None
    ended_label: str | None
    founded_label: str
    months_lasted: int
    cash_cents: int
    arr_cents: int
    live_products: int
    customers: int
    peak_headcount: int
    final_headcount: int
    founder_fraction: float
    funding_summary: str | None = Field(description="e.g. 'after a SAFE and a seed'")
    insolvent_from_label: str | None = Field(description="First month of the last insolvency")
    bridge_offered_cents: int | None = Field(description="A bridge offered in that insolvency")
    bridge_lapsed: bool = Field(description="That bridge was never accepted")
    timeline: list[TimelineItemOut] = Field(description="Finance news of the last six months")
    directors: list[GameOverDirectorOut] = Field(description="The board at the end")


class SafeIn(BaseModel):
    amount_cents: int
    cap_cents: int


class RoundIn(BaseModel):
    series: str
    target_cents: int


class FinanceActionOut(BaseModel):
    energy: EnergyOut
    unread_inbox: int
