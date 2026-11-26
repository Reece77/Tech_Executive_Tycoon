"""M40 sub-tasks 2-4 (formulas.md 56.1-56.3): launch economics and reuse levels, failures and
groundings, constellations (building, launching, shells, coverage, retirements), service gates
(coverage, licences, capacity, D2D, EO), licences' seeded decisions, the failure event's answers,
and a company without space playing as before."""

from __future__ import annotations

from dataclasses import replace

import pytest

import tst.sim.actions  # noqa: F401
from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.errors import SpaceRuleError
from tst.sim.events.models import GameEvent
from tst.sim.facilities.models import Facility
from tst.sim.ledger import LedgerBalances
from tst.sim.products.models import Product, ProductSegment
from tst.sim.research.models import ResearchLead
from tst.sim.rng import RngFactory
from tst.sim.space import constellation as con
from tst.sim.space import events, launch, phase, policy, rivals, services
from tst.sim.space.actions import (
    ApplyLicence,
    PlanConstellation,
    SetLaunchSpec,
    apply_licence,
    plan_constellation,
    set_launch_spec,
)
from tst.sim.space.models import Cohort, Constellation, LaunchSpec, Licence
from tst.sim.state import GameState, with_facility, with_product, with_research_lead, with_segments

PLAYER = 1
RICH: LedgerBalances = {(PLAYER, "1000_cash"): 10**14}
T2026 = ym_to_turn(2026, 1)


def _founder(state: GameState) -> int:
    founder = state.founder_of(PLAYER)
    assert founder is not None
    return founder.id


def _state(loaded: LoadedData, turn: int = T2026) -> GameState:
    return replace(fresh_game(loaded), turn=turn)


def _line(state: GameState, category: str, pid: int = 9001) -> GameState:
    p = Product(
        id=pid,
        company_id=PLAYER,
        category=category,
        name=f"Line {pid}",
        status="live",
        quality=60.0,
        feature_points=0.0,
        brand=50.0,
        marketing_budget_cents=0,
        created_turn=0,
        launched_turn=0,
    )
    return with_product(state, p)


def _site(state: GameState, kind: str, capacity: int, fid: int = 8001) -> GameState:
    return with_facility(
        state,
        Facility(
            id=fid,
            company_id=PLAYER,
            kind=kind,
            region="north_america",
            capacity=capacity,
            on_time=capacity,
            ordered_turn=0,
            ready_turn=0,
            late_turn=0,
            capex_cents=0,
            input_index=1.0,
            capex_paid_cents=0,
            status="live",
        ),
    )


def _constellation(**kw: object) -> Constellation:
    base = dict(
        id=1,
        company_id=PLAYER,
        name="Test",
        kind="broadband",
        product_id=9001,
        shells=2,
        mass_kg=300.0,
        life_months=60,
        d2d=False,
        insured=True,
        build_per_month=20,
        launches_per_month=2,
        vehicle_product_id=None,
        created_turn=T2026,
    )
    base.update(kw)
    return Constellation(**base)  # type: ignore[arg-type]


# --- 56.1 launch --------------------------------------------------------------------------------


def test_full_reuse_is_far_cheaper_a_kg(loaded: LoadedData) -> None:
    """56.4 target 2's shape: the same design flown fully reused is at least 5x cheaper a kg."""
    b = loaded.balance
    for payload in (5_000.0, 20_000.0, 100_000.0):
        exp = launch.flight_cost(payload, 60.0, 0, "expendable", b).per_kg_cents
        rec = launch.flight_cost(payload, 60.0, 0, "recovery", b).per_kg_cents
        full = launch.flight_cost(payload, 60.0, 0, "full", b).per_kg_cents
        assert exp > rec > full
        assert exp / full >= 5
    # bigger vehicles are cheaper a kg (Electron against Falcon 9, space.yaml)
    small = launch.flight_cost(300.0, 60.0, 0, "expendable", b).per_kg_cents
    big = launch.flight_cost(20_000.0, 60.0, 0, "expendable", b).per_kg_cents
    assert small > 4 * big


def test_reuse_levels_need_lead_and_programme_time(loaded: LoadedData) -> None:
    b = loaded.balance
    state = _state(loaded)
    spec = LaunchSpec(product_id=1, company_id=PLAYER, payload_kg=20_000.0, reuse="full")
    assert launch.capable_level(state, spec, PLAYER, b) == "expendable"
    state = with_research_lead(state, ResearchLead(PLAYER, b.space.domain, 90.0))
    assert launch.capable_level(state, spec, PLAYER, b) == "expendable"  # no programme yet
    state = launch.programme_month(state, b)
    assert state.space.reuse_start(PLAYER) == state.turn
    rec = b.space.reuse["recovery"].min_months
    full = b.space.reuse["full"].min_months
    assert (
        launch.capable_level(replace(state, turn=state.turn + rec), spec, PLAYER, b) == "recovery"
    )
    assert launch.capable_level(replace(state, turn=state.turn + full), spec, PLAYER, b) == "full"
    aim = replace(spec, reuse="recovery")
    assert (
        launch.capable_level(replace(state, turn=state.turn + full), aim, PLAYER, b) == "recovery"
    )
    assert full >= 6 * 12  # 56.4 target 2: at least 6 years


def test_new_vehicles_fail_far_more(loaded: LoadedData) -> None:
    """56.4 target 4: the first ten flights fail at least 3x as often as flights after fifty."""
    b = loaded.balance
    early = sum(launch.failure_rate(i, 60.0, b) for i in range(10)) / 10
    late = launch.failure_rate(50, 60.0, b)
    assert early >= 3 * late
    assert launch.failure_rate(0, 40.0, b) > launch.failure_rate(0, 80.0, b)


def test_failures_ground_the_line_seeded(loaded: LoadedData) -> None:
    """A failed customer launch grounds the line and costs brand; the same seed flies the same."""
    b = loaded.balance
    state = _line(_state(loaded), b.space.launch)
    spec = LaunchSpec(product_id=9001, company_id=PLAYER, payload_kg=20_000.0, reuse="expendable")
    state = replace(state, space=replace(state.space, launch_specs=(spec,)))
    vehicle = state.product(9001)
    assert vehicle is not None
    outcomes = []
    for seed in (1, 1, 2):
        rng = RngFactory(seed)
        s, current = con.record_flight(state, vehicle, spec, True, rng, b)
        outcomes.append(current.grounded_until)
        assert current.failures == 1 and current.flights == 1
        assert current.grounded_until is not None and current.grounded_until > state.turn
        p = s.product(9001)
        assert p is not None and p.brand < vehicle.brand
    assert outcomes[0] == outcomes[1]


def test_launch_line_closed_without_design_or_grounded(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = _line(_state(loaded), b.space.launch)
    eff = services.effects(None, state, b, d)
    assert eff is not None and eff.appeal(9001, "north_america") == 0
    spec = LaunchSpec(product_id=9001, company_id=PLAYER, payload_kg=20_000.0, reuse="expendable")
    ok = replace(state, space=replace(state.space, launch_specs=(spec,)))
    eff = services.effects(None, ok, b, d)
    assert eff is None or eff.appeal(9001, "north_america") == 1
    grounded = replace(
        ok, space=replace(ok.space, launch_specs=(replace(spec, grounded_until=ok.turn + 3),))
    )
    eff = services.effects(None, grounded, b, d)
    assert eff is not None and eff.appeal(9001, "europe") == 0


# --- 56.2 constellations ------------------------------------------------------------------------


def test_coverage_opens_with_a_complete_shell(loaded: LoadedData) -> None:
    b = loaded.balance
    size = b.space.constellation.shell_sats
    c = _constellation()
    assert con.covered_regions(c, b) == ()
    part = replace(c, cohorts=(Cohort(0, T2026, size // 2, 0, T2026 + 60),))
    assert con.covered_regions(part, b) == ()
    full = replace(c, cohorts=(Cohort(0, T2026, size, 0, T2026 + 60),))
    assert set(con.covered_regions(full, b)) == set(b.space.constellation.shells[0].regions)
    gbps, d2d = con.capacity_gbps(full, b)
    assert gbps == pytest.approx(size * 300 * b.space.satellite.gbps_per_kg) and d2d == 0


def _built(loaded: LoadedData, **kw: object) -> GameState:
    b = loaded.balance
    state = _line(_state(loaded), b.space.broadband)
    state = _site(state, b.space.plant_kind, 25)
    c = _constellation(**kw)
    return replace(state, space=replace(state.space, constellations=(c,)))


def test_constellation_builds_launches_and_books(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = _built(loaded)
    rng = RngFactory(7)
    out, entries, _, flown, _ = con.month(state, rng, b, d, {}, {})
    for e in entries:
        assert sum(line.amount for line in e.lines) == 0
    c = out.space.constellations[0]
    assert c.month is not None and c.month.built == 20
    assert len(flown) >= 1
    assert c.cash_cents < 0
    ppe = sum(line.amount for e in entries for line in e.lines if line.account == "1500_ppe")
    assert ppe == c.capex_cents


def test_cohorts_retire_and_are_replaced_ahead(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    size = b.space.constellation.shell_sats
    old = Cohort(0, T2026 - 59, size, 1_000_000, T2026 + 1, depreciated_cents=983_333)
    state = _built(
        loaded, shells=1, cohorts=(old,), capex_cents=1_000_000, depreciated_cents=983_333
    )
    out, entries, _, _, _ = con.month(state, RngFactory(3), b, d, {}, {})
    c = out.space.constellations[0]
    assert c.month is not None and c.month.built > 0  # retiring within replace_ahead_months
    later = replace(out, turn=out.turn + 1)
    out2, entries2, _, _, _ = con.month(later, RngFactory(3), b, d, {}, {})
    assert all(x.launch_turn != old.launch_turn for x in out2.space.constellations[0].cohorts)
    for e in (*entries, *entries2):
        assert sum(line.amount for line in e.lines) == 0


def test_lost_satellites_are_written_off_and_insured(loaded: LoadedData) -> None:
    """A failed own launch loses its satellites (6700), the insurer pays (4900), the line is
    grounded, and for the player the loss is queued as a critical event."""
    b, d = loaded.balance, loaded.game_data
    state = _built(loaded, vehicle_product_id=9002)
    state = _line(state, b.space.launch, 9002)
    state = _site(state, b.space.site_kind, 4, fid=8002)
    bad = LaunchSpec(product_id=9002, company_id=PLAYER, payload_kg=20_000.0, reuse="expendable")
    # a vehicle at the failure model's worst: find a seed whose first flight fails
    state = replace(state, space=replace(state.space, launch_specs=(bad,)))
    for seed in range(1, 60):
        out, entries, _, _, lost = con.month(state, RngFactory(seed), b, d, {}, {})
        if lost:
            break
    else:
        pytest.fail("no failure in 59 seeds")
    memos = {e.memo for e in entries}
    assert any("satellites lost" in m for m in memos)
    assert any("insurance paid" in m for m in memos)
    spec = out.space.spec(9002)
    assert spec is not None and spec.failures == 1 and spec.grounded_until is not None
    c = out.space.constellations[0]
    queued = events.queue_failure(out, c, 10, 1_000_000, 9002)
    assert queued.queued and queued.space.constellations[0].event_turn == out.turn + 1


def test_failure_event_answers(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = _built(loaded, vehicle_product_id=9002, insured=True)
    spec = LaunchSpec(9002, PLAYER, 20_000.0, "expendable", 3, 1, state.turn + 8)
    c = replace(state.space.constellations[0], event_turn=state.turn, event_sats=30,
                event_value_cents=50_000_000, event_vehicle_id=9002)  # fmt: skip
    state = replace(state, space=replace(state.space, launch_specs=(spec,), constellations=(c,)))
    event = GameEvent(
        id=1,
        company_id=PLAYER,
        turn=state.turn,
        template_id="launch_failure_payload",
        category="space",
        severity="critical",
        trigger="space",
        strength=1.0,
    )
    s, entries, _ = events.space_step(state, event, "review", b, d)
    new = s.space.spec(9002)
    assert new is not None and new.grounded_until == state.turn + 4
    s, entries, _ = events.space_step(state, event, "rebuild", b, d)
    assert s.space.constellations[0].ground == c.ground + 30
    for e in entries:
        assert sum(line.amount for line in e.lines) == 0


# --- 56.3 services ------------------------------------------------------------------------------


def test_broadband_sells_only_where_covered_and_licensed(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    size = b.space.constellation.shell_sats
    state = _built(loaded, cohorts=(Cohort(0, T2026, size, 0, T2026 + 60),))
    eff = services.effects(None, state, b, d)
    assert eff is not None and eff.appeal(9001, "north_america") == 0  # no licence
    lic = Licence(PLAYER, "north_america", "granted", T2026, None, T2026)
    state = replace(state, space=replace(state.space, licences=(lic,)))
    eff = services.effects(None, state, b, d)
    assert eff is not None
    assert eff.appeal(9001, "north_america") == 1
    assert eff.appeal(9001, "europe") == 0  # covered, not licensed
    assert eff.appeal(9001, "africa") == 0  # licensed nowhere, not covered
    # D2D is closed without D2D-capable satellites
    assert eff.in_segment(9001, "north_america", b.space.d2d_segment) == 0


def test_congestion_and_trim_to_capacity(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    size = b.space.constellation.shell_sats
    state = _built(loaded, cohorts=(Cohort(0, T2026, size, 0, T2026 + 60),))
    lic = Licence(PLAYER, "north_america", "granted", T2026, None, T2026)
    state = replace(state, space=replace(state.space, licences=(lic,)))
    product = state.product(9001)
    assert product is not None
    cap, _ = services.capacity_by_region(state, product, b, d)
    room = cap["north_america"]
    state = with_segments(state, [ProductSegment(9001, "consumer", 9000, room * 3)], [])
    eff = services.effects(None, state, b, d)
    assert eff is not None and 0 < eff.appeal(9001, "north_america") < 1
    trimmed = services.trim_to_capacity(state, b, d)
    subs, _ = services.customers_by_region(trimmed, product, b, d)
    assert subs["north_america"] == pytest.approx(room)


def test_licences_decide_after_review_seeded(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = _state(loaded)
    out = apply_licence(state, ApplyLicence(_founder(state), "europe"), RICH, b, d)
    lic = out.state.space.licence(PLAYER, "europe")
    assert lic is not None and lic.status == "applied"
    assert lic.decision_turn == state.turn + b.space.licence.review_months["europe"]
    s = out.state
    results = []
    for _ in range(2):
        x = s
        for month in range(1, 60):
            x, _ = policy.licences_month(replace(x, turn=state.turn + month), RngFactory(5), b, d)
            if x.space.licence(PLAYER, "europe").status != "applied":  # type: ignore[union-attr]
                results.append((month, x.space.licence(PLAYER, "europe").status))  # type: ignore[union-attr]
                break
    assert len(results) == 2 and results[0] == results[1]
    assert results[0][0] >= b.space.licence.review_months["europe"]


def test_actions_validate(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = _line(_state(loaded), b.space.launch)
    founder = _founder(state)
    with pytest.raises(SpaceRuleError):
        set_launch_spec(state, SetLaunchSpec(founder, 9001, 10.0, "full"), b, d)
    with pytest.raises(SpaceRuleError):
        set_launch_spec(state, SetLaunchSpec(founder, 9001, 20_000.0, "orbital"), b, d)
    out = set_launch_spec(state, SetLaunchSpec(founder, 9001, 20_000.0, "recovery"), b, d)
    assert out.state.space.spec(9001) is not None
    with pytest.raises(SpaceRuleError):  # a broadband constellation needs a broadband line
        plan_constellation(
            out.state,
            PlanConstellation(founder, "X", "broadband", 9001, 2, 300.0, 60, 10, 1),
            b,
            d,
        )
    s = _line(out.state, b.space.broadband, 9003)
    ok = plan_constellation(
        s, PlanConstellation(founder, "Ring", "broadband", 9003, 2, 300.0, 60, 10, 1, 9001), b, d
    )
    assert ok.state.space.constellations[0].vehicle_product_id == 9001


def test_rivals_hold_until_the_history_ends(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = _state(loaded, ym_to_turn(2020, 1))
    spacex = next(c for c in state.companies if c.name == "SpaceX")
    assert rivals.holds(state, spacex, b, d)
    assert not rivals.holds(replace(state, turn=T2026), spacex, b, d)


def test_space_companies_are_not_ranked_while_they_hold(
    loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    """56.4 target 1: before space.start the space companies are out of the Top 50 and the other
    lists, so the January profile stories to 2025 are main's; from 2026 they are ranked."""
    from tst.sim.modes import rankings
    from tst.sim.space.data import is_space_rival

    b, d = loaded.balance, loaded.game_data
    state = _state(loaded, ym_to_turn(2015, 1))
    space = {c.id for c in state.companies if is_space_rival(c, d)}
    # M55: the space companies' revenue tops the list (with M55's 22 rivals after them, the 50
    # highest ids alone no longer reach theirs)
    monkeypatch.setattr(
        rankings, "_revenue", lambda state, cid: 10**12 * (2 if cid in space else 1) + cid
    )
    assert space
    for listed in rankings.lists(state, b, d).values():
        assert not {cid for cid, _ in listed} & space
    later = rankings.lists(replace(state, turn=T2026), b, d)["revenue"]
    assert {cid for cid, _ in later} & space


def test_a_company_without_space_plays_as_before(loaded: LoadedData) -> None:
    """56.4 target 1: no space records, no space lines: the phases leave the state as it was and
    add no effects for the player's lines."""
    b, d = loaded.balance, loaded.game_data
    state = _state(loaded, ym_to_turn(2020, 3))
    out, entries, logs = phase.after_sales(state, RngFactory(1), b, d, {})
    assert out is state and entries == [] and logs == []
    assert phase.with_effects(None, state, b, d) is None
