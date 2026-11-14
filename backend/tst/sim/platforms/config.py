"""Schemas for M31's data and tunables (ADR-0008, ADR-0021, docs/formulas.md 44):
`platforms.yaml` and `platforms.*` in balance.yaml.

Model definitions only (no file reads), so `tst.sim.data_models` can import them without a cycle.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import month_to_turn

OTHER: Final = "other"  # tunable-exempt: user_shares' residual (feature phones, consoles, the rest)
SHARE_TOLERANCE: Final = 1e-6  # tunable-exempt: a year's regional shares sum to 1 within this

type PlatformKind = Literal["device", "developer"]
type FeeKind = Literal["standard", "subscription", "small_business", "regulated"]
type RuleKind = Literal["alt_payments", "anti_steering_banned", "side_loading"]
type Strictness = Literal["lenient", "standard", "strict"]
type SelfPref = Literal["off", "mild", "strong"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _turn(text: str | None) -> int | None:
    return None if text is None else month_to_turn(text)


# --- platforms.yaml ---------------------------------------------------------------------------


class PlatformDef(_Frozen):
    """A historical platform (44.1)."""

    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    store: str = Field(min_length=1)
    kind: PlatformKind = "device"
    owner: str | None = None  # an incumbents.yaml company name; None = outside the game
    owner_label: str = Field(min_length=1)
    store_opened: str | None = None  # "YYYY-MM"; None = before 2010
    ended: str | None = None
    regions: tuple[str, ...] | None = None  # None = every region
    licensable: bool = False
    side_loading: bool = False
    open_source: str | None = None  # "YYYY-MM" its base opened
    first_party: dict[str, str] = Field(default_factory=dict)  # category -> "YYYY-MM"

    @property
    def ended_turn(self) -> int | None:
        return _turn(self.ended)

    @property
    def opened_turn(self) -> int:
        return _turn(self.store_opened) or 0

    def first_party_from(self, category: str) -> int | None:
        return _turn(self.first_party.get(category))


class FeeRuleDef(_Frozen):
    """A dated fee schedule entry (44.4, ADR-0021 3)."""

    platform: str = Field(min_length=1)
    region: str | None = None  # None = every region
    part: str | None = None  # a regulated rule's country (region_parts)
    from_: str = Field(alias="from")
    kind: FeeKind
    rate: float = Field(ge=0, le=1)
    after_year: bool = False  # subscription: only after a subscriber's first year
    threshold_cents: int | None = Field(default=None, gt=0)  # small_business
    source: str = Field(min_length=1)

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    @property
    def from_turn(self) -> int:
        return month_to_turn(self.from_)

    @model_validator(mode="after")
    def _check(self) -> FeeRuleDef:
        if (self.kind == "small_business") != (self.threshold_cents is not None):
            raise ValueError(
                f"fee rule {self.platform} {self.from_}: threshold only for small_business"
            )
        if (self.kind == "regulated") != (self.region is not None and self.part is not None):
            raise ValueError(
                f"fee rule {self.platform} {self.from_}: regulated needs region and part"
            )
        return self


class RuleDef(_Frozen):
    region: str = Field(min_length=1)
    part: str = Field(min_length=1)
    from_: str = Field(alias="from")
    kind: RuleKind
    platforms: tuple[str, ...] = Field(min_length=1)
    source: str = Field(min_length=1)

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    @property
    def from_turn(self) -> int:
        return month_to_turn(self.from_)


class StandardRuleDef(_Frozen):
    region: str
    from_: str = Field(alias="from")
    source: str = Field(min_length=1)

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class StandardDef(_Frozen):
    """A historical standards contest (44.7)."""

    key: str = Field(min_length=1)
    category: str
    label: str
    formats: tuple[str, str]
    sponsors: dict[str, str] = Field(default_factory=dict)  # format -> platform key
    winner: str
    tipped: str
    rule: StandardRuleDef | None = None

    @model_validator(mode="after")
    def _check(self) -> StandardDef:
        if self.winner not in self.formats or set(self.sponsors) - set(self.formats):
            raise ValueError(f"standard {self.key}: winner and sponsors must be its formats")
        return self


class OpenSourceDef(_Frozen):
    key: str
    label: str
    category: str
    from_: str = Field(alias="from")
    owner_label: str
    source: str = Field(min_length=1)

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class PlatformsFile(_Frozen):
    history_end: str
    region_parts: dict[str, dict[str, float]]
    platforms: tuple[PlatformDef, ...] = Field(min_length=1)
    fee_rules: tuple[FeeRuleDef, ...]
    rules: tuple[RuleDef, ...] = ()
    developers_by_year: dict[int, float] = Field(min_length=1)
    app_counts: dict[str, dict[int, float]] = Field(default_factory=dict)
    standards: tuple[StandardDef, ...] = ()
    open_source: tuple[OpenSourceDef, ...] = ()
    user_shares: dict[str, dict[int, dict[str, float]]]  # region -> year -> platform -> share

    @property
    def history_end_turn(self) -> int:
        return month_to_turn(self.history_end)

    def platform(self, key: str) -> PlatformDef:
        for p in self.platforms:
            if p.key == key:
                return p
        raise KeyError(key)

    def part_share(self, region: str, part: str) -> float:
        parts = self.region_parts[region]
        return parts[part] / sum(parts.values())

    @model_validator(mode="after")
    def _check(self) -> PlatformsFile:
        keys = [p.key for p in self.platforms]
        if len(set(keys)) != len(keys) or OTHER in keys:
            raise ValueError("platforms.yaml: duplicate platform keys (or one named 'other')")
        known = set(keys)
        for rule in self.fee_rules:
            if rule.platform not in known:
                raise ValueError(f"fee rule names unknown platform {rule.platform!r}")
            if rule.part is not None and rule.part not in self.region_parts.get(
                rule.region or "", {}
            ):
                raise ValueError(
                    f"fee rule {rule.platform} {rule.from_}: unknown part {rule.part!r}"
                )
        for r in self.rules:
            if set(r.platforms) - known or r.part not in self.region_parts.get(r.region, {}):
                raise ValueError(f"rule {r.kind} {r.from_}: unknown platform or part")
        standard = {
            p.key
            for p in self.platforms
            if any(r.kind == "standard" for r in self.fee_rules if r.platform == p.key)
        }
        if missing := sorted(known - standard):
            raise ValueError(f"platforms without a standard fee rule: {missing}")
        for region, years in self.user_shares.items():
            for year, shares in years.items():
                if unknown := sorted(set(shares) - known - {OTHER}):
                    raise ValueError(f"user_shares {region} {year}: unknown platforms {unknown}")
                if any(v < 0 for v in shares.values()):
                    raise ValueError(f"user_shares {region} {year}: negative share")
                if abs((total := sum(shares.values())) - 1) > SHARE_TOLERANCE:
                    raise ValueError(f"user_shares {region} {year}: shares sum to {total:.6f}")
        for s in self.standards:
            if set(s.sponsors.values()) - known:
                raise ValueError(f"standard {s.key}: sponsors name unknown platforms")
        for key in self.app_counts:
            if key not in known:
                raise ValueError(f"app_counts names unknown platform {key!r}")
        return self


# --- balance.yaml: platforms.* -----------------------------------------------------------------


class AppCategoryBalance(_Frozen):
    paid_share: float = Field(ge=0, le=1)  # share of revenue that is paid through the store
    subscription_share: float = Field(ge=0, le=1)  # share of that which is subscriptions
    renewal_share: float = Field(ge=0, le=1)  # share of subscriptions past their first year
    segments: tuple[str, ...] = Field(min_length=1)  # the segments distributed through stores


class ReviewBalance(_Frozen):
    base: dict[str, float]  # strictness -> chance of an action a month on a product
    first_party: float = Field(ge=1)  # x when the product competes with the owner's own apps
    own_store: float = Field(ge=1)  # x when the seller runs a competing store
    steering: float = Field(ge=1)  # x when the seller steers users to pay outside
    weights: dict[str, float]  # action -> weight: rejected_update, fee_dispute, removal
    appeal_months: tuple[int, int]  # an appeal's length, lowest and highest
    appeal_odds: tuple[float, float]  # the range shown; the true chance is drawn inside it
    regulator_odds: float = Field(ge=0, le=1)  # going to regulators where rules exist
    removed_loss: float = Field(ge=0, le=1)  # share of the platform's customers lost a month
    recovery_months: int = Field(ge=1)  # months for a relisted product to win them back
    player_removes: dict[str, int]  # the player's strictness -> rivals' apps removed a year
    player_goodwill: dict[str, float]  # ... and its monthly goodwill cost


class OpenSourceBalance(_Frozen):
    adoption: float = Field(ge=1)  # customers x this over `months`, toward the market (44.6)
    months: int = Field(ge=1)
    paid_share: dict[str, float]  # category -> share of customers on the paid tier
    feature_mult: float = Field(ge=1)  # x the product's feature gain a month
    tools_gain: float = Field(ge=0)  # an open OS or developer platform's T_p gain
    goodwill_gain: float = Field(ge=0)
    close_goodwill_loss: float = Field(ge=0)


class StandardsBalance(_Frozen):
    rate: float = Field(ge=0)  # contests a December after the history, on average
    tip_share: float = Field(gt=0.5, le=1)
    penalty: float = Field(ge=0)  # feature points off products on a losing standard
    inertia: float = Field(ge=0, lt=1)  # a month's weight on last month's adoption
    adopt_months: int = Field(ge=0)  # development months to adopt the winner
    categories: tuple[str, ...] = Field(min_length=1)


class RivalPlatformsBalance(_Frozen):
    fee_step: float = Field(ge=0, le=1)  # a rival owner's fee change when it responds
    respond_below: float = Field(
        ge=0, le=1
    )  # it cuts its fee when developer share falls under this x its users
    raise_above: float = Field(ge=1)  # ... and raises it above this
    store_chance: float = Field(ge=0, le=1)  # a rival store in a region that allows one, a year
    licence_switch: float = Field(
        ge=0, le=1
    )  # rest-of-market OEM share that re-chooses each December


class PlatformsBalance(_Frozen):
    start: str  # the first month computed shares and effects run (after the history)
    fees_from: str  # the first month fees post (M31 decision: with the start; see the brief)
    android_licence_cents: int = Field(ge=0)  # a device unit on a licensed Android, from the start
    reach_exp: float = Field(gt=0)  # alpha
    fee_exp: float = Field(gt=0)  # beta
    dev_inertia: float = Field(ge=0, lt=1)
    dev_noise_sd: float = Field(ge=0)
    multihome_share: float = Field(ge=0, le=1)
    multihome_min_users: float = Field(ge=0, le=1)
    catalogue_decay: float = Field(ge=0, lt=1)
    catalogue_points: float = Field(ge=0)
    catalogue_floor: float = Field(ge=0)
    stay: float = Field(ge=0, le=1)
    stay_drop: float = Field(ge=0, le=1)  # stay falls this much per stay_step index points behind
    stay_step: float = Field(gt=0)
    rest_tilt: float = Field(
        ge=0
    )  # the rest of the market's switchers choose by users x (C/C_lead)^this
    dev_churn_cut: float = Field(ge=0, le=1)
    developer_growth: float = Field(ge=0)  # a year, after the data's last point
    tools: tuple[float, float]  # T_p range
    tools_default: float = Field(gt=0)
    goodwill: tuple[float, float]  # G_p range
    goodwill_fee: float = Field(ge=0)  # goodwill a month toward 1 - this x (fee - 0.30)
    goodwill_speed: float = Field(ge=0, le=1)  # share of the gap closed a month
    goodwill_self_pref: dict[str, float]  # self-preferencing -> goodwill target cut
    self_pref_share: dict[str, float]  # self-preferencing -> own apps' share boost
    alternative_share: float = Field(ge=0, le=1)  # sales through a regulated alternative path
    steer_share: float = Field(ge=0, le=1)  # sales a steering seller sends outside
    os_build_features: float = Field(gt=0)  # an own OS launches at this feature score
    own_fee_range: tuple[float, float]  # what an owner may set its standard fee to
    energy: dict[str, int]  # founder energy for each platform action (6)
    switch_energy_months: int = Field(ge=0)  # a device line's switch: months of lost features
    app_categories: dict[str, AppCategoryBalance]
    review: ReviewBalance
    open_source: OpenSourceBalance
    standards: StandardsBalance
    rivals: RivalPlatformsBalance

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.start)

    @property
    def fees_turn(self) -> int:
        return month_to_turn(self.fees_from)
