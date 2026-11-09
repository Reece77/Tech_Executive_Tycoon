"""Exploration arithmetic (docs/formulas.md 34.2): the range rule, estimate convergence and the
feasibility NPV. Pure functions of revealed numbers and balance.yaml."""

from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import NormalDist

from tst.sim.exploration.config import ExplorationBalance, FeasibilityBalance


def range_factor(skill: float, eb: ExplorationBalance) -> float:
    """34.2: every range x (skill_base - skill_slope x skill), never below skill_floor."""
    return max(eb.skill_floor, eb.skill_base - eb.skill_slope * skill)


def z_of(confidence: float) -> float:
    """The two-sided normal quantile of a stated confidence (0.9 -> 1.645)."""
    return NormalDist().inv_cdf((1 + confidence) / 2)


def fpc(n: int, cells: int) -> float:
    """Finite-population correction: an ore body has `cells` drill positions and a hole samples
    one not yet drilled, so the mean of n holes converges faster than 1/sqrt(n)."""
    if n >= cells:
        return 0.0
    return math.sqrt((cells - n) / (cells - 1))


def grade_estimate(
    assays: Sequence[float],
    factors: Sequence[float],
    hole_sd: float,
    cells: int,
    confidence: float,
) -> tuple[float, float]:
    """The running grade estimate from n holes (34.2): the log centre is the mean log assay;
    the half-width is z x hole_sd x sqrt(sum f^2) / n x fpc. Each hole's deviation from the
    deposit's grade was drawn x its team's range factor f, so the range holds its confidence."""
    n = len(assays)
    if n == 0:
        raise ValueError("no holes")
    center = sum(math.log(a) for a in assays) / n
    spread = math.sqrt(sum(f * f for f in factors)) / n
    return center, z_of(confidence) * hole_sd * spread * fpc(n, cells)


def half_width_pct(hw: float) -> float:
    """A log half-width as the +/-% it is shown with: the mean of the two sides."""
    return (math.exp(hw) - math.exp(-hw)) / 2


def category_for(holes: int, inferred: int, indicated: int, measured: int) -> str | None:
    """34.2: inferred from 8 holes, indicated from 20, measured from 40."""
    if holes >= measured:
        return "measured"
    if holes >= indicated:
        return "indicated"
    if holes >= inferred:
        return "inferred"
    return None


def annuity(rate: float, years: int) -> float:
    """The present value of 1 a year for `years` years."""
    return (1 - (1 + rate) ** -years) / rate


def npv_usd(
    *,
    tonnage_mt: float,
    grade: float,
    recovery: float,
    capex_usd: float,
    opex_per_t: float,
    price_now: float,
    price_long: float,
    build_years: int,
    fb: FeasibilityBalance,
) -> float:
    """A mine's NPV in dollars at the price deck (34.2): capex spent evenly over the build
    years, then `life_years` of equal output (tonnage x grade x recovery / life), the first
    `deck_years` at the current price and the rest at the long-run level, less operating cost
    and royalty, discounted at `discount_rate`."""
    r, life = fb.discount_rate, fb.life_years
    product = tonnage_mt * 1e6 * grade * recovery / life  # tonnes of product a year
    build = max(build_years, 1)
    capex_pv = capex_usd / build * annuity(r, build)
    start = (1 + r) ** -build
    early = min(fb.deck_years, life)

    def cash(price: float) -> float:
        return product * (price * (1 - fb.royalty) - opex_per_t)

    pv = cash(price_now) * annuity(r, early) if early else 0.0
    if life > early:
        pv += cash(price_long) * (annuity(r, life) - annuity(r, early))
    return pv * start - capex_pv


def capex_usd(
    *,
    tonnage_mt: float,
    grade: float,
    recovery: float,
    intensity: float,
    kind_mult: float,
    infra_km: float,
    depth_m: float,
    fb: FeasibilityBalance,
) -> float:
    """Capex (34.2, dossier 6): capital intensity x annual capacity of product, x the deposit
    type's multiple, x (1 + per km to infrastructure) x (1 + per metre of depth)."""
    product = tonnage_mt * 1e6 * grade * recovery / fb.life_years
    return (
        product
        * intensity
        * kind_mult
        * (1 + fb.infra_capex_per_km * infra_km)
        * (1 + fb.depth_capex_per_m * depth_m)
    )
