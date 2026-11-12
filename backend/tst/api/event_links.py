"""The screens an event is about (M23c, playtest 5: "If I haven't looked in a while I don't
have the information to make an informed decision"). Each link is a path under the game's
route (`/game/{save}/...`) and a label; the event card shows them so the player can look before
answering. Read only: the links come from the event's own subjects (its product, people, rival,
loan) and, for v3's facilities, the mine, refinery or project whose open event it is."""

from __future__ import annotations

from tst.api.schemas.events import EventLinkOut
from tst.api.views import person_name
from tst.loader import LoadedData
from tst.sim.events.models import GameEvent
from tst.sim.mining.actions import mine_name
from tst.sim.state import GameState, group_members, listed_id

MAX_PEOPLE = 2  # tunable-exempt: a pair event names two people; more would crowd the card

# A category's screen, when the event names nothing more specific.
CATEGORY_SCREENS: dict[str, tuple[str, str]] = {
    "mining": ("products/mines", "Mines"),
    "refining": ("products/refineries", "Refineries"),
    "exploration": ("products/exploration", "Exploration"),
    "geopolitics": ("competitors/world", "World"),
    "group": ("finance/group", "Group"),
    "public": ("finance/stock", "Stock"),
    "lender": ("finance/debt", "Debt"),
    "finance": ("finance", "Finance"),
    "board": ("finance/board", "Board"),
    "deals": ("finance/deals", "Deals"),
    "facility": ("products/infrastructure", "Infrastructure"),
    "research": ("products/research", "Research"),
    "market": ("products/markets", "Markets"),
    "rivals": ("competitors", "Competitors"),
    "operations": ("products", "Products"),
    "personnel": ("people", "People"),
    "executive": ("org", "Org"),
    "founder": ("overview", "Overview"),
    "personal": ("overview", "Overview"),
    "press": ("overview", "Overview"),
    "crisis": ("overview", "Overview"),
}


def _mines(state: GameState, event: GameEvent, data: LoadedData) -> list[tuple[int, str]]:
    """The mines whose open event of this kind was shown in the event's month (as the engine's
    answer finds them, tst.sim.mining.risk)."""
    t, template = event.turn, event.template_id or ""
    out = []
    for m in sorted(state.mines, key=lambda m: m.id):
        if template == "mine_takeover":
            hit = m.takeover_turn == t
        elif template == "mine_price_crash":
            hit = m.crash_turn == t
        elif template == "mine_protest":
            hit = m.protest_turn == t
        else:
            hit = template.startswith("mine_") and m.accident_turn == t
        if hit and m.company_id in _group(state):
            out.append((m.id, mine_name(m, data.game_data)))
    return out


def _group(state: GameState) -> set[int]:
    root = listed_id(state)
    return {root, state.player.id, *(m.company_id for m in group_members(state, root))}


def event_links(state: GameState, event: GameEvent, data: LoadedData) -> list[EventLinkOut]:
    links: list[EventLinkOut] = []
    seen: set[str] = set()

    def add(path: str, label: str) -> None:
        if path not in seen:
            seen.add(path)
            links.append(EventLinkOut(path=path, label=label))

    if event.product_id is not None:
        product = state.product(event.product_id)
        add(f"products/{event.product_id}", product.name if product else "The product")
    if event.category == "mining":
        for mine_id, name in _mines(state, event, data):
            add(f"products/mines?mine={mine_id}", name)
    if event.category == "refining":
        for r in state.refineries:
            if r.incident_turn == event.turn and r.company_id in _group(state):
                add(f"products/refineries?plant={r.facility_id}", "The refinery")
    if event.category == "exploration":
        for p in state.projects:
            if p.protest_turn == event.turn and p.company_id in _group(state):
                add(f"products/exploration?project={p.id}", "The project")
    for pid in event.person_ids[:MAX_PEOPLE]:
        person = state.person(pid)
        add(f"people/{pid}", person_name(person))
    if event.rival_id is not None:
        add(f"competitors/{event.rival_id}", state.company(event.rival_id).name)
    if event.loan_id is not None:
        add("finance/debt", "Debt")
    screen = CATEGORY_SCREENS.get(event.category)
    if screen is not None:
        add(*screen)
    add("finance/statements", "Cash and statements")
    return links
