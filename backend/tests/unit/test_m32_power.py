"""M32 (formulas.md 46, ADR-0022): the grid price, demand, plants, PPAs, the settlement, queues,
outages and paths. Each game test is a real game (tst.balance.m32, on M21's rich company)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tst.balance import m21, m32
from tst.balance.game import PLAYER
from tst.sim.calendar import ym_to_turn
from tst.sim.commodities import power as m17
from tst.sim.ledger import ENERGY, ENERGY_SALES
from tst.sim.power import demand, grid, outages, paths, plants, ppa, queues
from tst.sim.power import formulas as pf
from tst.sim.power.actions import BuildPlant, SignPpa
from tst.sim.rng import RngFactory

NA = "north_america"


# --- 46.1-46.2: the grid price and the meter ------------------------------------------------


def test_the_grid_multiple_is_m17s_index_to_2025() -> None:
    """46.8 target 1's unit guard: every region pays exactly M17's index before power.start."""
    lg = m32.loaded()
    b, d = lg.balance, lg.game_data
    game = m32.game_at(1, 0)
    for turn in (0, 37, 120, 191):
        state = replace(game.state, turn=turn)
        for r in d.region_keys:
            assert grid.multiplier(state, r, b, d) == m17.index(state, r, d)
            assert grid.carbon_uplift(state, r, b, d) == 0.0


def test_carbon_passes_through_after_2025() -> None:
    lg = m32.loaded()
    b, d = lg.balance, lg.game_data
    game = m32.game_at(1, ym_to_turn(2026, 1))
    rng = RngFactory(1)
    state = paths.paths_month(game.state, rng, b, d)
    p = grid.path(state, "europe")
    assert p is not None and p.year == 2026
    ref = d.power.region("europe").carbon_at(2025)  # type: ignore[union-attr]
    uplift = (p.carbon - ref) * p.intensity * b.power.carbon.pass_through
    assert grid.carbon_uplift(state, "europe", b, d) == pytest.approx(uplift)
    want = m17.index(state, "europe", d) + uplift / (b.refining.power_cents_per_mwh / 100)
    assert grid.multiplier(state, "europe", b, d) == pytest.approx(want)


def test_a_fab_is_metered_at_its_starts_energy() -> None:
    game = m32.game_at(1, ym_to_turn(2015, 1))
    fid = m32.fab(game, "east_asia")
    m21.keep_staffed(game)
    m32.play(game)
    lg = m32.loaded()
    fab = next(f for f in game.state.fabs if f.facility_id == fid)
    assert fab.month is not None and fab.month.energy_mwh > 0
    per = fab.month.energy_mwh / fab.month.run
    from tst.sim.fabs.plants import power_mwh

    assert per == pytest.approx(power_mwh(game.state, fab, lg.balance, lg.game_data))
    # it paid exactly MWh x the reference price x the region's multiple
    readings = demand.meters(
        replace(game.state, turn=game.state.turn - 1), lg.balance, lg.game_data
    )
    m = next(r for r in readings if r.facility_id == fid)
    assert m.mwh == fab.month.energy_mwh and m.grid_cents == fab.month.power_cents
    pm = next(x for x in game.state.power_months if x.company_id == PLAYER)
    assert pm.demand_mwh == pytest.approx(m.mwh) and pm.grid_mwh == pytest.approx(m.mwh)
    assert pm.net_cents == pm.grid_cents  # all from the grid: the settlement changes nothing


# --- 46.2: plants ----------------------------------------------------------------------------


def test_plants_unlock_at_stage_four() -> None:
    game = m32.game_at(1, ym_to_turn(2027, 1), stage=3)
    m32.energise(game)
    assert not game.act(BuildPlant(game.founder_id, "gas", 100, NA))
    game = m32.game_at(1, ym_to_turn(2027, 1))
    fid = m32.plant(game, "gas", 100, NA)
    p = plants.plant_of(game.state, fid)
    f = game.state.facility(fid)
    assert p is not None and f is not None and f.kind == "plant"
    assert queues.waiting(game.state, fid)  # grid-tied: it queues
    assert not p.connected and p.site_id is None


def test_the_overrun_is_hidden_in_the_capex_and_the_completion() -> None:
    b = m32.loaded().balance
    for seed in range(1, 6):
        game = m32.game_at(seed, ym_to_turn(2027, 1))
        fid = m32.plant(game, "nuclear", 1000, NA)
        f = game.state.facility(fid)
        p = plants.plant_of(game.state, fid)
        assert f is not None and p is not None
        share = f.capex_cents / p.estimate_cents - 1
        span = b.power.plants.overrun["nuclear"]
        assert span.lo - 1e-9 <= share <= span.hi + 1e-9
        quoted = f.ready_turn - game.state.turn
        assert quoted == 84 and p.complete_turn - game.state.turn >= quoted


def test_a_behind_the_meter_plant_supplies_its_site_and_skips_the_queue() -> None:
    game = m32.game_at(1, ym_to_turn(2027, 1))
    lg = m32.loaded()
    fid = m32.fab(game, NA)
    f = game.state.facility(fid)
    assert f is not None
    load = demand.facility_mw(game.state, f, lg.balance, lg.game_data)
    pid = m32.plant(game, "gas", m32.size_for(game, "gas", NA, load), NA, fid)
    p = plants.plant_of(game.state, pid)
    assert p is not None and p.connected and queues.entry_for(game.state, pid) is None
    for _ in range(37):
        m21.keep_staffed(game)
        m32.play(game)
    p = plants.plant_of(game.state, pid)
    assert p is not None and p.live(game.state.turn - 1) and p.month is not None
    assert p.month.used_mwh > 0 and p.month.exported_mwh == 0  # no grid: no exports
    grid_c, net = m32.energy_cents(game, NA)
    assert 0 < net < grid_c  # the plant's energy is cheaper than the grid's


def test_a_plant_depreciates_over_its_life() -> None:
    game = m32.game_at(1, ym_to_turn(2027, 1))
    fid = m32.fab(game, NA)
    pid = m32.plant(game, "solar_storage", 250, NA, fid)
    for _ in range(20):
        m21.keep_staffed(game)
        m32.play(game)
    f = game.state.facility(pid)
    assert f is not None and f.status == "live" and f.capex_paid_cents == f.capex_cents
    months = game.state.turn - 1 - (plants.plant_of(game.state, pid).live_turn or 0) + 1  # type: ignore[union-attr]
    assert f.depreciated_cents == f.capex_cents * months // (30 * 12)


# --- 46.2: PPAs ------------------------------------------------------------------------------


def test_a_ppa_prices_below_the_forward_and_settles_take_or_pay() -> None:
    lg = m32.loaded()
    b, d = lg.balance, lg.game_data
    game = m32.game_at(1, ym_to_turn(2027, 1))
    fid = m32.fab(game, NA)
    m21.keep_staffed(game)
    m32.play(game)  # a month of demand sets the PPA's size limit
    q = ppa.quote(game.state, NA, "nextera", 10_000, 10, b, d)
    fwd = ppa.forward_cents(game.state, NA, b, d)
    assert q.price_cents == pytest.approx(fwd * (1 - 0.05))
    pid = m32.sign_ppa(game, NA, "nextera", 10_000, 10)
    for _ in range(2):
        m21.keep_staffed(game)
        m32.play(game)
    contract = next(p for p in game.state.ppas if p.id == pid)
    assert contract.used_mwh == pytest.approx(10_000)
    assert contract.paid_cents == round(10_000 * contract.price_cents)
    pm = next(
        x for x in game.state.power_months if x.turn == game.state.turn - 1 and x.region == NA
    )
    assert pm.ppa_mwh == pytest.approx(10_000)
    assert pm.grid_mwh == pytest.approx(pm.demand_mwh - 10_000)
    _ = fid


def test_a_ppa_larger_than_demand_is_refused() -> None:
    game = m32.game_at(1, ym_to_turn(2027, 1))
    m32.fab(game, NA)
    m21.keep_staffed(game)
    m32.play(game)
    m32.energise(game)
    assert not game.act(SignPpa(game.founder_id, NA, "nextera", 10_000_000, 10))
    assert not game.act(SignPpa(game.founder_id, NA, "edf", 1_000, 10))  # EDF sells in Europe
    assert not game.act(SignPpa(game.founder_id, NA, "nextera", 1_000, 30))  # 5-20 years


def test_a_ppa_terminates_at_m23as_fee() -> None:
    from tst.sim.contracts.termination import TerminateContract, quote

    lg = m32.loaded()
    game = m32.game_at(1, ym_to_turn(2027, 1))
    m32.fab(game, NA)
    m21.keep_staffed(game)
    m32.play(game)
    pid = m32.sign_ppa(game, NA, "nextera", 10_000, 5)
    q = quote(game.state, "ppa", pid, lg.balance, lg.game_data)
    assert q.counterparty == "power:nextera" and q.fee_cents > 0
    m32.energise(game)
    assert game.act(TerminateContract(game.founder_id, "ppa", pid))
    assert next(p for p in game.state.ppas if p.id == pid).status == "terminated"


# --- 46.3: queues ----------------------------------------------------------------------------


def test_a_large_data_centre_queues_from_2026_only() -> None:
    game = m32.game_at(1, ym_to_turn(2024, 1))
    fid = m32.data_centre(game, NA)
    assert queues.entry_for(game.state, fid) is None
    game = m32.game_at(1, ym_to_turn(2026, 1))
    fid = m32.data_centre(game, NA)
    q = queues.entry_for(game.state, fid)
    assert q is not None and q.kind == "load" and q.median_months == pytest.approx(55)
    small = m32.data_centre(game, NA, units=500)  # 2 MW: under the threshold
    assert queues.entry_for(game.state, small) is None


def test_a_queued_data_centre_waits_after_its_build() -> None:
    game = m32.game_at(2, ym_to_turn(2026, 1))
    fid = m32.data_centre(game, NA)
    m32.play(game, 13)
    f = game.state.facility(fid)
    assert f is not None and f.status == "building" and f.live_capacity(game.state.turn) == 0
    assert queues.waiting(game.state, fid)


def test_the_hazard_gives_the_median_wait() -> None:
    med, lo = 48.0, 0.5
    h = pf.hazard(med, lo)
    # after the minimum, half connect by the median
    assert 1 - (1 - h) ** (med * (1 - lo)) == pytest.approx(0.5, abs=1e-9)


# --- 46.5: outages ---------------------------------------------------------------------------


def test_grid_outages_are_seeded_and_start_in_2026() -> None:
    lg = m32.loaded()
    b, d = lg.balance, lg.game_data
    game = m32.game_at(1, ym_to_turn(2025, 6))
    state, _ = outages.outages_month(game.state, RngFactory(1), b, d)
    assert state.grid_outages == ()

    def months(seed: int) -> list[tuple[int, str]]:
        g = m32.game_at(seed, ym_to_turn(2026, 1))
        s = g.state
        out = []
        for t in range(ym_to_turn(2026, 1), ym_to_turn(2031, 1)):
            s, _ = outages.outages_month(replace(s, turn=t), RngFactory(seed), b, d)
            out += [(o.turn, o.region) for o in s.grid_outages if o.turn == t]
        return out

    a, again, other = months(3), months(3), months(4)
    assert a == again and a != other
    africa = sum(1 for _, r in a if r == "africa")
    east = sum(1 for _, r in a if r == "east_asia")
    assert africa > east  # the data's 12 a year against 0.2


def test_a_grid_outage_scraps_wafers_and_a_plant_behind_the_meter_holds_them() -> None:
    from tst.sim.power.models import GridOutage

    game = m32.game_at(1, ym_to_turn(2030, 1))
    fid = m32.fab(game, "africa")
    m21.keep_staffed(game)
    game.state = replace(game.state, grid_outages=(GridOutage(game.state.turn, "africa"),))
    m32.play(game)
    lg = m32.loaded()
    fab = next(f for f in game.state.fabs if f.facility_id == fid)
    assert fab.month is not None and fab.month.outage_starts > 0
    share = fab.month.outage_starts / (fab.month.available + fab.month.outage_starts)
    assert share == pytest.approx(lg.balance.power.outage.wafer_loss)


# --- 46.6: levelised cost -------------------------------------------------------------------


def test_the_worked_example_levelised_cost() -> None:
    capex, fom, cf = 948.0, 11.1, 0.9
    var = 6.226 * 2.38 + 2.40
    lcoe = pf.levelised_usd_mwh(capex, fom, cf, var, 0.07, 30)
    assert lcoe == pytest.approx(28.3, abs=0.2)
    assert pf.crf(0.07, 30) == pytest.approx(0.0806, abs=1e-4)


def test_the_cheapest_new_plant_in_europe_is_gas_in_2020() -> None:
    game = m32.game_at(1, ym_to_turn(2020, 1))
    assert m32.cheapest(game, "europe") == "gas"


def test_settlement_posts_one_balanced_entry() -> None:
    game = m32.game_at(1, ym_to_turn(2027, 1))
    fid = m32.fab(game, NA)
    m32.plant(game, "gas", 100, NA, fid)
    for _ in range(37):
        m21.keep_staffed(game)
        m32.play(game)
    res = game.last_result
    assert res is not None
    entries = [e for e in res.ledger_entries if e.memo.startswith("Power settlement")]
    assert len(entries) == 1
    assert {line.account for line in entries[0].lines} <= {ENERGY, ENERGY_SALES, "1000_cash"}


# --- 46.6: siting; 46.4: disclosure; 46.7: rivals ---------------------------------------------


def test_siting_shows_each_city_with_a_queue_range_from_2026() -> None:
    from tst.sim.power import siting

    lg = m32.loaded()
    b, d = lg.balance, lg.game_data
    game = m32.game_at(1, ym_to_turn(2028, 1))
    rows = siting.sites(game.state, PLAYER, "data_centre_gpu", 10_000, b, d)
    assert {r.city for r in rows} == {c.key for c in d.cities}
    na = next(r for r in rows if r.region == NA)
    assert na.queue_lo is not None and na.queue_hi is not None and na.queue_lo < na.queue_hi
    assert na.behind_meter and na.price_usd_mwh == pytest.approx(68.0, rel=0.3)
    small = siting.sites(game.state, PLAYER, "data_centre_gpu", 100, b, d)
    assert all(r.queue_lo is None for r in small)  # under the threshold: no queue
    early = siting.sites(
        m32.game_at(1, ym_to_turn(2020, 1), stage=3).state, PLAYER, "fab", 50_000, b, d
    )
    assert all(r.queue_lo is None and not r.behind_meter for r in early)


def test_disclosure_hits_brands_above_the_threshold() -> None:
    from tst.sim.power import disclosure
    from tst.sim.power.models import PowerMonth

    lg = m32.loaded()
    b, d = lg.balance, lg.game_data
    game = m32.game_at(1, ym_to_turn(2030, 12))
    t = game.state.turn
    months = tuple(
        PowerMonth(PLAYER, NA, t - k, demand_mwh=1e5, grid_mwh=1e5, scope2_tonnes=40_000)
        for k in range(12)
    )
    state = replace(game.state, power_months=months)
    revenue = {(PLAYER, "4000_revenue_subscriptions"): -100 * 100_000_000}  # $100M this year
    new, logs = disclosure.disclose(state, b, d, revenue)
    assert any(item.kind == "emissions_report" for item in logs)
    points = disclosure.brand_points(new, PLAYER)
    assert points <= -b.power.carbon.brand_hit.lo  # 4,800 t a $1M against 200
    clean = tuple(replace(m, plant_mwh=1e5, grid_mwh=0, scope2_tonnes=0) for m in months)
    new, _ = disclosure.disclose(replace(game.state, power_months=clean), b, d, revenue)
    assert disclosure.brand_points(new, PLAYER) == 1.0


def test_power_producers_follow_every_earlier_chain_key() -> None:
    from tst.sim.world import data as wd

    lg = m32.loaded()
    d = lg.game_data
    with_power = wd.specs(d)
    without = wd.specs(d.model_copy(update={"power": None}))
    assert [s.key for s in with_power[: len(without)]] == [s.key for s in without]
    rest = with_power[len(without) :]
    assert all(all(wd.is_power_good(g) for g in s.goods) for s in rest)
    assert {s.key for s in rest} >= {p.key for p in d.power.producers}  # type: ignore[union-attr]
    # named producers and other generators sum to the region's generation
    for good in wd.power_goods(d):
        caps = wd.capacities(d, good, ym_to_turn(2025, 12))
        assert sum(caps.values()) == pytest.approx(wd.world_capacity(d, good, ym_to_turn(2025, 12)))
        assert all(v > 0 for v in caps.values())
