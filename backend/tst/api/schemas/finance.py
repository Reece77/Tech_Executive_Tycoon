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
    gross_margin_cents: int
    operating_expenses: list[StatementLineOut]
    operating_result_cents: int
    interest_cents: int
    tax_cents: int
    net_result_cents: int


class BalanceSheetOut(BaseModel):
    assets: list[StatementLineOut]
    total_assets_cents: int
    liabilities: list[StatementLineOut]
    paid_in_equity: list[StatementLineOut]
    accumulated_result_cents: int = Field(description="Every past net result; no closing entries")
    total_liabilities_and_equity_cents: int


class CashFlowOut(BaseModel):
    operating_cents: int = Field(description="The net result: no accruals in v1")
    investing_cents: int
    financing_cents: int = Field(description="SAFEs and priced rounds")
    change_in_cash_cents: int


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


class CapTableOut(BaseModel):
    fd_shares: int
    share_price_dollars: str = Field(description="Latest priced round's price; '0' before any")
    holders: list[HolderOut] = Field(description="Largest first; options as one line")
    granted_options: int = Field(description="Options held by staff and former staff")
    vested_options: int
    unallocated_options: int
    pool_left_bp: int = Field(description="Unallocated less pending offers, in bp of FD")
    grants: list[GrantOut]


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


class SeriesGuideOut(BaseModel):
    """The next round and whether it is allowed (14.5)."""

    series: str | None = Field(description="Null after Series B (Series C is v2)")
    series_label: str | None
    allowed: bool
    problem: str | None
    typical_min_cents: int | None
    typical_max_cents: int | None
    arr_cents: int = Field(description="ARR at the last month end")
    open_turns: int


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


class SafesOut(BaseModel):
    safes: list[SafeOut] = Field(description="Newest first")
    min_cents: int
    max_cents: int
    open: bool = Field(description="A SAFE raise is waiting for investors' answers")


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


class DirectorOut(BaseModel):
    seat_id: int
    kind: str = Field(description="common | investor | independent")
    person_id: int
    name: str
    firm: str | None
    firm_name: str | None
    confidence: float | None = Field(description="Null for common seats, which back the founder")
    label: str | None = Field(description="confident | watchful | losing patience")
    months_below: int
    seated_label: str


class BoardOut(BaseModel):
    directors: list[DirectorOut]
    average_confidence: float | None
    label: str | None
    warning_below: float
    removal_below: float
    removal_months: int
    votes_to_remove: int = Field(description="Directors below the threshold long enough")
    seats: int


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


class SafeIn(BaseModel):
    amount_cents: int
    cap_cents: int


class RoundIn(BaseModel):
    series: str
    target_cents: int


class FinanceActionOut(BaseModel):
    energy: EnergyOut
    unread_inbox: int
