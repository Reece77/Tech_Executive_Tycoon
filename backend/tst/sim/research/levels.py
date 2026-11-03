"""Domain levels, leads and the tech factor (docs/formulas.md 21.1-21.2, 21.4).

A company's level in a domain is the world's baseline `D_d(t)` plus its own lead `R_c,d`.
The baseline accrues from `tech_frontier.yaml` month by month and rises `rnd.era_baseline`
with each arrived era of the domain. `tech_factor` is the one hook the product code and the
rivals call (21.2): a company that never researches has a factor of exactly 1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from tst.sim.calendar import MONTHS_PER_YEAR, ym_to_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.research.data import DomainDef, EraDef, rate_in
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

START_YEAR = 2010  # tunable-exempt: turn 0 is January 2010 (ADR-0006)


def domain_def(data: GameData, domain: str) -> DomainDef:
    assert data.tech is not None
    for d in data.tech.domains:
        if d.key == domain:
            return d
    raise KeyError(domain)


def domain_keys(data: GameData) -> tuple[str, ...]:
    return tuple(d.key for d in data.tech.domains) if data.tech else ()


def accrued(domain: DomainDef, turn: int) -> float:
    """The baseline from the data alone at the start of month `turn`: `start` plus
    per_year / 12 for each month before it (21.1), without era steps."""
    value = domain.baseline.start
    year = START_YEAR
    left = turn
    while left > 0:
        months = min(left, MONTHS_PER_YEAR)
        value += rate_in(domain.baseline.per_year, year) * months / MONTHS_PER_YEAR
        left -= months
        year += 1
    return value


def historical_turn(era: EraDef) -> int:
    """The era's public reference month: its historical arrival, or for a future era its
    window's midpoint `t_start + floor(n / 2)` (26.4). Never the drawn scheduled month."""
    if era.window is None:
        return ym_to_turn(*era.arrival)
    start, n = window_span(era)
    return start + n // 2


def window_span(era: EraDef) -> tuple[int, int]:
    """(t_start, n): a future era's first month and its number of months (26.4)."""
    assert era.window is not None
    start, end = era.window
    t0 = ym_to_turn(*start)
    return t0, ym_to_turn(*end) - t0 + 1


def scheduled_month(t_start: int, months: int, u: float) -> int:
    """t_sched = t_start + floor(u x n) (26.4)."""
    return t_start + min(months - 1, math.floor(u * months))


def scheduled_turn(era: EraDef, era_index: int, rng: RngFactory) -> int:
    """When an era is due: its historical month, or for a future era one uniform from stream
    `era_window` at turn 0, key (era_index,) with era_index its position in eras.yaml (26.4).
    A pure function of the seed: nothing is stored. Engine only: never sent to the API or a
    prompt before the era arrives (ADR-0007)."""
    if era.window is None:
        return historical_turn(era)
    start, n = window_span(era)
    u = float(rng.stream(0, "era_window", era_index).random())
    return scheduled_month(start, n, u)


def eras_in(data: GameData, domain: str) -> tuple[EraDef, ...]:
    return tuple(e for e in data.eras.eras if e.domain == domain)


def baseline(state: GameState, data: GameData, balance: Balance, domain: str) -> float:
    """D_d(t) this month: accrued plus era_baseline for each era of the domain that has
    arrived (21.1, 21.4)."""
    arrived = sum(
        1
        for e in eras_in(data, domain)
        if (a := state.era_arrival(e.key)) is not None and a.turn <= state.turn
    )
    return accrued(domain_def(data, domain), state.turn) + balance.rnd.era_baseline * arrived


def level(
    state: GameState, data: GameData, balance: Balance, company_id: int, domain: str
) -> float:
    return baseline(state, data, balance, domain) + state.research_lead(company_id, domain)


def threshold(data: GameData, balance: Balance, era: EraDef) -> float:
    """The level that causes an era early (21.4): the domain's baseline at the end of the
    era's historical month, with the eras of its domain historically before it, plus
    rnd.era_lead. Transformers: 23.5 + 5 + 15 = 43.5 (21.9). A future era reads its window's
    midpoint, so the threshold never reveals the drawn month (26.4): chiplets 81.375."""
    hist = historical_turn(era)
    before = sum(1 for e in eras_in(data, era.domain) if historical_turn(e) < hist)
    base = accrued(domain_def(data, era.domain), hist + 1)
    return base + balance.rnd.era_baseline * before + balance.rnd.era_lead


def lead(state: GameState, company_id: int, domain: str) -> float:
    """A company's lead in a domain (21.1). M12a's Cloud hosting reads it: keep this
    signature stable."""
    return state.research_lead(company_id, domain)


def category_lead(state: GameState, data: GameData, company_id: int, category: str) -> float:
    """R_cat = sum of w_d x R_d with the category's tech weights (21.1)."""
    if data.tech is None:
        return 0.0
    weights = data.tech.tech_weights.get(category, {})
    return sum(w * state.research_lead(company_id, d) for d, w in weights.items())


def feeds(data: GameData, domain: str) -> tuple[str, ...]:
    """Categories a domain feeds (a positive tech weight), in tech_weights order."""
    if data.tech is None:
        return ()
    return tuple(c for c, w in data.tech.tech_weights.items() if w.get(domain, 0) > 0)


@dataclass(frozen=True, slots=True)
class TechFactor:
    """What a company's lead does for a product in one category (21.2) and the first
    mover's window (21.4). The identity (1, 0, 1, 0) for a company with no lead and no
    window."""

    cap_mult: float = 1.0
    cap_points: float = 0.0
    feature_mult: float = 1.0
    brand_points: float = 0.0
    lead: float = 0.0  # R_cat, for the breakdowns

    def cap(self, q_cap: float) -> float:
        """Q_cap x (1 + cap_per_point x min(R_cat, cap_points)) + first-mover points."""
        if self.cap_mult == 1 and self.cap_points == 0:
            return q_cap
        return q_cap * self.cap_mult + self.cap_points

    @property
    def is_identity(self) -> bool:
        return self == IDENTITY


IDENTITY = TechFactor()


def first_mover_eras(
    state: GameState, data: GameData, balance: Balance, company_id: int
) -> tuple[EraDef, ...]:
    """Eras whose first-mover window the company holds this month (21.4)."""
    out = []
    months = balance.rnd.first_mover_months
    for era in data.eras.eras:
        a = state.era_arrival(era.key)
        if a is not None and a.company_id == company_id and a.turn <= state.turn < a.turn + months:
            out.append(era)
    return tuple(out)


def tech_factor(
    state: GameState, company_id: int, category: str, balance: Balance, data: GameData
) -> TechFactor:
    """The shared hook (21.2, 21.4), called once for products (`product_team`) and once in
    rivals' quality target: the quality-cap and feature multipliers from the
    company's category lead, plus the first mover's cap and brand points."""
    if not state.research_leads and not state.era_arrivals:
        return IDENTITY
    rnd = balance.rnd
    r_cat = category_lead(state, data, company_id, category)
    cap_mult = 1 + rnd.cap_per_point * min(r_cat, rnd.cap_points) if r_cat > 0 else 1.0
    feature_mult = 1 + rnd.feature_per_point * min(r_cat, rnd.feature_points) if r_cat > 0 else 1.0
    window = any(
        category in e.categories for e in first_mover_eras(state, data, balance, company_id)
    )
    factor = TechFactor(
        cap_mult=cap_mult,
        cap_points=(rnd.first_mover_cap if window else 0.0)
        + era_cap_points(state, data, balance, company_id, category),
        feature_mult=feature_mult,
        brand_points=rnd.first_mover_brand if window else 0.0,
        lead=r_cat,
    )
    return IDENTITY if factor == TechFactor(lead=0.0) else factor


def uses_own_chip(
    state: GameState, data: GameData, balance: Balance, company_id: int, category: str
) -> bool:
    """The company sells a live chip of the type the category's products use (26.2, 26.4)."""
    bom = balance.hardware.bom.get(category)
    if bom is None:
        return False
    return any(
        p.status == "live" and data.category(p.category).chip_type == bom.chip_type
        for p in state.company_products(company_id)
    )


def era_cap_points(
    state: GameState, data: GameData, balance: Balance, company_id: int, category: str
) -> float:
    """Quality-cap points from running era boosts for everyone (M12b, 26.4: Custom silicon's
    +5 for devices with their own SoC)."""
    total = 0.0
    for era in data.eras.eras:
        a = state.era_arrival(era.key)
        if a is None:
            continue
        for b in era.boosts:
            if (
                b.cap_points
                and b.category == category
                and a.turn <= state.turn < a.turn + b.months
                and (not b.own_chip or uses_own_chip(state, data, balance, company_id, category))
            ):
                total += b.cap_points
    return total


def yield_cap(state: GameState, data: GameData, base_cap: float) -> float:
    """Chips' yield cap: chips.chip_yield.cap, raised by arrived eras' yield_cap (26.4)."""
    cap = base_cap
    for era in data.eras.eras:
        if era.yield_cap is not None and state.era_arrival(era.key) is not None:
            cap = max(cap, era.yield_cap)
    return cap
