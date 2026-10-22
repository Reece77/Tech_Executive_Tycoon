from __future__ import annotations

import pytest

from tst.sim.data_models import (
    DIFFICULTY_LEVELS,
    BackupBalance,
    Balance,
    CompanyBalance,
    DifficultyBalance,
    ScenarioBalance,
)
from tst.sim.decisions import Decisions
from tst.sim.ledger import CASH, GENERAL_ADMIN, apply_entries
from tst.sim.rng import RngFactory
from tst.sim.snapshot import runway_months
from tst.sim.state import CompanyState, GameState, SaveMeta, company_cash
from tst.sim.turn import advance_turn

OVERHEAD = 200_000


def make_balance(overhead: int = OVERHEAD) -> Balance:
    return Balance(
        company=CompanyBalance(base_monthly_cost_cents=overhead),
        scenario={"garage_bootstrap": ScenarioBalance(starting_cash_cents=5_000_000)},
        difficulty={
            level: DifficultyBalance(starting_cash_mult_bp=10_000) for level in DIFFICULTY_LEVELS
        },
        backup=BackupBalance(every_n_turns=12, keep_periodic=10),
    )


def make_state(n_companies: int = 2) -> GameState:
    return GameState(
        save_meta=SaveMeta(
            name="t", master_seed=1, scenario_id="garage_bootstrap", difficulty="standard"
        ),
        turn=0,
        companies=tuple(
            CompanyState(id=i, name=f"Co {i}", is_player=i == 1, stage=0, founded_turn=0)
            for i in range(1, n_companies + 1)
        ),
    )


def test_phase_6_posts_overhead_for_each_company() -> None:
    state = make_state(2)
    balances = {(1, CASH): 5_000_000, (2, CASH): 1_000_000}
    result = advance_turn(state, Decisions(), RngFactory(1), make_balance(), balances)

    assert [e.company_id for e in result.ledger_entries] == [1, 2]
    for entry in result.ledger_entries:
        assert entry.turn == 0
        assert {(ln.account, ln.amount) for ln in entry.lines} == {
            (GENERAL_ADMIN, OVERHEAD),
            (CASH, -OVERHEAD),
        }


def test_snapshot_cash_and_burn() -> None:
    state = make_state(1)
    balances = {(1, CASH): 5_000_000}
    result = advance_turn(state, Decisions(), RngFactory(1), make_balance(), balances)
    snap = result.snapshot.for_company(1)
    assert result.snapshot.turn == 0
    assert snap.cash_cents == 4_800_000
    assert snap.monthly_burn_cents == OVERHEAD
    assert snap.headcount == 0
    assert snap.cash_cents == company_cash(apply_entries(balances, result.ledger_entries), 1)


def test_turn_increments_and_inputs_not_mutated() -> None:
    state = make_state(1)
    balances = {(1, CASH): 5_000_000}
    result = advance_turn(state, Decisions(), RngFactory(1), make_balance(), balances)
    assert result.new_state.turn == 1
    assert state.turn == 0
    assert balances == {(1, CASH): 5_000_000}
    assert result.new_state.companies == state.companies
    assert result.event_requests == ()


def test_zero_overhead_posts_nothing() -> None:
    result = advance_turn(make_state(1), Decisions(), RngFactory(1), make_balance(0), {})
    assert result.ledger_entries == ()
    assert result.snapshot.for_company(1).monthly_burn_cents == 0


def test_month_end_log() -> None:
    result = advance_turn(make_state(1), Decisions(), RngFactory(1), make_balance(), {})
    assert [(i.kind, i.message) for i in result.log_items] == [
        ("month_end", "Jan 2010 closed for Co 1")
    ]


@pytest.mark.parametrize(
    ("cash", "burn", "expected"),
    [(5_000_000, 200_000, 25), (199_999, 200_000, 0), (-5, 200_000, 0), (100, 0, None)],
)
def test_runway_months(cash: int, burn: int, expected: int | None) -> None:
    assert runway_months(cash, burn) == expected
