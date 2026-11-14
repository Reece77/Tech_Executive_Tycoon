"""Chain companies' December decisions (docs/formulas.md 41.2), and their executive moves.

Each December, companies in order of cost (lowest first, then stable key) look at each good they
make. The outlook is 41.2's 3-year displayed price outlook (a year of spot, two of the long-run
level) times the balance factor the market would have when a new build arrives (the good's
`build_months` ahead): demand at the data's growth, against the capacity live and building
(announced builds are public) plus this expansion. A company expands when the market would be
tight then without it (that factor at least 1: M28 decision, so producers build for demand
rather than into a balanced market after a price spike), that outlook tops a new unit's full
cost x (1 + `hurdle`), and its net debt is under `max_leverage` x a year's EBITDA (a company
with no EBITDA does not expand). The size is `expand_share` by personality x its capacity of
the good, x a draw in
[0.75, 1.25] (stream world, key (0, *rival_key, good_index)). Capex is paid at the order, from
cash and then debt while the leverage test holds after it; the capacity arrives after the good's
`build_months`. A subsidiary whose rival owner set a `cash` mandate does not expand; `margin`
doubles its hurdle (41.3, 31.4).

A chain company's CEO changes with chance `ceo_change` a year (stream world, key (4, ...)).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import CASH, DEBT, PPE, AccountCode, LedgerEntry, LedgerLine, account_balance
from tst.sim.money import Cents
from tst.sim.rng import RngFactory
from tst.sim.state import GameState
from tst.sim.world import data as wd
from tst.sim.world import draws
from tst.sim.world import formulas as wf
from tst.sim.world import operate as wo
from tst.sim.world import query as wq
from tst.sim.world.models import WorldFacility
from tst.sim.world.news import Item
from tst.sim.world.setup import CHANGE_TAG, ROLES, executive_names

MONTHS: Final = 12  # tunable-exempt: calendar
DECEMBER: Final = 11  # tunable-exempt: the month index of December
SIZE_LO, SIZE_SPAN = 0.75, 0.5  # tunable-exempt: an expansion's size draw, x [0.75, 1.25]


def is_december(turn: int) -> bool:
    return turn % MONTHS == DECEMBER


def _year_ebitda(ebitda: tuple[int, ...]) -> int:
    return sum(ebitda) * MONTHS // len(ebitda) if ebitda else 0


def decide(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, list[LedgerEntry], list[Item]]:
    if not is_december(state.turn):
        return state, [], []
    wb = balance.world
    turn = state.turn
    goods = wd.all_goods(data)
    flows = wo.player_flows(state, balance, data)
    mean = wo.cycle_mean(state)
    planned = {
        g: sum(
            f.capacity
            for f in state.world_facilities
            if f.good == g and f.status in ("live", "building")
        )
        for g in goods
    }
    builds = wd.chain_file(data).build_months
    future = {g: wo.baseline(state, g, turn + builds[g], balance, data) * mean for g in goods}
    mandates = {m.company_id: m.kind for m in state.rival_mandates}
    facilities = list(state.world_facilities)
    next_id = max((f.id for f in facilities), default=0) + 1
    entries: list[LedgerEntry] = []
    news: list[Item] = []

    def own(cid: int) -> list[WorldFacility]:
        return [f for f in facilities if f.company_id == cid]

    order = sorted(
        (r for r in state.chain_companies if state.company(r.company_id).alive),
        key=lambda r: (min((f.cost for f in own(r.company_id)), default=1.0), r.index),
    )
    for rec in order:
        cid = rec.company_id
        company = state.company(cid)
        kind = mandates.get(cid)
        if kind == "cash":
            continue
        hurdle = wb.hurdle * (2 if kind == "margin" else 1)
        cash = account_balance(balances, cid, CASH)
        debt = -account_balance(balances, cid, DEBT)
        ebitda = _year_ebitda(rec.ebitda)
        if ebitda <= 0 or (debt - cash) >= wb.max_leverage * ebitda:
            continue
        mine = own(cid)
        running = [f for f in mine if f.status in ("live", "building")]
        for g in sorted({f.good for f in running}, key=goods.index):
            have = sum(f.capacity for f in running if f.good == g)
            if have <= 0:
                continue
            gen = draws.gen(rng, turn, draws.CAPEX, *company.rival_key, goods.index(g))
            u = float(gen.random())
            size = wb.expand_share[company.personality or "fast_follower"] * have
            size *= SIZE_LO + SIZE_SPAN * u
            # rivals plan on the world's demand against chain capacity: the player's output
            # reaches them through prices and mothballing, not their plans (41.2)
            demand = future[g] + flows[g][1]
            if wf.balance_factor(demand, wf.normal_supply(planned[g], 0.0, wb), wb) < 1:
                continue  # the market will not need it
            supply = wf.normal_supply(planned[g] + size, 0.0, wb)
            factor = wf.balance_factor(demand, supply, wb)
            wg = wq.world_good(state, g)
            lr = wq.long_run_usd(state, g, balance, data)
            seen = wf.outlook(wg.prices if wg else (), lr, wb) * factor
            cost_pos = min(f.cost for f in mine if f.good == g)
            sample = replace(mine[0], good=g, cost=cost_pos)
            full = wf.unit_full_cost(lr, wq.cash_cost_usd(state, sample, balance, data), wb)
            if seen <= full * (1 + hurdle):
                continue
            capex = round(size * lr * wb.capex_years * wq.CENTS)
            borrow = max(0, capex - cash)
            if borrow and (debt + borrow - (cash + borrow - capex)) > wb.max_leverage * ebitda:
                continue
            if borrow:
                entries.append(
                    LedgerEntry(
                        turn,
                        cid,
                        f"{company.name}: borrows for an expansion (41.2)",
                        (LedgerLine(CASH, borrow), LedgerLine(DEBT, -borrow)),
                    )
                )
                debt += borrow
                cash += borrow
            entries.append(
                LedgerEntry(
                    turn,
                    cid,
                    f"{company.name}: expansion capex (41.2)",
                    (LedgerLine(PPE, capex), LedgerLine(CASH, -capex)),
                )
            )
            cash -= capex
            site = next(f for f in mine if f.good == g)
            ready = turn + wd.chain_file(data).build_months[g]
            facilities.append(
                WorldFacility(
                    id=next_id,
                    company_id=cid,
                    good=g,
                    country=site.country,
                    region=site.region,
                    capacity=size,
                    cost=cost_pos,
                    status="building",
                    ordered_turn=turn,
                    ready_turn=ready,
                    capex_cents=capex,
                )
            )
            next_id += 1
            planned[g] += size
            news.append(
                Item(
                    "capacity",
                    f"{company.name} will add {size:,.0f} {_unit(data, g)} a year of "
                    f"{wd.label(data, g)} capacity, ready in {_month(ready)}",
                    cid,
                    region=site.region,
                    good=g,
                )
            )
    state = replace(state, world_facilities=tuple(facilities))
    state, moved = _ceo_changes(state, rng, balance, data)
    return state, entries, news + moved


def _unit(data: GameData, good: str) -> str:
    if data.commodities is None or good not in {g.key for g in data.commodities.goods}:
        return "wafers"
    return data.commodities.good(good).volume_unit


def _month(turn: int) -> str:
    from tst.sim.calendar import format_turn

    return format_turn(turn)


def _ceo_changes(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[Item]]:
    wb = balance.world
    out = []
    news = []
    for rec in state.chain_companies:
        company = state.company(rec.company_id)
        if not company.alive or rec.is_other:
            out.append(rec)
            continue
        gen = draws.gen(rng, state.turn, draws.PEOPLE, *company.rival_key, CHANGE_TAG)
        if float(gen.random()) >= wb.ceo_change:
            out.append(rec)
            continue
        (_, name), *_ = executive_names(rng, state.turn, rec.index, rec.region, 1, data)
        old = rec.executives[0][1] if rec.executives else "its CEO"
        executives = ((ROLES[0], name), *rec.executives[1:])
        out.append(replace(rec, executives=executives, ceo_since=state.turn))
        news.append(
            Item("executive", f"{company.name}: {name} succeeds {old} as CEO", rec.company_id)
        )
    return replace(state, chain_companies=tuple(out)), news
