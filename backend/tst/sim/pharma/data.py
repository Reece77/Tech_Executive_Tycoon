"""Lookups and pure formulas over pharma.yaml (docs/formulas.md 55): markets and patients by
indication and region, prices, the game's scale, regulators and exclusivity dates.

Money: pharma.yaml is real US dollars; `cents()` converts to game cents with `pharma.scale`
(M42 decision 2: patients sold to and money spent are both at the game's economy, so a trial's
cost and a drug's revenue stand in their real proportion)."""

from __future__ import annotations

import itertools
import math
from typing import Final

from tst.sim import dmath
from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.pharma.config import (
    STAGES,
    AreaDef,
    IndicationDef,
    ModalityDef,
    PharmaFile,
    ReviewDef,
)
from tst.sim.pharma.models import Programme
from tst.sim.regulation import data as rdata
from tst.sim.regulation.config import DrugRegulatorDef
from tst.sim.state import GameState

MONTHS: Final = 12  # tunable-exempt: calendar
CENTS: Final = 100  # tunable-exempt: cents a dollar
BILLION: Final = 1e9  # tunable-exempt: units
RELY: Final = "rely:"  # tunable-exempt: a reliance authority's prefix
US_REGION: Final = "north_america"  # tunable-exempt: where the US rules apply (its part)
EU_REGION: Final = "europe"  # tunable-exempt: where the EU rules apply (its part)
SELLING: Final = ("marketed",)
NAME_MAX: Final = 80  # tunable-exempt: name column width
ENGAGE_STAGE: Final = 3  # tunable-exempt: the unlock's company stage (M29's growth stage)
STOPS: Final = ("import_ban", "consent_decree")  # findings that stop sales (50.5)


def enabled(data: GameData) -> bool:
    return data.pharma is not None


def file(data: GameData) -> PharmaFile:
    if data.pharma is None:
        raise ValueError("pharma.yaml is not loaded")
    return data.pharma


def year_of(turn: int) -> int:
    return turn_to_ym(turn)[0]


def history_end_turn(data: GameData) -> int:
    return month_to_turn(file(data).history_end)


def area(data: GameData, key: str) -> AreaDef:
    return file(data).area(key)


def indication(data: GameData, key: str) -> IndicationDef:
    return file(data).indication(key)


def modality(data: GameData, key: str) -> ModalityDef:
    return file(data).modality(key)


def stage_index(stage: str) -> int:
    return STAGES.index(stage)


def next_stage(stage: str) -> str:
    return STAGES[STAGES.index(stage) + 1]


def cents(real_usd: float, balance: Balance) -> int:
    """Real US dollars as game cents (pharma.scale)."""
    return round(real_usd * CENTS * balance.pharma.scale)


def scaled(real: float, balance: Balance) -> float:
    return real * balance.pharma.scale


def engaged(state: GameState, data: GameData) -> bool:
    """The player's group has come to pharmaceuticals (55): a programme, a deal or a plant of a
    player company, or the Pharma unlock's condition (an AI or medical product at stage 3)."""
    players = {c.id for c in state.companies if c.is_player}
    if any(p.company_id in players for p in state.pharma_programmes):
        return True
    if any(d.company_id in players for d in state.pharma_deals):
        return True
    if any(p.company_id in players for p in state.pharma_plants):
        return True
    stage_ok = any(c.stage >= ENGAGE_STAGE for c in state.companies if c.is_player)
    return stage_ok and any(
        p.company_id in players
        and p.status != "retired"
        and (p.category == "ai_models" or data.category(p.category).medical)
        for p in state.products
    )


# --- series ---------------------------------------------------------------------------------


def series_at(points: dict[int, float], t: float, growth_after: float, last_year: int) -> float:
    """A yearly series at a fractional year: linear between its years (each year's value at its
    mid-year), held before the first; after `last_year` it grows `growth_after` a year."""
    mid = 0.5  # tunable-exempt: a year's value sits at its middle
    years = sorted(points)
    if t <= years[0] + mid:
        return points[years[0]]
    end = max(y for y in years if y <= max(last_year, years[0]))
    if t >= end + mid:
        return points[end] * dmath.pow(1 + growth_after, t - end - mid)
    for a, b in itertools.pairwise(years):
        if a + mid <= t <= b + mid:
            w = (t - a - mid) / (b - a)
            return points[a] + (points[b] - points[a]) * w
    return points[years[-1]]


def year_frac(turn: int) -> float:
    y, m = turn_to_ym(turn)
    return y + (m - 1) / MONTHS


def last_data_year(data: GameData) -> int:
    return year_of(history_end_turn(data))


def market_b(data: GameData, ind: IndicationDef, turn: int) -> float:
    """An indication's branded sales a year (real $B, world) this month."""
    return series_at(ind.market_b, year_frac(turn), ind.growth_after, last_data_year(data))


def price_index(data: GameData, region: str) -> float:
    return file(data).pricing.region(region).price_index


def mean_net_price(data: GameData, ind: IndicationDef) -> float:
    """Real USD a patient-year, the world's mean: the US list less the area's gross-to-net,
    x each region's price index, weighed by its patients."""
    a = area(data, ind.area)
    net = ind.price_year * (1 - a.gross_to_net)
    return net * sum(s * price_index(data, r) for r, s in a.region_share.items())


def treated(data: GameData, ind: IndicationDef, region: str, turn: int) -> float:
    """Real patients a year on branded therapy in a region: the market / the mean net price,
    x the area's share of patients there."""
    world = market_b(data, ind, turn) * BILLION / mean_net_price(data, ind)
    return world * area(data, ind.area).region_share.get(region, 0.0)


def net_price(data: GameData, ind: IndicationDef, list_cents: int, region: str) -> float:
    """Real USD a patient-year a drug listed at `list_cents` nets in a region (before the IRA)."""
    a = area(data, ind.area)
    # money-exact: rate: real dollars a patient-year, a unit price
    return list_cents / CENTS * (1 - a.gross_to_net) * price_index(data, region)


# --- regulators -----------------------------------------------------------------------------


def regulators(data: GameData) -> tuple[DrugRegulatorDef, ...]:
    rf = data.regulation
    return rf.drug_regulators if rf is not None else ()


def regulator(data: GameData, key: str) -> DrugRegulatorDef:
    return next(r for r in regulators(data) if r.key == key)


def regulator_index(data: GameData, key: str) -> int:
    return next(i for i, r in enumerate(regulators(data)) if r.key == key)


def review_def(data: GameData, regulator_key: str) -> ReviewDef:
    return next(r for r in file(data).approval.reviews if r.regulator == regulator_key)


def in_region(data: GameData, region: str) -> tuple[DrugRegulatorDef, ...]:
    return tuple(r for r in regulators(data) if r.region == region)


def part_share(data: GameData, reg: DrugRegulatorDef) -> float:
    return rdata.part_share(data, reg)  # M34's helper (platforms.yaml parts)


def reliance_share(data: GameData, region: str) -> float:
    return max(0.0, 1.0 - sum(part_share(data, r) for r in in_region(data, region)))


def authorised(state: GameState, programme_id: int, authority: str, turn: int) -> bool:
    return any(
        a.programme_id == programme_id and a.authority == authority and a.from_turn <= turn
        for a in state.pharma_authorisations
    )


def stopped(state: GameState, company_id: int, regulator: str) -> bool:
    return any(
        i.company_id == company_id
        and i.regulator == regulator
        and i.finding in STOPS
        and state.turn < i.until_turn
        for i in state.pharma_inspections
    )


def held(state: GameState, company_id: int, regulator: str) -> bool:
    """An open warning letter holds the regulator's decisions on the company's filings."""
    return any(
        i.company_id == company_id
        and i.regulator == regulator
        and i.finding == "warning_letter"
        and state.turn < i.until_turn
        for i in state.pharma_inspections
    )


def access(state: GameState, programme_id: int, region: str, data: GameData) -> float:
    """The share of a region's patients a drug may reach: its regulators' parts where approved,
    plus the rest once registered by reliance (M41's rule, 50.2)."""
    turn = state.turn
    company = next((p.company_id for p in state.pharma_programmes if p.id == programme_id), None)
    out = sum(
        part_share(data, r)
        for r in in_region(data, region)
        if authorised(state, programme_id, r.key, turn)
        and (company is None or not stopped(state, company, r.key))
    )
    if authorised(state, programme_id, RELY + region, turn):
        out += reliance_share(data, region)
    return min(1.0, out)


def us_regulator(data: GameData) -> DrugRegulatorDef:
    return next(r for r in regulators(data) if r.region == US_REGION)


def eu_regulator(data: GameData) -> DrugRegulatorDef:
    return next(r for r in regulators(data) if r.region == EU_REGION)


# --- exclusivity (55.3) ---------------------------------------------------------------------


def approval_in(state: GameState, programme_id: int, regulator_key: str) -> int | None:
    return min(
        (
            a.from_turn
            for a in state.pharma_authorisations
            if a.programme_id == programme_id and a.authority == regulator_key
        ),
        default=None,
    )


def first_approval(state: GameState, programme_id: int) -> int | None:
    return min(
        (a.from_turn for a in state.pharma_authorisations if a.programme_id == programme_id),
        default=None,
    )


def loe_turn(state: GameState, p: Programme, region: str, data: GameData) -> int | None:
    """The month a drug's exclusivity ends in a region (55.3), or None before it is approved
    there (or with no patent date). US: the patent's 20 years plus Hatch-Waxman's restoration
    (half the testing months plus the review, at most 5 years and 14 after approval), against
    data exclusivity (5 or 12 years) and orphan exclusivity (7). The EU: 8 + 2 (+ 1 for a
    significant benefit) or orphan 10, against the patent with its SPC (at most 5 years, 15
    after approval). Elsewhere: the patent against a few years' data protection."""
    ex = file(data).exclusivity
    ind = indication(data, p.indication)
    mod = modality(data, p.modality)
    if p.patent_turn is None:
        return None
    patent = p.patent_turn + ex.us.patent_years * MONTHS
    if region == US_REGION:
        approved = approval_in(state, p.id, us_regulator(data).key)
        if approved is None:
            return None
        start = p.ind_turn if p.ind_turn is not None else approved
        filed = p.filed_turn if p.filed_turn is not None else approved
        testing = max(0, filed - start)
        review = max(0, approved - filed)
        pte = min(ex.us.pte_max_years * MONTHS, ex.us.pte_trial_share * testing + review)
        patent_end = min(patent + math.floor(pte), approved + int(ex.us.pte_cap_years * MONTHS))
        patent_end = max(patent_end, patent)
        data_end = approved + mod.us_data_years * MONTHS
        orphan_end = approved + ex.us.orphan_years * MONTHS if ind.orphan else 0
        return max(patent_end, data_end, orphan_end)
    if region == EU_REGION:
        approved = approval_in(state, p.id, eu_regulator(data).key)
        if approved is None:
            return None
        protection = (ex.eu.data_years + ex.eu.market_years) * MONTHS
        spc = min(
            ex.eu.spc_max_years * MONTHS,
            max(0, approved - p.patent_turn - ex.eu.spc_offset_years * MONTHS),
        )
        patent_end = min(patent + math.floor(spc), approved + int(ex.eu.spc_cap_years * MONTHS))
        patent_end = max(patent_end, patent)
        orphan_end = approved + ex.eu.orphan_years * MONTHS if ind.orphan else 0
        return max(patent_end, approved + protection, orphan_end)
    approved = first_approval(state, p.id)
    if approved is None:
        return None
    return max(patent, approved + ex.other.data_years * MONTHS)


def retained(mod: ModalityDef, months_after: float) -> float:
    """The brand's share of its patients `months_after` exclusivity ended (55.4)."""
    if months_after < 0:
        return 1.0
    e = mod.erosion
    return e.floor + (1 - e.floor) * dmath.exp(-months_after / e.months)
