"""Chain companies come into being (docs/formulas.md 41.1): in the world's first month
(`world.start`, January 2026, or a later save's next month) each chain company of the data
becomes a rival company with facilities at its December 2025 capacity, named executives and
opening books; each good gets its world month and each region its cycle.

Opening books (one entry a company): cash `open_cash_months` of revenue, plant at `open_book` of
its replacement capex, debt `open_leverage` x a year's EBITDA at December 2025's prices and
`base_utilisation`, and equity the balance.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.fabs import market
from tst.sim.fabs import nodes as nd
from tst.sim.ledger import CASH, COMMON_EQUITY, DEBT, PPE, LedgerEntry, LedgerLine
from tst.sim.rivals.models import CHAIN_KEY
from tst.sim.rng import RngFactory
from tst.sim.state import CompanyState, GameState
from tst.sim.world import data as wd
from tst.sim.world import draws
from tst.sim.world import formulas as wf
from tst.sim.world import query as wq
from tst.sim.world.config import FOUNDRY_GOOD
from tst.sim.world.models import ChainCompany, ChinaLag, RegionCycle, WorldFacility, WorldGood

ROLES: Final = ("CEO", "CFO", "COO", "CTO")  # tunable-exempt: named executives' titles, in order
CHAIN_STAGE: Final = 3  # tunable-exempt: an established company (never the startup stages)
MONTHS: Final = 12  # tunable-exempt: calendar
NAMES_TAG, CHANGE_TAG = 0, 1  # tunable-exempt: the last key part of stream world (4, ...) draws
CHINA: Final = "china"  # tunable-exempt: countries.yaml key of China (41.5)


def executive_names(
    rng: RngFactory, turn: int, index: int, region: str, n: int, data: GameData
) -> tuple[tuple[str, str], ...]:
    """`n` named executives from the region's name pool (stream world key (4, 7, index, 0))."""
    pool = data.names.get(region) or next(iter(data.names.values()))
    gen = draws.gen(rng, turn, draws.PEOPLE, CHAIN_KEY, index, NAMES_TAG)
    out = []
    for i in range(n):
        u, v = (float(x) for x in gen.random(2))
        first = pool.first[min(len(pool.first) - 1, int(u * len(pool.first)))]
        last = pool.last[min(len(pool.last) - 1, int(v * len(pool.last)))]
        out.append((ROLES[i % len(ROLES)], f"{first} {last}"))
    return tuple(out)


def _capacity(data: GameData, spec: wd.ChainSpec, good: str, turn: int) -> float:
    return wd.capacities(data, good, turn).get(spec.key, 0.0)


def _tranches(spec: wd.ChainSpec, capacity: float, balance: Balance) -> list[tuple[float, float]]:
    """An aggregate producer's capacity split along the cost curve (capacity, cost), so its
    dearest producers can mothball first; a named company has one facility a good."""
    if not spec.is_other:
        return [(capacity, spec.cost)]
    n, spread = balance.world.other_tranches, balance.world.other_spread
    out = []
    for i in range(n):
        offset = -spread + 2 * spread * i / (n - 1) if n > 1 else 0.0
        out.append((capacity / n, wf.clamp(spec.cost + offset, 0.0, 1.0)))
    return out


def materialise(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry]]:
    """The world's first month: every chain company, facility, good and region record."""
    wb = balance.world
    turn = state.turn
    if state.chain_companies or turn < wb.start_turn or not wd.has_world(data):
        return state, []
    last = min(turn - 1, nd.HISTORY_END)
    next_id = max(c.id for c in state.companies) + 1
    facility_id = max((f.id for f in state.world_facilities), default=0) + 1
    companies = list(state.companies)
    records: list[ChainCompany] = []
    facilities: list[WorldFacility] = []
    entries: list[LedgerEntry] = []
    prices = {g: wq.price_usd(state, g, balance, data) for g in wd.all_goods(data)}
    for spec in wd.specs(data):
        goods = [g for g in spec.goods if _capacity(data, spec, g, last) > 0]
        if not goods:
            continue
        cid = next_id
        next_id += 1
        companies.append(
            CompanyState(
                id=cid,
                name=spec.name,
                is_player=False,
                stage=CHAIN_STAGE,
                founded_turn=turn,
                stage_history=((CHAIN_STAGE, turn),),
                personality=spec.personality,
                rival_key=(CHAIN_KEY, spec.index),
            )
        )
        revenue = cash_costs = fixed = book = 0.0
        for good in goods:
            lr = wq.long_run_usd(state, good, balance, data)
            for capacity, cost in _tranches(spec, _capacity(data, spec, good, last), balance):
                capex = capacity * lr * wb.capex_years * wq.CENTS
                f = WorldFacility(
                    id=facility_id,
                    company_id=cid,
                    good=good,
                    country=spec.country,
                    region=spec.region,
                    capacity=capacity,
                    cost=cost,
                    status="live",
                    ordered_turn=turn,
                    ready_turn=turn,
                    capex_cents=round(capex * wb.open_book),
                    output=capacity * wb.base_utilisation / MONTHS,
                )
                facility_id += 1
                facilities.append(f)
                made = capacity * wb.base_utilisation
                revenue += made * prices[good]
                cash_costs += made * wq.cash_cost_usd(state, f, balance, data)
                fixed += capacity * lr * wb.fixed_share
                book += f.capex_cents
        ebitda = revenue - cash_costs - fixed
        cash = round(revenue / MONTHS * wb.open_cash_months * wq.CENTS)
        debt = round(max(ebitda, 0.0) * wb.open_leverage * wq.CENTS)
        plant = round(book)
        equity = cash + plant - debt
        entries.append(
            LedgerEntry(
                turn=turn,
                company_id=cid,
                memo=f"{spec.name}: opening books (41.1)",
                lines=(
                    LedgerLine(CASH, cash),
                    LedgerLine(PPE, plant),
                    LedgerLine(DEBT, -debt),
                    LedgerLine(COMMON_EQUITY, -equity),
                ),
            )
        )
        records.append(
            ChainCompany(
                company_id=cid,
                key=spec.key,
                index=spec.index,
                country=spec.country,
                region=spec.region,
                executives=executive_names(rng, turn, spec.index, spec.region, wb.executives, data),
                ceo_since=turn,
                is_other=spec.is_other,
            )
        )
    goods_months = tuple(
        WorldGood(
            good=g,
            turn=last,
            capacity=sum(f.capacity for f in facilities if f.good == g),
            supply=sum(f.capacity for f in facilities if f.good == g) * wb.base_utilisation,
            demand=sum(f.capacity for f in facilities if f.good == g) * wb.base_utilisation,
            output=sum(f.capacity for f in facilities if f.good == g) * wb.base_utilisation,
            player_supply=0.0,
            player_demand=0.0,
            factor=1.0,
            prices=_history_prices(state, g, last, balance, data),
        )
        for g in wd.all_goods(data)
    )
    cycles = tuple(RegionCycle(region=r.key, turn=last) for r in data.regions)
    state = replace(
        state,
        companies=tuple(sorted(companies, key=lambda c: c.id)),
        chain_companies=tuple(records),
        world_facilities=tuple(facilities),
        world_goods=goods_months,
        region_cycles=cycles,
        china_lags=_china_lags(state, records, balance, data),
    )
    return state, entries


def _history_prices(
    state: GameState, good: str, last: int, balance: Balance, data: GameData
) -> tuple[float, ...]:
    """The last 12 months' prices (dollars a unit) for the first outlook."""
    if good == FOUNDRY_GOOD:
        return (wq.long_run_usd(state, good, balance, data),) * MONTHS
    from tst.sim.commodities import commodity

    unit = wq.price_unit(good, balance, data)
    out = []
    for t in range(max(0, last - MONTHS + 1), last + 1):
        try:
            out.append(commodity.price(state, good, t, data, balance) * unit)
        except commodity.FutureMonthError:
            out.append(wq.price_usd(state, good, balance, data))
    return tuple(out)


def _china_lags(
    state: GameState, records: list[ChainCompany], balance: Balance, data: GameData
) -> tuple[ChinaLag, ...]:
    """Chinese foundries' lag at the start (41.5): generations between the leading node and the
    newest the foundry has reached."""
    if data.nodes is None:
        return ()
    tl = market.timeline(state, balance, data)
    foundries = {f.key for f in data.nodes.foundries}
    lead = tl.generation(tl.leading(state.turn - 1))
    out = []
    for r in records:
        if r.key not in foundries or r.country != CHINA:
            continue
        reached = tl.reached(r.key, state.turn - 1)
        best = max((tl.generation(k) for k in reached), default=0)
        out.append(ChinaLag(foundry=r.key, turn=state.turn - 1, behind=float(lead - best)))
    return tuple(out)
