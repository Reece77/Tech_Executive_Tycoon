"""The Regulation API (M34, docs/formulas.md 48.6): regulators, rules and their dates,
designations and the thresholds, duties, investigations and their stages, rulings, fines,
warnings, and odds as ranges. Never an investigation's draw or chance, a stage's drawn end, a
regulator's strictness path, or a future rule before it is announced."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class RegimeOut(BaseModel):
    key: str
    name: str
    in_force: str = Field(description="The month it took effect")
    users_share: float | None = Field(description="Users test: share of the part's users")
    turnover_cents: int | None = Field(description="Turnover test, US cents a year")
    turnover_scope: Literal["region", "world"]
    market_value_cents: int | None = Field(description="Market value test, US cents")
    turnover_game_cents: int | None = Field(description="The turnover test in the game's economy")
    market_value_game_cents: int | None = Field(description="The value test in the game's economy")
    comply_months: int
    duties: list[str]
    max_fine_share: float
    repeat_fine_share: float


class RegulatorOut(BaseModel):
    key: str
    name: str
    region: str
    region_label: str
    part: str | None
    structural: bool = Field(description="Its law allows a break-up or unbundling")
    regime: RegimeOut | None


class TestOut(BaseModel):
    """The player's own position against a regime's thresholds (Explain on thresholds)."""

    regime: str
    regime_name: str
    users: float = Field(description="The largest share of users on a platform of the group")
    users_needed: float | None
    turnover_cents: int
    turnover_needed_cents: int | None = Field(description="In the game's economy")
    turnover_legal_cents: int | None = Field(description="The law's figure, real-world scale")
    market_value_cents: int | None
    market_value_needed_cents: int | None = Field(description="In the game's economy")
    market_value_legal_cents: int | None
    ratio: float = Field(description="The test's ratio: 1 or more meets every threshold")
    warn_at: float
    designated: bool
    warned: str | None = Field(description="The month of the latest warning, if any")


class DesignationOut(BaseModel):
    regime: str
    regime_name: str
    regulator: str
    company: str
    company_id: int | None
    player: bool
    since: str
    duties_from: str
    services: list[str]
    historical: bool
    source: str | None


class DutyOut(BaseModel):
    id: int
    regulator: str
    regulator_name: str
    company: str
    company_id: int
    player: bool
    kind: str
    label: str
    since: str
    source: Literal["designation", "remedy", "commitment"]
    breached: bool = Field(description="The player keeps a setting this duty forbids")


class StepOut(BaseModel):
    stage: str
    month: str
    note: str | None = None


class CaseOut(BaseModel):
    id: int | None = Field(description="None for a case from history (regulation.yaml)")
    key: str | None
    regulator: str
    regulator_name: str
    company: str
    company_id: int | None
    player: bool
    title: str
    conduct: str
    market: str
    opened: str
    stage: str
    stage_since: str | None
    stage_window: str | None = Field(description="How long the stage lasts, as a range")
    outcome: str
    fine_cents: int
    final_cents: int | None = Field(description="History: the fine after appeals")
    remedy: str | None
    odds: str | None = Field(description="Counsel's odds for the next step, as a range")
    steps: list[StepOut]
    historical: bool


class WarningSignOut(BaseModel):
    kind: Literal["press", "report", "political", "board"]
    month: str
    label: str


class WatchOut(BaseModel):
    regulator: str
    regulator_name: str
    market: str
    since: str
    months: int = Field(description="Months since the first sign")
    needed_months: int = Field(description="A structural order needs at least this many")
    signs: list[WarningSignOut]


class OrderOut(BaseModel):
    id: int
    regulator: str
    regulator_name: str
    company: str
    player: bool
    unit: str
    unit_kind: Literal["platform", "company", "products"]
    ordered: str
    deadline: str
    status: str
    warned_from: str
    can_sell: bool
    can_spin_off: bool


class PrecedentOut(BaseModel):
    label: str
    month: str
    note: str
    source: str


class RegulationExplainOut(BaseModel):
    fine: str
    thresholds: str
    structural: str


class RegulationOut(BaseModel):
    month: str
    running: bool = Field(description="The model acts from January 2026; history before")
    regulators: list[RegulatorOut]
    tests: list[TestOut]
    designations: list[DesignationOut]
    duties: list[DutyOut]
    cases: list[CaseOut]
    watches: list[WatchOut]
    orders: list[OrderOut]
    precedents: list[PrecedentOut]
    fines_cents: int = Field(description="The player's group's fines and penalties to date")
    breaches: list[str]
    explain: RegulationExplainOut


class AnswerOrderIn(BaseModel):
    order_id: int
    how: Literal["sell", "spin_off"]


class RegulationActionOut(BaseModel):
    regulation: RegulationOut
    energy: EnergyOut
    unread_inbox: int
