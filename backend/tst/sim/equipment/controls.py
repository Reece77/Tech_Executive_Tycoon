"""Export controls on the queue (docs/formulas.md 47.3).

An open order is **blocked** this month when its tools' destination is covered by

- one of equipment.yaml's dated queue rules on its generation (to December 2025; from 2026 M22's
  rules carry the bans, so a détente can loosen them), or
- a biting M22 rule on `euv_tools` (every queued generation is EUV) whose destinations take in
  the order's country, or that names the buyer as an entity: a ban always; a licence regime
  unless the player's company holds an approved tool licence for that rule and country (rivals
  request no licences, M23a), or
- an entity listing of the player's company by a toolmakers' actor (M22's fab rule).

A blocked order loses its place (status `lost`). Installed tools in a country a biting **ban**
covers lose `equipment.service_ban_uptime_cut` of their uptime (servicing restricted).
"""

from __future__ import annotations

from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.equipment import data as ed
from tst.sim.equipment.models import ToolOrder
from tst.sim.fabs.nodes import HISTORY_END
from tst.sim.geopolitics import rules as gr
from tst.sim.geopolitics import world
from tst.sim.geopolitics.config import EntityTarget
from tst.sim.geopolitics.rules import ActiveRule
from tst.sim.state import GameState

PLAYER: Final = "player"  # tunable-exempt: an order's buyer key for the player's group
# M22's (tst.sim.geopolitics.fabs; not imported: that module imports the actions package)
EUV: Final = "euv_tools"
TOOLMAKERS: Final = ("us", "netherlands", "japan", "us_aligned")
TOOLS: Final = 0  # tunable-exempt: a tool licence's product id (M22)


def tool_licensed(state: GameState, company_id: int, rule_key: str, country: str) -> bool:
    """As tst.sim.geopolitics.fabs.tool_licensed: an approved tool licence in force."""
    return any(
        x.company_id == company_id
        and x.product_id == TOOLS
        and x.rule_key == rule_key
        and x.country == country
        and x.status == "approved"
        and (x.until_turn is None or state.turn <= x.until_turn)
        for x in state.licences
    )


def queue_rules(data: GameData, generation: str, country: str, turn: int) -> list[str]:
    """equipment.yaml's dated rules on `generation` to `country` in `turn` (to 2025)."""
    if turn > HISTORY_END:
        return []
    return [
        c.title
        for c in ed.equipment_file(data).controls
        if c.generation == generation and country in c.to and c.turn <= turn
    ]


def _entity_hit(active: ActiveRule, name: str | None) -> bool:
    if name is None:
        return False
    return any(
        isinstance(to, EntityTarget) and to.entity.casefold() == name.casefold()
        for to in active.rule.to
    )


def m22_rules(
    state: GameState, data: GameData, country: str, name: str | None, turn: int | None = None
) -> list[ActiveRule]:
    """Biting M22 rules on EUV tools covering `country` or the entity `name`."""
    if not world.enabled(data):
        return []
    t = state.turn if turn is None else turn
    out = []
    for a in gr.biting(state, data, t):
        if EUV not in a.rule.goods:
            continue
        if country in world.destination_countries(data, a.rule, t) or _entity_hit(a, name):
            out.append(a)
    return out


def blocking(
    state: GameState,
    data: GameData,
    generation: str,
    country: str,
    *,
    company_id: int | None = None,
    name: str | None = None,
) -> str | None:
    """Why tools of `generation` to `country` (for the player's `company_id`, or the rival
    entity `name`) are blocked this month, or None (module docstring)."""
    hits = queue_rules(data, generation, country, state.turn)
    if hits:
        return hits[0]
    if company_id is not None and any(
        x.company_id == company_id and x.actor in TOOLMAKERS for x in state.entity_listings
    ):
        return "the company is on an entity list"
    for a in m22_rules(state, data, country, name):
        if a.rule.regime == "ban":
            return a.rule.title
        if company_id is None or not tool_licensed(state, company_id, a.key, country):
            return a.rule.title
    return None


def order_blocked(state: GameState, data: GameData, order: ToolOrder) -> str | None:
    country = order.country or ed.equipment_file(data).buyer_countries.get(order.buyer, "us")
    if order.buyer == PLAYER:
        return blocking(state, data, order.generation, country, company_id=order.company_id)
    return blocking(state, data, order.generation, country, name=buyer_name(data, order.buyer))


def buyer_name(data: GameData, buyer: str) -> str | None:
    """A rival buyer's name as an entity list writes it (nodes.yaml's foundry name)."""
    assert data.nodes is not None
    for f in data.nodes.foundries:
        if f.key == buyer:
            return f.name
    return None


def service_banned(state: GameState, data: GameData, country: str) -> bool:
    """Whether a biting ban on EUV tools covers `country` (47.3: servicing restricted)."""
    return any(a.rule.regime == "ban" for a in m22_rules(state, data, country, None))


def uptime_factor(state: GameState, data: GameData, country: str, balance: Balance) -> float:
    if service_banned(state, data, country):
        return 1.0 - balance.equipment.service_ban_uptime_cut
    return 1.0
