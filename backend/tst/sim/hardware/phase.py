"""Hardware's part of phase 4 (production and capacity; docs/formulas.md 26.2), after M12a's
facility months: each live assembly plant's yield for the month (one normal draw on stream
`manufacturing`, key (facility_id,)), contracts past their last month end, and each player
company's contract-manufacturing product takes its quality and features."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.lifecycle import staffing
from tst.sim.hardware import cm_market
from tst.sim.hardware import formulas as hf
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, player_companies, with_facility, with_production_contract

KEEP_MONTHS = 24  # tunable-exempt: ended contracts the state keeps for the API (as M12a's)


def plant_yields(state: GameState, rng: RngFactory, balance: Balance) -> GameState:
    """yield = (base + share x mean manufacturing skill / 20) x (1 + noise), in bounds (26.2)."""
    y = balance.hardware.plant_yield
    for f in state.facilities:
        if f.kind != balance.hardware.plant_kind or f.live_capacity(state.turn) <= 0:
            continue
        mean = staffing(state, f, balance).mean_skill
        noise = float(rng.stream(state.turn, "manufacturing", f.id).normal(0.0, y.noise_sd))
        value = hf.plant_yield(y.base, y.skill_share, mean) * (1 + noise)
        value = min(y.bounds.hi, max(y.bounds.lo, value))
        state = with_facility(state, replace(f, yield_rate=value))
    return state


def end_contracts(state: GameState, data: GameData) -> tuple[GameState, list[LogItem]]:
    logs: list[LogItem] = []
    kept = []
    for c in state.production_contracts:
        if c.status == "active" and state.turn > c.end_turn:
            c = replace(c, status="ended", delivered=0.0, used=0.0, charged_cents=0)
            product = state.product(c.product_id)
            logs.append(
                inbox_item(
                    state.turn,
                    c.company_id,
                    "production_contract_ended",
                    what="contract-manufacturing" if c.kind == "assembly" else "wafer",
                    product=product.name if product else f"product {c.product_id}",
                    units=f"{c.units:,}",
                )
            )
        if c.status == "active" or state.turn - c.end_turn <= KEEP_MONTHS:
            kept.append(c)
    state = replace(state, production_contracts=())
    for c in kept:
        state = with_production_contract(state, c)
    return state, logs


def hardware_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    state = plant_yields(state, rng, balance)
    state, logs = end_contracts(state, data)
    for company in player_companies(state):
        state = cm_market.refresh_product(state, company.id, balance, data)
    return state, logs
