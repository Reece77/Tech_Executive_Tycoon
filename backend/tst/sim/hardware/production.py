"""Making and costing units (docs/formulas.md 26.1-26.3): the capacity cap, the cost of goods
at sale, internal chips, take-or-pay, and selling spare plant capacity.

A `ProductionPlan` is built at the start of phase 5 from the state alone and used only
within that phase. For each player company (`player_companies`; rivals' manufacturing is
abstract) it knows:

- **devices and servers**: the company's live assembly plants (one shared pool of runnable
  capacity, `live x staff coverage`, each run unit making `yield` good units; a server takes
  `plant_slots`) and each product's running contract-manufacturing contracts (`units` a
  month x allocation, 26.2). A sale takes plants first, then contracts by id. Each unit also
  needs a chip of its type: the company's own live chip product's first (internal supply at
  cost, no revenue; ADR-0020 4), else bought at the market price;
- **chips**: each chip product's good chips from its wafer contracts (26.3). Devices are
  sold before chips (categories.yaml order), so own devices take their chips first.

Build to order: units made = units sold. After the markets, `settle` books the month: the
cost of goods per product (bill of materials at the good's index, chips, contract fees and
plants' cost per unit run) to 5000, take-or-pay on contracts' unused volume to 6900, each
contract's and plant's use, and a `ProductionMonth` per product.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from tst.sim.chips import chips
from tst.sim.commodities import costs
from tst.sim.data_models import Balance, GameData
from tst.sim.fabs import plants as fab_plants
from tst.sim.fabs import supply as fab_supply
from tst.sim.facilities.lifecycle import facility_name, staffing
from tst.sim.facilities.models import Facility
from tst.sim.geopolitics import supply as geo_supply
from tst.sim.hardware import formulas as hf
from tst.sim.hardware.models import ProductionContract, ProductionMonth
from tst.sim.hardware.supply import delivered_share
from tst.sim.ledger import CASH, COGS, GENERAL_ADMIN, LedgerEntry, LedgerLine
from tst.sim.money import Cents
from tst.sim.products.models import SELLING, Product
from tst.sim.state import (
    GameState,
    player_companies,
    with_facility,
    with_production_contract,
)

EPS = 1e-9  # tunable-exempt: float tolerance on units


def is_plant(facility: Facility, balance: Balance) -> bool:
    return facility.kind == balance.hardware.plant_kind


def live_plants(state: GameState, company_id: int, balance: Balance) -> list[Facility]:
    return [
        f
        for f in state.company_facilities(company_id)
        if is_plant(f, balance) and f.live_capacity(state.turn) > 0
    ]


def runnable(state: GameState, plant: Facility, balance: Balance) -> float:
    """Units a plant can run this month: live capacity x staff coverage (26.2)."""
    return plant.live_capacity(state.turn) * staffing(state, plant, balance).coverage


def assembly_contracts(state: GameState, product_id: int) -> list[ProductionContract]:
    return [
        c
        for c in state.production_contracts
        if c.product_id == product_id and c.kind == "assembly" and c.running(state.turn)
    ]


def contract_delivered(
    state: GameState, contract: ProductionContract, balance: Balance, data: GameData
) -> float:
    """A contract-manufacturing contract's units this month after allocation of the product's
    bill-of-materials good (26.2)."""
    product = state.product(contract.product_id)
    assert product is not None
    good = balance.hardware.bom[product.category].good
    return contract.units * delivered_share(state, good, contract.signed_turn, data)


def plant_yield_of(plant: Facility, balance: Balance) -> float:
    """This month's yield (phase 4 sets it); the formula's base before a first month."""
    return plant.yield_rate if plant.yield_rate > 0 else balance.hardware.plant_yield.base


def has_source(state: GameState, product: Product, balance: Balance, data: GameData) -> bool:
    """A manufacturing source for launch (26.1): a running contract for the product, or a
    live plant (devices and servers); a running wafer contract (chips)."""
    if chips.is_chip(product, data):  # M21 (38.2): or a live fab of the company
        return bool(chips.wafer_contracts(state, product.id)) or fab_plants.has_live_fab(
            state, product.company_id, balance
        )
    if assembly_contracts(state, product.id):
        return True
    return bool(live_plants(state, product.company_id, balance))


@dataclass
class _Usage:
    plant: float = 0.0  # good units from plants
    contract: float = 0.0
    own_chips: float = 0.0
    internal: float = 0.0  # a chip product: chips its company's devices took
    market: float = 0.0  # a chip product: chips sold to the market
    lost: float = 0.0


@dataclass
class ProductionPlan:
    """Phase 5's capacity, consumed as segments sell (see the module docstring)."""

    capped: set[int] = field(default_factory=set)  # player unit-sale product ids
    plant_left: dict[int, float] = field(default_factory=dict)  # plant id -> run units left
    plant_run: dict[int, float] = field(default_factory=dict)  # plant id -> run for own products
    plant_yield: dict[int, float] = field(default_factory=dict)
    plants_of: dict[int, list[int]] = field(default_factory=dict)  # company -> plant ids
    contract_left: dict[int, float] = field(default_factory=dict)
    contract_used: dict[int, float] = field(default_factory=dict)
    contract_delivered: dict[int, float] = field(default_factory=dict)
    contracts_of: dict[int, list[int]] = field(default_factory=dict)  # product -> contract ids
    chips_left: dict[int, float] = field(default_factory=dict)  # chip product -> chips left
    chips_capacity: dict[int, float] = field(default_factory=dict)
    fab_chips: dict[int, float] = field(default_factory=dict)  # M21: chips its own fabs can make
    usage: dict[int, _Usage] = field(default_factory=dict)
    capacity: dict[int, float] = field(default_factory=dict)  # product -> units at the start
    slots: dict[int, int] = field(default_factory=dict)  # product -> plant slots a unit
    chip_type: dict[int, str] = field(default_factory=dict)  # device product -> its chip type
    company_of: dict[int, int] = field(default_factory=dict)
    own_chip_of: dict[tuple[int, str], int] = field(default_factory=dict)  # (company, type)
    unit_cap: dict[int, float] = field(default_factory=dict)  # M17: units left in a shortage

    def is_capped(self, product_id: int) -> bool:
        return product_id in self.capped

    def available(self, product_id: int) -> float:
        """Units the product can still make this month."""
        if product_id in self.chips_left:
            return self.chips_left[product_id]
        company = self.company_of[product_id]
        slots = self.slots.get(product_id, 1)
        plant = sum(
            self.plant_left[f] * self.plant_yield[f] / slots
            for f in self.plants_of.get(company, [])
        )
        made = plant + sum(self.contract_left[c] for c in self.contracts_of.get(product_id, []))
        if product_id in self.unit_cap:  # M17: a commodity shortage (33.1)
            return min(made, self.unit_cap[product_id])
        return made

    def take(self, product_id: int, units: float) -> float:
        """Make up to `units`: plants first, then contracts by id; a device takes its chips.
        Returns the units made."""
        use = self.usage.setdefault(product_id, _Usage())
        if product_id in self.chips_left:
            got = min(units, self.chips_left[product_id])
            self.chips_left[product_id] -= got
            use.market += got
            return got
        if product_id in self.unit_cap:  # M17: a commodity shortage (33.1)
            units = min(units, self.unit_cap[product_id])
        left = units
        company = self.company_of[product_id]
        slots = self.slots.get(product_id, 1)
        for f in self.plants_of.get(company, []):
            per_run = self.plant_yield[f] / slots  # good units per run unit
            can = self.plant_left[f] * per_run
            got = min(left, can)
            if got > EPS:
                run = got / per_run
                self.plant_left[f] -= run
                self.plant_run[f] = self.plant_run.get(f, 0.0) + run
                use.plant += got
                left -= got
            if left <= EPS:
                break
        for c in self.contracts_of.get(product_id, []):
            got = min(left, self.contract_left[c])
            if got > EPS:
                self.contract_left[c] -= got
                self.contract_used[c] = self.contract_used.get(c, 0.0) + got
                use.contract += got
                left -= got
            if left <= EPS:
                break
        made = units - max(0.0, left)
        if product_id in self.unit_cap:
            self.unit_cap[product_id] = max(0.0, self.unit_cap[product_id] - made)
        self._chips_for(product_id, made)
        return made

    def _chips_for(self, product_id: int, units: float) -> None:
        chip_type = self.chip_type.get(product_id)
        if chip_type is None or units <= 0:
            return
        own = self.own_chip_of.get((self.company_of[product_id], chip_type))
        if own is None:
            return
        got = min(units, self.chips_left.get(own, 0.0))
        if got > 0:
            self.chips_left[own] -= got
            self.usage.setdefault(own, _Usage()).internal += got
            self.usage[product_id].own_chips += got

    def lose(self, product_id: int, units: float) -> None:
        self.usage.setdefault(product_id, _Usage()).lost += units


def _commodity_caps(
    state: GameState, plan: ProductionPlan, balance: Balance, data: GameData
) -> None:
    """M17 (33.1, 33.3): in a commodity shortage a product makes at most its mix's weighted
    allocation of what it could; a chip product's wafer starts fall the same way."""
    uses: dict[int, dict[str, float]] = {}
    for pid in sorted(plan.capped):
        product = state.product(pid)
        assert product is not None
        company = plan.company_of[pid]
        good = (
            balance.chips.good
            if pid in plan.chips_left
            else balance.hardware.bom[product.category].good
        )
        if company not in uses:
            uses[company] = costs.company_use(state, company, balance, data)
        share = costs.product_allocation(state, company, good, uses[company], balance, data)
        if share >= 1:
            continue
        if pid in plan.chips_left:
            plan.chips_left[pid] *= share
            plan.chips_capacity[pid] *= share
            if pid in plan.fab_chips:
                plan.fab_chips[pid] *= share
        else:
            plan.unit_cap[pid] = plan.available(pid) * share


def build_plan(state: GameState, balance: Balance, data: GameData) -> ProductionPlan | None:
    """The month's plan for the player's companies; None when none sells units."""
    plan = ProductionPlan()
    for company in player_companies(state):
        products = [
            p
            for p in state.company_products(company.id)
            if p.status in SELLING and data.category(p.category).sells_units
        ]
        if not products:
            continue
        plants = live_plants(state, company.id, balance)
        plan.plants_of[company.id] = [f.id for f in plants]
        for f in plants:
            plan.plant_left[f.id] = runnable(state, f, balance)
            plan.plant_yield[f.id] = plant_yield_of(f, balance)
        for p in products:
            plan.capped.add(p.id)
            plan.company_of[p.id] = company.id
            category = data.category(p.category)
            if category.chip_type is not None:
                cap = chips.chip_capacity(state, p, balance, data)
                plan.chips_left[p.id] = cap
                plan.chips_capacity[p.id] = cap
                if state.fabs:  # M21 (38.2)
                    plan.fab_chips[p.id] = fab_supply.fab_chips(state, p, balance, data)
                if p.status == "live":
                    plan.own_chip_of.setdefault((company.id, category.chip_type), p.id)
                continue
            bom = balance.hardware.bom[p.category]
            plan.slots[p.id] = bom.plant_slots
            plan.chip_type[p.id] = bom.chip_type
            ids = []
            for c in assembly_contracts(state, p.id):
                delivered = contract_delivered(state, c, balance, data)
                plan.contract_left[c.id] = delivered
                plan.contract_delivered[c.id] = delivered
                ids.append(c.id)
            plan.contracts_of[p.id] = ids
    if not plan.capped:
        return None
    _commodity_caps(state, plan, balance, data)
    for pid in plan.capped:
        plan.capacity[pid] = plan.available(pid)
    return plan


# --- After the markets: the month's books ----------------------------------------------------


def unit_bom_cents(state: GameState, product: Product, balance: Balance, data: GameData) -> float:
    """The BOM at this month's index with its commodities at spot (26.2, 33.2)."""
    bom = balance.hardware.bom[product.category]
    cents = hf.bom_cents(bom.base_cents, costs.cost_index(state, bom.good, data, balance))
    # M22 (39.3): the premium on its commodities bought from a restricting actor
    return cents + geo_supply.surcharge_cents(
        state, product.company_id, bom.good, bom.base_cents, balance, data
    )


def plant_unit_cents(state: GameState, plant: Facility, balance: Balance) -> float:
    """A plant's cost per unit run that posts at sale (26.2): its variable cost."""
    return float(balance.facility.kinds[plant.kind].variable_cents)


def _entry(
    turn: int, company: int, memo: str, amount: Cents, debit: str, d: int | None
) -> LedgerEntry:
    return LedgerEntry(
        turn=turn,
        company_id=company,
        memo=memo,
        lines=(LedgerLine(debit, amount, d), LedgerLine(CASH, -amount, d)),
    )


def settle(
    state: GameState,
    plan: ProductionPlan | None,
    cm_sold: dict[int, float],
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry]]:
    """Book the month's production (module docstring). `cm_sold`: plant id -> units run for
    contract-manufacturing customers (their revenue is the market's)."""
    turn = state.turn
    entries: list[LedgerEntry] = []
    rows: list[ProductionMonth] = []
    fab_used: dict[int, float] = {}  # M21: facility id -> starts run for own chips
    if plan is not None:
        posted = _posted_units(state, plan, fab_used, balance, data)
        for pid in sorted(plan.capped):
            product = state.product(pid)
            assert product is not None
            use = plan.usage.get(pid, _Usage())
            if chips.is_chip(product, data):
                unit = posted[pid]
                chip_cents = round(use.market * unit)
                rows.append(
                    ProductionMonth(
                        turn,
                        pid,
                        product.company_id,
                        capacity=plan.capacity[pid],
                        units=use.market,
                        internal_units=use.internal,
                        chip_cents=chip_cents,
                        lost_units=use.lost,
                    )
                )
                if chip_cents:
                    memo = f"Cost of goods: {product.name} chips"
                    entries.append(
                        _entry(
                            turn, product.company_id, memo, chip_cents, COGS, product.division_id
                        )
                    )
                continue
            units = use.plant + use.contract
            bom = round(units * unit_bom_cents(state, product, balance, data))
            chip_type = plan.chip_type[pid]
            own_id = plan.own_chip_of.get((product.company_id, chip_type))
            own_unit = 0.0
            if own_id is not None:
                own_unit = posted.get(own_id, 0.0)
            bought = units - use.own_chips
            chip = round(
                use.own_chips * own_unit
                + bought * chips.bought_price_cents(data, balance, chip_type)
            )
            fees = sum(
                plan.contract_used.get(c, 0.0) * contract.price_cents
                for c in plan.contracts_of.get(pid, [])
                if (contract := state.production_contract(c)) is not None
            )
            run = (
                use.plant / _mean_yield(plan, product.company_id) * plan.slots[pid]
                if use.plant
                else 0
            )
            variable = run * balance.facility.kinds[balance.hardware.plant_kind].variable_cents
            assembly = round(fees + variable)
            rows.append(
                ProductionMonth(
                    turn,
                    pid,
                    product.company_id,
                    capacity=plan.capacity[pid],
                    units=units,
                    plant_units=use.plant,
                    contract_units=use.contract,
                    own_chips=use.own_chips,
                    bought_chips=bought,
                    bom_cents=bom,
                    chip_cents=chip,
                    assembly_cents=assembly,
                    lost_units=use.lost,
                )
            )
            total = bom + chip + assembly
            if total:
                memo = f"Cost of goods: {product.name}"
                entries.append(
                    _entry(turn, product.company_id, memo, total, COGS, product.division_id)
                )
    state, more = _contracts_month(state, plan, balance, data)
    entries += more
    state, more = _plants_month(state, plan, cm_sold, balance, data)
    entries += more
    state = replace(state, production=tuple(rows))
    if state.fabs:  # M21 (38.2): own starts, foundry slots and the fabs' month
        state, more = fab_plants.settle_fabs(state, fab_used, balance, data)
        entries += more
    return state, entries


def _fab_made(plan: ProductionPlan, pid: int) -> float:
    """Chips the product made from its own fabs (taken first, 38.2)."""
    use = plan.usage.get(pid, _Usage())
    return min(use.market + use.internal, plan.fab_chips.get(pid, 0.0))


def _posted_units(
    state: GameState,
    plan: ProductionPlan,
    fab_used: dict[int, float],
    balance: Balance,
    data: GameData,
) -> dict[int, float]:
    """Each chip product's cost a chip at sale (26.3): contract chips at their unit cost, own-fab
    chips at packaging only (M21: the fab's month carries the wafer). Fills `fab_used` with the
    starts each fab ran for them."""
    out: dict[int, float] = {}
    for pid in sorted(plan.chips_capacity):
        product = state.product(pid)
        assert product is not None
        contract = chips.contract_unit_cents(state, product, balance, data)
        own = _fab_made(plan, pid)
        use = plan.usage.get(pid, _Usage())
        made = use.market + use.internal
        if own <= EPS or made <= EPS:
            out[pid] = contract
            continue
        pack = balance.chips.packaging_cents
        out[pid] = (own * pack + (made - own) * contract) / made
        left = own
        for s in fab_supply.product_shares(state, product, balance, data):
            if left <= EPS or s.chips_per_start <= 0:
                break
            cap = (
                s.starts * s.chips_per_start * _cap_share(plan, pid, state, product, balance, data)
            )
            got = min(left, cap)
            fab_used[s.facility_id] = fab_used.get(s.facility_id, 0.0) + got / s.chips_per_start
            left -= got
    return out


def _cap_share(
    plan: ProductionPlan,
    pid: int,
    state: GameState,
    product: Product,
    balance: Balance,
    data: GameData,
) -> float:
    """The commodity-shortage share applied to the product's fab chips (33.1)."""
    full = fab_supply.fab_chips(state, product, balance, data)
    return plan.fab_chips.get(pid, 0.0) / full if full > 0 else 0.0


def _mean_yield(plan: ProductionPlan, company: int) -> float:
    """The run-weighted yield of the company's plants this month (cost per good unit)."""
    ids = plan.plants_of.get(company, [])
    run = sum(plan.plant_run.get(f, 0.0) for f in ids)
    if run <= 0:
        return 1.0
    return sum(plan.plant_run.get(f, 0.0) * plan.plant_yield[f] for f in ids) / run


def _contracts_month(
    state: GameState, plan: ProductionPlan | None, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry]]:
    """Each running contract's use and take-or-pay this month (26.2, 26.3)."""
    entries: list[LedgerEntry] = []
    for c in state.production_contracts:
        if not c.running(state.turn):
            continue
        product = state.product(c.product_id)
        if product is None:
            continue
        if c.kind == "assembly":
            delivered = plan.contract_delivered.get(c.id) if plan else None
            if delivered is None:
                delivered = contract_delivered(state, c, balance, data)
            used = plan.contract_used.get(c.id, 0.0) if plan else 0.0
            share = balance.hardware.contract.take_or_pay
        else:
            delivered = chips.wafers_delivered(state, c, balance, data)
            used = _wafers_used(state, c, plan, balance, data)
            share = balance.chips.contract.take_or_pay
        charge = hf.take_or_pay_cents(delivered - used, c.price_cents, share)
        if charge:
            what = "contract-manufacturing" if c.kind == "assembly" else "wafer"
            memo = f"Take-or-pay: unused {what} volume for {product.name}"
            entries.append(
                _entry(state.turn, c.company_id, memo, charge, GENERAL_ADMIN, product.division_id)
            )
        state = with_production_contract(
            state, replace(c, delivered=delivered, used=used, charged_cents=charge)
        )
    return state, entries


def _wafers_used(
    state: GameState,
    contract: ProductionContract,
    plan: ProductionPlan | None,
    balance: Balance,
    data: GameData,
) -> float:
    """A wafer contract's share of the chips its product made, in wafers (by delivered
    wafers across the product's contracts)."""
    if plan is None or contract.product_id not in plan.chips_capacity:
        return 0.0
    cap = plan.chips_capacity[contract.product_id]
    if cap <= 0:
        return 0.0
    use = plan.usage.get(contract.product_id, _Usage())
    own = _fab_made(plan, contract.product_id)  # M21: own fabs' chips first (38.2)
    cap -= plan.fab_chips.get(contract.product_id, 0.0)
    if cap <= EPS:
        return 0.0
    made_share = min(1.0, max(0.0, use.market + use.internal - own) / cap)
    return chips.wafers_delivered(state, contract, balance, data) * made_share


def _plants_month(
    state: GameState,
    plan: ProductionPlan | None,
    cm_sold: dict[int, float],
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry]]:
    """Each live plant's units run this month (own and sold), and the variable cost of the
    units run for contract-manufacturing customers (5000)."""
    entries: list[LedgerEntry] = []
    for company in player_companies(state):
        for f in live_plants(state, company.id, balance):
            own = plan.plant_run.get(f.id, 0.0) if plan else 0.0
            sold = cm_sold.get(f.id, 0.0)
            cost = round(sold * plant_unit_cents(state, f, balance))
            if cost:
                memo = f"Cost of goods: contract manufacturing at {facility_name(f, balance, data)}"
                entries.append(_entry(state.turn, f.company_id, memo, cost, COGS, None))
            state = with_facility(state, replace(f, run_units=own, sold_units=sold))
    return state, entries


def spare_units(
    state: GameState, company_id: int, plan: ProductionPlan | None, balance: Balance
) -> dict[int, float]:
    """Plant id -> run units left after the company's own products this month."""
    out: dict[int, float] = {}
    for f in live_plants(state, company_id, balance):
        out[f.id] = (
            plan.plant_left[f.id]
            if plan and f.id in plan.plant_left
            else runnable(state, f, balance)
        )
    return out
