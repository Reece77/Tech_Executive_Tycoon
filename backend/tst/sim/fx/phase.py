"""Currencies' place in the turn (docs/formulas.md 64.4, ADR-0025).

- **Phase 5, before the markets** (`before_markets`): this month's step of each region's index walk
  (from `fx.applies_from`), the translation marks (a new or changed regional price is marked at this
  month's index), and the month's translated prices, which revenue books at (`Effects.fx_price`).
- **Phase 5, after the markets** (`after_sales`): each player company's foreign money this month
  (revenue and local costs by region, translated and as set), its hedging programme's forwards,
  then every open forward's fair value and settlements.
- **Phase 6, after payroll** (`cost_entries`): local salaries and rent abroad translated.

A company that sells and spends only in North America books exactly as before (64.6 target 1).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.fx import hedges, rates, translate
from tst.sim.fx.models import FxMonth
from tst.sim.ledger import LedgerEntry
from tst.sim.platforms.phase import NO_EFFECTS, Effects
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def before_markets(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, dict[tuple[int, str, str], int]]:
    if not rates.enabled(data):
        return state, {}
    state = rates.walk_month(state, rng, balance, data)
    state = translate.update_marks(state, balance, data)
    return state, translate.fx_prices(state, balance, data)


def with_effects(base: Effects | None, prices: dict[tuple[int, str, str], int]) -> Effects | None:
    if not prices:
        return base
    return replace(base if base is not None else NO_EFFECTS, fx_price=prices)


def _foreign_months(
    state: GameState,
    balance: Balance,
    data: GameData,
    booked: Mapping[tuple[int, str], tuple[int, int]],
    settled: Mapping[tuple[int, str], int],
) -> GameState:
    """Each player company's foreign revenue and local costs by region this month (FxMonth).
    M57r-A (review 10 items 11-12): revenue is what phase 5 booked there (units sold for a
    unit-sale line, the ad tier's paid share), and the hedge column every forward that settled
    in the region this month, summed; a region with settlements alone has a row too."""
    xb = balance.fx
    months: list[FxMonth] = []
    for company in state.companies:
        if not company.is_player:
            continue
        rev = {
            region: amounts
            for (cid, region), amounts in booked.items()
            if cid == company.id and region != xb.home and amounts != (0, 0)
        }
        costs = translate.local_costs(state, company.id, balance, data)
        hedged = {r: v for (cid, r), v in settled.items() if cid == company.id}
        for region in data.region_keys:
            if region == xb.home or (
                region not in rev and region not in costs and region not in hedged
            ):
                continue
            r_now, r_set = rev.get(region, (0, 0))
            c = costs.get(region, translate.LocalCosts())
            months.append(
                FxMonth(
                    turn=state.turn,
                    company_id=company.id,
                    region=region,
                    revenue_cents=r_now,
                    cost_cents=c.base_cents + c.delta_cents,
                    untranslated_revenue_cents=r_set,
                    untranslated_cost_cents=c.base_cents,
                    hedge_cents=hedged.get(region, 0),
                )
            )
    if not months and not state.fx.months:
        return state
    keep = xb.history_months
    kept = tuple(m for m in state.fx.months if m.turn > state.turn - keep and m.turn != state.turn)
    return replace(state, fx=replace(state.fx, months=(*kept, *months)))


def after_sales(
    state: GameState,
    balance: Balance,
    data: GameData,
    booked: Mapping[tuple[int, str], tuple[int, int]] | None = None,
) -> tuple[GameState, list[LedgerEntry]]:
    """`booked`: phase 5's revenue by (company, region), booked and as set (MarketOutcome)."""
    if not rates.enabled(data):
        return state, []
    state, entries, settled = hedges.mark_and_settle(state, balance, data)
    state = _foreign_months(state, balance, data, booked or {}, settled)
    if state.fx.programmes:
        state = hedges.programme_month(state, balance, data)
    if state.fx.hedges:
        state = hedges.prune(state, balance)
    return state, entries


def cost_entries(state: GameState, balance: Balance, data: GameData) -> list[LedgerEntry]:
    if not rates.enabled(data):
        return []
    return translate.cost_entries(state, balance, data)
