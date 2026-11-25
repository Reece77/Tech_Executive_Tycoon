"""Networks and generations (docs/formulas.md 62.1): coverage, capacity and quality a company's
networks give it in a region.

- **Sites** are a region's live `tower` facilities' units; **radios** of a generation are those
  of its `tower` and `radio` records (a radio record adds a generation to sites the company already
  has, at most its sites), less sites switched off after a ban's deadline (`dark`).
- **Spectrum:** a band's licensed share of the region is the sum of its licence areas' shares
  where the company holds that band; its MHz is the licences' MHz x their area's share.
- **Coverage** on band b from n sites carrying a generation:
  `min(licensed share_b, (n / (sites_full x scale x density_b)) ** exponent)`; a network's coverage
  is its best band's (none without spectrum: a mobile line can't sell there, but a satellite
  partner adds `satellite.partner_coverage` from direct-to-device's opening).
- **Capacity** (GB a month): for each radio record and band held, sites x MHz x the generation's
  efficiency (x `low_mult` on low band, `high_mult` on high) x sectors x seconds a month x
  utilisation / 8,000. **Demand** is the company's mobile subscribers there x the year's traffic a
  subscription (telecom.yaml). Over capacity, appeal x (capacity / demand) ** congestion_k.
- **Generations** give their feature points on the covered share they carry: a generation that
  needs mid-band (5G, 6G) gives its points in full only where mid-band coverage reaches, and the
  low-band generation's points elsewhere.
- **Fibre** passes `capacity x 1,000` homes (game scale); a fixed line sells to the share of the
  region's households it passes and to at most `fibre.max_take_up` of them.
- **Wholesale** contracts a company can serve in a region are its spare mobile and fibre GB plus
  its subsea cables' landing there, over a contract's GB this year.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.state import GameState
from tst.sim.telecom.config import BANDS
from tst.sim.telecom.data import LAST_YEAR, MILLION, THOUSAND, TINY, end_year_at, file
from tst.sim.telecom.models import RadioNetwork

SECONDS_A_MONTH: Final = 2_592_000  # tunable-exempt: 30 days
MBIT_PER_GB: Final = 8_000  # tunable-exempt: unit conversion
GB_PER_TBPS_SECOND: Final = 125.0  # tunable-exempt: 1 Tbps = 125 GB a second
BASE_YEAR: Final = 2010.0  # tunable-exempt: a contract's Gbps is 2010's


@dataclass(frozen=True, slots=True)
class RegionNetwork:
    """A company's network in a region this month (module docstring)."""

    sites: int
    radios: dict[str, int]  # generation -> sites carrying it (live, not dark)
    licensed: dict[str, float]  # band -> licensed share of the region
    mhz: dict[str, float]  # band -> population-weighted MHz
    coverage: float
    generation_cov: dict[str, float]  # generation -> population it covers
    mid_cov: dict[str, float]  # generation -> population it covers on mid-band
    capacity_gb: float
    homes_passed: float
    fibre_gb: float
    cable_gb: float

    @property
    def best(self) -> str:
        """Its best generation with coverage ("" for none)."""
        best = ""
        for g, c in self.generation_cov.items():
            if c > TINY:
                best = g
        return best


def year_of(state: GameState, balance: Balance) -> float:
    return end_year_at(state.turn)


def _live(state: GameState, facility_id: int) -> int:
    f = state.facility(facility_id)
    return f.live_capacity(state.turn) if f is not None else 0


def radios_in(state: GameState, company_id: int, region: str) -> list[RadioNetwork]:
    return [r for r in state.telecom.radios if r.company_id == company_id and r.region == region]


def sites_in(state: GameState, company_id: int, region: str) -> int:
    """Physical sites: live tower facilities' units."""
    return sum(
        _live(state, r.facility_id) for r in radios_in(state, company_id, region) if not r.overlay
    )


def working(state: GameState, record: RadioNetwork) -> int:
    """A radio record's live sites that are not switched off."""
    return max(0, _live(state, record.facility_id) - record.dark)


def spectrum(
    state: GameState, company_id: int, region: str, data: GameData
) -> tuple[dict[str, float], dict[str, float]]:
    """(licensed share, population-weighted MHz) by band."""
    r = file(data).region(region)
    areas: dict[str, set[str]] = {b: set() for b in BANDS}
    mhz: dict[str, float] = {b: 0.0 for b in BANDS}
    for lic in state.telecom.licences_of(company_id, region):
        a = r.area(lic.area)
        share = a.share if a is not None else 0.0
        areas[lic.band].add(lic.area)
        mhz[lic.band] += lic.mhz * share
    licensed: dict[str, float] = {
        b: min(1.0, float(sum(a.share for a in r.areas if a.key in areas[b]))) for b in BANDS
    }
    return licensed, dict(mhz)


def site_coverage(sites: float, band: str, region: str, balance: Balance, data: GameData) -> float:
    cb = balance.telecom.coverage
    full = file(data).region(region).sites_full * balance.telecom.scale * cb.density[band]
    if full <= 0 or sites <= 0:
        return 0.0
    return min(1.0, float(dmath.pow(sites / full, cb.exponent)))


def _band_mult(band: str, balance: Balance) -> float:
    cap = balance.telecom.capacity
    return cap.low_mult if band == "low" else cap.high_mult if band == "high" else 1.0


def site_gb(mhz: float, efficiency: float, band: str, balance: Balance) -> float:
    """One site's GB a month on `mhz` of a band at a generation's efficiency."""
    cap = balance.telecom.capacity
    return (
        mhz
        * efficiency
        * _band_mult(band, balance)
        * cap.sectors
        * SECONDS_A_MONTH
        * cap.utilisation
        / MBIT_PER_GB
    )


def network(
    state: GameState, company_id: int, region: str, balance: Balance, data: GameData
) -> RegionNetwork:
    f = file(data)
    tb = balance.telecom
    records = radios_in(state, company_id, region)
    sites = sum(_live(state, r.facility_id) for r in records if not r.overlay)
    radios: dict[str, int] = {}
    for r in records:
        radios[r.generation] = radios.get(r.generation, 0) + working(state, r)
    radios = {g: min(n, sites) for g, n in radios.items()}
    licensed, mhz = spectrum(state, company_id, region, data)
    gen_cov: dict[str, float] = {}
    mid_cov: dict[str, float] = {}
    capacity = 0.0
    order = [g.key for g in f.generations]
    for g in order:
        n = radios.get(g, 0)
        if n <= 0:
            continue
        cov = max(
            (min(licensed[b], site_coverage(n, b, region, balance, data)) for b in BANDS),
            default=0.0,
        )
        gen_cov[g] = cov
        mid_cov[g] = min(licensed["mid"], site_coverage(n, "mid", region, balance, data))
        eff = f.generation(g).efficiency
        for b in BANDS:
            if mhz[b] > 0:
                capacity += n * site_gb(mhz[b], eff, b, balance)
    total_working = sum(working(state, r) for r in records if not r.overlay)
    coverage = max(
        (min(licensed[b], site_coverage(total_working, b, region, balance, data)) for b in BANDS),
        default=0.0,
    )
    homes = (
        sum(
            _live(state, x.facility_id)
            for x in state.telecom.fibres
            if x.company_id == company_id and x.region == region
        )
        * THOUSAND
    )
    cable_tbps = 0.0
    for c in state.telecom.cables:
        if c.company_id != company_id or region not in c.regions:
            continue
        fac = state.facility(c.facility_id)
        if fac is not None:
            cable_tbps += fac.live_capacity(state.turn) / len(c.regions)
    cable_gb = cable_tbps * GB_PER_TBPS_SECOND * SECONDS_A_MONTH * tb.capacity.utilisation
    return RegionNetwork(
        sites=sites,
        radios=radios,
        licensed=licensed,
        mhz=mhz,
        coverage=coverage,
        generation_cov=gen_cov,
        mid_cov=mid_cov,
        capacity_gb=capacity,
        homes_passed=homes,
        fibre_gb=homes * tb.fibre.gb_per_home,
        cable_gb=cable_gb,
    )


def feature_points(net: RegionNetwork, balance: Balance, data: GameData) -> float:
    """The generations' feature points over the covered population (module docstring)."""
    if net.coverage <= TINY:
        return 0.0
    f = file(data)
    best = 0.0
    low_points = 0.0
    for g in f.generations:
        cov = net.generation_cov.get(g.key, 0.0)
        if cov <= TINY:
            continue
        points = g.feature_points if g.key != "g6" else balance.telecom.g6_feature_points
        share = min(1.0, cov / net.coverage)
        if g.mid_band_needed:
            mid = min(1.0, net.mid_cov.get(g.key, 0.0) / net.coverage)
            value = points * mid + low_points * max(0.0, share - mid)
        else:
            value = points * share
            low_points = max(low_points, points)
        best = max(best, value)
    return best


def households(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """Households in the region at the game's scale."""
    r = file(data).region(region)
    return r.households_at(year_of(state, balance)) * MILLION * balance.telecom.scale


def traffic_at(year: float, balance: Balance, data: GameData) -> float:
    """Mobile data a subscription a month (GB): telecom.yaml's to 2025, then x (1 +
    `traffic_growth_after`) a year."""
    f = file(data)
    last = float(LAST_YEAR)
    if year <= last:
        return f.traffic_at(year)
    return f.traffic_at(last) * float(
        dmath.pow(1.0 + balance.telecom.traffic_growth_after, year - last)
    )


def traffic_gb(state: GameState, balance: Balance, data: GameData) -> float:
    return traffic_at(year_of(state, balance), balance, data)


def contract_gb(state: GameState, balance: Balance, data: GameData) -> float:
    """A wholesale contract's GB a month this year: its 2010 Gbps grown `contract_growth` a
    year (international capacity grew far slower than mobile data a subscription)."""
    cap = balance.telecom.capacity
    years = max(0.0, year_of(state, balance) - BASE_YEAR)
    gbps = cap.gbps_per_contract * float(dmath.pow(1.0 + cap.contract_growth, years))
    return gbps * GB_PER_TBPS_SECOND / THOUSAND * SECONDS_A_MONTH * cap.utilisation
