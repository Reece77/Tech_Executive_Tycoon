"""Refineries' month (docs/formulas.md 36.1, 36.2): phase 4 runs every live plant, upstream
first (`refining.order`), and hands its output to the group, contracts or spot; phase 5, after
production, settles what the group's products used (`settle_supply`).

**A plant's month.** Capacity this month is `live capacity / 12 x ramp x reliability x curb`
(reliability as a data centre's, 22.2: no staff, no output), x the effective yield over the
stated one (36.3). Input comes, in order, from the **group** (output of the group's plants made
earlier this month, at the transfer price: the seller's unit cost inside one company, else the
M16 `materials` flow's price, cost by default), from the company's **buy contracts** (100%
allocation if signed before the shortage, else the good's), then **spot** (the good's
allocation). Output is what the input makes, at most capacity. Costs post to `5000_cogs`:
inputs bought outside the company, power at the region's index (33.5), other variable cost and
the fixed cost; depreciation runs on the generic lifecycle. Unit cost adds depreciation and the
plant's staff salaries (paid by payroll) for the Refineries screen and the transfer price.

**Output** goes, in order, to the group's later plants (above), to the group's products (a
wafer plant's wafers to the group's chip products' wafer starts, product id order; commodities
to the group's companies' use last month, company order), to the seller's sell contracts, then
to spot (`4410_materials_sales`). Group supply is an `OwnSupply` lot: wafers lower the chip's
wafer cost (36.2: `chips.wafer_cents`) and keep 100% allocation on the starts they cover;
commodities count as protected volume in the buyer's allocation (33.1). After production a lot
is **taken** up to what the buyer used (commodities: after M17's deals took theirs); the rest
sells at spot. Taking reverses what the buyer paid at sale (the market price for commodities,
the transfer price inside wafers) and, between two companies, moves the transfer price from
buyer (`5900`) to seller (`4300`); consolidation removes both.

A company without refineries never reaches past the first line of either phase.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from fractions import Fraction

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities import lifecycle
from tst.sim.facilities.models import Facility
from tst.sim.group import formulas as gf
from tst.sim.group.assets import inbox_company
from tst.sim.ledger import (
    CASH,
    COGS,
    GENERAL_ADMIN,
    INTERCOMPANY_PURCHASES,
    INTERCOMPANY_SALES,
    MATERIALS_SALES,
    LedgerEntry,
    LedgerLine,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.refining import formulas as rf
from tst.sim.refining import goods as rg
from tst.sim.refining.config import RecipeDef
from tst.sim.refining.models import OwnSupply, PlantMonth, Refinery, RefiningDeal
from tst.sim.state import (
    GameState,
    group_companies,
    listed_id,
    with_refinery,
    with_refining_deal,
)

MONTHS = 12  # tunable-exempt: calendar
PCT = 100  # tunable-exempt: reliability is 0-100
EPS = 1e-9  # tunable-exempt: float tolerance on volumes
FLOW_GOOD = "materials"  # M16's flow good for refined materials and wafers (31.6)


# --- Lookups ---------------------------------------------------------------------------------


def refinery_of(state: GameState, facility_id: int) -> Refinery | None:
    return next((r for r in state.refineries if r.facility_id == facility_id), None)


def recipe_of(ref: Refinery, balance: Balance) -> RecipeDef:
    return balance.refining.recipes[ref.recipe]


def is_refinery_kind(kind: str, balance: Balance) -> bool:
    return kind in balance.refining.kinds


def group_of(state: GameState, company_id: int) -> tuple[int, ...]:
    """The companies that share supply with `company_id`: the player's group (31.1) for its
    members, else the company alone."""
    ids = tuple(c.id for c in group_companies(state, listed_id(state)))
    return ids if company_id in ids else (company_id,)


def transfer_cents(
    state: GameState, seller: int, buyer: int, cost: float, market: float, balance: Balance
) -> float:
    """The price a unit moves at inside the group (31.6): its cost inside one company; else the
    `materials` flow's kind (cost by default)."""
    if seller == buyer:
        return cost
    from tst.sim.group.transfer import flow_of

    flow = flow_of(state, seller, buyer, FLOW_GOOD)
    if flow is None:
        return cost
    return float(
        gf.transfer_price_cents(flow.kind, round(cost), round(market), balance, flow.margin)
    )


def process_level(state: GameState, company_id: int, balance: Balance, data: GameData) -> float:
    """The company's process level (36.3): the domain's baseline plus its lead (21.1)."""
    if data.tech is None:
        return 0.0
    from tst.sim.research import levels

    return levels.level(state, data, balance, company_id, balance.refining.domain)


def effective_yield(state: GameState, ref: Refinery, balance: Balance, data: GameData) -> float:
    r, rb = recipe_of(ref, balance), balance.refining
    level = process_level(state, ref.company_id, balance, data) if r.semi_grade else 0.0
    return rf.effective_yield(r.yield_, r.semi_grade, level, rb.semi_min_level, rb.semi_low_yield)


def host_live(state: GameState, ref: Refinery) -> bool:
    """A by-product line needs its host plant standing (36.1)."""
    if ref.host_id is None:
        return True
    host = state.facility(ref.host_id)
    return host is not None and host.status != "closed"


def month_capacity(
    state: GameState, facility: Facility, ref: Refinery, balance: Balance, data: GameData
) -> float:
    """Output units the plant can make this month with all the input it wants."""
    turn = state.turn
    live = facility.live_capacity(turn)
    if live <= 0 or ref.stopped(turn) or not host_live(state, ref):
        return 0.0
    r = recipe_of(ref, balance)
    ramp = rf.ramp_share(turn, facility.ready_turn, r.ramp_months)
    reliability = lifecycle.staffing(state, facility, balance).reliability / PCT
    curb = ref.curb_run if ref.curbed(turn) else 1.0
    ratio = effective_yield(state, ref, balance, data) / r.yield_
    return live * r.per_capacity_unit / MONTHS * ramp * reliability * curb * ratio


def staff_cents(state: GameState, facility: Facility, balance: Balance) -> int:
    """The plant's staff's salaries this month (paid by payroll; in the unit cost only)."""
    return sum(e.salary_cents for e in lifecycle.staff_of(state, facility, balance)) // MONTHS


def power_index(state: GameState, region: str, data: GameData) -> float:
    from tst.sim.commodities import power

    return power.index(state, region, data)


# --- Ledger helpers --------------------------------------------------------------------------


def _pay(turn: int, company: int, memo: str, account: str, amount: int) -> LedgerEntry:
    return LedgerEntry.transfer(
        turn=turn, company_id=company, memo=memo, debit=account, credit=CASH, amount=amount
    )


def _sale(turn: int, company: int, memo: str, amount: int) -> LedgerEntry:
    return LedgerEntry.transfer(
        turn=turn, company_id=company, memo=memo, debit=CASH, credit=MATERIALS_SALES, amount=amount
    )


def intercompany(turn: int, seller: int, buyer: int, memo: str, amount: int) -> list[LedgerEntry]:
    """The buyer pays the seller the transfer price (31.6)."""
    if amount <= 0 or seller == buyer:
        return []
    return [
        LedgerEntry.transfer(
            turn=turn,
            company_id=buyer,
            memo=memo,
            debit=INTERCOMPANY_PURCHASES,
            credit=CASH,
            amount=amount,
        ),
        LedgerEntry.transfer(
            turn=turn,
            company_id=seller,
            memo=memo,
            debit=CASH,
            credit=INTERCOMPANY_SALES,
            amount=amount,
        ),
    ]


# --- The month (phase 4) ---------------------------------------------------------------------


@dataclass(slots=True)
class _Lot:
    facility_id: int
    seller: int
    volume: float
    unit_cents: float


@dataclass(slots=True)
class _Month:
    """A plant's month while it is being built up (PlantMonth at the end)."""

    pm: PlantMonth
    group_revenue: float = 0.0
    extra: dict[str, float] = field(default_factory=dict)


def protected(deal: RefiningDeal, start: int | None) -> bool:
    """A buy contract signed before the running shortage began keeps 100% (as 22.4)."""
    return start is not None and deal.signed_turn < start


def _take_contracts(
    state: GameState,
    company: int,
    good: str,
    need: float,
    balance: Balance,
    data: GameData,
    entries: list[LedgerEntry],
    name: str,
) -> tuple[GameState, float, float]:
    """Buy contracts' share of `need` (volume, cents). Take-or-pay on what a contract could
    deliver but was not taken."""
    rb = balance.refining
    alloc = rg.allocation(state, good, balance, data)
    start = rg.shortage_start(state, good, balance, data)
    taken_total = cents = 0.0
    for deal in state.refining_deals:
        if deal.company_id != company or deal.side != "buy" or deal.good != good:
            continue
        if not deal.running(state.turn):
            continue
        share = 1.0 if alloc >= 1 or protected(deal, start) else alloc
        deliverable = deal.monthly_volume * share
        take = min(max(0.0, need - taken_total), deliverable)
        charge = round((deliverable - take) * deal.price_cents * rb.deal.take_or_pay)
        if charge > 0:
            entries.append(
                _pay(state.turn, company, f"Take-or-pay: {name} contract", GENERAL_ADMIN, charge)
            )
        taken_total += take
        cents += take * deal.price_cents
        state = with_refining_deal(
            state,
            replace(
                deal,
                taken=deal.taken + take,
                last_taken=take,
                charged_cents=deal.charged_cents + max(0, charge),
            ),
        )
    return state, taken_total, cents


def _take_group(
    pools: dict[tuple[int, str], list[_Lot]],
    months: dict[int, _Month],
    state: GameState,
    root: int,
    good: str,
    buyer: int,
    need: float,
    market: float,
    balance: Balance,
    entries: list[LedgerEntry],
    memo: str,
) -> tuple[float, float]:
    """Take up to `need` from the group's lots of `good` (in order): volume, input cents."""
    got = cents = 0.0
    for lot in pools.get((root, good), []):
        if got >= need - EPS:
            break
        take = min(lot.volume, need - got)
        if take <= EPS:
            continue
        lot.volume -= take
        price = transfer_cents(state, lot.seller, buyer, lot.unit_cents, market, balance)
        got += take
        cents += take * price
        seller_month = months[lot.facility_id]
        seller_month.pm = replace(seller_month.pm, to_group=seller_month.pm.to_group + take)
        if lot.seller != buyer:
            amount = round(take * price)
            seller_month.group_revenue += amount
            entries += intercompany(state.turn, lot.seller, buyer, memo, amount)
    return got, cents


def _run_plant(
    state: GameState,
    facility: Facility,
    ref: Refinery,
    pools: dict[tuple[int, str], list[_Lot]],
    months: dict[int, _Month],
    balance: Balance,
    data: GameData,
    entries: list[LedgerEntry],
    logs: list[LogItem],
) -> GameState:
    rb = balance.refining
    r = recipe_of(ref, balance)
    turn, company = state.turn, ref.company_id
    name = lifecycle.facility_name(facility, balance, data)
    root = group_of(state, company)[0]
    eff = effective_yield(state, ref, balance, data)
    cap = month_capacity(state, facility, ref, balance, data)
    per_in = rf.input_per_output(r.input_per_output, r.yield_, eff)
    market = rg.price_cents(state, r.output_good, balance, data)
    p_index = power_index(state, facility.region, data)
    group_in = contract_in = spot_in = short = 0.0
    group_cents = contract_cents = spot_cents = 0.0
    if r.input_good is None:
        output = cap
    else:
        need = cap * per_in
        in_market = rg.price_cents(state, r.input_good, balance, data)
        group_in, group_cents = _take_group(
            pools,
            months,
            state,
            root,
            r.input_good,
            company,
            need,
            in_market,
            balance,
            entries,
            f"Group supply to {name}",
        )
        state, contract_in, contract_cents = _take_contracts(
            state, company, r.input_good, need - group_in, balance, data, entries, name
        )
        left = max(0.0, need - group_in - contract_in)
        alloc = rg.allocation(state, r.input_good, balance, data)
        mined = min(left, ref.mine_protected)  # the group's mines' volume keeps 100%
        spot_in = mined + (left - mined) * alloc
        short = left - spot_in
        spot_cents = spot_in * in_market
        got = group_in + contract_in + spot_in
        output = min(cap, got / per_in) if per_in > 0 else cap
    live = facility.live_capacity(turn)
    power = round(output * rf.power_cents(r.mwh_per_unit, rb.power_cents_per_mwh, p_index))
    other = round(output * r.other_cents)
    fixed = round(Fraction(live * r.fixed_cents, MONTHS)) if live > 0 else 0
    bought = round(contract_cents + spot_cents)
    for memo, amount in (
        (f"Refinery inputs: {name}", bought),
        (f"Refinery power: {name}", power),
        (f"Refinery operations: {name}", other + fixed),
    ):
        if amount > 0:
            entries.append(_pay(turn, company, memo, COGS, amount))
    depreciation = max(0, facility.depreciated_cents - ref.last_depreciated_cents)
    staff = staff_cents(state, facility, balance)
    input_cents = round(group_cents) + bought
    total = input_cents + power + other + fixed + depreciation + staff
    unit = total / output if output > EPS else 0.0
    if output > EPS:
        pools.setdefault((root, r.output_good), []).append(_Lot(facility.id, company, output, unit))
    if short > EPS and (ref.month is None or ref.month.input_short <= EPS):
        logs.append(
            inbox_item(
                turn,
                company,
                "refinery_input_short",
                link_kind="refinery",
                link_id=facility.id,
                plant=name,
                good=rg.label(r.input_good or r.output_good, balance, data),
            )
        )
    months[facility.id] = _Month(
        PlantMonth(
            turn=turn,
            output=output,
            capacity=cap,
            yield_=eff,
            input_group=group_in,
            input_contract=contract_in,
            input_spot=spot_in,
            input_short=short,
            input_cents=input_cents,
            power_cents=power,
            power_index=p_index,
            other_cents=other,
            fixed_cents=fixed,
            depreciation_cents=depreciation,
            staff_cents=staff,
            market_cents=market,
            unit_cost_cents=unit,
        )
    )
    return with_refinery(state, replace(ref, last_depreciated_cents=facility.depreciated_cents))


def _consumers(
    state: GameState, root: int, good: str, balance: Balance, data: GameData
) -> list[tuple[int, int | None, int | None, float]]:
    """(buyer, product or None, fab or None, volume wanted) for the group's products (36.2,
    33.2) and, M23a, the group's fabs: a wafer plant's wafers are the substrate of a fab's
    starts (last month's run, after the chip products' wafer starts)."""
    from tst.sim.chips import chips
    from tst.sim.commodities import costs

    group = group_of(state, root)
    out: list[tuple[int, int | None, int | None, float]] = []
    if good == balance.refining.wafer.good:
        for cid in group:
            for p in state.company_products(cid):
                if p.status != "live" or not chips.is_chip(p, data):
                    continue
                starts = sum(c.units for c in chips.wafer_contracts(state, p.id))
                if starts > 0:
                    out.append((cid, p.id, None, float(starts)))
    if state.fabs and good == balance.fab.materials.substrate_good:
        for fab in state.fabs:
            m = fab.month
            if fab.company_id in group and m is not None and m.turn == state.turn - 1 and m.run > 0:
                out.append((fab.company_id, None, fab.facility_id, m.run))
    if good == balance.refining.wafer.good or not rg.is_commodity(good, data):
        return out
    for cid in group:
        use = costs.company_use(state, cid, balance, data).get(good, 0.0)
        if use > EPS:
            out.append((cid, None, None, use))
    return out


def _distribute(
    state: GameState,
    pools: dict[tuple[int, str], list[_Lot]],
    months: dict[int, _Month],
    balance: Balance,
    data: GameData,
) -> list[OwnSupply]:
    supply: list[OwnSupply] = []
    for (root, good), lots in sorted(pools.items()):
        market = rg.price_cents(state, good, balance, data)
        for buyer, product, fab_id, want in _consumers(state, root, good, balance, data):
            for lot in lots:
                if want <= EPS:
                    break
                take = min(lot.volume, want)
                if take <= EPS:
                    continue
                lot.volume -= take
                want -= take
                price = transfer_cents(state, lot.seller, buyer, lot.unit_cents, market, balance)
                supply.append(
                    OwnSupply(
                        turn=state.turn,
                        facility_id=lot.facility_id,
                        seller_id=lot.seller,
                        buyer_id=buyer,
                        good=good,
                        volume=take,
                        unit_cents=price,
                        market_cents=market,
                        product_id=product,
                        fab_id=fab_id,
                    )
                )
                m = months[lot.facility_id]
                m.pm = replace(m.pm, to_group=m.pm.to_group + take)
    return supply


def _sell(
    state: GameState,
    pools: dict[tuple[int, str], list[_Lot]],
    months: dict[int, _Month],
    balance: Balance,
    data: GameData,
    entries: list[LedgerEntry],
) -> GameState:
    """What is left of each lot: the seller's sell contracts (id order, each up to its monthly
    volume), then spot."""
    delivered: dict[int, float] = {}
    for (_, good), lots in sorted(pools.items()):
        market = rg.price_cents(state, good, balance, data)
        for lot in lots:
            left = lot.volume
            if left <= EPS:
                continue
            m = months[lot.facility_id]
            revenue = 0.0
            for deal in state.refining_deals:
                if left <= EPS:
                    break
                if deal.company_id != lot.seller or deal.side != "sell" or deal.good != good:
                    continue
                if not deal.running(state.turn):
                    continue
                take = min(left, max(0.0, deal.monthly_volume - delivered.get(deal.id, 0.0)))
                if take <= EPS:
                    continue
                left -= take
                delivered[deal.id] = delivered.get(deal.id, 0.0) + take
                revenue += take * deal.price_cents
                m.pm = replace(m.pm, to_contract=m.pm.to_contract + take)
            if left > EPS:
                revenue += left * market
                m.pm = replace(m.pm, to_spot=m.pm.to_spot + left)
            lot.volume = 0.0
            amount = round(revenue)
            if amount > 0:
                plant = state.facility(lot.facility_id)
                assert plant is not None
                memo = f"Materials sold: {lifecycle.facility_name(plant, balance, data)}"
                entries.append(_sale(state.turn, lot.seller, memo, amount))
                m.pm = replace(m.pm, revenue_cents=m.pm.revenue_cents + amount)
    for deal in state.refining_deals:
        if deal.side == "sell" and deal.running(state.turn):
            took = delivered.get(deal.id, 0.0)
            state = with_refining_deal(
                state, replace(deal, taken=deal.taken + took, last_taken=took)
            )
    return state


def end_deals(state: GameState) -> tuple[GameState, list[LogItem]]:
    """Contracts past their last month end."""
    logs: list[LogItem] = []
    for deal in state.refining_deals:
        if deal.status == "active" and state.turn > deal.end_turn:
            state = with_refining_deal(state, replace(deal, status="ended"))
            logs.append(
                inbox_item(
                    state.turn,
                    inbox_company(state, deal.company_id),
                    "refining_deal_ended",
                    link_kind="refinery",
                    side="buy" if deal.side == "buy" else "sell",
                    good=deal.good,
                    taken=f"{deal.taken:,.1f}",
                )
            )
    return state, logs


def run_plants(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Phase 4 (module docstring), after the facilities' month and the events' draws."""
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    pools: dict[tuple[int, str], list[_Lot]] = {}
    months: dict[int, _Month] = {}
    for key in balance.refining.order:
        for ref in [r for r in state.refineries if r.recipe == key]:
            facility = state.facility(ref.facility_id)
            if facility is None or facility.status == "closed":
                continue
            current = refinery_of(state, ref.facility_id)
            assert current is not None
            state = _run_plant(
                state, facility, current, pools, months, balance, data, entries, logs
            )
    supply = _distribute(state, pools, months, balance, data)
    state = _sell(state, pools, months, balance, data, entries)
    state = replace(state, own_supply=tuple(supply))
    for fid, m in months.items():
        plant = refinery_of(state, fid)
        assert plant is not None
        pm = replace(m.pm, revenue_cents=m.pm.revenue_cents + round(m.group_revenue))
        state = with_refinery(state, replace(plant, month=pm))
    return state, entries, logs


# --- After production (phase 5) --------------------------------------------------------------


def _wafers_used(state: GameState, product_id: int, balance: Balance, data: GameData) -> float:
    from tst.sim.chips import chips

    row = next((r for r in state.production if r.product_id == product_id), None)
    product = state.product(product_id)
    if row is None or product is None:
        return 0.0
    t = chips.type_of(product, data, balance)
    y = chips.chip_yield(state, product.company_id, balance, data)
    return (row.units + row.internal_units) / max(EPS, t.per_wafer * y)


def _starts(state: GameState, product_id: int) -> float:
    from tst.sim.chips import chips

    return float(sum(c.units for c in chips.wafer_contracts(state, product_id)))


def _use_left(state: GameState, buyer: int, balance: Balance, data: GameData) -> dict[str, float]:
    """The buyer's commodity use this month after M17's deals took theirs (33.3)."""
    from tst.sim.commodities import costs

    use = dict(costs.company_use(state, buyer, balance, data))
    for d in state.commodity_deals:
        if d.company_id == buyer and d.running(state.turn) and d.good in use:
            use[d.good] = max(0.0, use[d.good] - d.last_taken)
    return use


def settle_supply(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry]]:
    """Phase 5 after production (module docstring)."""
    lots = [s for s in state.own_supply if s.turn == state.turn]
    if not lots:
        return state, []
    turn = state.turn
    entries: list[LedgerEntry] = []
    uses: dict[int, dict[str, float]] = {}
    wafer_left: dict[int, float] = {}
    fab_left: dict[int, float] = {}  # M23a: fab -> starts run this month not yet supplied
    spot: dict[int, float] = {}  # facility -> cents sold at spot after production
    settled: list[OwnSupply] = []
    for lot in lots:
        if lot.product_id is not None:
            if lot.product_id not in wafer_left:
                starts = _starts(state, lot.product_id)
                own = sum(x.volume for x in lots if x.product_id == lot.product_id)
                share = min(1.0, own / starts) if starts > 0 else 0.0
                wafer_left[lot.product_id] = share * _wafers_used(
                    state, lot.product_id, balance, data
                )
            taken = min(lot.volume, wafer_left[lot.product_id])
            wafer_left[lot.product_id] -= taken
            amount = round(taken * lot.unit_cents)
            if amount > 0:
                memo = "Own wafers in chips"
                if lot.seller_id == lot.buyer_id:  # its cost is already in the plant's month
                    entries.append(
                        LedgerEntry(
                            turn,
                            lot.buyer_id,
                            memo,
                            (LedgerLine(CASH, amount), LedgerLine(COGS, -amount)),
                        )
                    )
                else:
                    entries.append(
                        LedgerEntry(
                            turn,
                            lot.buyer_id,
                            memo,
                            (
                                LedgerLine(INTERCOMPANY_PURCHASES, amount),
                                LedgerLine(COGS, -amount),
                            ),
                        )
                    )
                    entries.append(
                        LedgerEntry(
                            turn,
                            lot.seller_id,
                            memo,
                            (LedgerLine(CASH, amount), LedgerLine(INTERCOMPANY_SALES, -amount)),
                        )
                    )
        elif lot.fab_id is not None:  # M23a: substrate wafers for a group fab's starts
            if lot.fab_id not in fab_left:
                fab = next((f for f in state.fabs if f.facility_id == lot.fab_id), None)
                month = fab.month if fab is not None else None
                fab_left[lot.fab_id] = (
                    month.run if month is not None and month.turn == turn else 0.0
                )
            taken = min(lot.volume, fab_left[lot.fab_id])
            fab_left[lot.fab_id] -= taken
            at_market = round(taken * lot.market_cents)
            if at_market > 0:  # the fab paid the market price for its substrate in its month
                entries.append(
                    LedgerEntry(
                        turn,
                        lot.buyer_id,
                        "Own-group wafers in fab starts",
                        (LedgerLine(CASH, at_market), LedgerLine(COGS, -at_market)),
                    )
                )
            entries += intercompany(
                turn, lot.seller_id, lot.buyer_id, "Own-group wafers", round(taken * lot.unit_cents)
            )
        else:
            if lot.buyer_id not in uses:
                uses[lot.buyer_id] = _use_left(state, lot.buyer_id, balance, data)
            use = uses[lot.buyer_id]
            taken = min(lot.volume, use.get(lot.good, 0.0))
            use[lot.good] = use.get(lot.good, 0.0) - taken
            at_market = round(taken * lot.market_cents)
            if at_market > 0:  # the buyer paid the market price at sale; it came from the group
                entries.append(
                    LedgerEntry(
                        turn,
                        lot.buyer_id,
                        "Own-group materials in products",
                        (LedgerLine(CASH, at_market), LedgerLine(COGS, -at_market)),
                    )
                )
            entries += intercompany(
                turn,
                lot.seller_id,
                lot.buyer_id,
                "Own-group materials",
                round(taken * lot.unit_cents),
            )
        rest = lot.volume - taken
        if rest > EPS:
            spot[lot.facility_id] = spot.get(lot.facility_id, 0.0) + rest * lot.market_cents
        settled.append(replace(lot, taken=taken))
    others = tuple(s for s in state.own_supply if s.turn != turn)
    state = replace(state, own_supply=(*others, *settled))
    for fid, cents in sorted(spot.items()):
        ref = refinery_of(state, fid)
        plant = state.facility(fid)
        if ref is None or plant is None:
            continue
        amount = round(cents)
        if amount > 0:
            entries.append(
                _sale(
                    turn,
                    ref.company_id,
                    f"Materials sold: {lifecycle.facility_name(plant, balance, data)}",
                    amount,
                )
            )
        if ref.month is not None and ref.month.turn == turn:
            back = sum((x.volume - x.taken) for x in settled if x.facility_id == fid)
            pm = replace(
                ref.month,
                to_group=ref.month.to_group - back,
                to_spot=ref.month.to_spot + back,
                revenue_cents=ref.month.revenue_cents + amount,
            )
            state = with_refinery(state, replace(ref, month=pm))
    return state, entries


def record_history(state: GameState, balance: Balance) -> GameState:
    """Each plant's latest month into its history (the API's chart)."""
    keep = balance.refining.history_months
    for ref in state.refineries:
        pm = ref.month
        if pm is None or pm.turn != state.turn:
            continue
        row = (pm.turn, pm.output, pm.unit_cost_cents, pm.market_cents)
        state = with_refinery(state, replace(ref, history=(*ref.history, row)[-keep:]))
    return state


def live_refineries(state: GameState) -> Iterable[tuple[Refinery, Facility]]:
    for ref in state.refineries:
        f = state.facility(ref.facility_id)
        if f is not None and f.status != "closed":
            yield ref, f
