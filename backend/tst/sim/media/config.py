"""Schemas for M55's data and tunables (ADR-0008, docs/formulas.md 65): `media.yaml` (history to
2025, every value tagged and sourced) and the `media.*` keys of balance.yaml.

media.yaml writes values as `[value, tag]` pairs and money as `[value, dollar year, tag]` under
keys ending `_usd` (tags as telecom.yaml's). These models keep the numbers and drop the tags; money
becomes the game's 2010 cents with the file's `cpi` once, at load (robotics.yaml's conversion):
media.yaml's billions stay billions of cents (`BILLION` restores them). Model definitions only.
"""

from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import Range, month_to_turn
from tst.sim.robotics.config import _convert
from tst.sim.vehicles.config import interp

type TitleKind = Literal["series", "film", "game"]
KINDS: Final[tuple[TitleKind, ...]] = ("series", "film", "game")
type Platform = Literal["pc", "console", "mobile"]
PLATFORMS: Final[tuple[Platform, ...]] = ("pc", "console", "mobile")
type Monetisation = Literal["premium", "free_to_play"]
type Moderation = Literal["light", "standard", "strong"]
MODERATION_LEVELS: Final[tuple[Moderation, ...]] = ("light", "standard", "strong")
BILLION: Final = 1_000_000_000  # tunable-exempt: media.yaml's money and revenue are billions
MILLION: Final = 1_000_000  # tunable-exempt: media.yaml's users and subscribers are millions


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _year_share(table: dict[int, dict[str, float]], year: float, region: str) -> float:
    """A region's share of a by-year split at a fractional year (interpolated; a year that does
    not list the region holds 0 there), normalised so the regions sum to 1."""
    regions = {r for row in table.values() for r in row}
    values = {r: interp({y: row.get(r, 0.0) for y, row in table.items()}, year) for r in regions}
    total = sum(values[r] for r in sorted(values))  # M57r-A: a fixed order, not the set's
    return values.get(region, 0.0) / total if total > 0 else 0.0


# --- media.yaml ---------------------------------------------------------------------------------


class PrivacyDef(_Frozen):
    """A privacy rule that cuts ad targeting from its month in its regions (65.1)."""

    key: str
    label: str
    month: str
    regions: tuple[str, ...] = Field(min_length=1)
    cut: float = Field(ge=0, lt=1)
    ios_only: bool = False

    @property
    def turn(self) -> int:
        return month_to_turn(self.month)


class AdsDef(_Frozen):
    spend_cents: dict[int, float]  # global ad revenue a year (billions of 2010 cents)
    digital_share: dict[int, float]
    region_share: dict[int, dict[str, float]]
    ios_share: dict[str, float]
    privacy: tuple[PrivacyDef, ...]

    def spend_at(self, year: float, region: str) -> float:
        """A region's ad spend a year (2010 cents, real world) at a fractional year."""
        return (
            interp(self.spend_cents, year) * BILLION * _year_share(self.region_share, year, region)
        )

    def digital_at(self, year: float) -> float:
        return interp(self.digital_share, year)


class FormatDef(_Frozen):
    key: str
    label: str
    month: str

    @property
    def turn(self) -> int:
        return month_to_turn(self.month)


class DivestLawDef(_Frozen):
    company: str
    region: str
    month: str
    deadline: str
    enforced: bool


class GenerationDef(_Frozen):
    key: str
    label: str
    month: str

    @property
    def turn(self) -> int:
        return month_to_turn(self.month)


class StoreFeesDef(_Frozen):
    default: float = Field(ge=0, lt=1)
    epic: float = Field(ge=0, lt=1)
    epic_from: str
    epic_reach: float = Field(gt=0, le=1)


class LootBoxDef(_Frozen):
    key: str
    label: str
    month: str
    until: str | None = None
    region: str
    share: float = Field(ge=0, le=1)
    cut: float = Field(ge=0, le=1)

    def active(self, turn: int) -> bool:
        return month_to_turn(self.month) <= turn and (
            self.until is None or turn < month_to_turn(self.until)
        )


class StrikeDef(_Frozen):
    key: str
    label: str
    region: str
    from_: str = Field(alias="from")
    to: str

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    def active(self, turn: int) -> bool:
        return month_to_turn(self.from_) <= turn <= month_to_turn(self.to)


class LineDef(_Frozen):
    """A rival media line's history (65.7): worldwide customers (millions) or, for games, revenue a
    year (billions of 2010 cents), its split by region, and its first and last months."""

    company: str
    line: str
    category: str
    customers: dict[int, float] = Field(default_factory=dict)
    revenue_cents: dict[int, float] = Field(default_factory=dict)
    split: dict[int, dict[str, float]]
    first: str | None = None
    last: str | None = None
    content_cents: dict[int, float] = Field(default_factory=dict)
    arpu_mult: float = Field(default=1.0, gt=0)
    format: str | None = None

    @model_validator(mode="after")
    def _one_series(self) -> LineDef:
        if bool(self.customers) == bool(self.revenue_cents):
            raise ValueError(f"{self.line}: give customers or revenue_usd, not both")
        return self

    @property
    def first_turn(self) -> int | None:
        return month_to_turn(self.first) if self.first else None

    @property
    def last_turn(self) -> int | None:
        return month_to_turn(self.last) if self.last else None

    def active(self, turn: int) -> bool:
        f, last = self.first_turn, self.last_turn
        return (f is None or turn >= f) and (last is None or turn < last)

    def share(self, year: float, region: str) -> float:
        return _year_share(self.split, year, region)

    def regions(self) -> tuple[str, ...]:
        return tuple(sorted({r for row in self.split.values() for r in row}))


class MediaFile(_Frozen):
    ads: AdsDef
    internet_users: dict[str, dict[int, float]]
    multi_home: dict[int, float]
    arpu_cents: dict[str, dict[int, float]]  # a social user's ad revenue a year (2010 cents)
    formats: tuple[FormatDef, ...] = Field(min_length=1)
    divest_laws: tuple[DivestLawDef, ...]
    streaming_market: dict[str, dict[int, float]]
    music_market: dict[str, dict[int, float]]
    ad_tier_from: str
    licence_availability: dict[int, float]
    games_market_cents: dict[int, float]  # billions of 2010 cents a year
    games_region_share: dict[int, dict[str, float]]
    console_generations: tuple[GenerationDef, ...] = Field(min_length=1)
    store_fees: StoreFeesDef
    loot_box_rules: tuple[LootBoxDef, ...]
    strikes: tuple[StrikeDef, ...]
    lines: tuple[LineDef, ...]
    box_office_cents: dict[int, float]

    @model_validator(mode="before")
    @classmethod
    def _parse(cls, raw: Any) -> Any:
        if not isinstance(raw, dict) or "cpi" not in raw:
            return raw
        cpi = {int(y): float(v[0] if isinstance(v, list) else v) for y, v in raw["cpi"].items()}
        return _convert({k: v for k, v in raw.items() if k != "cpi"}, cpi)

    def lines_of(self, company: str) -> tuple[LineDef, ...]:
        return tuple(x for x in self.lines if x.company == company)

    def line(self, company: str, name: str) -> LineDef | None:
        return next((x for x in self.lines if x.company == company and x.line == name), None)

    def format_keys(self) -> tuple[str, ...]:
        return tuple(f.key for f in self.formats)


# --- balance.yaml media.* -----------------------------------------------------------------------


class AdsBalance(_Frozen):
    """The advertising market (65.1)."""

    digital_ceiling: float = Field(gt=0, le=1)  # digital's share of ad spend approaches this
    digital_approach: float = Field(
        ge=0, le=1
    )  # of the gap to the ceiling closed a year after 2025
    growth_after: Range  # ad spend's yearly growth after 2025 (seeded each January)
    confidence_exponent: float = Field(ge=0)  # x (consumer confidence / 100) ** this
    impressions_per_hour: float = Field(gt=0)
    hours: dict[str, float]  # category -> hours a user (or an ad-tier subscriber) a month
    ad_load: dict[str, float]  # category -> ads an hour x this (the default load)
    load_range: Range  # a player's ad load setting
    targeting_base: float = Field(gt=0)  # targeting = base + quality_weight x quality / 100
    targeting_quality_weight: float = Field(ge=0)
    consumer_apps_from: str  # consumer apps may opt into ad pricing from this month


class KindBalance(_Frozen):
    """A title kind (65.2): its development, typical budget (2010 cents, real), the expected
    revenue at quality 1 (x the typical budget), the hit draw's sigma, the revenue's time
    constant (months) and the amortisation schedule (shares by year from release, summing to 1)."""

    dev_months: int = Field(ge=1)
    typical_budget_cents: int = Field(gt=0)
    min_budget_share: float = Field(gt=0, le=1)  # of the typical budget, the least a title may have
    max_budget_mult: float = Field(ge=1)
    revenue_mult: float = Field(gt=0)
    hit_sigma: float = Field(gt=0)
    tau_months: float = Field(gt=0)
    tail_months: int = Field(ge=1)  # revenue stops this many months after release
    amortisation: tuple[float, ...] = Field(min_length=1)
    audience_m: float = Field(gt=0)  # a typical title's audience (millions, real) at quality 1

    @model_validator(mode="after")
    def _sums(self) -> KindBalance:
        if abs(sum(self.amortisation) - 1.0) > 1e-6:  # tunable-exempt: float tolerance
            raise ValueError("media.kinds.*.amortisation sums to 1")
        return self


class QualityBalance(_Frozen):
    """A title's quality multiplier (65.2): lead x team x budget x franchise x morale."""

    lead_exponent: float = Field(ge=0)  # ((creative + vision) / 2 / 10) ** this
    no_lead: float = Field(gt=0)
    team_exponent: float = Field(ge=0)  # (the unit's development skill / 10) ** this
    no_team: float = Field(gt=0)
    budget_exponent: float = Field(ge=0)  # (budget / typical) ** this
    franchise_k: float = Field(ge=0)  # 1 + k x (prior ratio - 1) x decay
    franchise_years: float = Field(gt=0)  # the franchise's time constant
    franchise_range: Range
    morale_floor: float = Field(gt=0)  # x (floor + span x morale / 100)
    morale_span: float = Field(ge=0)
    range: Range  # the multiplier is clamped to this
    impairment_ratio: float = Field(ge=0, le=1)  # audience under this of expected: written down
    strike_slip: bool = True


class StreamingBalance(_Frozen):
    """Video and music services (65.3)."""

    recency_months: float = Field(gt=0)  # a title's catalogue value decays with this time constant
    appeal_k: float = Field(ge=0)  # appeal x (value / the median service's) ** this
    appeal_range: Range
    churn_k: float = Field(ge=0)  # churn x (the median's / value) ** this
    churn_range: Range
    rival_content_share: float = Field(ge=0, le=1)  # of a rival service's revenue, content a year
    licence_value: float = Field(ge=0)  # catalogue value a licensed dollar a year keeps
    licence_years: Range
    music_payout: float = Field(ge=0, lt=1)
    ad_tier_take: float = Field(ge=0, le=1)  # subscribers who take an ad tier
    ad_tier_price: float = Field(gt=0, le=1)  # x the line's price, an ad tier's
    cash_months: int = Field(ge=1)  # months of service cash shown


class GamesBalance(_Frozen):
    """Games (65.4)."""

    price_cents: dict[str, int]  # platform -> a premium copy's price (2010 cents)
    platform_share: dict[str, float]  # of a typical game's audience on each platform
    payer_share: float = Field(ge=0, le=1)  # free-to-play players who pay in a month
    spend_cents: int = Field(ge=0)  # a paying player's spend a month (2010 cents)
    f2p_audience_mult: float = Field(gt=0)  # a free-to-play title's players x its premium audience
    decay: float = Field(ge=0, lt=1)  # players lost a month without updates
    live_decay: float = Field(ge=0, lt=1)  # with live-service updates
    live_cost_share: float = Field(ge=0)  # of the budget a month, a live-service update
    gen_lift: float = Field(ge=1)  # a console title on a generation's first months sells x this
    gen_lift_months: int = Field(ge=0)
    old_gen_cut: float = Field(gt=0, le=1)  # a console title from before a new generation, after it
    console_every: Range  # years between seeded generations after 2025


class SocialBalance(_Frozen):
    """Social networks (65.5)."""

    network_k: float = Field(ge=0)  # appeal x (share / share_ref) ** this
    share_ref: float = Field(gt=0, le=1)
    appeal_range: Range
    churn_k: float = Field(ge=0)  # churn x (share_ref / share) ** this
    churn_range: Range
    format_advantage: float = Field(ge=1)  # appeal x this on the newest format, for advantage_years
    advantage_years: float = Field(gt=0)
    old_format: float = Field(gt=0, le=1)  # appeal x this an era behind the newest
    format_every: Range  # years between seeded format eras after 2025
    format_names: tuple[str, ...] = Field(min_length=1)  # seeded eras' keys, in order
    rival_adopt_years: Range  # a rival network moves to a new format this long after it arrives
    switch_quality_cut: float = Field(ge=0, lt=1)  # a network's quality x (1 - this) on a switch
    moderation_cents: float = Field(ge=0)  # a user's moderation a month (2010 cents, real)
    moderation_mult: dict[str, float]  # level -> x
    dsa_from: str  # Europe's moderation x dsa_mult from this month
    dsa_mult: float = Field(ge=1)
    light_fine_chance: float = Field(ge=0, le=1)  # a year, light moderation in a DSA region
    fine_share: float = Field(ge=0, le=1)  # of the region's revenue a year
    strong_appeal: float = Field(ge=1)  # strong moderation's appeal x this
    divest_chance: float = Field(ge=0, le=1)  # a year, a seeded law against a foreign network
    divest_min_share: float = Field(ge=0, le=1)  # of the region's users, for a law to come
    divest_notice_months: int = Field(ge=1)
    divest_revenue_mult: float = Field(ge=0)  # a forced sale's price: years of the region's revenue


class TalentBalance(_Frozen):
    """Creative leads (65.6)."""

    pool_size: int = Field(ge=0)  # leads on offer each January
    pool_months: int = Field(ge=1)  # an unsigned lead stays on offer this long
    attribute_mean: float = Field(ge=1, le=20)  # tunable-exempt: the attribute scale
    attribute_sd: float = Field(ge=0)
    trait_sd: float = Field(ge=0)  # hidden ego and loyalty: the personality trait + N(0, this)
    reveal_hw: float = Field(ge=0)  # creative and vision shown +/- this before a title together
    base_fee_cents: int = Field(gt=0)  # a year, an average lead's overall deal (2010 cents, real)
    fee_exponent: float = Field(ge=0)  # x ((creative + vision) / 20) ** this
    reputation_fee: float = Field(ge=0)  # x (1 + this x reputation)
    upfront_share: float = Field(ge=0, le=1)  # of the deal's total paid at signing
    deal_years: Range
    overrule_morale: float = Field(ge=0)  # morale lost at ego 20 (x ego / 20)
    cut_morale: float = Field(ge=0)
    move_morale: float = Field(ge=0)
    overrule_reach: float = Field(ge=0)  # an overrule's audience gain (the commercial cut)
    grievance_keep: float = Field(ge=0, le=1)  # of a title's lost morale its quality keeps losing
    walk_morale: float = Field(ge=0, le=100)  # below this an event may make the lead walk
    walk_chance: float = Field(ge=0, le=1)  # x (21 - loyalty) / 20 x (walk - morale) / walk
    hit_reputation: float = Field(ge=0)  # reputation += this x (ratio - 1)
    reputation_range: Range
    strike_chance: float = Field(ge=0, le=1)  # a region's seeded strike a year after 2025
    strike_months: Range


class MediaBalance(_Frozen):
    start: str  # "YYYY-MM": history holds before this month
    streaming: str  # categories.yaml keys
    music: str
    games: str
    social: str
    consumer_apps: str
    scale: float = Field(gt=0)
    scale_basis: str
    growth_after: dict[str, Range]  # category -> a region's market's yearly growth after 2025
    ads: AdsBalance
    kinds: dict[str, KindBalance]
    quality: QualityBalance
    streaming_service: StreamingBalance
    game_titles: GamesBalance
    social_network: SocialBalance
    talent: TalentBalance
    rival_cash_cents: int = Field(ge=0)
    history_months: int = Field(ge=1)
    energy: dict[str, int]
    unlock_year: int
    lead_role: str  # roles.yaml key a signed creative lead is employed as

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.start)

    @property
    def categories(self) -> tuple[str, str, str, str]:
        return (self.streaming, self.music, self.games, self.social)

    def kind(self, key: str) -> KindBalance:
        return self.kinds[key]

    @model_validator(mode="after")
    def _check(self) -> MediaBalance:
        if set(self.kinds) != set(KINDS):
            raise ValueError(f"media.kinds lists {list(KINDS)}")
        if set(self.game_titles.price_cents) != set(PLATFORMS):
            raise ValueError(f"media.game_titles.price_cents lists {list(PLATFORMS)}")
        if set(self.social_network.moderation_mult) != set(MODERATION_LEVELS):
            raise ValueError(f"media.social_network.moderation_mult lists {MODERATION_LEVELS}")
        return self
