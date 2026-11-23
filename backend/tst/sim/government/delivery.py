"""Contracts and their delivery (docs/formulas.md 57.2).

A contract starts the month after its award stands, for its tender's term (base months, then the
options). Each month (stream `defence` (3, contract_id, turn)): the month's ceiling V = value /
term months; an IDIQ vehicle's task orders are V x U(`idiq_orders`); the delivery cost is the
work x `cost_share[area]` x (1 + overrun), overrun ~ N(`overrun_mean`, `overrun_sd[type]`),
floored at -0.1. Revenue is the work for fixed-price and IDIQ (the
company bears the overrun) and the cost x (1 + `cost_plus_fee`) for cost-plus (the government
does). The month's performance is 100 - `perf_per_overrun` x the overrun in percent (0-100), its
running mean the contract's. A month the company cannot deliver (its product no longer live, or
a classified contract's clearances lapsed) earns nothing and scores 0; `lapse_months` of them in a
row is a default. At the base's end the options are exercised when performance is at least
`option_threshold`, else the contract completes. Completed and defaulted contracts are the
company's past performance (57.2).

A fixed-price month's revenue is its installment: the price x months / term rounded, less the
same for the months before (so a contract delivered every month books its price exactly).

Books: revenue 4070 against cash, delivery cost 5300 against cash, in integer cents (rounded
half to even once each), in the product's division."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.government import draws
from tst.sim.government.config import LEVELS, Level
from tst.sim.government.data import PCT, file
from tst.sim.government.models import (
    Bid,
    Contract,
    ContractMonth,
    ContractStatus,
    ControlledProduct,
    Tender,
)
from tst.sim.government.sourcing import cleared_facility, cleared_staff
from tst.sim.ledger import CASH, CONTRACT_COSTS, GOVERNMENT_REVENUE, LedgerEntry, LedgerLine
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import exact
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

OVERRUN_FLOOR: Final = -0.1  # tunable-exempt: a month's saving is at most 10%


def start(
    state: GameState, tender: Tender, bid: Bid, balance: Balance, data: GameData
) -> tuple[GameState, Contract]:
    """The player's contract from an award that stands (this month), and its controlled product."""
    world = state.government_world
    begin = state.turn + 1
    contract = Contract(
        id=world.next_contract,
        tender_id=tender.id,
        company_id=bid.company_id,
        product_id=bid.product_id,
        government=tender.government,
        area=tender.area,
        buyer=tender.buyer,
        contract=tender.contract,
        value_cents=bid.price_cents,
        start_turn=begin,
        base_end_turn=begin + tender.base_months,
        end_turn=begin + tender.term_months,
        awards=tender.awards,
        clearance=tender.clearance,
    )
    state = replace(
        state,
        gov_contracts=(*state.gov_contracts, contract),
        government_world=replace(world, next_contract=world.next_contract + 1),
    )
    area = file(data).areas[tender.area]
    if (
        tender.buyer == "defence"
        and area.controlled
        and not any(c.product_id == bid.product_id for c in state.controlled_products)
    ):
        state = replace(
            state,
            controlled_products=(
                *state.controlled_products,
                ControlledProduct(bid.product_id, bid.company_id, begin),
            ),
        )
    return state, contract


def _entitled(value_cents: int, months: int, term: int) -> int:
    """Cents of a fixed price earned over its first `months` of `term`, rounded half to even."""
    return round(Fraction(value_cents * months, term))


def requirement(state: GameState, c: Contract, balance: Balance) -> Level:
    """The clearance the contract's delivery needs: the awarded tender's, kept on the contract.
    A contract from before M43r has it from its tender while the tender is kept (the loader
    copies it); one whose tender was already pruned needs the strictest level its buyer's
    tenders are drawn at, since the awarded one cannot be known (M43r decision)."""
    if c.clearance is not None:
        return c.clearance
    tender = state.tender(c.tender_id)
    if tender is not None:
        return tender.clearance
    mix = balance.government.tenders.clearance_mix[c.buyer]
    return next((lv for lv in reversed(LEVELS) if mix.get(lv, 0.0) > 0), "none")


def _able(state: GameState, c: Contract, clearance: str, balance: Balance) -> bool:
    product = state.product(c.product_id)
    if product is None or product.status != "live":
        return False
    if clearance == "none":
        return True
    need = balance.government.clearances.required.get(clearance, 0)
    return cleared_staff(state, c.company_id, clearance) >= need and cleared_facility(
        state, c.company_id
    )


def month(
    state: GameState, rng: RngFactory, balance: Balance
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not any(c.status == "active" for c in state.gov_contracts):
        return state, [], []
    db = balance.government.delivery
    turn = state.turn
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    out = []
    for c in state.gov_contracts:
        if c.status != "active" or turn < c.start_turn:
            out.append(c)
            continue
        if turn >= c.end_turn:
            out.append(replace(c, status="completed", month=None))
            logs.append(inbox_item(turn, c.company_id, "contract_completed", contract=str(c.id)))
            continue
        if turn == c.base_end_turn and c.options == "pending" and c.base_end_turn < c.end_turn:
            if c.performance >= db.option_threshold:
                c = replace(c, options="exercised")
            else:
                out.append(replace(c, options="declined", status="completed", month=None))
                logs.append(
                    inbox_item(turn, c.company_id, "contract_options_declined", contract=str(c.id))
                )
                continue
        clearance = requirement(state, c, balance)
        g = draws.gen(rng, turn, draws.DELIVERY, c.id, turn)
        overrun = max(
            OVERRUN_FLOOR, db.overrun_mean + db.overrun_sd[c.contract] * float(g.normal())
        )
        orders = db.idiq_orders.lo + (db.idiq_orders.hi - db.idiq_orders.lo) * float(g.random())
        if not _able(state, c, clearance, balance):
            unable = c.unable_months + 1
            perf = (c.performance * c.months) / (c.months + 1)
            status: ContractStatus = "defaulted" if unable >= db.lapse_months else "active"
            out.append(
                replace(
                    c,
                    unable_months=unable,
                    months=c.months + 1,
                    performance=perf,
                    status=status,
                    month=ContractMonth(turn, 0, 0, 0.0),
                )
            )
            if status == "defaulted":
                logs.append(
                    inbox_item(turn, c.company_id, "contract_defaulted", contract=str(c.id))
                )
            continue
        term = max(1, c.end_turn - c.start_turn)
        work = exact(c.value_cents) / term
        if c.contract == "idiq":
            work *= exact(orders)
        cost = work * exact(db.cost_share[c.area]) * (1 + exact(overrun))
        revenue = cost * (1 + exact(db.cost_plus_fee)) if c.contract == "cost_plus" else work
        cost_c = round(cost)
        if c.contract == "fixed_price":
            # installment i is the difference of the rounded cumulative entitlements, so the
            # months delivered settle the accepted price exactly (M43r, review 9 finding 13)
            i = turn - c.start_turn
            rev_c = _entitled(c.value_cents, i + 1, term) - _entitled(c.value_cents, i, term)
        else:
            rev_c = round(revenue)
        month_perf = max(0.0, min(PCT, PCT - db.perf_per_overrun * max(0.0, overrun) * PCT))
        perf = (c.performance * c.months + month_perf) / (c.months + 1)
        product = state.product(c.product_id)
        div = product.division_id if product is not None else None
        if rev_c > 0:
            entries.append(
                LedgerEntry(
                    turn=turn,
                    company_id=c.company_id,
                    memo=f"Government contract {c.id}",
                    lines=(
                        LedgerLine(CASH, rev_c, div),
                        LedgerLine(GOVERNMENT_REVENUE, -rev_c, div),
                    ),
                )
            )
        if cost_c > 0:
            entries.append(
                LedgerEntry(
                    turn=turn,
                    company_id=c.company_id,
                    memo=f"Government contract {c.id} delivery",
                    lines=(LedgerLine(CONTRACT_COSTS, cost_c, div), LedgerLine(CASH, -cost_c, div)),
                )
            )
        out.append(
            replace(
                c,
                months=c.months + 1,
                unable_months=0,
                performance=perf,
                revenue_cents=c.revenue_cents + rev_c,
                cost_cents=c.cost_cents + cost_c,
                month=ContractMonth(turn, rev_c, cost_c, month_perf),
            )
        )
    return replace(state, gov_contracts=tuple(out)), entries, logs
