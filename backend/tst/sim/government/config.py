"""Schemas for M44's data and tunables (ADR-0008, docs/formulas.md 57): `government.yaml` (history
to 2025, every value tagged and cited) and the `government.*` keys of balance.yaml.

government.yaml writes every number as `[value, "TAG:source"]` (or money as `[value, dollar year,
"TAG:source"]` under keys ending `_usd_m` or `_usd_bn`), where TAG is S (sourced), D (derived from
sourced values), R (recalled from a named source) or A (an assumption, its basis named), and
`source` a key of the file's `sources` table: the loader refuses a value without one (57, the
brief's first criterion). These models keep the numbers and drop the tags; money becomes the
game's 2010 cents at real scale with the file's `cpi` once, at load (the game's scale is applied
by the engine, `economy_scale.money`). Model definitions only (no file reads).
"""

from __future__ import annotations

import re
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import Range, month_to_turn
from tst.sim.vehicles.config import interp

BASE_YEAR: Final = 2010  # tunable-exempt: the game's money is in 2010 dollars
CENTS: Final = 100  # tunable-exempt: unit conversion
MILLION: Final = 1_000_000  # tunable-exempt: unit conversion
BILLION: Final = 1_000_000_000  # tunable-exempt: unit conversion
SHOWN: Final = 10  # tunable-exempt: problems an error message lists
PAIR: Final = 2  # tunable-exempt: a [value, tag] pair
TRIPLE: Final = 3  # tunable-exempt: a [value, dollar year, tag] triple
TAG_RE: Final = re.compile(r"^(S|D|R|A):([a-z0-9_]+)$")
MONEY_SUFFIXES: Final = {"_usd_m": MILLION, "_usd_bn": BILLION, "_usd": 1}
# counts and calendar fields, not figures: the record they come from is cited on the tender's value
STRUCTURAL: Final = ("term_years", "awards", "from_year")
AREAS: Final = ("cloud", "ai", "space", "chips", "devices", "cyber")
CONTRACT_TYPES: Final = ("fixed_price", "cost_plus", "idiq")
LEVELS: Final = ("none", "secret", "top_secret")
type Area = Literal["cloud", "ai", "space", "chips", "devices", "cyber"]
type ContractType = Literal["fixed_price", "cost_plus", "idiq"]
type Level = Literal["none", "secret", "top_secret"]
type Buyer = Literal["defence", "civil"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def tag_problems(raw: Any, sources: set[str], path: str = "") -> list[str]:
    """Every number in government.yaml carries a tag naming a source (57; the loader's check)."""
    out: list[str] = []
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k in ("sources", "note", "label", "title", "source", *STRUCTURAL):
                continue
            out += tag_problems(v, sources, f"{path}.{k}" if path else str(k))
        return out
    if isinstance(raw, list):
        if (
            len(raw) >= PAIR
            and isinstance(raw[-1], str)
            and all(isinstance(x, int | float) and not isinstance(x, bool) for x in raw[:-1])
        ):
            if len(raw) not in (PAIR, TRIPLE):
                return [f"{path}: a tagged value is [value, tag] or [value, year, tag]"]
            match = TAG_RE.match(raw[-1])
            if match is None:
                return [f"{path}: tag {raw[-1]!r} is not TAG:source"]
            if match.group(2) not in sources:
                return [f"{path}: source {match.group(2)!r} is not in sources"]
            return []
        for i, x in enumerate(raw):
            out += tag_problems(x, sources, f"{path}[{i}]")
        return out
    if isinstance(raw, bool):
        return []
    if isinstance(raw, int | float):
        return [f"{path}: {raw!r} has no tag and source"]
    return []


def _is_tagged(raw: Any) -> bool:
    return (
        isinstance(raw, list)
        and len(raw) in (PAIR, TRIPLE)
        and isinstance(raw[-1], str)
        and TAG_RE.match(raw[-1]) is not None
        and all(isinstance(x, int | float) for x in raw[:-1])
    )


def convert(raw: Any, cpi: dict[int, float]) -> Any:
    """Drop tags; `*_usd_m` / `*_usd_bn` money -> 2010 cents (real scale) under the key without
    the suffix plus `_cents`. A money series `{year: [value, tag]}` is in each year's dollars."""
    if isinstance(raw, dict):
        out: dict[Any, Any] = {}
        for k, v in raw.items():
            if k in ("sources", "source"):
                continue
            name = str(k)
            suffix = next((s for s in MONEY_SUFFIXES if name.endswith(s)), None)
            if suffix is not None:
                out[name[: -len(suffix)] + "_cents"] = _money(v, cpi, MONEY_SUFFIXES[suffix])
            else:
                out[k] = convert(v, cpi)
        return out
    if _is_tagged(raw):
        return raw[0]
    if isinstance(raw, list):
        return [convert(x, cpi) for x in raw]
    return raw


def _money(raw: Any, cpi: dict[int, float], unit: int, year: int | None = None) -> Any:
    """`[value, dollar year, tag]`, or a `{year: [value, tag]}` series in each year's dollars, ->
    2010 cents."""
    if isinstance(raw, dict):
        return {int(k): _money(v, cpi, unit, int(k)) for k, v in raw.items()}
    if not isinstance(raw, list):
        raise ValueError(f"money is tagged, got {raw!r}")
    if len(raw) == TRIPLE:
        value, dollar_year = float(raw[0]), int(raw[1])
    elif len(raw) == PAIR and year is not None:
        value, dollar_year = float(raw[0]), year
    else:
        raise ValueError(f"money is [value, dollar year, tag], got {raw!r}")
    # money-exact: rate (data's dollars into 2010 dollars at load, real scale)
    return value * unit * CENTS * cpi[BASE_YEAR] / interp(cpi, dollar_year)


# --- government.yaml -------------------------------------------------------------------------


class SourceDef(_Frozen):
    title: str
    url: str = ""


class GovernmentDef(_Frozen):
    """A buying government (57.1): a country of countries.yaml with its defence budget (SIPRI,
    2010 cents a year, real scale) and civil technology budget to 2025, who may bid on its
    tenders (blocs), and whose militaries' suppliers it refuses (57.4)."""

    key: str
    label: str
    country: str  # countries.yaml key
    defence_cents: dict[int, float]  # a year's military expenditure, 2010 cents (real)
    civil_it_cents: dict[int, float] = Field(default_factory=dict)  # civil IT a year (real)
    civil_ratio: float = Field(default=0.0, ge=0)  # civil IT over defence where no series
    open_to: tuple[str, ...]  # blocs (countries.yaml) whose companies may bid
    refuses: tuple[str, ...] = ()  # blocs whose militaries' suppliers it will not buy from
    domestic: tuple[str, ...] = ()  # countries counted as domestic content (its own when empty)

    def defence_at(self, year: float) -> float:
        return interp(self.defence_cents, year)

    def civil_at(self, year: float) -> float:
        if self.civil_it_cents:
            return interp(self.civil_it_cents, year)
        return self.defence_at(year) * self.civil_ratio


class AreaDef(_Frozen):
    """A programme area (57.1): the categories whose products may bid, the shares of a defence and
    a civil technology budget it takes, and whether its defence work is a controlled (ITAR-style)
    item (57.3)."""

    categories: tuple[str, ...]
    defence_share: float = Field(ge=0, le=1)
    civil_share: float = Field(ge=0, le=1)
    controlled: bool = False


class HistoricalTenderDef(_Frozen):
    """A named tender to 2025 (57.1-57.2): announced, closed and awarded as history, its
    winners and protests from the record. Without a player bid, its outcome is the record's."""

    key: str
    title: str
    government: str
    area: Area
    buyer: Buyer = "defence"
    announced: str  # "YYYY-MM"
    closes: str
    awarded: str
    value_cents: float  # ceiling, 2010 cents (real)
    term_years: int = Field(ge=1, le=15)  # tunable-exempt: a validation bound
    contract: ContractType
    awards: int = Field(default=1, ge=1)
    clearance: Level = "none"
    winners: tuple[str, ...]
    protested_by: tuple[str, ...] = ()
    cancelled: str | None = None  # the award cancelled (JEDI, July 2021)
    note: str = ""

    @property
    def announce_turn(self) -> int:
        return month_to_turn(self.announced)

    @property
    def close_turn(self) -> int:
        return month_to_turn(self.closes)

    @property
    def award_turn(self) -> int:
        return month_to_turn(self.awarded)


class BanRuleDef(_Frozen):
    """A component ban (Section 889-style, 57.3): from its month, the governments listed refuse a
    bid whose product is made, in any share, in a listed country."""

    key: str
    label: str
    governments: tuple[str, ...]
    countries: tuple[str, ...]
    start: str  # "YYYY-MM"

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.start)


class ContentStepDef(_Frozen):
    start: str
    share: float = Field(ge=0, le=1)

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.start)


class DomesticContentDef(_Frozen):
    """A domestic-content rule (Buy American-style, 57.3): the least share of a product made in
    the government's domestic countries, stepping up on its dates."""

    governments: tuple[str, ...]
    areas: tuple[Area, ...]
    steps: tuple[ContentStepDef, ...]

    def share_at(self, turn: int) -> float:
        share = 0.0
        for s in self.steps:
            if turn >= s.start_turn:
                share = s.share
        return share


class TrustedFoundryDef(_Frozen):
    """Trusted-foundry rule (57.3): chips for these governments' defence tenders must be made in
    a listed trusted country (own fabs there, or a listed foundry supplier)."""

    governments: tuple[str, ...]
    start: str
    countries: tuple[str, ...]
    suppliers: tuple[str, ...] = ()

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.start)


class ClearanceLevelDef(_Frozen):
    """A clearance level's investigation (57.3): the fastest 90% of initial cases' end-to-end
    days by year (PAC / DCSA), the share of candidates who never clear (denials plus
    discontinued cases) and an investigation's price."""

    p90_days: dict[int, float]
    never_share: float = Field(ge=0, le=1)
    cost_cents: float = Field(ge=0)  # an investigation's price, 2010 cents (real)

    def p90_at(self, year: float) -> float:
        return interp(self.p90_days, year)


class ProtestYearDef(_Frozen):
    """GAO's bid-protest statistics for a fiscal year (57.2)."""

    filed: float
    sustain_rate: float = Field(ge=0, le=1)
    effectiveness: float = Field(ge=0, le=1)


class PrimeDef(_Frozen):
    """A defence prime or newer entrant (57.5), a bidder from the data: its home country, its
    strength by area (technical merit, 0-100), its past performance (0-100) and the years it
    bids. Not a game company: its awards are published records with no books (M44 decision)."""

    name: str
    country: str
    areas: dict[str, float]  # area -> technical merit 0-100
    past_performance: float = Field(ge=0, le=100)
    from_year: int = BASE_YEAR
    revenue_cents: dict[int, float] = Field(default_factory=dict)  # shown (real, 2010 cents)


class CompanyBidderDef(_Frozen):
    """A game company (incumbents or entrants) that bids in an area (57.5: the hyperscalers under
    JWCC-style vehicles): its merit is its best live product's quality there."""

    name: str
    areas: tuple[str, ...]
    past_performance: float = Field(ge=0, le=100)
    from_year: int = BASE_YEAR


class GovernmentFile(_Frozen):
    """government.yaml as the engine reads it (tags dropped, money in 2010 cents at real scale)."""

    cpi: dict[int, float]
    governments: tuple[GovernmentDef, ...]
    areas: dict[str, AreaDef]
    tenders: tuple[HistoricalTenderDef, ...]
    bans: tuple[BanRuleDef, ...]
    domestic_content: tuple[DomesticContentDef, ...]
    trusted_foundry: TrustedFoundryDef
    controlled_countries: tuple[str, ...]  # a controlled item may never be sold there (126.1)
    clearances: dict[str, ClearanceLevelDef]
    facility_clearance_months: Range
    protests: dict[int, ProtestYearDef]
    primes: tuple[PrimeDef, ...]
    company_bidders: tuple[CompanyBidderDef, ...]

    @model_validator(mode="before")
    @classmethod
    def _parse(cls, raw: Any) -> Any:
        """Check every number's tag and source (57; a value without one fails at load), then drop
        the tags and convert money with the file's cpi."""
        if not isinstance(raw, dict) or "sources" not in raw:
            return raw
        sources = raw["sources"]
        if not isinstance(sources, dict):
            raise ValueError("sources must map keys to citations")
        for key, cite in sources.items():
            SourceDef.model_validate(cite)
            if not re.match(r"^[a-z0-9_]+$", str(key)):
                raise ValueError(f"source key {key!r}")
        if problems := tag_problems(raw, set(sources)):
            raise ValueError("uncited values: " + "; ".join(problems[:SHOWN]))
        cpi = {int(y): float(v[0] if isinstance(v, list) else v) for y, v in raw["cpi"].items()}
        body = convert({k: v for k, v in raw.items() if k != "cpi"}, cpi)
        body["cpi"] = cpi
        return body

    @model_validator(mode="after")
    def _check(self) -> GovernmentFile:
        keys = [g.key for g in self.governments]
        if len(set(keys)) != len(keys):
            raise ValueError("government keys repeat")
        if set(self.areas) != set(AREAS):
            raise ValueError(f"areas must be exactly {list(AREAS)}")
        for t in self.tenders:
            if t.government not in keys:
                raise ValueError(f"tender {t.key}: unknown government {t.government!r}")
            if not t.announce_turn <= t.close_turn <= t.award_turn:
                raise ValueError(f"tender {t.key}: announced <= closes <= awarded")
        for level in ("secret", "top_secret"):
            if level not in self.clearances:
                raise ValueError(f"clearances needs {level}")
        return self

    def government(self, key: str) -> GovernmentDef:
        return next(g for g in self.governments if g.key == key)

    def government_index(self, key: str) -> int:
        return next(i for i, g in enumerate(self.governments) if g.key == key)

    def prime(self, name: str) -> PrimeDef | None:
        return next((p for p in self.primes if p.name == name), None)

    def protest_year(self, year: int) -> ProtestYearDef:
        years = sorted(self.protests)
        best = years[0]
        for y in years:
            if y <= year:
                best = y
        return self.protests[best]


# --- balance.yaml government.* ---------------------------------------------------------------


class ScoreWeights(_Frozen):
    price: float = Field(ge=0)
    technical: float = Field(ge=0)
    past_performance: float = Field(ge=0)


class TenderBalance(_Frozen):
    per_year: dict[str, int]  # government -> seeded tenders a year
    tendered_share: float = Field(gt=0, le=1)  # of an area's budget that is openly tendered
    bid_months: int = Field(ge=1)  # an announced tender takes bids this long
    evaluation_months: int = Field(ge=0)  # then the award
    term_years: Range  # a seeded tender's term
    option_share: float = Field(ge=0, le=1)  # of a term that is options after the base years
    large_cents: int = Field(ge=0)  # a large tender's value (game scale; 57.6 target 2)
    contract_mix: dict[str, float]  # contract type -> share of seeded tenders
    clearance_mix: dict[str, dict[str, float]]  # buyer -> level -> share
    value_sigma: float = Field(ge=0)  # lognormal spread of a seeded tender's value
    idiq_awards: Range  # awardees of a seeded IDIQ vehicle
    history_months: int = Field(ge=1)  # closed tenders kept this long


class BudgetBalance(_Frozen):
    """Budgets after 2025 (57.1): a year's growth = trend + tension x (T - 50)/50 + noise."""

    trend: float
    tension: float
    noise: float = Field(ge=0)


class BidBalance(_Frozen):
    weights: ScoreWeights
    large_weights: ScoreWeights  # large tenders weigh past performance more
    capture_skills: tuple[str, ...]
    capture_weight: float = Field(ge=0, le=1)  # of technical merit from the capture team
    capture_max: int = Field(ge=1)
    cost_bp: int = Field(ge=0)  # a proposal's cost, of the bid price over the first year (bp)
    min_cost_cents: int = Field(ge=0)
    price_floor: float = Field(gt=0)  # a bid's least price over the tender's value
    price_cap: float = Field(gt=0)
    band: int = Field(ge=1)  # score bands' width
    rival_bid_chance: float = Field(ge=0, le=1)
    rival_price: Range  # a rival's price over the value (uniform)
    rival_merit_sd: float = Field(ge=0)
    history_bonus: float = Field(ge=0)  # a historical winner's merit lift (keeps the record)
    pp_full: int = Field(ge=1)  # delivered contracts for full past-performance credit
    newcomer_pp: float = Field(ge=0, le=100)  # a company with no record


class ProtestBalance(_Frozen):
    rival_chance: float = Field(ge=0, le=1)  # a losing rival protests (large tenders x large_mult)
    large_mult: float = Field(ge=1)
    delay_months: Range
    cost_cents: int = Field(ge=0)  # the player's protest (legal fees)
    window_months: int = Field(ge=1)


class DeliveryBalance(_Frozen):
    cost_share: dict[str, float]  # area -> delivery cost over the contract's revenue
    cost_plus_fee: float = Field(ge=0)
    idiq_orders: Range  # a month's task orders over the vehicle's monthly ceiling (uniform)
    overrun_sd: dict[str, float]  # contract type -> a month's cost overrun spread
    overrun_mean: float
    perf_per_overrun: float = Field(ge=0)  # performance points lost per 1% overrun
    option_threshold: float = Field(ge=0, le=100)  # performance for an option's exercise
    lapse_months: int = Field(ge=1)  # months unable to deliver before default


class ClearanceBalance(_Frozen):
    median_of_p90: float = Field(gt=0)  # a case's median days over the fastest-90% days
    sponsor_months: float = Field(ge=0)  # sponsorship and forms before the investigation opens
    sigma: float = Field(ge=0)  # lognormal spread of months to a decision
    integrity_mult: float = Field(ge=0)  # never-clear share x (1 + this x (10 - integrity)/10)
    facility_cost_cents: int = Field(ge=0)
    required: dict[str, int]  # level -> cleared staff a classified bid needs


class ReputationBalance(_Frozen):
    consumer_categories: tuple[str, ...]
    brand_first: float = Field(ge=0)  # brand points the first defence award costs a consumer line
    brand_next: float = Field(ge=0)
    brand_year_cap: float = Field(ge=0)
    persona: dict[str, float]  # trait -> points a defence award adds
    influence: float = Field(ge=0)  # influence points a defence award adds in its region
    objector_interests: tuple[str, ...]
    low_tolerance: float  # adaptability at or below this objects
    morale_pct: float  # objectors' morale target modifier (percent)
    morale_months: int = Field(ge=1)
    letter_base: float = Field(ge=0, le=1)
    letter_slope: float = Field(ge=0)
    letter_max: float = Field(ge=0, le=1)
    resign_share: Range  # of objectors who resign when the company carries on
    withdraw_brand: float = Field(ge=0)
    board_cents: int = Field(ge=0)  # an ethics board's cost


class GovernmentBalance(_Frozen):
    start: str  # "YYYY-MM": data budgets before, seeded from it
    tenders: TenderBalance
    budgets: BudgetBalance
    bids: BidBalance
    protests: ProtestBalance
    delivery: DeliveryBalance
    clearances: ClearanceBalance
    reputation: ReputationBalance
    itar_keep: dict[str, float]  # bloc -> share of demand a controlled item keeps there
    energy: dict[str, int]
    unlock_year: int

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.start)

    @model_validator(mode="after")
    def _check(self) -> GovernmentBalance:
        if set(self.tenders.contract_mix) != set(CONTRACT_TYPES):
            raise ValueError(f"tenders.contract_mix needs {list(CONTRACT_TYPES)}")
        for buyer, mix in self.tenders.clearance_mix.items():
            if set(mix) != set(LEVELS):
                raise ValueError(f"tenders.clearance_mix.{buyer} needs {list(LEVELS)}")
        if set(self.delivery.cost_share) != set(AREAS):
            raise ValueError(f"delivery.cost_share needs {list(AREAS)}")
        return self
