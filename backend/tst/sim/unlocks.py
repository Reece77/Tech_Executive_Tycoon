"""Progressive unlocking and the Getting started checklist (docs/formulas.md 42.1-42.2; M29).

Pure and read-only: functions of state, balance and data that never change state. Each
screen or system the side navigation can hide has an unlock condition: the company's stage
(spec section 3) or the first fact that makes it relevant. The API shows a screen when its
condition holds now or when it was announced before (an `unlock` inbox item), so a screen
never disappears again. Which stage opens which screen is a UI gate, not a balance number
(M29 decision; recorded in the brief).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from tst.sim.data_models import Balance, GameData
from tst.sim.geopolitics import supply, world
from tst.sim.state import GameState, group_companies, listed_id, player_companies

type NavGroup = Literal[
    "company", "people", "products", "markets", "chain", "finance", "world", "automation"
]

# Company stages (spec section 3) at which a screen opens on its own.
STAGE_SCALEUP = 2  # tunable-exempt: spec stage 2 (seed or $1M ARR)
STAGE_GROWTH = 3  # tunable-exempt: spec stage 3 (Series B or $20M ARR)
STAGE_LISTED = 4  # tunable-exempt: spec stage 4 (listed)
STAGE_GROUP = 5  # tunable-exempt: spec stage 5 (holding company)
FIRST_YEAR_MONTHS = 12  # the checklist's months (42.2)
TWO_BLOCS = 2  # World: the company sells in at least this many blocs (42.1)


@dataclass(frozen=True, slots=True)
class System:
    """A screen or system that unlocks. `id` is stable (stored as the unlock inbox item's
    link id): append new systems, never renumber."""

    id: int
    key: str
    label: str
    group: NavGroup
    always: bool = False


SYSTEMS: tuple[System, ...] = (
    System(1, "inbox", "Inbox", "company", always=True),
    System(2, "overview", "Overview", "company", always=True),
    System(3, "history", "History", "company", always=True),
    System(4, "people", "People", "people", always=True),
    System(5, "recruitment", "Recruitment", "people", always=True),
    System(6, "org", "Org", "people", always=True),
    System(7, "offices", "Offices", "people"),
    System(8, "products", "Products", "products", always=True),
    System(9, "research", "Research", "products"),
    System(10, "infrastructure", "Infrastructure", "products"),
    System(11, "hardware", "Hardware", "products"),
    System(12, "markets", "Markets", "markets", always=True),
    System(13, "competitors", "Competitors", "markets", always=True),
    System(14, "rankings", "Rankings", "markets"),
    System(15, "exploration", "Exploration", "chain"),
    System(16, "mines", "Mines", "chain"),
    System(17, "refineries", "Refineries", "chain"),
    System(18, "fabs", "Fabs", "chain"),
    System(19, "finance", "Finance", "finance", always=True),
    System(20, "group", "Group", "finance"),
    System(21, "world", "World", "world"),
)
BY_KEY: dict[str, System] = {s.key: s for s in SYSTEMS}
BY_ID: dict[int, System] = {s.id: s for s in SYSTEMS}
OPT_IN: frozenset[str] = frozenset({"exploration"})  # the player may open these early (42.1)


def group_ids(state: GameState) -> set[int]:
    """The player's group: the companies the player runs and every company the group owns."""
    ids = {c.id for c in player_companies(state)}
    ids.update(c.id for c in group_companies(state, listed_id(state)))
    return ids


def _stage(state: GameState) -> int:
    return max(c.stage for c in player_companies(state))


def _sells_in_blocs(state: GameState, ids: set[int], data: GameData) -> int:
    if not world.enabled(data):
        return 0
    live = {p.id for p in state.products if p.company_id in ids and p.status in ("live", "sunset")}
    blocs: set[str] = set()
    countries = world.countries_of(data)
    for pr in state.product_regions:
        if pr.product_id in live and pr.live(state.turn):
            for c in countries.of_region(pr.region):
                if c.demand_share > 0:
                    blocs.add(world.bloc_of(data, c.key, state.turn))
    return len(blocs)


def _buys_controlled(state: GameState, ids: set[int], balance: Balance, data: GameData) -> bool:
    if not world.enabled(data) or data.commodities is None:
        return False
    from tst.sim.commodities import costs  # local: costs imports geopolitics

    for cid in sorted(ids):
        for commodity, used in costs.company_use(state, cid, balance, data).items():
            if used > 0 and supply.commodity_rules(state, cid, commodity, balance, data):
                return True
    return False


type Check = Callable[[GameState, set[int], Balance, GameData], str | None]


def _by_stage(stage: int, label: str) -> Check:
    def check(state: GameState, _ids: set[int], _b: Balance, _d: GameData) -> str | None:
        return f"the company reached {label}" if _stage(state) >= stage else None

    return check


def _any(*checks: Check) -> Check:
    def check(state: GameState, ids: set[int], b: Balance, d: GameData) -> str | None:
        for c in checks:
            reason = c(state, ids, b, d)
            if reason is not None:
                return reason
        return None

    return check


def _offices(state: GameState, ids: set[int], _b: Balance, _d: GameData) -> str | None:
    open_offices = [o for o in state.offices if o.company_id in ids and o.status == "open"]
    return "the company has more than one office" if len(open_offices) > 1 else None


def _research(state: GameState, ids: set[int], _b: Balance, _d: GameData) -> str | None:
    if any(p.company_id in ids for p in state.research_projects):
        return "a research project is running"
    return None


def _facility(state: GameState, ids: set[int], _b: Balance, _d: GameData) -> str | None:
    return (
        "the group owns a facility" if any(f.company_id in ids for f in state.facilities) else None
    )


def _units(state: GameState, ids: set[int], _b: Balance, data: GameData) -> str | None:
    for p in state.products:
        if p.company_id in ids and data.category(p.category).sells_units:
            return f"{p.name} is a hardware product"
    return None


def _exploration(state: GameState, ids: set[int], _b: Balance, _d: GameData) -> str | None:
    if any(p.company_id in ids for p in state.projects):
        return "the group holds an exploration licence"
    if any(s.company_id in ids for s in state.desk_studies):
        return "the group ran a desk study"
    return None


def _mines(state: GameState, ids: set[int], _b: Balance, _d: GameData) -> str | None:
    if any(m.company_id in ids for m in state.mines):
        return "the group owns a mine"
    if any(
        p.company_id in ids and (p.level is not None or p.status == "permitted")
        for p in state.projects
    ):
        return "an exploration project has a feasibility study"
    return None


def _refineries(state: GameState, ids: set[int], _b: Balance, _d: GameData) -> str | None:
    if any(r.company_id in ids for r in state.refineries):
        return "the group owns a refinery"
    if any(m.company_id in ids for m in state.mines):
        return "the group owns a mine, whose ore can be refined"
    return None


def _fabs(state: GameState, ids: set[int], _b: Balance, data: GameData) -> str | None:
    if any(f.company_id in ids for f in state.fabs):
        return "the group owns a fab"
    for p in state.products:
        if p.company_id in ids and data.category(p.category).chip_type is not None:
            return f"{p.name} is a chip product"
    return None


def _group(state: GameState, _ids: set[int], _b: Balance, _d: GameData) -> str | None:
    owners = {c.id for c in player_companies(state)}
    if any(o.owner_id in owners and o.to_turn is None for o in state.ownerships):
        return "the company owns a subsidiary"
    return None


def _world(state: GameState, ids: set[int], balance: Balance, data: GameData) -> str | None:
    if _sells_in_blocs(state, ids, data) >= TWO_BLOCS:
        return "your products sell in two blocs"
    if _buys_controlled(state, ids, balance, data):
        return "the group buys an input under export controls"
    return None


CHECKS: dict[str, Check] = {
    "offices": _any(_by_stage(STAGE_SCALEUP, "stage 2"), _offices),
    "research": _any(_by_stage(STAGE_SCALEUP, "stage 2"), _research),
    "rankings": _by_stage(STAGE_SCALEUP, "stage 2"),
    "infrastructure": _any(_by_stage(STAGE_GROWTH, "stage 3"), _facility),
    "hardware": _any(_by_stage(STAGE_GROWTH, "stage 3"), _units),
    "exploration": _exploration,
    "mines": _mines,
    "refineries": _any(_by_stage(STAGE_LISTED, "stage 4"), _refineries),
    "fabs": _any(_by_stage(STAGE_LISTED, "stage 4"), _fabs),
    "group": _any(_by_stage(STAGE_GROUP, "stage 5"), _group),
    "world": _world,
}


def conditions(state: GameState, balance: Balance, data: GameData) -> dict[str, str]:
    """Every system whose unlock condition holds now -> why ("always" for the stage-1
    screens). Read-only."""
    ids = group_ids(state)
    out: dict[str, str] = {}
    for system in SYSTEMS:
        if system.always:
            out[system.key] = "always"
            continue
        reason = CHECKS[system.key](state, ids, balance, data)
        if reason is not None:
            out[system.key] = reason
    return out


def newly_unlocked(
    before: GameState,
    after: GameState,
    announced: frozenset[str],
    balance: Balance,
    data: GameData,
) -> tuple[tuple[System, str], ...]:
    """Systems whose condition holds `after` a turn but did not before it and that were never
    announced: each gets an `unlock` inbox item. A system whose condition already held before
    (a save started before M29) is shown without an item."""
    was = conditions(before, balance, data)
    now = conditions(after, balance, data)
    return tuple(
        (s, now[s.key])
        for s in SYSTEMS
        if not s.always and s.key in now and s.key not in was and s.key not in announced
    )


# --- Getting started (42.2) -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Step:
    key: str
    label: str
    note: str  # the chief of staff's one line on why it matters
    screen: str  # a SYSTEMS key the step links to
    done: bool


STEP_TEXT: tuple[tuple[str, str, str, str], ...] = (
    (
        "hire_engineer",
        "Hire a first engineer",
        "Nothing gets built without builders; one engineer is the difference between an idea "
        "and a product.",
        "recruitment",
    ),
    (
        "product_team",
        "Set a product's team",
        "A product only improves while a team works on it; an unstaffed one starts to rot.",
        "org",
    ),
    (
        "launch_bars",
        "Reach the launch bars",
        "Quality, features and a price in every segment: the bars a product must clear to sell.",
        "products",
    ),
    (
        "launch",
        "Launch a product",
        "Revenue starts the month you launch, and every month of runway counts.",
        "products",
    ),
    (
        "hiring_plan",
        "Open a hiring plan",
        "A plan lets a recruiter hire for you each month, so your own energy goes further.",
        "recruitment",
    ),
    (
        "seed_round",
        "Raise a seed round",
        "A priced seed round buys the runway to grow, and brings a board with it.",
        "finance",
    ),
    (
        "delegate",
        "Give a seat authority or automate an area",
        "Executives with authority decide routine things for you; that is how a founder scales.",
        "org",
    ),
)


def first_year(state: GameState) -> bool:
    """The checklist's months: the player's company's first 12 months (42.2)."""
    return state.turn - state.player.founded_turn < FIRST_YEAR_MONTHS


def _done(state: GameState, key: str, balance: Balance, data: GameData) -> bool:
    from tst.sim.actions.products import launch_problems  # local: actions import widely

    cid = state.player.id
    products = state.company_products(cid)
    if key == "hire_engineer":
        return any(
            e.status == "active"
            and not state.person(e.person_id).is_founder
            and any(r.key == e.role and r.product_function == "builder" for r in data.roles)
            for e in state.staff(cid)
        )
    if key == "product_team":
        return state.player.root_product_id is not None or any(
            u.company_id == cid and u.product_id is not None for u in state.units
        )
    if key == "launch_bars":
        return any(p.launched_turn is not None for p in products) or any(
            p.status == "in_development" and not launch_problems(state, p, balance, data)
            for p in products
        )
    if key == "launch":
        return any(p.launched_turn is not None for p in products)
    if key == "hiring_plan":
        return any(p.company_id == cid for p in state.plans)
    if key == "seed_round":
        return any(r.company_id == cid and r.status == "closed" for r in state.rounds)
    if key == "delegate":
        return any(a.company_id == cid and a.enabled for a in state.authorities)
    raise KeyError(key)


def getting_started(state: GameState, balance: Balance, data: GameData) -> tuple[Step, ...]:
    """The checklist's steps in order, each ticked from state alone (42.2). Read-only."""
    return tuple(
        Step(key, label, note, screen, _done(state, key, balance, data))
        for key, label, note, screen in STEP_TEXT
    )
