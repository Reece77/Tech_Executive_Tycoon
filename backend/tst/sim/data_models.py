"""Pydantic schemas for balance and seed data (ADR-0008).

Model definitions only: this module never reads files. `tst.loader` parses the YAML and
validates it with these models. Unknown keys and out-of-range values fail validation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# ---------------------------------------------------------------------------
# balance.yaml
# ---------------------------------------------------------------------------


class CompanyBalance(_Frozen):
    base_monthly_cost_cents: int = Field(ge=0)


class ScenarioBalance(_Frozen):
    starting_cash_cents: int = Field(ge=0)


class DifficultyBalance(_Frozen):
    starting_cash_mult_bp: int = Field(gt=0)


class BackupBalance(_Frozen):
    every_n_turns: int = Field(gt=0)
    keep_periodic: int = Field(gt=0)


DIFFICULTY_LEVELS = ("easy", "standard", "hard", "ironman")  # ADR-0011
DEFAULT_DIFFICULTY = "standard"
LEVELS = ("junior", "mid", "senior", "staff", "principal", "exec")  # formulas.md section 2


class Span(_Frozen):
    """An inclusive [min, max] pair, written in YAML as a two-item list."""

    lo: float
    hi: float

    @model_validator(mode="before")
    @classmethod
    def _from_list(cls, value: object) -> object:
        if isinstance(value, list | tuple):
            if len(value) != 2:
                raise ValueError("expected [min, max]")
            return {"lo": value[0], "hi": value[-1]}
        return value

    @model_validator(mode="after")
    def _ordered(self) -> Span:
        if self.lo > self.hi:
            raise ValueError(f"min {self.lo} is greater than max {self.hi}")
        return self


class AgeBand(_Frozen):
    from_age: int = Field(ge=0)
    value: float


def _check_bands(bands: tuple[AgeBand, ...], name: str) -> None:
    if not bands or bands[0].from_age != 0:
        raise ValueError(f"{name}: the first band must start at from_age 0")
    ages = [b.from_age for b in bands]
    if ages != sorted(set(ages)):
        raise ValueError(f"{name}: from_age values must be strictly increasing")


def band_value(bands: tuple[AgeBand, ...], age: int) -> float:
    """Value of the last band whose from_age <= age."""
    value = bands[0].value
    for band in bands:
        if age >= band.from_age:
            value = band.value
    return value


class LevelCA(_Frozen):
    mean: float
    sd: float = Field(ge=0)


class SkillNoise(_Frozen):
    primary: float = Field(ge=0)
    secondary: float = Field(ge=0)


class PeopleBalance(_Frozen):
    level_ca: dict[str, LevelCA]
    level_age: dict[str, Span]
    ca_clip: Span
    skill_noise_sd: SkillNoise
    secondary_offset: float
    other_skill_range: Span
    ca_tolerance: float = Field(gt=0)
    pa_gap_mean: tuple[AgeBand, ...]
    pa_gap_sd: float = Field(ge=0)
    personality_mean: float
    personality_sd: float = Field(ge=0)
    max_tags: int = Field(ge=0)
    region_weights: dict[str, float]
    retire_bp_per_year_over_60: int = Field(ge=0)

    @model_validator(mode="after")
    def _check(self) -> PeopleBalance:
        for name, table in (("level_ca", self.level_ca), ("level_age", self.level_age)):
            if sorted(table) != sorted(LEVELS):
                raise ValueError(f"{name} must define exactly {list(LEVELS)}")
        _check_bands(self.pa_gap_mean, "pa_gap_mean")
        if any(w < 0 for w in self.region_weights.values()) or not any(
            w > 0 for w in self.region_weights.values()
        ):
            raise ValueError("region_weights must be non-negative with at least one positive")
        return self


class PayrollBalance(_Frozen):
    salary_round_to_cents: int = Field(gt=0)


class GrowthBalance(_Frozen):
    rate: float = Field(ge=0)
    age_factor: tuple[AgeBand, ...]
    decline: tuple[AgeBand, ...]
    noise_sd: float = Field(ge=0)

    @model_validator(mode="after")
    def _check(self) -> GrowthBalance:
        _check_bands(self.age_factor, "age_factor")
        _check_bands(self.decline, "decline")
        return self


REVEAL_ACTIONS = (
    "job_post_screen",
    "network_intro",
    "interview",
    "reference_check",
    "scouting_month",
    "employed_month",
)


class InitialHalfWidth(_Frozen):
    skill: float = Field(ge=0)
    personality: float = Field(ge=0)
    pa: float = Field(ge=0)


class RevealBalance(_Frozen):
    initial_hw: InitialHalfWidth
    strength: dict[str, float]
    scout_base: float
    scout_divisor: float = Field(gt=0)
    pa_phrase_bounds: tuple[float, ...]

    @model_validator(mode="after")
    def _check(self) -> RevealBalance:
        if sorted(self.strength) != sorted(REVEAL_ACTIONS):
            raise ValueError(f"strength must define exactly {list(REVEAL_ACTIONS)}")
        if any(not 0 <= s <= 1 for s in self.strength.values()):
            raise ValueError("strength values must be fractions in [0, 1]")
        if list(self.pa_phrase_bounds) != sorted(self.pa_phrase_bounds):
            raise ValueError("pa_phrase_bounds must be increasing")
        return self


class FounderBalance(_Frozen):
    skill_base: float
    skill_points: int = Field(ge=0)
    skill_cap: float
    default_age: int
    age_range: Span
    default_region: str

    @model_validator(mode="after")
    def _check(self) -> FounderBalance:
        if not self.age_range.lo <= self.default_age <= self.age_range.hi:
            raise ValueError("default_age must be within age_range")
        if self.skill_base > self.skill_cap:
            raise ValueError("skill_base must not exceed skill_cap")
        return self


class Balance(_Frozen):
    company: CompanyBalance
    scenario: dict[str, ScenarioBalance]
    difficulty: dict[str, DifficultyBalance]
    backup: BackupBalance
    people: PeopleBalance
    payroll: PayrollBalance
    growth: GrowthBalance
    reveal: RevealBalance
    founder: FounderBalance

    @model_validator(mode="after")
    def _check_difficulties(self) -> Balance:
        if sorted(self.difficulty) != sorted(DIFFICULTY_LEVELS):
            raise ValueError(
                f"difficulty must define exactly {list(DIFFICULTY_LEVELS)}, "
                f"got {sorted(self.difficulty)}"
            )
        return self


# ---------------------------------------------------------------------------
# Seed data files
# ---------------------------------------------------------------------------

type AccountType = Literal["asset", "liability", "equity", "revenue", "expense"]


class Account(_Frozen):
    code: str = Field(pattern=r"^\d{4}_[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    type: AccountType


class Scenario(_Frozen):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    available_in: Literal["v1", "v3"]
    starting_equity_account: str  # credited when starting cash is posted on turn 0

    @property
    def selectable(self) -> bool:
        """Only v1 scenarios can be started in this release."""
        return self.available_in == "v1"


class GameData(_Frozen):
    accounts: tuple[Account, ...]
    scenarios: tuple[Scenario, ...]

    @model_validator(mode="after")
    def _check_references(self) -> GameData:
        codes = [a.code for a in self.accounts]
        if len(set(codes)) != len(codes):
            raise ValueError("accounts.yaml has duplicate account codes")
        ids = [s.id for s in self.scenarios]
        if len(set(ids)) != len(ids):
            raise ValueError("scenarios.yaml has duplicate scenario ids")
        equity = {a.code for a in self.accounts if a.type == "equity"}
        for scenario in self.scenarios:
            if scenario.starting_equity_account not in equity:
                raise ValueError(
                    f"scenario {scenario.id!r}: starting_equity_account "
                    f"{scenario.starting_equity_account!r} is not an equity account"
                )
        return self

    def scenario(self, scenario_id: str) -> Scenario | None:
        for scenario in self.scenarios:
            if scenario.id == scenario_id:
                return scenario
        return None

    def account_codes(self) -> frozenset[str]:
        return frozenset(a.code for a in self.accounts)
