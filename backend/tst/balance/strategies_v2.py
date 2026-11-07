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
from tst.balance.strategies import STRATEGIES as V1
from tst.balance.strategies import Strategy, steady
from tst.sim.actions import AppointCeo, CreateUnit, Interview, MakeOffer, MovePerson, OpenSearch
from tst.sim.actions.authority import SetAuthority
from tst.sim.actions.facilities import BuildFacility, StaffFacility
from tst.sim.actions.geo import LaunchInRegion
from tst.sim.actions.research import StartProject
from tst.sim.facilities import compute
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


def steady_regions(game: Game) -> None:
    """M13b's arm: steady plus a region launch whenever one is due (30.6)."""
    steady(game, keep=_kept(game))
    regions_step(game)


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


def research_heavy(game: Game) -> None:
    """steady_regions plus a research unit of 6 (12 from stage 3) on the domain feeding its
    products, from the seed's close; a fully funded project, so it pulls that domain's eras
    early when its level reaches their thresholds (21.4)."""
    steady_regions(game)
    if not any(
        r.series == "seed" and r.status == "closed" for r in game.state.company_rounds(PLAYER)
    ):
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


def integrator(game: Game) -> None:
    """steady_regions plus its own general data centres once compute spend passes $200k a
    month (30.6): each in the region whose uncovered general CU (its own and the regions it
    serves as a neighbour, 19.5) is largest, the smallest size covering it, staffed by an
    infrastructure team of its own; another whenever a region's uncovered spend passes $200k
    again. Device plants follow only a hardware product, which these scripts never make."""
    steady_regions(game)
    b, g = game.loaded.balance, game.loaded.game_data
    state = game.state
    kind = b.facility.kinds[DC_KIND]
    mine = [f for f in state.facilities if f.company_id == PLAYER and f.kind == DC_KIND]
    for i, f in enumerate(sorted(mine, key=lambda f: f.id)):  # a unit staffs one data centre
        uid = staff_unit(
            game, f"{DC_UNIT} {i + 1}", DC_ROLE, math.ceil(f.capacity / kind.staff_per)
        )
        if uid is not None and f.unit_id != uid:
            game.act(StaffFacility(game.founder_id, f.id, uid))
    need: dict[str, float] = {}
    for n in compute.needs(state, PLAYER, b, g):
        if n.good == kind.output_good:
            need[n.region] = need.get(n.region, 0.0) + n.units
    built: dict[str, int] = {}
    for f in mine:
        built[f.region] = built.get(f.region, 0) + f.capacity
    uncovered = {
        r: sum(u for region, u in need.items() if compute.serves(region, r, g)) - built.get(r, 0)
        for r in g.region_keys
    }
    region = max(g.region_keys, key=lambda r: (uncovered[r], -g.region_keys.index(r)))
    spot = compute.spot_unit_cents(state, kind.output_good, b, g)
    if uncovered[region] * spot < DC_SPEND_CENTS:
        return
    sizes = sorted(kind.sizes or b.facility.sizes)
    size = next((s for s in sizes if s >= uncovered[region]), sizes[-1])
    refill_energy(game)
    game.act(BuildFacility(game.founder_id, DC_KIND, region, size))


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
