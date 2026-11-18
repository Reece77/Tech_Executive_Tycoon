"""Long-run growth (docs/formulas.md 54.1; M43a): after `markets.mature_start_year` each
category's base growth decays toward the economy's growth plus a category premium,

    g(y) = target + (g_start - target) x 0.5 ^ ((y - start) / half_life),
    target = markets.mature_gdp_growth + markets.mature_premium[category],

for every year to the year before dynasty mode's start (M37's maturity takes over from there,
52.2). A rate already at or below its target is unchanged; rates a table lists after the start are
replaced (they are not history: 54.3). Applied at load to categories.yaml's growth and eras.yaml's base_growth."""

from __future__ import annotations

from tst.sim import dmath
from tst.sim.data_models import CategoryDef, RegionalMarketsBalance
from tst.sim.research.data import ErasFile, rate_in

HALF = 0.5  # tunable-exempt: a half-life halves


def _path(
    table: dict[int, float], g0: float, key: str, mb: RegionalMarketsBalance, end: int
) -> dict[int, float] | None:
    """The table with its long-run years (they replace any it lists after the start), or None
    when its rate at the start is already at or below its target."""
    start = mb.mature_start_year
    target = mb.mature_gdp_growth + mb.premium_of(key)
    if g0 <= target:
        return None
    hl = mb.mature_half_life_years
    out = {y: g for y, g in table.items() if y <= start}
    out[start] = g0
    for y in range(start + 1, end + 1):
        out[y] = target + (g0 - target) * dmath.pow(HALF, (y - start) / hl)
    return out


def with_long_run(
    categories: tuple[CategoryDef, ...], eras: ErasFile, mb: RegionalMarketsBalance, end: int
) -> tuple[tuple[CategoryDef, ...], ErasFile]:
    if not mb.mature_premium:
        return categories, eras
    start = mb.mature_start_year
    out = []
    for c in categories:
        new = _path(dict(c.growth_by_year or {}), c.growth_in(start), c.key, mb, end)
        out.append(c if new is None else c.model_copy(update={"growth_by_year": new}))
    base = {}
    for k, t in eras.base_growth.items():
        new = _path(dict(t), rate_in(t, start), k, mb, end)
        base[k] = t if new is None else new
    return tuple(out), eras.model_copy(update={"base_growth": base})
