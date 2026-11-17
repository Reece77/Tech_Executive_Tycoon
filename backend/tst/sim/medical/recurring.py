"""Consumables and service (docs/formulas.md 50.1): the razor-and-blade part of a medical
device's revenue, after the markets in phase 5.

Each month every selling device in a sub-category with `consumables_cents` books installed units
(customers x units per customer, home and abroad) x that amount at the region's price index
(4050 consumables and service revenue), with its cost share (5000 cost of goods). Rivals' devices
book it too: their 2010 revenue mix follows the data (Intuitive's 53% recurring)."""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.geo.cities import home_region
from tst.sim.geo.formulas import regional_price_cents
from tst.sim.ledger import CASH, COGS, MEDICAL_RECURRING, LedgerEntry, LedgerLine
from tst.sim.medical import data as md
from tst.sim.money import times
from tst.sim.state import GameState

SELLING = ("live", "sunset")


def recurring_month(state: GameState, balance: Balance, data: GameData) -> list[LedgerEntry]:
    if not md.enabled(data):
        return []
    entries: list[LedgerEntry] = []
    home: str | None = None
    for product in state.products:
        if product.status not in SELLING:
            continue
        sub = md.subcategory(data, product.category)
        if sub is None or sub.consumables_cents <= 0:
            continue
        cat = data.category(product.category)
        if home is None:
            home = home_region(state, balance, data) if data.cities else data.region_keys[0]
        rows: list[tuple[float, int]] = []
        for seg in state.segments_of(product.id):
            units = seg.customers * cat.market(seg.segment).units_per_customer
            rows.append((units, sub.consumables_cents))
        for rseg in state.regional_segments_of(product.id):
            units = rseg.customers * cat.market(rseg.segment).units_per_customer
            rows.append(
                (units, regional_price_cents(sub.consumables_cents, rseg.region, home, data))
            )
        revenue = sum(times(cents, units) for units, cents in rows)
        if revenue <= 0:
            continue
        d = product.division_id
        entries.append(
            LedgerEntry(
                turn=state.turn,
                company_id=product.company_id,
                memo=f"Consumables and service: {product.name}",
                lines=(LedgerLine(CASH, revenue, d), LedgerLine(MEDICAL_RECURRING, -revenue, d)),
            )
        )
        cost = times(revenue, sub.consumables_cogs)
        if cost > 0:
            entries.append(
                LedgerEntry(
                    turn=state.turn,
                    company_id=product.company_id,
                    memo=f"Cost of consumables: {product.name}",
                    lines=(LedgerLine(COGS, cost, d), LedgerLine(CASH, -cost, d)),
                )
            )
    return entries
