"""Create and edit saves for the M44 Playwright flows and the practice save (an e2e fixture tool).
Never used by the game.

- `defence <save dir> <name>` (the practice save `pt-defence`): Aegis, a stage-4 cloud, AI and
  satellites group in January 2027 (2010-2026 played by the engine, the player's company doing
  nothing, so the world, its tenders and rivals' awards are the engine's): live cloud, AI and
  cyber products (and, once M40 has merged, a satellite broadband service), a consumer chat app,
  a live US data centre with a facility clearance, six engineers cleared at Top Secret, three
  account executives for capture teams, three completed contracts on its record (past
  performance), a stage-3 team, $20B of extra funding; and a rugged device assembled by Foxconn in
  Shenzhen. Three tenders announced this month for the flows: a US civil cloud tender, a US
  defence devices tender and a US defence AI tender (Secret).
- `award <save dir> <name>`: every bid tender closes and is awarded now, as the engine's award
  does (the government phase of the month, nothing else).
- `letter <save dir> <name>`: the open letter after the last defence award is queued for next
  month, as the engine's staff reaction does when it draws one (no-op if one is queued).
- `advance <save dir> <name> <months>`: plays the save's next months with the engine.

Usage: uv run --project backend python tools/e2e_m44_save.py <mode> <save dir> <name> [months]
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Final

import e2e_m38_save as m38
from tst.balance import fixtures
from tst.balance.game import Game, start_game
from tst.config import Settings
from tst.db.repository import (
    create_save,
    existing_save_path,
    ledger_balances,
    load_state,
    open_session,
)
from tst.loader import LoadedData, load_all
from tst.sim.actions.facilities import BuildFacility
from tst.sim.calendar import ym_to_turn
from tst.sim.government import phase as gov_phase
from tst.sim.government import reputation
from tst.sim.government.models import Clearance, Contract, FacilityClearance, Tender
from tst.sim.hardware.models import ProductionContract, ProductionMonth
from tst.sim.ledger import CASH
from tst.sim.rng import RngFactory
from tst.sim.state import with_company, with_product

SEED: Final = 44
COMPANY: Final = "Aegis"
EXTRA_CASH: Final = 20_000_000_000_00
STAGE: Final = 4
YEAR: Final = 2027
REGION: Final = "north_america"
CLEARED: Final = 6
SELLERS: Final = 3
QUALITY: Final = 82.0
DEVICE: Final = "Aegis Rugged"
TENDER_VALUE: Final = 4_000_000_000  # $40M over the term at the game's scale
TENDERS: Final = (
    ("E2E: US civil cloud services", "cloud", "civil", "none"),
    ("E2E: US rugged and secure devices", "devices", "defence", "none"),
    ("E2E: US AI and analytics", "ai", "defence", "secret"),
)


def _played(data: LoadedData) -> Game:
    game = start_game(data, SEED, "funded_spinout")
    game.state = replace(game.state, companies=tuple(
        replace(c, name=COMPANY) if c.is_player else c for c in game.state.companies
    ))  # fmt: skip
    while game.state.turn < ym_to_turn(YEAR, 1):
        game.turn()
    cash = (game.state.player.id, CASH)
    game.balances = {**game.balances, cash: game.balances.get(cash, 0) + EXTRA_CASH}
    game.state = with_company(game.state, replace(game.state.player, stage=STAGE))
    return game


def _live_product(game: Game, name: str, category: str, price: int, quality: float) -> int:
    pid = m38._product(game, name, category, price)
    m38._launch(game, pid)
    p = game.state.product(pid)
    assert p is not None
    game.state = with_product(game.state, replace(p, quality=quality))
    return pid


def _device(game: Game, pid: int) -> None:
    """Assembled by Foxconn in Shenzhen, with this month's production on record."""
    s = game.state
    cid, ids = s.next_ids.take("production_contract")
    contract = ProductionContract(
        id=cid,
        company_id=s.player.id,
        product_id=pid,
        kind="assembly",
        supplier="foxconn",
        units=20_000,
        price_millicents=2_000_000,
        signed_turn=s.turn,
        end_turn=s.turn + 36,
        city="shenzhen",
        used=10_000.0,
        delivered=10_000.0,
    )
    month = ProductionMonth(
        turn=s.turn,
        product_id=pid,
        company_id=s.player.id,
        capacity=20_000.0,
        units=10_000.0,
        contract_units=10_000.0,
        bom_cents=150_000_000,
        assembly_cents=20_000_000,
    )
    game.state = replace(
        s,
        next_ids=ids,
        production_contracts=(*s.production_contracts, contract),
        production=(*s.production, month),
    )


def _state(data: LoadedData) -> Game:
    game = _played(data)
    s0 = game.state
    cloud = _live_product(game, "Aegis Cloud", "cloud_hosting", 50_000, QUALITY)
    _live_product(game, "Aegis Mind", "ai_models", 2_000_000, 80.0)
    _live_product(game, "Aegis Shield", "cybersecurity", 30_000, 78.0)
    if any(c.key == "satellite_broadband" for c in data.game_data.categories):
        _live_product(game, "Aegis Orbit", "satellite_broadband", 9_900, 75.0)
    _live_product(game, "Aegis Chat", "consumer_apps", 500, 70.0)
    device = _live_product(game, DEVICE, "devices", 90_000, 75.0)
    _device(game, device)
    m38._energise(game)
    before = {f.id for f in game.state.facilities}
    assert game.act(BuildFacility(game.founder_id, "data_centre_general", REGION, 500)), (
        game.refused
    )
    (dc,) = {f.id for f in game.state.facilities} - before
    m38._live(game, dc)
    s = game.state
    s, sellers = fixtures.hire(s, data, "account_executive", "senior", SELLERS, "Capture", 15_000_000, 44)
    s, cleared = fixtures.hire(s, data, "software_engineer", "senior", CLEARED, "Cleared", 16_000_000, 45)
    t = s.turn
    s = replace(
        s,
        clearances=tuple(
            Clearance(pid, s.player.id, "top_secret", t - 14, t - 2, "cleared", "cleared", t - 2)
            for pid in cleared
        ),
        facility_clearances=(FacilityClearance(dc, s.player.id, t - 12, t - 2, "cleared"),),
        gov_contracts=tuple(
            Contract(
                id=900 + i,
                tender_id=0,
                company_id=s.player.id,
                product_id=cloud,
                government="us",
                area="cloud",
                buyer="civil",
                contract="fixed_price",
                value_cents=500_000_000,
                start_turn=t - 60,
                base_end_turn=t - 24,
                end_turn=t - 24,
                status="completed",
                performance=90.0,
                months=36,
            )
            for i in range(3)
        ),
    )
    world = s.government_world
    tenders = []
    for i, (title, area, buyer, level) in enumerate(TENDERS):
        tenders.append(
            Tender(
                id=world.next_tender + i,
                government="us",
                area=area,  # type: ignore[arg-type]
                buyer=buyer,  # type: ignore[arg-type]
                title=title,
                announce_turn=t,
                close_turn=t + 3,
                award_turn=t + 5,
                value_cents=TENDER_VALUE,
                term_months=36,
                base_months=24,
                contract="fixed_price",
                clearance=level,  # type: ignore[arg-type]
            )
        )
    s = replace(
        s,
        tenders=(*s.tenders, *tenders),
        government_world=replace(world, next_tender=world.next_tender + len(tenders)),
    )
    game.state = s
    del s0
    return game


def make(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name=COMPANY, data=data, save_dir=save_dir
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    game = _state(data)
    m38._write(path, game.state, game.balances, start)
    fixtures.finish(path, data, team=True, stage=STAGE)
    return path


def _edit(save_dir: Path, name: str, data: LoadedData, mode: str) -> int:
    path = existing_save_path(save_dir, name)
    with open_session(path) as session:
        state = load_state(session)
        balances = dict(ledger_balances(session))
    game = Game(data, state, dict(balances))
    n = 0
    s = game.state
    if mode == "award":
        bid = {b.tender_id for b in s.gov_bids if b.status == "submitted"}
        s = replace(
            s,
            tenders=tuple(
                replace(t, status="evaluating", close_turn=s.turn, award_turn=s.turn)
                if t.id in bid
                else t
                for t in s.tenders
            ),
        )
        s, entries, _ = gov_phase.month(s, RngFactory(s.save_meta.master_seed), data.balance, data.game_data)
        for e in entries:
            for line in e.lines:
                key = (e.company_id, line.account)
                game.balances[key] = game.balances.get(key, 0) + line.amount
        n = len(bid)
    else:
        record = s.defence_record(s.player.id)
        if record is None or record.letter_turn is None:
            objecting = reputation.objectors(s, s.player.id, data.balance)
            s = reputation.queue_letter(s, s.player.id)
            base = record or reputation.DefenceRecord(company_id=s.player.id)
            contract = max((c.id for c in s.gov_contracts if c.buyer == "defence" and c.status == "active"), default=None)
            s = reputation._with_record(
                s,
                replace(
                    base,
                    reactions=(*base.reactions, s.turn),
                    letter_turn=s.turn + 1,
                    objectors=objecting,
                    contract_id=contract,
                ),
            )
            n = 1
    game.state = s
    m38._write(path, game.state, game.balances, balances)
    return n


def main(argv: list[str]) -> int:
    modes = ("defence", "award", "letter", "advance")
    if len(argv) < 4 or argv[1] not in modes or (argv[1] == "advance") != (len(argv) == 5):
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    if argv[1] == "advance":
        m38.advance(Path(argv[2]), argv[3], data, int(argv[4]))
        return 0
    if argv[1] in ("award", "letter"):
        print(_edit(Path(argv[2]), argv[3], data, argv[1]))
        return 0
    print(make(Path(argv[2]), argv[3], data))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
