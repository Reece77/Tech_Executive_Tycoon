"""Create saves for the M49 Playwright flows, the API tests and the practice save (an e2e fixture
tool). Never used by the game.

- `talks <save dir> <name>` (the practice save `pt-talks`): Quill, a stage-3 company in January
  2019 (2010-2018 played by the engine, the company doing nothing, so the world is history's)
  with a device business and a stage-3 team. Two engineers have just been approached by
  rivals (their approaches answer at the next Continue), and a glucose monitor had a class I
  recall last month, so a press conference on it can be held now. Prints the approached
  people's ids as JSON.
- `launch <save dir> <name>`: as `talks`, with a press moment on the device's launch shown this
  month (its press event open): an interview can be taken.

Usage: uv run --project backend python tools/e2e_m49_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Final

import e2e_m38_save as m38
from e2e_m41_save import _product
from tst.balance import fixtures
from tst.balance.game import Game, start_game
from tst.config import Settings
from tst.db.repository import create_save, ledger_balances, open_session
from tst.db.events import write_pending
from tst.llm.offline import TemplateAdapter
from tst.loader import LoadedData, load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.events.models import GameEvent
from tst.sim.ledger import CASH
from tst.sim.medical import quality
from tst.sim.medical.models import Clearance, Design
from tst.sim.press.models import PressMoment
from tst.sim.rivals.models import PoachApproach
from tst.sim.state import GameState, with_company, with_event, with_press_moment

SEED: Final = 49
COMPANY: Final = "Quill"
YEAR: Final = 2019
STAGE: Final = 3
EXTRA_CASH: Final = 2_000_000_000_00
KEY_SALARY: Final = 16_000_000
POACH_PREMIUM: Final = 1.3


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


def _approached(state: GameState, data: LoadedData) -> tuple[GameState, list[int]]:
    """Two engineers, each approached last month by a different rival at 30% over salary."""
    state, keys = fixtures.hire(
        state, data, "software_engineer", "senior", 2, "Core", KEY_SALARY, 49
    )
    rivals = [c for c in state.rivals() if c.alive and c.failed_turn is None][: len(keys)]
    aid = max((a.id for a in state.approaches), default=0)
    approaches = [
        PoachApproach(aid + i + 1, r.id, pid, round(KEY_SALARY * POACH_PREMIUM), state.turn - 1)
        for i, (pid, r) in enumerate(zip(keys, rivals, strict=True))
    ]
    return replace(state, approaches=(*state.approaches, *approaches)), keys


def _recalled(state: GameState, data: LoadedData) -> GameState:
    """A cleared glucose monitor with users and a class I recall last month."""
    b, d = data.balance, data.game_data
    state, pid = _product(state, data, "wearables_diagnostics", "Quill Glucose", 15_000, 40_000.0)
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
    state, _, _, rec = quality.recall(state, product, "I", False, b, d)
    moved = replace(rec, turn=t - 1)  # last month's, as a turn's recall is seen the month after
    return replace(state, med_recalls=(*state.med_recalls[:-1], moved))


def _launch(state: GameState, data: LoadedData) -> GameState:
    """The device's launch press moment, its press event shown and open this month."""
    cid = state.player.id
    device = next(p for p in state.company_products(cid) if p.category == "devices")
    mid = max((m.id for m in state.press_moments), default=0) + 1
    state = with_press_moment(
        state,
        PressMoment(
            id=mid,
            company_id=cid,
            trigger="launch",
            turn=state.turn - 1,
            status="queued",
            event_turn=state.turn,
            product_id=device.id,
        ),
    )
    template = data.game_data.event_template("press_launch")
    eid, ids = state.next_ids.take("event")
    event = GameEvent(  # pending: the event service writes its words (make)
        id=eid,
        company_id=cid,
        turn=state.turn,
        template_id="press_launch",
        category=template.category,
        severity="major",
        trigger=template.trigger,
        strength=1.0,
        product_id=device.id,
    )
    return with_event(replace(state, next_ids=ids), event)


def make(save_dir: Path, name: str, data: LoadedData, mode: str) -> str:
    path = create_save(
        name, SEED, "funded_spinout", company_name=COMPANY, data=data, save_dir=save_dir
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    game = _played(data)
    state, _ = _product(game.state, data, "devices", "Quill Watch", 40_000, 100_000.0)
    state, keys = _approached(state, data)
    state = _recalled(state, data)
    if mode == "launch":
        state = _launch(state, data)
    m38._write(path, state, game.balances, start)
    fixtures.finish(path, data, team=True, stage=STAGE)
    if mode == "launch":
        write_pending(path, data, adapter=TemplateAdapter())
    return json.dumps({"approached": keys})


def main(argv: list[str]) -> int:
    modes = ("talks", "launch")
    if len(argv) != 4 or argv[1] not in modes:
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    print(make(Path(argv[2]), argv[3], data, argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
