"""Create and edit saves for the M31 Playwright flows and the practice save (an e2e fixture tool).
Never used by the game.

- `platform <save dir> <name>` (the practice save `pt-platform`): Kestrel, a device maker in
  January 2026 (2010-2025 played by the engine, so the world's markets are history's): a live
  phone line on Android holding 20% of its home region's device users, a Foxconn contract to
  make them, and its own operating system in development, ready to launch (and found its store).
  The months in memory are written as one ledger entry per company netting what they posted.
- `os_live <save dir> <name>`: `platform`, the OS launched (its store founded) and the phone
  line switched to it.
- `removal <save dir> <name>`: `platform` with a consumer app of its own that Google Play has
  just removed in the home region: the next Continue brings the removal as a critical event.
- `advance <save dir> <name> <months>`: plays the save's next months with the engine (each a
  turn of its own), answering nothing.

Usage: uv run --project backend python tools/e2e_m31_save.py <mode> <save dir> <name> [months]
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Final

from tst.balance import fixtures
from tst.balance.game import Game, start_game
from tst.config import Settings
from tst.db import repository
from tst.db.mappers import entry_to_row
from tst.db.repository import (
    create_save,
    existing_save_path,
    ledger_balances,
    load_state,
    open_session,
)
from tst.db.state_io import read_meta, sync_state
from tst.loader import LoadedData, load_all
from tst.sim.actions import ChooseEvent
from tst.sim.events.models import QueuedEvent
from tst.sim.hardware.models import ProductionContract
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry, LedgerLine
from tst.sim.platforms.actions import on_launch
from tst.sim.platforms.gatekeep import REMOVAL
from tst.sim.platforms.models import DeviceRun, PlatformListing
from tst.sim.platforms.phase import addressable_in, home_of
from tst.sim.products.formulas import held_feature_points
from tst.sim.products.models import Product, ProductSegment
from tst.sim.state import (
    GameState,
    with_company,
    with_product,
    with_product_segment,
    with_production_contract,
    with_queued,
)

SEED: Final = 31
COMPANY: Final = "Kestrel"
START: Final = 192  # January 2026
EXTRA_CASH: Final = 2_000_000_000_00  # $2B of funding (equity): a device maker
SHARE: Final = 0.20  # the phone line's share of its region's device users
PHONE_PRICE: Final = 45_000
APP_CUSTOMERS: Final = 2_000_000.0


def _new(
    state: GameState, data: LoadedData, category: str, name: str, *, live: bool, feature: float
) -> tuple[GameState, int]:
    pid, ids = state.next_ids.take("product")
    cat = data.game_data.category(category)
    product = Product(
        id=pid,
        company_id=state.player.id,
        category=category,
        name=name,
        status="live" if live else "in_development",
        quality=60.0,
        feature_points=held_feature_points(feature, cat, state.turn),
        brand=45.0,
        marketing_budget_cents=0,
        created_turn=state.turn - 24,
        launched_turn=state.turn - 12 if live else None,
    )
    return replace(with_product(state, product), next_ids=ids), pid


def _platform(state: GameState, data: LoadedData) -> GameState:
    b, d = data.balance, data.game_data
    state, phone = _new(state, data, "devices", "Kestrel Phone", live=True, feature=60)
    home = home_of(state, b, d) or "north_america"
    users = addressable_in(state, "devices", d, home, home)
    consumer = state.market("devices", "consumer")
    assert consumer is not None
    wanted = SHARE * users
    android = next(p.id for p in state.platforms if p.key == "android_play")
    # the phone's customers come from the other Android lines (Android's users stay history's)
    others = [
        seg
        for r in state.device_runs
        if r.platform_id == android and (seg := state.product_segment(r.product_id, "consumer"))
    ]
    held = sum(seg.customers for seg in others)
    for seg in others:
        state = with_product_segment(
            state, replace(seg, customers=seg.customers * max(0.0, 1 - wanted / held))
        )
    state = with_product_segment(
        state, ProductSegment(phone, "consumer", PHONE_PRICE, min(wanted, held))
    )
    state = replace(state, device_runs=(*state.device_runs, DeviceRun(phone, android, START - 12)))
    cid, ids = state.next_ids.take("production_contract")
    contract = ProductionContract(
        id=cid, company_id=state.player.id, product_id=phone, kind="assembly", supplier="foxconn",
        units=400_000, price_millicents=1_300_000, signed_turn=START, end_turn=START + 35,
        city="shenzhen",
    )  # fmt: skip
    state = with_production_contract(replace(state, next_ids=ids), contract)
    state, os_id = _new(
        state, data, "os", "Kestrel OS", live=False, feature=b.platforms.os_build_features + 5
    )
    return with_company(state, replace(state.player, root_product_id=os_id))


def _os_live(state: GameState, data: LoadedData) -> GameState:
    os_product = next(
        p for p in state.products if p.category == "os" and p.company_id == state.player.id
    )
    launched = replace(os_product, status="live", launched_turn=state.turn)
    state = on_launch(with_product(state, launched), launched, data.game_data)
    own = next(p for p in state.platforms if p.product_id == os_product.id)
    phone = next(
        p for p in state.products if p.category == "devices" and p.company_id == state.player.id
    )
    runs = tuple(
        DeviceRun(phone.id, own.id, state.turn, r.platform_id, 1.0)
        if r.product_id == phone.id
        else r
        for r in state.device_runs
    )
    return replace(state, device_runs=runs)


def _removal(state: GameState, data: LoadedData) -> GameState:
    b, d = data.balance, data.game_data
    state, app = _new(state, data, "consumer_apps", "Kestrel Chat", live=True, feature=70)
    state = with_product_segment(state, ProductSegment(app, "consumer", 45, APP_CUSTOMERS))
    play = next(p.id for p in state.platforms if p.key == "android_play")
    home = home_of(state, b, d) or "north_america"
    state = replace(
        state,
        platform_listings=(
            *state.platform_listings,
            PlatformListing(app, play, home, "removed", state.turn),
        ),
    )
    qid, ids = state.next_ids.take("queued")
    return with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid,
            company_id=state.player.id,
            template_id=REMOVAL,
            due_turn=state.turn,
            source_event_id=None,
            product_id=app,
        ),
    )


def _played(data: LoadedData) -> Game:
    """2010 to December 2025 played by the engine, the player's company doing nothing."""
    game = start_game(data, SEED, "funded_spinout")
    game.state = replace(game.state, companies=tuple(
        replace(c, name=COMPANY) if c.is_player else c for c in game.state.companies
    ))  # fmt: skip
    while game.state.turn < START:
        game.turn()
    cash = (game.state.player.id, CASH)
    game.balances = {**game.balances, cash: game.balances.get(cash, 0) + EXTRA_CASH}
    return game


def _write(
    path: Path,
    state: GameState,
    balances: Mapping[tuple[int, str], int],
    start: Mapping[tuple[int, str], int],
) -> None:
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, state)
        read_meta(session).current_turn = state.turn
        by_company: dict[int, list[LedgerLine]] = {}
        for key in sorted(set(balances) | set(start)):
            diff = balances.get(key, 0) - start.get(key, 0)
            if diff:
                by_company.setdefault(key[0], []).append(LedgerLine(key[1], diff))
        for cid, lines in sorted(by_company.items()):
            gap = sum(x.amount for x in lines)
            if gap:
                lines.append(LedgerLine(COMMON_EQUITY, -gap))
            if len(lines) >= 2:
                entry = LedgerEntry(state.turn - 1, cid, "E2E: the fixture's months", tuple(lines))
                session.add(entry_to_row(entry))


def make(save_dir: Path, name: str, data: LoadedData, mode: str) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name=COMPANY, data=data, save_dir=save_dir
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    game = _played(data)
    state = _platform(game.state, data)
    if mode == "os_live":
        state = _os_live(state, data)
    if mode == "removal":
        state = _removal(state, data)
    _write(path, state, game.balances, start)
    fixtures.finish(path, data, team=True, stage=3)
    return path


def advance(save_dir: Path, name: str, data: LoadedData, months: int) -> None:
    """Each month: an open critical event is answered with its first choice (as Holiday does
    for everything else), then the month is played."""
    path = existing_save_path(save_dir, name)
    for _ in range(months):
        with open_session(path) as session:
            state = load_state(session)
        founder = state.founder_of(state.player.id)
        for event in state.open_events(state.player.id):
            if event.severity == "critical" and event.status == "open" and founder is not None:
                choice = ChooseEvent(founder.id, event.id, event.choices[0].key)
                repository.run_action(path, data, choice)
        repository.run_turn(path, data, block_major=False)


def main(argv: list[str]) -> int:
    modes = ("platform", "os_live", "removal", "advance")
    if len(argv) < 4 or argv[1] not in modes or (argv[1] == "advance") != (len(argv) == 5):
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    if argv[1] == "advance":
        advance(Path(argv[2]), argv[3], data, int(argv[4]))
        return 0
    print(make(Path(argv[2]), argv[3], data, argv[1]))
    return 0


if __name__ == "__main__":
    import e2e_cache  # M59: CI keeps the saves it builds (tools/e2e_cache.py)

    sys.exit(e2e_cache.run(__file__, sys.argv[1:], lambda: main(sys.argv)))
