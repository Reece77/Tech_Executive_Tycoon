"""M20 (formulas.md 36): refineries on the generic facility lifecycle, a plant's month, the
group's own supply, own wafers in the chip cost path, power curbs and incidents. Each test is a
real game (tst.balance.m20) with a plant ordered through `build_refinery`."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tst.balance import m20
from tst.loader import LoadedData
from tst.sim.actions.events import ChooseEvent
from tst.sim.actions.facilities import BuildFacility
from tst.sim.calendar import ym_to_turn
from tst.sim.chips import chips
from tst.sim.errors import FacilityRuleError, RefiningRuleError
from tst.sim.refining.actions import BuildRefinery, SignRefiningDeal, overrun_share
from tst.sim.refining.plants import refinery_of


def _plant(game: m20.Game, fid: int):  # type: ignore[no-untyped-def]
    ref = refinery_of(game.state, fid)
    assert ref is not None
    return ref


def test_build_quotes_an_estimate_and_hides_the_overrun() -> None:
    b = m20.loaded().balance
    game = m20.game_at(1, ym_to_turn(2015, 1))
    fid = m20.build(game, "silicon_smelter", "north_america", 25_000, ready_now=False)
    ref = _plant(game, fid)
    f = game.state.facility(fid)
    assert f is not None and f.kind == "silicon_smelter" and f.status == "building"
    share = f.capex_cents / ref.estimate_cents - 1
    assert b.refining.overrun.lo <= share <= b.refining.overrun.hi
    assert share == pytest.approx(
        overrun_share(replace(game.state, turn=f.ordered_turn), fid, b), abs=1e-6
    )
    assert f.ready_turn == f.ordered_turn + b.facility.kinds["silicon_smelter"].build_months
    m20.months(game, 2)
    f = game.state.facility(fid)
    assert f is not None and 0 < f.capex_paid_cents < f.capex_cents


def test_the_overrun_is_seeded() -> None:
    a = m20.game_at(3, 70)
    b = m20.game_at(3, 70)
    fa = m20.build(a, "li_converter", "latin_america", 10_000, ready_now=False)
    fb = m20.build(b, "li_converter", "latin_america", 10_000, ready_now=False)
    assert a.state.facility(fa) == b.state.facility(fb)


def test_refinery_kinds_need_their_own_action() -> None:
    game = m20.game_at(1, 60)
    with pytest.raises(FacilityRuleError):
        from tst.sim.actions import apply_action
        from tst.sim.rng import RngFactory

        lg = m20.loaded()
        apply_action(
            game.state,
            BuildFacility(game.founder_id, "silicon_smelter", "europe", 10_000),
            RngFactory(1),
            lg.balance,
            lg.game_data,
            game.balances,
            seq=1,
        )


def test_a_byproduct_line_needs_a_host_plant() -> None:
    game = m20.game_at(1, 60)
    assert not game.act(BuildRefinery(game.founder_id, "byproduct_gallium", "east_asia", 25))
    host = m20.build(game, "silicon_smelter", "east_asia", 10_000)
    line = m20.build(game, "byproduct_gallium", "east_asia", 25)
    assert _plant(game, line).host_id == host


def test_a_staffed_plant_makes_its_capacity_and_unstaffed_makes_nothing() -> None:
    b = m20.loaded().balance
    game = m20.game_at(1, ym_to_turn(2015, 1) - 1)
    fid = m20.build(game, "silicon_smelter", "north_america", 10_000)
    m20.months(game, 8)  # past the 6-month ramp
    pm = _plant(game, fid).month
    assert pm is not None
    rel = 0.7 + 0.3 * m20.SKILL / 20  # 22.2 at full coverage
    assert pm.output == pytest.approx(10_000 / 12 * rel, rel=0.02)  # skill grows a little
    assert pm.input_spot == pytest.approx(pm.output * 2.5)
    assert pm.to_spot == pytest.approx(pm.output)
    assert pm.power_cents == round(pm.output * 12 * b.refining.power_cents_per_mwh)
    f = game.state.facility(fid)
    assert f is not None
    game.state = m20.with_facility(game.state, replace(f, unit_id=None))
    m20.months(game, 1)
    pm = _plant(game, fid).month
    assert pm is not None and pm.output == 0 and pm.fixed_cents > 0


def test_power_is_the_difference_between_regions() -> None:
    cheap = m20.game_at(1, ym_to_turn(2016, 1) - 1)
    europe = m20.game_at(1, ym_to_turn(2016, 1) - 1)
    fc = m20.build(cheap, "silicon_smelter", "south_southeast_asia", 10_000)
    fe = m20.build(europe, "silicon_smelter", "europe", 10_000)
    m20.months(cheap, 8)
    m20.months(europe, 8)
    pc, pe = _plant(cheap, fc).month, _plant(europe, fe).month
    assert pc is not None and pe is not None
    assert pc.power_index == pytest.approx(0.85) and pe.power_index == pytest.approx(1.5)
    per_tonne = (pe.power_cents / pe.output) - (pc.power_cents / pc.output)
    assert per_tonne == pytest.approx(12 * 6800 * 0.65, rel=1e-3)
    assert pc.unit_cost_cents < pe.unit_cost_cents


def test_semiconductor_polysilicon_halves_its_yield_below_the_process_level() -> None:
    b = m20.loaded().balance
    game = m20.game_at(1, ym_to_turn(2015, 1) - 1)  # the process baseline is 29-30, below 40
    fid = m20.build(game, "poly_plant_semi", "north_america", 1_000)
    m20.months(game, 20)
    pm = _plant(game, fid).month
    assert pm is not None
    assert pm.yield_ == pytest.approx(0.8 * b.refining.semi_low_yield)
    assert pm.input_spot == pytest.approx(pm.output * 0.0025)


def test_a_smelter_feeds_the_groups_poly_plant_first() -> None:
    game, _ = m20.chip_game(1, (2015, 1))
    smelter = m20.build(game, "silicon_smelter", "east_asia", 10_000)
    poly = m20.build(game, "poly_plant_semi", "east_asia", 1_000)
    m20.months(game, 20)
    s, p = _plant(game, smelter).month, _plant(game, poly).month
    assert s is not None and p is not None
    assert p.input_group == pytest.approx(min(s.output, p.input_group + p.input_spot))
    assert s.to_group == pytest.approx(p.input_group)
    assert p.input_spot == pytest.approx(0)


def test_own_wafers_cut_the_chip_wafer_price_and_keep_full_allocation() -> None:
    b, d = m20.loaded().balance, m20.loaded().game_data
    # contracts signed in the 2021 shortage: a spot buyer gets 70% of its starts (26.8)
    with_plant, pid = m20.chip_game(1, (2021, 3))
    m20.build(with_plant, "wafer_plant", "east_asia", 120_000)
    without, pid2 = m20.chip_game(1, (2021, 3))
    starts = chips.wafer_contracts(with_plant.state, pid)[0].units
    while with_plant.state.turn <= ym_to_turn(2022, 4):  # past the 12-month ramp
        with_plant.turn()
        without.turn()
    # between turns the state is the next month's; the lots belong to the month just played
    s1 = replace(with_plant.state, turn=with_plant.state.turn - 1)
    s2 = replace(without.state, turn=without.state.turn - 1)
    vol, price, market = chips.own_wafers(s1, pid)
    assert vol == pytest.approx(starts) and price < market
    p1, p2 = s1.product(pid), s2.product(pid2)
    assert p1 is not None and p2 is not None
    w1 = chips.wafer_cents(s1, p1, b, d)
    w2 = chips.wafer_cents(s2, p2, b, d)
    assert w2 - w1 == pytest.approx(market - price, rel=1e-6)
    c1 = chips.wafer_contracts(s1, pid)[0]
    c2 = chips.wafer_contracts(s2, pid2)[0]
    assert chips.wafers_delivered(s1, c1, b, d) == pytest.approx(starts)
    assert chips.wafers_delivered(s2, c2, b, d) == pytest.approx(0.7 * starts)  # 2021 (26.8)


def test_a_fabless_company_without_a_wafer_plant_pays_what_it_did() -> None:
    """36.2: with no own supply, the chip's wafer price is M12b's: the contracts' locked prices
    weighted by starts. A refinery that makes no wafers changes nothing either."""
    b, d = m20.loaded().balance, m20.loaded().game_data
    plain, pid = m20.chip_game(2, (2018, 1))
    other, pid2 = m20.chip_game(2, (2018, 1))
    m20.build(other, "li_converter", "latin_america", 10_000)
    m20.months(plain, 4)
    m20.months(other, 4)
    for game, product_id in ((plain, pid), (other, pid2)):
        p = game.state.product(product_id)
        assert p is not None
        contracts = chips.wafer_contracts(game.state, product_id)
        expected = sum(c.units * c.price_cents for c in contracts) / sum(c.units for c in contracts)
        assert chips.wafer_cents(game.state, p, b, d) == expected
    a = plain.state.production_of(pid)
    c = other.state.production_of(pid2)
    assert a is not None and c is not None
    assert (a.units, a.cogs_cents) == (c.units, c.cogs_cents)


def test_the_2021_power_curb_hits_east_asian_smelters() -> None:
    game = m20.game_at(1, ym_to_turn(2021, 1))
    east = m20.build(game, "silicon_smelter", "east_asia", 10_000)
    west = m20.build(game, "silicon_smelter", "north_america", 10_000)
    september = ym_to_turn(2021, 9)
    while game.state.turn <= september:
        game.turn()
    e, w = _plant(game, east), _plant(game, west)
    assert e.curbed(september) and e.curb_run == pytest.approx(0.6)
    assert e.curb_until == ym_to_turn(2021, 10)
    assert not w.curbed(september)
    assert e.month is not None and w.month is not None
    assert e.month.output == pytest.approx(0.6 * w.month.output, rel=0.02)
    while game.state.turn <= ym_to_turn(2021, 11):
        game.turn()
    e = _plant(game, east)
    assert not e.curbed(ym_to_turn(2021, 11))
    assert e.month is not None and e.month.output > 0.9 * w.month.output


def _always_incidents(loaded: LoadedData) -> LoadedData:
    b = loaded.balance
    recipes = dict(b.refining.recipes)
    recipes["ree_separator"] = recipes["ree_separator"].model_copy(update={"incident_rate": 1.0})
    incident = b.refining.incident.model_copy(update={"cover_base": 10.0})  # certain
    refining = b.refining.model_copy(update={"recipes": recipes, "incident": incident})
    return replace(loaded, balance=b.model_copy(update={"refining": refining}))


@pytest.mark.parametrize("step", ["A", "B", "C"])
def test_an_incident_is_a_critical_event_answered_by_the_engine(step: str) -> None:
    """36.4: brand and credibility fall at the incident; stop halves the fine and stops the
    plant for two months; compensate pays more and raises Beloved; contest risks legal costs
    and raises Ruthless."""
    from tst.sim.press.moments import credibility

    game = m20.game_at(1, ym_to_turn(2016, 1))
    game.loaded = _always_incidents(game.loaded)
    b = game.loaded.balance
    ib = b.refining.incident
    fid = m20.build(game, "ree_separator", "oceania", 1_000, skill=4.0)
    cred = credibility(game.state, m20.PLAYER, b)
    event = None
    for _ in range(4):
        game.turn()
        event = next(
            (
                e
                for e in game.state.open_events(m20.PLAYER)
                if e.template_id in ("refinery_fire", "chemical_release")
            ),
            None,
        )
        if event is not None:
            break
    assert event is not None and event.severity == "critical"
    assert credibility(game.state, m20.PLAYER, b) < cred
    assert _plant(game, fid).incident_turn == event.turn
    cash = game.cash
    assert game.act(ChooseEvent(game.founder_id, event.id, step))
    ref = _plant(game, fid)
    assert ref.incident_turn is None
    paid = cash - game.cash
    if step == "A":
        assert paid == round(ib.fine_cents * ib.stop_fine_share)
        assert ref.stopped(game.state.turn) and ref.stop_until == game.state.turn + 1
    elif step == "B":
        assert paid == ib.fine_cents + ib.compensate_cents
    else:
        assert paid in (ib.fine_cents, ib.fine_cents + ib.contest_legal_cents)


def test_refinery_contracts_lock_the_price_and_take_first() -> None:
    game = m20.game_at(1, ym_to_turn(2016, 1) - 1)
    fid = m20.build(game, "li_converter", "latin_america", 10_000)
    m20.months(game, 20)
    assert game.act(SignRefiningDeal(game.founder_id, "buy", "lithium_concentrate", 12, 200.0))
    assert game.act(SignRefiningDeal(game.founder_id, "sell", "lithium_carbonate", 12, 100.0))
    m20.months(game, 2)
    pm = _plant(game, fid).month
    assert pm is not None
    assert pm.input_contract == pytest.approx(200.0)
    assert pm.to_contract == pytest.approx(100.0)
    assert pm.to_spot == pytest.approx(pm.output - 100.0)
    with pytest.raises(RefiningRuleError):
        from tst.sim.refining.actions import sign_deal

        sign_deal(
            game.state,
            SignRefiningDeal(game.founder_id, "buy", "copper", 12, 1.0),
            game.loaded.balance,
            game.loaded.game_data,
        )


def test_a_group_mine_feeds_the_refinery_in_place_of_spot() -> None:
    """At M19's merge (36.1, 35.3): a lithium mine's output replaces the converter's spot
    concentrate this month (its purchase reversed at the concentrate price; inside one company
    no transfer), and next month that volume keeps 100% allocation."""
    from tst.sim.ledger import CASH, COGS
    from tst.sim.refining.mines import feed_from_mine, start_month

    lg = m20.loaded()
    game = m20.game_at(1, ym_to_turn(2016, 1) - 1)
    fid = m20.build(game, "li_converter", "latin_america", 10_000)
    m20.play(game, 20)
    state = replace(game.state, turn=game.state.turn - 1)  # the month just played
    pm = _plant(game, fid).month
    assert pm is not None and pm.input_spot > 0
    tonnes = 100.0  # of mine product: concentrate for 100 t of carbonate
    state, taken, entries = feed_from_mine(
        state,
        m20.PLAYER,
        "lithium_carbonate",
        tonnes,
        500_000,
        "cost",
        None,
        {m20.PLAYER},
        "Salar mine",
        lg.balance,
        lg.game_data,
    )
    assert taken == pytest.approx(tonnes)
    ref = refinery_of(state, fid)
    assert ref is not None and ref.month is not None
    conc = tonnes * lg.balance.refining.recipes["li_converter"].input_per_output
    assert ref.month.input_spot == pytest.approx(pm.input_spot - conc)
    assert ref.month.input_group == pytest.approx(pm.input_group + conc)
    assert ref.mine_fed == pytest.approx(conc)
    cash = sum(x.amount for e in entries for x in e.lines if x.account == CASH)
    cogs = sum(x.amount for e in entries for x in e.lines if x.account == COGS)
    assert cash == -cogs > 0  # one company: only the spot purchase is reversed
    assert all(not e.lines or {x.account for x in e.lines} == {CASH, COGS} for e in entries)
    nxt = start_month(state)
    ref = refinery_of(nxt, fid)
    assert ref is not None and ref.mine_protected == pytest.approx(conc) and ref.mine_fed == 0
    # a mine elsewhere in nobody's group feeds nothing
    _, taken, _ = feed_from_mine(
        state,
        99,
        "lithium_carbonate",
        tonnes,
        500_000,
        "cost",
        None,
        {99},
        "Rival",
        lg.balance,
        lg.game_data,
    )
    assert taken == 0
