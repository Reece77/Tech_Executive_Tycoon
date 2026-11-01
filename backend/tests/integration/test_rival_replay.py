"""Replay reproduces a save with rival moves, a startup and a poach in each direction (M5
acceptance, ADR-0015 section 5): player actions are re-applied; rival moves, startups and
approaches are recomputed every turn and must equal the logged ones."""

from __future__ import annotations

from pathlib import Path

from tests.golden.test_golden import ledger_rows, snapshots
from tests.helpers import answer_critical
from tst.db.repository import (
    create_save,
    load_state,
    open_session,
    replay_save,
    run_action,
    run_turn,
)
from tst.loader import LoadedData
from tst.sim.actions import (
    AssignUnit,
    CreateProduct,
    Interview,
    LaunchProduct,
    MakeOffer,
    OpenSearch,
    SetMarketing,
    SetPrice,
)
from tst.sim.actions.products import launch_problems
from tst.sim.state import GameState

# A seed whose 24 months bring a rival approach (rivals.need.poach_gain 0.007): 7 until
# M10, whose consumer confidence moved adoption.
SEED = 6
PRICES = {"smb": 4000, "mid_market": 70_000}
TURNS = 24  # the funded spinout's money lasts about 26 months at this burn
STAFF = 5  # the founder and four (M8: five ran out of money in month 21)


def _state(path: Path) -> GameState:
    with open_session(path) as session:
        return load_state(session)


def _hire_all(path: Path, loaded: LoadedData, ratio: float) -> None:
    state = _state(path)
    for c in state.open_candidates(1):
        pending = sum(1 for o in state.offers if o.status == "pending")
        if len(state.staff(1)) + pending >= STAFF:
            break
        if state.pending_offer_for(c.person_id) is not None:
            continue
        if (state.person_state(1).energy or 0) < 8:
            break
        run_action(path, loaded, Interview(1, c.person_id))
        ask = state.person(c.person_id).salary_expectation_cents or 0
        run_action(path, loaded, MakeOffer(1, c.person_id, round(ask * ratio), 0))
        state = _state(path)


def build(save_dir: Path, loaded: LoadedData) -> Path:
    path = create_save(
        "rivrep", SEED, "funded_spinout", company_name="Rep Co", data=loaded, save_dir=save_dir
    )
    run_action(path, loaded, OpenSearch(1, "software_engineer", "job_post"))
    product = _state(path).next_ids.product
    run_action(path, loaded, CreateProduct(1, "Pipeline", "b2b_saas", tuple(PRICES)))
    for segment, price in PRICES.items():
        run_action(path, loaded, SetPrice(1, product, segment, price))
    run_action(path, loaded, AssignUnit(1, product, None))
    run_action(path, loaded, SetMarketing(1, product, 1_000_000))
    poached = False
    for turn in range(TURNS):
        state = _state(path)
        current = state.product(product)
        ready = current is not None and current.status == "in_development"
        if ready and not launch_problems(state, current, loaded.balance, loaded.game_data):  # type: ignore[arg-type]
            run_action(path, loaded, LaunchProduct(1, product))
        if turn < 6:
            _hire_all(path, loaded, 1.15)
        if turn == 8:  # the player poaches from Zoho
            zoho = next(c.id for c in state.companies if c.name == "Zoho")
            run_action(path, loaded, OpenSearch(1, "software_engineer", "poach", rival_id=zoho))
        if turn == 9 and not poached:
            for c in [c for c in state.open_candidates(1) if c.channel == "poach"]:
                run_action(path, loaded, Interview(1, c.person_id))
                ask = state.person(c.person_id).salary_expectation_cents or 0
                run_action(path, loaded, MakeOffer(1, c.person_id, round(ask * 1.6), 0))
                poached = True
                break
        answer_critical(path, loaded)  # M6: a critical event is answered before Continue
        run_turn(path, loaded)
    return path


def test_replay_reproduces_rivals_a_startup_and_poaching(
    tmp_path: Path, loaded: LoadedData
) -> None:
    original = build(tmp_path / "a", loaded)
    state = _state(original)
    with open_session(original) as session:
        from sqlalchemy import select

        from tst.db.models import DecisionLogRow, PoachApproachRow

        rival_rows = session.scalars(
            select(DecisionLogRow).where(DecisionLogRow.source == "rival")
        ).all()
        approaches = session.scalars(select(PoachApproachRow)).all()
    kinds = {r.kind for r in rival_rows}
    assert {"rival_price_cut", "rival_quality_push"} & kinds  # rivals acted
    assert "rival_founded" in kinds or any(c.is_startup for c in state.companies)  # a startup
    assert any(e.end_reason == "poached" for e in state.employments) or any(
        e.company_id == 1 and e.person_id >= 1_000_001 for e in state.employments
    )  # the player poached a rival's key person
    assert approaches, "a rival approached one of the player's people"
    copy = replay_save(original, tmp_path / "b", "rivrep-copy", loaded)
    replayed = _state(copy)
    assert snapshots(copy, None) == snapshots(original, None)
    assert [r[1:] for r in ledger_rows(copy)] == [r[1:] for r in ledger_rows(original)]
    assert replayed.companies == state.companies
    assert replayed.rival_moves == state.rival_moves
    assert replayed.approaches == state.approaches
    assert replayed.people == state.people
