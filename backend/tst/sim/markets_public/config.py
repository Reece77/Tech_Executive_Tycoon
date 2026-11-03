"""Schemas for M13's tunables and data (ADR-0008, docs/formulas.md 25): `ipo.*`, `public.*`
and `ceo.*` in balance.yaml, and `banks.yaml`.

Model definitions only (no file reads, no imports from the rest of the sim), so
`tst.sim.data_models` can import them without a cycle.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

AMBITIONS: Final = ("high", "middle", "low")  # 25.2 step 3
SHARE_CHOICES: Final = ("low", "middle", "high")  # the share sold: 10%, 15%, 25% by default
CEO_SCOPES: Final = ("cto", "cro", "cmo", "coo", "cfo", "products")  # 25.6
CEO_SKILLS: Final = ("leadership", "strategy", "communication", "product", "finance")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Bounds(_Frozen):
    """[lo, hi], written as a two-item list in YAML."""

    lo: float
    hi: float

    @model_validator(mode="before")
    @classmethod
    def _from_list(cls, value: object) -> object:
        if isinstance(value, list | tuple) and len(value) == 2:  # tunable-exempt: a pair
            return {"lo": value[0], "hi": value[1]}
        return value

    @model_validator(mode="after")
    def _check(self) -> Bounds:
        if self.lo > self.hi:
            raise ValueError("bounds' lo must not exceed hi")
        return self

    def clamp(self, x: float) -> float:
        return max(self.lo, min(self.hi, x))


class Bank(_Frozen):
    """A lead underwriter in banks.yaml (25.2 step 1)."""

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    fee: float = Field(ge=0.055, le=0.07)  # tunable-exempt: 25.2 bounds the fee at 5.5-7%
    quality: float = Field(ge=0.9, le=1.1)  # tunable-exempt: 25.2 bounds quality at 0.9-1.1


class BanksFile(_Frozen):
    banks: tuple[Bank, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> BanksFile:
        keys = [b.key for b in self.banks]
        if len(set(keys)) != len(keys):
            raise ValueError("bank keys must be unique")
        return self


class DemandBalance(_Frozen):
    """Book demand d = clamp(N(mean + climate x (v - 1), sd), bounds) (25.2 step 4)."""

    mean: float = Field(gt=0)
    climate: float = Field(ge=0)
    sd: float = Field(gt=0)
    bounds: Bounds


class DemandWord(_Frozen):
    below: float = Field(gt=0)  # d below this reads as `word`
    word: str = Field(min_length=1)


class FirstDayBalance(_Frozen):
    """r = clamp(demand x (d - 1) - ambition x (a - 1) / step, bounds) (25.2 step 5)."""

    demand: float = Field(ge=0)
    ambition: float = Field(ge=0)
    step: float = Field(gt=0)
    bounds: Bounds


class IpoBalance(_Frozen):
    min_stage: int = Field(ge=0, le=5)  # tunable-exempt: the spec's stage scale is 0-5
    min_arr_cents: int = Field(gt=0)
    trailing_months: int = Field(ge=1)
    min_growth: float = Field(ge=0)
    board_min_confidence: float = Field(ge=0, le=100)
    hire_energy: int = Field(ge=0)
    retry_months: int = Field(ge=0)
    filing_delay_months: int = Field(ge=0)
    ambition: dict[str, float]
    share_sold: dict[str, float]
    dual_class_discount: float = Field(ge=0, lt=1)
    demand: DemandBalance
    demand_words: tuple[DemandWord, ...] = Field(min_length=1)
    demand_top_word: str = Field(min_length=1)
    raise_min_demand: float = Field(gt=0)
    raise_pct: float = Field(gt=0, lt=1)
    cut_pct: float = Field(gt=0, lt=1)
    pull_fee_share: float = Field(ge=0, le=1)
    pull_confidence: float = Field(le=0)
    first_day: FirstDayBalance
    independents: int = Field(ge=0)
    ticker_len: int = Field(ge=1)

    @model_validator(mode="after")
    def _check(self) -> IpoBalance:
        if sorted(self.ambition) != sorted(AMBITIONS):
            raise ValueError(f"ipo.ambition must define {list(AMBITIONS)}")
        if sorted(self.share_sold) != sorted(SHARE_CHOICES):
            raise ValueError(f"ipo.share_sold must define {list(SHARE_CHOICES)}")
        for share in self.share_sold.values():
            if not 0.10 <= share <= 0.25:  # tunable-exempt: 25.2 sells 10-25%
                raise ValueError("ipo.share_sold values must lie in 0.10-0.25 (25.2)")
        words = [w.below for w in self.demand_words]
        if words != sorted(words):
            raise ValueError("ipo.demand_words must rise")
        return self


class MultipleBalance(_Frozen):
    """m = clamp(base + growth g + margin x m_op - rate (r_base - pivot), bounds) x v (25.3)."""

    base: float
    growth: float
    margin: float
    rate: float
    rate_pivot: float
    bounds: Bounds


class SentimentBalance(_Frozen):
    """S toward 1.0: S' = 1 + phi (S - 1) + N(0, sd), clamped (25.3)."""

    phi: float = Field(ge=0, lt=1)
    sd: float = Field(ge=0)
    bounds: Bounds


class AnalystsBalance(_Frozen):
    min: int = Field(ge=1)
    max: int = Field(ge=1)
    base_cap_cents: int = Field(gt=0)  # market cap at which coverage starts adding analysts
    target_sd: float = Field(ge=0)
    buy_above: float = Field(gt=0)
    sell_below: float = Field(gt=0)
    firms: tuple[str, ...] = Field(min_length=1)  # names shown for the analysts, in order

    @model_validator(mode="after")
    def _check(self) -> AnalystsBalance:
        if self.min > self.max or len(self.firms) < self.max:
            raise ValueError("public.analysts: min <= max <= number of firms")
        if self.sell_below >= self.buy_above:
            raise ValueError("public.analysts: sell_below < buy_above")
        return self


class EarningsBalance(_Frozen):
    revenue_weight: float = Field(ge=0)
    margin_weight: float = Field(ge=0)
    jump: Bounds
    miss_below: float = Field(le=0)
    beat_from: float
    misses_in_row: int = Field(ge=1)
    misses_in_row_confidence: float = Field(le=0)
    beat_streak: int = Field(ge=1)
    beat_streak_sentiment: float = Field(ge=0)
    beat_board: float = Field(ge=0)
    miss_board: float = Field(le=0)
    guidance_energy: int = Field(ge=0)
    guidance_band: float = Field(gt=0)  # guided revenue within (1 +- band) x consensus


class TriggerBalance(_Frozen):
    value_share: float = Field(gt=0, le=1)
    months: int = Field(ge=1)
    misses: int | None = Field(default=None, ge=1)  # activist only
    window_quarters: int | None = Field(default=None, ge=1)
    gap_months: int = Field(ge=0)


class CapitalBalance(_Frozen):
    buyback_energy: int = Field(ge=0)
    buyback_premium: float = Field(ge=0)
    buyback_max_share: float = Field(gt=0, le=1)
    dividend_energy: int = Field(ge=0)
    secondary_energy: int = Field(ge=0)
    secondary_discount: float = Field(ge=0, lt=1)
    secondary_fee: float = Field(ge=0, lt=1)
    secondary_max_share: float = Field(gt=0, le=1)


class PublicBoardBalance(_Frozen):
    investor_lapse_months: int = Field(ge=1)
    patience: dict[str, float]  # analysts' consensus rating -> patience points (25.7)

    @model_validator(mode="after")
    def _check(self) -> PublicBoardBalance:
        if sorted(self.patience) != ["buy", "hold", "sell"]:
            raise ValueError("public.board.patience must define buy, hold and sell")
        return self


class ActivistBalance(_Frozen):
    """An activist's choices (25.4): the forced buyback's share of cash, and the proxy fight."""

    buyback_cash_share: float = Field(ge=0, le=1)
    settle_cash_share: float = Field(ge=0, le=1)
    board_seats: int = Field(ge=0)


class TakeoverBalance(_Frozen):
    premium: float = Field(ge=0)  # the bid over the price; talks move sentiment toward it
    talks_share: float = Field(ge=0, le=1)  # share of the premium sentiment takes on talks


class PublicBalance(_Frozen):
    multiple: MultipleBalance
    sentiment: SentimentBalance
    analysts: AnalystsBalance
    earnings: EarningsBalance
    activist_trigger: TriggerBalance
    takeover_trigger: TriggerBalance
    activist: ActivistBalance
    takeover: TakeoverBalance
    capital: CapitalBalance
    board: PublicBoardBalance
    history_months: int = Field(ge=1)


class CeoReplaceBalance(_Frozen):
    below: float = Field(ge=0, le=100)
    months: int = Field(ge=1)


class CeoBalance(_Frozen):
    appoint_energy: int = Field(ge=0)
    override_energy: int = Field(ge=0)
    chair_energy: int = Field(ge=0)
    min_stage: int = Field(ge=0, le=5)  # tunable-exempt: the spec's stage scale is 0-5
    weights: dict[str, float]
    price_band_pct: float = Field(ge=0)
    headcount_cap: int = Field(ge=0)
    max_salary_ratio_bp: int = Field(ge=0)
    replace: CeoReplaceBalance
    memory_months: int = Field(ge=1)

    @model_validator(mode="after")
    def _check(self) -> CeoBalance:
        if sorted(self.weights) != sorted(CEO_SKILLS):
            raise ValueError(f"ceo.weights must define {list(CEO_SKILLS)}")
        total = sum(self.weights.values())
        if abs(total - 1) > 1e-9:  # tunable-exempt: float tolerance
            raise ValueError("ceo.weights must sum to 1")
        return self
