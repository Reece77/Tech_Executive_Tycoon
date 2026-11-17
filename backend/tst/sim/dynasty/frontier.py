"""The technology frontier past 2039 (docs/formulas.md 52.2; M37): research generations come
with longer gaps. At load, every domain whose baseline has no entry from dynasty.start_year
gets one for each decade from it: the rate in force at the end of 2039 x
dynasty.frontier.slowdown^k for the k-th decade (2040s x0.85, 2050s x0.72, 2060s x0.61). A rate
tech_frontier.yaml gives itself for those years wins. Before 2040 every domain's baseline is
unchanged (52.5 target 1). Research budgets' growth is in tst.sim.research.projects."""

from __future__ import annotations

from tst.sim import dmath
from tst.sim.dynasty.config import DynastyBalance
from tst.sim.research.data import TechFrontierFile, rate_in

DECADE = 10  # tunable-exempt: years in a decade


def with_slowdown(tech: TechFrontierFile, rule: DynastyBalance) -> TechFrontierFile:
    domains = []
    for d in tech.domains:
        table = dict(d.baseline.per_year)
        if any(y >= rule.start_year for y in table):
            domains.append(d)
            continue
        last = rate_in(table, rule.start_year - 1)
        for k, year in enumerate(range(rule.start_year, rule.end_year + 1, DECADE), start=1):
            table[year] = last * dmath.pow(rule.frontier.slowdown, k)
        baseline = d.baseline.model_copy(update={"per_year": table})
        domains.append(d.model_copy(update={"baseline": baseline}))
    return tech.model_copy(update={"domains": tuple(domains)})
