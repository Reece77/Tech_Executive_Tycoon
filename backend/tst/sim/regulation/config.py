"""Schemas for M34's data and tunables (ADR-0008, docs/formulas.md 48): `regulation.yaml` and
`regulation.*` in balance.yaml.

Model definitions only (no file reads), so `tst.sim.data_models` can import them without a cycle.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import month_to_turn

type DutyKind = Literal[
    "side_loading",
    "alt_payments",
    "anti_steering",
    "interoperability",
    "no_self_preferencing",
    "data_portability",
    "fee_cap",
]
type Conduct = Literal[
    "self_preferencing",
    "anti_steering",
    "removals",
    "fees",
    "acquisitions",
    "noncompliance",
    "tying",
    "exclusivity",
    "dominance",
]
type CaseKind = Literal["conduct", "merger"]
type HistoryStage = Literal[
    "inquiry", "objections", "ruling", "appeal", "settled", "dismissed", "abandoned", "cleared"
]
type HistoryOutcome = Literal[
    "open", "fined", "remedied", "dismissed", "annulled", "abandoned", "cleared", "settled"
]
type TurnoverScope = Literal["region", "world"]

DUTY_KINDS: Final = (
    "side_loading",
    "alt_payments",
    "anti_steering",
    "interoperability",
    "no_self_preferencing",
    "data_portability",
    "fee_cap",
)
FIRST_YEAR: Final = 2010  # tunable-exempt: turn 0's year


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --- regulation.yaml ------------------------------------------------------------------------


class RegulatorDef(_Frozen):
    """A region's regulator (48.1)."""

    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    region: str = Field(min_length=1)
    part: str | None = None  # a platforms.yaml region_parts key; None = the whole region
    structural: bool = False  # may order a break-up or unbundling (48.4)
    strictness: dict[int, float] = Field(min_length=1)  # from year -> index (A)
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> RegulatorDef:
        if any(v < 0 for v in self.strictness.values()):
            raise ValueError(f"regulator {self.key}: strictness must be >= 0")
        return self

    def strictness_in(self, year: int) -> float:
        years = sorted(self.strictness)
        known = [y for y in years if y <= year]
        return self.strictness[known[-1] if known else years[0]]


class RegimeDef(_Frozen):
    """A designation regime (48.1): its tests and the duties designation brings (48.2)."""

    key: str = Field(min_length=1)
    regulator: str = Field(min_length=1)
    name: str = Field(min_length=1)
    in_force: str
    first_designations: str
    users_share: float | None = Field(default=None, ge=0, le=1)
    business_users: int | None = None  # recorded, not tested
    turnover_b: float | None = Field(default=None, gt=0)
    turnover_scope: TurnoverScope = "region"
    value_b: float | None = Field(default=None, gt=0)
    currency: str = Field(min_length=3, max_length=3)
    comply_months: int = Field(ge=0)
    duties: tuple[DutyKind, ...] = Field(min_length=1)
    max_fine_share: float = Field(gt=0, le=1)
    repeat_fine_share: float = Field(gt=0, le=1)
    periodic_share: float = Field(ge=0, le=1)

    @property
    def in_force_turn(self) -> int:
        return month_to_turn(self.in_force)

    @property
    def first_turn(self) -> int:
        return month_to_turn(self.first_designations)


class DesignationDef(_Frozen):
    """A historical designation (48.1)."""

    regime: str = Field(min_length=1)
    company: str | None = None  # an incumbents.yaml name; None = outside the game
    label: str = Field(min_length=1)
    platform: str | None = None  # a platforms.yaml key the designation covers (owner outside)
    from_: str = Field(alias="from")
    services: tuple[str, ...] = Field(min_length=1)
    source: str = Field(min_length=1)

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    @property
    def from_turn(self) -> int:
        return month_to_turn(self.from_)


class StageDef(_Frozen):
    stage: HistoryStage
    at: str
    note: str | None = None
    source: str = Field(min_length=1)

    @property
    def turn(self) -> int:
        return month_to_turn(self.at)


class CaseDef(_Frozen):
    """A historical case to 2025 (48.3)."""

    key: str = Field(min_length=1)
    regulator: str = Field(min_length=1)
    company: str | None = None
    label: str = Field(min_length=1)
    authority: str | None = None  # who acted when not the regulator itself (a court, a rival)
    kind: CaseKind
    conduct: Conduct
    title: str = Field(min_length=1)
    stages: tuple[StageDef, ...] = Field(min_length=1)
    fine: int = Field(ge=0)  # in `currency`, as decided
    final: int = Field(ge=0)  # after appeals to the history's end (0 = annulled)
    currency: str = Field(min_length=3, max_length=3)
    remedy: DutyKind | None = None
    outcome: HistoryOutcome

    @model_validator(mode="after")
    def _check(self) -> CaseDef:
        turns = [s.turn for s in self.stages]
        if turns != sorted(turns):
            raise ValueError(f"case {self.key}: stages must be in date order")
        return self

    @property
    def opened_turn(self) -> int:
        return self.stages[0].turn

    def ruled_against_turn(self) -> int | None:
        """The month of the first ruling against the company (a precedent for 48.4)."""
        if self.outcome not in ("fined", "remedied", "open"):
            return None
        rulings = [s.turn for s in self.stages if s.stage == "ruling"]
        return rulings[0] if rulings else None


class PrecedentDef(_Frozen):
    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    at: str
    note: str = Field(min_length=1)
    source: str = Field(min_length=1)


class RegulationFile(_Frozen):
    """regulation.yaml (48)."""

    history_end: str
    regulators: tuple[RegulatorDef, ...] = Field(min_length=1)
    regimes: tuple[RegimeDef, ...] = ()
    designations: tuple[DesignationDef, ...] = ()
    cases: tuple[CaseDef, ...] = ()
    precedents: tuple[PrecedentDef, ...] = ()

    @property
    def history_end_turn(self) -> int:
        return month_to_turn(self.history_end)

    def regulator(self, key: str) -> RegulatorDef:
        for r in self.regulators:
            if r.key == key:
                return r
        raise KeyError(key)

    def regime(self, key: str) -> RegimeDef:
        for r in self.regimes:
            if r.key == key:
                return r
        raise KeyError(key)

    @model_validator(mode="after")
    def _check(self) -> RegulationFile:
        keys = [r.key for r in self.regulators]
        if len(set(keys)) != len(keys):
            raise ValueError("regulator keys must be unique")
        for g in self.regimes:
            if g.regulator not in keys:
                raise ValueError(f"regime {g.key}: unknown regulator {g.regulator!r}")
        regimes = {g.key for g in self.regimes}
        for d in self.designations:
            if d.regime not in regimes:
                raise ValueError(f"designation of {d.label}: unknown regime {d.regime!r}")
        cases = [c.key for c in self.cases]
        if len(set(cases)) != len(cases):
            raise ValueError("case keys must be unique")
        for c in self.cases:
            if c.regulator not in keys:
                raise ValueError(f"case {c.key}: unknown regulator {c.regulator!r}")
        return self


# --- regulation.* in balance.yaml -----------------------------------------------------------


class InvestigationBalance(_Frozen):
    """48.3: the monthly chance a regulator opens a case (engine-side only)."""

    base: float = Field(ge=0, le=1)
    min_revenue_cents: int = Field(ge=0)
    dominance: float = Field(ge=1)
    designated: float = Field(ge=1)
    self_pref: dict[str, float]
    removals: float = Field(ge=1)
    fee_high: float = Field(ge=1)
    fee_high_above: float = Field(ge=0, le=1)
    acquisitions: float = Field(ge=1)
    acquisition_months: int = Field(gt=0)
    noncompliance: float = Field(ge=1)
    ruthless: float = Field(ge=1)
    complaint: float = Field(ge=1)
    complaint_months: int = Field(gt=0)
    influence_cut: float = Field(ge=0, le=1)
    compliant: float = Field(gt=0, le=1)
    max_chance: float = Field(gt=0, le=1)
    cooldown_months: int = Field(ge=0)


class StagesBalance(_Frozen):
    inquiry_months: tuple[int, int]
    objections_months: tuple[int, int]
    appeal_months: tuple[int, int]
    lobby_delay_months: int = Field(ge=0)
    lobby_cents: int = Field(ge=0)
    lobby_influence: float = Field(ge=0, le=100)


class OddsBalance(_Frozen):
    """Ranges the player sees; each chance is drawn inside its range when decided (48.3)."""

    proceed: tuple[float, float]
    ruling_against: tuple[float, float]
    appeal_win: tuple[float, float]
    lobby_cut: float = Field(ge=0, le=1)
    complied_cut: float = Field(ge=0, le=1)


class FineBalance(_Frozen):
    share: tuple[float, float]  # of global turnover, by the case's gravity
    noncompliance_mult: float = Field(ge=1)
    settle_share: float = Field(ge=0, le=1)  # the fine's share when settling after objections
    default_max_share: float = Field(gt=0, le=1)  # regulators with no regime (US, China)


class StructuralBalance(_Frozen):
    """48.4: rare, warned break-ups."""

    ruling_years: int = Field(gt=0)
    two_rulings_years: int = Field(gt=0)
    warning_months: int = Field(gt=0)
    warning_every: int = Field(gt=0)
    min_strictness: float = Field(ge=0)
    chance: float = Field(ge=0, le=1)
    window_months: int = Field(gt=0)
    periodic_days: int = Field(gt=0)
    sale_multiple: float = Field(gt=0)
    appeal_months: tuple[int, int]
    appeal_win: tuple[float, float]


class RivalRegulationBalance(_Frozen):
    contest: tuple[str, ...]  # personalities that contest at the statement of objections


class RegulationBalance(_Frozen):
    start: str  # the model acts on rivals from this month (the month after the history)
    fx: dict[str, float]  # USD per unit of each currency (A)
    warn_ratio: float = Field(gt=0, le=1)
    dominance_share: float = Field(gt=0, le=1)
    compliance_cents: int = Field(ge=0)  # a duty's yearly cost, posted monthly
    fee_cap: float = Field(ge=0, le=1)
    alt_discount: float = Field(ge=0, le=1)
    energy: dict[str, int]
    investigation: InvestigationBalance
    stages: StagesBalance
    odds: OddsBalance
    fine: FineBalance
    structural: StructuralBalance
    rivals: RivalRegulationBalance

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.start)

    @model_validator(mode="after")
    def _check(self) -> RegulationBalance:
        for name in ("inquiry_months", "objections_months", "appeal_months"):
            lo, hi = getattr(self.stages, name)
            if not 0 < lo <= hi:
                raise ValueError(f"regulation.stages.{name} must be 0 < lo <= hi")
        odds = self.odds
        for lo, hi in (odds.proceed, odds.ruling_against, odds.appeal_win, self.fine.share):
            if not 0 <= lo <= hi <= 1:
                raise ValueError("regulation odds and fine shares must be 0 <= lo <= hi <= 1")
        if "USD" not in self.fx:
            raise ValueError("regulation.fx needs USD")
        return self
