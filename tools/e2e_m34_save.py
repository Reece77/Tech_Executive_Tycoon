"""Create and edit saves for the M34 Playwright flows and the practice save (an e2e fixture tool).
Never used by the game.

Every mode plays 2010 to its month with the engine (a do-nothing Kestrel, so the world is
history's), then gives Kestrel a phone line on its own launched OS and store holding `SHARE` of
Europe's device users (taken from the other Android lines there, so Android's users stay
history's). The months in memory are written as one ledger entry per company.

- `warning <save dir> <name>`: January 2026. Kestrel's Europe share and turnover put it past the
  DMA's thresholds, so December 2026's test warns of a designation a year ahead (flow a; play
  with `advance`).
- `objections <save dir> <name>`: January 2026 with an EU case at its statement of objections;
  the next Continue brings the charges as a critical event (flow b: settle with a commitment).
- `order <save dir> <name>`: January 2026, the store designated, self-preferencing kept on
  against a 2021 ruling's remedy, warning signs since 2022 and a structural order on the OS and
  its store; the next Continue brings the order as a critical event (flow c: sell or spin off).
- `regulated <save dir> <name>` (the practice save `pt-regulated`): January 2029, a dominant
  platform owner designated under the DMA in 2027, self-preferencing on, under an EU inquiry.
- `advance <save dir> <name> <months>`: plays the save's next months (each a turn), answering an
  open critical event with its first choice.

Usage: uv run --project backend python tools/e2e_m34_save.py <mode> <save dir> <name> [months]
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Final

from e2e_m31_save import EXTRA_CASH, PHONE_PRICE, _new, _write
from tst.balance import fixtures
from tst.balance.game import Game, start_game
from tst.config import Settings
from tst.db import repository
from tst.db.repository import create_save, existing_save_path, ledger_balances, open_session
from tst.loader import LoadedData, load_all
from tst.sim.actions import ChooseEvent
from tst.sim.events.models import QueuedEvent
from tst.sim.geo.models import RegionalSegment
from tst.sim.ledger import CASH
from tst.sim.platforms.actions import on_launch
from tst.sim.platforms.models import DeviceRun
from tst.sim.platforms.phase import addressable_in, home_of
from tst.sim.regulation import cases, structural
from tst.sim.regulation.duties import add_duty
from tst.sim.regulation.models import Case, Designation, Order, Watch
from tst.sim.state import GameState, with_product, with_queued, with_regional_segment

SEED: Final = 34
COMPANY: Final = "Kestrel"
JAN_2026: Final = 192
JAN_2029: Final = 228
REGION: Final = "europe"
SHARE: Final = 0.45  # the phone line's share of Europe's device users
EU: Final = "eu_commission"
MONTHS_A_YEAR: Final = 12


def _played(data: LoadedData, until: int) -> Game:
    game = start_game(data, SEED, "funded_spinout")
    game.state = replace(game.state, companies=tuple(
        replace(c, name=COMPANY) if c.is_player else c for c in game.state.companies
    ))  # fmt: skip
    while game.state.turn < until:
        game.turn()
    cash = (game.state.player.id, CASH)
    game.balances = {**game.balances, cash: game.balances.get(cash, 0) + EXTRA_CASH}
    return game


def _owner(state: GameState, data: LoadedData, self_pref: str = "off") -> tuple[GameState, int]:
    """Kestrel's phone on its own OS and store, with SHARE of Europe's device users."""
    b, d = data.balance, data.game_data
    state, phone = _new(state, data, "devices", "Kestrel Phone", live=True, feature=70)
    home = home_of(state, b, d)
    users = addressable_in(state, "devices", d, REGION, home)
    wanted = SHARE * users
    android = next(p.id for p in state.platforms if p.key == "android_play")
    others = [
        seg
        for r in state.device_runs
        if r.platform_id == android
        for seg in state.regional_segments_of(r.product_id, REGION)
    ]
    held = sum(seg.customers for seg in others) or 1.0
    for seg in others:
        state = with_regional_segment(
            state, replace(seg, customers=seg.customers * max(0.0, 1 - wanted / held))
        )
    state = with_regional_segment(
        state, RegionalSegment(phone, REGION, "consumer", PHONE_PRICE, min(wanted, held))
    )
    state, os_id = _new(
        state, data, "os", "Kestrel OS", live=True, feature=b.platforms.os_build_features + 5
    )
    os_product = state.product(os_id)
    assert os_product is not None
    launched = replace(os_product, launched_turn=state.turn - 1)
    state = on_launch(with_product(state, launched), launched, d)
    own = next(p for p in state.platforms if p.product_id == os_id)
    state = replace(
        state,
        platforms=tuple(
            replace(p, self_pref=self_pref) if p.id == own.id else p  # type: ignore[arg-type]
            for p in state.platforms
        ),
        device_runs=(*state.device_runs, DeviceRun(phone, own.id, state.turn - 12)),
    )
    return state, own.id


def _queue(state: GameState, template: str) -> GameState:
    qid, ids = state.next_ids.take("queued")
    return with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid,
            company_id=state.player.id,
            template_id=template,
            due_turn=state.turn,
            source_event_id=None,
        ),
    )


def _objections(state: GameState) -> GameState:
    t = state.turn
    case = Case(
        id=cases.next_case_id(state), regulator=EU, company_id=state.player.id,
        conduct="self_preferencing", market="devices", opened_turn=t - 9, stage="objections",
        stage_turn=t, due_turn=t + 9, remedy="no_self_preferencing", contested=True,
        asked_turn=t, asked_template=cases.OBJECTIONS,
        steps=(("inquiry", t - 9), ("objections", t)),
    )  # fmt: skip
    return _queue(cases.with_case(state, case), cases.OBJECTIONS)


def _order(state: GameState, platform_id: int, data: LoadedData) -> GameState:
    b, d = data.balance, data.game_data
    t, me = state.turn, state.player.id
    ruled = Case(
        id=1, regulator=EU, company_id=me, conduct="self_preferencing", market="devices",
        opened_turn=t - 72, stage="closed", stage_turn=t - 54, due_turn=t - 54, outcome="fined",
        remedy="no_self_preferencing", ruled_turn=t - 54, closed_turn=t - 54,
        steps=(("inquiry", t - 72), ("objections", t - 63), ("ruling", t - 54), ("fined", t - 54)),
    )  # fmt: skip
    state = cases.with_case(state, ruled)
    state = add_duty(state, me, EU, "no_self_preferencing", t - 54, "remedy", d, b, case_id=1)
    state = replace(
        state,
        platforms=tuple(
            replace(p, self_pref="strong") if p.id == platform_id else p for p in state.platforms
        ),
        designations=(Designation("dma", me, t - 28, t - 22),),
    )
    first = t - 48
    signs = tuple((structural.SIGNS[k % len(structural.SIGNS)], first + 9 * k) for k in range(6))
    state = replace(state, reg_watches=(Watch(me, EU, "devices", first, signs),))  # type: ignore[arg-type]
    second = Case(
        id=2, regulator=EU, company_id=me, conduct="noncompliance", market="devices",
        opened_turn=t - 20, stage="closed", stage_turn=t, due_turn=t, outcome="structural",
        remedy="no_self_preferencing", ruled_turn=t, closed_turn=t, noncompliant=True,
        steps=(("inquiry", t - 20), ("objections", t - 10), ("ruling", t), ("structural", t)),
    )  # fmt: skip
    state = cases.with_case(state, second)
    own = state.platform(platform_id)
    assert own is not None
    order = Order(
        id=1, company_id=me, regulator=EU, case_id=2, unit_kind="platform", unit_id=platform_id,
        product_ids=(own.product_id,) if own.product_id else (),
        unit_label=f"{own.name} and {own.store}", ordered_turn=t,
        deadline_turn=t + b.regulation.structural.window_months, asked_turn=t,
        asked_template=structural.ORDER_EVENT, warned_from=first,
    )  # fmt: skip
    state = structural.with_order(state, order)
    return _queue(state, structural.ORDER_EVENT)


def _regulated(state: GameState, data: LoadedData) -> GameState:
    """Designated under the DMA in December 2027, self-preferencing on, an EU inquiry open."""
    t, me = state.turn, state.player.id
    designated = t - 13
    state = replace(state, designations=(Designation("dma", me, designated, designated + 6),))
    case = Case(
        id=cases.next_case_id(state), regulator=EU, company_id=me, conduct="noncompliance",
        market="devices", opened_turn=t - 2, stage="inquiry", stage_turn=t - 2, due_turn=t + 6,
        remedy="no_self_preferencing", noncompliant=True, steps=(("inquiry", t - 2),),
        asked_turn=t, asked_template=cases.INQUIRY,
    )  # fmt: skip
    return _queue(cases.with_case(state, case), cases.INQUIRY)


def make(save_dir: Path, name: str, data: LoadedData, mode: str) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name=COMPANY, data=data, save_dir=save_dir
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    game = _played(data, JAN_2029 if mode == "regulated" else JAN_2026)
    pref = "strong" if mode in ("regulated", "order") else "off"
    state, platform_id = _owner(game.state, data, pref)
    if mode == "objections":
        state = _objections(state)
    elif mode == "order":
        state = _order(state, platform_id, data)
    elif mode == "regulated":
        state = _regulated(state, data)
    _write(path, state, game.balances, start)
    fixtures.finish(path, data, team=True, stage=4)
    return path


def advance(save_dir: Path, name: str, data: LoadedData, months: int) -> None:
    path = existing_save_path(save_dir, name)
    for _ in range(months):
        with open_session(path) as session:
            state = repository.load_state(session)
        founder = state.founder_of(state.player.id)
        for event in state.open_events(state.player.id):
            if event.severity == "critical" and event.status == "open" and founder is not None:
                repository.run_action(
                    path, data, ChooseEvent(founder.id, event.id, event.choices[0].key)
                )
        repository.run_turn(path, data, block_major=False)


def main(argv: list[str]) -> int:
    modes = ("warning", "objections", "order", "regulated", "advance")
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
    sys.exit(main(sys.argv))
