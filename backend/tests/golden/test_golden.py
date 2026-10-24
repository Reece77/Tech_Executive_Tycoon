"""Golden seeds and determinism (ADR-0002).

Seeds 1..10 are played for 24 turns through the full persistence path, as an
ex_big_tech_founders game following a scripted hiring plan (M1b), and their per-turn
snapshots are compared with tests/golden/snapshots/seed_NN.json. The founder's current
ability after each turn goes to seed_NN.founder_ca.json instead: CA is hidden (ADR-0007), so
it never enters turn_snapshot, which the API returns. Never edit these files by hand:
regenerate with `uv run pytest tests/golden --update-golden` and record why in CHANGELOG.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from tst.db.models import LedgerEntryRow, TurnSnapshotRow
from tst.db.repository import create_save, load_state, open_session, run_action, run_turn
from tst.loader import LoadedData
from tst.sim.actions import CloseSearch, MakeOffer, OpenSearch
from tst.sim.calendar import format_turn
from tst.sim.people.models import current_ability

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"
SEEDS = range(1, 11)
TURNS = 24


TARGET_STAFF = 8  # the plan stops making offers at this many employees
CLOSE_JOB_POST_TURN = 6


def hiring_plan(path: Path, data: LoadedData) -> None:
    """Scripted player actions between turns, exercising payroll, morale and departures.

    Turn 0 opens all three channels. Every turn, while staff are below TARGET_STAFF, each open
    candidate without an offer gets one: 1.10x the ask for odd ids, 0.90x for even ids (some
    underpaid hires, to stress morale), no equity. The job post closes at turn 6.
    """
    with open_session(path) as session:
        state = load_state(session)
    actor = 1
    if state.turn == 0:
        run_action(path, data, OpenSearch(actor, "software_engineer", "job_post"))
        run_action(path, data, OpenSearch(actor, "product_manager", "recruiter"))
        run_action(path, data, OpenSearch(actor, "designer", "network"))
    if state.turn == CLOSE_JOB_POST_TURN:
        for search in state.searches:
            run_action(path, data, CloseSearch(actor, search.id))
    staff = len(state.staff(1)) - 1
    for candidate in state.candidates:
        if staff >= TARGET_STAFF:
            break
        if state.pending_offer_for(candidate.person_id) is not None:
            continue
        ask = state.person(candidate.person_id).salary_expectation_cents or 0
        ratio = 1.10 if candidate.person_id % 2 else 0.90
        run_action(path, data, MakeOffer(actor, candidate.person_id, round(ask * ratio), 0))
        staff += 1  # count pending offers toward the target


def play(
    save_dir: Path, slug: str, seed: int, data: LoadedData
) -> tuple[Path, list[dict[str, Any]]]:
    """Play TURNS turns with the hiring plan; return the save and the founder's CA per turn."""
    path = create_save(
        slug,
        seed,
        "ex_big_tech_founders",
        company_name="Golden Co",
        data=data,
        save_dir=save_dir,
    )
    founder_ca = []
    for _ in range(TURNS):
        hiring_plan(path, data)
        result = run_turn(path, data)
        with open_session(path) as session:
            founder = next(p for p in load_state(session).people if p.is_founder)
        founder_ca.append(
            {
                "turn": result.snapshot.turn,
                "date": format_turn(result.snapshot.turn),
                "founder_ca": current_ability(founder, data.game_data),
            }
        )
    return path, founder_ca


def _check_golden(name: str, actual: object, update: bool) -> None:
    golden = SNAPSHOT_DIR / name
    if update:
        SNAPSHOT_DIR.mkdir(exist_ok=True)
        with golden.open("w", encoding="utf-8", newline="\n") as fh:
            json.dump(actual, fh, indent=2)
            fh.write("\n")
        return
    if not golden.is_file():
        pytest.fail(f"{golden.name} missing; run `uv run pytest tests/golden --update-golden`")
    assert actual == json.loads(golden.read_text(encoding="utf-8"))


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
    path, founder_ca = play(tmp_path, f"golden-{seed}", seed, loaded)
    actual = snapshots(path)
    assert len(actual) == TURNS
    # CA is hidden (ADR-0007): it must never appear in turn_snapshot, which the API returns.
    assert all("founder_ca" not in row and "current_ability" not in row for row in actual)
    update = bool(request.config.getoption("--update-golden"))
    _check_golden(f"seed_{seed:02d}.json", actual, update)
    _check_golden(f"seed_{seed:02d}.founder_ca.json", founder_ca, update)


def test_same_seed_twice_is_identical(tmp_path: Path, loaded: LoadedData) -> None:
    first, first_ca = play(tmp_path / "a", "twin", 42, loaded)
    second, second_ca = play(tmp_path / "b", "twin", 42, loaded)
    assert first_ca == second_ca
    with open_session(first) as a, open_session(second) as b:
        assert load_state(a).people == load_state(b).people
    assert snapshots(first) == snapshots(second)
    assert ledger_rows(first) == ledger_rows(second)
    assert len(ledger_rows(first)) > 2 + 3 * TURNS  # payroll and fees on top of office/overhead
