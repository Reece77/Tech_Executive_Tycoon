"""Explain for M54's numbers (docs/formulas.md 64): a bank's profit and a region's currency result.
Public figures only (64.5): the player's own books and months; never a run's chance, a stress
test's shock or a catastrophe before it happens."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tst.advisor.model import Explanation, Item, MetricDef
from tst.advisor.v3 import _bad, _id, _none

if TYPE_CHECKING:
    from tst.advisor.build import Builder

YEAR_MONTHS = 12  # tunable-exempt: calendar


def bank_profit(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A bank's last 12 months: interest earned (loans, securities, reserves and its cards'
    interchange) less deposit interest and charge-offs (64.1)."""
    if not entity:
        return _none(b, m, "bank")
    bank = b.state.finserv.bank(_id(entity, "bank"))
    players = {c.id for c in b.state.companies if c.is_player}
    if bank is None or bank.company_id not in players:
        raise _bad(f"no bank {entity!r}")
    label = f"{b.data.game_data.region(bank.region).label} bank"
    months = [x for x in b.state.finserv.bank_months if x.bank_id == bank.id][-YEAR_MONTHS:]
    if not months:
        return b._out(
            m, entity, None, [], "Not lending yet: a bank earns once chartered.", (), [], label
        )
    income = sum(x.interest_income_cents for x in months)
    cost = sum(x.deposit_interest_cents for x in months)
    losses = sum(x.charge_offs_cents for x in months)
    last = months[-1]
    items = [
        Item("Interest and interchange earned, last 12 months", income, "cents"),
        Item("Deposit interest paid", -cost, "cents"),
        Item("Loans charged off", -losses, "cents"),
        Item("Policy rate now (% a year)", last.policy_rate, "points"),
        Item("Your deposit rate now (% a year)", last.deposit_rate, "points"),
    ]
    note = (
        f"Deposits pay the policy rate x your deposit beta ({bank.beta:.2f}); loans earn the "
        "policy rate plus their spread, so a low beta widens the margin as rates rise, and "
        "deposits leave faster."
    )
    return b._out(m, entity, income - cost - losses, items, note, (), [], label)


def fx_result(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A region's currency result over the last 12 months: what translation added to or took
    from revenue and local costs, and what forwards settled (64.4)."""
    if not entity:
        return _none(b, m, "region")
    d = b.data.game_data
    if entity not in d.region_keys:
        raise _bad(f"no region {entity!r}")
    players = {c.id for c in b.state.companies if c.is_player}
    rows = [
        x
        for x in b.state.fx.months
        if x.company_id in players and x.region == entity and x.turn > b.state.turn - YEAR_MONTHS
    ]
    label = d.region(entity).label
    if not rows:
        return b._out(
            m, entity, None, [], "You earn and spend nothing in this region.", (), [], label
        )
    revenue = sum(x.revenue_cents - x.untranslated_revenue_cents for x in rows)
    costs = sum(x.cost_cents - x.untranslated_cost_cents for x in rows)
    hedged = sum(x.hedge_cents for x in rows)
    items = [
        Item("Translation of revenue, last 12 months", revenue, "cents"),
        Item("Translation of local costs", -costs, "cents"),
        Item("Forwards settled", hedged, "cents"),
    ]
    note = (
        "Prices and local costs are set in local money: when the dollar rises they are worth "
        "fewer dollars. Forwards fix the rate ahead; their gains and losses are below the "
        "operating result."
    )
    return b._out(m, entity, revenue - costs + hedged, items, note, (), [], f"{label} currency")
