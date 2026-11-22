"""The foundry market and the nodes a company may build (docs/formulas.md 38.1-38.3).

- **Nodes in volume.** A node is in volume from its first foundry's first-volume month
  (`nodes.Timeline`); a future node's month is hidden until then (the API shows its window).
- **Wafer prices.** A node's market price is nodes.yaml's reference price moved by the
  foundry wafer index since its reference month, by `fab.price_decay` for each generation it
  fell further behind the edge, and by the capacity factor (38.3). M12b's own prices (a wafer
  contract without a node) take only the factor, which is exactly 1 through 2025 unless the
  player's fabs sell slots (38.5 target 6).
- **What a company may build.** A node in volume, or due within `fab.preorder_months` (a
  historical node's date is public; a future node's window start stands in), at a process
  level of at least the domain's baseline at the node's first volume (a future node: its
  window's midpoint) plus `fab.node_level`.
- **EUV tools.** A fab at an EUV node needs `ceil(starts / wafers_per_tool)` tools. They arrive
  after the lead time (longer in a shortage of the `euv_tools` good) or, if later, when the
  supplier's open share of its yearly shipments has covered them after the company's earlier
  orders.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.calendar import ym_to_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.fabs import formulas as fx
from tst.sim.fabs import nodes as nd
from tst.sim.fabs.config import NodesFile
from tst.sim.fabs.models import Fab
from tst.sim.facilities import goods
from tst.sim.facilities.config import month_to_turn
from tst.sim.research import levels
from tst.sim.state import GameState

NEVER: Final = nd.NEVER  # a turn no game reaches (re-exported)
HISTORY_END: Final = nd.HISTORY_END
EUV_GOOD: Final = "euv_tools"  # components_history.yaml key (38.2)
MONTHS: Final = 12
MIDDLE: Final = 0.5  # tunable-exempt: a range's middle
THOUSAND: Final = 1000  # tunable-exempt: capacity is in thousand wafer starts a month
TOOL_PRICE_MONTH: Final = "2020-06"  # dossier 3.4: the month nodes.yaml's tool price was read


def nodes_file(data: GameData) -> NodesFile:
    if data.nodes is None:
        raise RuntimeError("nodes.yaml is not loaded")
    return data.nodes


def timeline(state: GameState, balance: Balance, data: GameData) -> nd.Timeline:
    """The seed's node timeline; from 2026 a Chinese foundry's reach after 2025 is the living
    world's (41.5, M28: tst.sim.world.china) instead of its seeded lag, and (M35b) a rival
    foundry's growth waits on its EUV deliveries (`euv_gated`)."""
    return euv_gated(_china(state, balance, data), state, balance, data)


def _china(state: GameState, balance: Balance, data: GameData) -> nd.Timeline:
    base = nd.timeline(state.save_meta.master_seed, nodes_file(data), balance.fab)
    if not state.china_lags:
        return base
    key = (id(base), tuple((x.foundry, x.reached) for x in state.china_lags))
    hit = _OVERLAY.get(key)
    got = hit[1] if hit is not None and hit[0] is base else None
    if got is None:
        if len(_OVERLAY) > _OVERLAY_SIZE:
            _OVERLAY.clear()
        reach = {
            k: t
            for k, t in base.reach.items()
            if not (t > HISTORY_END and any(k[0] == x.foundry for x in state.china_lags))
        }
        for x in state.china_lags:
            for node, turn in x.reached:
                reach[(x.foundry, node)] = turn
        got = replace(base, reach=reach)
        _OVERLAY[key] = (base, got)  # the base kept with it: its id is never reused (M43r)
    return got


_OVERLAY: dict[tuple[object, ...], tuple[nd.Timeline, nd.Timeline]] = {}
_OVERLAY_SIZE: Final = 256  # tunable-exempt: memo entries kept
_GATED: dict[tuple[object, ...], tuple[nd.Timeline, nd.Timeline]] = {}
_RATIOS: dict[
    tuple[object, ...], tuple[nd.Timeline, Balance, GameData, dict[tuple[str, int], float]]
] = {}


def euv_ratios(
    state: GameState, tl: nd.Timeline, balance: Balance, data: GameData
) -> dict[tuple[str, int], float]:
    """(foundry, year) -> the share of its expected EUV tools ASML delivered in `year` (to this
    month in the current year), for each rival foundry at an EUV-only node (one in a queued
    generation's nodes and not in an unqueued one's) from equipment.start (M35b): expected is
    its buyer share x the generation's capacity that year, pro rata to the months played."""
    from tst.sim.equipment import data as ed

    if not ed.enabled(data) or state.turn < balance.equipment.start_turn:
        return {}
    memo = (
        id(tl),
        id(balance),
        id(data),
        state.turn,
        len(state.tool_deliveries),
        state.tool_deliveries[-1] if state.tool_deliveries else None,
        state.supplier_years,
    )
    hit = _RATIOS.get(memo)
    if hit is not None:
        held_tl, held_balance, held_data, kept = hit
        if held_tl is tl and held_balance is balance and held_data is data:
            return kept
    if len(_RATIOS) > _OVERLAY_SIZE:
        _RATIOS.clear()
    out = _ratios(state, tl, balance, data)
    _RATIOS[memo] = (tl, balance, data, out)  # the inputs kept with it (M43r)
    return out


def _ratios(
    state: GameState, tl: nd.Timeline, balance: Balance, data: GameData
) -> dict[tuple[str, int], float]:
    from tst.sim.equipment import data as ed

    ef = ed.equipment_file(data)
    queued = ef.queued()
    duv = {n for g in ef.generations if not g.queued for n in g.nodes}
    euv_only = {n for g in queued for n in g.nodes} - duv
    first = ed.year_of(balance.equipment.start_turn)
    now = ed.year_of(state.turn)
    got: dict[tuple[str, int], int] = {}
    for d in state.tool_deliveries:
        y = ed.year_of(d.turn)
        if d.company_id is None and y >= first and d.turn <= state.turn:
            got[(d.buyer, y)] = got.get((d.buyer, y), 0) + d.tools
    out: dict[tuple[str, int], float] = {}
    for f in nodes_file(data).foundries:
        for y in range(first, now + 1):
            if not any(tl.foundry_has(f.key, n, ed.year_turn(y)) for n in euv_only):
                continue
            months = MONTHS if y < now else state.turn - ed.year_turn(y) + 1
            expected = (
                sum(g.buyers.get(f.key, 0.0) * ed.capacity(state, g, y) for g in queued)
                * months
                / MONTHS
            )
            if expected <= 0:
                continue
            out[(f.key, y)] = min(1.0, got.get((f.key, y), 0) / expected)
    return out


def euv_gated(tl: nd.Timeline, state: GameState, balance: Balance, data: GameData) -> nd.Timeline:
    """`tl` with each gated (foundry, year)'s growth x (1 - s + s x ratio), s
    `equipment.rival_growth.euv_share` (M35b; module docstring of euv_ratios)."""
    ratios = euv_ratios(state, tl, balance, data)
    if not ratios:
        return tl
    key = (id(tl), tuple(sorted(ratios.items())))
    hit = _GATED.get(key)
    out = hit[1] if hit is not None and hit[0] is tl else None
    if out is None:
        if len(_GATED) > _OVERLAY_SIZE:
            _GATED.clear()
        s = balance.equipment.rival_growth.euv_share
        growth = dict(tl.growth)
        for k, r in ratios.items():
            if k in growth:
                growth[k] = growth[k] * (1 - s + s * r)
        out = replace(tl, growth=growth)
        _GATED[key] = (tl, out)  # the timeline kept with it (M43r)
    return out


def player_slots(state: GameState) -> float:
    """Last month's foundry slots the player's fabs sold, thousand starts a month."""
    return sum(f.month.sold for f in state.fabs if f.month is not None) / THOUSAND


def price_factor(state: GameState, balance: Balance, data: GameData) -> float:
    """The foundry market's price factor this month (38.3); 1 without nodes.yaml."""
    if data.nodes is None:
        return 1.0
    tl = timeline(state, balance, data)
    rivals = world_capacity(state, data)
    return nd.price_factor(tl, data.nodes, state.turn, balance.fab, player_slots(state), rivals)


def allocation_factor(state: GameState, balance: Balance, data: GameData) -> float:
    if data.nodes is None:
        return 1.0
    tl = timeline(state, balance, data)
    rivals = world_capacity(state, data)
    return nd.allocation_factor(
        tl, data.nodes, state.turn, balance.fab, player_slots(state), rivals
    )


def world_capacity(state: GameState, data: GameData) -> float | None:
    """The rival foundries' open capacity after 2025 from the living world (41.2, M28): each
    named foundry's live chain capacity (wafers a year as thousand starts a month) x its open
    share. None before the world runs (the seeded growth of 38.3 applies)."""
    if state.turn <= HISTORY_END or not state.world_facilities or data.nodes is None:
        return None
    named = {f.key: f for f in data.nodes.foundries}
    total = 0.0
    for rec in state.chain_companies:
        f = named.get(rec.key)
        if f is None:
            continue
        wafers = sum(
            x.capacity
            for x in state.world_facilities
            if x.company_id == rec.company_id and x.status == "live"
        )
        total += wafers / (THOUSAND * MONTHS) * nd.open_share(f, state.turn)
    return total


def in_volume(state: GameState, node: str, balance: Balance, data: GameData) -> bool:
    return timeline(state, balance, data).arrival[node] <= state.turn


def public_arrival(state: GameState, node: str, balance: Balance, data: GameData) -> int | None:
    """A node's first-volume month if the player may know it: a historical node's always, a
    future node's once it has arrived (ADR-0007)."""
    nf = nodes_file(data)
    tl = timeline(state, balance, data)
    if nf.node(node) is not None or tl.arrival[node] <= state.turn:
        return tl.arrival[node]
    return None


def offered(state: GameState, node: str, balance: Balance, data: GameData) -> bool:
    """M37 (52.2, 52.5 target 1): a dynasty successor node exists for players and the API only
    from January of dynasty.start_year; every other node always."""
    if not nodes_file(data).is_successor(node):
        return True
    return state.turn >= ym_to_turn(balance.dynasty.start_year, 1)


def public_reach(
    state: GameState, foundry: str, node: str, balance: Balance, data: GameData
) -> int | None:
    """When a foundry reached a node, if it has (nothing about the future is shown)."""
    turn = timeline(state, balance, data).reach.get((foundry, node))
    return turn if turn is not None and turn <= state.turn else None


def planning_turn(state: GameState, node: str, balance: Balance, data: GameData) -> int:
    """The month the player plans a node around: its first volume when public, else its
    window's midpoint (never the drawn month, 38.1 and 26.4)."""
    known = public_arrival(state, node, balance, data)
    if known is not None:
        return known
    fut = nodes_file(data).future_node(node)
    assert fut is not None
    return fut.start_turn + fut.months // 2


def planning_economics(
    state: GameState, node: str, balance: Balance, data: GameData
) -> tuple[float, float]:
    """(capital per wafer-per-year, wafer price), cents, the player may plan a node around
    (ADR-0007; M23a, Codex review 5 finding 9): a historical or arrived node's own; an unarrived
    future node's the public estimate, the previous node's planning values x the middle of
    fab.future_capital_mult and fab.future_wafer_mult, never its seeded draws."""
    nf = nodes_file(data)
    tl = timeline(state, balance, data)
    if public_arrival(state, node, balance, data) is not None:
        return tl.capital_cents[node], tl.wafer_cents[node]
    keys = nf.node_keys()
    capital, wafer = planning_economics(state, keys[keys.index(node) - 1], balance, data)
    fb = balance.fab
    mid_c = (fb.future_capital_mult.lo + fb.future_capital_mult.hi) / 2
    mid_w = (fb.future_wafer_mult.lo + fb.future_wafer_mult.hi) / 2
    if nf.is_successor(node):  # M37 (52.2): a successor's public estimate, dynasty.nodes' middle
        nr = balance.dynasty.nodes
        mid_c, mid_w = nr.capital_mult.at(MIDDLE), nr.wafer_mult.at(MIDDLE)
    return capital * mid_c, wafer * mid_w


def window_start(data: GameData, node: str) -> int | None:
    fut = nodes_file(data).future_node(node)
    return fut.start_turn if fut is not None else None


def need_level(state: GameState, node: str, balance: Balance, data: GameData) -> float:
    """The process level a company needs for a node (38.1): the domain's baseline at the node's
    first volume (a future node: its window's midpoint) + fab.node_level."""
    domain = levels.domain_def(data, balance.refining.domain)
    return (
        levels.accrued(domain, planning_turn(state, node, balance, data)) + balance.fab.node_level
    )


def process_level(state: GameState, company_id: int, balance: Balance, data: GameData) -> float:
    if data.tech is None:
        return 0.0
    return levels.level(state, data, balance, company_id, balance.refining.domain)


def orderable(state: GameState, node: str, balance: Balance, data: GameData) -> bool:
    """A node in volume, or due within fab.preorder_months (38.2)."""
    known = public_arrival(state, node, balance, data)
    start = known if known is not None else window_start(data, node)
    return start is not None and start - balance.fab.preorder_months <= state.turn


def age_months(state: GameState, node: str, balance: Balance, data: GameData) -> int:
    """Months since the node's first volume (negative before it: planning month)."""
    return state.turn - planning_turn(state, node, balance, data)


def uses_euv(data: GameData, node: str, duv: bool) -> bool:
    """5 nm and below need EUV; 7 nm by its EUV route unless built by DUV (38.1)."""
    nf = nodes_file(data)
    n = nf.node(node)
    if n is None:
        return True  # future nodes
    if n.duv_route:
        return not duv
    return n.euv


# --- Prices (38.1, 38.3) ---------------------------------------------------------------------


def _index_at(data: GameData, turn: int) -> float:
    """The foundry wafer index in a past month (the history's; after it, December 2025's)."""
    assert data.components is not None
    h = data.components.good("foundry_wafer")
    return h.index_at(max(0, min(turn, h.last_turn)))


def node_price_cents(state: GameState, node: str, balance: Balance, data: GameData) -> float:
    """A node's market wafer price this month (38.1)."""
    tl = timeline(state, balance, data)
    ref = tl.price_turn[node]
    index_now = goods.index_now(state, balance.chips.good, data)
    return fx.node_price_cents(
        tl.wafer_cents[node],
        index_now,
        _index_at(data, ref),
        tl.behind(node, state.turn),
        tl.behind(node, ref),
        balance.fab.price_decay,
        price_factor(state, balance, data),
    )


def slot_price_cents(state: GameState, node: str, balance: Balance, data: GameData) -> float:
    # money-exact: rate
    return node_price_cents(state, node, balance, data) * balance.fab.slot.discount


def median_node(state: GameState, balance: Balance, data: GameData) -> str:
    """A chip category's median node this month (38.4)."""
    return timeline(state, balance, data).median(state.turn, balance.fab.median_lag_months)


def node_points(state: GameState, node: str | None, balance: Balance, data: GameData) -> float:
    """Quality cap points for a chip on `node` (38.4); 0 without one."""
    if node is None or data.nodes is None:
        return 0.0
    tl = timeline(state, balance, data)
    return fx.node_quality_points(
        tl.generation(node),
        tl.generation(median_node(state, balance, data)),
        balance.fab.node_quality,
    )


# --- EUV tools (38.2) ------------------------------------------------------------------------


def euv_rate(state: GameState, turn: int, balance: Balance, data: GameData) -> float:
    """Tools a month open to a new customer in `turn`."""
    year = nd.FIRST_YEAR + turn // MONTHS
    return nd.euv_shipments(nodes_file(data), year) / MONTHS * balance.fab.euv.open_share


def tools_turn(
    state: GameState, company_id: int, tools: int, balance: Balance, data: GameData
) -> int:
    """When `tools` EUV tools ordered this month arrive: the lead time (longer in a shortage),
    or when the supplier's open share has delivered them after the company's earlier orders
    still waiting, if later (38.2)."""
    eb = balance.fab.euv
    month = goods.current(state, EUV_GOOD, data)
    lead = eb.shortage_lead_months if month.allocation < 1 else eb.lead_months
    queued = sum(
        f.tools
        for f in state.fabs
        if f.company_id == company_id and (f.tools_turn or 0) > state.turn
    )
    wanted = queued + tools
    first = max(state.turn, _first_euv(data))
    got, t = 0.0, first
    while got < wanted:
        rate = euv_rate(state, t, balance, data) * min(1.0, month.allocation)
        if rate <= 0 and t >= first + MONTHS:
            return nd.NEVER  # none open to this buyer (M22 may restrict them)
        got += rate
        t += 1
    return max(state.turn + lead, t)


def _first_euv(data: GameData) -> int:
    return month_to_turn(nodes_file(data).euv.first_month)


def tool_price_cents(state: GameState, data: GameData) -> float:
    """One EUV tool this month (dossier 3.4: $120M c.2020, by the euv_tools index)."""
    assert data.components is not None
    h = data.components.good(EUV_GOOD)
    ref = h.index_at(month_to_turn(TOOL_PRICE_MONTH))
    # money-exact: rate
    return nodes_file(data).euv.tool_cents * goods.index_now(state, EUV_GOOD, data) / ref


def fab_of(state: GameState, facility_id: int) -> Fab | None:
    for f in state.fabs:
        if f.facility_id == facility_id:
            return f
    return None
