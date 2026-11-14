"""The platforms' place in the turn (docs/formulas.md 44; ADR-0021 2), in phase 5.

`before_markets`: the platforms month (users, developers, catalogues) and the effects demand
reads (none before 2026). `after_markets`, on the month's customers and revenue: fees and
licences (from `platforms.fees_from`), then removals' losses and win-backs, open products'
adoption, appeals' answers, gatekeepers' reviews, the player's own reviews, standards and the
rivals' December moves (all from 2026).
"""

from __future__ import annotations

from collections.abc import Mapping

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import LedgerEntry
from tst.sim.log import LogItem
from tst.sim.platforms import data as pdata
from tst.sim.platforms import fees, gatekeep, opensource, rivals, standards
from tst.sim.platforms.phase import Effects, effects, platforms_month
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def before_markets(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, Effects | None]:
    if not pdata.enabled(data):
        return state, None
    state = platforms_month(state, rng, balance, data)
    eff = effects(state, balance, data)
    return state, eff if (
        eff.feature_bonus or eff.appeal_mult or eff.churn_mult or eff.revenue_share
    ) else None


def after_markets(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    flows: Mapping[tuple[int, str], object],
    regional_units: Mapping[tuple[int, str, str], float],
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not pdata.enabled(data) or not state.platforms:
        return state, [], []
    entries: list[LedgerEntry] = fees.fee_entries(state, balance, data)
    units = fees.units_sold(flows, regional_units)
    entries += fees.licence_entries(state, units, balance, data)
    entries += fees.own_licence_entries(state, units, balance, data)
    if pdata.in_history(state.turn, data):
        return state, entries, []
    logs: list[LogItem] = []
    state = gatekeep.listing_effects(state, balance, data)
    state = opensource.adoption_month(state, balance, data)
    state, more = gatekeep.answers_month(state, rng, balance, data)
    logs += more
    state, posted, more = gatekeep.reviews_month(state, rng, balance, data)
    entries += posted
    logs += more
    state, more = gatekeep.player_reviews(state, balance, data)
    logs += more
    state, more = standards.standards_month(state, rng, balance, data)
    logs += more
    state, more = rivals.rivals_month(state, rng, balance, data)
    logs += more
    return state, entries, logs
