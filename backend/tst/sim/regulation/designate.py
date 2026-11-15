"""Gatekeeper designation (docs/formulas.md 48.1), each December from `regulation.start`.

For every regime in force and every group (an ultimate owner with books), the test reads:

- **users:** the largest share of the region's users on a platform it owns (44: a device
  platform's share of device users, a developer platform's of its category), against the regime's
  `users_share` (the DMA's 45M of the EU's 447M; Japan's 40M of 126M; Korea's any app store).
  The game counts no individual users of other products, so a core service is a platform (A).
  A regime without a users test (the UK's) reads `regulation.dominance_share` ("substantial
  and entrenched market power", A);
- **money:** its turnover (in the region, or the world's for the UK) against `turnover_b`, or its
  market value against `value_b` (listed companies), whichever is nearer; a regime with neither
  passes it.

The test's ratio is the smaller of the two. At 1 or more a company warned at least a year before
is designated; one not yet warned is warned now (so a warning always comes a year ahead). At
`regulation.warn_ratio` or more a company is warned, once a year. A designation's duties start
`comply_months` later (tst.sim.regulation.duties). History's designations (regulation.yaml) are
data; a company already designated under a regime is not tested again."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import LedgerBalances
from tst.sim.log import LogItem, inbox_item
from tst.sim.mna.valuation import market_cap_cents
from tst.sim.regulation import data as rdata
from tst.sim.regulation.config import RegimeDef
from tst.sim.regulation.measure import View
from tst.sim.regulation.models import Designation, DesignationWarning
from tst.sim.state import GameState, owner_of

DECEMBER: Final = MONTHS_PER_YEAR - 1  # tunable-exempt: calendar
LINK: Final = "regulation"
SHOWN_MAX: Final = 9.99  # tunable-exempt: a warning shows at most 999%
NO_TEST: Final = 10.0  # tunable-exempt: a test a regime does not set counts as passed


def is_designated(state: GameState, data: GameData, company_id: int, regime: str) -> bool:
    if any(d.regime == regime and d.company_id == company_id for d in state.designations):
        return True
    return rdata.designated_in_history(state, data, company_id, regime, state.turn) is not None


def designated_by(state: GameState, data: GameData, company_id: int, regulator: str) -> bool:
    return any(
        is_designated(state, data, company_id, g.key)
        for g in rdata.file(data).regimes
        if g.regulator == regulator
    )


def users_measure(v: View, owner: int, region: str) -> float:
    return v.users.get((owner, region), 0.0)


def ratio(
    state: GameState,
    regime: RegimeDef,
    owner: int,
    v: View,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
) -> float:
    """The designation test's ratio for the group (module docstring)."""
    reg = rdata.file(data).regulator(regime.regulator)
    users = users_measure(v, owner, reg.region)
    if regime.users_share is None:
        u = users / balance.regulation.dominance_share
    elif regime.users_share == 0:
        u = NO_TEST if v.users.get((owner, reg.region), 0.0) > 0 else 0.0
    else:
        u = users / rdata.game_users_share(regime.users_share, balance)
    turnover = rdata.game_threshold_cents(regime.turnover_b, regime.currency, balance)
    value = rdata.game_threshold_cents(regime.value_b, regime.currency, balance)
    if turnover is None and value is None:
        money = NO_TEST
    else:
        money = 0.0
        if turnover is not None:
            have = (
                v.world_year.get(owner, 0)
                if regime.turnover_scope == "world"
                else round(v.region_year(owner, reg.region) * rdata.part_share(data, reg))
            )
            money = have / turnover
        if value is not None and balances is not None:
            cap = market_cap_cents(state, owner, balances, balance, data)
            if cap is not None:
                money = max(money, cap / value)
    return min(u, money)


def december(
    state: GameState,
    v: View,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LogItem]]:
    if state.turn % MONTHS_PER_YEAR != DECEMBER:
        return state, []
    rb = balance.regulation
    logs: list[LogItem] = []
    owners = sorted({owner_of(state, c.id) for c in state.ledger_companies()})
    for regime in rdata.file(data).regimes:
        if regime.in_force_turn > state.turn:
            continue
        reg = rdata.file(data).regulator(regime.regulator)
        for owner in owners:
            if is_designated(state, data, owner, regime.key):
                continue
            r = ratio(state, regime, owner, v, balances, balance, data)
            if r < rb.warn_ratio:
                continue
            warned = [
                w.turn
                for w in state.designation_warnings
                if w.regime == regime.key and w.company_id == owner
            ]
            year_ago = state.turn - MONTHS_PER_YEAR
            if r >= 1 and warned and min(warned) <= year_ago:
                g = Designation(regime.key, owner, state.turn, state.turn + regime.comply_months)
                state = replace(state, designations=(*state.designations, g))
                logs.append(
                    inbox_item(
                        state.turn, owner, "regulation_designated", link_kind=LINK,
                        regime=regime.name, regulator=reg.name, months=regime.comply_months,
                    )
                )  # fmt: skip
            elif not warned or max(warned) <= year_ago:
                w = DesignationWarning(regime.key, owner, state.turn)
                state = replace(state, designation_warnings=(*state.designation_warnings, w))
                logs.append(
                    inbox_item(
                        state.turn, owner, "regulation_designation_warning", link_kind=LINK,
                        regime=regime.name, regulator=reg.name, pct=f"{min(r, SHOWN_MAX):.0%}",
                    )
                )  # fmt: skip
    return state, [x for x in logs if x.company_id == state.player.id]
