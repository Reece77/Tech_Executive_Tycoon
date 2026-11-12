"""Schemas for M22's data and tunables (ADR-0008, docs/formulas.md 39): `countries.yaml`,
`export_controls.yaml`, `tariffs.yaml` and `geopolitics.*` in balance.yaml.

Model definitions only (no file reads, no imports from the rest of the sim), so
`tst.sim.data_models` can import them without a cycle.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tst.sim.facilities.config import month_to_turn

BLOCS: Final = ("us_aligned", "china", "non_aligned")
TOLERANCE: Final = 1e-6  # tunable-exempt: float tolerance on shares summing to 1
type Bloc = Literal["us_aligned", "china", "non_aligned"]
type Regime = Literal["ban", "licence", "quota"]
type GoodKind = Literal["product", "input", "commodity", "facility", "service", "news"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _month(text: str) -> str:
    month_to_turn(text)  # raises on a bad month
    return text


# --- countries.yaml ---------------------------------------------------------------------------


class CountryDef(_Frozen):
    """A country (39.1): its region, bloc in January 2010 and later membership changes, and
    its share of the region's demand."""

    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    region: str
    bloc: Bloc
    bloc_history: tuple[tuple[str, Bloc], ...] = ()
    demand_share: float = Field(ge=0, le=1)
    default: bool = False

    @field_validator("bloc_history")
    @classmethod
    def _months(cls, v: tuple[tuple[str, Bloc], ...]) -> tuple[tuple[str, Bloc], ...]:
        turns = [month_to_turn(m) for m, _ in v]
        if turns != sorted(turns):
            raise ValueError("bloc_history must be in month order")
        return v

    def bloc_at(self, turn: int) -> Bloc:
        bloc = self.bloc
        for month, b in self.bloc_history:
            if month_to_turn(month) <= turn:
                bloc = b
        return bloc


class CountriesFile(_Frozen):
    countries: tuple[CountryDef, ...]
    sites: dict[str, str] = Field(default_factory=dict)  # supplier/maker/foundry -> country
    rivals: dict[str, str] = Field(default_factory=dict)  # rival name -> country
    tension_history: tuple[tuple[str, float], ...]

    @model_validator(mode="after")
    def _check(self) -> CountriesFile:
        keys = [c.key for c in self.countries]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate country keys")
        known = set(keys)
        if bad := sorted({v for v in (*self.sites.values(), *self.rivals.values())} - known):
            raise ValueError(f"unknown countries {bad}")
        regions: dict[str, list[CountryDef]] = {}
        for c in self.countries:
            regions.setdefault(c.region, []).append(c)
        for region, members in regions.items():
            total = sum(c.demand_share for c in members)
            if abs(total - 1) > TOLERANCE:
                raise ValueError(f"{region}: demand shares sum to {total}, not 1")
            if sum(1 for c in members if c.default) != 1:
                raise ValueError(f"{region}: exactly one default country")
        turns = [month_to_turn(m) for m, _ in self.tension_history]
        if not turns or turns[0] != 0 or turns != sorted(turns):
            raise ValueError("tension_history starts in 2010-01 and runs in month order")
        if any(not 0 <= v <= 100 for _, v in self.tension_history):
            raise ValueError("tension is 0-100")
        return self

    def country(self, key: str) -> CountryDef:
        for c in self.countries:
            if c.key == key:
                return c
        raise KeyError(key)

    def by_name(self, name: str) -> CountryDef | None:
        """A country by key, label or alias (commodities.yaml's top_country)."""
        for c in self.countries:
            if name in (c.key, c.label, *c.aliases):
                return c
        return None

    def default_of(self, region: str) -> CountryDef:
        return next(c for c in self.countries if c.region == region and c.default)

    def of_region(self, region: str) -> tuple[CountryDef, ...]:
        return tuple(c for c in self.countries if c.region == region)


# --- export_controls.yaml ---------------------------------------------------------------------


class EntityTarget(_Frozen):
    entity: str = Field(min_length=1)


type Destination = str | EntityTarget


class RuleDef(_Frozen):
    """An export control (39.2). Months are 'YYYY-MM'; seeded rules have none (their month
    is the escalation's)."""

    key: str = Field(min_length=1)
    title: str = Field(min_length=1)
    month: str | None = None
    announced: str | None = None
    end: str | None = None
    actor: str
    goods: tuple[str, ...] = Field(min_length=1)
    to: tuple[Destination, ...] = Field(min_length=1)
    regime: Regime
    approval: float = Field(default=0.0, ge=0, le=1)
    quota: float = Field(default=0.0, ge=0, le=1)
    threshold: float | None = Field(default=None, ge=0, le=100)
    voids_variants: bool = False
    by_ownership: bool = False
    via: Literal["m19"] | None = None
    news: bool = False
    tag: Literal["V", "R"] | None = None
    source: str = ""

    @field_validator("month", "announced", "end")
    @classmethod
    def _valid(cls, v: str | None) -> str | None:
        return None if v is None else _month(v)

    @model_validator(mode="after")
    def _check(self) -> RuleDef:
        if self.month is not None:
            start = month_to_turn(self.month)
            if self.announced is not None and month_to_turn(self.announced) > start:
                raise ValueError(f"{self.key}: announced after it takes effect")
            if self.end is not None and month_to_turn(self.end) < start:
                raise ValueError(f"{self.key}: ends before it takes effect")
            if self.tag is None:
                raise ValueError(f"{self.key}: a historical rule needs a source tag (V or R)")
        if self.regime == "licence" and self.approval <= 0:
            raise ValueError(f"{self.key}: a licence regime needs an approval chance")
        if self.regime == "quota" and self.quota <= 0:
            raise ValueError(f"{self.key}: a quota regime needs a quota share")
        return self

    @property
    def start_turn(self) -> int:
        assert self.month is not None
        return month_to_turn(self.month)

    @property
    def announced_turn(self) -> int:
        return month_to_turn(self.announced) if self.announced else self.start_turn

    @property
    def end_turn(self) -> int | None:
        return month_to_turn(self.end) if self.end else None

    @property
    def countries(self) -> tuple[str, ...]:
        return tuple(d for d in self.to if isinstance(d, str))

    @property
    def entities(self) -> tuple[str, ...]:
        return tuple(d.entity for d in self.to if isinstance(d, EntityTarget))


class DetenteDef(_Frozen):
    key: str = Field(min_length=1)
    title: str = Field(min_length=1)
    month: str
    suspends: tuple[str, ...] = Field(min_length=1)
    months: int = Field(ge=1)
    tag: Literal["V", "R"]
    source: str = ""

    @field_validator("month")
    @classmethod
    def _valid(cls, v: str) -> str:
        return _month(v)

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.month)


class RivalVariantDef(_Frozen):
    """A rival's compliant variant, from history (M23a, 39.3): `company` (an incumbent's or
    entrant's name) sells a cut-down `chip_type` to restricted destinations from `month`, until
    a rule that voids variants launched before it."""

    company: str = Field(min_length=1)
    chip_type: str = Field(min_length=1)
    month: str
    label: str = Field(min_length=1)
    tag: str = "R"

    @property
    def turn(self) -> int:
        return month_to_turn(self.month)


class ExportControlsFile(_Frozen):
    last_month: str
    rules: tuple[RuleDef, ...]
    detentes: tuple[DetenteDef, ...] = ()
    seeded: tuple[RuleDef, ...] = ()
    rival_variants: tuple[RivalVariantDef, ...] = ()  # M23a

    @model_validator(mode="after")
    def _check(self) -> ExportControlsFile:
        keys = [r.key for r in (*self.rules, *self.seeded)]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate rule keys")
        if any(r.month is None for r in self.rules):
            raise ValueError("every historical rule has a month")
        if any(r.month is not None for r in self.seeded):
            raise ValueError("seeded rules take the escalation's month")
        historical = {r.key for r in self.rules}
        for d in self.detentes:
            if bad := sorted(set(d.suspends) - historical):
                raise ValueError(f"{d.key}: suspends unknown rules {bad}")
        return self

    @property
    def last_turn(self) -> int:
        return month_to_turn(self.last_month)

    def rule(self, key: str) -> RuleDef:
        for r in (*self.rules, *self.seeded):
            if r.key == key:
                return r
        raise KeyError(key)


# --- tariffs.yaml -----------------------------------------------------------------------------


class TariffSchedule(_Frozen):
    key: str = Field(min_length=1)
    title: str = Field(min_length=1)
    origin: str  # country key or bloc
    market: str  # country key or bloc
    goods: tuple[str, ...] = Field(min_length=1)
    steps: tuple[tuple[str, float], ...] = Field(min_length=1)
    tag: Literal["V", "R"]

    @field_validator("steps")
    @classmethod
    def _steps(cls, v: tuple[tuple[str, float], ...]) -> tuple[tuple[str, float], ...]:
        turns = [month_to_turn(m) for m, _ in v]
        if turns != sorted(turns) or any(not 0 <= r <= 1 for _, r in v):
            raise ValueError("steps run in month order with rates in 0-1")
        return v

    def rate_at(self, turn: int) -> float:
        rate = 0.0
        for month, r in self.steps:
            if month_to_turn(month) <= turn:
                rate = r
        return rate


class TariffsFile(_Frozen):
    schedules: tuple[TariffSchedule, ...]


# --- balance.yaml geopolitics.* ---------------------------------------------------------------


class GoodDef(_Frozen):
    """A controlled good (39.2): what kind of thing it is in the game and how a control bites.
    `product`: a chip type's products (`chip_types`); `input`: a share `weight` of those chips'
    output needs it; `commodity`: an M17 commodity (`commodity`); `facility`/`service`: M21's
    tools and foundry services; `news`: not traded in the game."""

    label: str = Field(min_length=1)
    kind: GoodKind
    chip_types: tuple[str, ...] = ()
    commodity: str | None = None
    weight: float = Field(default=0.0, ge=0, le=1)


class TensionBalance(_Frozen):
    mean: float = Field(ge=0, le=100)  # the AR(1)'s long-run level after 2025
    phi: float = Field(ge=0, lt=1)  # monthly persistence toward the mean
    sd: float = Field(ge=0)  # monthly noise, points


class ShockBalance(_Frozen):
    base: float = Field(ge=0, le=1)  # monthly chance at tension `pivot`
    slope: float  # chance change per tension point above the pivot (a détente: below)
    pivot: float = Field(ge=0, le=100)
    jump: float = Field(ge=0)  # tension points it adds (escalation) or removes (détente)
    gap_months: int = Field(ge=0)  # no new shock of either kind within this many months


class DetenteBalance(ShockBalance):
    suspend_months: int = Field(ge=1)


class LicenceBalance(_Frozen):
    influence: float = Field(ge=0)  # approval x (1 + influence x I / 100), 39.3
    decision_months: int = Field(ge=1)
    term_months: int = Field(ge=1)
    energy: int = Field(ge=0)


class VariantBalance(_Frozen):
    energy: int = Field(ge=0)
    quality_penalty: float = Field(ge=0, le=100)  # the variant's quality cap below its parent's
    keep: float = Field(gt=0, le=1)  # share of a restricted destination's buyers who take it


class BuyBalance(_Frozen):
    premium: dict[str, float]  # regime -> price premium on the exposed volume (39.3)
    # the share of the exposed volume a licence regime still delivers (a ban 0, a quota its share)
    licence_allowed: float = Field(ge=0, le=1)


class ListingBalance(_Frozen):
    grey_monthly: float = Field(ge=0, le=1)  # listing chance a month while selling unlicensed
    owned_share: float = Field(gt=0, le=1)  # >= this share owned by a listed company (39.3)
    owned_monthly: float = Field(ge=0, le=1)  # its monthly chance without an affiliates rule
    appeal_cents: int = Field(ge=0)
    appeal_chance: float = Field(ge=0, le=1)


class LobbyBalance(_Frozen):
    cents: int = Field(ge=0)
    influence: float = Field(ge=0, le=100)


class PartnerBalance(_Frozen):
    categories: tuple[str, ...]
    countries: tuple[str, ...]
    share: float = Field(gt=0, lt=1)  # the local partner's share of the market's revenue
    energy: int = Field(ge=0)


class GeopoliticsBalance(_Frozen):
    tension: TensionBalance
    escalation: ShockBalance
    detente: DetenteBalance
    licence: LicenceBalance
    variant: VariantBalance
    exit_rate: float = Field(gt=0, le=1)  # blocked customers who leave a month (M22 decision)
    equipment_node: str = "n16"  # chip_equipment controls cover this node and below (M21 merge)
    buy: BuyBalance
    listing: ListingBalance
    lobby: LobbyBalance
    local_partner: PartnerBalance
    goods: dict[str, GoodDef]
    tariff_goods: dict[str, tuple[str, ...]]  # devices/servers/chips -> category keys
    # M23a: export controls bind rivals' sales as the player's (rival variants from history);
    # false gives M22's rule (the player's group only), for comparison runs
    rivals_controlled: bool = True
    actor_regions: dict[str, str] = Field(default_factory=dict)  # bloc -> region for influence

    @model_validator(mode="after")
    def _check(self) -> GeopoliticsBalance:
        for regime in ("ban", "licence", "quota"):
            if regime not in self.buy.premium:
                raise ValueError(f"buy.premium needs {regime!r}")
        return self
