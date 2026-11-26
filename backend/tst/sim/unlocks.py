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

from tst.sim.calendar import turn_to_ym
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
    System(3, "history", "History", "company", always=True),  # tunable-exempt: stable id
    System(4, "people", "People", "people", always=True),  # tunable-exempt: stable id
    System(5, "recruitment", "Recruitment", "people", always=True),  # tunable-exempt: stable id
    System(6, "org", "Org", "people", always=True),  # tunable-exempt: stable id
    System(7, "offices", "Offices", "people"),  # tunable-exempt: stable id
    System(8, "products", "Products", "products", always=True),  # tunable-exempt: stable id
    System(9, "research", "Research", "products"),  # tunable-exempt: stable id
    System(10, "infrastructure", "Infrastructure", "products"),  # tunable-exempt: stable id
    System(11, "hardware", "Hardware", "products"),  # tunable-exempt: stable id
    System(12, "markets", "Markets", "markets", always=True),  # tunable-exempt: stable id
    System(13, "competitors", "Competitors", "markets", always=True),  # tunable-exempt: stable id
    System(14, "rankings", "Rankings", "markets"),  # tunable-exempt: stable id
    System(15, "exploration", "Exploration", "chain"),  # tunable-exempt: stable id
    System(16, "mines", "Mines", "chain"),  # tunable-exempt: stable id
    System(17, "refineries", "Refineries", "chain"),  # tunable-exempt: stable id
    System(18, "fabs", "Fabs", "chain"),  # tunable-exempt: stable id
    System(19, "finance", "Finance", "finance", always=True),  # tunable-exempt: stable id
    System(20, "group", "Group", "finance"),  # tunable-exempt: stable id
    System(21, "world", "World", "world"),  # tunable-exempt: stable id
    System(22, "automation", "Automation", "automation"),  # tunable-exempt: stable id (M27a)
    System(23, "platforms", "Platforms", "markets"),  # tunable-exempt: stable id (M31)
    System(24, "family", "Family", "people"),  # tunable-exempt: stable id (M36)
    System(25, "regulation", "Regulation", "world"),  # tunable-exempt: stable id (M34)
    System(26, "equipment", "Equipment", "chain"),  # tunable-exempt: stable id (M33; 25 is M34's)
    System(27, "power", "Power", "chain"),  # tunable-exempt: stable id (M32)
    System(28, "vehicles", "Vehicles", "products"),  # tunable-exempt: stable id (M38)
    System(29, "medical", "Medical", "products"),  # tunable-exempt: stable id (M41; 28 is M38's)
    System(30, "robotics", "Robotics", "products"),  # tunable-exempt: stable id (M39; 29 is M41's)
    System(31, "mobility", "Mobility", "products"),  # tunable-exempt: stable id (M39)
    System(32, "pharma", "Pharma", "products"),  # tunable-exempt: stable id (M42; 31 is M39's)
    System(33, "space", "Space", "products"),  # tunable-exempt: stable id (M40; 32 left for M42)
    System(34, "government", "Government", "markets"),  # tunable-exempt: stable id (M44)
    System(35, "telecom", "Telecom", "products"),  # tunable-exempt: stable id (M53)
    System(36, "finserv", "Financial services", "products"),  # tunable-exempt: stable id (M54)
    System(37, "currency", "Currency", "finance"),  # tunable-exempt: stable id (M54)
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


def _equipment(state: GameState, ids: set[int], _b: Balance, data: GameData) -> str | None:
    """M33 (47): the group owns a fab (its tools come from ASML's queue)."""
    if data.equipment is None:
        return None
    return "the group owns a fab" if any(f.company_id in ids for f in state.fabs) else None


def _power(state: GameState, ids: set[int], b: Balance, _d: GameData) -> str | None:
    """M32 (46): a data centre or fab of the group's (its energy and siting)."""
    for f in state.facilities:
        live = f.company_id in ids and f.status != "closed"
        if live and (f.kind == "fab" or f.kind in b.power.paid_by):
            return "the group runs a data centre or a fab"
    return None


def _vehicles(state: GameState, ids: set[int], b: Balance, d: GameData) -> str | None:
    """M38 (49): the EV era (from vehicles.unlock_year) for a stage-3 company, a car line, or
    the group's own lithium supply (a lithium mine or converter)."""
    if d.vehicles is None:
        return None
    vb = b.vehicles
    if any(p.category == vb.category for p in state.products if p.company_id in ids):
        return "the company makes cars"
    lithium = "lithium_carbonate"
    if any(m.commodity == lithium for m in state.mines if m.company_id in ids and m.is_open):
        return "the group holds lithium supply"
    for r in state.refineries:
        if r.company_id in ids and b.refining.recipes[r.recipe].output_good == lithium:
            return "the group holds lithium supply"
    year = turn_to_ym(state.turn)[0]
    if year >= vb.unlock_year and _stage(state) >= STAGE_GROWTH:
        return f"the EV era opened ({vb.unlock_year}) at stage 3"
    return None


def _robotics(state: GameState, ids: set[int], b: Balance, d: GameData) -> str | None:
    """M39 (53.1-53.2): a robot line, an own assembly or vehicle plant, or the robotics year
    (robotics.unlock_year) for a stage-3 company."""
    if d.robotics is None:
        return None
    rb = b.robotics
    if any(
        p.category in (rb.industrial, rb.humanoid) for p in state.products if p.company_id in ids
    ):
        return "the company makes robots"
    if any(f.kind in rb.automation.plant_kinds for f in state.facilities if f.company_id in ids):
        return "the group runs a plant robots can automate"
    if turn_to_ym(state.turn)[0] >= rb.unlock_year and _stage(state) >= STAGE_GROWTH:
        return f"industrial robots are open to a stage-3 company ({rb.unlock_year})"
    return None


def _government(state: GameState, ids: set[int], b: Balance, d: GameData) -> str | None:
    """M44 (57): a bid or contract of the group, or the government year
    (government.unlock_year) for a stage-3 company with a product in a programme area."""
    if d.government is None:
        return None
    if any(x.company_id in ids for x in state.gov_bids) or any(
        c.company_id in ids for c in state.gov_contracts
    ):
        return "the company bids for government work"
    from tst.sim.government.data import area_of

    if (
        turn_to_ym(state.turn)[0] >= b.government.unlock_year
        and _stage(state) >= STAGE_GROWTH
        and any(p.company_id in ids and area_of(p, d) is not None for p in state.products)
    ):
        return f"governments tender for what the company makes ({b.government.unlock_year})"
    return None


def _mobility(state: GameState, ids: set[int], b: Balance, d: GameData) -> str | None:
    """M39 (53.3): a robotaxi service, or a car line of the group once a region has approved
    driverless (L4) service."""
    if d.robotics is None:
        return None
    if any(p.category == b.robotics.mobility for p in state.products if p.company_id in ids):
        return "the company runs a robotaxi service"
    from tst.sim.vehicles import spec as vs

    cars = any(p.category == b.vehicles.category for p in state.products if p.company_id in ids)
    if cars and any(vs.approved(state, r, "l4", b, d) for r in d.region_keys):
        return "driverless service is approved and the group makes cars"
    return None


def _space(state: GameState, ids: set[int], b: Balance, d: GameData) -> str | None:
    """M40 (56): a launch, broadband or Earth-observation line, a launch site or satellite plant,
    or the space year (space.unlock_year) for a stage-3 company that makes chips or devices."""
    if d.space is None:
        return None
    sb = b.space
    cats = (sb.launch, sb.broadband, sb.eo)
    if any(p.category in cats for p in state.products if p.company_id in ids):
        return "the company has a space line"
    kinds = (sb.site_kind, sb.plant_kind)
    if any(f.kind in kinds for f in state.facilities if f.company_id in ids):
        return "the group runs a launch site or satellite plant"
    if turn_to_ym(state.turn)[0] >= sb.unlock_year and _stage(state) >= STAGE_GROWTH:
        return f"space is open to a stage-3 company ({sb.unlock_year})"
    return None


def _telecom(state: GameState, ids: set[int], b: Balance, d: GameData) -> str | None:
    """M53 (62): a telecom line, a network, a licence or a bid, or the telecom year
    (telecom.unlock_year) for a stage-3 company that makes chips or devices."""
    if d.telecom is None:
        return None
    tb = b.telecom
    if any(p.category in tb.categories for p in state.products if p.company_id in ids):
        return "the company has a telecom line"
    if any(f.kind in tb.kinds for f in state.facilities if f.company_id in ids):
        return "the group runs a network"
    t = state.telecom
    if any(x.company_id in ids for x in t.licences) or any(
        a.bid_company_id in ids for a in t.auctions
    ):
        return "the group holds or bids for spectrum"
    if turn_to_ym(state.turn)[0] >= tb.unlock_year and _stage(state) >= STAGE_GROWTH:
        makes = ("devices", "chips_mobile_soc", "chips_server_cpu", "chips_ai_accelerator")
        if any(p.category in makes for p in state.products if p.company_id in ids):
            return f"telecom is open to a stage-3 device or chip company ({tb.unlock_year})"
    return None


def _finserv(state: GameState, ids: set[int], b: Balance, d: GameData) -> str | None:
    """M54 (64.1-64.3): a banking, payments or insurance line, a bank, a network or an insurer,
    or from finserv.unlock_year a stage-3 company with a fintech line (the Bank, Payments and
    Insurance screens)."""
    if d.finserv is None:
        return None
    fb = b.finserv
    if any(p.category in fb.categories for p in state.products if p.company_id in ids):
        return "the company has a finance line"
    fs = state.finserv
    if (
        any(x.company_id in ids for x in fs.banks)
        or any(x.company_id in ids for x in fs.networks)
        or any(x.company_id in ids for x in fs.insurers)
    ):
        return "the group runs a bank, a network or an insurer"
    if turn_to_ym(state.turn)[0] >= fb.unlock_year and _stage(state) >= STAGE_GROWTH:
        if any(p.category == "fintech" for p in state.products if p.company_id in ids):
            return f"banking is open to a stage-3 fintech ({fb.unlock_year})"
    return None


def _currency(state: GameState, ids: set[int], b: Balance, d: GameData) -> str | None:
    """M54 (64.4): forwards or a hedging programme, or foreign revenue of at least
    fx.unlock_share of the company's (the Currency screen)."""
    if d.fx is None:
        return None
    if any(h.company_id in ids for h in state.fx.hedges) or any(
        p.company_id in ids for p in state.fx.programmes
    ):
        return "the group hedges its currencies"
    from tst.sim.fx.cfo import foreign_share

    if any(foreign_share(state, c) >= b.fx.unlock_share for c in ids):
        return f"{b.fx.unlock_share:.0%} of revenue is earned abroad"
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


def _automation(state: GameState, _ids: set[int], balance: Balance, _d: GameData) -> str | None:
    """M27a (40.1): someone could run an area, or one already does."""
    from tst.sim.automation import owners

    cid = state.player.id
    if state.owners_of(cid):
        return "someone runs an area for you"
    for area in owners.area_keys(balance):
        if owners.eligible_people(state, cid, area, balance):
            return "someone on your team could run an area for you"
    return None


def _family(state: GameState, _ids: set[int], _b: Balance, _d: GameData) -> str | None:
    """M36 (45.1): a family exists (never with Family set to none)."""
    return "you have a family" if state.family is not None else None


def _platforms(state: GameState, ids: set[int], b: Balance, _d: GameData) -> str | None:
    """M31 (44): a device line (from development) or a live app sold through stores."""
    for p in state.products:
        if p.company_id not in ids or p.status == "retired":
            continue
        if p.category in ("devices", "os"):
            return f"{p.name} runs on a platform"
        if p.category in b.platforms.app_categories and p.status in ("live", "sunset"):
            return f"{p.name} is sold through app stores"
    return None


def _regulation(state: GameState, ids: set[int], _b: Balance, _d: GameData) -> str | None:
    """M34 (48): the first designation warning, investigation or duty of the group."""
    if any(w.company_id in ids for w in state.designation_warnings):
        return "a regulator has warned of a designation"
    if any(c.company_id in ids for c in state.reg_cases):
        return "a regulator has opened an investigation"
    if any(d.company_id in ids for d in state.duties):
        return "a regulator has given the company duties"
    return None


def _medical(state: GameState, ids: set[int], _b: Balance, data: GameData) -> str | None:
    """M41 (50): a medical device of the group's, or a device, chip or AI product at stage 3."""
    for p in state.products:
        if p.company_id in ids and p.status != "retired" and data.category(p.category).medical:
            return f"{p.name} is a medical device"
    if _stage(state) < STAGE_GROWTH:
        return None
    for p in state.products:
        if p.company_id not in ids or p.status == "retired":
            continue
        cat = data.category(p.category)
        if p.category in ("devices", "ai_models") or cat.chip_type is not None:
            return f"{p.name} can become a medical device, and the company reached stage 3"
    return None


def _pharma(state: GameState, ids: set[int], _b: Balance, data: GameData) -> str | None:
    """M42 (55): a programme, deal or plant of the group's, or an AI or medical product at
    stage 3 (AI discovery and a health business lead to drugs)."""
    for programme in state.pharma_programmes:
        if programme.company_id in ids:
            return f"{programme.name} is a drug programme"
    if any(d.company_id in ids for d in state.pharma_deals):
        return "the company has a pharmaceutical deal"
    if _stage(state) < STAGE_GROWTH:
        return None
    for product in state.products:
        if product.company_id not in ids or product.status == "retired":
            continue
        if product.category == "ai_models" or data.category(product.category).medical:
            return f"{product.name} can lead to drug discovery, and the company reached stage 3"
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
    "automation": _any(_by_stage(STAGE_GROWTH, "stage 3"), _automation),
    "family": _family,  # M36
    "equipment": _equipment,  # M33
    "platforms": _any(_by_stage(STAGE_GROWTH, "stage 3"), _platforms),  # M31
    "power": _any(_by_stage(STAGE_LISTED, "stage 4"), _power),  # M32 (46)
    "regulation": _regulation,  # M34
    "vehicles": _vehicles,  # M38 (49)
    "medical": _medical,  # M41 (50)
    "robotics": _robotics,  # M39 (53.1-53.2)
    "pharma": _pharma,  # M42 (55)
    "mobility": _mobility,  # M39 (53.3)
    "space": _space,  # M40 (56)
    "government": _government,  # M44 (57)
    "telecom": _telecom,  # M53 (62)
    "finserv": _finserv,  # M54 (64.1-64.3)
    "currency": _currency,  # M54 (64.4)
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
