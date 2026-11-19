"""Governments and tenders (docs/formulas.md 57.1).

- **Named tenders** (government.yaml `tenders`: JEDI, JWCC, NSSL, SDA, Secure Enclave, Maven) are
  added once, with ids from 1 in the file's order, at their real months and values (the game's
  scale). Without a player bid each is awarded as history.
- **Seeded tenders**: each January, for each government (stream `defence` (0, government index,
  year)): after 2025 the year's budget growth (`budgets.trend` + `budgets.tension` x (T - 50)/50
  + `budgets.noise` x N(0, 1), T the month's geopolitical tension, 39.1), then
  `tenders.per_year[government]` tenders. Each takes an area and a buyer (defence or civil) in
  proportion to the budgets' area shares, a value of the year's openly tendered pool (the area
  budgets x `tendered_share` x the game's scale) over the count, x a mean-one lognormal
  (`value_sigma`), a term (`term_years`), a contract type (`contract_mix`), a clearance level
  (`clearance_mix` by buyer), awardees (an IDIQ's `idiq_awards`), and an announcement month in
  the year; it closes `bid_months` later and is awarded `evaluation_months` after that.

A tender is hidden until its announcement month (57.7)."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Final

import numpy as np

from tst.sim.data_models import Balance, GameData
from tst.sim.geopolitics.tension import tension_at
from tst.sim.government import draws
from tst.sim.government.config import AREAS, CONTRACT_TYPES, LEVELS, GovernmentDef
from tst.sim.government.data import MONTHS, budget_cents, file, january, scale, year_of
from tst.sim.government.models import Tender
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

HALF: Final = 50.0  # tunable-exempt: tension's midpoint (0-100)
AREA_LABELS: Final = {
    "cloud": "cloud services",
    "ai": "AI and analytics",
    "space": "space systems",
    "chips": "trusted microelectronics",
    "devices": "rugged and secure devices",
    "cyber": "cyber defence",
}
CONTRACT_LABELS: Final = {"fixed_price": "fixed price", "cost_plus": "cost-plus", "idiq": "IDIQ"}


def add_history(state: GameState, balance: Balance, data: GameData) -> GameState:
    """The named tenders, once (a save from before M44 gets them at its first month here)."""
    world = state.government_world
    if any(t.key for t in state.tenders):
        return state
    f = file(data)
    m = scale(balance)
    out = []
    next_id = world.next_tender
    for h in f.tenders:
        term = h.term_years * MONTHS
        out.append(
            Tender(
                id=next_id,
                government=h.government,
                area=h.area,
                buyer=h.buyer,
                title=h.title,
                announce_turn=h.announce_turn,
                close_turn=h.close_turn,
                award_turn=h.award_turn,
                value_cents=round(h.value_cents * m),
                term_months=term,
                base_months=max(1, round(term * (1 - balance.government.tenders.option_share))),
                contract=h.contract,
                clearance=h.clearance,
                awards=h.awards,
                key=h.key,
            )
        )
        next_id += 1
    return replace(
        state,
        tenders=(*state.tenders, *out),
        government_world=replace(world, next_tender=next_id),
    )


def _weights(
    state: GameState, gov: GovernmentDef, year: int, balance: Balance, data: GameData
) -> list[tuple[str, str, float]]:
    """(area, buyer, budget cents real) for the year."""
    f = file(data)
    defence = budget_cents(state, gov, year, balance, civil=False)
    civil = budget_cents(state, gov, year, balance, civil=True)
    out = []
    for area in AREAS:
        a = f.areas[area]
        out.append((area, "defence", defence * a.defence_share))
        out.append((area, "civil", civil * a.civil_share))
    return out


def draw_year(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """In January (or the first month a save sees M44): the year's budget growth and tenders,
    for every government in government.yaml's order."""
    year = year_of(state.turn)
    world = state.government_world
    if world.drawn_year is not None and world.drawn_year >= year:
        return state
    gb = balance.government
    f = file(data)
    growth = list(world.growth)
    tenders: list[Tender] = []
    next_id = world.next_tender
    tension = tension_at(state, data)
    for i, gov in enumerate(f.governments):
        g = draws.gen(rng, january(year), draws.BUDGET, i, year)
        if january(year) >= gb.start_turn:
            b = gb.budgets
            rate = b.trend + b.tension * (tension - HALF) / HALF + b.noise * float(g.normal())
            growth.append((gov.key, year, rate))
            state = replace(state, government_world=replace(world, growth=tuple(growth)))
        made, next_id = _tenders_for(state, gov, year, g, next_id, balance, data)
        tenders += made
    world = replace(
        state.government_world,
        growth=tuple(growth),
        drawn_year=year,
        next_tender=next_id,
    )
    return replace(state, tenders=(*state.tenders, *tenders), government_world=world)


def _pick(g: np.random.Generator, shares: dict[str, float], keys: tuple[str, ...]) -> str:
    total = sum(shares.get(k, 0.0) for k in keys)
    u = float(g.random()) * total
    acc = 0.0
    for k in keys:
        acc += shares.get(k, 0.0)
        if u < acc:
            return k
    return keys[-1]


def _tenders_for(
    state: GameState,
    gov: GovernmentDef,
    year: int,
    g: np.random.Generator,
    next_id: int,
    balance: Balance,
    data: GameData,
) -> tuple[list[Tender], int]:
    tb = balance.government.tenders
    n = tb.per_year.get(gov.key, 0)
    weights = _weights(state, gov, year, balance, data)
    pool = sum(w for _, _, w in weights)
    if n <= 0 or pool <= 0:
        return [], next_id
    mean = pool * tb.tendered_share * scale(balance) / n
    sigma = tb.value_sigma
    out = []
    jan = january(year)
    for _ in range(n):
        u = float(g.random()) * pool
        acc = 0.0
        area, buyer = weights[-1][0], weights[-1][1]
        for a, b, w in weights:
            acc += w
            if u < acc:
                area, buyer = a, b
                break
        value = mean * math.exp(sigma * float(g.normal()) - sigma * sigma / 2)
        years = int(g.integers(round(tb.term_years.lo), round(tb.term_years.hi) + 1))
        contract = _pick(g, tb.contract_mix, CONTRACT_TYPES)
        level = _pick(g, tb.clearance_mix[buyer], LEVELS)
        lo, hi = round(tb.idiq_awards.lo), round(tb.idiq_awards.hi)
        awards = int(g.integers(lo, hi + 1)) if contract == "idiq" else 1
        month = int(g.integers(0, MONTHS))
        term = years * MONTHS
        announce = jan + month
        close = announce + tb.bid_months
        out.append(
            Tender(
                id=next_id,
                government=gov.key,
                area=area,  # type: ignore[arg-type]
                buyer=buyer,  # type: ignore[arg-type]
                title=f"{gov.label} {AREA_LABELS[area]} ({CONTRACT_LABELS[contract]})",
                announce_turn=announce,
                close_turn=close,
                award_turn=close + tb.evaluation_months,
                value_cents=max(1, round(value)),
                term_months=term,
                base_months=max(1, round(term * (1 - tb.option_share))),
                contract=contract,  # type: ignore[arg-type]
                clearance=level,  # type: ignore[arg-type]
                awards=awards,
            )
        )
        next_id += 1
    return out, next_id


def prune(state: GameState, balance: Balance) -> GameState:
    """Closed tenders leave the state `history_months` after their award (the player's bids and
    contracts keep their own records)."""
    keep_from = state.turn - balance.government.tenders.history_months
    live_bids = {b.tender_id for b in state.gov_bids if b.status == "submitted"}
    kept = tuple(
        t
        for t in state.tenders
        if t.status not in ("awarded", "cancelled")
        or t.award_turn >= keep_from
        or t.key
        or t.id in live_bids
        or (t.protest_until is not None and t.protest_until >= keep_from)
    )
    if len(kept) == len(state.tenders):
        return state
    return replace(state, tenders=kept)
