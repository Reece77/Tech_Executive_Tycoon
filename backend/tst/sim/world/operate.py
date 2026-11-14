"""Chain companies' month (docs/formulas.md 41.1-41.2): simplified operations and books, and
each good's balance factor for the next month's price.

For each good, demand a year is the rest of the world's baseline (December 2025's output grown
at the data's `demand_growth`, times the regions' mean cycle multiplier) plus the player's
purchases; supply is every producer's output at normal running: `base_utilisation` of chain
producers' live capacity plus the player's output sold to the market (M28 decision: so the
price answers a tight or slack market, not only one at the edge of capacity). What chain
producers actually make is the demand left after the player, inside their utilisation band of
live capacity, and every live facility of the good runs at that utilisation. The factor for
next month is `balance_factor(demand, supply)`.

A facility's month: output x this month's price is revenue; output x its cash cost (region's
power, cost position) is cost of goods; fixed costs a month (less when mothballed); straight-line
depreciation. A facility whose cash cost tops spot `mothball_months` in a row mothballs; a
mothballed one restarts after spot tops its cost x (1 + hurdle) `restart_months` in a row, and
closes after `close_months` mothballed. A company's books post as one entry a month, interest
on its debt at the base rate plus the spread; a shortfall of cash is borrowed while net debt
stays under `max_leverage` x a year's EBITDA, else counts toward failure after
`insolvent_months`. Cash above `repay_cash_months` of costs repays debt.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.fabs import market
from tst.sim.fabs import nodes as nd
from tst.sim.finance import macro
from tst.sim.ledger import (
    ACCUMULATED_DEPRECIATION,
    CASH,
    COGS,
    COMMODITY_REVENUE,
    DEBT,
    DEPRECIATION,
    FOUNDRY_SALES,
    GENERAL_ADMIN,
    INTEREST,
    AccountCode,
    LedgerEntry,
    LedgerLine,
    account_balance,
)
from tst.sim.money import Cents
from tst.sim.state import GameState, with_company
from tst.sim.world import data as wd
from tst.sim.world import formulas as wf
from tst.sim.world import query as wq
from tst.sim.world.config import FOUNDRY_GOOD
from tst.sim.world.models import ChainCompany, WorldFacility, WorldGood
from tst.sim.world.news import Item

MONTHS: Final = 12  # tunable-exempt: calendar
PERCENT: Final = 100.0  # tunable-exempt: the base rate is in % a year
SHORT: Final = 0.7  # tunable-exempt: 41.8 target 3's "supply under 70% of demand"
THOUSAND: Final = 1000  # tunable-exempt: fab slots are thousand starts a month


# --- Demand and the player's flows ---------------------------------------------------------------


def cycle_mean(state: GameState) -> float:
    """The regions' mean demand multiplier this month (41.6); 1 before any cycle."""
    xs = [c.multiplier for c in state.region_cycles]
    return sum(xs) / len(xs) if xs else 1.0


def baseline(state: GameState, good: str, turn: int, balance: Balance, data: GameData) -> float:
    """The rest of the world's demand a year in `turn`: December 2025's output grown at the
    data's rate."""
    chain = wd.chain_file(data)
    start = wd.world_capacity(data, good, nd.HISTORY_END) * balance.world.base_utilisation
    years = max(0, turn - nd.HISTORY_END) / MONTHS
    return float(start * (1 + chain.demand_growth[good]) ** years)


def player_flows(
    state: GameState, balance: Balance, data: GameData
) -> dict[str, tuple[float, float]]:
    """The player's group's (supply to the market, purchases) a year by good: refineries' and
    mines' output not used inside the group, own fabs' foundry slots; deals' volumes and
    refineries' bought inputs."""
    goods = set(wd.all_goods(data))
    supply: dict[str, float] = {}
    demand: dict[str, float] = {}
    last = state.turn - 1
    for r in state.refineries:
        m = r.month
        recipe = balance.refining.recipes.get(r.recipe)
        if m is None or recipe is None or m.turn < last:
            continue
        if recipe.output_good in goods:
            supply[recipe.output_good] = supply.get(recipe.output_good, 0.0) + max(
                0.0, m.output - m.to_group
            )
        if recipe.input_good in goods:
            bought = m.input_spot + m.input_contract
            demand[recipe.input_good] = demand.get(recipe.input_good, 0.0) + bought
    for mine in state.mines:
        if mine.history and mine.history[-1].turn >= last and mine.commodity in goods:
            supply[mine.commodity] = supply.get(mine.commodity, 0.0) + mine.history[-1].output_t
    slots = market.player_slots(state) * THOUSAND
    if slots:
        supply[FOUNDRY_GOOD] = supply.get(FOUNDRY_GOOD, 0.0) + slots
    out = {g: (supply.get(g, 0.0) * MONTHS, demand.get(g, 0.0) * MONTHS) for g in goods}
    for deal in state.commodity_deals:
        if deal.good in goods and deal.running(state.turn):
            s, d = out[deal.good]
            out[deal.good] = (s, d + deal.volume_year)
    return out


# --- The month -------------------------------------------------------------------------------


def operate(
    state: GameState,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, list[LedgerEntry], list[Item]]:
    wb = balance.world
    turn = state.turn
    news: list[Item] = []
    names = {c.company_id: state.company(c.company_id).name for c in state.chain_companies}
    alive = {c.id for c in state.chain()}

    # Builds finish.
    facilities: list[WorldFacility] = []
    for f in state.world_facilities:
        if f.status == "building" and f.ready_turn <= turn:
            if f.company_id in alive:
                f = replace(f, status="live")
                news.append(
                    Item(
                        "built",
                        f"{names[f.company_id]} brings new {wd.label(data, f.good)} capacity "
                        f"on line in {_country(data, f.country)}",
                        f.company_id,
                        region=f.region,
                        good=f.good,
                    )
                )
            else:
                f = replace(f, status="closed", closed_turn=turn)
        facilities.append(f)

    flows = player_flows(state, balance, data)
    mean = cycle_mean(state)
    prices = {g: wq.price_usd(state, g, balance, data) for g in wd.all_goods(data)}
    contracted = {
        g: sum(o.volume for o in state.world_offtakes if o.good == g and o.end_turn >= turn)
        for g in wd.all_goods(data)
    }
    utilisation: dict[str, float] = {}
    goods_out: list[WorldGood] = []
    for g in wd.all_goods(data):
        live = [f for f in facilities if f.good == g and f.status == "live"]
        capacity = sum(f.capacity for f in live)
        p_supply, p_demand = flows[g]
        demand = baseline(state, g, turn, balance, data) * mean + p_demand
        made = wf.producers_output(demand, p_supply, capacity, wb) if capacity > 0 else 0.0
        utilisation[g] = made / capacity if capacity > 0 else 0.0
        supply = wf.normal_supply(capacity, p_supply, wb)
        prev = wq.world_good(state, g)
        output = made + p_supply
        short = (prev.short_months if prev else 0) + 1 if output < SHORT * demand else 0
        history = (*(prev.prices if prev else ()), prices[g])[-MONTHS:]
        goods_out.append(
            WorldGood(
                good=g,
                turn=turn,
                capacity=capacity,
                supply=supply,
                demand=demand,
                player_supply=p_supply,
                player_demand=p_demand,
                factor=wf.balance_factor(demand, supply, wb),
                prices=history,
                contracted=contracted[g],
                output=output,
                short_months=short,
            )
        )

    # Facilities run, mothball, restart and close.
    revenue: dict[int, float] = {}
    cogs: dict[int, float] = {}
    fixed: dict[int, float] = {}
    depreciation: dict[int, int] = {}
    ran: list[WorldFacility] = []
    for f in facilities:
        if f.status in ("building", "closed") or f.company_id not in alive:
            ran.append(f)
            continue
        lr = wq.long_run_usd(state, f.good, balance, data)
        cash_cost = wq.cash_cost_usd(state, f, balance, data)
        spot = prices[f.good]
        share = 1.0 if f.status == "live" else wb.mothball_fixed
        fixed[f.company_id] = fixed.get(f.company_id, 0.0) + f.capacity * lr * wb.fixed_share * (
            share / MONTHS
        )
        dep = min(
            f.capex_cents - f.depreciated_cents,
            round(f.capex_cents / (wb.life_years * MONTHS)),
        )
        if dep > 0:
            depreciation[f.company_id] = depreciation.get(f.company_id, 0) + dep
            f = replace(f, depreciated_cents=f.depreciated_cents + dep)
        if f.status == "live":
            output = f.capacity * utilisation[f.good] / MONTHS
            revenue[f.company_id] = revenue.get(f.company_id, 0.0) + output * spot
            cogs[f.company_id] = cogs.get(f.company_id, 0.0) + output * cash_cost
            below = f.below_months + 1 if spot < cash_cost else 0
            f = replace(f, output=output, below_months=below)
            if below >= wb.mothball_months:
                f = replace(f, status="mothballed", mothballed_turn=turn, output=0.0)
                f = replace(f, below_months=0, above_months=0)
                news.append(_move("mothball", names[f.company_id], f, data, "mothballs"))
        else:  # mothballed
            above = f.above_months + 1 if spot > cash_cost * (1 + wb.hurdle) else 0
            f = replace(f, above_months=above)
            if above >= wb.restart_months:
                f = replace(f, status="live", mothballed_turn=None, above_months=0)
                news.append(_move("restart", names[f.company_id], f, data, "restarts"))
            elif f.mothballed_turn is not None and turn - f.mothballed_turn >= wb.close_months:
                f = replace(f, status="closed", closed_turn=turn)
                news.append(_move("close", names[f.company_id], f, data, "closes"))
        ran.append(f)

    state = replace(state, world_facilities=tuple(ran), world_goods=tuple(goods_out))
    state, entries, failed = _books(
        state, balance, data, balances, revenue, cogs, fixed, depreciation
    )
    news += failed
    return state, entries, news


def _country(data: GameData, country: str) -> str:
    assert data.countries is not None
    return data.countries.country(country).label


def _move(kind: str, name: str, f: WorldFacility, data: GameData, verb: str) -> Item:
    return Item(
        kind,  # type: ignore[arg-type]
        f"{name} {verb} a {wd.label(data, f.good)} facility in {_country(data, f.country)}",
        f.company_id,
        region=f.region,
        good=f.good,
    )


def _books(
    state: GameState,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
    revenue: Mapping[int, float],
    cogs: Mapping[int, float],
    fixed: Mapping[int, float],
    depreciation: Mapping[int, int],
) -> tuple[GameState, list[LedgerEntry], list[Item]]:
    wb = balance.world
    turn = state.turn
    rate = (macro.base_rate(state, data) / PERCENT + wb.interest_spread) / MONTHS
    entries: list[LedgerEntry] = []
    news: list[Item] = []
    records: list[ChainCompany] = []
    for rec in state.chain_companies:
        company = state.company(rec.company_id)
        if not company.alive:
            records.append(rec)
            continue
        cid = rec.company_id
        foundry = any(f.good == FOUNDRY_GOOD for f in state.world_facilities if f.company_id == cid)
        rev = round(revenue.get(cid, 0.0) * wq.CENTS)
        cost = round(cogs.get(cid, 0.0) * wq.CENTS)
        fix = round(fixed.get(cid, 0.0) * wq.CENTS)
        debt = -account_balance(balances, cid, DEBT)
        interest = round(max(0, debt) * rate)
        dep = depreciation.get(cid, 0)
        net = rev - cost - fix - interest
        lines = [
            LedgerLine(CASH, net),
            LedgerLine(FOUNDRY_SALES if foundry else COMMODITY_REVENUE, -rev),
            LedgerLine(COGS, cost),
            LedgerLine(GENERAL_ADMIN, fix),
            LedgerLine(INTEREST, interest),
            LedgerLine(DEPRECIATION, dep),
            LedgerLine(ACCUMULATED_DEPRECIATION, -dep),
        ]
        kept = tuple(x for x in lines if x.amount)
        if len(kept) >= 2:
            entries.append(LedgerEntry(turn, cid, f"{company.name}: the month's operations", kept))
        ebitda = (*rec.ebitda, rev - cost - fix)[-MONTHS:]
        costs = cost + fix + interest
        cash = account_balance(balances, cid, CASH) + net
        year_ebitda = sum(ebitda) * MONTHS // max(1, len(ebitda))
        insolvent = 0
        if cash < 0:
            room = round(wb.max_leverage * max(0, year_ebitda)) - (debt - cash)
            if rec.is_other or room >= 0:
                entries.append(_borrow(turn, cid, company.name, -cash))
            else:
                insolvent = rec.insolvent_months + 1
        elif debt > 0 and cash > wb.repay_cash_months * costs:
            repay = min(debt, cash - round(wb.repay_cash_months * costs))
            if repay > 0:
                entries.append(_borrow(turn, cid, company.name, -repay))
        rec = replace(
            rec,
            revenue_cents=rev,
            costs_cents=costs,
            ebitda=ebitda,
            insolvent_months=insolvent,
        )
        if insolvent >= wb.insolvent_months:
            state = with_company(state, replace(company, failed_turn=turn))
            state = replace(
                state,
                world_facilities=tuple(
                    replace(f, status="closed", closed_turn=turn, output=0.0)
                    if f.company_id == cid and f.status != "closed"
                    else f
                    for f in state.world_facilities
                ),
            )
            news.append(Item("failure", f"{company.name} fails and closes its plants", cid))
        records.append(rec)
    return replace(state, chain_companies=tuple(records)), entries, news


def _borrow(turn: int, cid: int, name: str, amount: int) -> LedgerEntry:
    """Draw (positive) or repay (negative) debt."""
    memo = f"{name}: {'borrows' if amount > 0 else 'repays debt'} (41.1)"
    return LedgerEntry(turn, cid, memo, (LedgerLine(CASH, amount), LedgerLine(DEBT, -amount)))
