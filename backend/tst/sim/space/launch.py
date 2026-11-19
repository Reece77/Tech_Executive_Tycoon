"""Launch vehicles: their cost, cadence and failures (docs/formulas.md 56.1).

- **Reuse level.** A design aims for `expendable`, `recovery` (first-stage recovery) or `full`
  reuse; it flies at the best level at or below its aim that the company's lead in the
  `reusability` domain (over the domain's baseline, 21.1) reaches (`space.reuse.<level>.lead`).
- **Build cost** of an expendable vehicle: `payload x build_cents_per_kg x (payload / ref) **
  (size_exponent - 1) x (1 + quality_cost x (quality - 50) / 100) x learning`, the learning
  `(flights / 1) ** log2(1 - learning_rate)` capped at `max_learning_flights`.
- **A flight's cost** at a level: `B x ((1 - r) + r / N + r x refurb) + ops`, with `r` the level's
  reused share of the vehicle, `N` its flights and `ops = ops_cents_per_kg x payload x (payload /
  ref) ** (size_exponent - 1)`; the payload
  flown is `payload x (1 - payload_cut)`. **Cost per kg** = a flight's cost / the payload flown.
  A fully reusable vehicle is about ten times cheaper a kg than an expendable one of the same era
  (56.4 target 2).
- **Cadence.** A launch site's capacity (units) x the level's `pad_rate` launches a month.
- **Failures** (stream space (1, product_id, flight)): a flight fails with `floor + (new_rate -
  floor) x 0.5 ** (flights flown / half_flights)`, x `(1 + quality_k x (60 - quality) / 100)`, at
  most `max_rate`. A new vehicle's first ten flights fail about ten times as often as its flights
  after fifty (56.4 target 4). The draw is never stored or shown.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.products.models import Product
from tst.sim.space.config import REUSE_LEVELS, ReuseLevel
from tst.sim.space.data import TINY, file, year_at
from tst.sim.space.models import LaunchSpec
from tst.sim.state import GameState

QUALITY_MID: Final = 50.0  # tunable-exempt: the quality a build cost is quoted at
QUALITY_RELIABLE: Final = 60.0  # tunable-exempt: the quality the failure rate is quoted at
HALF: Final = 0.5  # tunable-exempt: a half-life
MIN_MULT: Final = (
    0.5  # tunable-exempt: a floor on the quality cost factor (quality 0 at most halves it)
)
MIN_RATE_MULT: Final = (
    0.2  # tunable-exempt: a floor on the quality failure factor (never below a fifth)
)


@dataclass(frozen=True, slots=True)
class FlightCost:
    level: ReuseLevel
    build_cents: float  # the whole vehicle, made new
    flight_cents: float  # a flight at the level (build share, refurbishment, operations)
    payload_kg: float  # flown at the level
    pad_rate: float

    @property
    def per_kg_cents(self) -> float:
        # money-exact: rate (a cost a kg, shown and compared; nothing posts from it)
        return self.flight_cents / self.payload_kg if self.payload_kg > TINY else 0.0


def capable_level(
    state: GameState, spec: LaunchSpec, company_id: int, balance: Balance
) -> ReuseLevel:
    """The best reuse level at or below the design's aim that the company's lead allows."""
    lead = state.research_lead(company_id, balance.space.domain)
    start = state.space.reuse_start(company_id)
    months = state.turn - start if start is not None else 0
    best: ReuseLevel = "expendable"
    for key in REUSE_LEVELS[: REUSE_LEVELS.index(spec.reuse) + 1]:
        level = balance.space.reuse[key]
        if lead + TINY >= level.lead and months >= level.min_months:
            best = key
    return best


def programme_month(state: GameState, balance: Balance) -> GameState:
    """Phase 9: the month a company's reusability lead first rises starts its programme (the
    levels' `min_months` count from it)."""
    have = {cid for cid, _ in state.space.reuse_started}
    new = [
        (c.id, state.turn)
        for c in state.companies
        if c.is_player and c.id not in have and state.research_lead(c.id, balance.space.domain) > 0
    ]
    if not new:
        return state
    started = tuple(sorted((*state.space.reuse_started, *new)))
    return replace(state, space=replace(state.space, reuse_started=started))


def build_cents(payload_kg: float, quality: float, flights: int, balance: Balance) -> float:
    vb = balance.space.vehicle
    size = dmath.pow(payload_kg / vb.ref_payload_kg, vb.size_exponent - 1)
    quality_mult = 1 + vb.quality_cost * (quality - QUALITY_MID) / 100
    n = max(1, min(flights, vb.max_learning_flights))
    learning = dmath.pow(float(n), dmath.log2(1 - vb.learning_rate)) if vb.learning_rate else 1.0
    # money-exact: rate (a vehicle's build cost, rounded where a flight is posted)
    return payload_kg * vb.build_cents_per_kg * size * max(MIN_MULT, quality_mult) * learning


def ops_cents(payload_kg: float, balance: Balance) -> float:
    """A flight's operations: `ops_cents_per_kg x payload x (payload / ref) ** (size_exponent -
    1)` (big vehicles' range and propellant cost less a kg, as their build does)."""
    vb = balance.space.vehicle
    size = dmath.pow(payload_kg / vb.ref_payload_kg, vb.size_exponent - 1)
    # money-exact: rate (a flight's operations, rounded where a flight is posted)
    return vb.ops_cents_per_kg * payload_kg * size


def flight_cost(
    payload_kg: float, quality: float, flights: int, level: ReuseLevel, balance: Balance
) -> FlightCost:
    sb = balance.space
    lv = sb.reuse[level]
    b = build_cents(payload_kg, quality, flights, balance)
    r = lv.reused_share
    cents = b * ((1 - r) + r / lv.flights + r * lv.refurb_share)
    cents += ops_cents(payload_kg, balance)
    return FlightCost(
        level=level,
        build_cents=b,
        flight_cents=cents,
        payload_kg=payload_kg * (1 - lv.payload_cut),
        pad_rate=lv.pad_rate,
    )


def cost_of(state: GameState, product: Product, balance: Balance) -> FlightCost | None:
    """A vehicle line's flight cost this month (None without a design)."""
    spec = state.space.spec(product.id)
    if spec is None:
        return None
    level = capable_level(state, spec, product.company_id, balance)
    return flight_cost(spec.payload_kg, product.quality, spec.flights, level, balance)


def unit_cents(state: GameState, product: Product, balance: Balance) -> float:
    """A sold launch's cost of goods (the plant hook, tst.sim.hardware.production)."""
    cost = cost_of(state, product, balance)
    if cost is None:
        # money-exact: rate (a placeholder for a line without a design, which cannot sell)
        return balance.space.vehicle.build_cents_per_kg * balance.space.vehicle.ref_payload_kg
    return cost.flight_cents


def failure_rate(flights: int, quality: float, balance: Balance) -> float:
    fb = balance.space.failure
    base = fb.floor + (fb.new_rate - fb.floor) * dmath.pow(HALF, flights / fb.half_flights)
    q = 1 + fb.quality_k * (QUALITY_RELIABLE - quality) / 100
    return float(min(fb.max_rate, max(0.0, base * max(MIN_RATE_MULT, q))))


def site_capacity(state: GameState, company_id: int, balance: Balance) -> float:
    """Launch-site units live this month (each supports `pad_rate` launches a month)."""
    kind = balance.space.site_kind
    return float(
        sum(
            f.live_capacity(state.turn)
            for f in state.company_facilities(company_id)
            if f.kind == kind
        )
    )


def bought_price_cents(state: GameState, balance: Balance, data: GameData) -> tuple[float, float]:
    """(price, payload kg) of a bought launch: space.yaml's reference vehicle at its year's price
    (held at 2025's after the history)."""
    f = file(data)
    v = f.launch.vehicle(f.launch.bought_vehicle)
    assert v is not None
    year = min(year_at(state.turn), 2025.99)  # tunable-exempt: the data's last year
    return v.price_at(year), v.payload_kg


def pads_per_unit(state: GameState, company_id: int, balance: Balance) -> float:
    """Launches a month one launch-site unit flies for the company: the best reuse level its
    vehicle lines fly at (turnaround)."""
    best = balance.space.reuse["expendable"].pad_rate
    for spec in state.space.launch_specs:
        if spec.company_id == company_id:
            level = capable_level(state, spec, company_id, balance)
            best = max(best, balance.space.reuse[level].pad_rate)
    return best
