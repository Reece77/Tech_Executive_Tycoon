"""Create a save for the M13b Playwright flows (an e2e fixture tool). Never used by the game.

`cpo <save dir> <name>`: a stage-3 funded spinout ($20M) with a live product, a CPO with
authority and the CPO's new-product pitch waiting (27.1).
`holiday <save dir> <name>`: the same company with a CPO and a CTO with authority, at a
quarter's first month whose draws make both pitch; prints the dollar limit between their two
costs, so on Holiday the cheaper pitch goes ahead and the dearer one waits.

Usage: uv run --project backend python tools/e2e_m13b_save.py cpo <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.balance.game import Game
from tst.balance.m8 import add_staff
from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, load_state, open_session
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.actions.authority import guardrails_for
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.org import pitches
from tst.sim.org.authority import run_executives
from tst.sim.org.models import Authority, ExecSeat, PitchPolicy
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    reach_stage,
    with_authority,
    with_company,
    with_exec_seat,
    with_pitch,
    with_pitch_policy,
    with_product,
    with_product_segment,
)

FOUNDER = 1
FUNDING_CENTS = 2_000_000_000  # $20M
SEEDS = range(1, 400)


def _company(
    save_dir: Path, name: str, seed: int, data: LoadedData, seats: tuple[str, ...]
) -> tuple[Path, GameState, dict[str, int]]:
    path = create_save(
        name, seed, "funded_spinout", company_name="Kestrel", data=data, save_dir=save_dir
    )
    entry = LedgerEntry.transfer(
        turn=0,
        company_id=FOUNDER,
        memo="Fixture funding",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=FUNDING_CENTS,
    )
    with open_session(path) as session, session.begin():
        session.add(entry_to_row(entry))
        before = load_state(session)
        game = Game(data, before, {})
        roles = {"cpo": "product_manager", "cto": "software_engineer"}
        holders = {}
        for seat in seats:
            (pid,) = add_staff(game, roles[seat], "senior", 1, skill=16.0)
            person = game.state.person(pid)
            person = replace(person, personality=person.personality.updated({"ambition": 20.0}))
            game.state = replace(
                game.state, people=tuple(person if p.id == pid else p for p in game.state.people)
            )
            holders[seat] = pid
        add_staff(game, "software_engineer", "mid", 4)
        state = with_company(game.state, reach_stage(game.state.player, 3, 0))
        pid, ids = state.next_ids.take("product")
        state = with_product(
            replace(state, next_ids=ids),
            Product(pid, FOUNDER, "b2b_saas", "Pipeline", "live", 55.0, 400.0, 30.0, 0, 0, 0),
        )
        state = with_product_segment(state, ProductSegment(pid, "smb", 4000, 2000.0))
        for seat, holder in holders.items():
            state = with_exec_seat(state, ExecSeat(FOUNDER, seat, holder, 0))
            rails = guardrails_for(None, seat, (), state, FOUNDER, data.balance, data.game_data)
            state = with_authority(state, Authority(FOUNDER, seat, True, rails, 0))
        sync_state(session, before, state)
    with open_session(path) as session:
        return path, load_state(session), holders


def cpo(save_dir: Path, name: str, data: LoadedData) -> Path:
    path, state, holders = _company(save_dir, name, 29, data, ("cpo",))
    ranked = pitches.candidates(
        state, FOUNDER, ("new_product",), FUNDING_CENTS, data.balance, data.game_data
    )
    pitch = pitches.make_pitch(state, FOUNDER, "cpo", holders["cpo"], ranked[0], data.balance)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        after = with_pitch(replace(before, next_ids=before.next_ids.take("pitch")[1]), pitch)
        sync_state(session, before, after)
    return path


def _limit(state: GameState, seed: int, data: LoadedData) -> int | None:
    """The dollar limit between the two pitches' costs if this seed's draws make both
    executives pitch on this state, else None."""
    asks = with_pitch_policy(state, PitchPolicy(FOUNDER, auto_approve_cents=0))
    out, _, _, _ = run_executives(
        asks, RngFactory(seed), data.balance, data.game_data, {(FOUNDER, CASH): FUNDING_CENTS}
    )
    costs = sorted(p.cost_cents for p in out.pending_pitches(FOUNDER))
    if len(costs) == 2 and costs[1] > costs[0] + 200_00:
        return (costs[0] + costs[1]) // 2 // 100  # whole dollars
    return None


def holiday(save_dir: Path, name: str, data: LoadedData) -> tuple[Path, int]:
    """A seed whose first month makes both executives pitch, and a limit between the costs.
    The draws are probed on one company first (cheap), then checked on the seed's own save."""
    path, probe, _ = _company(save_dir, f"{name}-probe", SEEDS[0], data, ("cpo", "cto"))
    path.unlink()
    for seed in SEEDS:
        if _limit(probe, seed, data) is None:
            continue
        path, state, _ = _company(save_dir, name, seed, data, ("cpo", "cto"))
        limit = _limit(state, seed, data)
        if limit is not None:
            return path, limit
        path.unlink()
    raise SystemExit("no seed makes both executives pitch")


def main(argv: list[str]) -> int:
    data = load_all(Settings().data_dir)
    if len(argv) == 3 and argv[0] == "cpo":
        print(cpo(Path(argv[1]), argv[2], data))
        return 0
    if len(argv) == 3 and argv[0] == "holiday":
        path, limit = holiday(Path(argv[1]), argv[2], data)
        print(f"{path}\nlimit={limit}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
