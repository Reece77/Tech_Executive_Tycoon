"""Research numbers as the player can judge them (docs/formulas.md 21.7, ADR-0007).

The engine's research output comes from true skills and tags. What the Research screen
shows uses the same lab with each researcher's research skill taken from the midpoints of
the ranges the company sees and only the tags it has noticed (as 23.4 does for product
teams). A rival's lead shows as a range of whole points that always contains the true value,
offset by a seeded draw so its midpoint is not the true lead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from tst.sim.data_models import Balance, GameData
from tst.sim.people.reveal import revealed_range
from tst.sim.products import formulas as pf
from tst.sim.research import levels
from tst.sim.research.data import EraDef
from tst.sim.research.projects import Lab, progress, research_skill
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

CENTRE = 0.5  # tunable-exempt: a uniform draw centred on 0


def _shown_skills(state: GameState, company_id: int, person_id: int) -> dict[str, float] | None:
    person = state.person(person_id)
    reveal = state.reveal(company_id, person_id)
    if person.is_founder or reveal is None:
        return None
    return {k: sum(revealed_range(person, reveal, k)) / 2 for k in person.skills.as_dict()}


def _known_tags(state: GameState, company_id: int, person_id: int) -> tuple[str, ...]:
    person = state.person(person_id)
    reveal = state.reveal(company_id, person_id)
    if person.is_founder or reveal is None:
        return person.tags
    return tuple(tag for tag, _ in reveal.revealed_tags)


def shown_lab(
    state: GameState, company_id: int, lab: Lab, domain: str, balance: Balance, data: GameData
) -> Lab:
    """`lab` with each researcher's output x (shown r x shown t) / (true r x true t)."""
    pb = balance.products
    d = levels.domain_def(data, domain)
    out = []
    for r in lab.researchers:
        person = state.person(r.person_id)
        shown = _shown_skills(state, company_id, r.person_id)
        true = r.skill * pf.tag_multiplier(person.tags, pb)
        seen = (research_skill(shown, d) if shown is not None else r.skill) * pf.tag_multiplier(
            _known_tags(state, company_id, r.person_id), pb
        )
        out.append(
            replace(
                r,
                skill=research_skill(shown, d) if shown is not None else r.skill,
                output=r.output * (seen / true if true else 1.0),
            )
        )
    n = len(out)
    output = pf.coord_factor(n, pb) * sum(r.output for r in out) if n else 0.0
    return replace(lab, researchers=tuple(out), output=output)


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
