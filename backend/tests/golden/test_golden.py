"""Golden seeds and determinism (ADR-0002).

Seeds 1..10 are played for 24 turns through the full persistence path and their per-turn
snapshots are compared with tests/golden/snapshots/seed_NN.json. Never edit those files by
hand: regenerate with `uv run pytest tests/golden --update-golden` and record why in
CHANGELOG.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from tst.db.models import LedgerEntryRow, TurnSnapshotRow
from tst.db.repository import create_save, open_session, run_turn
from tst.loader import LoadedData
from tst.sim.calendar import format_turn

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"
SEEDS = range(1, 11)
TURNS = 24


def play(save_dir: Path, slug: str, seed: int, data: LoadedData) -> Path:
    path = create_save(
        slug,
        seed,
        "garage_bootstrap",
        company_name="Golden Co",
        data=data,
        save_dir=save_dir,
    )
    for _ in range(TURNS):
        run_turn(path, data)
    return path


def snapshots(path: Path) -> list[dict[str, Any]]:
    with open_session(path) as session:
        rows = session.scalars(
            select(TurnSnapshotRow).order_by(TurnSnapshotRow.turn, TurnSnapshotRow.company_id)
        ).all()
        return [
            {"turn": r.turn, "date": format_turn(r.turn), "company_id": r.company_id, **r.kpis}
            for r in rows
        ]


def ledger_rows(path: Path) -> list[tuple[Any, ...]]:
    with open_session(path) as session:
        entries = session.scalars(select(LedgerEntryRow).order_by(LedgerEntryRow.id)).all()
        return [
            (e.id, e.turn, e.company_id, e.memo, ln.id, ln.account_code, ln.amount_cents)
            for e in entries
            for ln in e.lines
        ]


@pytest.mark.parametrize("seed", SEEDS)
def test_golden_seed(
    seed: int, tmp_path: Path, loaded: LoadedData, request: pytest.FixtureRequest
) -> None:
    path = play(tmp_path, f"golden-{seed}", seed, loaded)
    actual = snapshots(path)
    assert len(actual) == TURNS
    golden = SNAPSHOT_DIR / f"seed_{seed:02d}.json"

    if request.config.getoption("--update-golden"):
        SNAPSHOT_DIR.mkdir(exist_ok=True)
        with golden.open("w", encoding="utf-8", newline="\n") as fh:
            json.dump(actual, fh, indent=2)
            fh.write("\n")
        return

    if not golden.is_file():
        pytest.fail(f"{golden.name} missing; run `uv run pytest tests/golden --update-golden`")
    assert actual == json.loads(golden.read_text(encoding="utf-8"))


def test_same_seed_twice_is_identical(tmp_path: Path, loaded: LoadedData) -> None:
    first = play(tmp_path / "a", "twin", 42, loaded)
    second = play(tmp_path / "b", "twin", 42, loaded)
    assert snapshots(first) == snapshots(second)
    assert ledger_rows(first) == ledger_rows(second)
    assert len(ledger_rows(first)) == 2 * (1 + TURNS)  # starting cash + one entry per turn
