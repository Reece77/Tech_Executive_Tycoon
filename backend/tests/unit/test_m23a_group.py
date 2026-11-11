"""M23a sub-task 1 (formulas.md 31, 35.1, 36, 38.2; ADR-0020): one company owns an asset while its
group uses it. Codex review 5's findings 1, 4, 5 and 7, each reproduced first, and the shared
group-ownership layer that fixes them: a facility moves between group companies with every
kind-specific record, its crew and its books; a subsidiary's critical events reach the player;
every facility kind supplies any group company at the flow's transfer price."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tst.balance import m20, m21
from tst.balance.game import Game
from tst.sim.fabs import market as fm
from tst.sim.facilities import lifecycle
from tst.sim.ledger import CASH
from tst.sim.mining.actions import FoundSubsidiary, TransferAsset
from tst.sim.refining.plants import refinery_of
from tst.sim.research.models import ResearchLead
from tst.sim.state import CompanyState, with_person_state, with_research_lead

SUB_CENTS = 500_000_000_000  # $5B: a subsidiary that can pay book value for a fab


def _stage3(game: Game) -> None:
    player = game.state.player
    companies = tuple(
        replace(c, stage=max(3, c.stage)) if c.id == player.id else c for c in game.state.companies
    )
    game.state = replace(game.state, companies=companies)


def _energy(game: Game) -> None:
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))


def found(game: Game, name: str, region: str = "north_america", cents: int = SUB_CENTS) -> int:
    """A wholly owned subsidiary founded through the action; its company id."""
    _stage3(game)
    _energy(game)
    before = {c.id for c in game.state.companies}
    assert game.act(FoundSubsidiary(game.founder_id, name, region, cents)), dict(game.refused)
    (cid,) = {c.id for c in game.state.companies} - before
    return cid


def _owners(game: Game, fid: int) -> set[int]:
    """Every record's owner of a facility: the facility, and its fab or refinery record."""
    out = {game.state.facility(fid).company_id}  # type: ignore[union-attr]
    fab = fm.fab_of(game.state, fid)
    if fab is not None:
        out.add(fab.company_id)
    ref = refinery_of(game.state, fid)
    if ref is not None:
        out.add(ref.company_id)
    return out


# --- Finding 1: a transfer moves every record ------------------------------------------------


def test_a_transferred_fab_belongs_to_its_new_owner_in_every_record() -> None:
    game = m21.game_at(1, m21.ym_to_turn(2016, 1))
    fid = m21.build(game, "n28", "east_asia", 10_000)
    sub = found(game, "Wafer Works")
    _energy(game)
    assert game.act(TransferAsset(game.founder_id, sub, facility_id=fid)), dict(game.refused)
    assert _owners(game, fid) == {sub}
    f = game.state.facility(fid)
    assert f is not None
    # its crew moves with it: still fully staffed, on the new owner's payroll
    staff = lifecycle.staff_of(game.state, f, m21.loaded().balance)
    assert staff and all(e.company_id == sub for e in staff)
    assert lifecycle.staffing(game.state, f, m21.loaded().balance).coverage == pytest.approx(1)
    game.notes.pop(f"staff:{fid}")  # the fixture's top-up hires for the player
    before = dict(game.balances)
    game.turn()
    fab = fm.fab_of(game.state, fid)
    assert fab is not None and fab.month is not None and fab.month.available > 0
    # the month's operations, depreciation and slot sales post to the new owner only
    player = game.state.player.id

    def moved(cid: int, account: str) -> int:
        return game.balances.get((cid, account), 0) - before.get((cid, account), 0)

    for account in ("6700_depreciation", "4420_foundry_sales"):
        assert moved(sub, account) != 0 and moved(player, account) == 0, account
    assert moved(sub, "5000_cogs") > 0


def test_a_transferred_refinery_charges_its_new_owner() -> None:
    game = m20.game_at(1, m20.ym_to_turn(2015, 1))
    fid = m20.build(game, "silicon_smelter", "north_america", 25_000)
    m20.play(game, 2)
    sub = found(game, "Smelter Co")
    _energy(game)
    assert game.act(TransferAsset(game.founder_id, sub, facility_id=fid)), dict(game.refused)
    assert _owners(game, fid) == {sub}
    game.notes.pop(f"staff:{fid}")
    before = dict(game.balances)
    game.turn()
    ref = refinery_of(game.state, fid)
    assert ref is not None and ref.month is not None and ref.month.output > 0
    cogs = {
        cid
        for (cid, acc), v in game.balances.items()
        if acc == "5000_cogs" and v != before.get((cid, acc), 0)
    }
    assert sub in cogs and game.state.player.id not in cogs


def test_a_transfer_survives_a_cold_reload(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from tst.db.repository import create_save, ledger_balances, load_state, open_session
    from tst.db.state_io import sync_state

    lg = m21.loaded()
    path = create_save(
        "reload", 1, "funded_spinout", company_name="Lithos", data=lg, save_dir=tmp_path
    )
    with open_session(path) as session, session.begin():
        before = load_state(session)
        game = Game(
            lg, replace(before, turn=m21.ym_to_turn(2016, 1)), dict(ledger_balances(session))
        )
        game.balances[(1, CASH)] = game.balances.get((1, CASH), 0) + m21.RICH
        domain = lg.balance.refining.domain
        game.state = with_research_lead(game.state, ResearchLead(1, domain, m21.LEAD))
        fid = m21.build(game, "n28", "east_asia", 10_000)
        sub = found(game, "Reload Fab")
        _energy(game)
        assert game.act(TransferAsset(game.founder_id, sub, facility_id=fid))
        sync_state(session, before, game.state)
    with open_session(path) as session:
        state = load_state(session)
    fab = fm.fab_of(state, fid)
    f = state.facility(fid)
    assert fab is not None and f is not None and {fab.company_id, f.company_id} == {sub}


def _company(game: Game, cid: int) -> CompanyState:
    return game.state.company(cid)


def test_cash_moves_at_book_value_between_the_two() -> None:
    game = m21.game_at(1, m21.ym_to_turn(2016, 1))
    fid = m21.build(game, "n28", "east_asia", 10_000)
    sub = found(game, "Book Fab")
    f = game.state.facility(fid)
    assert f is not None
    book = f.book_value_cents
    player = game.state.player.id
    before_p, before_s = game.balances.get((player, CASH), 0), game.balances.get((sub, CASH), 0)
    _energy(game)
    assert game.act(TransferAsset(game.founder_id, sub, facility_id=fid))
    assert game.balances.get((player, CASH), 0) - before_p == book
    assert game.balances.get((sub, CASH), 0) - before_s == -book


# --- Finding 4: a subsidiary's critical events reach the player -------------------------------


def _always_incidents(loaded: m20.LoadedData) -> m20.LoadedData:
    b = loaded.balance
    recipes = dict(b.refining.recipes)
    recipes["ree_separator"] = recipes["ree_separator"].model_copy(update={"incident_rate": 1.0})
    incident = b.refining.incident.model_copy(update={"cover_base": 10.0})  # certain
    refining = b.refining.model_copy(update={"recipes": recipes, "incident": incident})
    return replace(loaded, balance=b.model_copy(update={"refining": refining}))


def _crew_to(game: Game, uid: int, cid: int) -> None:
    """A unit and its people employed by `cid` (a subsidiary's own crew)."""
    from tst.sim.state import with_employment, with_unit

    unit = game.state.unit(uid)
    assert unit is not None
    game.state = with_unit(game.state, replace(unit, company_id=cid))
    for e in list(game.state.employments):
        if e.unit_id == uid and e.status == "active":
            game.state = with_employment(game.state, replace(e, company_id=cid))


def test_a_subsidiarys_refinery_incident_reaches_the_player_and_closes() -> None:
    from tst.sim.actions.events import ChooseEvent
    from tst.sim.refining.actions import BuildRefinery

    game = m20.game_at(1, m20.ym_to_turn(2016, 1))
    game.loaded = _always_incidents(game.loaded)
    ib = game.loaded.balance.refining.incident
    sub = found(game, "Rare Earths Co", "oceania")
    _energy(game)
    fid = game.state.next_ids.facility
    assert game.act(
        BuildRefinery(game.founder_id, "ree_separator", "oceania", 1_000, company_id=sub)
    )
    uid = m20.hire_unit(game, "REE crew", 4, 4.0, seed=fid)
    _crew_to(game, uid, sub)
    f = game.state.facility(fid)
    assert f is not None and f.company_id == sub
    turn = game.state.turn
    game.state = m20.with_facility(  # built, paid for and staffed by the subsidiary's crew
        game.state,
        replace(
            f,
            unit_id=uid,
            ready_turn=turn,
            late_turn=turn,
            on_time=f.capacity,
            capex_paid_cents=f.capex_cents,
        ),
    )
    game.balances[(sub, CASH)] = game.balances.get((sub, CASH), 0) - f.capex_cents
    game.balances[(sub, m20.PPE)] = game.balances.get((sub, m20.PPE), 0) + f.capex_cents
    player = game.state.player.id
    event = None
    for _ in range(4):
        game.turn()
        event = next(
            (
                e
                for e in game.state.open_events(player)
                if e.template_id in ("refinery_fire", "chemical_release")
            ),
            None,
        )
        if event is not None:
            break
    assert event is not None and event.severity == "critical"
    ref = refinery_of(game.state, fid)
    assert ref is not None and ref.incident_turn == event.turn
    sub_cash, player_cash = game.balances.get((sub, CASH), 0), game.cash
    assert game.act(ChooseEvent(game.founder_id, event.id, "A"))  # stop and investigate
    ref = refinery_of(game.state, fid)
    assert ref is not None and ref.incident_turn is None and ref.stop_until is not None
    assert sub_cash - game.balances.get((sub, CASH), 0) == round(ib.fine_cents * ib.stop_fine_share)
    assert game.cash == player_cash  # the fine is the subsidiary's


# --- Finding 5: own-fab chips carry their origin's tariff --------------------------------------

US_CHIPS_2021 = 0.25  # tariffs.yaml us_301_chips from 2018-08 (independent of the engine)
US_SHARE = 0.88  # countries.yaml: the US's share of North America's demand


def _own_fab_chip(year: int, *, contract: bool) -> tuple[Game, int, int]:
    from tst.balance import m12b
    from tst.sim.chips import chips
    from tst.sim.state import with_production_contract

    lg = m21.loaded()
    b, d = lg.balance, lg.game_data
    turn = m21.ym_to_turn(year, 1)
    game = m21.game_at(1, turn)
    ref = d.category("chips_ai_accelerator").market("hyperscalers").reference_price_cents
    state, pid = m12b.product(
        game.state, "chips_ai_accelerator", "hyperscalers", ref, "Accel", root=True
    )
    if contract:  # TSMC (Taiwan: no US tariff) beside the fab
        price = chips.index_wafer_cents(state, "ai_accelerator", b, d, "tsmc", "n28")
        state = m12b.contract(state, pid, "wafer", 2_000, price, turn, 36)
        c = next(c for c in state.production_contracts if c.product_id == pid)
        state = with_production_contract(state, replace(c, node="n28"))
    game.state = state
    fid = m21.build(game, "n28", "east_asia", 10_000)  # east Asia's default country: China
    return game, pid, fid


@pytest.mark.parametrize("own", [100.0, 40.0])
def test_own_fab_chips_pay_their_fabs_countrys_tariff(own: float) -> None:
    """Codex's reproduction: a China fab, a production month of 100 chips sold to North America
    in 2021. Own-fab chips are taxed at their full cost a good die; with a TSMC contract beside
    the fab (Taiwan: untaxed), only the fab's share is."""
    from tst.sim.chips import chips
    from tst.sim.geopolitics import tariffs, world
    from tst.sim.hardware.models import ProductionMonth
    from tst.sim.state import with_product_segment

    lg = m21.loaded()
    b, d = lg.balance, lg.game_data
    game, pid, fid = _own_fab_chip(2021, contract=own < 100)
    f = game.state.facility(fid)
    assert f is not None and world.facility_country(game.state, f, d) == "china"
    m21.play(game, 2)
    state = replace(game.state, turn=game.state.turn - 1)  # the month just played
    seg = next(iter(state.segments_of(pid)))
    state = with_product_segment(state, replace(seg, customers=1_000.0))
    product = state.product(pid)
    assert product is not None
    contract = chips.contract_unit_cents(state, product, b, d)
    row = ProductionMonth(
        state.turn,
        pid,
        1,
        capacity=1_000.0,
        units=100.0,
        chip_cents=round((100 - own) * contract + own * b.chips.packaging_cents),
        fab_chips=own,
    )
    state = replace(state, production=(row,))
    fab_unit = chips.fab_unit_cents(state, product, b, d)
    assert fab_unit is not None
    expected = round(US_CHIPS_2021 * US_SHARE * own * fab_unit)
    assert tariffs.product_tariff_cents(state, product, b, d) == pytest.approx(expected, abs=1)


# --- Finding 7: materials flows feed the minority-fairness monitor -----------------------------


def _materials_flow(unfair_months: int, complaint: bool, unit_cents: float) -> tuple:  # type: ignore[type-arg]
    """An 80%-owned refiner selling 100 units of polysilicon to its parent this month, at
    `unit_cents` against a market of 100 cents (the lot taken after production)."""
    from tst.sim.group.models import TransferFlow
    from tst.sim.refining.models import OwnSupply
    from tst.sim.state import owner_at, with_flow, with_ownership

    game = m20.game_at(1, m20.ym_to_turn(2016, 1))
    sub = found(game, "Minority Refining")
    held = owner_at(game.state, sub)
    assert held is not None
    state = with_ownership(game.state, replace(held, stake_bp=8_000))
    player = state.player.id
    state = with_flow(
        state,
        TransferFlow(
            id=0,
            seller_id=sub,
            buyer_id=player,
            good="materials",
            kind="cost",
            unfair_months=unfair_months,
            complaint=complaint,
            complaint_turn=state.turn - 1 if complaint else None,
        ),
    )
    lot = OwnSupply(
        turn=state.turn,
        facility_id=999,
        seller_id=sub,
        buyer_id=player,
        good="polysilicon",
        volume=100.0,
        unit_cents=unit_cents,
        market_cents=100.0,
        taken=100.0,
    )
    return replace(state, own_supply=(lot,)), sub, player


def test_an_unfair_materials_price_raises_the_complaint_in_its_sixth_month() -> None:
    from tst.sim.group.transfer import transfer_month

    lg = m20.loaded()
    state, sub, _ = _materials_flow(5, False, 50.0)  # half of market: unfair
    out, _, logs = transfer_month(state, {}, {sub: 1_200_000}, lg.balance, lg.game_data)
    flow = next(f for f in out.transfer_flows if f.good == "materials")
    assert flow.unfair_months == 6 and flow.complaint
    assert flow.trailing[-1] == 5_000  # the month's transfer consideration enters the totals
    assert any(x.template == "minority_complaint_filed" for x in logs)


def test_a_materials_price_corrected_to_market_settles_the_complaint() -> None:
    from tst.sim.group.transfer import transfer_month

    lg = m20.loaded()
    unfair, sub, _ = _materials_flow(6, True, 50.0)
    out, _, _ = transfer_month(unfair, {}, {sub: 1_200_000}, lg.balance, lg.game_data)
    flow = next(f for f in out.transfer_flows if f.good == "materials")
    assert flow.complaint and flow.unfair_months == 7  # it stands while the price is unfair
    fair, sub, _ = _materials_flow(7, True, 100.0)
    out, _, logs = transfer_month(fair, {}, {sub: 1_200_000}, lg.balance, lg.game_data)
    flow = next(f for f in out.transfer_flows if f.good == "materials")
    assert not flow.complaint and flow.unfair_months == 0
    assert any(x.template == "minority_complaint_settled" for x in logs)


# --- The group chain: a wafer plant, a fab and a device company --------------------------------


def _ready_for(game: Game, fid: int, cid: int, uid: int) -> None:
    """A facility built for `cid`, paid for now and staffed by `cid`'s own crew `uid`."""
    from tst.sim.state import with_fab, with_facility

    f = game.state.facility(fid)
    assert f is not None and f.company_id == cid
    turn = game.state.turn
    fab = fm.fab_of(game.state, fid)
    if fab is not None:
        f = replace(f, ordered_turn=turn - fab.build_months, capex_paid_cents=f.capex_cents)
        game.state = with_fab(game.state, replace(fab, live_turn=turn, tools_turn=None))
    else:
        f = replace(
            f,
            ready_turn=turn,
            late_turn=turn,
            on_time=f.capacity,
            capex_paid_cents=f.capex_cents,
        )
    game.state = with_facility(game.state, replace(f, unit_id=uid))
    _crew_to(game, uid, cid)
    game.balances[(cid, CASH)] = game.balances.get((cid, CASH), 0) - f.capex_cents
    game.balances[(cid, m20.PPE)] = game.balances.get((cid, m20.PPE), 0) + f.capex_cents


def chain(
    seed: int = 1, start: tuple[int, int] = (2016, 1)
) -> tuple[Game, dict[str, int], dict[str, int]]:
    """The player (a device maker whose own SoC goes into its devices), a subsidiary with a
    28 nm fab making the SoC, and a subsidiary with a wafer plant making the fab's wafers."""
    from tst.sim.fabs.actions import BuildFab
    from tst.sim.refining.actions import BuildRefinery

    game, chip = m20.chip_game(seed, start)
    game.state = with_research_lead(
        game.state, ResearchLead(1, m20.loaded().balance.refining.domain, m21.LEAD)
    )
    fab_co = found(game, "Group Foundry", "east_asia")
    wafer_co = found(game, "Group Wafers", "east_asia")
    domain = m20.loaded().balance.refining.domain
    for cid in (fab_co, wafer_co):  # the subsidiaries' own process research
        game.state = with_research_lead(game.state, ResearchLead(cid, domain, m21.LEAD))
    _energy(game)
    fab_id = game.state.next_ids.facility
    assert game.act(BuildFab(game.founder_id, "n28", "east_asia", 10_000, company_id=fab_co)), dict(
        game.refused
    )
    _ready_for(game, fab_id, fab_co, m21.hire_unit(game, "Foundry crew", 10, seed=fab_id))
    _energy(game)
    plant_id = game.state.next_ids.facility
    assert game.act(
        BuildRefinery(game.founder_id, "wafer_plant", "east_asia", 120_000, company_id=wafer_co)
    ), dict(game.refused)
    _ready_for(game, plant_id, wafer_co, m20.hire_unit(game, "Wafer crew", 2, seed=plant_id))
    companies = {"device": game.state.player.id, "fab": fab_co, "wafers": wafer_co}
    return game, companies, {"chip": chip, "fab": fab_id, "plant": plant_id}


def _delta(game: Game, before: dict[tuple[int, str], int], cid: int, account: str) -> int:
    return game.balances.get((cid, account), 0) - before.get((cid, account), 0)


def test_a_group_chain_supplies_at_transfer_price_on_the_right_entities() -> None:
    from tst.sim.ledger import INTERCOMPANY_PURCHASES as BUY
    from tst.sim.ledger import INTERCOMPANY_SALES as SELL

    game, co, ids = chain()
    for _ in range(3):  # the fab's first month, then its wafers come from the group
        game.turn()
    before = dict(game.balances)
    game.turn()
    month = replace(game.state, turn=game.state.turn - 1)
    fab = fm.fab_of(month, ids["fab"])
    assert fab is not None and fab.month is not None
    # the fab ran starts for the device company's SoC and was paid at cost (the default flow)
    rows = {cid: (n, price) for cid, n, price, _ in fab.month.group}
    assert co["device"] in rows and rows[co["device"]][0] > 0
    starts, price = rows[co["device"]]
    assert price == round(starts * fab.month.cost_per_start_cents)

    # the wafer plant's wafers went into the fab's starts (and the SoC's TSMC starts) at the
    # plant's transfer price (cost)
    def paid(buyer: int, *, fab_lots: bool) -> int:
        return sum(
            round(s.taken * s.unit_cents)
            for s in month.own_supply
            if s.seller_id == co["wafers"]
            and s.buyer_id == buyer
            and (s.fab_id is not None) == fab_lots
            and s.turn == month.turn
        )

    to_fab, to_device = paid(co["fab"], fab_lots=True), paid(co["device"], fab_lots=False)
    assert to_fab > 0
    assert _delta(game, before, co["device"], BUY) == price + to_device
    assert _delta(game, before, co["fab"], BUY) == to_fab
    assert _delta(game, before, co["fab"], SELL) == -price
    assert _delta(game, before, co["wafers"], SELL) == -(to_fab + to_device)
    # each plant's costs stay with its owner: nothing of the fab or the wafer plant on the device
    # company, nothing of the wafer plant on the fab's
    assert _delta(game, before, co["device"], "6700_depreciation") == 0
    assert _delta(game, before, co["fab"], "6700_depreciation") > 0
    assert _delta(game, before, co["wafers"], "6700_depreciation") > 0
    # inside the group the two sides mirror: consolidation removes them
    sold = sum(_delta(game, before, c, SELL) for c in co.values())
    bought = sum(_delta(game, before, c, BUY) for c in co.values())
    assert sold + bought == 0
