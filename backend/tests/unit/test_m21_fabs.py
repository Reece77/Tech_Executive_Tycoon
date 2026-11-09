"""M21 (formulas.md 38.2-38.4): building a fab, EUV tools, yield learning, costs and slots, own
chips at cost, node contracts, node quality and conversions. Each test is a real game
(tst.balance.m21) with the fab ordered through `build_fab`."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tst.balance import m12b, m21
from tst.sim.calendar import ym_to_turn
from tst.sim.chips import chips
from tst.sim.fabs import market as fm
from tst.sim.fabs import supply as fs
from tst.sim.fabs.actions import BuildFab, UpgradeFab, overrun_share, quote
from tst.sim.ledger import FOUNDRY_SALES
from tst.sim.state import with_production_contract


def _fab(game: m21.Game, fid: int):  # type: ignore[no-untyped-def]
    fab = fm.fab_of(game.state, fid)
    assert fab is not None
    return fab


def test_build_quotes_an_estimate_and_hides_the_overrun() -> None:
    b = m21.loaded().balance
    game = m21.game_at(1, ym_to_turn(2014, 1))
    fid = m21.build(game, "n28", "east_asia", 25_000, ready_now=False)
    fab = _fab(game, fid)
    f = game.state.facility(fid)
    assert f is not None and f.kind == "fab" and f.status == "building"
    share = f.capex_cents / fab.estimate_cents - 1
    assert b.fab.overrun.lo <= share <= b.fab.overrun.hi
    assert share == pytest.approx(
        overrun_share(replace(game.state, turn=f.ordered_turn), fid, b), abs=1e-6
    )
    assert fab.build_months == 24  # 28 nm is mature in 2014
    assert fab.tools == 0 and fab.tools_turn is None
    m21.play(game, 3)
    f = game.state.facility(fid)
    assert f is not None and 0 < f.capex_paid_cents < f.capex_cents


def test_a_mature_fab_goes_live_after_construction_and_its_yield_climbs() -> None:
    game = m21.game_at(1, ym_to_turn(2014, 1))
    fid = m21.build(game, "n28", "east_asia", 10_000, ready_now=False)
    m21.play(game, 24)
    f = game.state.facility(fid)
    assert f is not None and f.status == "building"
    m21.play(game, 1)
    f = game.state.facility(fid)
    fab = _fab(game, fid)
    assert f is not None and f.status == "live" and f.capex_paid_cents == f.capex_cents
    first = fab.yield_
    assert first == pytest.approx(0.7, abs=0.01)  # 28 nm was 3+ years old
    m21.play(game, 6)
    assert _fab(game, fid).yield_ > first


def test_the_process_level_gates_a_node() -> None:
    game = m21.game_at(1, ym_to_turn(2019, 1), lead=0.0)
    lg = m21.loaded()
    q = quote(game.state, 1, "n7", "east_asia", 10_000, lg.balance, lg.game_data)
    assert not q.allowed and "process research" in (q.reason or "")
    assert not game.act(BuildFab(game.founder_id, "n7", "east_asia", 10_000))
    # far future nodes cannot be planned yet
    q = quote(game.state, 1, "a16", "east_asia", 10_000, lg.balance, lg.game_data)
    assert not q.allowed


def test_a_leading_edge_fab_takes_three_years_and_waits_for_euv_tools() -> None:
    lg = m21.loaded()
    b, d = lg.balance, lg.game_data
    game = m21.game_at(1, ym_to_turn(2021, 1))  # the EUV backlog: a 24-month lead
    q = quote(game.state, 1, "n5", "east_asia", 100_000, b, d)
    assert q.euv and q.tools == 50 and q.build_months == 36  # n5 is 9 months old: leading
    q3 = quote(game.state, 1, "n3", "east_asia", 100_000, b, d)
    assert q3.build_months == 36
    assert q.tools_turn is not None and q.tools_turn > game.state.turn + 24
    fid = m21.build(game, "n5", "east_asia", 100_000, ready_now=False)
    fab = _fab(game, fid)
    assert fab.live_turn == q.tools_turn + b.fab.euv.install_months > game.state.turn + 24
    m21.play(game, 36)
    f = game.state.facility(fid)
    assert f is not None and f.status == "building"
    assert f.capex_paid_cents == f.capex_cents  # construction is paid, the tools are not here
    from tst.sim.fabs.plants import fab_month
    from tst.sim.rng import RngFactory

    assert game.state.turn == f.ordered_turn + fab.build_months
    _, _, logs = fab_month(game.state, RngFactory(1), b, d)
    assert [x.template for x in logs] == ["fab_waiting_tools"]
    # a fab at 7 nm by DUV needs no tools, at the DUV route's yield and cost
    q7 = quote(game.state, 1, "n7", "east_asia", 10_000, b, d, duv=True)
    q7e = quote(game.state, 1, "n7", "east_asia", 10_000, b, d)
    assert q7.tools == 0 and q7e.tools == 5
    assert q7.capex_cents == pytest.approx(q7e.capex_cents * 1.15, rel=1e-9)


def test_spare_starts_sell_as_foundry_slots() -> None:
    b = m21.loaded().balance
    game = m21.game_at(1, ym_to_turn(2016, 1))
    fid = m21.build(game, "n28", "east_asia", 10_000)
    before = game.balances.get((1, FOUNDRY_SALES), 0)
    m21.play(game, 3)
    fab = _fab(game, fid)
    m = fab.month
    assert m is not None and m.available == pytest.approx(10_000)
    assert 0 < m.sold <= m.available and m.own == 0
    assert m.slot_price_cents == pytest.approx(m.market_cents * b.fab.slot.discount)
    assert m.revenue_cents == round(m.sold * m.slot_price_cents)
    assert game.balances.get((1, FOUNDRY_SALES), 0) - before < 0  # revenue is a credit
    assert m.customers and sum(s for _, s in m.customers) == pytest.approx(m.sold)
    assert m.depreciation_cents > 0 and m.fixed_cents > 0 and m.materials_cents > 0


def test_an_unstaffed_fab_runs_nothing() -> None:
    game = m21.game_at(1, ym_to_turn(2016, 1))
    fid = m21.build(game, "n28", "east_asia", 10_000)
    f = game.state.facility(fid)
    assert f is not None
    game.notes.pop(f"staff:{fid}")
    game.state = m21.with_facility(game.state, replace(f, unit_id=None))
    m21.play(game, 2)
    m = _fab(game, fid).month
    assert m is not None and m.available == 0 and m.sold == 0 and m.revenue_cents == 0
    assert m.depreciation_cents > 0  # it still depreciates


def _chip_company(year: int, node: str | None) -> tuple[m21.Game, int]:
    lg = m21.loaded()
    b, d = lg.balance, lg.game_data
    turn = ym_to_turn(year, 1)
    game = m21.game_at(1, turn)
    ref = d.category("chips_ai_accelerator").market("hyperscalers").reference_price_cents
    state, pid = m12b.product(
        game.state, "chips_ai_accelerator", "hyperscalers", ref, "Accel", root=True
    )
    price = chips.index_wafer_cents(state, "ai_accelerator", b, d, "tsmc", node)
    state = m12b.contract(state, pid, "wafer", 2_000, price, turn, 36)
    c = next(c for c in state.production_contracts if c.product_id == pid)
    game.state = with_production_contract(state, replace(c, node=node))
    return game, pid


def test_own_fab_chips_cost_the_fab_and_post_packaging_only() -> None:
    lg = m21.loaded()
    b, d = lg.balance, lg.game_data
    game, pid = _chip_company(2021, "n5")
    fid = m21.build(game, "n5", "east_asia", 10_000)
    m21.play(game, 2)
    state = replace(game.state, turn=game.state.turn - 1)  # the month just played
    product = state.product(pid)
    assert product is not None
    shares = fs.product_shares(state, product, b, d)
    assert shares and shares[0].facility_id == fid
    own = chips.fab_unit_cents(state, product, b, d)
    assert own is not None
    share = chips.fab_share_of_capacity(state, product, b, d)
    assert 0 < share <= 1
    unit = chips.unit_cost_cents(state, product, b, d)
    contract = chips.contract_unit_cents(state, product, b, d)
    assert unit == pytest.approx(share * own + (1 - share) * contract)
    posted = chips.posted_unit_cents(state, product, b, d)
    assert posted == pytest.approx(share * b.chips.packaging_cents + (1 - share) * contract)
    assert fs.product_node(state, product, b, d) == "n5"


def test_a_node_contract_needs_a_foundry_running_it_and_prices_the_node() -> None:
    from tst.sim.actions.hardware import SignWaferContract

    lg = m21.loaded()
    b, d = lg.balance, lg.game_data
    game, pid = _chip_company(2019, None)
    assert not game.act(SignWaferContract(game.founder_id, pid, "tsmc", 100, 12, node="n5"))
    assert not game.act(SignWaferContract(game.founder_id, pid, "globalfoundries", 100, 12, "n7"))
    assert game.act(SignWaferContract(game.founder_id, pid, "tsmc", 100, 12, node="n7"))
    c = max(game.state.production_contracts, key=lambda c: c.id)
    assert c.node == "n7"
    assert c.price_cents == pytest.approx(fm.node_price_cents(game.state, "n7", b, d))
    # Intel takes contracts only from March 2021
    assert not game.act(SignWaferContract(game.founder_id, pid, "intel", 100, 12))


def test_a_chip_ahead_of_the_median_node_gains_quality_cap() -> None:
    from tst.sim.org.rules import org_view
    from tst.sim.products.phases import team_of

    def product_team(state, product, b, d):  # type: ignore[no-untyped-def]
        return team_of(state, org_view(state, product.company_id), product, b, d)

    lg = m21.loaded()
    b, d = lg.balance, lg.game_data
    game, pid = _chip_company(2023, "n3")
    product = game.state.product(pid)
    assert product is not None
    # 2023: the median is the node in volume three years before (7 nm in 2020... 5 nm from
    # April 2020), n3 is a generation or two ahead
    median = fm.median_node(game.state, b, d)
    tl = fm.timeline(game.state, b, d)
    ahead = tl.generation("n3") - tl.generation(median)
    assert ahead >= 1
    team = product_team(game.state, product, b, d)
    assert team.tech.cap_points >= 3 * ahead
    # the same chip on M12b's wafer (no node) gains nothing
    plain, pid2 = _chip_company(2023, None)
    p2 = plain.state.product(pid2)
    assert p2 is not None
    assert product_team(plain.state, p2, b, d).tech.cap_points < team.tech.cap_points


def test_a_fabless_chip_company_pays_what_it_did() -> None:
    """Nothing moves without a fab: M12b's wafer price and unit cost through 2025 (38.5 t6)."""
    lg = m21.loaded()
    b, d = lg.balance, lg.game_data
    for year in (2012, 2018, 2021, 2024):
        game, pid = _chip_company(year, None)
        product = game.state.product(pid)
        assert product is not None
        state = game.state
        from tst.sim.commodities import costs

        index = costs.cost_index(state, b.chips.good, d, b)
        assert chips.index_wafer_cents(state, "ai_accelerator", b, d, "tsmc") == (
            b.chips.types["ai_accelerator"].wafer_cents * index * 1.0
        )
        assert chips.unit_cost_cents(state, product, b, d) == chips.contract_unit_cents(
            state, product, b, d
        )
        assert chips.posted_unit_cents(state, product, b, d) == chips.unit_cost_cents(
            state, product, b, d
        )
        c = chips.wafer_contracts(state, pid)[0]
        from tst.sim.hardware.supply import delivered_share

        t = chips.type_of(product, d, b)
        share = delivered_share(state, b.chips.good, c.signed_turn, d, advanced=t.advanced_node)
        assert chips.wafers_delivered(state, c, b, d) == c.units * share


def test_a_fab_converts_to_the_next_node() -> None:
    lg = m21.loaded()
    b, d = lg.balance, lg.game_data
    game = m21.game_at(1, ym_to_turn(2017, 6))  # 10 nm in volume from October 2016
    fid = m21.build(game, "n16", "east_asia", 10_000)
    m21.play(game, 2)
    f = game.state.facility(fid)
    assert f is not None
    paid = f.capex_paid_cents
    assert game.act(UpgradeFab(game.founder_id, fid))
    fab = _fab(game, fid)
    assert fab.upgrade_node == "n10" and fab.upgrading(game.state.turn)
    new = quote(game.state, 1, "n10", "east_asia", 10_000, b, d).capex_cents
    assert fab.upgrade_cents >= round(new * b.fab.upgrade.capex_share)
    m21.play(game, b.fab.upgrade.months)
    fab = _fab(game, fid)
    m = fab.month
    assert m is not None and m.available == 0  # offline while it converts
    m21.play(game, 1)
    fab = _fab(game, fid)
    f = game.state.facility(fid)
    assert f is not None
    assert fab.node == "n10" and not fab.upgrading(game.state.turn)
    assert f.capex_paid_cents == paid + fab.parts[-1].cents
    assert len(fab.parts) == 2
