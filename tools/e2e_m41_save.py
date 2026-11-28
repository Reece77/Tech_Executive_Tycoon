"""Create and edit saves for the M41 Playwright flows and the practice save (an e2e fixture tool).
Never used by the game.

Every mode plays 2010 to January 2024 with the engine (a do-nothing Lumen, so the world is
history's), then gives Lumen a stage-3 device and AI business: a smartwatch and an AI model
(live), and medical products in development's last stage (live, not yet designed or cleared).
The months in memory are written as one ledger entry per company.

- `medical <save dir> <name>` (the practice save `pt-medical`): the watch and AI model, a
  wearable ECG (`Lumen Pulse`, wearables_diagnostics) and a radiology AI (`Lumen Read`, samd),
  each ready to be given an intended use and filed (flow a files the wearable by 510(k)).
- `implant <save dir> <name>`: as `medical` plus a pacemaker (`Lumen Beat`, implantables),
  designed for cardiac rhythm management, ready for its pivotal study (flow b).
- `readout <save dir> <name>`: the save's running pivotal study reads out a success this month
  (flow b then files the PMA).
- `recall <save dir> <name>`: as `medical` plus a cleared CGM (`Lumen Glucose`) with installed
  users and a class I recall this month; the next Continue brings the recall as a critical event.

Usage: uv run --project backend python tools/e2e_m41_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Final

from e2e_m31_save import EXTRA_CASH, _new, _write
from tst.balance import fixtures
from tst.balance.game import Game, start_game
from tst.config import Settings
from tst.db import repository
from tst.db.repository import create_save, existing_save_path, ledger_balances, open_session
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.hardware.models import ProductionContract
from tst.sim.ledger import CASH
from tst.sim.medical import quality
from tst.sim.medical.models import Clearance, Design
from tst.sim.products.models import ProductSegment
from tst.sim.state import GameState, with_product, with_product_segment, with_production_contract

SEED: Final = 41
COMPANY: Final = "Lumen"
JAN_2024: Final = 168
QUALITY: Final = 72.0


def _played(data: LoadedData) -> Game:
    game = start_game(data, SEED, "funded_spinout")
    game.state = replace(game.state, companies=tuple(
        replace(c, name=COMPANY) if c.is_player else c for c in game.state.companies
    ))  # fmt: skip
    while game.state.turn < JAN_2024:
        game.turn()
    cash = (game.state.player.id, CASH)
    game.balances = {**game.balances, cash: game.balances.get(cash, 0) + EXTRA_CASH}
    return game


def _product(
    state: GameState, data: LoadedData, category: str, name: str, price: int, customers: float = 0.0
) -> tuple[GameState, int]:
    state, pid = _new(state, data, category, name, live=True, feature=65)
    product = state.product(pid)
    assert product is not None
    state = with_product(state, replace(product, quality=QUALITY))
    segment = data.game_data.category(category).markets[0].segment
    state = with_product_segment(state, ProductSegment(pid, segment, price, customers))
    if data.game_data.category(category).sells_units:
        cid, ids = state.next_ids.take("production_contract")
        contract = ProductionContract(
            id=cid, company_id=state.player.id, product_id=pid, kind="assembly",
            supplier="foxconn", units=20_000, price_millicents=1_000_000,
            signed_turn=state.turn, end_turn=state.turn + 47, city="shenzhen",
        )  # fmt: skip
        state = with_production_contract(replace(state, next_ids=ids), contract)
    return state, pid


def _business(state: GameState, data: LoadedData) -> GameState:
    """The device and AI company and its two medical products (module docstring)."""
    state, _ = _product(state, data, "devices", "Lumen Watch", 40_000, 200_000.0)
    state, _ = _product(state, data, "ai_models", "Lumen Vision", 10_000)
    state, _ = _product(state, data, "wearables_diagnostics", "Lumen Pulse", 15_000)
    state, _ = _product(state, data, "samd", "Lumen Read", 800_000)
    return state


def _implant(state: GameState, data: LoadedData) -> GameState:
    state, pid = _product(state, data, "implantables", "Lumen Beat", 800_000)
    return replace(state, med_designs=(*state.med_designs, Design(pid, "cardiac_rhythm")))


def _recall(state: GameState, data: LoadedData) -> GameState:
    b, d = data.balance, data.game_data
    state, pid = _product(state, data, "wearables_diagnostics", "Lumen Glucose", 15_000, 40_000.0)
    t = state.turn
    state = replace(
        state,
        med_designs=(*state.med_designs, Design(pid, "glucose_monitoring")),
        med_clearances=(
            *state.med_clearances,
            Clearance(pid, "fda", "north_america", t - 12, "k510"),
        ),
    )
    product = state.product(pid)
    assert product is not None
    state, _, _, _ = quality.recall(state, product, "I", False, b, d)
    state = quality.queue_class_i(state, product)
    q = state.queued[-1]
    return replace(state, queued=(*state.queued[:-1], replace(q, due_turn=t)))


def make(save_dir: Path, name: str, data: LoadedData, mode: str) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name=COMPANY, data=data, save_dir=save_dir
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    game = _played(data)
    state = _business(game.state, data)
    if mode == "implant":
        state = _implant(state, data)
    elif mode == "recall":
        state = _recall(state, data)
    _write(path, state, game.balances, start)
    fixtures.finish(path, data, team=True, stage=3)
    return path


def readout(save_dir: Path, name: str) -> None:
    """The running pivotal study reads out a success now (the fixture's result)."""
    path = existing_save_path(save_dir, name)
    with open_session(path) as session, session.begin():
        before = repository.load_state(session)
        t = before.turn
        studies = tuple(
            replace(s, status="succeeded", read_turn=t, due_turn=t, spent_cents=s.cost_cents)
            if s.status == "running" and s.kind == "pivotal"
            else s
            for s in before.med_studies
        )
        done = {s.product_id for s in studies if s.status == "succeeded"}
        designs = tuple(
            replace(x, evidence=max(x.evidence, 0.6)) if x.product_id in done else x
            for x in before.med_designs
        )
        sync_state(session, before, replace(before, med_studies=studies, med_designs=designs))


def main(argv: list[str]) -> int:
    modes = ("medical", "implant", "recall", "readout")
    if len(argv) != 4 or argv[1] not in modes:
        print(__doc__)
        return 2
    if argv[1] == "readout":
        readout(Path(argv[2]), argv[3])
        return 0
    data = load_all(Settings().data_dir)
    print(make(Path(argv[2]), argv[3], data, argv[1]))
    return 0


if __name__ == "__main__":
    import e2e_cache  # M59: CI keeps the saves it builds (tools/e2e_cache.py)

    sys.exit(e2e_cache.run(__file__, sys.argv[1:], lambda: main(sys.argv)))
