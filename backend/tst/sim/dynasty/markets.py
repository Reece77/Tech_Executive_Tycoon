"""Markets past 2039 (docs/formulas.md 52.2; M37): category growth decays toward a mature rate.
At load, each category's base demand growth (eras.yaml's base_growth where it has one, else
categories.yaml's growth and growth_by_year) gains a rate for every year from dynasty.start_year
to end_year:

    g(y) = mature + (g_2039 - mature) x 0.5 ^ ((y - start_year + 1) / half_life_years)

with `mature` dynasty.markets.mature_growth's for the category (else its default), never above
g_2039. Eras' boosts still add on top, so an era renews a market (52.2). Rates before 2040 are
unchanged (52.5 target 1)."""

from __future__ import annotations

from tst.sim import dmath
from tst.sim.data_models import CategoryDef
from tst.sim.dynasty.config import DynastyBalance
from tst.sim.research.data import ErasFile, rate_in

HALF = 0.5  # tunable-exempt: a half-life halves


def _path(last: float, mature: float, rule: DynastyBalance) -> dict[int, float]:
    target = min(mature, last)
    hl = rule.markets.half_life_years
    return {
        y: target + (last - target) * dmath.pow(HALF, (y - rule.start_year + 1) / hl)
        for y in range(rule.start_year, rule.end_year + 1)
    }


def with_maturity(
    categories: tuple[CategoryDef, ...], eras: ErasFile, rule: DynastyBalance
) -> tuple[tuple[CategoryDef, ...], ErasFile]:
    year = rule.start_year - 1
    out = []
    for c in categories:
        if c.growth_by_year and any(y >= rule.start_year for y in c.growth_by_year):
            out.append(c)
            continue
        table = dict(c.growth_by_year or {})
        table.update(_path(c.growth_in(year), rule.markets.mature(c.key), rule))
        out.append(c.model_copy(update={"growth_by_year": table}))
    base = {}
    for key, table in eras.base_growth.items():
        if any(y >= rule.start_year for y in table):
            base[key] = table
            continue
        base[key] = {**table, **_path(rate_in(table, year), rule.markets.mature(key), rule)}
    return tuple(out), eras.model_copy(update={"base_growth": base})
