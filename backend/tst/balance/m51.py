"""M51's balance runs (docs/formulas.md 63.4): every new scenario played by a sensible and a
passive script on seeds 1-10 (target 1), and the challenge rules' effect on the scripted
player's company score (target 2). Target 3 is the M30 state cache, unchanged.

Each start is built as `create_save` builds it (`new_game` in the world's first year, then
`start_mode`), held in memory as a `Game`."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Final

from tst.balance.game import PLAYER, Game
from tst.balance.known_misses import KNOWN_MISSES
from tst.balance.strategies import (
    accept_bridges,
    fundraise,
    go_public,
    headcount,
    hire,
    last_revenue,
    launch_ready,
    runway,
    set_marketing,
    steady,
)
from tst.balance.strategies_v2 import refill_energy, regions_step, staff_unit
from tst.balance.strategies_v3 import (
    RENEW_BEFORE,
    _staff_plants,
    sign_foundry_contracts,
)
from tst.loader import LoadedData
from tst.sim.actions import (
    AssignUnit,
    CloseSearch,
    CreateProduct,
    Interview,
    MakeOffer,
    OpenSearch,
    SetPrice,
)
from tst.sim.actions.hardware import SignManufacturingContract
from tst.sim.actions.research import StartProject
from tst.sim.errors import SimError
from tst.sim.family.config import READINESS
from tst.sim.ledger import apply_entries
from tst.sim.modes import scenarios as sc
from tst.sim.modes.world import start_mode
from tst.sim.platforms.actions import SetDevicePlatform
from tst.sim.products.models import Product
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game

NEW: Final = (
    "the_crash",
    "failing_chipmaker",
    "ev_maker",
    "under_controls",
    "platform_war",
    "the_dynasty",
)
SEEDS: Final = tuple(range(1, 11))
WIN_BAND: Final = (3, 8)  # 63.4 target 1: the sensible script's wins of 10
PASSIVE_MAX: Final = 2  # ... and the passive one's at most

log = logging.getLogger(__name__)

type Script = Callable[[Game], None]


def start_scenario(loaded: LoadedData, key: str, seed: int) -> Game:
    """The scenario's start as a new save has it, in memory."""
    data = loaded.game_data
    h = sc.scenario(data, key)
    background = data.scenario(h.background)
    assert background is not None
    founder = sc.founder_spec(h, DEFAULT_FOUNDER)
    state, entries = new_game(
        save_name="balance",
        master_seed=seed,
        scenario=background,
        difficulty="standard",
        company_name="Balance Co",
        founder=founder,
        balance=loaded.balance,
        data=data,
        start_year=sc.world_year(h),
        hq_city=h.hq_city,
        family=sc.family_spec(h),
    )
    spec = sc.scenario_spec(key, data)
    state, opening = start_mode(
        state, entries, spec, founder, RngFactory(seed), loaded.balance, data
    )
    game = Game(loaded, state, dict(apply_entries({}, opening)))
    game.record_value()
    return game


@dataclass(frozen=True, slots=True)
class Run:
    key: str
    seed: int
    script: str
    result: str | None  # success | failure (None: the run stopped before a verdict)
    result_turn: int | None
    score: int | None  # the company score at the verdict
    note: str = ""  # the goal's measure at the end


def play(game: Game, script: Script, key: str, seed: int, name: str) -> Run:
    """Play the scenario month by month until its verdict."""
    while game.state.mode is not None and game.state.mode.result is None and not game.state.ended:
        script(game)
        game.turn()
    mode = game.state.mode
    score = next(
        (s.score for s in reversed(game.state.scores) if s.company_id == game.state.player.id),
        None,
    )
    return Run(
        key,
        seed,
        name,
        mode.result if mode is not None else None,
        mode.result_turn if mode is not None else None,
        score,
    )


# --- The scripts -----------------------------------------------------------------------------


def passive(game: Game) -> None:
    """The passive player: keeps what the scenario gave and does nothing."""


def crash_sensible(game: Game) -> None:
    """The crash: v1's steady script (the next round is the Series A, the seed being closed),
    holding hiring until runway allows."""
    steady(game)


def _own(game: Game, category: str) -> Product | None:
    return next(
        (
            p
            for p in game.state.company_products(PLAYER)
            if p.category == category and p.status != "retired"
        ),
        None,
    )


def renew_contract(game: Game, product: Product, units_floor: int) -> None:
    """A new 24-month assembly contract when none runs (or the last ends within two months),
    sized to last month's units with headroom."""
    contracts = [
        c
        for c in game.state.production_contracts
        if c.product_id == product.id and c.kind == "assembly" and c.end_turn >= game.state.turn
    ]
    last = max((c.end_turn for c in contracts), default=game.state.turn - 1)
    if last - game.state.turn >= RENEW_BEFORE:
        return
    sold = sum(
        r.customers
        * (
            game.loaded.game_data.category(product.category).market(r.segment).units_per_customer
            or 1
        )
        for r in game.last_product_months
        if r.product_id == product.id
    )
    units = min(
        game.loaded.balance.hardware.contract.max_units, max(units_floor, round(sold * 1.2))
    )
    refill_energy(game)
    game.act(
        SignManufacturingContract(game.founder_id, product.id, "foxconn", "shenzhen", units, 24)
    )


OS_TEAM: Final = 6  # software engineers building the OS
PHONE_TEAM: Final = 16  # hardware engineers keeping the phone current (root team)
PHONE_MARKETING: Final = 2_000_000_00  # $2M a month
PW_ROUNDS: Final = {"a": 2_000_000_000, "b": 5_000_000_000, "c": 10_000_000_000}


def platform_sensible(game: Game) -> None:
    """The platform war: the phone kept current (16 engineers, $2M a month of marketing,
    contracts renewed), an OS team of 6 from the first month, the phone moved onto the OS
    once it launches; rounds raised when allowed."""
    accept_bridges(game)
    fundraise(game, PW_ROUNDS, pick="pre")
    phone = _own(game, "devices")
    if phone is not None:
        keep = frozenset(v for k, v in game.notes.items() if k.startswith("search:"))
        hire(game, PHONE_TEAM + 7, per_month=2, order=("hardware_engineer",), keep=keep)
        renew_contract(game, phone, 20_000)
        set_marketing(game, PHONE_MARKETING)
        regions_step(game)
    os_product = _own(game, "os")
    if os_product is None:
        uid = staff_unit(game, "OS team", "software_engineer", OS_TEAM)
        if uid is not None:
            pid = game.state.next_ids.product
            refill_energy(game)
            if game.act(CreateProduct(game.founder_id, "Kestrel OS", "os", ())):
                game.act(AssignUnit(game.founder_id, pid, uid))
        return
    staff_unit(game, "OS team", "software_engineer", OS_TEAM)
    launch_ready(game)
    platform = next((p for p in game.state.platforms if p.product_id == os_product.id), None)
    if platform is None or phone is None:
        return
    run = game.state.device_run(phone.id)
    if run is None or run.platform_id != platform.id:
        refill_energy(game)
        game.act(SetDevicePlatform(game.founder_id, phone.id, platform.id))


SENIOR: Final = ("senior", "staff")
OFFER: Final = 1.05  # x the candidate's ask, as v1's scripts


def hire_senior(game: Game, wanted: int, per_month: int, order: tuple[str, ...]) -> None:
    """Toward `wanted` employees, senior and staff hires only, through a recruiter search per
    role in `order` (cycled): candidates interviewed while energy lasts, offered 1.05x."""
    state = game.state
    count = headcount(game)
    roles = list(dict.fromkeys(order[(count + i) % len(order)] for i in range(per_month)))
    open_ids = {}
    for role in dict.fromkeys(order):
        key = f"rsearch:{role}"
        search = next((x for x in state.searches if x.id == game.notes.get(key)), None)
        live = search is not None and search.status == "open"
        if count >= wanted or role not in roles:
            if live:
                game.act(CloseSearch(game.founder_id, search.id))  # type: ignore[union-attr]
            continue
        if not live:
            sid = game.state.next_ids.search
            if not game.act(OpenSearch(game.founder_id, role, "recruiter")):
                continue
            game.notes[key] = sid
        open_ids[game.notes[key]] = role
    made = 0
    for candidate in list(game.state.open_candidates(PLAYER)):
        if count + made >= wanted or made >= per_month:
            break
        person = game.state.person(candidate.person_id)
        if (
            candidate.search_id not in open_ids
            or person.level not in SENIOR
            or person.salary_expectation_cents is None
            or game.state.pending_offer_for(person.id) is not None
        ):
            continue
        if candidate.interviewed_turn is None:
            if game.energy() < game.loaded.balance.founder.energy_cost["interview"]:
                break
            if not game.act(Interview(game.founder_id, person.id)):
                continue
        salary = round(person.salary_expectation_cents * OFFER)
        if game.act(MakeOffer(game.founder_id, person.id, salary, 0)):
            made += 1


CAR_TEAM: Final = 100  # the root team building and improving the car
CAR_ORDER: Final = (
    "hardware_engineer",
    "manufacturing_engineer",
    "software_engineer",
    "hardware_engineer",
    "designer",
)
CAR_RUNWAY: Final = 18  # hire while projected runway is above this (or profitable)
CAR_MARKETING: Final = 1_000_000_000  # $10M a month once live
CAR_PRICE: Final = 3_500_000  # $35,000: the consumer reference price
CAR_UNITS: Final = 2_000  # the first assembly contract's cars a month
CAR_ROUNDS: Final = {
    "c": 50_000_000_000,
    "d": 100_000_000_000,
}  # $500M and $1B, largest amount


def ev_sensible(game: Game) -> None:
    """The EV maker: the prototype's team grown to 100 senior and staff hires (a recruiter
    search per role) while runway allows, priced at the $35,000 reference,
    an assembly contract signed before launch and renewed to last month's cars, $10M a month of
    marketing once live, a region launch whenever the CRO's best candidate allows (at most one
    a year), every round raised when allowed (largest amount) and the IPO when eligible."""
    accept_bridges(game)
    fundraise(game, CAR_ROUNDS, pick="amount")
    go_public(game)
    car = _own(game, "vehicles")
    if car is None:
        return
    months = runway(game)
    wanted = headcount(game) + 1 if months is None or months > CAR_RUNWAY else headcount(game)
    hire_senior(game, min(CAR_TEAM, wanted), per_month=3, order=CAR_ORDER)
    seg = game.state.product_segment(car.id, "consumer")
    if seg is not None and seg.price_cents != CAR_PRICE:
        game.act(SetPrice(game.founder_id, car.id, "consumer", CAR_PRICE))
    renew_contract(game, car, CAR_UNITS)
    launch_ready(game)
    if car.status == "live":
        set_marketing(game, CAR_MARKETING)
        regions_step(game)
        reprice_abroad(game, car)
        hedge_abroad(game)


# M54 (PM ruling 2026-11-26, M54 decision 22): a sensible exporter does not hold one dollar price
# in every region while currencies move. Each January it reprices each foreign region back to the
# region's $35,000 reference at that month's rate, by at most 10% a year, and it runs a 50%
# rolling hedge 12 months ahead (the scenario has no CFO, so the programme is the founder's at the
# CFO's term).
REPRICE_MONTH: Final = 1  # January
REPRICE_CAP: Final = 0.10  # a year's reprice is at most +/- 10%
HEDGE_SHARE: Final = 0.5
HEDGE_TERM: Final = 12


def reprice_abroad(game: Game, car: Product) -> None:
    from tst.sim.actions.geo import SetRegionalPrice
    from tst.sim.calendar import turn_to_ym
    from tst.sim.facilities.compute import home_region_of
    from tst.sim.fx import rates
    from tst.sim.fx.translate import translated
    from tst.sim.geo.formulas import regional_price_cents

    s = game.state
    if turn_to_ym(s.turn)[1] != REPRICE_MONTH:
        return
    b, d = game.loaded.balance, game.loaded.game_data
    home = home_region_of(s, b, d)
    marks = {(m.product_id, m.region, m.segment): m for m in s.fx.marks}
    for rs in s.regional_segments_of(car.id):
        mark = marks.get((car.id, rs.region, rs.segment))
        if rs.price_cents is None or mark is None or mark.price_cents != rs.price_cents:
            continue
        now = rates.index_at(s, rs.region, s.turn, b, d)
        worth = translated(rs.price_cents, now, rates.index_at(s, rs.region, mark.turn, b, d))
        target = regional_price_cents(CAR_PRICE, rs.region, home, d, category=car.category)
        factor = min(1 + REPRICE_CAP, max(1 - REPRICE_CAP, target / worth))
        price = max(1, round(worth * factor))
        if price != rs.price_cents:
            game.act(SetRegionalPrice(game.founder_id, car.id, rs.region, rs.segment, price))


def hedge_abroad(game: Game) -> None:
    from tst.sim.fx.actions import SetHedgeProgramme

    s = game.state
    if s.fx.programme(PLAYER) is None and s.regional_segments_of(_car_id(game)):
        game.act(SetHedgeProgramme(game.founder_id, HEDGE_SHARE, HEDGE_TERM))


def _car_id(game: Game) -> int:
    car = _own(game, "vehicles")
    return car.id if car is not None else -1


FAB_REGION: Final = ("east_asia", "taiwan")  # where the scripts build (as m21's EUV fabs)
FAB_SIZE: Final = 10_000  # wafer starts a month, a new fab
FAB_CASH: Final = 1.0  # cash for the estimate and every build's capex still owed
FAB_SETTLE: Final = 24  # months a fab runs before it is converted to the next node


def _fab_cash_ok(game: Game, cents: int) -> bool:
    """Cash for this share of the new estimate and of the capex still owed on builds."""
    owed = sum(
        f.capex_cents - f.capex_paid_cents
        for f in game.state.facilities
        if f.company_id == PLAYER and f.status == "building"
    )
    owed += sum(
        f.upgrade_cents - f.upgrade_paid_cents for f in game.state.fabs if f.company_id == PLAYER
    )
    return game.cash >= (cents + owed) * FAB_CASH


def fab_step(game: Game, region: tuple[str, str | None] = FAB_REGION, duv: bool = False) -> None:
    """A new fab whenever a node newer than every fab the group has (built or building) is
    orderable and the process level and cash allow it; with nothing building or converting, the
    newest fab that has run FAB_SETTLE months converted to the next node, cash allowing."""
    from tst.sim.fabs import actions as fa
    from tst.sim.fabs import market as fm

    b, d = game.loaded.balance, game.loaded.game_data
    state, turn = game.state, game.state.turn
    mine = [f for f in state.fabs if f.company_id == PLAYER]
    tl = fm.timeline(state, b, d)
    best = max((tl.generation(f.node) for f in mine), default=-1)
    where, country = region
    routes = {n.key for n in fm.nodes_file(d).nodes if n.duv_route}
    for node in reversed(tl.keys):
        if tl.generation(node) <= best:
            break
        if not fm.orderable(state, node, b, d):
            continue
        by_duv = duv and node in routes
        try:
            q = fa.quote(state, PLAYER, node, where, FAB_SIZE, b, d, duv=by_duv, country=country)
        except SimError:
            continue
        if q.allowed and _fab_cash_ok(game, q.capex_cents):
            refill_energy(game)
            build = fa.BuildFab(game.founder_id, node, where, FAB_SIZE, duv=by_duv, country=country)
            if game.act(build):
                return
    if any(f.upgrading(turn) or f.upgrade_node is not None for f in mine) or any(
        (fac := state.facility(f.facility_id)) is not None and fac.status == "building"
        for f in mine
    ):
        return
    newest = max(mine, key=lambda f: tl.generation(f.node), default=None)
    if newest is None or turn - newest.live_turn < FAB_SETTLE:
        return
    try:
        uq = fa.upgrade_quote(state, PLAYER, newest.facility_id, b, d)
    except SimError:
        return
    if uq.new is not None and uq.allowed and _fab_cash_ok(game, uq.capex_cents):
        refill_energy(game)
        game.act(fa.UpgradeFab(game.founder_id, newest.facility_id))


CHIP_PROCESS_TEAM: Final = 20  # researchers
PROCESS_ROLE: Final = "manufacturing_engineer"  # a builder role (21.10) with manufacturing skill
FAB_ROUNDS: Final = {
    "a": 50_000_000_000,
    "b": 100_000_000_000,
    "c": 200_000_000_000,
    "d": 300_000_000_000,
}  # $500M to $3B, largest amount


def process_research(game: Game, size: int) -> None:
    """v3's process research unit at `size` people, kept on the process domain."""
    domain = game.loaded.balance.refining.domain
    uid = staff_unit(game, "Process research", PROCESS_ROLE, size)
    if uid is None:
        return
    active = [
        p for p in game.state.research_projects if p.company_id == PLAYER and p.status == "active"
    ]
    staffed = any(e.unit_id == uid for e in game.state.staff(PLAYER))
    if staffed and not any(p.unit_id == uid for p in active):
        game.act(StartProject(game.founder_id, uid, domain))


def chip_sensible(game: Game) -> None:
    """The failing chipmaker: a round whenever allowed ($500M to $3B) and the IPO when
    eligible, a process research unit of 12, every fab staffed, its starts under
    foundry contracts (v3's foundry steps), and fab_step's new fabs and conversions."""
    accept_bridges(game)
    fundraise(game, FAB_ROUNDS, pick="amount")
    go_public(game)
    process_research(game, CHIP_PROCESS_TEAM)
    _staff_plants(game, "fab", "fab_engineer", "Fab crew")
    sign_foundry_contracts(game)
    fab_step(game)


CHINA: Final = ("east_asia", "china")
TARGET_NODE: Final = "n7"


def build_target(game: Game, node: str, region: tuple[str, str]) -> None:
    """One fab at `node` (by DUV where it has the route), saved for rather than any cheaper
    node; an export licence requested when the controls ask for one (51.x's tool licences)."""
    from tst.sim.fabs import actions as fa
    from tst.sim.fabs import market as fm
    from tst.sim.geopolitics.fabs import RequestToolLicence, check_order

    b, d = game.loaded.balance, game.loaded.game_data
    state = game.state
    tl = fm.timeline(state, b, d)
    if any(
        f.company_id == PLAYER and tl.generation(f.node) >= tl.generation(node) for f in state.fabs
    ):
        return
    if not fm.orderable(state, node, b, d):
        return
    where, country = region
    duv = node in {n.key for n in fm.nodes_file(d).nodes if n.duv_route}
    try:
        check_order(state, PLAYER, country, node, duv, b, d)
    except SimError as exc:
        if "export licence" in exc.message and not any(
            x.company_id == PLAYER and x.status == "pending" for x in state.licences
        ):
            refill_energy(game)
            game.act(RequestToolLicence(game.founder_id, country))
        return
    try:
        q = fa.quote(state, PLAYER, node, where, FAB_SIZE, b, d, duv=duv, country=country)
    except SimError:
        return
    if q.allowed and _fab_cash_ok(game, q.capex_cents):
        refill_energy(game)
        game.act(fa.BuildFab(game.founder_id, node, where, FAB_SIZE, duv=duv, country=country))


def controls_sensible(game: Game) -> None:
    """Under controls: chip_sensible's research, staffing and foundry contracts, saving for a
    7 nm fab in China by the DUV route (EUV tools do not ship there: equipment.yaml
    nl_euv_2019), with an export licence requested when the controls ask for one."""
    accept_bridges(game)
    process_research(game, CHIP_PROCESS_TEAM)
    _staff_plants(game, "fab", "fab_engineer", "Fab crew")
    sign_foundry_contracts(game)
    build_target(game, TARGET_NODE, CHINA)


HEIR_LEVEL: Final = "senior"  # the level a child is offered
HEIR_READY: Final = "ready"  # hand over once the readiest heir is at least this ready ...
HAND_OVER_AGE: Final = 72  # ... or from this age with any eligible heir at least developing
FAMILY_TIME: Final = 10  # energy a month for the family (45.2: closeness holds)


def _start_staff(game: Game) -> int:
    return int(game.notes.setdefault("start_staff", headcount(game)))


def dynasty_sensible(game: Game) -> None:
    """The dynasty: the company run as it is (staff kept at the start's number, marketing 20%
    of revenue, no outside money, so the family keeps control), some family time every month,
    each adult child offered a senior job in a role their interests match, the readiest one
    mentored, and the succession named once that heir is ready (or from 72, at least
    developing)."""
    from tst.sim.actions.family import NameSuccessor, OfferFamilyJob, SetFamilyTime, SetMentoring
    from tst.sim.family import rules

    b, d = game.loaded.balance, game.loaded.game_data
    hire(game, _start_staff(game), per_month=2)
    set_marketing(game, round(0.2 * last_revenue(game)))
    family = game.state.family
    if family is None or family.head_id != game.founder_id:
        return  # handed over: the heir runs it as it is
    if family.family_time != FAMILY_TIME:
        game.act(SetFamilyTime(game.founder_id, FAMILY_TIME))
    for member in rules.children(game.state):
        person = game.state.person(member.person_id)
        if (
            person.age(game.state.turn) < b.family.join_age
            or game.state.employment_of(person.id) is not None
            or member.own_way is not None
        ):
            continue
        role = next((r.key for r in d.roles if rules.roles_match(person, r.key, d)), None)
        if role is not None and game.state.turn % 12 == 0:
            refill_energy(game)
            game.act(OfferFamilyJob(game.founder_id, person.id, PLAYER, role, HEIR_LEVEL))
    heirs = rules.eligible_heirs(game.state, b, "not_ready")
    if not heirs:
        return
    heir = heirs[0]
    member = next(m for m in game.state.family_members if m.person_id == heir)
    if not member.mentored:
        refill_energy(game)
        game.act(SetMentoring(game.founder_id, heir, True))
    band = rules.readiness(game.state, member, b)
    age = game.state.person(game.founder_id).age(game.state.turn)
    bands = READINESS
    if bands.index(band) >= bands.index(HEIR_READY) or (
        age >= HAND_OVER_AGE and bands.index(band) >= bands.index("developing")
    ):
        refill_energy(game)
        game.act(NameSuccessor(game.founder_id, heir_id=heir))


def rated_steady(game: Game) -> None:
    """The five M15b scenarios' rating script (63.3's difficulty only; target 1 is the six new
    ones'): v1's steady, the generic sensible player."""
    steady(game)


FIVE: Final = ("ai_lab", "mobile_first", "survive_2022", "chip_startup", "turnaround")

SCRIPTS: Final[dict[str, dict[str, Script]]] = {
    **{key: {"sensible": rated_steady, "passive": passive} for key in FIVE},
    "the_crash": {"sensible": crash_sensible, "passive": passive},
    "ev_maker": {"sensible": ev_sensible, "passive": passive},
    "failing_chipmaker": {"sensible": chip_sensible, "passive": passive},
    "under_controls": {"sensible": controls_sensible, "passive": passive},
    "the_dynasty": {"sensible": dynasty_sensible, "passive": passive},
    "platform_war": {"sensible": platform_sensible, "passive": passive},
}


def progress(game: Game, key: str) -> str:
    """A short reading of the goal's measure, for the printed table."""
    if key in ("failing_chipmaker", "under_controls"):
        from tst.sim.fabs import market as fm
        from tst.sim.modes.scenarios import best_node_gap

        b, d = game.loaded.balance, game.loaded.game_data
        nodes = sorted({f.node for f in game.state.fabs if f.company_id == PLAYER})
        gap = best_node_gap(game.state, PLAYER, b, d)
        lead = fm.timeline(game.state, b, d).leading(game.state.turn)
        return f"gap {gap} (leader {lead}) fabs {','.join(nodes)}"
    if key == "the_dynasty":
        from tst.sim.family import rules

        f = game.state.family
        if f is None:
            return "no family"
        kids = [
            (
                game.state.person(m.person_id).age(game.state.turn),
                rules.readiness(game.state, m, game.loaded.balance),
                m.company_id is not None,
            )
            for m in rules.children(game.state)
        ]
        head = game.state.person(f.head_id)
        handed = f.generations[1].from_turn if len(f.generations) > 1 else None
        return (
            f"handed {handed} head {head.age(game.state.turn)} {f.head_mode} "
            f"gens {len(f.generations)} "
            f"bp {rules.family_bp(game.state)} kids {kids}"
        )
    if key == "ev_maker":
        from tst.sim.modes.scenarios import cars_a_year

        car = _own(game, "vehicles")
        return f"cars/yr {cars_a_year(game.state, PLAYER):,} {car.status if car else '-'}"
    if key == "platform_war":
        phone = _own(game, "devices")
        cust = sum(s.customers for s in game.state.segments_of(phone.id)) if phone else 0
        best = max(
            (
                (r.dev_share, r.region)
                for r in game.state.platform_regions
                if (p := game.state.platform(r.platform_id)) is not None and p.owner_id == PLAYER
            ),
            default=(0.0, "-"),
        )
        return f"devs {best[0]:.3f} in {best[1]} phone {cust:,.0f}"
    return ""


def run_one(loaded: LoadedData, key: str, seed: int, script: str) -> Run:
    game = start_scenario(loaded, key, seed)
    run = play(game, SCRIPTS[key][script], key, seed, script)
    log.info("%s %s seed %d: %s (%s)", key, script, seed, run.result, progress(game, key))
    return replace(run, note=progress(game, key))


def _worker(job: tuple[str, int, str]) -> Run:
    from tst.config import get_settings
    from tst.loader import load_all

    global _LOADED
    if _LOADED is None:
        _LOADED = load_all(get_settings().data_dir)
    return run_one(_LOADED, *job)


_LOADED: LoadedData | None = None


def run_table(
    keys: tuple[str, ...] = NEW,
    seeds: tuple[int, ...] = SEEDS,
    scripts: tuple[str, ...] = ("sensible", "passive"),
    workers: int = 4,
) -> list[Run]:
    """Every (scenario, seed, script) run, in `workers` processes."""
    from multiprocessing import get_context

    jobs = [(k, s, sc_) for k in keys for sc_ in scripts for s in seeds]
    with get_context("spawn").Pool(workers) as pool:
        return list(pool.imap(_worker, jobs))


def target_1(runs: list[Run]) -> list[tuple[str, int, int, bool]]:
    """(scenario, sensible wins, passive wins, in band) per scenario: 3-8 and at most 2."""
    out = []
    for key in dict.fromkeys(r.key for r in runs):
        won = sum(
            1 for r in runs if r.key == key and r.script == "sensible" and r.result == "success"
        )
        idle = sum(
            1 for r in runs if r.key == key and r.script == "passive" and r.result == "success"
        )
        out.append((key, won, idle, WIN_BAND[0] <= won <= WIN_BAND[1] and idle <= PASSIVE_MAX))
    return out


# --- Target 2: challenges are real ------------------------------------------------------------

TARGET2_MONTHS: Final = 60  # to December 2014 (M51 decision 9: the score saturates by year 10)
TARGET2_DROP: Final = 0.10  # each rule lowers the median score by at least this share
# the scripted player whose plan each rule cuts into (strategies_v2, 30.6)
TARGET2_ARMS: Final[dict[str, str]] = {
    "bootstrapped": "steady_regions",
    "hardware_only": "steady_regions",
    "no_acquisitions": "acquirer",
    "one_region": "steady_regions",
    "hard_rivals": "steady_regions",
    "no_automation": "ceo",
}


def challenge_score(
    loaded: LoadedData, strategy: str, rule: str | None, seed: int, months: int = TARGET2_MONTHS
) -> int:
    """The company score in December 2019 of a 2010 campaign played by `strategy`, under
    `rule` (None: no challenge, the normal game)."""
    from tst.balance.game import start_game
    from tst.balance.strategies_v2 import STRATEGIES
    from tst.sim.modes.models import GameMode

    game = start_game(loaded, seed)
    if rule is not None:
        game.state = replace(game.state, mode=GameMode(kind="campaign", challenges=(rule,)))
    script = STRATEGIES[strategy]
    for _ in range(months):
        if game.state.ended:
            break
        script(game)
        game.turn()
    snap = next((s for s in reversed(game.state.scores) if s.company_id == PLAYER), None)
    return snap.score if snap is not None else 0


def _score_worker(job: tuple[str, str | None, int, int]) -> tuple[str, str | None, int, int]:
    from tst.config import get_settings
    from tst.loader import load_all

    global _LOADED
    if _LOADED is None:
        _LOADED = load_all(get_settings().data_dir)
    strategy, rule, seed, months = job
    return strategy, rule, seed, challenge_score(_LOADED, strategy, rule, seed, months)


def target_2(
    seeds: tuple[int, ...] = SEEDS, workers: int = 4, months: int = TARGET2_MONTHS
) -> list[tuple[str, float, float, float]]:
    """(rule, median score without, with, drop) per rule (63.4 target 2)."""
    from multiprocessing import get_context
    from statistics import median

    arms = sorted(set(TARGET2_ARMS.values()))
    jobs: list[tuple[str, str | None, int, int]] = [
        (a, None, s, months) for a in arms for s in seeds
    ]
    jobs += [(TARGET2_ARMS[r], r, s, months) for r in TARGET2_ARMS for s in seeds]
    with get_context("spawn").Pool(workers) as pool:
        out = list(pool.imap(_score_worker, jobs))
    rows = []
    for rule, arm in TARGET2_ARMS.items():
        base = median(x[3] for x in out if x[0] == arm and x[1] is None)
        hit = median(x[3] for x in out if x[0] == arm and x[1] == rule)
        rows.append((rule, float(base), float(hit), 1 - hit / base if base else 0.0))
    return rows


# Reece's decision (2026-11-25, M51 decision 9): these rules stand as 63.2 defines them though
# the scripted players' score does not show them; target 2 is printed and carried for them.
# M57r-B (review 10 item 36): the carried rules are known misses, bounded and owned there.
TARGET2_CARRIED: Final = frozenset(
    k.target.removeprefix("M51.T2.") for k in KNOWN_MISSES if k.target.startswith("M51.T2.")
)


def report(runs: list[Run], rows: list[tuple[str, float, float, float]]) -> str:
    """63.4's targets 1 and 2 as a table (target 3 is the M30 state cache)."""
    lines = ["63.4 target 1: sensible wins 3-8 of 10, passive at most 2", ""]
    lines.append("| Scenario | Sensible | Passive | |")
    lines.append("| --- | --- | --- | --- |")
    for key, won, idle, ok in target_1([r for r in runs if r.key in NEW]):
        lines.append(f"| {key} | {won}/10 | {idle}/10 | {'ok' if ok else 'MISS'} |")
    lines += ["", "Rated (63.3 difficulty only):"]
    for key, won, idle, _ in target_1([r for r in runs if r.key in FIVE]):
        lines.append(f"- {key}: {won}/10 ({idle}/10 passive)")
    lines += ["", f"63.4 target 2: each rule's median score drop >= {TARGET2_DROP:.0%}", ""]
    lines.append("| Rule | Arm | Without | With | Drop | |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for rule, base, hit, drop in rows:
        verdict = "ok" if drop >= TARGET2_DROP else "carried" if rule in TARGET2_CARRIED else "MISS"
        arm = TARGET2_ARMS[rule]
        lines.append(f"| {rule} | {arm} | {base:.1f} | {hit:.1f} | {drop:.1%} | {verdict} |")
    return "\n".join(lines)


def met(runs: list[Run], rows: list[tuple[str, float, float, float]]) -> bool:
    one = all(ok for *_, ok in target_1([r for r in runs if r.key in NEW]))
    two = all(d >= TARGET2_DROP for r, _, _, d in rows if r not in TARGET2_CARRIED)
    return one and two
