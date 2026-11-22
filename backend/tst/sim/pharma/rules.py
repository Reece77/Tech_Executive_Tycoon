"""Pricing rules by date (docs/formulas.md 55.4): the Inflation Reduction Act's negotiation.

Each January from the first round's year, a round selects drugs for a negotiated Medicare price
from that January: pharma.yaml's rounds (10 in 2026 at 22% net, 15 in 2027 at 44%, ...), then a
seeded count and discount a year after them (stream pharma (5, year)). History's rival drugs take
their data's places (pharma.yaml `ira_year`); a modelled drug (the player's) is selected when it is
not orphan, its US approval is at least 9 years old (13 for a biologic; 13 for both once the seeded
'pill fix' has happened), and its US sales over the last 12 months are at least
`rules.ira_min_b` (real equivalent): the largest first, up to the round's places left."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.log import LogItem, inbox_item
from tst.sim.pharma import data as pd
from tst.sim.pharma import draws
from tst.sim.pharma.demand import us_revenue_year
from tst.sim.pharma.models import IraPick, Rule
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def pill_fixed(state: GameState, year: int) -> bool:
    return any(r.kind == "pill_fix" and r.year <= year for r in state.pharma_rules)


def window_years(state: GameState, biologic: bool, year: int, data: GameData) -> int:
    ira = pd.file(data).ira
    if biologic or pill_fixed(state, year):
        return ira.biologic_years
    return ira.small_molecule_years


def january(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    turn = state.turn
    ira = pd.file(data).ira
    year = pd.year_of(turn)
    if turn % pd.MONTHS != 0 or year < ira.rounds[0].year:
        return state, []
    rb = balance.pharma.rules
    rnd = next((r for r in ira.rounds if r.year == year), None)
    rules = list(state.pharma_rules)
    if rnd is not None:
        drugs, discount = rnd.drugs, rnd.discount
    else:
        g = draws.gen(rng, turn, draws.RULES, year)
        lo, hi = rb.drugs_after
        drugs = int(lo + g.integers(hi - lo + 1))
        dlo, dhi = rb.discount_after
        discount = dlo + (dhi - dlo) * float(g.random())
        if not pill_fixed(state, year) and float(g.random()) < rb.pill_fix_chance:
            rules.append(Rule(year, "pill_fix"))
    rules.append(Rule(year, "ira_round", drugs, discount))
    state = replace(state, pharma_rules=tuple(rules))
    history = sum(1 for r in pd.file(data).rivals for d in r.drugs if d.ira_year == year)
    places = max(0, drugs - history)
    picked = {i.programme_id for i in state.pharma_ira}
    per_b = pd.BILLION * pd.CENTS * balance.pharma.scale
    candidates = []
    for p in state.pharma_programmes:
        if p.status != "marketed" or p.id in picked:
            continue
        if pd.indication(data, p.indication).orphan:
            continue
        us = pd.approval_in(state, p.id, pd.us_regulator(data).key)
        if us is None:
            continue
        biologic = pd.modality(data, p.modality).biologic
        if turn - us < window_years(state, biologic, year, data) * pd.MONTHS:
            continue
        sales = us_revenue_year(state, p.id)
        # money-exact: ratio: sales in real billions, only compared with a threshold
        if sales / per_b >= rb.ira_min_b:
            candidates.append((-sales, p.id, p))
    logs: list[LogItem] = []
    picks: list[IraPick] = []
    for _, _, p in sorted(candidates)[:places]:
        picks.append(IraPick(year, p.id, p.name, discount))
        logs.append(
            inbox_item(
                turn,
                p.company_id,
                "pharma_ira_selected",
                link_kind="pharma",
                link_id=p.id,
                name=p.name,
                discount_pct=round(discount * pd.CENTS),
            )
        )
    if picks:
        state = replace(state, pharma_ira=(*state.pharma_ira, *picks))
    return state, logs
