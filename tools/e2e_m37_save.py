"""Create saves for the M37 Playwright flows and the practice save (an e2e fixture tool). Never
used by the game.

- `end <save dir> <name>`: a standard campaign whose December 2039 has been played: the
  campaign summary waits, with its choice to end or continue (flow a). The month is moved on
  directly (the world is January 2010's): the flow is about the end, not the world.
- `era <save dir> <name>`: a dynasty campaign moved to the month fusion power (the first era of
  dynasty years) is scheduled on its seed, and that month played: the era arrives (flow b).
- `practice <save dir> <name>` (the practice save `pt-dynasty`): full_integrator's chain group
  (devices, its own chips, a fab, lithium) played by the engine from January 2010 to December
  2039 in a standard campaign at its end (so the 2039 summary shows, then continue); the founder
  aged 68 with a partner and two adult heirs (40 and 37, the elder in the company); a car line
  (on a Foxconn contract, CATL cells) and a 2,000-CU cloud data centre with a Cloud hosting
  product added in December 2039. Takes a few minutes.

Usage: uv run --project backend python tools/e2e_m37_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tst.config import Settings
from tst.db import repository
from tst.db.repository import create_save, load_state, open_session, run_turn
from tst.db.state_io import read_meta, sync_state
from tst.loader import LoadedData, load_all
from tst.sim.research import levels
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

SEED: Final = 37
JAN_2040: Final = 360
FIRST_ERA: Final = "fusion_power"
FOUNDER_AGE_2010: Final = 38  # 68 in December 2039


def _edit(path: Path, change) -> GameState:  # type: ignore[no-untyped-def]
    with open_session(path) as session, session.begin():
        before = load_state(session)
        after = change(before)
        sync_state(session, before, after)
        read_meta(session).current_turn = after.turn
    repository._LAST.clear()
    return after


def _new(save_dir: Path, name: str, data: LoadedData, length: str) -> Path:
    return create_save(
        name,
        SEED,
        "funded_spinout",
        company_name="Longview",
        data=data,
        save_dir=save_dir,
        length=length,  # type: ignore[arg-type]
    )


def end(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _new(save_dir, name, data, "standard")
    _edit(path, lambda s: replace(s, turn=JAN_2040))
    return path


def era(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _new(save_dir, name, data, "dynasty")
    eras = data.game_data.eras.eras
    index = next(i for i, e in enumerate(eras) if e.key == FIRST_ERA)
    month = levels.scheduled_turn(eras[index], index, RngFactory(SEED))
    _edit(path, lambda s: replace(s, turn=month))
    run_turn(path, data)
    return path


def _refill_cto(game) -> None:  # type: ignore[no-untyped-def]
    from tst.sim.actions import AppointExecutive
    from tst.sim.actions.scaleup import appoint_problem

    state, b = game.state, game.loaded.balance
    if state.seat_holder(1, "cto") is not None:
        return
    engineers = [
        e.person_id
        for e in state.staff(1)
        if state.person(e.person_id).role == "software_engineer"
        and appoint_problem(state, 1, "cto", e.person_id, b) is None
    ]
    if engineers:
        game.act(AppointExecutive(game.founder_id, "cto", engineers[0]))


def practice(save_dir: Path, name: str, data: LoadedData) -> Path:
    """pt-dynasty (see the module docstring)."""
    import e2e_m12a_save as cloud
    import e2e_m38_save as cars
    from tst.balance import fixtures
    from tst.balance.game import Game
    from tst.balance.strategies_v3 import V3
    from tst.db.repository import ledger_balances
    from tst.sim.family import answers, rules
    from tst.sim.family.setup import FamilySpec, start_family
    from tst.sim.ledger import apply_entries
    from tst.sim.people.founder import FounderSpec
    from tst.sim.products.models import Product, ProductSegment
    from tst.sim.setup import new_game
    from tst.sim.state import (
        with_company,
        with_family_member,
        with_product,
        with_product_segment,
    )
    from tst.sim.vehicles.models import VehicleSpec

    founder_spec = FounderSpec(background="engineer", age=FOUNDER_AGE_2010)  # 68 in 2039
    path = create_save(
        name,
        SEED,
        "ex_big_tech_founders",
        company_name="Balance Co",
        data=data,
        save_dir=save_dir,
        founder=founder_spec,
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    state, entries = new_game(
        save_name=name,
        master_seed=SEED,
        scenario=data.game_data.scenario("ex_big_tech_founders"),  # type: ignore[arg-type]
        difficulty="standard",
        company_name="Balance Co",
        founder=founder_spec,
        balance=data.balance,
        data=data.game_data,
    )
    game = Game(data, state, apply_entries({}, entries))
    script = V3["full_integrator"]
    while game.state.turn < JAN_2040 - 1 and not game.state.ended:
        script(game)
        game.turn()
    # M43a: the CTO can leave in the campaign's last months; a player refills the seat from its
    # own engineers before December 2039 closes it (fixtures.finish's CTO comes after the end,
    # when the engine refuses appointments)
    _refill_cto(game)
    while game.state.turn < JAN_2040 and not game.state.ended:
        script(game)
        game.turn()
    if game.state.ended:
        raise SystemExit(f"the game ended at {game.state.turn}: try another seed")
    b, d = data.balance, data.game_data
    game.state = start_family(game.state, FamilySpec("children", (40, 37)), RngFactory(SEED), b, d)
    kid = rules.children(game.state)[0]
    game.state = with_family_member(game.state, replace(kid, closeness=90.0))
    person = game.state.person(kid.person_id)
    role = next(r.key for r in d.roles if r.founder_fit and rules.roles_match(person, r.key, d))
    game.state, _ = answers.offer_job(game.state, kid.person_id, 1, role, "senior", b, d)
    # cars: a line on a Foxconn contract with CATL cells, launched
    car = cars._product(game, "Balance Drive", "vehicles", cars.CAR_PRICE)
    fee = b.hardware.bom["vehicles"].contract_fee_cents
    cars._contract(game, car, cars.CAR_UNITS, fee, cars.CITY)
    spec = VehicleSpec(car, 70.0, "lfp", 150.0, "l2", "licensed", "catl")
    game.state = replace(game.state, vehicle_specs=(*game.state.vehicle_specs, spec))
    cars._launch(game, car)
    # cloud: a live general data centre and a Cloud hosting product on it
    game.state = cloud._facility(game.state, data, 2000)
    pid, ids = game.state.next_ids.take("product")
    hosting = Product(
        id=pid,
        company_id=1,
        category="cloud_hosting",
        name="Balance Cloud",
        status="live",
        quality=60.0,
        feature_points=d.category("cloud_hosting").features_at_start,
        brand=40.0,
        marketing_budget_cents=0,
        created_turn=game.state.turn,
        launched_turn=game.state.turn,
    )
    game.state = replace(with_product(game.state, hosting), next_ids=ids)
    game.state = with_product_segment(game.state, ProductSegment(pid, "smb", 3000, 0.0))
    game.state = with_company(game.state, replace(game.state.player, name="Balance Co"))
    cars._write(path, game.state, game.balances, start)
    fixtures.finish(path, data, team=True)  # M23c: knowledge records and a believable team
    return path


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode, save_dir, name = argv[0], Path(argv[1]), argv[2]
    data = load_all(Settings().data_dir)
    makers = {"end": end, "era": era, "practice": practice}
    if mode not in makers:
        print(__doc__)
        return 2
    print(makers[mode](save_dir, name, data))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
