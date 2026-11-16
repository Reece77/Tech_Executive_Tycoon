"""M32's balance runs and targets (docs/formulas.md 46.8), printed by tools/m32_targets.py, and
the helpers the M32 tests share. Target 1 (history holds) is `tst.balance.m32_history`.

Each run is a real game (tst.balance.m21's: a rich funded spin-out, cash topped up) placed at a
month, with its facilities and plants ordered through the actions:

2. **Power binds later:** a 500 CU GPU data centre ordered in January 2028 in the US's most
   congested region (North America), with and without a solar-with-storage plant behind its
   meter sized to its load; months from the order to power.
3. **Owning plants pays at a price:** a 50,000-start fab live in 2030 with a gas or
   solar-storage plant behind its meter sized to its load: its energy cost over 2030-2039 against
   the grid's, and the plant's IRR on its capex (savings and its own costs); nuclear's IRR and
   overrun on each seed.
4. **Carbon moves the cheapest plant:** the cheapest new plant type by levelised cost in Europe
   in 2020 and 2035.
5. **Outages matter:** a fab on the grid in the least reliable region (by the data's outage
   rate) in 2030: the share of a year's starts lost, with and without a gas plant behind the
   meter.
6. **Turn time:** M30's guards (`make check-timing`).
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from typing import Final

from tst.balance import m21
from tst.balance.game import PLAYER, Game
from tst.loader import LoadedData
from tst.sim.actions.facilities import BuildFacility
from tst.sim.calendar import ym_to_turn
from tst.sim.ledger import ENERGY, ENERGY_SALES
from tst.sim.power import demand, grid, plants, queues
from tst.sim.power import formulas as pf
from tst.sim.power.actions import BuildPlant, SignPpa
from tst.sim.rng import RngFactory
from tst.sim.state import with_company, with_person_state, with_queue_entry

SEEDS: Final = tuple(range(1, 11))
STAGE: Final = 4  # plants unlock (46.2)
DC_KIND: Final = "data_centre_gpu"
DC_UNITS: Final = (
    10_000  # CU (power.yaml draw 2.941 MWh a CU-month: about 40 MW, above the queue threshold)
)
FAB_STARTS: Final = 50_000
FAB_NODE: Final = "n28"
CONGESTED: Final = "north_america"  # the data's longest wait by 2025 (power.yaml queue_months)
EU: Final = "europe"
MONTHS: Final = 12
NUCLEAR_MW: Final = 1000  # a large reactor's one size


def loaded() -> LoadedData:
    return m21.loaded()


def game_at(seed: int, turn: int, stage: int = STAGE) -> Game:
    """M21's rich company at `turn` and company stage `stage` (plants from stage 4)."""
    g = m21.game_at(seed, turn)
    g.state = with_company(g.state, replace(g.state.company(PLAYER), stage=stage))
    return g


def play(game: Game, n: int = 1) -> None:
    m21.play(game, n)


def energise(game: Game) -> None:
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))


def connect_now(game: Game, fid: int) -> None:
    """An established site: its grid connection is done (target runs of existing fabs)."""
    q = queues.entry_for(game.state, fid)
    if q is not None and q.connected_turn is None:
        game.state = with_queue_entry(game.state, replace(q, connected_turn=game.state.turn))


def data_centre(game: Game, region: str, units: int = DC_UNITS, kind: str = DC_KIND) -> int:
    """Order a data centre; its facility id."""
    energise(game)
    before = {f.id for f in game.state.facilities}
    assert game.act(BuildFacility(game.founder_id, kind, region, units)), dict(game.refused)
    (fid,) = {f.id for f in game.state.facilities} - before
    return fid


def fab(game: Game, region: str, starts: int = FAB_STARTS, ready_now: bool = True) -> int:
    """A fab (staffed, and by default live now and already connected); its facility id."""
    fid = m21.build(game, FAB_NODE, region, starts, ready_now=ready_now)
    if ready_now:
        connect_now(game, fid)
    return fid


def plant(game: Game, kind: str, mw: float, region: str, site_id: int | None = None) -> int:
    """Order a plant (behind `site_id`'s meter when given); its facility id."""
    energise(game)
    before = {p.facility_id for p in game.state.plants}
    city = game.state.facility(site_id).city if site_id is not None else None  # type: ignore[union-attr]
    assert game.act(BuildPlant(game.founder_id, kind, mw, region, city, site_id)), dict(
        game.refused
    )
    (fid,) = {p.facility_id for p in game.state.plants} - before
    return fid


def sign_ppa(game: Game, region: str, producer: str, mwh: float, years: int) -> int:
    energise(game)
    before = {p.id for p in game.state.ppas}
    assert game.act(SignPpa(game.founder_id, region, producer, mwh, years)), dict(game.refused)
    (pid,) = {p.id for p in game.state.ppas} - before
    return pid


def size_for(game: Game, kind: str, region: str, load_mw: float, *, whole: bool = False) -> float:
    """The smallest plant size whose energy a year covers the share of `load_mw` it can serve,
    or with `whole` all of it (46.3: sized to the whole load, so the load skips the queue)."""
    b, d = game.loaded.balance, game.loaded.game_data
    cf = plants.capacity_factor(plants.type_def(d, kind), region)
    need = load_mw * (1.0 if whole else b.power.plants.load_share[kind])
    for mw in b.power.plants.sizes_mw:
        if mw * cf >= need:
            return mw
    return b.power.plants.sizes_mw[-1]


def energy_cents(game: Game, region: str) -> tuple[int, int]:
    """(grid-priced energy, net energy after settlement) this month for the player in `region`."""
    m = next(
        (
            x
            for x in game.state.power_months
            if x.company_id == PLAYER and x.region == region and x.turn == game.state.turn - 1
        ),
        None,
    )
    return (m.grid_cents, m.net_cents) if m else (0, 0)


def settlement_cents(game: Game) -> int:
    """The month's settlement for the player: 5950 energy less 4950 energy sales."""
    res = game.last_result
    assert res is not None
    out = 0
    for e in res.ledger_entries:
        if e.company_id != PLAYER:
            continue
        for line in e.lines:
            if line.account == ENERGY or line.account == ENERGY_SALES:
                out += line.amount
    return out


# --- Target 2: power binds later ------------------------------------------------------------


def time_to_power(seed: int, behind_meter: bool) -> int | None:
    """Months from ordering a data centre in January 2028 in the congested region to its going
    live (None if not in 10 years)."""
    game = game_at(seed, ym_to_turn(2028, 1))
    start = game.state.turn
    fid = data_centre(game, CONGESTED)
    if behind_meter:
        f = game.state.facility(fid)
        assert f is not None
        b, d = game.loaded.balance, game.loaded.game_data
        load = demand.facility_mw(game.state, f, b, d)
        plant(
            game,
            "solar_storage",
            size_for(game, "solar_storage", CONGESTED, load, whole=True),
            CONGESTED,
            fid,
        )
    for _ in range(10 * MONTHS):
        play(game)
        f = game.state.facility(fid)
        if f is not None and f.live_capacity(game.state.turn) > 0:
            return game.state.turn - start
    return None


# --- Target 4: carbon moves the cheapest plant ----------------------------------------------


def cheapest(game: Game, region: str) -> str:
    b, d = game.loaded.balance, game.loaded.game_data
    types = ("gas", "solar_storage", "wind")
    return min(types, key=lambda k: plants.levelised(game.state, k, region, b, d))


def cheapest_change(seed: int) -> tuple[str, str]:
    game = game_at(seed, ym_to_turn(2020, 1))
    first = cheapest(game, EU)
    game.state = replace(game.state, turn=ym_to_turn(2026, 1))
    for year in range(2026, 2036):
        game.state = replace(game.state, turn=ym_to_turn(year, 1))
        from tst.sim.power import paths

        rng = _rng(game)
        game.state = paths.paths_month(game.state, rng, game.loaded.balance, game.loaded.game_data)
        game.state = plants.draw_world(game.state, rng, game.loaded.balance, game.loaded.game_data)
    return first, cheapest(game, EU)


def _rng(game: Game) -> RngFactory:
    return RngFactory(game.state.save_meta.master_seed)


# --- Targets 3 and 5: a fab with and without its own plant ---------------------------------------


@dataclass(frozen=True, slots=True)
class FabPower:
    seed: int
    kind: str | None
    grid_cents: int  # energy at the grid price over the window
    net_cents: int  # after the settlement
    capex_cents: int  # the plant's
    irr: float | None
    overrun: float | None
    starts: float
    lost: float


def fab_power(seed: int, kind: str | None, region: str, start: int, years: int) -> FabPower:
    """A fab built just before `start` (and its plant, sized to its load, live by then): its
    energy over `years` years; the plant's IRR on its capex against buying from the grid."""
    b, d = loaded().balance, loaded().game_data
    t_build = plants.type_def(d, kind).build_months if kind else 0
    game = game_at(seed, start - t_build - 1)
    fid = fab(game, region)
    pid = None
    capex = 0
    if kind is not None:
        f = game.state.facility(fid)
        assert f is not None
        load = demand.facility_mw(game.state, f, b, d)
        if kind == "nuclear":  # a 1 GW reactor on the grid: it sells what the fab does not use
            pid = plant(game, kind, NUCLEAR_MW, region)
        else:
            pid = plant(game, kind, size_for(game, kind, region, load), region, fid)
    while game.state.turn < start:
        m21.keep_staffed(game)
        play(game)
    grid_c = net = 0
    starts = lost = 0.0
    yearly: list[float] = []
    saved_year = 0.0
    live_year = False
    for i in range(years * MONTHS):
        m21.keep_staffed(game)
        play(game)
        g, n = energy_cents(game, region)
        grid_c += g
        net += n
        saved_year += g - n
        fm = next(x for x in game.state.fabs if x.facility_id == fid).month
        if fm is not None:
            starts += fm.run + fm.outage_starts
            lost += fm.outage_starts
        if pid is not None:
            pl = plants.plant_of(game.state, pid)
            live_year = live_year or (pl is not None and pl.live(game.state.turn - 1))
        if (i + 1) % MONTHS == 0:
            if pid is None or live_year:  # the IRR counts its operating years
                yearly.append(saved_year)
            saved_year = 0.0
            live_year = False
    irr = overrun = None
    if pid is not None:
        f = game.state.facility(pid)
        p = plants.plant_of(game.state, pid)
        assert f is not None and p is not None
        capex = f.capex_cents
        overrun = f.capex_cents / p.estimate_cents - 1
        life = plants.type_def(d, kind).life_years  # type: ignore[arg-type]
        if yearly:
            irr = pf.irr([-float(capex), *([statistics.mean(yearly)] * life)])
    return FabPower(seed, kind, grid_c, net, capex, irr, overrun, starts, lost)


def least_reliable(lg: LoadedData) -> str:
    pd = lg.game_data.power
    assert pd is not None
    return max(pd.regions, key=lambda r: r.outages_a_year).key


@dataclass(frozen=True, slots=True)
class Results:
    time_grid: list[int | None]
    time_btm: list[int | None]
    saving: dict[str, list[float]]  # kind -> energy cost saving over 2030-2039 (share of grid)
    irr: dict[str, list[float | None]]
    nuclear_overrun: list[float | None]
    cheapest: list[tuple[str, str]]
    lost_grid: list[float]
    lost_btm: list[float]


def _seed(seed: int) -> dict[str, object]:
    start = ym_to_turn(2030, 1)
    out: dict[str, object] = {
        "time_grid": time_to_power(seed, False),
        "time_btm": time_to_power(seed, True),
        "cheapest": cheapest_change(seed),
    }
    for kind in ("gas", "solar_storage", "nuclear"):
        r = fab_power(seed, kind, CONGESTED, start, 10)
        out[f"fab_{kind}"] = r
    weak = least_reliable(loaded())
    out["lost_grid"] = fab_power(seed, None, weak, start, 1)
    out["lost_btm"] = fab_power(seed, "gas", weak, start, 1)
    return out


def run(seeds: Sequence[int] = SEEDS, jobs: int = 1) -> Results:
    if jobs <= 1:
        rows = [_seed(s) for s in seeds]
    else:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            rows = list(pool.map(_seed, seeds))

    def share(r: FabPower) -> float:
        return 1 - r.net_cents / r.grid_cents if r.grid_cents else 0.0

    def lost(r: FabPower) -> float:
        return r.lost / r.starts if r.starts else 0.0

    return Results(
        time_grid=[r["time_grid"] for r in rows],  # type: ignore[misc]
        time_btm=[r["time_btm"] for r in rows],  # type: ignore[misc]
        saving={k: [share(r[f"fab_{k}"]) for r in rows] for k in ("gas", "solar_storage")},  # type: ignore[arg-type]
        irr={k: [r[f"fab_{k}"].irr for r in rows] for k in ("gas", "solar_storage", "nuclear")},  # type: ignore[attr-defined]
        nuclear_overrun=[r["fab_nuclear"].overrun for r in rows],  # type: ignore[attr-defined]
        cheapest=[r["cheapest"] for r in rows],  # type: ignore[misc]
        lost_grid=[lost(r["lost_grid"]) for r in rows],  # type: ignore[arg-type]
        lost_btm=[lost(r["lost_btm"]) for r in rows],  # type: ignore[arg-type]
    )


def _median(xs: Sequence[float | int | None]) -> float | None:
    vals = [float(x) for x in xs if x is not None]
    return statistics.median(vals) if vals else None


def checks(r: Results) -> dict[int, bool]:
    never = 10 * MONTHS + 1
    grid_m = _median([x if x is not None else never for x in r.time_grid]) or 0
    btm_m = _median([x if x is not None else never for x in r.time_btm]) or never
    # 46.8 target 3's "an owned gas or solar-storage plant": the better of the two (M32 decision)
    t3 = any(
        (_median(r.saving[k]) or 0) >= 0.15 and 0.06 <= (_median(r.irr[k]) or 0) <= 0.12
        for k in ("gas", "solar_storage")
    )
    nuc = [x for x in r.irr["nuclear"] if x is not None]
    big = sum(1 for o in r.nuclear_overrun if o is not None and o > 0.5)
    t3 = t3 and big >= 3 and (not nuc or (min(nuc) < max(nuc)))
    flips = sum(1 for a, b in r.cheapest if a == "gas" and b in ("solar_storage", "wind"))
    lg, lb = _median(r.lost_grid) or 0.0, _median(r.lost_btm) or 0.0
    return {
        2: grid_m >= 36 and btm_m <= 24,
        3: t3,
        4: flips >= 7,
        5: lg >= 0.01 and lb <= lg / 2,
    }


def report(r: Results) -> str:
    def fmt(x: float | None, pct: bool = False) -> str:
        if x is None:
            return "n/a"
        return f"{x:.1%}" if pct else f"{x:.1f}"

    ok = checks(r)
    lines = [
        "M32 targets (docs/formulas.md 46.8), medians over the seeds",
        f"2. power binds later: time to power {fmt(_median(r.time_grid))} months on the grid "
        f"(>= 36), {fmt(_median(r.time_btm))} behind the meter (<= 24): "
        f"{'met' if ok[2] else 'MISSED'}",
    ]
    for k in ("gas", "solar_storage"):
        lines.append(
            f"3. {k}: energy cost {fmt(_median(r.saving[k]), True)} below grid (>= 15%), IRR "
            f"{fmt(_median(r.irr[k]), True)} (6-12%)"
        )
    nuc = [x for x in r.irr["nuclear"] if x is not None]
    big = sum(1 for o in r.nuclear_overrun if o is not None and o > 0.5)
    lines.append(
        f"3. nuclear: IRR {fmt(min(nuc), True) if nuc else 'n/a'} to "
        f"{fmt(max(nuc), True) if nuc else 'n/a'} (-5 to 12%), overruns above 50% on {big} "
        f"seeds (>= 3): {'met' if ok[3] else 'MISSED'}"
    )
    flips = sum(1 for a, b in r.cheapest if a == "gas" and b in ("solar_storage", "wind"))
    lines.append(
        f"4. carbon: the EU's cheapest new plant moves from gas by 2035 on {flips} seeds (>= 7): "
        f"{'met' if ok[4] else 'MISSED'} ({', '.join(f'{a}->{b}' for a, b in r.cheapest)})"
    )
    lines.append(
        f"5. outages: a grid fab loses {fmt(_median(r.lost_grid), True)} of a year's starts "
        f"(>= 1%), behind the meter {fmt(_median(r.lost_btm), True)} (<= half): "
        f"{'met' if ok[5] else 'MISSED'}"
    )
    lines.append("6. turn time: make check-timing (M30's guards)")
    return "\n".join(lines)


__all__ = ["checks", "grid", "report", "run"]
