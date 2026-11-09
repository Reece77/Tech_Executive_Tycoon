"""Create saves for the M20 Playwright flows and tests (an e2e fixture tool). Never used by the
game.

- `smelter <save dir> <name>`: a funded spinout in January 2016 with $2B more cash and a team
  of twelve process engineers: ready to build a silicon smelter.
- `wafers <save dir> <name>`: January 2018, a device maker with its own mobile SoC on a TSMC
  wafer contract (M12b's 26.6 company) and its own 300 mm wafer plant in East Asia, built,
  staffed and past its ramp, and a process lead (as if researched): one Continue supplies its
  chips' wafers at transfer price.
- `curb <save dir> <name>`: September 2021, a staffed silicon smelter in East Asia, live and
  past its ramp: the next Continue brings China's 2021 power curb (September-October).
- `gallium <save dir> <name>`: December 2024, the chip company of `wafers` (no wafer plant)
  with a silicon smelter in East Asia and a gallium recovery line on it: the next Continue is
  inside the December 2024 ban on gallium exports, and the line supplies the chips' gallium.

Plants are ordered through `build_refinery` (the engine's own action); only construction is
skipped: a plant is made ready and its capex posted to PPE at once.

Usage: uv run --project backend python tools/e2e_m20_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from tst.balance import m20
from tst.balance.game import Game
from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, ledger_balances, load_state, open_session
from tst.db.state_io import read_meta, sync_state
from tst.loader import LoadedData, load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.ledger import (
    ACCUMULATED_DEPRECIATION,
    CASH,
    COMMON_EQUITY,
    DEPRECIATION,
    PPE,
    LedgerEntry,
)

SEED = 20
EXTRA_CASH = 200_000_000_000  # $2B


def _create(save_dir: Path, name: str, data: LoadedData, turn: int) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name="Crucible", data=data, save_dir=save_dir
    )
    entry = LedgerEntry.transfer(
        turn=0,
        company_id=1,
        memo="E2E funding",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=EXTRA_CASH,
    )
    with open_session(path) as session, session.begin():
        session.add(entry_to_row(entry))
        before = load_state(session)
        sync_state(session, before, replace(before, turn=turn))
        read_meta(session).current_turn = turn
    return path


def _edit(path: Path, data: LoadedData, step: Callable[[Game], None]) -> None:
    """Run `step(game)` on the save's state in memory and write the result: the state, and the
    capex of plants made ready at once as an entry (cash to PPE)."""
    with open_session(path) as session, session.begin():
        before = load_state(session)
        game = Game(data, before, dict(ledger_balances(session)))
        ppe = game.balances.get((1, PPE), 0)
        step(game)
        built = game.balances.get((1, PPE), 0) - ppe
        sync_state(session, before, replace(game.state, turn=before.turn))
        booked = game.notes.get("depreciation", 0)
        for memo, debit, credit, amount in (
            ("E2E: plants built", PPE, CASH, built),
            ("E2E: plants' depreciation to date", DEPRECIATION, ACCUMULATED_DEPRECIATION, booked),
        ):
            if amount > 0:
                session.add(
                    entry_to_row(
                        LedgerEntry.transfer(
                            turn=before.turn,
                            company_id=1,
                            memo=memo,
                            debit=debit,
                            credit=credit,
                            amount=amount,
                        )
                    )
                )


def smelter(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _create(save_dir, name, data, ym_to_turn(2016, 1))
    _edit(path, data, lambda g: m20.hire_unit(g, "Process team", 12))
    return path


def _chips(game: Game) -> None:
    """M12b's device maker with its own mobile SoC (26.6 target 4's company): a live phone on a
    20,000-unit Foxconn contract and its SoC on a TSMC wafer contract, every chip going into
    the phone; and a process lead, as if researched (36.3)."""
    from tst.balance import m12b
    from tst.sim.chips import chips
    from tst.sim.research.models import ResearchLead
    from tst.sim.state import with_research_lead

    b, d = game.loaded.balance, game.loaded.game_data
    state, t = game.state, game.state.turn
    ref = d.category("devices").market("consumer").reference_price_cents
    state, pid = m12b.product(
        state, "devices", "consumer", round(ref * 0.8), "Forge Phone", root=True
    )
    fee = b.hardware.bom["devices"].contract_fee_cents
    state = m12b.contract(state, pid, "assembly", 20_000, fee, t, 36)
    soc = d.category("chips_mobile_soc").market("device_oems").reference_price_cents
    state, chip = m12b.product(
        state, "chips_mobile_soc", "device_oems", soc * 10, "Forge SoC", root=False
    )
    wafer = chips.index_wafer_cents(state, "mobile_soc", b, d, "tsmc")
    wafers = round(20_000 * 1.1 / (600 * b.chips.chip_yield.base))
    state = m12b.contract(state, chip, "wafer", wafers, wafer, t, 36)
    game.state = with_research_lead(state, ResearchLead(1, b.refining.domain, 25.0))


def _past_ramp(game: Game, fid: int, months: int) -> None:
    """The plant finished `months` ago: its depreciation to last month is booked (6700 against
    1510) so this month's charge is one month's."""
    from tst.sim.facilities import formulas as ff
    from tst.sim.refining.plants import refinery_of
    from tst.sim.state import with_refinery

    b = game.loaded.balance
    f = game.state.facility(fid)
    assert f is not None
    t = game.state.turn - months
    f = replace(f, ready_turn=t, late_turn=t, ordered_turn=t)
    life = b.facility.kinds[f.kind].life_months
    booked = ff.cumulative_depreciation_cents(
        f.capex_paid_cents, f.capacity, f.on_time, t, t, life, game.state.turn - 1
    )
    game.state = m20.with_facility(game.state, replace(f, depreciated_cents=booked, status="live"))
    ref = refinery_of(game.state, fid)
    assert ref is not None
    game.state = with_refinery(game.state, replace(ref, last_depreciated_cents=booked))
    game.notes["depreciation"] = game.notes.get("depreciation", 0) + booked


def wafers(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _create(save_dir, name, data, ym_to_turn(2018, 1))

    def step(game: Game) -> None:
        _chips(game)
        fid = m20.build(game, "wafer_plant", "east_asia", 120_000)
        _past_ramp(game, fid, 12)

    _edit(path, data, step)
    return path


def curb(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _create(save_dir, name, data, ym_to_turn(2021, 9))

    def step(game: Game) -> None:
        fid = m20.build(game, "silicon_smelter", "east_asia", 25_000)
        _past_ramp(game, fid, 6)

    _edit(path, data, step)
    return path


def gallium(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _create(save_dir, name, data, ym_to_turn(2024, 12))

    def step(game: Game) -> None:
        _chips(game)
        host = m20.build(game, "silicon_smelter", "east_asia", 10_000)
        line = m20.build(game, "byproduct_gallium", "east_asia", 25, host_id=host)
        _past_ramp(game, host, 6)
        _past_ramp(game, line, 6)

    _edit(path, data, step)
    return path


MODES = {"smelter": smelter, "wafers": wafers, "curb": curb, "gallium": gallium}


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] not in MODES:
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    MODES[argv[1]](Path(argv[2]), argv[3], data)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
