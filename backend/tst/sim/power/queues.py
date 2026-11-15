"""Grid queues (docs/formulas.md 46.3): a new grid-tied plant, and from `power.start` a new
data centre or fab drawing more than `power.queue.min_mw`, joins its region's interconnection
queue. It connects with a monthly hazard after `power.queue.min_share` x the region's median
wait (stream power (2, entry)); nothing about its connection month is stored ahead (46.9), and
the screen shows the wait as `power.queue.shown` x the median.

A queued load may still finish building: it then waits, held back from going live, until it
connects (46.3's holding cost: its fixed costs run). Behind-the-meter plants sized to its whole
load connect it as soon as they are live (they skip the queue).

The region's median: the data's to 2025 (power.yaml `queue_months`, linear by year), then its
seeded path (tst.sim.power.paths).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.facilities.models import Facility
from tst.sim.log import LogItem, inbox_item
from tst.sim.power import demand, draws, grid, plants
from tst.sim.power import formulas as pf
from tst.sim.power.config import interp
from tst.sim.power.models import QueueEntry
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_facility, with_plant, with_queue_entry

HISTORY_YEAR: Final = 2025  # tunable-exempt: the data's last year
LOAD_KINDS: Final = ("data_centre_general", "data_centre_gpu", "fab")  # tunable-exempt: 46.3


def median_months(state: GameState, region: str, data: GameData) -> float:
    """The region's median wait this month (module docstring)."""
    assert data.power is not None
    p = grid.path(state, region)
    if p is not None:
        return p.queue_months
    pts = data.power.region(region).queue_months
    return interp(pts, min(grid.year_of(state.turn), HISTORY_YEAR))


def shown_range(median: float, balance: Balance) -> tuple[float, float]:
    s = balance.power.queue.shown
    return median * s.lo, median * s.hi


def entry_for(state: GameState, facility_id: int) -> QueueEntry | None:
    return next((q for q in state.grid_queue if q.facility_id == facility_id), None)


def waiting(state: GameState, facility_id: int) -> bool:
    """Whether a facility is still waiting for its grid connection."""
    q = entry_for(state, facility_id)
    return q is not None and q.connected_turn is None


def join(state: GameState, facility: Facility, kind: str, mw: float, data: GameData) -> GameState:
    """A project joins its region's queue this month."""
    entry = QueueEntry(
        id=max((q.id for q in state.grid_queue), default=0) + 1,
        company_id=facility.company_id,
        region=facility.region,
        facility_id=facility.id,
        kind="plant" if kind == plants.PLANT_KIND else "load",
        mw=mw,
        joined_turn=state.turn,
        median_months=median_months(state, facility.region, data),
    )
    return with_queue_entry(state, entry)


def load_joins(state: GameState, facility: Facility, balance: Balance, data: GameData) -> bool:
    """Whether a newly ordered facility must queue (46.3): a data centre or fab above the
    threshold, ordered from power.start."""
    if data.power is None or facility.kind not in LOAD_KINDS:
        return False
    if state.turn < month_to_turn(balance.power.start):
        return False
    return demand.facility_mw(state, facility, balance, data) > balance.power.queue.min_mw


def btm_covers(state: GameState, facility: Facility, balance: Balance, data: GameData) -> bool:
    """Live behind-the-meter plants at the facility generate at least its whole load a year."""
    load = demand.facility_mw(state, facility, balance, data)
    if load <= 0:
        return False
    supply = 0.0
    for p in state.plants:
        if p.site_id != facility.id or not p.live(state.turn):
            continue
        t = plants.type_def(data, p.type)
        supply += p.mw * plants.capacity_factor(t, facility.region)
    return supply >= load


def queue_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Phase 4 (before production): connections, and queued loads held back."""
    logs: list[LogItem] = []
    qb = balance.power.queue
    turn = state.turn
    for q in state.grid_queue:
        if q.connected_turn is not None:
            continue
        f = state.facility(q.facility_id)
        if f is None or f.status == "closed":
            continue
        connected = False
        if q.kind == "load" and btm_covers(state, f, balance, data):
            connected = True
        elif turn - q.joined_turn >= qb.min_share * q.median_months:
            u = float(draws.gen(rng, turn, plants.QUEUE_FAMILY, q.id).random())
            connected = u < pf.hazard(q.median_months, qb.min_share)
        if connected:
            state = with_queue_entry(state, replace(q, connected_turn=turn))
            name = (
                plants.plant_name(state, plants.plant_of(state, f.id), data)  # type: ignore[arg-type]
                if q.kind == "plant"
                else _facility_name(state, f, balance, data)
            )
            logs.append(inbox_item(turn, q.company_id, "grid_connected", facility=name))
            if q.kind == "plant":
                p = plants.plant_of(state, f.id)
                if p is not None:
                    state = with_plant(state, replace(p, connected=True))
            else:
                state = _release(state, f, balance)
            continue
        if q.kind == "load" and f.status == "building":
            state = _hold(state, f)
    return state, logs


def _hold(state: GameState, f: Facility) -> GameState:
    """Built, waiting for the grid: held back a month. A generic facility by its ready month
    (the shortfall's late part kept), a fab by its live month (38.2's go-live reads it)."""
    turn = state.turn
    if f.kind == demand.FAB:
        fab = next((x for x in state.fabs if x.facility_id == f.id), None)
        if fab is not None and fab.live_turn <= turn:
            from tst.sim.state import with_fab

            state = with_fab(state, replace(fab, live_turn=turn + 1))
        return state
    if f.ready_turn <= turn + 1:  # held two months ahead: not live between turns either
        late = max(0, f.late_turn - f.ready_turn)
        state = with_facility(state, replace(f, ready_turn=turn + 2, late_turn=turn + 2 + late))
    return state


def _release(state: GameState, f: Facility, balance: Balance) -> GameState:
    """A held load connects: live this month if its build is done (a generic facility's ready
    month back to now; a fab's go-live reads its own months)."""
    turn = state.turn
    if f.kind == demand.FAB or f.status != "building":
        return state
    built = f.ordered_turn + balance.facility.kinds[f.kind].build_months
    if built <= turn < f.ready_turn:
        late = max(0, f.late_turn - f.ready_turn)
        state = with_facility(state, replace(f, ready_turn=turn, late_turn=turn + late))
    return state


def _facility_name(state: GameState, f: Facility, balance: Balance, data: GameData) -> str:
    from tst.sim.facilities.lifecycle import facility_name

    return facility_name(f, balance, data)
