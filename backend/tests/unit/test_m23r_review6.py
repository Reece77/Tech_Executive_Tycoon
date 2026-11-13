"""M23r (Codex review 6; docs/tasks/M23r-review-6-fixes.md): each finding's regression test, written
first and seen failing on m23a-done."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tst.balance import m19
from tst.loader import LoadedData
from tst.sim.ledger import EXPLORATION
from tst.sim.mining.actions import BuildMine, CloseMine
from tst.sim.state import GameState, with_mine


def reload(state: GameState, data: LoadedData, tmp_path: Path, name: str = "reload") -> GameState:
    """`state` written into a fresh save and read back cold (a new session)."""
    from tst.db.repository import create_save, load_state, open_session
    from tst.db.state_io import read_meta, sync_state

    path = create_save(
        name, 1, "funded_spinout", company_name="Reload", data=data, save_dir=tmp_path
    )
    with open_session(path) as session, session.begin():
        sync_state(session, load_state(session), state)
        read_meta(session).current_turn = state.turn
    with open_session(path) as session:
        return load_state(session)


# --- Finding 1: depletion across mine lifetimes ------------------------------------------------


def test_repeated_rebuilds_deplete_the_deposit_once(loaded: LoadedData, tmp_path: Path) -> None:
    """Codex's reproduction carried to four lifetimes, with a cold reload before each rebuild: the
    deposit's ore extracted plus the ore left always equals its original tonnage, and the
    project's exploration spend is capitalized once, with the first mine."""
    run = m19.miner(loaded, 7)
    mine = m19.build(run, "copper")
    original = mine.hidden_ore_mt
    project_spend = mine.moved_cents
    assert project_spend > 0
    exploration = run.balances.get((m19.PLAYER, EXPLORATION), 0)
    for lifetime, share in enumerate((0.1, 0.25, 0.45), start=2):
        now = m19.mine_of(run, mine.id)
        extracted = original * share  # the deposit's cumulative extraction so far
        run.state = with_mine(run.state, replace(now, ore_mined_mt=extracted))
        assert run.act(CloseMine(run.founder, mine.id)) is not None, run.log
        run.state = reload(run.state, loaded, tmp_path, f"life{lifetime}")
        assert run.act(BuildMine(run.founder, now.project_id)) is not None, run.log
        mine = run.state.mines[-1]
        assert mine.ore_mined_mt == pytest.approx(extracted), lifetime
        assert mine.ore_mined_mt + mine.hidden_ore_left_mt == pytest.approx(original), lifetime
        lifetimes = [m for m in run.state.mines if m.project_id == now.project_id]
        assert len(lifetimes) == lifetime
        assert sum(m.moved_cents for m in lifetimes) == project_spend
        assert run.balances.get((m19.PLAYER, EXPLORATION), 0) == exploration


# --- Finding 2's check on mines and refineries ------------------------------------------------


def test_a_subsidiarys_mine_counts_the_crew_the_founder_gives_it(loaded: LoadedData) -> None:
    """The matching gap on mines: a player unit put on a subsidiary's mine moves to the mine's
    owner with its people, so the mine counts its crew and the owner pays it."""
    from tst.sim.facilities import lifecycle
    from tst.sim.mining.actions import FoundSubsidiary, StaffMine, TransferAsset

    run = m19.miner(loaded, 7)
    mine = m19.build(run, "copper")
    before = {c.id for c in run.state.companies}
    assert run.act(FoundSubsidiary(run.founder, "Copper Co", mine.region, 50_000_000_000)), run.log
    (sub,) = {c.id for c in run.state.companies} - before
    assert run.act(TransferAsset(run.founder, sub, facility_id=mine.id)), run.log
    assert run.act(StaffMine(run.founder, mine.id, None)), run.log
    need = len(lifecycle.staff_of(run.state, run.state.facility(mine.id), loaded.balance))  # type: ignore[arg-type]
    assert need == 0
    uid = m19.add_engineers(run, 40, 12.0)  # the player's
    assert run.act(StaffMine(run.founder, mine.id, uid)), run.log
    f = run.state.facility(mine.id)
    assert f is not None and f.company_id == sub and f.unit_id == uid
    unit = run.state.unit(uid)
    assert unit is not None and unit.company_id == sub
    crew = lifecycle.staff_of(run.state, f, loaded.balance)
    assert len(crew) == 40 and all(e.company_id == sub for e in crew)


def test_the_founder_staffs_and_sells_a_subsidiarys_refinery() -> None:
    """The matching gap on refineries: a refinery transferred to a subsidiary is staffed and sold
    by the founder; the proceeds are the owner's."""
    from tests.unit.test_m23a_group import _energy, found
    from tst.balance import m20
    from tst.sim.actions.facilities import SellFacility, StaffFacility
    from tst.sim.ledger import CASH

    game = m20.game_at(1, m20.ym_to_turn(2015, 1))
    fid = m20.build(game, "silicon_smelter", "north_america", 25_000)
    m20.play(game, 2)
    sub = found(game, "Smelter Co")
    _energy(game)
    from tst.sim.mining.actions import TransferAsset

    assert game.act(TransferAsset(game.founder_id, sub, facility_id=fid)), dict(game.refused)
    _energy(game)
    assert game.act(StaffFacility(game.founder_id, fid, None)), dict(game.refused)
    sub_cash, player_cash = game.balances.get((sub, CASH), 0), game.cash
    _energy(game)
    assert game.act(SellFacility(game.founder_id, fid)), dict(game.refused)
    f = game.state.facility(fid)
    assert f is not None and f.status == "closed"
    assert game.balances.get((sub, CASH), 0) > sub_cash and game.cash == player_cash


# --- Finding 3: a fab's foundry contracts move with it --------------------------------------------


def test_a_transferred_fabs_foundry_contracts_are_its_new_owners(tmp_path: Path) -> None:
    """Codex's reproduction: a 24-month, 3,000-start foundry contract on company 1's fab, the fab
    transferred to an 80%-owned subsidiary. Deliveries, revenue, the termination quote and its
    fee are the subsidiary's, also after a cold reload."""
    from tests.unit.test_m23a_group import _energy, found
    from tst.balance import m21
    from tst.sim.contracts import termination as ct
    from tst.sim.contracts.termination import TerminateContract
    from tst.sim.fabs import foundry
    from tst.sim.fabs import market as fm
    from tst.sim.ledger import CASH
    from tst.sim.mining.actions import TransferAsset
    from tst.sim.state import owner_at, with_ownership

    lg = m21.loaded()
    b, d = lg.balance, lg.game_data
    game = m21.game_at(1, m21.ym_to_turn(2016, 1))
    fid = m21.build(game, "n28", "east_asia", 10_000)
    m21.play(game)
    fab = fm.fab_of(game.state, fid)
    assert fab is not None
    price = foundry.slot_price_cents(game.state, fab, b, d) * 0.5
    customer = foundry.customers(d)[0]
    _energy(game)
    sign = foundry.SignFoundryContract(game.founder_id, fid, customer, 3_000.0, 24, price)
    assert game.act(sign), dict(game.refused)
    (contract,) = game.state.foundry_contracts
    player = game.state.player.id

    def sales(cid: int) -> int:
        return game.balances.get((cid, "4420_foundry_sales"), 0)

    before = sales(player)
    m21.play(game)
    assert sales(player) < before  # credit: the player's fab delivered and was paid
    sub = found(game, "Foundry Co")
    held = owner_at(game.state, sub)
    assert held is not None
    game.state = with_ownership(game.state, replace(held, stake_bp=8_000))  # 20% minority
    _energy(game)
    assert game.act(TransferAsset(game.founder_id, sub, facility_id=fid)), dict(game.refused)
    moved = next(c for c in game.state.foundry_contracts if c.id == contract.id)
    assert moved.company_id == sub
    assert ct.quote(game.state, "foundry", contract.id, b, d).company_id == sub
    player_sales, sub_sales = sales(player), sales(sub)
    m21.play(game)
    delivered = next(c for c in game.state.foundry_contracts if c.id == contract.id).delivered
    assert delivered > 0
    assert sales(player) == player_sales and sales(sub) < sub_sales
    cold = reload(game.state, lg, tmp_path)
    again = next(c for c in cold.foundry_contracts if c.id == contract.id)
    assert again.company_id == sub
    q = ct.quote(cold, "foundry", contract.id, b, d)
    assert q.company_id == sub and q.fee_cents > 0
    sub_cash, player_cash = game.balances.get((sub, CASH), 0), game.cash
    _energy(game)
    assert game.act(TerminateContract(game.founder_id, "foundry", contract.id)), game.refused
    assert sub_cash - game.balances.get((sub, CASH), 0) == q.cash_cents
    assert game.cash == player_cash


# --- Finding 5: foundry-contract money is exact ---------------------------------------------------


def _foundry_month(own: float) -> tuple[int, float, float, int]:
    """A live 10,000-start fab with an accepted contract for 100 starts at 0.545 cents a start,
    settled with `own` starts used by the group: (revenue posted to 4420, contracted starts,
    spot starts, the month's revenue_cents)."""
    from tests.unit.test_m23a_group import _energy
    from tst.balance import m21
    from tst.sim.fabs import foundry
    from tst.sim.fabs import market as fm
    from tst.sim.fabs.plants import settle_fabs
    from tst.sim.ledger import FOUNDRY_SALES
    from tst.sim.state import with_fab

    lg = m21.loaded()
    b, d = lg.balance, lg.game_data
    game = m21.game_at(1, m21.ym_to_turn(2016, 1))
    fid = m21.build(game, "n28", "east_asia", 10_000)
    m21.play(game)
    _energy(game)
    customer = foundry.customers(d)[0]
    assert game.act(foundry.SignFoundryContract(game.founder_id, fid, customer, 100.0, 12, 0.545))
    fab = fm.fab_of(game.state, fid)
    assert fab is not None and fab.month is not None
    month = replace(fab.month, turn=game.state.turn, available=10_000.0)
    state = with_fab(game.state, replace(fab, month=month))
    state, entries = settle_fabs(state, {fid: own}, b, d)
    posted = -sum(line.amount for e in entries for line in e.lines if line.account == FOUNDRY_SALES)
    after = fm.fab_of(state, fid)
    assert after is not None and after.month is not None
    m = after.month
    return posted, m.contracted, m.sold - m.contracted, m.revenue_cents


def test_a_half_cent_of_contracted_revenue_rounds_half_even_once() -> None:
    """Codex's reproduction: 9,900 of 10,000 starts used inside the group, the 100 left all
    contracted at 0.545 cents, no spot sales: exactly 54.5 cents, posted as 54 (half to even),
    not the 55 that binary floating point gave."""
    posted, contracted, spot, revenue = _foundry_month(9_900.0)
    assert contracted == 100.0 and spot == 0.0
    assert posted == revenue == 54


def test_mixed_contracted_and_spot_revenue_matches_a_rational_reference() -> None:
    """Contracted and spot revenue are summed exactly and rounded once at posting."""
    from fractions import Fraction

    from tst.balance import m21
    from tst.sim.fabs import foundry
    from tst.sim.fabs import market as fm
    from tst.sim.money import exact

    posted, contracted, spot, revenue = _foundry_month(9_700.0)
    assert contracted == 100.0 and spot > 0
    lg = m21.loaded()
    # the reference: the same month's slot price, every product exact, one rounding
    game = m21.game_at(1, m21.ym_to_turn(2016, 1))
    fid = m21.build(game, "n28", "east_asia", 10_000)
    m21.play(game)
    fab = fm.fab_of(game.state, fid)
    assert fab is not None
    slot = foundry.slot_price_cents(game.state, fab, lg.balance, lg.game_data)
    expected = round(Fraction(100) * Fraction(545, 1000) + exact(spot) * exact(slot))
    assert posted == revenue == expected
