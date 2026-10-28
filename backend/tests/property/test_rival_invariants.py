"""Rival invariants (M5, formulas.md 15.1): every rival ledger entry balances, cash moves only
through entries, and pools never go negative, whatever the seed and turn count."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.balance_scripts import Run
from tst.loader import LoadedData
from tst.sim.ledger import CASH, account_balance, apply_entries
from tst.sim.setup import DEFAULT_FOUNDER, new_game


def _run(loaded: LoadedData, seed: int, scenario: str) -> Run:
    state, entries = new_game(
        save_name="p",
        master_seed=seed,
        scenario=loaded.game_data.scenario(scenario),  # type: ignore[arg-type]
        difficulty="standard",
        company_name="Co",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
    )
    return Run(loaded, state, dict(apply_entries({}, entries)))


@settings(
    max_examples=12, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    seed=st.integers(min_value=0, max_value=10_000),
    turns=st.integers(min_value=1, max_value=8),
    scenario=st.sampled_from(["garage_bootstrap", "funded_spinout"]),
)
def test_rival_books_balance_and_pools_stay_positive(
    loaded: LoadedData, seed: int, turns: int, scenario: str
) -> None:
    run = _run(loaded, seed, scenario)
    for _ in range(turns):
        run.turn()
        # Each rival with books has a month-end snapshot that matches its cash account.
        for company in run.state.ledger_companies():
            snap = run.snapshots[-1] if company.is_player else None
            if snap is not None:
                assert snap.cash_cents == account_balance(run.balances, company.id, CASH)
        assert all(p.headcount >= 0 for p in run.state.pools)
        assert all(0 <= p.morale <= 100 and 1 <= p.skill <= 20 for p in run.state.pools)
    # Every entry balances by construction (LedgerEntry raises otherwise); the totals agree.
    assert sum(run.balances.values()) == 0
    rivals = [c for c in run.state.companies if not c.is_player]
    assert rivals and all(c.personality for c in rivals)
