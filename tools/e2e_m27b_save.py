"""Create the M27b practice save and its Playwright saves (formulas.md 40.7; an e2e fixture
tool). Never used by the game.

- `chain <save dir> <name>` (Reece's `pt-auto-chain`): an integrator in January 2019 with a
  live handset on a contract manufacturer (too small for its demand, so its cover and its
  inputs' cover are short), its own 28 nm fab in East Asia (live, staffed), and a mining
  subsidiary, Minerals, running a copper mine in Latin America (built on a permitted project,
  staffed by its own crew) under its own CEO and a plant manager. Senior leads for every chain
  area (manufacturing engineer, procurement manager, geologist, plant manager, fab manager,
  public policy manager, corporate development manager) and a COO, CTO and CFO; nothing
  automated yet.
- `corp <save dir> <name>`: `chain` at a quarter's first month with diligence finished on the
  best related target: given Corporate development with a budget, the lead pitches a bid (a
  one-off proposal) at the next Continue.

The months in memory are played with the engine (tst.balance.game); the ledger is written as
one entry per company netting what they posted (every entry balances, so each net does too).

Usage: uv run --project backend python tools/e2e_m27b_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Final

from tst.balance import fixtures, m12b, m21
from tst.balance.game import PLAYER, Game, start_game
from tst.balance.m27b import add_staff_at
from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, ledger_balances, load_state, open_session
from tst.db.state_io import read_meta, sync_state
from tst.loader import LoadedData, load_all
from tst.sim.actions import AppointExecutive
from tst.sim.calendar import ym_to_turn
from tst.sim.exploration import pipeline as xp
from tst.sim.exploration.pipeline import TakeLicence
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry, LedgerLine
from tst.sim.mining import formulas as mf
from tst.sim.mining.actions import BuildMine, FoundSubsidiary, StaffMine, TransferAsset
from tst.sim.org.models import OrgUnit
from tst.sim.rng import RngFactory
from tst.sim.research.models import ResearchLead
from tst.sim.state import (
    reach_stage,
    with_company,
    with_person_state,
    with_research_lead,
    with_unit,
)

SEED: Final = 27
COMPANY: Final = "Lattice"
START: Final = ym_to_turn(2019, 1)
RICH: Final = 2_000_000_000_000  # $20B of funding (equity): a fab and a mine
SUB_CENTS: Final = 300_000_000_000  # $3B: the subsidiary's capital
DEVICE_UNITS: Final = 2_000  # the handset's contract: well short of its demand
HOLES: Final = 40
LEADS: Final = (
    "manufacturing_engineer",
    "procurement_manager",
    "geologist",
    "plant_manager",
    "fab_manager",
    "public_policy_manager",
    "corporate_development_manager",
)
SEATS: Final = (("coo", "operations_manager"), ("cto", "software_engineer"), ("cfo", "finance_manager"))
LEAD_SKILL: Final = 14.0


def _energy(game: Game) -> None:
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))


def _act(game: Game, action: object) -> None:
    _energy(game)
    if not game.act(action):  # type: ignore[arg-type]
        raise RuntimeError(f"{action} was refused: {dict(game.refused)}")


def _permitted(game: Game, commodity: str, region: str) -> int:
    """A licence on a block holding the commodity, taken to a definitive study and a permit by
    M18's own functions (only the months between are skipped, as M19's fixture does)."""
    b, d = game.loaded.balance, game.loaded.game_data
    blk = next(
        x
        for x in game.state.geo_blocks
        if x.true_commodity == commodity
        and x.region == region
        and xp.holder_of(game.state, x.region, x.index) is None
    )
    _act(game, TakeLicence(game.founder_id, blk.region, blk.index))
    p = game.state.projects[-1]
    p = replace(p, commodity=commodity, reading="strong", kind=blk.true_kind or "hard_rock")
    rng = RngFactory(SEED)
    p = xp.sample_result(game.state, p, rng, b, d)
    game.state = xp.with_project(game.state, p)
    holes = tuple(xp.drill_hole(game.state, p, n, rng, b, d) for n in range(1, HOLES + 1))
    game.state = replace(game.state, holes=(*game.state.holes, *holes))
    p = xp.estimate_result(game.state, p, rng, b, d)
    p = xp.study_result(game.state, p, "definitive", rng, b, d)
    t = game.state.turn
    p = replace(p, status="permitted", permit_start=t, hidden_due_turn=t, permit_turn=t)
    game.state = xp.with_project(game.state, p)
    return p.id


def _crew(game: Game, company: int, name: str, role: str, n: int) -> int:
    uid, ids = game.state.next_ids.take("unit")
    game.state = replace(game.state, next_ids=ids)
    unit = OrgUnit(uid, company, "team", name, None, None, None, game.state.turn)
    game.state = with_unit(game.state, unit)
    add_staff_at(game, company, role, "senior", n, skill=12.0, unit_id=uid)
    return uid


def build(data: LoadedData, *, corp: bool) -> Game:
    game = start_game(data, SEED, "funded_spinout")
    game.state = replace(
        game.state,
        turn=START,
        companies=tuple(
            replace(c, name=COMPANY) if c.is_player else c for c in game.state.companies
        ),
    )
    game.state = with_company(game.state, reach_stage(game.state.player, 3, START))
    game.balances[(PLAYER, CASH)] = game.balances.get((PLAYER, CASH), 0) + RICH
    # A handset on a contract well short of its demand (M12b's device company).
    game.state = m12b.hire(game.state, "hardware_engineer", m12b.STAFF, SEED)
    ref = data.game_data.category("devices").market("consumer").reference_price_cents
    game.state, pid = m12b.product(
        game.state, "devices", "consumer", round(ref * m12b.PRICE), "Handset", root=True
    )
    fee = data.balance.hardware.bom["devices"].contract_fee_cents
    game.state = m12b.contract(game.state, pid, "assembly", DEVICE_UNITS, fee, START, 24)
    # Its own fab, live and staffed (M21's fixture, with its process-research lead).
    domain = data.balance.refining.domain
    game.state = with_research_lead(game.state, ResearchLead(PLAYER, domain, m21.LEAD))
    m21.build(game, "n28", "east_asia", 10_000)
    # Minerals: a subsidiary with a copper mine, its own CEO, plant manager and crew.
    before = {c.id for c in game.state.companies}
    _act(game, FoundSubsidiary(game.founder_id, f"{COMPANY} Minerals", "latin_america", SUB_CENTS))
    (sub,) = {c.id for c in game.state.companies} - before
    project = _permitted(game, "copper", "latin_america")
    _act(game, TransferAsset(game.founder_id, sub, project_id=project))
    _act(game, BuildMine(game.founder_id, project))
    mine = game.state.mines[-1]
    need = mf.staff_needed(mine.capacity_t, data.balance.mining.staff_per_kt)
    add_staff_at(game, sub, "operations_manager", "exec", 1, skill=LEAD_SKILL)
    add_staff_at(game, sub, "plant_manager", "senior", 1, skill=LEAD_SKILL)
    crew = _crew(game, sub, "Mine crew", "mining_engineer", need)
    _act(game, StaffMine(game.founder_id, mine.id, crew))
    # Leads for every chain area, and the COO, CTO and CFO seats.
    for role in LEADS:
        add_staff_at(game, PLAYER, role, "senior", 1, skill=LEAD_SKILL)
    for seat, role in SEATS:
        (holder,) = add_staff_at(game, PLAYER, role, "senior", 1, skill=LEAD_SKILL)
        _act(game, AppointExecutive(game.founder_id, seat, holder))
    game.turn()  # a month played: production rows, the fab's month, the mine's first month
    m21.keep_staffed(game)
    if corp:
        _diligenced(game)
    return game


def _diligenced(game: Game) -> None:
    """The next quarter's first month, with diligence finished on the best related target."""
    from tst.sim.automation import chain
    from tst.sim.mna.models import TargetFile
    from tst.sim.state import target_file, with_target_file

    b, d = game.loaded.balance, game.loaded.game_data
    turn = game.state.turn + (-game.state.turn) % 3
    game.state = replace(game.state, turn=turn)
    ranked = chain.corp_targets(game.state, PLAYER, game.balances, b, d)
    if not ranked:
        raise RuntimeError("no related target to screen")
    tid = ranked[0][1]
    done = replace(
        target_file(game.state, PLAYER, tid) or TargetFile(PLAYER, tid),
        diligence_turn=turn - 2,
        diligence_done_turn=turn,
    )
    game.state = with_target_file(game.state, done)


def _write(path: Path, game: Game, start: Mapping[tuple[int, str], int]) -> None:
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, game.state)
        read_meta(session).current_turn = game.state.turn
        by_company: dict[int, list[LedgerLine]] = {}
        for (cid, account), amount in game.balances.items():
            diff = amount - start.get((cid, account), 0)
            if diff:
                by_company.setdefault(cid, []).append(LedgerLine(account, diff))
        for (cid, account), amount in start.items():
            if (cid, account) not in game.balances and amount:
                by_company.setdefault(cid, []).append(LedgerLine(account, -amount))
        for cid, lines in sorted(by_company.items()):
            gap = sum(x.amount for x in lines)  # funding set directly: equity
            if gap:
                lines.append(LedgerLine(COMMON_EQUITY, -gap))
            if len(lines) >= 2:
                entry = LedgerEntry(
                    game.state.turn - 1, cid, "E2E: the fixture's months", tuple(lines)
                )
                session.add(entry_to_row(entry))


def make(save_dir: Path, name: str, data: LoadedData, *, corp: bool) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name=COMPANY, data=data, save_dir=save_dir
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    game = build(data, corp=corp)
    _write(path, game, start)
    return fixtures.finish(path, data)


MODES = {"chain": False, "corp": True}


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] not in MODES:
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    print(make(Path(argv[2]), argv[3], data, corp=MODES[argv[1]]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
