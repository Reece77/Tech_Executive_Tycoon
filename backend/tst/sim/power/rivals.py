"""Rivals' power (docs/formulas.md 46.7), each December from `power.start`, after M28's capacity
decisions. Power producers are M28 chain companies of the regions' power goods (tst.sim.world.data;
their capacity rule is 41.2's on the power price). Rival foundries (chain companies with foundry
capacity) power their fabs:

- **PPAs:** each keeps `rivals.ppa_share` (by personality) of its load (its foundry capacity x
  `rivals.mwh_per_wafer`) under PPAs with its region's largest producer, as M28 offtakes of the
  region's power good for `rivals.ppa_years`.
- **Plants:** with chance `rivals.plant_rate` (by personality; stream power (4, chain index)) it
  orders a plant of its own: a world facility of the power good of `rivals.plant_share` x its
  load a year, low on the cost curve, ready after power.yaml `build_months`, its capex paid at
  the order as M28's expansions are.

Rival hyperscalers are static incumbents without facilities (ADR-0017), so they have no load to
contract (M32 decision; a follow-up).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Final

from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.ledger import CASH, PPE, AccountCode, LedgerEntry, LedgerLine, account_balance
from tst.sim.money import Cents
from tst.sim.power import draws
from tst.sim.rng import RngFactory
from tst.sim.state import GameState
from tst.sim.world import data as wd
from tst.sim.world import query as wq
from tst.sim.world.config import FOUNDRY_GOOD
from tst.sim.world.models import WorldFacility, WorldOfftake
from tst.sim.world.news import Item

RIVAL_FAMILY: Final = 4  # tunable-exempt: stream power family (4, chain index)
MONTHS: Final = 12  # tunable-exempt: calendar
DECEMBER: Final = 11  # tunable-exempt: month index
TWH: Final = 1e6  # tunable-exempt: MWh a TWh


def _largest_producer(state: GameState, good: str) -> int | None:
    cap: dict[int, float] = {}
    for f in state.world_facilities:
        if f.good == good and f.status in ("live", "building"):
            cap[f.company_id] = cap.get(f.company_id, 0.0) + f.capacity
    named = [c for c in state.chain_companies if c.company_id in cap]
    if not named:
        return None
    return max(named, key=lambda c: (cap[c.company_id], -c.index)).company_id


def rivals_month(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, list[LedgerEntry], list[Item]]:
    if data.power is None or not state.chain_companies:
        return state, [], []
    if state.turn < month_to_turn(balance.power.start) or state.turn % MONTHS != DECEMBER:
        return state, [], []
    rb = balance.power.rivals
    turn = state.turn
    facilities = list(state.world_facilities)
    offtakes = list(state.world_offtakes)
    next_fac = max((f.id for f in facilities), default=0) + 1
    next_off = max((o.id for o in offtakes), default=0) + 1
    entries: list[LedgerEntry] = []
    news: list[Item] = []
    for rec in state.chain_companies:
        company = state.company(rec.company_id)
        if not company.alive:
            continue
        fabs = [
            f
            for f in facilities
            if f.company_id == rec.company_id and f.good == FOUNDRY_GOOD and f.live(turn)
        ]
        if not fabs:
            continue
        region = fabs[0].region
        good = wd.POWER_PREFIX + region
        load = sum(f.capacity for f in fabs) * rb.mwh_per_wafer
        personality = company.personality or "fast_follower"
        held = sum(
            o.volume
            for o in offtakes
            if o.buyer_id == rec.company_id
            and o.good == good
            and o.start_turn <= turn + 1 <= o.end_turn
        )
        want = rb.ppa_share.get(personality, 0.0) * load - held
        seller = _largest_producer(state, good)
        if want > 0 and seller is not None and seller != rec.company_id:
            offtakes.append(
                WorldOfftake(
                    id=next_off,
                    buyer_id=rec.company_id,
                    seller_id=seller,
                    good=good,
                    volume=want,
                    start_turn=turn + 1,
                    end_turn=turn + rb.ppa_years * MONTHS,
                )
            )
            next_off += 1
            news.append(
                Item(
                    "offtake",
                    f"{company.name} signs a {rb.ppa_years}-year power contract with "
                    f"{state.company(seller).name} for {want / TWH:,.1f} TWh a year",
                    rec.company_id,
                    region=region,
                    good=good,
                )
            )
        u = float(draws.gen(rng, turn, RIVAL_FAMILY, rec.index).random())
        if u >= rb.plant_rate.get(personality, 0.0):
            continue
        size = rb.plant_share * load
        lr = wq.long_run_usd(state, good, balance, data)
        capex = round(size * lr * balance.world.capex_years * wq.CENTS)
        if capex <= 0 or account_balance(balances, rec.company_id, CASH) < capex:
            continue
        entries.append(
            LedgerEntry(
                turn,
                rec.company_id,
                f"{company.name}: power plant capex (46.7)",
                (LedgerLine(PPE, capex), LedgerLine(CASH, -capex)),
            )
        )
        ready = turn + wd.build_months(data, good)
        facilities.append(
            WorldFacility(
                id=next_fac,
                company_id=rec.company_id,
                good=good,
                country=fabs[0].country,
                region=region,
                capacity=size,
                cost=rb.plant_cost,
                status="building",
                ordered_turn=turn,
                ready_turn=ready,
                capex_cents=capex,
            )
        )
        next_fac += 1
        news.append(
            Item(
                "capacity",
                f"{company.name} builds its own power plant for its fabs, ready in "
                f"{format_turn(ready)}",
                rec.company_id,
                region=region,
                good=good,
            )
        )
    state = replace(state, world_facilities=tuple(facilities), world_offtakes=tuple(offtakes))
    return state, entries, news
