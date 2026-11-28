"""Schemas for M54's financial services (ADR-0008, docs/formulas.md 64.1-64.3, 64.5):
`finance_services.yaml` (history to 2025, every value tagged and sourced) and the `finserv.*`
keys of balance.yaml.

finance_services.yaml writes values as `[value, tag]` pairs and money as `[value, dollar year, tag]`
under keys ending `_usd` (tags as telecom.yaml's). These models keep the numbers and drop the tags;
money becomes the game's 2010 cents with the file's `cpi` once, at load (robotics.yaml's
conversion).
Model definitions only.
"""

from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.calendar import history_floor_turn, start_turn_of
from tst.sim.facilities.config import Range, month_to_turn
from tst.sim.robotics.config import _convert
from tst.sim.vehicles.config import interp

BANK_SEGMENTS: Final = ("bank_consumer", "bank_business")
PAY_SEGMENTS: Final = ("pay_merchants", "pay_networks")
INS_SEGMENTS: Final = ("ins_property", "ins_life")
LINES: Final = ("property", "life")  # insurance lines; segment ins_<line>
type RivalKind = Literal["bank", "acquirer", "insurer"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _turn(month: str) -> int:
    return month_to_turn(month)


def series_at(points: dict[int, float], year: float) -> float:
    """A yearly series read at a fractional year: linear between points, held at the ends."""
    return interp(points, year)


# --- banking (64.1) -----------------------------------------------------------------------------


class LoanKindDef(_Frozen):
    key: str
    label: str
    spread: float  # % a year over the policy rate
    fixed: bool = False  # written at the month's rate and held (else floats with the policy rate)
    risk_weight: float = Field(ge=0, le=2)
    term_months: int = Field(ge=1)
    losses: dict[int, float]  # yearly net charge-off rate, %

    def loss_at(self, year: int) -> float:
        """The year's charge-off rate, % (net recoveries read as 0; held at the ends)."""
        years = sorted(self.losses)
        y = min(max(year, years[0]), years[-1])
        return max(0.0, self.losses[y])


class CapitalRule(_Frozen):
    from_: str = Field(alias="from")
    cet1_min: float
    buffer: float
    surcharge: float

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    @property
    def turn(self) -> int:
        return _turn(self.from_)


class DatedCents(_Frozen):
    from_: str = Field(alias="from")
    insured_cents: float = Field(alias="limit_cents")

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class CharterNote(_Frozen):
    name: str
    month: str
    kind: str


class FailureNote(_Frozen):
    name: str
    month: str
    withdrawn_real_cents: float | None = Field(default=None, alias="withdrawn_cents")

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class BankingDef(_Frozen):
    nim: dict[int, float]
    deposits_trn: dict[int, float]
    loans_trn: dict[int, float]
    accounts: dict[str, dict[int, float]]  # region -> year -> millions of adults with an account
    business_per_consumer: float = Field(gt=0)
    balance_2010_cents: dict[str, float] = Field(alias="balance_cents")  # segment -> a North
    # American account's balance in 2010
    deposit_index: dict[str, float]
    uninsured_share: dict[str, float]  # segment -> share above the insured limit
    insured_limit: dict[str, tuple[DatedCents, ...]]
    loan_kinds: tuple[LoanKindDef, ...] = Field(min_length=1)
    capital: tuple[CapitalRule, ...] = Field(min_length=1)
    stress_from: dict[str, int]
    charters: tuple[CharterNote, ...]
    failures: tuple[FailureNote, ...]

    def loan_kind(self, key: str) -> LoanKindDef:
        for k in self.loan_kinds:
            if k.key == key:
                return k
        raise KeyError(key)

    def rule_at(self, turn: int) -> CapitalRule:
        rule = self.capital[0]
        for r in self.capital:
            if r.turn <= turn:
                rule = r
        return rule

    def limit_at(self, region: str, turn: int) -> float:
        out = 0.0
        floor = min(history_floor_turn(turn), WORLD_2008)  # M50b: pre-2008 rows only before it
        for row in self.insured_limit.get(region, ()):
            if floor <= _turn(row.from_) <= turn:
                out = row.insured_cents
        return out


WORLD_2008: Final = start_turn_of(2008)  # M50b: rows dated before it are the 2000 world's


# --- payments (64.2) ----------------------------------------------------------------------------


class NetworkDef(_Frozen):
    name: str
    share_points: dict[str, dict[int, float]] = Field(alias="shares")  # region -> year -> share

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    def share_at(self, region: str, year: float) -> float:
        points = self.share_points.get(region)
        return series_at(points, year) if points else 0.0


class DatedBp(_Frozen):
    from_: str = Field(alias="from")
    bp: float

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class RailDef(_Frozen):
    name: str
    region: str
    from_: str = Field(alias="from")
    share_points: dict[int, float] = Field(alias="shares")

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    @property
    def turn(self) -> int:
        return _turn(self.from_)

    def share_at(self, year: float) -> float:
        return series_at(self.share_points, year)


class Note(_Frozen):
    month: str
    text: str


class PaymentsDef(_Frozen):
    volume_bn: dict[str, dict[int, float]]  # region -> year -> card volume, $ billion (real)
    networks: tuple[NetworkDef, ...]
    interchange_bp: dict[str, tuple[DatedBp, ...]]
    network_fee_bp: float = Field(ge=0)
    fraud_bp: float = Field(ge=0)
    merchant_discount_bp: float = Field(ge=0)
    volume_per_merchant_cents: float = Field(gt=0)
    network_unit_cents: float = Field(gt=0)
    rails: tuple[RailDef, ...]
    notes: tuple[Note, ...]

    def network(self, name: str) -> NetworkDef | None:
        return next((n for n in self.networks if n.name == name), None)

    def interchange_at(self, region: str, turn: int) -> float:
        out = 0.0
        floor = min(history_floor_turn(turn), WORLD_2008)  # M50b: pre-2008 rows only before it
        for row in self.interchange_bp.get(region, ()):
            if floor <= _turn(row.from_) <= turn:
                out = row.bp
        return out


# --- insurance (64.3) ---------------------------------------------------------------------------


class SolvencyRule(_Frozen):
    from_: str = Field(alias="from")
    premium_share: float = Field(ge=0)
    reserve_share: float = Field(ge=0)

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class InsuranceDef(_Frozen):
    premiums_bn: dict[str, dict[int, float]]  # line -> year -> world premiums, $ billion
    region_share: dict[str, float]
    premium_2010_cents: dict[str, float] = Field(alias="premium_cents")  # line -> a policy's
    # monthly premium (2010 cents)
    combined_ratio: dict[str, dict[int, float]]  # line -> year -> %
    expense_share: dict[str, float]
    claims_lag_months: dict[str, int]
    cat_losses_bn: dict[int, float]
    cat_region_share: dict[str, float]
    solvency: dict[str, tuple[SolvencyRule, ...]]  # region or "default"
    notes: tuple[Note, ...]

    def solvency_at(self, region: str, turn: int) -> SolvencyRule:
        rows = self.solvency.get(region) or self.solvency["default"]
        rule = rows[0]
        for r in rows:
            if _turn(r.from_) <= turn:
                rule = r
        return rule


# --- rivals and regulators (64.5) ---------------------------------------------------------------


class FinRivalDef(_Frozen):
    name: str
    kind: RivalKind
    region: str
    share_points: dict[int, float] = Field(alias="shares")  # year -> share of the region's market
    segments: tuple[str, ...] | None = None  # None = every segment of its category
    last: str | None = None  # "YYYY-MM": the line closes this month (a failure)

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    def share_at(self, year: float) -> float:
        return series_at(self.share_points, year)

    @property
    def last_turn(self) -> int | None:
        return _turn(self.last) if self.last else None


class BankRegulatorDef(_Frozen):
    name: str
    charter_months: int = Field(ge=1)


class InsuranceRegulatorDef(_Frozen):
    name: str
    licence_months: int = Field(ge=1)


class ActionDef(_Frozen):
    company: str
    from_: str = Field(alias="from")
    to: str | None = None
    kind: str
    text: str

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    def in_force(self, turn: int) -> bool:
        return _turn(self.from_) <= turn and (self.to is None or turn < _turn(self.to))


class RegulatorsDef(_Frozen):
    bank: dict[str, BankRegulatorDef]
    insurance: dict[str, InsuranceRegulatorDef]
    actions: tuple[ActionDef, ...]


class FinservFile(_Frozen):
    banking: BankingDef
    payments: PaymentsDef
    insurance: InsuranceDef
    rivals: tuple[FinRivalDef, ...]
    regulators: RegulatorsDef

    @model_validator(mode="before")
    @classmethod
    def _parse(cls, raw: Any) -> Any:
        if not isinstance(raw, dict) or "cpi" not in raw:
            return raw
        cpi = {int(y): float(v[0] if isinstance(v, list) else v) for y, v in raw["cpi"].items()}
        return _convert({k: v for k, v in raw.items() if k != "cpi"}, cpi)

    def rival(self, name: str) -> FinRivalDef | None:
        return next((r for r in self.rivals if r.name == name), None)


# --- balance.yaml finserv.* ---------------------------------------------------------------------


class StressBalance(_Frozen):
    size_cents: int = Field(ge=0)  # banks with assets above this are stress-tested
    month: int = Field(ge=1, le=12)  # results this month each year
    rate_shock: Range  # percentage points added to the policy rate
    loss_mult: Range  # charge-offs x this for a year
    deposit_outflow: Range  # share of deposits that leaves
    freeze_months: int = Field(ge=1)  # dividends frozen after a failed test


class RunBalance(_Frozen):
    unrealised_share: float = Field(ge=0)  # unrealised losses over CET1 capital above this ...
    uninsured_min: float = Field(ge=0, le=1)  # ... and uninsured deposits above this share
    chance: float = Field(ge=0, le=1)  # a month's run chance at full pressure
    withdraw: Range  # a run withdraws this share of uninsured deposits
    pressure_k: float = Field(gt=0)  # unrealised share over the line that is full pressure


class BankBalance(_Frozen):
    charter_capital_cents: int = Field(ge=0)  # minimum capital to apply for a charter (game scale)
    charter_fee_cents: int = Field(ge=0)  # legal and application costs
    strict_months: int = Field(ge=0)  # months a strict regulator adds to a charter
    strict_line: float = Field(ge=0)  # a regulator is strict at or above this strictness
    beta_range: Range  # the deposit beta the player may choose
    default_beta: float = Field(ge=0, le=1)
    market_beta: float = Field(ge=0, le=1)  # the market's deposit rate = policy x this
    rate_elasticity: float = Field(ge=0)  # deposits' target x (1 + this x rate gap in points)
    rate_floor: float = Field(ge=0)  # the target's lower limit
    rate_cap: float = Field(gt=0)  # the target's upper limit
    deposit_adjust: float = Field(gt=0, le=1)  # a month's move toward the target
    partner_share: float = Field(ge=0, le=1)  # of net interest income a partner bank passes on
    loan_mix: dict[str, float]  # default mix of new loans by kind (sums to 1)
    loan_to_deposit: float = Field(ge=0, le=1)  # default loans / deposits target
    securities_share: float = Field(ge=0, le=1)  # default securities / deposits target
    duration_years: Range  # securities' duration the player may choose
    default_duration: float = Field(gt=0)
    term_premium: float = Field(ge=0)  # securities' yield over policy, points a year of duration
    loss_cycle_k: float = Field(ge=0)  # charge-offs x (1 + k x (100 - confidence) / 100) after 2025
    loss_base_years: Range  # years whose mean charge-off rate is a kind's base after 2025
    reserve_min: float = Field(ge=0, le=1)  # cash kept against deposits before lending
    gsib_assets_cents: int = Field(ge=0)  # the size surcharge applies above these assets
    intervene_share: float = Field(ge=0, le=1)  # CET1 below this x the minimum: the regulator acts
    stress: StressBalance
    run: RunBalance
    dividend_share: float = Field(ge=0, le=1)  # profit above the line paid to the parent yearly
    group_review_share: float = Field(ge=0, le=1)  # non-bank revenue share that makes a tech group
    rival_fee_share: float = Field(ge=0, le=1)  # rivals' fee lines are this share of revenue


class PaymentsBalance(_Frozen):
    network_cost_cents: int = Field(ge=0)  # launching a network in a region (game scale)
    acceptance_ref: float = Field(gt=0, le=1)  # acceptance at which a network's appeal is 1x
    acceptance_k: float = Field(ge=0)  # appeal x (acceptance / ref) ** k
    acceptance_adjust: float = Field(gt=0, le=1)  # a month's move of acceptance toward its target
    acceptance_exponent: float = Field(gt=0)  # target acceptance = share ** this
    appeal_range: Range  # the network's appeal multiplier is held within this
    fraud_skill_cut: float = Field(ge=0, le=1)  # the most a top security team cuts fraud
    card_turnover: float = Field(ge=0)  # a month's card volume per dollar of card balances
    growth_after: dict[str, Range]  # region -> card volume's yearly growth after 2025 (seeded)
    rail_growth_after: float = Field(ge=0)  # rails' share gains this a year after 2025 ...
    rail_cap: float = Field(ge=0, le=1)  # ... up to this


class CatBalance(_Frozen):
    chance: float = Field(ge=0, le=1)  # a year's chance of a catastrophe year after 2025
    extra: Range  # points added to property's combined ratio in a catastrophe year
    region_mult: float = Field(ge=0)  # the hit region's extra x this (others x its share)


class InsuranceBalance(_Frozen):
    licence_capital_cents: int = Field(ge=0)  # minimum capital for a licence (game scale)
    licence_fee_cents: int = Field(ge=0)
    price_elasticity: float = Field(ge=0)  # combined ratio x (reference / price) ** this
    skill_cut: float = Field(ge=0, le=1)  # the most a top pricing team cuts the claims ratio
    float_spread: float  # the float earns the policy rate plus this (points)
    cat: CatBalance
    base_years: Range  # years whose mean combined ratio is a line's base after 2025
    rival_claims_share: float = Field(ge=0, le=1)  # rivals' running cost, of premiums


class FinservBalance(_Frozen):
    """balance.yaml finserv.* (formulas.md 64)."""

    start: str  # "YYYY-MM": history holds before this month
    banking_category: str  # categories.yaml keys
    payments_category: str
    insurance_category: str
    scale: float = Field(gt=0)
    scale_basis: str
    bank: BankBalance
    payments: PaymentsBalance
    insurance: InsuranceBalance
    growth_after: Range  # accounts' and policies' yearly growth after 2025 (seeded, a region)
    rival_cash_cents: int = Field(ge=0)
    history_months: int = Field(ge=1)
    energy: dict[str, int]  # founder energy a finance or currency action spends
    unlock_year: int

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.start)

    @property
    def categories(self) -> tuple[str, str, str]:
        return (self.banking_category, self.payments_category, self.insurance_category)
