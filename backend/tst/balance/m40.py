"""M40's balance targets (docs/formulas.md 56.4), printed by tools/m40_targets.py.

Each seed's world is played by the engine from January 2010 to December 2025 with the player's
company doing nothing (so history holds); then:

2. **Reuse changes everything:** from January 2026 the player starts a reusability programme (a
   research lead in the domain rising from a team's output, `TEAM_OUTPUT`, by 21.3's progress and
   decay); its launch line aims for full reuse. The months until the line flies fully reused, and
   that month's cost a kg against an expendable design of the same payload, quality and flights
   in the same month (tst.sim.space.launch).
3. **Constellations are capital-heavy:** from a seeded start in 2026-2030 the player builds a
   four-shell broadband constellation (300 kg satellites with a 5-year life, its own satellite
   plant, launches bought, insured), licensed in every region it covers, its broadband line held
   at a fixed quality (`QUALITY`) and priced at the market's reference; played to December 2049.
   Its cumulative cash flow (tst.sim.space.constellation) must take at least 8 years to turn
   positive (median), and at least 20% of runs never turn positive.
4. **Launches fail:** a new vehicle's failure rate over its first 10 flights against its rate after
   50 (`launch.failure_rate`, a design of quality 60), and the same read from flown records: the
   player's own vehicle line flying its constellation's launches from 2026 on seeds 1-10.
5. **Turn time:** the mean wall-clock time of a turn from 2026 to 2035 on these worlds with a
   constellation (the guards themselves are M30's `make check-timing`).
"""

from __future__ import annotations

import os
import pickle
import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path
from statistics import median
from typing import Final

import tst.sim.actions  # noqa: F401
from tst.balance.game import PLAYER, Game, start_game
from tst.loader import LoadedData, load_all
from tst.sim.calendar import format_turn, ym_to_turn
from tst.sim.facilities.models import Facility
from tst.sim.geo.models import ProductRegion, RegionalSegment
from tst.sim.ledger import CASH
from tst.sim.products.models import Product, ProductSegment
from tst.sim.research.models import ResearchLead
from tst.sim.space import launch
from tst.sim.space.models import Constellation, LaunchSpec, Licence
from tst.sim.state import (
    GameState,
    with_company,
    with_facility,
    with_product,
    with_product_region,
    with_research_lead,
    with_segments,
)

SEEDS: Final = tuple(range(1, 11))
DATA: Final = Path(__file__).resolve().parents[2] / "data"
RICH: Final = 10**14
START: Final = ym_to_turn(2026, 1)
END: Final = ym_to_turn(2039, 12)  # a standard campaign ends here (M37)
TIMING_END: Final = ym_to_turn(2035, 12)
TEAM_OUTPUT: Final = 12.0  # research output a month: about ten researchers of skill 14 (21.3)
QUALITY: Final = 70.0
PAYLOAD: Final = 20_000.0
PAYBACK_YEARS: Final = 8
NEVER_SHARE: Final = 0.20
FAIL_RATIO: Final = 3.0
REUSE_RATIO: Final = 5.0
REUSE_YEARS: Final = 6


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


@cache
def _world_bytes(seed: int) -> bytes:
    """The seed's world to December 2025, the player doing nothing (history holds). With
    TST_WORLD_CACHE set, worlds are kept in that folder between runs (local iteration only)."""
    folder = os.environ.get("TST_WORLD_CACHE")
    cached = Path(folder) / f"m40_world_{seed}.pkl" if folder else None
    if cached is not None and cached.exists():
        return cached.read_bytes()
    g = start_game(loaded(), seed, "funded_spinout")
    g.balances[(PLAYER, CASH)] = g.balances.get((PLAYER, CASH), 0) + RICH
    while g.state.turn < START:
        g.turn()
    out = pickle.dumps((g.state, g.balances))
    if cached is not None:
        cached.write_bytes(out)
    return out


def world(seed: int) -> Game:
    state, balances = pickle.loads(_world_bytes(seed))
    g = Game(loaded(), state, balances)
    g.state = with_company(g.state, replace(g.state.player, stage=4))
    return g


# --- target 2 ---------------------------------------------------------------------------------


def reuse_months(state: GameState) -> tuple[int, float]:
    """(months from the programme's start to full reuse, expendable / fully reused cost a kg)."""
    b = loaded().balance
    rnd = b.rnd
    spec = LaunchSpec(product_id=0, company_id=PLAYER, payload_kg=PAYLOAD, reuse="full")
    s = replace(state, space=replace(state.space, reuse_started=((PLAYER, state.turn),)))
    lead = 0.0
    for month in range(1, 30 * 12):
        lead += rnd.rate * TEAM_OUTPUT / (1 + lead / rnd.half)
        lead *= 1 - rnd.decay
        s = with_research_lead(
            replace(s, turn=state.turn + month), ResearchLead(PLAYER, b.space.domain, lead)
        )
        if launch.capable_level(s, spec, PLAYER, b) == "full":
            full = launch.flight_cost(PAYLOAD, 60.0, 0, "full", b).per_kg_cents
            exp = launch.flight_cost(PAYLOAD, 60.0, 0, "expendable", b).per_kg_cents
            return month, exp / full
    return 10**6, 0.0


# --- target 3 ---------------------------------------------------------------------------------


def _line(state: GameState, category: str, name: str) -> tuple[GameState, int]:
    d = loaded().game_data
    pid, ids = state.next_ids.take("product")
    p = Product(
        id=pid,
        company_id=PLAYER,
        category=category,
        name=name,
        status="live",
        quality=QUALITY,
        feature_points=0.0,
        brand=60.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn,
        held_feature=QUALITY,
    )
    cat = d.category(category)
    home = "north_america"
    segs = tuple(
        ProductSegment(pid, m.segment, m.reference_price_cents, 0.0, False, state.turn)
        for m in cat.markets
        if m.segment != loaded().balance.space.d2d_segment
    )
    regions = [r for r in d.region_keys if r != home]
    regional = tuple(
        RegionalSegment(pid, r, s.segment, s.price_cents, 0.0, False, state.turn)
        for r in regions
        for s in segs
    )
    state = replace(with_product(state, p), next_ids=ids)
    state = with_segments(state, list(segs), list(regional))
    for r in regions:
        state = with_product_region(state, ProductRegion(pid, r, state.turn, state.turn))
    return state, pid


def _plant(state: GameState, fid: int, kind: str, capacity: int) -> Facility:
    return Facility(
        id=fid,
        company_id=PLAYER,
        kind=kind,
        region="north_america",
        capacity=capacity,
        on_time=capacity,
        ordered_turn=state.turn,
        ready_turn=state.turn,
        late_turn=state.turn,
        capex_cents=0,
        input_index=1.0,
        capex_paid_cents=0,
        status="live",
    )


def constellation_start(g: Game, own_vehicle: bool = False) -> int:
    """Set the player up (module docstring) and return the constellation's id."""
    b = loaded().balance
    d = loaded().game_data
    s = g.state
    s, bb = _line(s, b.space.broadband, "Orbit Broadband")
    vehicle = None
    if own_vehicle:
        s, vehicle = _line(s, b.space.launch, "Orbit Launcher")
        spec = LaunchSpec(
            product_id=vehicle, company_id=PLAYER, payload_kg=PAYLOAD, reuse="recovery"
        )
        s = replace(s, space=replace(s.space, launch_specs=(spec,)))
        s = with_facility(s, _plant(s, 10**6 + 2, b.space.site_kind, 2))
    s = with_facility(s, _plant(s, 10**6 + 1, b.space.plant_kind, 25))
    lic = tuple(
        Licence(PLAYER, r, "granted", s.turn, None, s.turn)
        for r in d.region_keys
        if r != "east_asia"
    )
    c = Constellation(
        id=1,
        company_id=PLAYER,
        name="Orbit",
        kind="broadband",
        product_id=bb,
        shells=4,
        mass_kg=300.0,
        life_months=60,
        d2d=False,
        insured=True,
        build_per_month=25,
        launches_per_month=2,
        vehicle_product_id=vehicle,
        created_turn=s.turn,
    )
    g.state = replace(s, space=replace(s.space, constellations=(c,), licences=lic))
    return c.id


@dataclass(frozen=True, slots=True)
class SeedRun:
    seed: int
    reuse_months: int
    reuse_ratio: float
    start_turn: int
    payback_turn: int | None
    final_cash: int
    flights: int
    early_rate: float
    late_rate: float
    turn_seconds: float


def _start_turn(seed: int) -> int:
    """A seeded start in 2026-2030 (the script's own choice, not the game's RNG)."""
    return START + (seed * 7) % 60


def run_seed(seed: int) -> SeedRun:
    g = world(seed)
    months, ratio = reuse_months(g.state)
    start = _start_turn(seed)
    while g.state.turn < start:
        g.turn()
    cid = constellation_start(g, own_vehicle=True)
    times: list[float] = []
    while g.state.turn <= END:
        t0 = time.perf_counter()
        g.turn()
        if g.state.turn - 1 <= TIMING_END:
            times.append(time.perf_counter() - t0)
    c = g.state.space.constellation(cid)
    assert c is not None
    own = [r for r in g.state.space.launches if r.product_id is not None]
    early = [r for r in own[:10]]
    spec = g.state.space.launch_specs[0]
    return SeedRun(
        seed=seed,
        reuse_months=months,
        reuse_ratio=ratio,
        start_turn=start,
        payback_turn=c.paid_back_turn,
        final_cash=c.cash_cents,
        flights=spec.flights,
        early_rate=sum(not r.ok for r in early) / len(early) if early else 0.0,
        late_rate=spec.failures / max(1, spec.flights),
        turn_seconds=sum(times) / len(times) if times else 0.0,
    )


@dataclass(frozen=True, slots=True)
class Results:
    runs: tuple[SeedRun, ...]


def run(seeds: Sequence[int] = SEEDS, jobs: int = os.cpu_count() or 1) -> Results:
    if jobs <= 1:
        return Results(tuple(run_seed(s) for s in seeds))
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        return Results(tuple(pool.map(run_seed, seeds)))


def failure_ratio() -> tuple[float, float]:
    b = loaded().balance
    early = sum(launch.failure_rate(i, 60.0, b) for i in range(10)) / 10
    late = launch.failure_rate(50, 60.0, b)
    return early, late


def report(r: Results) -> str:
    lines = [
        "M40 balance targets (formulas.md 56.4), seeds " + ", ".join(str(x.seed) for x in r.runs)
    ]
    for x in r.runs:
        paid = format_turn(x.payback_turn) if x.payback_turn is not None else "never"
        years = (x.payback_turn - x.start_turn) / 12 if x.payback_turn is not None else None
        lines.append(
            f"  seed {x.seed}: full reuse after {x.reuse_months} months"
            f" (x{x.reuse_ratio:.1f} a kg);"
            f" constellation from {format_turn(x.start_turn)}, paid back {paid}"
            + (f" ({years:.1f} years)" if years is not None else "")
            + f", cash ${x.final_cash / 100 / 1e6:,.0f}M by December 2039; own vehicle"
            f" {x.flights} flights,"
            f" first-10 failures {x.early_rate:.0%}; {x.turn_seconds * 1000:.0f} ms a turn"
        )
    reuse_m = min(x.reuse_months for x in r.runs)
    reuse_x = min(x.reuse_ratio for x in r.runs)
    ok2 = reuse_m >= REUSE_YEARS * 12 and reuse_x >= REUSE_RATIO
    spans = [
        (x.payback_turn - x.start_turn) / 12 if x.payback_turn is not None else float("inf")
        for x in r.runs
    ]
    never = sum(1 for x in r.runs if x.payback_turn is None) / len(r.runs)
    med = median(spans)
    ok3 = med >= PAYBACK_YEARS and never >= NEVER_SHARE
    early, late = failure_ratio()
    ok4 = late > 0 and early / late >= FAIL_RATIO
    lines += [
        f"2. Reuse changes everything: full reuse at least {reuse_m} months after the programme"
        f" starts (>= {REUSE_YEARS * 12}), at least x{reuse_x:.1f} cheaper a kg than expendable"
        f" (>= x{REUSE_RATIO:.0f}): {'met' if ok2 else 'MISSED'}",
        f"3. Constellations are capital-heavy: median payback {med:.1f} years (>= {PAYBACK_YEARS}),"
        f" never {never:.0%} (>= {NEVER_SHARE:.0%}): {'met' if ok3 else 'MISSED'}",
        f"4. Launches fail: first 10 flights {early:.1%} against {late:.2%} after 50"
        f" (x{early / late:.1f}, >= x{FAIL_RATIO:.0f}): {'met' if ok4 else 'MISSED'}",
        f"5. Turn time: median {median(x.turn_seconds for x in r.runs) * 1000:.0f} ms a turn"
        " (2026-2035; the guards are make check-timing)",
    ]
    return "\n".join(lines)


# --- 56.4 target 1: a game without space plays as before --------------------------------------


def space_rivals(state: GameState, data: LoadedData) -> set[int]:
    from tst.sim.space.data import is_space_rival

    return {c.id for c in state.companies if is_space_rival(c, data.game_data)}


def history_without_space(seed: int) -> dict[str, dict[str, str]]:
    """M28's history fingerprint (41.8 target 1) with M40's own rivals' lines left out and later
    companies' ids as main numbers them (M41's normalisation): equal to the recorded fingerprint
    when every earlier company's books, events, prices and capacities to December 2025 are
    unchanged (tools/m40_history_diff.py)."""
    import hashlib

    from tst.balance import m28
    from tst.balance.m41 import _normalise
    from tst.sim.calendar import MONTHS_PER_YEAR

    data = loaded()
    game = start_game(data, seed)
    mine = space_rivals(game.state, data)
    names = tuple(c.name for c in game.state.companies if c.id in mine)
    first = max(mine) + 1
    hashes: dict[str, dict[int, hashlib._Hash]] = {s: {} for s in m28.SERIES}
    while game.state.turn <= m28.LAST_HISTORY_TURN:
        turn = game.state.turn
        game.turn()
        result = game.last_result
        assert result is not None
        kept = replace(
            result,
            ledger_entries=tuple(e for e in result.ledger_entries if e.company_id not in mine),
            log_items=tuple(i for i in result.log_items if i.company_id not in mine),
            event_requests=tuple(r for r in result.event_requests if r.company_id not in mine),
        )
        year = m28.FIRST_YEAR + turn // MONTHS_PER_YEAR
        for series, lines in m28._month_lines(game, kept, turn).items():
            h = hashes[series].setdefault(year, hashlib.sha256())
            for line in lines:
                if series in ("books", "events") and "|" in line and line.split("|")[0].isdigit():
                    line = _normalise(line, series, names, len(mine), first)
                h.update(line.encode())
                h.update(b"\n")
    return {s: {str(y): h.hexdigest() for y, h in sorted(ys.items())} for s, ys in hashes.items()}
