"""Frozen space records (docs/formulas.md 56). GameState holds one `SpaceState`: the player's launch
vehicle designs (by product id), constellations with their satellites in orbit by cohort, landing
and spectrum licences by region, the launches flown (`space.history_months`), constellation
months, and the game-wide `SpaceWorld` (rivals' seeded growth after 2025 and the seeded debris
rule). Persisted in `space_record` (migration 0063_m40), one row a record.

Hidden values (56.5): `SpaceWorld.growth` (each year's drawn rate), `SpaceWorld.debris_turn`
before it comes and a licence's `decision_turn` are engine-only: the API never returns them.
Failure draws are never stored; a launch's outcome is public once flown."""

from __future__ import annotations

from dataclasses import dataclass, field

from tst.sim.space.config import ConstellationKind, ReuseLevel


@dataclass(frozen=True, slots=True)
class LaunchSpec:
    """A launch vehicle's design (56.1) on a `launch` product: payload to LEO (expendable), the
    reuse level it aims for (flown at the best the company's reusability lead allows), and its
    record: flights, failures, the grounding after a failure, and customer launches sold but not
    yet flown (`pending`, a fraction until a whole launch is due)."""

    product_id: int
    company_id: int
    payload_kg: float
    reuse: ReuseLevel
    flights: int = 0
    failures: int = 0
    grounded_until: int | None = None
    pending: float = 0.0
    first_flight_turn: int | None = None


@dataclass(frozen=True, slots=True)
class Cohort:
    """Satellites launched together into a shell (56.2): they serve until `retire_turn`, carrying
    `cost_cents` of capitalized cost between them (the satellites and their launch)."""

    shell: int
    launch_turn: int
    count: int
    cost_cents: int
    retire_turn: int
    depreciated_cents: int = 0


@dataclass(frozen=True, slots=True)
class ConstellationMonth:
    turn: int
    constellation_id: int
    in_orbit: int
    built: int
    launched: int
    lost: int
    retired: int
    capacity_gbps: float
    covered: tuple[str, ...]
    subscribers: float
    revenue_cents: int
    spend_cents: int  # cash out: satellites, launches, ground stations, disposal, premiums

    @property
    def cash_cents(self) -> int:
        return self.revenue_cents - self.spend_cents


@dataclass(frozen=True, slots=True)
class Constellation:
    """A constellation (56.2): `shells` planned shells of `constellation.shell_sats` satellites of
    one design (mass, life, D2D), built `build_per_month` a month in the group's satellite plants
    (or bought), and launched `launches_per_month` a month on an own vehicle (`vehicle_product_id`)
    or on bought launches (None). `ground` satellites are built and waiting for a launch. It serves
    the product `product_id` (a satellite_broadband or earth_observation line)."""

    id: int
    company_id: int
    name: str
    kind: ConstellationKind
    product_id: int | None
    shells: int
    mass_kg: float
    life_months: int
    d2d: bool
    insured: bool
    build_per_month: int
    launches_per_month: int
    vehicle_product_id: int | None
    created_turn: int
    ground: int = 0
    cohorts: tuple[Cohort, ...] = ()
    capex_cents: int = 0  # capitalized satellites and launches in service or waiting
    depreciated_cents: int = 0
    cash_cents: int = 0  # cumulative cash flow since it was created (payback, 56.4 target 3)
    paid_back_turn: int | None = None
    lost: int = 0  # satellites lost in failed launches, all time
    event_turn: int | None = None  # the month a lost-satellites critical event is shown
    event_sats: int = 0  # satellites the event's failure lost
    event_value_cents: int = 0  # their value, written off
    event_vehicle_id: int | None = None  # the own vehicle line that failed (None: bought)
    month: ConstellationMonth | None = None

    def in_orbit(self) -> int:
        return sum(c.count for c in self.cohorts)

    def in_shell(self, shell: int) -> int:
        return sum(c.count for c in self.cohorts if c.shell == shell)


@dataclass(frozen=True, slots=True)
class Licence:
    """Landing rights and spectrum in a region (56.3): `applied`, `granted` or `refused`. The
    decision month is hidden until it comes."""

    company_id: int
    region: str
    status: str
    applied_turn: int
    decision_turn: int | None = None
    granted_turn: int | None = None


@dataclass(frozen=True, slots=True)
class LaunchRecord:
    """A launch flown (public once flown). `purpose`: `customer` (a sold launch) or `own` (the
    constellation's satellites); `product_id` the vehicle line flown (None: a bought launch)."""

    turn: int
    company_id: int
    product_id: int | None
    vehicle: str
    purpose: str
    constellation_id: int | None
    satellites: int
    ok: bool
    insured_cents: int = 0  # the insurer's payment for a lost payload


@dataclass(frozen=True, slots=True)
class SpaceWorld:
    """Game-wide space state. `growth`: (year, rate) rivals' launches and satellites a year after
    2025 (hidden); `debris_turn`: the seeded month a tighter debris rule arrives (hidden before);
    `terminals`: user terminals made by the player, all time (the cost's learning curve)."""

    growth: tuple[tuple[int, float], ...] = ()
    debris_turn: int | None = None
    terminals: float = 0.0

    def growth_of(self, year: int) -> float | None:
        return next((g for y, g in self.growth if y == year), None)


@dataclass(frozen=True, slots=True)
class SpaceState:
    launch_specs: tuple[LaunchSpec, ...] = ()
    constellations: tuple[Constellation, ...] = ()
    licences: tuple[Licence, ...] = ()
    launches: tuple[LaunchRecord, ...] = ()
    months: tuple[ConstellationMonth, ...] = ()
    world: SpaceWorld = field(default_factory=SpaceWorld)
    reuse_started: tuple[tuple[int, int], ...] = ()  # (company id, the month its lead first rose)
    terminal_prices: tuple[tuple[int, int], ...] = ()  # (product id, a terminal's price, cents)
    d2d_partners: tuple[int, ...] = ()  # broadband product ids with a carrier partner

    def spec(self, product_id: int) -> LaunchSpec | None:
        return next((s for s in self.launch_specs if s.product_id == product_id), None)

    def constellation(self, cid: int) -> Constellation | None:
        return next((c for c in self.constellations if c.id == cid), None)

    def licence(self, company_id: int, region: str) -> Licence | None:
        return next(
            (x for x in self.licences if x.company_id == company_id and x.region == region), None
        )

    def licensed(self, company_id: int, region: str) -> bool:
        lic = self.licence(company_id, region)
        return lic is not None and lic.status == "granted"

    def reuse_start(self, company_id: int) -> int | None:
        return next((t for cid, t in self.reuse_started if cid == company_id), None)

    def terminal_price(self, product_id: int) -> int | None:
        return next((p for pid, p in self.terminal_prices if pid == product_id), None)

    def is_empty(self) -> bool:
        return not (self.launch_specs or self.constellations or self.licences or self.launches)
