"""Rivals and platforms (docs/formulas.md 44.8), each December from 2026.

- **Rival owners** (every historical platform still running; owners outside the game too)
  move their standard fee by `rivals.fee_step` when their developer share falls below
  `respond_below` x their users (a cut) or rises over `raise_above` x it (a raise), within
  `own_fee_range`. Regulated paths stay as the data and M34 set them. Stream `platforms` key
  (2, platform id): the order of owners does not matter; one uniform keeps a 50% chance of
  holding when the signal is weak (within 10% of a threshold).
- **Rival OEMs** (rivals' in-game device lines) re-choose their platform with chance
  `licence_switch` (key (4, company id)): the player's OS when it is licensed and its
  catalogue index x (Android's licence / its licence) beats Android's index.
- **Rival stores**: in each region where a platform must allow side-loading or other stores,
  at most one opens a year, with chance `store_chance` (key (2, platform id, region index)), at
  the platform's fee less 10 points.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.geopolitics import world
from tst.sim.log import LogItem
from tst.sim.platforms import data as pdata
from tst.sim.platforms import draws
from tst.sim.platforms import formulas as pf
from tst.sim.platforms.models import DeviceRun, RivalStore
from tst.sim.platforms.phase import by_region, leader_catalogue, live_in
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

COIN: Final = 0.5  # tunable-exempt: a weak signal moves the fee half the time
WEAK: Final = 0.1  # tunable-exempt: a signal within 10% of a threshold is weak
STORE_DISCOUNT: Final = 0.10  # tunable-exempt: a rival store's rate under the platform's
STORE_NAMES: Final = (
    "Epic Games Store",
    "AltStore",
    "Aptoide",
    "Setapp",
)  # tunable-exempt: real alternative stores (personal use)


def rivals_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    if not pdata.enabled(data) or pdata.in_history(state.turn, data):
        return state, []
    if state.turn % MONTHS_PER_YEAR != MONTHS_PER_YEAR - 1:
        return state, []
    state = _owners(state, rng, balance, data)
    state = _oems(state, rng, balance, data)
    return _stores(state, rng, balance, data), []


def _owners(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    rb = balance.platforms.rivals
    lo, hi = balance.platforms.own_fee_range
    group = {c.id for c in world.group(state)}
    rows = [r for r in state.platform_regions]
    out = []
    for p in state.platforms:
        if not p.historical or p.owner_id in group or p.ended_turn is not None:
            out.append(p)
            continue
        mine = [r for r in rows if r.platform_id == p.id and r.users > 0]
        users = sum(r.users for r in mine)
        devs = sum(r.dev_share for r in mine)
        if users <= 0:
            out.append(p)
            continue
        ratio = devs / users
        current = (
            p.fee
            if p.fee is not None
            else pdata.schedule(p, mine[0].region, state.turn, balance, data).standard
        )
        move = 0.0
        if ratio < rb.respond_below:
            move = -rb.fee_step
            weak = ratio > rb.respond_below * (1 - WEAK)
        elif ratio > rb.raise_above:
            move = rb.fee_step
            weak = ratio < rb.raise_above * (1 + WEAK)
        else:
            weak = False
        if move and weak and float(draws.gen(rng, state.turn, draws.OWNER, p.id).random()) < COIN:
            move = 0.0
        out.append(replace(p, fee=pf.clamp(current + move, lo, hi)) if move else p)
    return replace(state, platforms=tuple(out))


def _oems(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    pb = balance.platforms
    group = {c.id for c in world.group(state)}
    own = [
        p
        for p in state.platforms
        if not p.historical and p.licence_cents is not None and p.kind == "device"
    ]
    if not own:
        return state
    android = next((p for p in state.platforms if p.key == pdata.ANDROID), None)
    if android is None:
        return state
    rows = by_region(state)

    def index(pid: int) -> float:
        vals = []
        for region in data.region_keys:
            here = rows.get(region, {})
            if pid in here:
                vals.append(pf.catalogue_index(here[pid].catalogue, leader_catalogue(here, state)))
        return sum(vals) / len(vals) if vals else 0.0

    best = max(
        own,
        key=lambda p: index(p.id) * (pb.android_licence_cents + 1) / ((p.licence_cents or 0) + 1),
    )
    score = index(best.id) * (pb.android_licence_cents + 1) / ((best.licence_cents or 0) + 1)
    runs = list(state.device_runs)
    for i, run in enumerate(runs):
        product = state.product(run.product_id)
        if product is None or product.company_id in group or run.platform_id != android.id:
            continue
        if any(p.historical and p.owner_id == product.company_id for p in state.platforms):
            continue  # an owner keeps its own platform
        if score <= index(android.id):
            continue
        if (
            float(draws.gen(rng, state.turn, draws.OEM, product.company_id, product.id).random())
            < pb.rivals.licence_switch
        ):
            runs[i] = DeviceRun(run.product_id, best.id, state.turn, run.platform_id, 1.0)
    return replace(state, device_runs=tuple(runs))


def _stores(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    rb = balance.platforms.rivals
    year = pdata.year_of(state.turn)
    stores = list(state.rival_stores)
    for r_index, region in enumerate(data.region_keys):
        if any(s.region == region and pdata.year_of(s.opened_turn) == year for s in stores):
            continue
        for p in state.platforms:
            if not p.historical or p.side_loading or not live_in(p, region, state.turn):
                continue
            if pdata.allows_side_loading(data, p, region, state.turn) <= 0:
                continue
            if any(s.platform_id == p.id and s.region == region for s in stores):
                continue
            if (
                float(draws.gen(rng, state.turn, draws.OWNER, p.id, r_index).random())
                >= rb.store_chance
            ):
                continue
            fee = pdata.schedule(p, region, state.turn, balance, data).standard
            name = STORE_NAMES[len(stores) % len(STORE_NAMES)]
            stores.append(
                RivalStore(p.id, region, name, max(0.0, fee - STORE_DISCOUNT), state.turn)
            )
            break
    return replace(state, rival_stores=tuple(stores))
