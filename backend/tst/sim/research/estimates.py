"""Research numbers as the player can judge them (docs/formulas.md 21.7, ADR-0007).

The engine's research output comes from true skills and tags. What the Research screen
shows is the lab built with `estimate=True` (`projects.lab`): each researcher's research
skill from the midpoints of the ranges the company sees, only the tags it has noticed (as
23.4 does for product teams) and executive seat factors from displayed ranges (18.8). A
rival's lead shows as a range of whole points that always contains the true value, offset
by a seeded draw so its midpoint is not the true lead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from tst.sim.data_models import Balance, GameData
from tst.sim.research import levels
from tst.sim.research.data import EraDef
from tst.sim.research.projects import Lab, progress
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

CENTRE = 0.5  # tunable-exempt: a uniform draw centred on 0


@dataclass(frozen=True, slots=True)
class Outlook:
    gain: float  # estimated lead gained a month, before decay
    net: float  # after this month's decay
    months: int | None  # to the next era threshold at this pace; None if not reached


def outlook(
    state: GameState,
    company_id: int,
    domain: str,
    shown: Lab,
    balance: Balance,
    data: GameData,
) -> Outlook:
    """Estimated monthly progress and months to the domain's next era threshold (21.7),
    simulated month by month with decay, at most 120 months ahead."""
    lead = state.research_lead(company_id, domain)
    gain = progress(shown.funded_output, lead, balance)
    net = gain - (lead + gain) * balance.rnd.decay
    target = next_era(state, data, domain)
    months: int | None = None
    if target is not None and gain > 0:
        need = levels.threshold(data, balance, target)
        base = levels.baseline(state, data, balance, domain)
        r = lead
        for m in range(1, 121):  # tunable-exempt: ten years of look-ahead
            r = (r + progress(shown.funded_output, r, balance)) * (1 - balance.rnd.decay)
            d = levels.domain_def(data, domain)
            grown = levels.accrued(d, state.turn + m) - levels.accrued(d, state.turn)
            if base + grown + r >= need:
                months = m
                break
    return Outlook(gain, net, months)


def next_era(state: GameState, data: GameData, domain: str) -> EraDef | None:
    """The domain's first era that has not arrived, in eras.yaml order; None if none."""
    for era in levels.eras_in(data, domain):
        if state.era_arrival(era.key) is None:
            return era
    return None


def lead_range(
    state: GameState,
    observer_id: int,
    company_id: int,
    domain: str,
    balance: Balance,
    data: GameData,
) -> tuple[int, int]:
    """Another company's lead as whole points (21.7): +-rnd.reveal.range around the true
    value, +-licensed_range once the two have a licence, offset by a seeded draw (stream
    `lead_reveal`, key (observer, company id, domain index), drawn at turn 0) so the midpoint
    is not the true lead. Never below 0."""
    if observer_id == company_id:
        lead = state.research_lead(company_id, domain)
        return math.floor(lead), math.ceil(lead)
    licensed = any(x.involves(observer_id, company_id) for x in state.licenses)
    half = balance.rnd.reveal.licensed_range if licensed else balance.rnd.reveal.range
    index = levels.domain_keys(data).index(domain)
    gen = RngFactory(state.save_meta.master_seed).stream(
        0, "lead_reveal", observer_id, company_id, index
    )
    offset = (float(gen.random()) - CENTRE) * half
    lead = state.research_lead(company_id, domain)
    low = max(0, math.floor(lead + offset - half))
    high = max(low + 1, math.ceil(lead + offset + half))
    return low, high
