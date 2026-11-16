"""The v4 scripted strategies (M35b): platform_owner, compliant_platform, power_hyperscaler and
litho_bet, with cloud_steady, power_hyperscaler's comparison. Like the v1-v3 scripts they act
only through `Game.act`, so every rule applies, and they read only what a player sees (the
build screens' siting rows, quotes, the Regulation screen's events), never a hidden draw. Their
numbers describe the scripts, not the game, so they live here rather than in balance.yaml.

- **platform_owner** (44): devices_regions (M23b's device line and SoC on contracts) with its
  own operating system, built by a small team from 2012 and launched by 2014 (its store founds
  with it, 44.1). The phone runs it from the line's first month (SetDevicePlatform), and from
  January 2018 the OS is licensed to other makers at half Android's licence. It answers the
  regulators as M34's "default" player does (cooperates with an inquiry, defends the case).
- **compliant_platform** (48): platform_owner, but it settles early (M34's "compliant"
  answers: commitments at an inquiry) and pays for influence (32.5): $500k a month of lobbying
  in its home region and in Europe from the month its platform has users (2026).
- **cloud_steady**: a steady cloud company without plants: integrator's general data centres in
  its home region (30.6, _own_compute), and from the first live data centre its spare capacity
  sold as cloud hosting (22.3, SellCapacity) at 0.9x the reference price.
- **power_hyperscaler** (46): cloud_steady, but from stage 4 (owned plants unlock, 46.2) each
  new data centre is sited by power (the build screen's rows, 46.6: the shortest queue among
  the cities that serve its home market, then the cheapest grid) and, when it would queue
  (above power.queue.min_mw), comes with a plant behind its meter sized to its whole load
  (46.3: such a load skips the queue): the type whose whole-load size costs least a year.
- **litho_bet** (47): M23b's full_integrator, which from its fab's first month funds a
  lithography research unit (47.4's domain; 120 researchers, litho_2's staff) once it has formed
  its holding company (31.2: stage 5, where the domain opens; from 2027), and from January 2028
  starts the lithography programme at the 60th percentile of the funding range (as M33's
  47.5 target 3), then litho_2 when litho_1 works.
"""

from __future__ import annotations

import math
from typing import Final

from tst.balance.game import PLAYER, Game
from tst.balance.strategies import Strategy, runway
from tst.balance.strategies_v2 import (
    DC_KIND,
    DC_ROLE,
    DC_SPEND_CENTS,
    _own_compute,
    _unit,
    refill_energy,
    staff_unit,
    steady_regions,
)
from tst.balance.strategies_v3 import (
    DEVICE,
    _facilities,
    _mark,
    _product,
    chip_step,
    devices_step,
    full_integrator,
    rung,
)
from tst.sim.actions import AssignUnit, CreateProduct, SetMarketing, SetPrice
from tst.sim.actions.events import ChooseEvent
from tst.sim.actions.facilities import BuildFacility, SellCapacity, StaffFacility
from tst.sim.actions.founder import SetLobbying
from tst.sim.actions.research import StartProject
from tst.sim.calendar import ym_to_turn
from tst.sim.equipment import programme as ep
from tst.sim.equipment.actions import StartLitho
from tst.sim.facilities import compute, lifecycle
from tst.sim.group.holding import FormHolding
from tst.sim.platforms.actions import SetDevicePlatform, SetPlatformRules
from tst.sim.power import plants, siting
from tst.sim.power.actions import BuildPlant
from tst.sim.regulation import cases, structural
from tst.sim.state import holding_of

# --- platform_owner ---------------------------------------------------------------------------

OS_SPEC: Final = ("Own OS", "os")
OS_TEAM_NAME: Final = "OS team"
OS_TEAM: Final = 4  # software engineers: a launchable OS in about a year (M35b probe: 12 months)
OS_FROM: Final = ym_to_turn(2012, 1)  # the build starts once runway allows, from this month
OS_LATEST: Final = ym_to_turn(2013, 1)  # ... and by this month whatever the runway (launch by 2014)
OS_RUNWAY: Final = 12  # months of runway (or profitable) the build needs before OS_LATEST
LICENCE_FROM: Final = ym_to_turn(2018, 1)
LICENCE_SHARE: Final = 0.5  # x Android's licence a unit: cheaper than Android draws OEMs (44.1)
# M34's answers (events/regulation.yaml): A cooperates with an inquiry and defends the case; the
# compliant player's B at an inquiry offers commitments (a settlement); a structural order is
# appealed (C) by both
DEFAULT_ANSWERS: Final[dict[str, str]] = {
    cases.INQUIRY: "A",
    cases.OBJECTIONS: "A",
    cases.RULING: "A",
}
COMPLIANT_ANSWERS: Final[dict[str, str]] = {**DEFAULT_ANSWERS, cases.INQUIRY: "B"}
ORDER_ANSWER: Final = "C"
LOBBY_DOLLARS: Final = 500_000  # a month in a region (48.5 target 4's influence)
LOBBY_FROM: Final = ym_to_turn(2026, 1)  # platforms have users from platforms.start (44.1)
LOBBY_REGIONS: Final = ("north_america", "europe")


def own_os(game: Game) -> int | None:
    """The group's operating system product (None before it is made)."""
    return _product(game, OS_SPEC[1])


def own_platform(game: Game) -> int | None:
    """The device platform the group's OS founded at launch (44.1)."""
    pid = own_os(game)
    if pid is None:
        return None
    return next((p.id for p in game.state.platforms if p.product_id == pid), None)


def os_step(game: Game) -> None:
    """The OS team and product: started from OS_FROM once runway allows (by OS_LATEST in any
    case), kept staffed; steady's launch_ready launches it once built."""
    pid = own_os(game)
    if pid is None:
        if game.state.turn < OS_FROM:
            return
        months = runway(game)
        if game.state.turn < OS_LATEST and months is not None and months <= OS_RUNWAY:
            return
        uid = staff_unit(game, OS_TEAM_NAME, "software_engineer", OS_TEAM)
        if uid is None:
            return
        refill_energy(game)
        pid = game.state.next_ids.product
        name, category = OS_SPEC
        if not game.act(CreateProduct(game.founder_id, name, category, ())):
            return
        game.act(AssignUnit(game.founder_id, pid, uid))
        _mark(game, "os_started")
    staff_unit(game, OS_TEAM_NAME, "software_engineer", OS_TEAM)
    product = game.state.product(pid)
    if product is not None and product.status in ("live", "sunset"):
        _mark(game, "os")


def _run_on_own(game: Game, platform_id: int) -> None:
    """The phone runs the group's OS (a one-off switch, 44.1)."""
    device = _product(game, DEVICE[1])
    if device is None:
        return
    run = game.state.device_run(device)
    if run is not None and run.platform_id == platform_id:
        return
    refill_energy(game)
    if game.act(SetDevicePlatform(game.founder_id, device, platform_id)):
        _mark(game, "device_on_os")


def _license(game: Game, platform_id: int) -> None:
    if game.state.turn < LICENCE_FROM:
        return
    p = game.state.platform(platform_id)
    if p is None or p.licence_cents is not None:
        return
    cents = round(game.loaded.balance.platforms.android_licence_cents * LICENCE_SHARE)
    refill_energy(game)
    if game.act(SetPlatformRules(game.founder_id, platform_id, licence_cents=cents)):
        _mark(game, "licensed")


def answer_regulators(game: Game, answers: dict[str, str]) -> None:
    """Answer the open regulation events as `answers` says (M34's scripted players)."""
    for event in game.state.open_events(PLAYER):
        if event.status != "open" or event.category != "regulation":
            continue
        key = (
            ORDER_ANSWER
            if event.template_id == structural.ORDER_EVENT
            else answers.get(event.template_id, "A")
        )
        if any(c.key == key for c in event.choices):
            game.act(ChooseEvent(game.founder_id, event.id, key))


def _platform_owner(game: Game, answers: dict[str, str]) -> None:
    steady_regions(game)
    os_step(game)
    devices_step(game)
    chip_step(game)
    platform = own_platform(game)
    if platform is not None:
        _run_on_own(game, platform)
        _license(game, platform)
    answer_regulators(game, answers)


def platform_owner(game: Game) -> None:
    """devices_regions with its own OS and store by 2014, licensed to other makers from 2018."""
    _platform_owner(game, DEFAULT_ANSWERS)


def _lobby(game: Game) -> None:
    if game.state.turn < LOBBY_FROM or own_platform(game) is None:
        return
    for region in LOBBY_REGIONS:
        key = f"lobby:{region}"
        if key in game.notes:
            continue
        refill_energy(game)
        if game.act(SetLobbying(game.founder_id, region, LOBBY_DOLLARS)):
            game.notes[key] = game.state.turn
            _mark(game, "lobbying")


def compliant_platform(game: Game) -> None:
    """platform_owner, settling early (commitments at an inquiry) and lobbying $500k a month in
    its home region and Europe from 2026."""
    _platform_owner(game, COMPLIANT_ANSWERS)
    _lobby(game)


# --- cloud_steady and power_hyperscaler -------------------------------------------------------

CLOUD_PRICE: Final = 0.9  # x the reference price (M12a's target 3 seller)
CLOUD_MARKETING: Final = 5_000_000  # cents a month: $50,000 (M12a's target 3 seller)


def sell_cloud(game: Game) -> None:
    """From the first live data centre, its spare capacity sold as cloud hosting (22.3)."""
    turn = game.state.turn
    live = [f for f in _facilities(game, DC_KIND) if f.live_capacity(turn) > 0]
    if not live:
        return
    g = game.loaded.game_data
    cloud = compute.capacity_product(game.state, PLAYER, g)
    if cloud is None:
        refill_energy(game)
        if not game.act(SellCapacity(game.founder_id)):
            return
        cloud = compute.capacity_product(game.state, PLAYER, g)
        if cloud is None:
            return
        _mark(game, "cloud")
        for m in g.category(cloud.category).markets:
            game.act(
                SetPrice(
                    game.founder_id,
                    cloud.id,
                    m.segment,
                    round(m.reference_price_cents * CLOUD_PRICE),
                )
            )
    if cloud.marketing_budget_cents < CLOUD_MARKETING:
        game.act(SetMarketing(game.founder_id, cloud.id, CLOUD_MARKETING))


def cloud_steady(game: Game) -> None:
    """steady_regions with its own general data centres (integrator's, 30.6) selling their
    spare capacity as cloud hosting: T1's and T4's steady cloud company without plants."""
    steady_regions(game)
    _own_compute(game, DC_KIND)
    sell_cloud(game)


PLANT_TYPES: Final = ("gas", "solar_storage", "wind")  # what the build screen ranks (46.6)


def _sited(game: Game, size: int) -> siting.Site | None:
    """The build screen's best city for a data centre of `size` (46.6): among the cities whose
    region serves the home market (19.5), the shortest queue (none when it would not queue),
    then the cheapest grid."""
    b, g = game.loaded.balance, game.loaded.game_data
    home = compute.home_region_of(game.state, b, g)
    rows = [
        s
        for s in siting.sites(game.state, PLAYER, DC_KIND, size, b, g)
        if compute.serves(home, s.region, g)
    ]
    if not rows:
        return None
    return min(rows, key=lambda s: (s.queue_hi or 0.0, s.price_usd_mwh, s.city))


def _plant_size(game: Game, kind: str, region: str, load_mw: float) -> float:
    """The smallest plant whose energy covers the whole load (46.3: so it skips the queue)."""
    b, g = game.loaded.balance, game.loaded.game_data
    cf = plants.capacity_factor(plants.type_def(g, kind), region)
    for mw in b.power.plants.sizes_mw:
        if mw * cf >= load_mw:
            return mw
    return b.power.plants.sizes_mw[-1]


def _plant_for(game: Game, region: str, load_mw: float) -> tuple[str, float]:
    """The plant a player picks to carry a whole load (M35b, rule 2): of the screen's types, the
    one whose smallest whole-load size costs least a year (size x capacity factor x levelised
    $/MWh). The screen's cheapest $/MWh alone picked 250 MW of wind behind a 50 MW load."""
    b, g = game.loaded.balance, game.loaded.game_data

    def cost(kind: str) -> tuple[float, str]:
        mw = _plant_size(game, kind, region, load_mw)
        cf = plants.capacity_factor(plants.type_def(g, kind), region)
        return mw * cf * plants.levelised(game.state, kind, region, b, g), kind

    kind = min(cost(k) for k in PLANT_TYPES)[1]
    return kind, _plant_size(game, kind, region, load_mw)


def _hyperscale_compute(game: Game) -> None:
    """_own_compute's trigger and size (uncovered spend past $200k a month, built only below
    spot), but sited by power and, when the load would queue, with a plant behind its meter."""
    b, g = game.loaded.balance, game.loaded.game_data
    state = game.state
    kind = b.facility.kinds[DC_KIND]
    mine = [f for f in state.facilities if f.company_id == PLAYER and f.kind == DC_KIND]
    for i, f in enumerate(sorted(mine, key=lambda f: f.id)):
        uid = staff_unit(
            game, f"{kind.label} {i + 1}", DC_ROLE, math.ceil(f.capacity / kind.staff_per)
        )
        if uid is not None and f.unit_id != uid:
            game.act(StaffFacility(game.founder_id, f.id, uid))
    built = sum(f.capacity for f in mine)
    home = compute.home_region_of(state, b, g)
    need = sum(
        n.units
        for n in compute.needs(state, PLAYER, b, g)
        if n.good == kind.output_good and compute.serves(n.region, home, g)
    )
    spot = compute.spot_unit_cents(state, kind.output_good, b, g)
    if (need - built) * spot < DC_SPEND_CENTS:
        return
    sizes = sorted(kind.sizes or b.facility.sizes)
    size = next((s for s in sizes if s >= need - built), sizes[-1])
    site = _sited(game, size)
    if site is None:
        return
    q = lifecycle.quote(state, PLAYER, DC_KIND, site.region, size, b, g)
    per_cu = q.capex_cents / (size * kind.life_months) + kind.opex_per_unit_cents
    if per_cu >= spot:
        return
    refill_energy(game)
    before = {f.id for f in game.state.facilities}
    if not game.act(BuildFacility(game.founder_id, DC_KIND, site.region, size, city=site.city)):
        return
    _mark(game, "dc_sited")
    if site.queue_hi is None:  # it would not queue: the grid serves it
        return
    (fid,) = {f.id for f in game.state.facilities} - before
    load = siting.draw_mw(DC_KIND, size, b, g)
    plant, mw = _plant_for(game, site.region, load)
    refill_energy(game)
    if game.act(BuildPlant(game.founder_id, plant, mw, site.region, site.city, fid)):
        _mark(game, "plant")


def power_hyperscaler(game: Game) -> None:
    """cloud_steady, but from stage 4 each new data centre sited by power with a plant behind
    its meter when it would queue."""
    steady_regions(game)
    if plants.plants_unlocked(game.state, PLAYER, game.loaded.balance):
        _hyperscale_compute(game)
    else:
        _own_compute(game, DC_KIND)
    sell_cloud(game)


# --- litho_bet --------------------------------------------------------------------------------

LITHO_FROM: Final = ym_to_turn(2028, 1)
LITHO_PERCENTILE: Final = 0.6  # of the funding range (M33's 47.5 target 3)
LITHO_UNIT: Final = "Lithography research"
LITHO_ROLE: Final = "hardware_engineer"  # M33's lab
LITHO_STAGES: Final = ("litho_1", "litho_2")
LITHO_COVER_MONTHS: Final = 6  # cash covers this many months of a stage's funding at its start
# (M35b probe, seed 1: two years' cover held the 2028 start back to 2035; the group's income
# pays the rest month by month)
HOLDING_FROM: Final = ym_to_turn(2027, 1)  # the programme opens at stage 5 (a holding company)


def _holding(game: Game) -> None:
    """Form the holding company (31.2: stage 5, where lithography opens) from 2027."""
    if game.state.turn < HOLDING_FROM or holding_of(game.state) is not None:
        return
    refill_energy(game)
    if game.act(FormHolding(game.founder_id)):
        _mark(game, "holding")


def _litho_staff(game: Game) -> int:
    d = game.loaded.game_data
    assert d.equipment is not None
    return max(p.staff for p in d.equipment.programme if p.key in LITHO_STAGES)


def _litho_research(game: Game) -> None:
    """A lithography research unit (litho_2's staff) from the fab's first month, researching."""
    if not _facilities(game, "fab") or holding_of(game.state) is None:
        return
    domain = game.loaded.balance.equipment.programme.domain
    uid = staff_unit(game, LITHO_UNIT, LITHO_ROLE, _litho_staff(game))
    if uid is None:
        return
    active = [
        p for p in game.state.research_projects if p.company_id == PLAYER and p.status == "active"
    ]
    if not any(p.unit_id == uid for p in active) and any(
        e.unit_id == uid for e in game.state.staff(PLAYER)
    ):
        refill_energy(game)
        if game.act(StartProject(game.founder_id, uid, domain)):
            _mark(game, "litho_research")


def litho_funding(game: Game) -> float:
    f = game.loaded.balance.equipment.programme.funding
    return f.lo + LITHO_PERCENTILE * (f.hi - f.lo)


def _litho_programme(game: Game) -> None:
    if game.state.turn < LITHO_FROM:
        return
    b, d = game.loaded.balance, game.loaded.game_data
    assert d.equipment is not None
    funding = litho_funding(game)
    for stage in LITHO_STAGES:
        if ep.why_not(game.state, PLAYER, stage, b, d) is not None:
            continue
        p = d.equipment.stage(stage)
        cover = ep.reference_cents(p, b) * funding * LITHO_COVER_MONTHS
        if game.cash < cover:
            continue
        refill_energy(game)
        if game.act(StartLitho(game.founder_id, stage, funding)):
            _mark(game, f"start:{stage}")
    for stage in LITHO_STAGES:
        if ep.succeeded(game.state, PLAYER, stage):
            _mark(game, stage)


def litho_bet(game: Game) -> None:
    """full_integrator with a lithography research unit from its fab and the programme from
    2028 at the 60th-percentile funding (47.5 target 3's bet, played)."""
    full_integrator(game)
    _holding(game)
    _litho_research(game)
    _litho_programme(game)


V4: Final[dict[str, Strategy]] = {
    "platform_owner": platform_owner,
    "power_hyperscaler": power_hyperscaler,
    "litho_bet": litho_bet,
    "compliant_platform": compliant_platform,
}
V4_ARMS: Final[dict[str, Strategy]] = {"cloud_steady": cloud_steady}

_ = (rung, _unit)
