"""Pharmaceuticals' place in the turn (docs/formulas.md 55).

Phase 5, after the markets (`sales_month`): every marketed drug's patients, revenue, cost of
goods and commercial support; licences' milestones, royalties and partners' shares; every pharma
rival's revenue and costs (history's to 2025). The revenue joins the month's MRR.

Phase 12, with M41's medical step (`events_month`): each January the IRA's round and seeded rules,
rivals' seeded approvals (after 2025) and the assets listed for licence; then every programme's
stage and readout, reviews and HTAs, plants, inspections and recalls.

A game where no company has entered pharmaceuticals draws nothing for the player and leaves its
company exactly as before (55.6 target 1); the rivals' businesses run in every game."""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import LedgerEntry
from tst.sim.log import LogItem
from tst.sim.pharma import approval, demand, licensing, pipeline, rivals, rules, supply
from tst.sim.pharma import data as pd
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def sales_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], dict[int, int]]:
    if not pd.enabled(data):
        return state, [], {}
    state, entries, out = demand.month(state, balance, data)
    revenue = dict(out.revenue)
    if state.pharma_deals:
        state, more, _ = licensing.month(state, state.pharma_months, balance, data)
        entries += more
    more, rival_revenue = rivals.month(state, out.share, out.generic_cents, balance, data)
    entries += more
    for cid, cents in rival_revenue.items():
        revenue[cid] = revenue.get(cid, 0) + cents
    return state, entries, revenue


def events_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not pd.enabled(data):
        return state, [], []
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    state, lg = rules.january(state, rng, balance, data)
    logs += lg
    state = rivals.january(state, rng, balance, data)
    state = licensing.january(state, rng, balance, data)
    if not state.pharma_programmes and not state.pharma_plants:
        return state, entries, logs
    state, e, lg = pipeline.month(state, rng, balance, data)
    entries += e
    logs += lg
    state, e, lg = approval.month(state, rng, balance, data)
    entries += e
    logs += lg
    state, e, lg = supply.month(state, rng, balance, data)
    entries += e
    logs += lg
    return state, entries, logs
