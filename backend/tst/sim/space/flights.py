"""Customer launches (docs/formulas.md 56.1): the launches a vehicle line sold this month fly.

A sold launch (a unit of the `launch` market, made on the company's launch sites through the
hardware production path) is owed until it flies: the line's `pending` launches add the month's
units, and each whole one flies this month. Each flight can fail (stream space (1, product_id,
flight)); a failure grounds the line (no sales and no flights until `grounded_until`) and costs it
brand. A grounded line's owed launches wait, drawing nothing, until the grounding ends. The
customer's payload is insured by the customer: no money moves on a failure.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.space import draws, launch
from tst.sim.space.constellation import record_flight
from tst.sim.space.data import TINY
from tst.sim.space.models import LaunchRecord
from tst.sim.state import GameState


def customer_flights(
    state: GameState, rng: RngFactory, balance: Balance
) -> tuple[GameState, list[LaunchRecord], list[LogItem], dict[int, float]]:
    """Fly the month's sold launches. Returns the state, the launches, logs and each company's
    launches flown for customers (the pads they took)."""
    turn = state.turn
    flown: list[LaunchRecord] = []
    logs: list[LogItem] = []
    used: dict[int, float] = {}
    for spec in sorted(state.space.launch_specs, key=lambda s: s.product_id):
        product = state.product(spec.product_id)
        if product is None:
            continue
        made = state.production_of(product.id)
        units = made.units if made is not None and made.turn == turn else 0.0
        if units <= 0 and spec.pending < 1 - TINY:
            continue
        if spec.grounded_until is not None and turn < spec.grounded_until:
            # grounded (56.1): the backlog waits for the investigation, untouched (M43r, Codex
            # review 9 finding 7); a grounded line sells nothing, so `units` is zero here
            continue
        used[spec.company_id] = used.get(spec.company_id, 0.0) + units
        pending = spec.pending + units
        n = int(pending + TINY)
        current = replace(spec, pending=pending - n)
        specs = tuple(
            current if s.product_id == spec.product_id else s for s in state.space.launch_specs
        )
        state = replace(state, space=replace(state.space, launch_specs=specs))
        for _ in range(n):
            vehicle = state.product(product.id)
            assert vehicle is not None
            rate = launch.failure_rate(current.flights, vehicle.quality, balance)
            gen = draws.gen(rng, turn, draws.FLIGHT, vehicle.id, current.flights)
            failed = float(gen.random()) < rate
            state, current = record_flight(state, vehicle, current, failed, rng, balance)
            flown.append(
                LaunchRecord(
                    turn=turn,
                    company_id=spec.company_id,
                    product_id=vehicle.id,
                    vehicle=vehicle.name,
                    purpose="customer",
                    constellation_id=None,
                    satellites=0,
                    ok=not failed,
                )
            )
            if failed:
                logs.append(
                    inbox_item(
                        turn,
                        spec.company_id,
                        "space_launch_failed",
                        vehicle=vehicle.name,
                        until=str(current.grounded_until or turn),
                    )
                )
                # the rest of the month's owed launches wait for the investigation
                left = n - sum(1 for r in flown if r.product_id == vehicle.id)
                current = replace(current, pending=current.pending + left)
                specs = tuple(
                    current if s.product_id == spec.product_id else s
                    for s in state.space.launch_specs
                )
                state = replace(state, space=replace(state.space, launch_specs=specs))
                break
    return state, flown, logs, used
