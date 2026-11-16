"""M32 sub-task 3 (formulas.md 46.2, ADR-0022 3): energy and money balance per entity through
dispatch, PPAs, plants and surplus sales. One real game holds a live fab with a gas plant behind
its meter, a grid-tied solar-storage plant and a PPA; Hypothesis varies the fab's energy, the
plants' sizes and outages, and the PPA's volume, and settles the month."""

from __future__ import annotations

from dataclasses import replace
from functools import cache

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tst.balance import m21, m32
from tst.balance.game import PLAYER
from tst.sim.calendar import ym_to_turn
from tst.sim.ledger import CASH, ENERGY, ENERGY_SALES
from tst.sim.power import settle
from tst.sim.state import GameState, with_fab, with_plant, with_ppa

NA = "north_america"
EPS = 1e-6


@cache
def base() -> tuple[GameState, int, int, int, int]:
    """(state, fab id, the behind-the-meter gas plant, the grid-tied solar plant, the PPA id)."""
    game = m32.game_at(1, ym_to_turn(2027, 1))
    fid = m32.fab(game, NA)
    gas = m32.plant(game, "gas", 100, NA, fid)
    solar = m32.plant(game, "solar_storage", 250, NA)
    m21.keep_staffed(game)
    m32.play(game)
    pid = m32.sign_ppa(game, NA, "nextera", 10_000, 10)
    state = game.state
    for p in state.plants:  # both live and connected now
        f = state.facility(p.facility_id)
        assert f is not None
        state = with_plant(state, replace(p, live_turn=state.turn - 1, connected=True))
    from tst.sim.state import with_facility

    for pid_ in (gas, solar):
        f = state.facility(pid_)
        assert f is not None
        state = with_facility(state, replace(f, status="live", capex_paid_cents=f.capex_cents))
    return state, fid, gas, solar, pid


@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    energy=st.floats(min_value=0, max_value=200_000),
    gas_mw=st.sampled_from([50.0, 100.0, 250.0]),
    solar_mw=st.sampled_from([50.0, 250.0, 1000.0]),
    ppa_mwh=st.floats(min_value=0, max_value=80_000),
    gas_out=st.booleans(),
    solar_out=st.booleans(),
)
def test_energy_and_money_balance(
    energy: float,
    gas_mw: float,
    solar_mw: float,
    ppa_mwh: float,
    gas_out: bool,
    solar_out: bool,
) -> None:
    state, fid, gas, solar, pid = base()
    lg = m32.loaded()
    b, d = lg.balance, lg.game_data
    turn = state.turn
    fab = next(f for f in state.fabs if f.facility_id == fid)
    assert fab.month is not None
    price = b.refining.power_cents_per_mwh
    month = replace(fab.month, turn=turn, energy_mwh=energy, power_cents=round(energy * price))
    state = with_fab(state, replace(fab, month=month))
    for key, mw, out in ((gas, gas_mw, gas_out), (solar, solar_mw, solar_out)):
        p = next(x for x in state.plants if x.facility_id == key)
        state = with_plant(state, replace(p, mw=mw, outage_until=turn if out else None))
    contract = next(x for x in state.ppas if x.id == pid)
    state = with_ppa(state, replace(contract, mwh_month=ppa_mwh, start_turn=turn))
    new, entries = settle.settle(state, b, d)

    pm = next(m for m in new.power_months if m.turn == turn and m.region == NA)
    # energy: demand = own plants + PPAs + grid, nothing negative
    assert pm.demand_mwh == pytest.approx(energy, abs=EPS)
    assert pm.plant_mwh + pm.ppa_mwh + pm.grid_mwh == pytest.approx(pm.demand_mwh, abs=1e-3)
    assert min(pm.plant_mwh, pm.ppa_mwh, pm.grid_mwh, pm.exported_mwh) >= -EPS
    # each plant: output = used + exported; it never generates more than it can
    for p in new.plants:
        assert p.month is not None and p.month.turn == turn
        cap = p.mw * b.power.hours_a_month * (0.9 if p.type == "gas" else 0.24)
        assert p.month.output_mwh == pytest.approx(p.month.used_mwh + p.month.exported_mwh)
        assert p.month.output_mwh + p.month.curtailed_mwh <= cap + 1e-3
        if p.offline(turn):
            assert p.month.output_mwh == 0
        if p.site_id is not None:
            assert p.month.exported_mwh == 0  # behind the meter: no grid sales
    used = sum(p.month.used_mwh for p in new.plants if p.month is not None)
    assert used == pytest.approx(pm.plant_mwh, abs=1e-3)
    ppa = next(x for x in new.ppas if x.id == pid)
    assert ppa.used_mwh == pytest.approx(pm.ppa_mwh, abs=1e-3) and ppa.used_mwh <= ppa_mwh + EPS
    # money: one balanced entry, cash the other side of energy and energy sales
    mine = [e for e in entries if e.company_id == PLAYER]
    assert len(mine) <= 1
    total = {ENERGY: 0, ENERGY_SALES: 0, CASH: 0}
    for e in mine:
        assert sum(x.amount for x in e.lines) == 0
        for x in e.lines:
            total[x.account] += x.amount
    assert total[CASH] == -(total[ENERGY] + total[ENERGY_SALES])
    assert pm.net_cents == pm.grid_cents + total[ENERGY] + total[ENERGY_SALES]
    assert pm.grid_cents == round(energy * price)
