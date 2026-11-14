"""Create and edit saves for the M36 Playwright flows and the practice save (an e2e fixture
tool). Never used by the game.

- `teen <save dir> <name>`: a founder of 45 with a partner and a child of 18 who has not yet
  chosen a university, and $1M of personal cash (flow b).
- `heir <save dir> <name>`: a founder of 60 with a partner and children of 30 and 27; the elder
  works at the company (closeness high), a month played (flow c).
- `proposal <save dir> <name>`: an executive's pending proposal (a lease) this month, so the
  month end brings the adviser's opinion on it.
- `family <save dir> <name>` (the practice save `pt-family`): M13's listed scale-up moved to
  January 2034 in the living world; the founder is 62 with a partner and three adult children
  (the eldest in the company), holding $8B of the company's shares at the save's share price
  (the market reprices toward the company's fundamentals from the next month), no estate planning.

Usage: uv run --project backend python tools/e2e_m36_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tst.config import Settings
from tst.db import repository
from tst.db.repository import (
    create_save,
    existing_save_path,
    ledger_balances,
    load_state,
    open_session,
    run_turn,
)
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.calendar import MONTHS_PER_YEAR, ym_to_turn
from tst.sim.family import answers, rules
from tst.sim.family.setup import FamilySpec, start_family
from tst.sim.founder import personal
from tst.sim.org.models import Proposal
from tst.sim.people.founder import FounderSpec
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_family_member, with_person, with_proposal

SEED: Final = 36
MILLION: Final = 1_000_000_00  # cents
EIGHT_BILLION: Final = 8_000_000_000_00


def _edit(path: Path, change) -> GameState:  # type: ignore[no-untyped-def]
    with open_session(path) as session, session.begin():
        before = load_state(session)
        after = change(before)
        sync_state(session, before, after)
    repository._LAST.clear()
    return after


def _new(save_dir: Path, name: str, data: LoadedData, age: int, kids: tuple[int, ...]) -> Path:
    return create_save(
        name,
        SEED,
        "funded_spinout",
        company_name="Hearth",
        data=data,
        save_dir=save_dir,
        founder=FounderSpec(background="engineer", age=age),
        family=FamilySpec("children", kids),
    )


def _hire_eldest(state: GameState, data: LoadedData) -> GameState:
    kid = rules.children(state)[0]
    state = with_family_member(state, replace(kid, closeness=90.0))
    person = state.person(kid.person_id)
    d = data.game_data
    role = next(r.key for r in d.roles if r.founder_fit and rules.roles_match(person, r.key, d))
    state, _ = answers.offer_job(state, kid.person_id, 1, role, "senior", data.balance, d)
    return state


def teen(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _new(save_dir, name, data, 45, (18,))
    _edit(path, lambda s: personal.credit(s, 1, MILLION, "secondary", "E2E savings"))
    return path


def heir(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _new(save_dir, name, data, 60, (30, 27))
    _edit(path, lambda s: _hire_eldest(s, data))
    run_turn(path, data)
    return path


def proposal(path: Path) -> None:
    def change(state: GameState) -> GameState:
        pid, ids = state.next_ids.take("proposal")
        founder = state.founder_of(1)
        assert founder is not None
        staff = [e.person_id for e in state.staff(1) if e.person_id != founder.id]
        p = Proposal(
            pid,
            1,
            "cfo",
            staff[0] if staff else founder.id,
            state.turn,
            "lease",
            (("seats", 20),),
            "a lease on a bigger office for 20 more people",
        )
        return with_proposal(replace(state, next_ids=ids), p)

    _edit(path, change)


def family(save_dir: Path, name: str, data: LoadedData) -> Path:
    """pt-family (see the module docstring)."""
    from e2e_m28_save import SEED as M28_SEED
    from e2e_m28_save import _listed_game, _write

    from tst.sim.finance.captable import person_shares
    from tst.sim.state import listed_id, public_of, with_public
    from tst.sim.world.setup import materialise
    from tst.sim.ledger import apply_entries

    path = create_save(  # M13's listed game's seed, so the founder in the file is the same
        name, M28_SEED, "funded_spinout", company_name="Hearth", data=data, save_dir=save_dir
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    game = _listed_game(data)
    game.state = replace(game.state, companies=tuple(
        replace(c, name="Hearth") if c.is_player else c for c in game.state.companies
    ))  # fmt: skip
    b, d = data.balance, data.game_data
    game.state = replace(game.state, turn=ym_to_turn(2034, 1))
    state, opening = materialise(game.state, RngFactory(SEED), b, d)
    game.state = state
    game.balances = dict(apply_entries(game.balances, opening))
    founder = game.state.person(game.founder_id)
    born = game.state.turn - 62 * MONTHS_PER_YEAR - 3
    game.state = with_person(game.state, replace(founder, birth_turn=born))
    game.state = start_family(
        game.state, FamilySpec("children", (34, 31, 28)), RngFactory(SEED), b, d
    )
    game.state = _hire_eldest(game.state, data)
    game.turn()
    lid = listed_id(game.state)
    public = public_of(game.state, lid)
    assert public is not None
    held = person_shares(game.state, lid, game.founder_id)
    factor = EIGHT_BILLION / max(1, held * public.price_cents)  # sentiment carries the price
    game.state = with_public(
        game.state,
        replace(
            public,
            price_cents=max(1, EIGHT_BILLION // max(1, held)),
            sentiment=public.sentiment * factor,
        ),
    )
    _write(path, game, start)
    return path


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode, save_dir, name = argv[0], Path(argv[1]), argv[2]
    data = load_all(Settings().data_dir)
    if mode == "teen":
        path = teen(save_dir, name, data)
    elif mode == "heir":
        path = heir(save_dir, name, data)
    elif mode == "family":
        path = family(save_dir, name, data)
    elif mode == "proposal":
        path = existing_save_path(save_dir, name)
        proposal(path)
    else:
        print(__doc__)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
