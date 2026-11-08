"""The v2 scripted strategies (docs/formulas.md 30.6, M15a): steady_regions, research_heavy,
acquirer, integrator and ceo. Like the v1 scripts (tst.balance.strategies) they act only
through `Game.act`, so every rule applies, and their numbers describe the scripts, not the
game, so they live here rather than in balance.yaml.

This module imports only the game wrapper, the v1 scripts and the sim, so tst.balance.report
can list it without an import cycle. Its region-launch and acquisition helpers are M13b's and
M14's arms (tst.balance.m13b, tst.balance.m14), which keep their own copies so their targets'
measures do not move.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Final

from tst.balance.game import PLAYER, Game
from tst.balance.strategies import (
    STEADY_MARKETING,
    STEADY_MARKETING_MIN,
    STEADY_RUNWAY,
    Strategy,
    last_revenue,
    runway,
    set_marketing,
    steady,
)
from tst.balance.strategies import STRATEGIES as V1
from tst.sim.actions import (
    AppointCeo,
    AssignUnit,
    CreateProduct,
    CreateUnit,
    Interview,
    MakeOffer,
    MovePerson,
    OpenSearch,
    SetPrice,
)
from tst.sim.actions.authority import SetAuthority
from tst.sim.actions.facilities import BuildFacility, StaffFacility
from tst.sim.actions.geo import LaunchInRegion
from tst.sim.actions.research import StartProject
from tst.sim.facilities import compute, lifecycle
from tst.sim.mna import deals, valuation
from tst.sim.mna.deals import BidForCompany
from tst.sim.mna.models import Deal
from tst.sim.org import pitches
from tst.sim.org.models import SEATS
from tst.sim.state import ceo_of, with_person_state

# --- Helpers (as M13b's and M14's arms) -------------------------------------

REGION_GAP: Final = 24  # months between the founder's region launches (M13b, 2026-11-04)
OFFER_RATIO: Final = 1.05


def refill_energy(game: Game) -> None:
    """The scripts' energy top-up before a region launch or a bid (as M13b's and M14's arms)."""
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))


def launch_region(game: Game) -> bool:
    """Launch the CRO's best region candidate as the founder; False if there is none or the
    rules refuse it (cash, energy)."""
    loaded = game.loaded
    ranked = pitches.candidates(
        game.state, PLAYER, ("region",), game.cash, loaded.balance, loaded.game_data
    )
    if not ranked:
        return False
    params = dict(ranked[0].params)
    refill_energy(game)
    return bool(
        game.act(LaunchInRegion(game.founder_id, int(params["product_id"]), str(params["region"])))
    )


def regions_step(game: Game) -> None:
    """A region launch when one is due: at most one per REGION_GAP months."""
    last = game.notes.get("region_turn")
    if (last is None or game.state.turn - last >= REGION_GAP) and launch_region(game):
        game.notes["region_turn"] = game.state.turn


def _bid(game: Game, target: int, price: int, mode: str = "integrate") -> bool:
    refill_energy(game)
    return game.act(BidForCompany(game.founder_id, target, price, mode=mode))  # type: ignore[arg-type]


def _deal(game: Game, target: int) -> Deal | None:
    return next((d for d in game.state.deals if d.target_id == target), None)


def buy_private(game: Game, target: int, mode: str = "integrate") -> tuple[int, int] | None:
    """Bid the displayed midpoint, then the counter (28.3); (price, V_f) once agreed."""
    b, g = game.loaded.balance, game.loaded.game_data
    value = valuation.fundamental_value_cents(game.state, target, game.balances, b, g)
    estimate = deals.estimate_cents(game.state, PLAYER, target, game.balances, b, g)
    _bid(game, target, estimate, mode)
    deal = _deal(game, target)
    if deal is None:
        found = next(
            (f for f in game.state.target_files if f.target_id == target and f.counter_cents),
            None,
        )
        if found is None or found.counter_cents is None:
            return None
        _bid(game, target, found.counter_cents, mode)
        deal = _deal(game, target)
    if deal is None or deal.status not in ("accepted", "review"):
        return None
    return deal.price_cents, value


BUY_CASH_MONTHS: Final = 18  # the acquirer buys when cash covers this many months (M14)


def acquire_yearly(game: Game) -> int | None:
    """Once a year, when cash covers 18 months: one startup in the player's categories,
    integrated (M14's acquirer). The bought company's id, or None."""
    if game.state.turn % 12 != 0 or game.state.turn == 0:
        return None
    b, g = game.loaded.balance, game.loaded.game_data
    costs = deals.monthly_costs_cents(game.state, PLAYER, b, g)
    if costs <= 0 or game.cash < BUY_CASH_MONTHS * costs:
        return None
    mine = {p.category for p in game.state.company_products(PLAYER)}
    startups = [
        c
        for c in game.state.rivals()
        if c.is_startup
        and c.parent_id is None
        and any(p.category in mine for p in game.state.company_products(c.id))
    ]
    ranked = sorted(
        startups,
        key=lambda c: (deals.estimate_cents(game.state, PLAYER, c.id, game.balances, b, g), c.id),
    )
    for c in ranked:
        estimate = deals.estimate_cents(game.state, PLAYER, c.id, game.balances, b, g)
        if estimate * 2 > game.cash:
            continue
        if buy_private(game, c.id) is not None:
            return c.id
    return None


def _kept(game: Game) -> frozenset[int]:
    """The v2 scripts' own open searches, which steady's hiring leaves open."""
    return frozenset(v for k, v in game.notes.items() if k.startswith("search:"))


def _unit(game: Game, name: str) -> int | None:
    """The id of the script's unit `name`, created under the root when missing."""
    unit = next((u for u in game.state.active_units(PLAYER) if u.name == name), None)
    if unit is not None:
        return unit.id
    uid = game.state.next_ids.unit
    return uid if game.act(CreateUnit(game.founder_id, "team", name)) else None


def staff_unit(game: Game, name: str, role: str, wanted: int) -> int | None:
    """Work toward `wanted` people of `role` in unit `name`: a job post of its own (left open
    by steady's hiring), offers at 1.05x the ask, and each hire of that role who joined last
    month at the root moved in. Returns the unit's id."""
    uid = _unit(game, name)
    if uid is None:
        return None
    state = game.state
    members = [e for e in state.staff(PLAYER) if e.unit_id == uid]
    for e in state.staff(PLAYER):
        if len(members) >= wanted:
            break
        joined = e.start_turn == state.turn - 1
        mine = e.unit_id is None and joined and state.person(e.person_id).role == role
        if mine and game.act(MovePerson(game.founder_id, e.person_id, uid)):
            members.append(e)
    key = f"search:{name}"
    search = next((s for s in game.state.searches if s.id == game.notes.get(key)), None)
    if len(members) >= wanted:
        return uid
    if search is None or search.status != "open":
        sid = game.state.next_ids.search
        if not game.act(OpenSearch(game.founder_id, role, "job_post")):
            return uid
        game.notes[key] = sid
    pending = sum(
        1
        for o in game.state.offers
        if o.company_id == PLAYER
        and o.status == "pending"
        and game.state.person(o.candidate_id).role == role
    )
    for candidate in list(game.state.open_candidates(PLAYER)):
        if len(members) + pending >= wanted:
            break
        if candidate.search_id != game.notes.get(key):
            continue
        person = game.state.person(candidate.person_id)
        ask = person.salary_expectation_cents
        if ask is None or game.state.pending_offer_for(person.id) is not None:
            continue
        if candidate.interviewed_turn is None and not game.act(
            Interview(game.founder_id, person.id)
        ):
            break
        if game.act(MakeOffer(game.founder_id, person.id, round(ask * OFFER_RATIO), 0)):
            pending += 1
    return uid


def _stage(game: Game) -> int:
    return game.state.player.stage


# --- The strategies --------------------------------------------------------------------------


NEW_PRODUCT_GAP: Final = 36  # months between the founder's new-category products (2026-11-07)
BUILDER_ROLE: Final = "software_engineer"  # the CPO's builders (27.1)


def new_category_step(game: Game) -> None:
    """The founder's own version of the CPO's new-product pitch (product manager's ruling,
    2026-11-07): from the first product's launch, while steady would grow (profitable, or
    runway above STEADY_RUNWAY months), the best candidate the CPO's scoring finds (27.1),
    at most once per NEW_PRODUCT_GAP months: a team unit, the product at its reference
    price, and the candidate's builders hired into the unit. Launched by launch_ready."""
    count = game.notes.get("np_count", 0)
    for i in range(count):  # keep hiring each new product's team
        staff_unit(game, f"New product {i + 1} team", BUILDER_ROLE, game.notes[f"np_team:{i}"])
    state = game.state
    if not any(p.launched_turn is not None for p in state.company_products(PLAYER)):
        return
    last = game.notes.get("np_turn")
    if last is not None and state.turn - last < NEW_PRODUCT_GAP:
        return
    months = runway(game)
    if months is not None and months <= STEADY_RUNWAY:
        return
    b, g = game.loaded.balance, game.loaded.game_data
    ranked = pitches.candidates(state, PLAYER, ("new_product",), game.cash, b, g)
    if not ranked:
        return
    p = dict(ranked[0].params)
    cat = g.category(str(p["category"]))
    segment = str(p["segment"])
    refill_energy(game)
    name = f"New product {count + 1} team"
    uid = _unit(game, name)
    product_id = game.state.next_ids.product
    if uid is None or not game.act(
        CreateProduct(
            game.founder_id, pitches.new_product_name(game.state, PLAYER, cat), cat.key, (segment,)
        )
    ):
        return
    game.act(
        SetPrice(game.founder_id, product_id, segment, cat.market(segment).reference_price_cents)
    )
    game.act(AssignUnit(game.founder_id, product_id, uid))
    game.notes["np_count"] = count + 1
    game.notes[f"np_team:{count}"] = int(p["team"])
    game.notes["np_turn"] = state.turn
    staff_unit(game, name, BUILDER_ROLE, int(p["team"]))


def split_marketing(game: Game) -> None:
    """steady's 20% of last month's revenue as one company budget, split equally over its
    products (each at least STEADY_MARKETING_MIN): steady sets the whole 20% on every product,
    which with new-category products spent about 80% of revenue (M15a decision)."""
    products = [p for p in game.state.company_products(PLAYER) if p.status != "retired"]
    if not products:
        return
    share = round(STEADY_MARKETING * last_revenue(game) / len(products))
    set_marketing(game, max(STEADY_MARKETING_MIN, share))


def steady_regions(game: Game) -> None:
    """M13b's arm: steady plus a region launch whenever one is due (30.6), and from
    2026-11-07 a new-category product when one is due (new_category_step), with steady's
    marketing split over the products (split_marketing)."""
    steady(game, keep=_kept(game))
    regions_step(game)
    new_category_step(game)
    split_marketing(game)


RESEARCH_UNIT: Final = "Research"
RESEARCH_EARLY: Final = 6  # researchers before stage 3 (30.6)
RESEARCH_LATE: Final = 12  # from stage 3
# The role a domain's researchers are hired as: the role whose skills its research skill
# weighs most (tech_frontier.yaml research_skill).
RESEARCH_ROLE: Final = {
    "software_platform": "software_engineer",
    "ai": "data_scientist",
    "infrastructure": "devops_engineer",
    "chip_design": "chip_designer",
    "devices": "hardware_engineer",
}


def research_domain(game: Game) -> str | None:
    """The domain feeding the player's selling products most: the sum of tech_weights over
    their categories (21.1); ties by domain order."""
    tech = game.loaded.game_data.tech
    if tech is None:
        return None
    totals: dict[str, float] = {}
    for p in game.state.company_products(PLAYER):
        if p.status in ("live", "sunset"):
            for domain, weight in tech.tech_weights.get(p.category, {}).items():
                totals[domain] = totals.get(domain, 0.0) + weight
    order = [d.key for d in tech.domains]
    return max(totals, key=lambda d: (totals[d], -order.index(d))) if totals else None


RESEARCH_RUNWAY: Final = 18  # months of runway that also let the research unit start


def research_ready(game: Game) -> bool:
    """The research unit starts after a Series A closes, or once runway covers 18 months
    (product manager, 2026-11-07, fourth round: started after the seed, its salaries
    bankrupted seed 5 before a Series A)."""
    if game.notes.get("research_on"):
        return True
    closed = {r.series for r in game.state.company_rounds(PLAYER) if r.status == "closed"}
    months = runway(game)
    if "a" in closed or months is None or months >= RESEARCH_RUNWAY:
        game.notes["research_on"] = 1
        return True
    return False


def research_heavy(game: Game) -> None:
    """steady_regions plus a research unit of 6 (12 from stage 3) on the domain feeding its
    products, from a Series A or 18 months of runway (research_ready); a fully funded
    project, so it pulls that domain's eras early when its level reaches their thresholds
    (21.4)."""
    steady_regions(game)
    if not research_ready(game):
        return
    domain = research_domain(game)
    if domain is None:
        return
    wanted = (
        RESEARCH_LATE if _stage(game) >= game.loaded.balance.exec_seats.stage else RESEARCH_EARLY
    )
    uid = staff_unit(game, RESEARCH_UNIT, RESEARCH_ROLE.get(domain, "software_engineer"), wanted)
    if uid is None:
        return
    projects = [
        p for p in game.state.research_projects if p.company_id == PLAYER and p.status == "active"
    ]
    if not any(p.unit_id == uid for p in projects) and any(
        e.unit_id == uid for e in game.state.staff(PLAYER)
    ):
        game.act(StartProject(game.founder_id, uid, domain))


def acquirer(game: Game) -> None:
    """M14's arm: steady_regions plus one startup a year in its categories when cash covers
    18 months, integrated (30.6)."""
    steady_regions(game)
    acquire_yearly(game)


DC_SPEND_CENTS: Final = 20_000_000  # $200,000 a month of compute on spot (30.6)
DC_KIND: Final = "data_centre_general"
DC_UNIT: Final = "Infrastructure"
DC_ROLE: Final = "devops_engineer"


def compute_spend_cents(game: Game) -> int:
    """This month's compute need at spot prices, the general and GPU goods together."""
    b, g = game.loaded.balance, game.loaded.game_data
    return round(
        sum(
            n.units * compute.spot_unit_cents(game.state, n.good, b, g)
            for n in compute.needs(game.state, PLAYER, b, g)
        )
    )


def _own_compute(game: Game, kind_key: str) -> None:
    """Data centres of `kind_key` in the home region once the spot spend they could serve
    (the home region and its neighbour) passes $200k a month: the smallest size covering the
    uncovered CU, built only when its cost per CU at full use is below spot, staffed by an
    infrastructure
    team of its own; another whenever the uncovered spend passes $200k again (30.6)."""
    b, g = game.loaded.balance, game.loaded.game_data
    state = game.state
    kind = b.facility.kinds[kind_key]
    mine = [f for f in state.facilities if f.company_id == PLAYER and f.kind == kind_key]
    built = sum(f.capacity for f in mine)
    home = compute.home_region_of(state, b, g)
    need = sum(  # only what a home data centre can serve: home and its neighbour (19.5)
        n.units
        for n in compute.needs(state, PLAYER, b, g)
        if n.good == kind.output_good and compute.serves(n.region, home, g)
    )
    spot = compute.spot_unit_cents(state, kind.output_good, b, g)
    for i, f in enumerate(sorted(mine, key=lambda f: f.id)):  # a unit staffs one data centre
        uid = staff_unit(
            game, f"{kind.label} {i + 1}", DC_ROLE, math.ceil(f.capacity / kind.staff_per)
        )
        if uid is not None and f.unit_id != uid:
            game.act(StaffFacility(game.founder_id, f.id, uid))
    if (need - built) * spot < DC_SPEND_CENTS:
        return
    sizes = sorted(kind.sizes or b.facility.sizes)
    size = next((s for s in sizes if s >= need - built), sizes[-1])
    q = lifecycle.quote(state, PLAYER, kind_key, home, size, b, g)
    per_cu = q.capex_cents / (size * kind.life_months) + kind.opex_per_unit_cents
    if per_cu >= spot:  # only when its own CU, fully used, costs less than spot (22.2)
        return
    refill_energy(game)
    game.act(BuildFacility(game.founder_id, kind_key, home, size))


def integrator(game: Game) -> None:
    """steady_regions plus its own general data centres in its home region once compute spend
    passes $200k a month (30.6, _own_compute). Device plants follow only a hardware product,
    which these scripts never make."""
    steady_regions(game)
    _own_compute(game, DC_KIND)


AI_PRODUCT: Final = ("Oracle", "ai_models", ("smb", "mid_market"))
GPU_KIND: Final = "data_centre_gpu"


def _ai_first(game: Game) -> None:
    """The company's first product is in AI models (product manager's ruling, 2026-11-07):
    made before steady's own first product, which then finds it and builds it."""
    if game.state.company_products(PLAYER):
        return
    name, category, segments = AI_PRODUCT
    product_id = game.state.next_ids.product
    if not game.act(CreateProduct(game.founder_id, name, category, segments)):
        return
    cat = game.loaded.game_data.category(category)
    for segment in segments:
        game.act(
            SetPrice(
                game.founder_id, product_id, segment, cat.market(segment).reference_price_cents
            )
        )
    game.act(AssignUnit(game.founder_id, product_id, None))


def ai_regions(game: Game) -> None:
    """V3's AI baseline: steady_regions with an AI-models first product, no data centres."""
    _ai_first(game)
    steady_regions(game)


def integrator_ai(game: Game) -> None:
    """V3's AI arm: ai_regions plus its own GPU and general data centres (_own_compute)."""
    ai_regions(game)
    _own_compute(game, GPU_KIND)
    _own_compute(game, DC_KIND)


def _ceo_candidate(game: Game) -> int | None:
    """The senior-or-above employee (not the founder) with the best CEO score (25.6)."""
    b = game.loaded.balance
    weights = b.ceo.weights
    best: tuple[float, int] | None = None
    for e in game.state.staff(PLAYER):
        person = game.state.person(e.person_id)
        if person.is_founder or e.level not in ("senior", "principal", "exec"):
            continue
        score = sum(w * person.skills[k] for k, w in weights.items())
        if best is None or (score, -e.person_id) > (best[0], -best[1]):
            best = (score, e.person_id)
    return best[1] if best is not None else None


def ceo(game: Game) -> None:
    """steady_regions with every filled seat given authority from stage 3, and a CEO appointed
    as soon as the rules allow (ceo.min_stage, stage 4: M15a decision), the founder as Chair;
    pitches under the default auto-approve limit (5% of cash) go ahead (30.6)."""
    steady_regions(game)
    if _stage(game) < game.loaded.balance.exec_seats.stage:
        return
    for seat in SEATS:
        a = game.state.authority(PLAYER, seat)
        if game.state.seat_holder(PLAYER, seat) is not None and (a is None or not a.enabled):
            game.act(SetAuthority(game.founder_id, seat, True))
    if ceo_of(game.state, PLAYER) is not None or _stage(game) < game.loaded.balance.ceo.min_stage:
        return
    pid = _ceo_candidate(game)
    if pid is not None:
        refill_energy(game)
        game.act(AppointCeo(game.founder_id, pid))


V2: Final[dict[str, Strategy]] = {
    "steady_regions": steady_regions,
    "research_heavy": research_heavy,
    "acquirer": acquirer,
    "integrator": integrator,
    "ceo": ceo,
}
STRATEGIES: Final[dict[str, Strategy]] = {**V1, **V2}  # the nine (30.6)
# Delegation benchmarks (product manager, 2026-11-07): measured by V4, not among the strategies
# whose wins V1 and T2 count
DELEGATED: Final = ("ceo",)
# V3's AI arms (product manager's ruling, 2026-11-07): measured, not among the nine
ARMS: Final[dict[str, Strategy]] = {"ai_regions": ai_regions, "integrator_ai": integrator_ai}
PLAYABLE: Final[dict[str, Strategy]] = {**STRATEGIES, **ARMS}
