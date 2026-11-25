"""Frozen telecom records (docs/formulas.md 62). GameState holds one `TelecomState`: the player's
networks (radio records on tower and radio facilities, fibre and subsea cables, each wrapping a
facility, as M38's charging networks), spectrum licences, auctions (announced and run), line
settings (zero-rating, a satellite partner), network months, and the game-wide `TelecomWorld`
(6G's month, subscriptions' growth after 2025, the seeded auction schedule and seeded bans, all
hidden until they come). Persisted in `telecom_record` (migration 0067_m53), one row a record.

Hidden values (62.5): rivals' auction values are drawn when an auction runs and never stored;
`TelecomWorld` is engine-only (the API shows an auction only once announced, a ban once announced,
6G once it arrives)."""

from __future__ import annotations

from dataclasses import dataclass, field

from tst.sim.telecom.config import Band


@dataclass(frozen=True, slots=True)
class RadioNetwork:
    """Radios of one generation from one vendor on `sites` sites in a region (62.1, 62.3): a
    `tower` facility (new sites with their radios) or a `radio` facility (radios added to sites
    the company already has). `replaced` of its sites have had a banned vendor's radios swapped
    (rip-and-replace); `dark` sites are switched off after a ban's deadline."""

    facility_id: int
    company_id: int
    region: str
    generation: str
    vendor: str  # telecom.yaml vendors key, or "own"
    overlay: bool = False  # a radio facility on existing sites
    replaced: int = 0
    dark: int = 0
    replaces_facility_id: int | None = None  # a rip-and-replace order's banned record


@dataclass(frozen=True, slots=True)
class FibreNetwork:
    """Fibre in a region (62.1): a `fibre` facility whose capacity is thousands of homes passed
    (game scale)."""

    facility_id: int
    company_id: int
    region: str


@dataclass(frozen=True, slots=True)
class SubseaCable:
    """A subsea cable (62.1): a `subsea_cable` facility of `tbps` capacity landing in `regions`,
    `km` long; its capacity serves the owner's wholesale line in its landing regions."""

    facility_id: int
    company_id: int
    name: str
    regions: tuple[str, ...]
    km: float


@dataclass(frozen=True, slots=True)
class SpectrumLicence:
    """Spectrum won at auction (62.2): `mhz` in a licence area's band from `turn` to
    `expires_turn`, carried at `paid_cents` and amortized straight line over its term. A coverage
    obligation of `obligation` of the area's population is owed by `obligation_turn`."""

    id: int
    company_id: int
    region: str
    area: str
    band: Band
    mhz: float
    auction_id: int
    paid_cents: int
    turn: int
    expires_turn: int
    obligation: float = 0.0
    obligation_turn: int | None = None
    amortized_cents: int = 0
    status: str = "active"  # active, expired, revoked
    fines: int = 0  # years an obligation was missed and fined


@dataclass(frozen=True, slots=True)
class Award:
    """A bidder's result in an auction: blocks won and the price paid (public once run)."""

    bidder: str  # a company's name (a rival's, the player's, or one outside the game)
    company_id: int | None
    blocks: int
    paid_cents: int


@dataclass(frozen=True, slots=True)
class Auction:
    """A spectrum auction (62.2): announced `notice_months` before `turn`, when it runs as a
    clock auction from `reserve_cents` a block. The player registers `bid_blocks` at most
    `bid_limit_cents` a block. Once run: rounds, the final price a block and the awards."""

    id: int
    key: str  # telecom.yaml auction key, or a seeded auction's
    label: str
    region: str
    area: str
    band: Band
    mhz: float
    blocks: int
    reserve_cents: int  # a block
    turn: int
    term_years: int
    obligation: float
    obligation_years: int
    history: bool  # a dated auction from telecom.yaml
    status: str = "announced"  # announced, closed
    bid_company_id: int | None = None
    bid_blocks: int = 0
    bid_limit_cents: int = 0
    rounds: int = 0
    price_cents: int = 0  # the final price a block
    awards: tuple[Award, ...] = ()


@dataclass(frozen=True, slots=True)
class LineSetting:
    """A telecom line's options (62.2, 62.4): zero-rating (refused where net neutrality is in
    force) and a direct-to-device satellite partner."""

    product_id: int
    zero_rating: bool = False
    satellite_partner: bool = False


@dataclass(frozen=True, slots=True)
class NetworkMonth:
    """A company's network in a region this month (shown, and target 3's cash flow)."""

    turn: int
    company_id: int
    region: str
    sites: int
    coverage: float  # population covered by its best usable generation
    generation: str  # its best generation with coverage
    capacity_gb: float
    demand_gb: float
    homes_passed: float
    subscribers: float
    revenue_cents: int
    spend_cents: int  # capex paid, opex, spectrum, replacement

    @property
    def cash_cents(self) -> int:
        return self.revenue_cents - self.spend_cents


@dataclass(frozen=True, slots=True)
class SeededBan:
    """A seeded ban after 2025 (hidden until `announced_turn`)."""

    vendor: str
    region: str
    area: str
    announced_turn: int
    replace_turn: int


@dataclass(frozen=True, slots=True)
class TelecomWorld:
    """Game-wide telecom draws (hidden): 6G's first month, each region's yearly subscription
    growth after 2025 (year, region index, rate), the next seeded auction month by area, and
    seeded bans."""

    g6_turn: int | None = None
    growth: tuple[tuple[int, int, float], ...] = ()
    next_auction: tuple[tuple[str, int], ...] = ()  # (area key, turn)
    bans: tuple[SeededBan, ...] = ()

    def rate(self, year: int, region_index: int) -> float | None:
        return next((g for y, r, g in self.growth if y == year and r == region_index), None)


@dataclass(frozen=True, slots=True)
class TelecomState:
    radios: tuple[RadioNetwork, ...] = ()
    fibres: tuple[FibreNetwork, ...] = ()
    cables: tuple[SubseaCable, ...] = ()
    licences: tuple[SpectrumLicence, ...] = ()
    auctions: tuple[Auction, ...] = ()
    settings: tuple[LineSetting, ...] = ()
    months: tuple[NetworkMonth, ...] = ()
    cash: tuple[
        tuple[int, str, int, int], ...
    ] = ()  # (company, region, cumulative cash, capex paid)
    paid_back: tuple[tuple[int, str, int], ...] = ()  # (company, region, turn) first month >= 0
    world: TelecomWorld = field(default_factory=TelecomWorld)

    def radio(self, facility_id: int) -> RadioNetwork | None:
        return next((r for r in self.radios if r.facility_id == facility_id), None)

    def setting(self, product_id: int) -> LineSetting | None:
        return next((s for s in self.settings if s.product_id == product_id), None)

    def auction(self, auction_id: int) -> Auction | None:
        return next((a for a in self.auctions if a.id == auction_id), None)

    def licences_of(self, company_id: int, region: str) -> tuple[SpectrumLicence, ...]:
        return tuple(
            x
            for x in self.licences
            if x.company_id == company_id and x.region == region and x.status == "active"
        )

    def next_licence_id(self) -> int:
        return max((x.id for x in self.licences), default=0) + 1

    def next_auction_id(self) -> int:
        return max((a.id for a in self.auctions), default=0) + 1
