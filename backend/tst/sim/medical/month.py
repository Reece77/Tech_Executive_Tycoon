"""Medical devices' place in the turn (docs/formulas.md 50).

Phase 5, after the markets: consumables and service revenue (recurring.py). Phase 12, after
regulation: review drift each January after 2025, studies, submissions' decisions, coverage and
adoption, quality and surveillance costs, inspections and recalls. A game without medical
designs (no company has entered medical devices) skips all of phase 12's steps and draws
nothing (50.6 target 1)."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import LedgerEntry
from tst.sim.log import LogItem
from tst.sim.medical import coverage, draws, quality, routes, studies
from tst.sim.medical import data as md
from tst.sim.medical.models import Drift
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

JANUARY = 0  # tunable-exempt: month index


def drift_january(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """Seeded rules after 2025: each regulator's review times move by a bounded factor."""
    if state.turn % 12 != JANUARY or state.turn <= md.file(data).history_end_turn:
        return state
    db = balance.medical.drift
    year = md.year_of(state.turn)
    rows = list(state.med_drift)
    for i, reg in enumerate(md.health_regulators(data)):
        prev = next((d.factor for d in rows if d.regulator == reg.key and d.year == year - 1), 1.0)
        g = draws.gen(rng, state.turn, draws.DRIFT, i)
        f = min(db.bounds[1], max(db.bounds[0], prev * (1 + db.sd * float(g.standard_normal()))))
        rows = [d for d in rows if not (d.regulator == reg.key and d.year < year - 1)]
        rows.append(Drift(reg.key, year, f))
    return replace(state, med_drift=tuple(rows))


def medical_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not md.enabled(data) or not state.med_designs:
        return state, [], []
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    state = drift_january(state, rng, balance, data)
    state, e, lg = studies.month(state, rng, balance, data)
    entries += e
    logs += lg
    state, lg = routes.decisions_month(state, rng, balance, data)
    logs += lg
    state, e, lg = coverage.month(state, rng, balance, data)
    entries += e
    logs += lg
    entries += quality.cost_entries(state, balance, data)
    state, e, lg = quality.inspections_month(state, rng, balance, data)
    entries += e
    logs += lg
    state, e, lg = quality.recalls_month(state, rng, balance, data)
    entries += e
    logs += lg
    return state, entries, logs
