"""Create and edit saves for the M26 Playwright flows (an e2e fixture tool). Never used by
the game.

- `rounds <save dir> <name>`: Kestrel (tools/e2e_m24_save.py `fresh`) with $5M of personal
  cash, played until a rival startup has a round open to the founder. Prints the startup's
  company id on a second line.
- `leaver <save dir> <name>`: `fresh` with $5M of personal cash and a software engineer who
  worked for Kestrel and left, in the founder's network with skills the player knows well.
  Prints the person's id on a second line.
- `dividend <save dir> <name>`: `fresh` with $5M of personal cash, played to March 2010 (a
  quarter's last month), with a listed rival whose last quarter was profitable. Prints the
  rival's company id on a second line.
- `insider <save dir> <name>`: `fresh` with $5M of personal cash; the company has started
  diligence on a listed rival, the founder bought its shares, the bid was agreed and walked
  away from, and the regulator's draw (formulas.md 37.3) opens an investigation at this
  month's end, as the engine's draw would make it.

Usage: uv run --project backend python tools/e2e_m26_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from e2e_m24_save import _edit, fresh

from tst.config import Settings
from tst.db.repository import load_state, open_session, run_turn
from tst.loader import LoadedData, load_all
from tst.sim.founder import angel, personal
from tst.sim.state import GameState

CASH = 5_000_000_00  # $5M of personal cash
MAX_MONTHS = 12


def _rich(path: Path) -> GameState:
    def change(state: GameState) -> GameState:
        founder = state.founder_of(state.player.id)
        assert founder is not None
        return personal.credit(state, founder.id, CASH, "exit", "E2E personal cash")

    return _edit(path, change)


def _state(path: Path) -> GameState:
    with open_session(path) as session:
        return load_state(session)


def rounds(save_dir: Path, name: str, data: LoadedData) -> tuple[Path, int]:
    path = fresh(save_dir, name, data)
    _rich(path)
    for _ in range(MAX_MONTHS):
        state = _state(path)
        for c in state.companies:
            if c.is_startup and c.alive and angel.open_round(state, c.id, data.balance):
                return path, c.id
        run_turn(path, data)
    raise SystemExit("no startup round opened")


def leaver(save_dir: Path, name: str, data: LoadedData) -> tuple[Path, int]:
    from tst.sim.founder.investing_models import NetworkEntry
    from tst.sim.people.generator import generate_pool, people_gen_stream
    from tst.sim.people.models import Employment
    from tst.sim.people.reveal import new_reveal_state
    from tst.sim.rng import RngFactory
    from tst.sim.state import with_employment, with_network, with_person, with_reveal

    path = fresh(save_dir, name, data)
    _rich(path)
    made: list[int] = []

    def change(state: GameState) -> GameState:
        rng = RngFactory(state.save_meta.master_seed)
        role = data.game_data.role("software_engineer")
        pid, ids = state.next_ids.take("rival_person")
        eid, ids = ids.take("rival_employment")
        (person,) = generate_pool(
            people_gen_stream(rng, state.turn, 990_000, 0),
            data.game_data,
            data.balance,
            state.turn,
            role,
            ["senior"],
            first_person_id=pid,
        )
        person = replace(person, first_name="Ada", last_name="Leaver")
        state = replace(with_person(state, person), next_ids=ids)
        state = with_employment(
            state,
            Employment(eid, pid, 1, role.key, "senior", 0, 0, 0, state.turn, "ended", "resigned"),
        )
        reveal = new_reveal_state(
            observer_company_id=1,
            person=person,
            turn=state.turn,
            rng=rng,
            data=data.game_data,
            balance=data.balance,
            knows_exactly=True,
        )
        state = with_reveal(state, reveal)
        made.append(pid)
        return with_network(state, [NetworkEntry(pid, state.turn)], data.balance.angel.network_size)

    _edit(path, change)
    return path, made[0]


def _listed_profitable(state: GameState, data: LoadedData) -> int:
    from tst.sim.mna.valuation import is_listed

    return max(
        (c for c in state.rivals() if is_listed(state, c.id, data.game_data)),
        key=lambda c: sum(c.op_history[-3:]),
    ).id


def dividend(save_dir: Path, name: str, data: LoadedData) -> tuple[Path, int]:
    path = fresh(save_dir, name, data)
    _rich(path)
    while _state(path).turn % 3 != 2:
        run_turn(path, data)
    state = _state(path)
    rid = _listed_profitable(state, data)
    assert sum(state.company(rid).op_history[-3:]) > 0
    return path, rid


def insider(save_dir: Path, name: str, data: LoadedData) -> Path:
    from tst.db.repository import ledger_balances
    from tst.sim.founder import shares
    from tst.sim.mna.models import Deal, TargetFile
    from tst.sim.state import with_deal, with_target_file, with_trade

    path = fresh(save_dir, name, data)
    _rich(path)
    run_turn(path, data)
    with open_session(path) as session:
        balances = ledger_balances(session)

    def change(state: GameState) -> GameState:
        founder = state.founder_of(state.player.id)
        assert founder is not None
        rid = _listed_profitable(state, data)
        state = with_target_file(state, TargetFile(1, rid, diligence_turn=state.turn - 1))
        state, _, _ = shares.trade(
            state, founder.id, rid, "buy", 1000, balances, data.balance, data.game_data
        )
        trade = state.personal_trades[-1]
        assert trade.sensitive_target_id == rid
        deal = Deal(
            1, 1, rid, 10**12, 1.0, state.turn, status="abandoned", resolved_turn=state.turn
        )
        state = with_deal(state, deal)
        # the regulator's draw (stream personal) says: investigated, opening this month
        return with_trade(
            state,
            replace(
                trade,
                risk=data.balance.personal.risk_per_trade,
                public_turn=state.turn,
                investigate_turn=state.turn,
                resolved=True,
            ),
        )

    _edit(path, change)
    return path


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode, save_dir, name = argv[0], Path(argv[1]), argv[2]
    data = load_all(Settings().data_dir)
    if mode in ("rounds", "leaver", "dividend"):
        path, ident = {"rounds": rounds, "leaver": leaver, "dividend": dividend}[mode](
            save_dir, name, data
        )
        print(path)
        print(ident)
    elif mode == "insider":
        print(insider(save_dir, name, data))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
