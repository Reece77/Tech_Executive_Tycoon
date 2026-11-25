"""Schemas for M53's data and tunables (ADR-0008, docs/formulas.md 62): `telecom.yaml` (history to
2025, every value tagged and sourced) and the `telecom.*` keys of balance.yaml.

telecom.yaml writes values as `[value, tag]` pairs and money as `[value, dollar year, tag]` under
keys ending `_usd` (tags as space.yaml's: S sourced, D derived, R recalled from a named source, A an
assumption). These models keep the numbers and drop the tags; money becomes the game's 2010 cents
with the file's `cpi` once, at load (robotics.yaml's conversion). Model definitions only.
"""

from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import Range, month_to_turn
from tst.sim.robotics.config import _convert
from tst.sim.vehicles.config import interp

type Band = Literal["low", "mid", "high"]
BANDS: Final[tuple[Band, ...]] = ("low", "mid", "high")
type AreaMethod = Literal["auction", "closed"]
YEAR_CHARS: Final = 4  # tunable-exempt: "YYYY-MM"'s year
MOBILE_SEGMENTS: Final = ("telecom_consumer", "telecom_business")
FIXED_SEGMENTS: Final = ("telecom_consumer", "telecom_business")
CARRIER_SEGMENTS: Final = ("carriers",)
OWN_SUPPLIER: Final = "own"  # tunable-exempt: the player's own network_equipment line


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _turn(month: str) -> int | None:
    return month_to_turn(month) if month else None


# --- telecom.yaml: regions, areas and generations (62.1) ---------------------------------------


class AreaDef(_Frozen):
    """A licence area (a country or a group of countries) inside a game region: its share of the
    region's population and how spectrum is assigned there (`closed`: administrative assignment
    to state operators, no auctions for the player, as China's)."""

    key: str
    label: str
    share: float = Field(gt=0, le=1)
    method: AreaMethod = "auction"


class RegionDef(_Frozen):
    """A game region's telecom history to 2025 (real world): mobile and fixed broadband
    subscriptions (millions), fibre's share of fixed, a subscription's revenue a month (ARPU,
    2010 cents), households (millions), the first commercial 4G and 5G months, the macro sites
    a national low-band network needs and its licence areas."""

    key: str
    mobile: dict[int, float]
    fixed: dict[int, float]
    fibre_share: dict[int, float]
    households: dict[int, float]
    arpu_mobile_cents: dict[int, float]
    arpu_fixed_cents: dict[int, float]
    lte: str  # "YYYY-MM"
    nr: str  # "YYYY-MM"
    nr_coverage: dict[int, float] = Field(default_factory=dict)  # 5G population coverage
    sites_full: float = Field(gt=0)  # macro sites for national coverage on low band, real world
    areas: tuple[AreaDef, ...] = Field(min_length=1)

    def mobile_at(self, year: float) -> float:
        return interp(self.mobile, year)

    def fixed_at(self, year: float) -> float:
        return interp(self.fixed, year)

    def households_at(self, year: float) -> float:
        return interp(self.households, year)

    def fibre_at(self, year: float) -> float:
        return interp(self.fibre_share, year)

    def area(self, key: str) -> AreaDef | None:
        return next((a for a in self.areas if a.key == key), None)

    @property
    def lte_turn(self) -> int:
        return month_to_turn(self.lte)

    @property
    def nr_turn(self) -> int:
        return month_to_turn(self.nr)

    @model_validator(mode="after")
    def _shares(self) -> RegionDef:
        total = sum(a.share for a in self.areas)
        if abs(total - 1.0) > 0.011:  # tunable-exempt: shares sum to 1 within rounding
            raise ValueError(f"region {self.key}: area shares sum to {total:.3f}, not 1")
        return self


class GenerationDef(_Frozen):
    """A network generation (62.1): its world first commercial month (6G's is seeded, `first`
    empty), spectral efficiency (bit/s/Hz a sector on mid-band; low band x `low_mult`), a radio's
    cost a site (2010 cents) by year, and the feature points it gives a mobile line."""

    key: str
    label: str
    first: str = ""  # "YYYY-MM"; empty: seeded (balance telecom.g6_window)
    efficiency: float = Field(gt=0)
    radio_cents: dict[int, float]
    feature_points: float = Field(ge=0)
    mid_band_needed: bool = False  # its quality needs mid-band spectrum (5G, 6G)

    @property
    def first_turn(self) -> int | None:
        return _turn(self.first)

    def radio_at(self, year: float) -> float:
        return interp(self.radio_cents, year)


# --- telecom.yaml: operators and vendors (62.3-62.4) -------------------------------------------


class OperatorDef(_Frozen):
    """An incumbent operator's subscribers in a region to 2025 (millions, real world): its
    `mobile` and `fixed_broadband` lines are pinned to them before telecom.start; `wholesale` its
    share of the region's wholesale market. No sales before `first`, none from `last`."""

    company: str  # incumbents.yaml name
    region: str
    mobile: dict[int, float] = Field(default_factory=dict)
    fixed: dict[int, float] = Field(default_factory=dict)
    wholesale: dict[int, float] = Field(default_factory=dict)  # share of the region's wholesale
    first: str = ""
    last: str = ""
    supplier: str = ""  # its main radio vendor (shown; vendors key)

    @property
    def first_turn(self) -> int | None:
        return _turn(self.first)

    @property
    def last_turn(self) -> int | None:
        return _turn(self.last)

    def active(self, turn: int) -> bool:
        f, end = self.first_turn, self.last_turn
        return (f is None or turn >= f) and (end is None or turn < end)

    def mobile_at(self, year: float) -> float:
        return interp(self.mobile, year) if self.mobile else 0.0

    def fixed_at(self, year: float) -> float:
        return interp(self.fixed, year) if self.fixed else 0.0

    def wholesale_at(self, year: float) -> float:
        return interp(self.wholesale, year) if self.wholesale else 0.0


class VendorDef(_Frozen):
    """A network-equipment vendor (62.3): its share of the RAN market by year (world), its
    price against the market's (a radio bought from it costs the generation's radio x this) and
    its incumbents.yaml company (whose network_equipment line is pinned to the share)."""

    key: str
    label: str
    company: str
    origin: str  # countries.yaml key
    share: dict[int, float]
    price_mult: float = Field(gt=0)
    region_mult: dict[str, float] = Field(default_factory=dict)  # region -> x its world share

    def share_at(self, year: float, region: str = "") -> float:
        return interp(self.share, year) * self.region_mult.get(region, 1.0)


# --- telecom.yaml: spectrum auctions (62.2) ----------------------------------------------------


class AuctionDef(_Frozen):
    """A dated spectrum auction (62.2) in a licence area: its band, MHz, blocks, the month it
    ran, its gross proceeds and reserve (2010 cents, real world), its licence term, its coverage
    obligation, and who won how many blocks (operators named in incumbents.yaml; blocks left to
    others go to bidders outside the game). Seeded auctions after 2025 are generated, not
    listed."""

    key: str
    label: str
    region: str
    area: str
    band: Band
    mhz: float = Field(gt=0)
    blocks: int = Field(ge=1)
    month: str
    gross_cents: float = Field(gt=0)
    reserve_cents: float = Field(gt=0)
    rounds: int = Field(default=0, ge=0)  # the real auction's rounds (shown)
    term_years: int = Field(ge=1)
    obligation: float = Field(default=0.0, ge=0, le=1)  # population coverage owed
    obligation_years: int = Field(default=0, ge=0)
    winners: dict[str, int] = Field(default_factory=dict)  # company -> blocks won

    @property
    def turn(self) -> int:
        return month_to_turn(self.month)

    @model_validator(mode="after")
    def _blocks(self) -> AuctionDef:
        if sum(self.winners.values()) > self.blocks:
            raise ValueError(f"auction {self.key}: winners hold more than {self.blocks} blocks")
        if self.reserve_cents > self.gross_cents:
            raise ValueError(f"auction {self.key}: the reserve is above the proceeds")
        return self


# --- telecom.yaml: bans (62.3) ------------------------------------------------------------------


class BanDef(_Frozen):
    """A ban on a vendor's equipment in a licence area (62.3, through 39's rules): no new
    radios from `no_new` and every one replaced by `replace_by` (empty: no removal ordered).
    `scope` is the share of the area's networks it covers (the UK's covers 5G, not 4G)."""

    key: str
    label: str
    vendor: str  # vendors key
    region: str
    area: str
    announced: str
    no_new: str
    replace_by: str = ""
    scope: float = Field(default=1.0, gt=0, le=1)
    reimburse: float = Field(default=0.0, ge=0, le=1)  # share of replacement a programme pays

    @property
    def announced_turn(self) -> int:
        return month_to_turn(self.announced)

    @property
    def no_new_turn(self) -> int:
        return month_to_turn(self.no_new)

    @property
    def replace_turn(self) -> int | None:
        return _turn(self.replace_by)


# --- telecom.yaml: subsea cables, regulation and markets (62.1, 62.4) --------------------------


class CableDef(_Frozen):
    """A named subsea cable (shown; context for the player's own): ready for service, length,
    design capacity (Tbps), the regions it lands in and its owners."""

    key: str
    label: str
    rfs: str
    km: float = Field(gt=0)
    tbps: float = Field(gt=0)
    regions: tuple[str, ...] = Field(min_length=2)
    owners: tuple[str, ...] = Field(min_length=1)


class NeutralityDef(_Frozen):
    """A net-neutrality rule in a licence area (62.4): in force from `start` until `end`
    (empty: still in force). While in force, a line there cannot zero-rate."""

    key: str
    label: str
    region: str
    area: str
    start: str
    end: str = ""

    def in_force(self, turn: int) -> bool:
        s, e = month_to_turn(self.start), _turn(self.end)
        return turn >= s and (e is None or turn < e)


class MergerDef(_Frozen):
    """An operator merger and its review (precedent, shown with the telecom regulator)."""

    key: str
    label: str
    region: str
    announced: str
    decided: str
    outcome: Literal["cleared", "cleared_with_remedies", "blocked", "abandoned"]


class MarketSizeDef(_Frozen):
    key: str
    label: str
    year: int
    size_cents: float = Field(gt=0)  # 2010 cents a year, real world


class TelecomFile(_Frozen):
    regions: tuple[RegionDef, ...] = Field(min_length=1)
    traffic_gb: dict[int, float]  # mobile data a subscription a month, world (GB)
    generations: tuple[GenerationDef, ...] = Field(min_length=1)
    operators: tuple[OperatorDef, ...]
    vendors: tuple[VendorDef, ...] = Field(min_length=1)
    auctions: tuple[AuctionDef, ...]
    bans: tuple[BanDef, ...]
    cables: tuple[CableDef, ...]
    hyperscaler_share: dict[int, float]  # of international capacity content providers own
    neutrality: tuple[NeutralityDef, ...]
    mergers: tuple[MergerDef, ...]
    markets: tuple[MarketSizeDef, ...]
    site_civil_cents: dict[int, float]  # a macro site's mast, power and backhaul (2010 cents)
    fibre_home_cents: dict[int, float]  # fibre a home passed (2010 cents)
    cable_km_cents: dict[int, float]  # a subsea cable a km (2010 cents)

    @model_validator(mode="before")
    @classmethod
    def _parse(cls, raw: Any) -> Any:
        if not isinstance(raw, dict) or "cpi" not in raw:
            return raw
        cpi = {int(y): float(v[0] if isinstance(v, list) else v) for y, v in raw["cpi"].items()}
        return _convert({k: v for k, v in raw.items() if k != "cpi"}, cpi)

    def region(self, key: str) -> RegionDef:
        for r in self.regions:
            if r.key == key:
                return r
        raise KeyError(key)

    def generation(self, key: str) -> GenerationDef:
        for g in self.generations:
            if g.key == key:
                return g
        raise KeyError(key)

    def vendor(self, key: str) -> VendorDef | None:
        return next((v for v in self.vendors if v.key == key), None)

    def vendor_of(self, company: str) -> VendorDef | None:
        return next((v for v in self.vendors if v.company == company), None)

    def operators_of(self, company: str) -> tuple[OperatorDef, ...]:
        return tuple(o for o in self.operators if o.company == company)

    def operator(self, company: str, region: str) -> OperatorDef | None:
        return next(
            (o for o in self.operators if o.company == company and o.region == region), None
        )

    def auction(self, key: str) -> AuctionDef | None:
        return next((a for a in self.auctions if a.key == key), None)

    def traffic_at(self, year: float) -> float:
        return interp(self.traffic_gb, year)

    def hyperscaler_at(self, year: float) -> float:
        return interp(self.hyperscaler_share, year)

    def site_civil_at(self, year: float) -> float:
        return interp(self.site_civil_cents, year)

    def fibre_home_at(self, year: float) -> float:
        return interp(self.fibre_home_cents, year)

    def cable_km_at(self, year: float) -> float:
        return interp(self.cable_km_cents, year)


# --- balance.yaml telecom.* -----------------------------------------------------------------------


class CoverageBalance(_Frozen):
    """Population coverage from sites (62.1): `(sites x density_low / (sites_full x scale x
    density[band])) ** exponent`, at most 1 and at most the licensed areas' share."""

    exponent: float = Field(gt=0, le=1)
    density: dict[str, float]  # band -> sites needed for the same coverage, x low band's


class CapacityBalance(_Frozen):
    """A site's monthly capacity (GB): MHz x efficiency x sectors x seconds a month x
    utilisation / 8,000 (Mbit to GB); low band x `low_mult`, high band x `high_mult`."""

    sectors: int = Field(ge=1)
    utilisation: float = Field(gt=0, le=1)
    low_mult: float = Field(gt=0)
    high_mult: float = Field(gt=0)
    congestion_k: float = Field(ge=0)  # appeal x (capacity / demand) ** this when over
    fixed_gb_mult: float = Field(gt=0)  # a fixed subscription's traffic x a mobile one's
    gbps_per_contract: float = Field(gt=0)  # a wholesale contract's Gbps in 2010
    contract_growth: float = Field(ge=0)  # a contract's Gbps grows this a year from 2010


class FibreBalance(_Frozen):
    max_take_up: float = Field(gt=0, le=1)  # of homes passed that may subscribe
    gb_per_home: float = Field(gt=0)  # a home passed's share of the fibre's capacity a month


class AuctionBalance(_Frozen):
    """Clock auctions (62.2): the price a block rises `increment` a round from the reserve until
    demand fits the blocks; rivals' values a block (hidden) are drawn from their ranges."""

    increment: float = Field(gt=0, le=1)
    max_rounds: int = Field(ge=1)
    notice_months: int = Field(ge=0)  # an auction is announced this many months before it runs
    winner_value: Range  # x the data's price a block, a historical winner's value
    loser_value: Range  # x the data's price a block, the marginal loser's value
    seeded_value: Range  # x the reserve, a seeded auction's rivals' values (lognormal-free uniform)
    seeded_bidders: Range  # rival bidders in a seeded auction
    seeded_every: Range  # years between an area's seeded auctions
    seeded_blocks: Range
    seeded_mhz: dict[str, float]  # band -> MHz on offer in a seeded auction
    seeded_reserve_cents_mhz_pop: dict[str, float]  # band -> reserve a MHz a person (2010 cents)
    seeded_term_years: int = Field(ge=1)
    seeded_obligation: float = Field(ge=0, le=1)
    seeded_obligation_years: int = Field(ge=0)
    max_blocks_share: float = Field(gt=0, le=1)  # a bidder may win at most this share (cap)
    renewal_share: float = Field(ge=0, le=1)  # of the price paid, to renew at the term's end
    deposit_share: float = Field(ge=0, le=1)  # of the limit, held while registered (shown)


class BanBalance(_Frozen):
    swap_mult: float = Field(ge=1)  # a rip-and-replace radio's price x this (removal, integration)
    refuse_share: float = Field(gt=0, le=1)  # a vendor banned in this share of a region is refused
    seeded_window: Range  # years after telecom.start a seeded ban may come (hidden)
    seeded_chance: float = Field(ge=0, le=1)  # an area's chance of a seeded ban in the window
    seeded_replace_years: Range


class CableBalance(_Frozen):
    km: Range  # a cable's length
    ref_tbps: float = Field(gt=0)  # capex x (Tbps / ref) ** tbps_exponent
    tbps_exponent: float = Field(ge=0, le=1)


class RegulationBalance(_Frozen):
    obligation_fine_share: float = Field(ge=0, le=1)  # of the licence's price, a year missed
    obligation_grace_years: int = Field(ge=0)  # after which a missed licence is revoked
    merger_mult: float = Field(ge=1)  # a telecom market's block chance x this (x strictness)
    merger_share: float = Field(gt=0, le=1)  # combined share from which a telecom deal is reviewed
    zero_rating_appeal: float = Field(ge=1)  # a zero-rating line's appeal x this


class SatelliteBalance(_Frozen):
    partner_coverage: float = Field(ge=0, le=1)  # coverage a satellite partner adds (rural)
    partner_fee_share: float = Field(ge=0, le=1)  # of the line's revenue the partner keeps


class TelecomBalance(_Frozen):
    start: str  # "YYYY-MM": history holds before this month
    mobile: str  # categories.yaml keys
    fixed: str
    wholesale: str
    equipment: str
    scale: float = Field(gt=0)
    scale_basis: str
    tower_kind: str  # facility.kinds keys
    radio_kind: str
    fibre_kind: str
    cable_kind: str
    mobile_split: dict[
        str, float
    ]  # segment -> share of a region's (and an operator's) subscriptions
    fixed_split: dict[str, float]
    wholesale_per_sub: float = Field(gt=0)  # wholesale contracts a million mobile subscriptions
    equipment_sites_per_sub: float = Field(gt=0)  # macro site sets a mobile subscription
    growth_after: dict[str, Range]  # region -> subscriptions' yearly growth after 2025 (seeded)
    coverage: CoverageBalance
    capacity: CapacityBalance
    fibre: FibreBalance
    cable: CableBalance
    auction: AuctionBalance
    ban: BanBalance
    regulation: RegulationBalance
    satellite: SatelliteBalance
    traffic_growth_after: float = Field(ge=0)  # mobile data a subscription, yearly after 2025
    g6_window: Range  # years 6G's first commercial month may fall in (seeded, hidden)
    g6_feature_points: float = Field(ge=0)
    rival_cash_cents: int = Field(ge=0)
    history_months: int = Field(ge=1)
    energy: dict[str, int]
    unlock_year: int

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.start)

    @property
    def categories(self) -> tuple[str, str, str, str]:
        return (self.mobile, self.fixed, self.wholesale, self.equipment)

    @property
    def kinds(self) -> tuple[str, str, str, str]:
        return (self.tower_kind, self.radio_kind, self.fibre_kind, self.cable_kind)

    @model_validator(mode="after")
    def _splits(self) -> TelecomBalance:
        for name, split in (("mobile_split", self.mobile_split), ("fixed_split", self.fixed_split)):
            if abs(sum(split.values()) - 1.0) > 1e-6:  # tunable-exempt: float tolerance
                raise ValueError(f"telecom.{name} sums to 1")
        if set(self.coverage.density) != set(BANDS):
            raise ValueError(f"telecom.coverage.density lists {list(BANDS)}")
        return self
