"""Export controls on M21's fabs (docs/formulas.md 39.3, wired at the M21 merge).

A fab order (a new fab, or a conversion to a new node) needs tools from the US-aligned
toolmakers. It is refused when the fab's country (its city's, else its region's default) is a
destination of a biting rule on

- `euv_tools`, for a node that uses EUV (M21's `uses_euv`), or
- `chip_equipment`, for a node at or below `geopolitics.equipment_node` (16/14 nm, October
  2022's line),

unless the company holds an approved **tool licence** for that rule and country (a licence
with product id 0: `RequestToolLicence`, decided like a product's, 39.3). A company on an
entity list of a toolmakers' actor gets neither, licence or not. Orders already placed are not
recalled (M22 decision). M21's foundry customers are the chip incumbents, none in China, so
`fab_services` rules have no sale to stop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import GeopoliticsRuleError
from tst.sim.fabs import market as fm
from tst.sim.geopolitics import rules as gr
from tst.sim.geopolitics import world
from tst.sim.geopolitics.models import Licence
from tst.sim.geopolitics.rules import ActiveRule
from tst.sim.log import inbox_item
from tst.sim.state import GameState, with_licence

TOOLS: Final = 0  # tunable-exempt: a tool licence's product id
EUV: Final = "euv_tools"
EQUIPMENT: Final = "chip_equipment"
TOOLMAKERS: Final = ("us", "netherlands", "japan", "us_aligned")


@dataclass(frozen=True, slots=True)
class RequestToolLicence:
    actor_id: int
    country: str
    kind: Literal["request_tool_licence"] = "request_tool_licence"


def advanced(data: GameData, node: str, balance: Balance) -> bool:
    keys = fm.nodes_file(data).node_keys()
    return keys.index(node) >= keys.index(balance.geopolitics.equipment_node)


def tool_rules(
    state: GameState, country: str, node: str, duv: bool, balance: Balance, data: GameData
) -> list[ActiveRule]:
    """Biting rules on the tools a fab at `node` in `country` needs."""
    euv = fm.uses_euv(data, node, duv)
    adv = advanced(data, node, balance)
    out = []
    for a in gr.biting(state, data):
        goods = set(a.rule.goods)
        if not ((euv and EUV in goods) or (adv and EQUIPMENT in goods)):
            continue
        if country in world.destination_countries(data, a.rule, state.turn):
            out.append(a)
    return out


def tool_licensed(state: GameState, company_id: int, rule_key: str, country: str) -> bool:
    return any(
        x.company_id == company_id
        and x.product_id == TOOLS
        and x.rule_key == rule_key
        and x.country == country
        and x.status == "approved"
        and (x.until_turn is None or state.turn <= x.until_turn)
        for x in state.licences
    )


def check_order(
    state: GameState,
    company_id: int,
    country: str,
    node: str,
    duv: bool,
    balance: Balance,
    data: GameData,
) -> None:
    """Refuse a fab order the controls forbid (module docstring)."""
    if not world.enabled(data) or not world.in_group(state, company_id):
        return
    euv = fm.uses_euv(data, node, duv)
    if (euv or advanced(data, node, balance)) and any(
        x.company_id == company_id and x.actor in TOOLMAKERS for x in state.entity_listings
    ):
        raise GeopoliticsRuleError("the company is on an entity list: no advanced chip tools")
    for a in tool_rules(state, country, node, duv, balance, data):
        if a.rule.regime == "ban" or not tool_licensed(state, company_id, a.key, country):
            label = world.countries_of(data).country(country).label
            need = "is banned" if a.rule.regime == "ban" else "needs an export licence"
            raise GeopoliticsRuleError(f"{a.rule.title}: tools for a fab in {label} {need}")


def fab_country(state: GameState, region: str, city: str | None, data: GameData) -> str:
    if city is not None:
        return world.city_country(data, city)
    return world.countries_of(data).default_of(region).key


def request_tool_licence(
    state: GameState, action: RequestToolLicence, balance: Balance, data: GameData
) -> Outcome:
    company = acting_company(state, action.actor_id)
    found = [
        a
        for a in gr.biting(state, data)
        if a.rule.regime == "licence"
        and {EUV, EQUIPMENT} & set(a.rule.goods)
        and action.country in world.destination_countries(data, a.rule, state.turn)
        and not tool_licensed(state, company, a.key, action.country)
        and not any(
            x.company_id == company
            and x.product_id == TOOLS
            and x.rule_key == a.key
            and x.country == action.country
            and x.status == "pending"
            for x in state.licences
        )
    ]
    if not found:
        raise GeopoliticsRuleError(f"no tool licence is needed or possible for {action.country}")
    lb = balance.geopolitics.licence
    state = spend_energy(state, action.actor_id, "request_tool_licence", balance, cost=lb.energy)
    for a in found:
        state = with_licence(
            state,
            Licence(
                id=max((x.id for x in state.licences), default=0) + 1,
                company_id=company,
                product_id=TOOLS,
                rule_key=a.key,
                country=action.country,
                requested_turn=state.turn,
                decide_turn=state.turn + lb.decision_months,
            ),
        )
    log = inbox_item(
        state.turn,
        company,
        "licence_requested",
        link_kind="world",
        link_id=company,
        product="chipmaking tools",
        country=world.countries_of(data).country(action.country).label,
        decision=format_turn(state.turn + lb.decision_months),
    )
    return Outcome(state, (), (log,))
