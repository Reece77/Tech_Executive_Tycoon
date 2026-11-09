"""M19 invariants (formulas.md 35): through construction, operations, transfers into a founded
subsidiary, care and maintenance, closure and reclamation, every posting balances, a mine's
book value never goes below zero, and neither do its reserves (Hypothesis over seeds and
choices)."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tst.balance import m19
from tst.loader import LoadedData
from tst.sim.ledger import ARO, MINERAL_PROPERTIES
from tst.sim.mining.actions import CareMaintenance, CloseMine, FoundSubsidiary, TransferAsset

SUB_CENTS = 100_000_000_000


def _check(run: m19.Miner) -> None:
    for e in run.posted:
        assert sum(x.amount for x in e.lines) == 0, e.memo
    assert sum(run.balances.values()) == 0  # the trial balance of every company together
    for m in run.state.mines:
        assert m.book_cents >= 0, m.id
        assert m.hidden_ore_left_mt >= 0 and m.ore_mined_mt >= 0
        assert m.product_t >= 0 and 0 <= m.aro_paid_cents <= m.aro_cents
    for (cid, account), v in run.balances.items():
        if account == MINERAL_PROPERTIES:
            assert v >= 0, cid  # 1520 is the open mines' book values
            assert v == sum(m.book_cents for m in run.state.mines if m.company_id == cid)
        if account == ARO:
            owed = sum(
                m.aro_cents - m.aro_paid_cents for m in run.state.mines if m.company_id == cid
            )
            assert -v == owed, cid


@settings(
    max_examples=12,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(
    seed=st.integers(1, 40),
    commodity=st.sampled_from(["copper", "lithium_carbonate", "cobalt"]),
    transfer_at=st.integers(0, 40),
    care_at=st.integers(0, 60),
    close_at=st.integers(10, 90),
    capacity=st.floats(0.75, 1.25),
)
def test_mines_keep_the_books(
    loaded: LoadedData,
    seed: int,
    commodity: str,
    transfer_at: int,
    care_at: int,
    close_at: int,
    capacity: float,
) -> None:
    run = m19.miner(loaded, seed)
    run.act(FoundSubsidiary(run.founder, "Prop Mining", "oceania", SUB_CENTS))
    sub = run.state.companies[-1].id
    try:
        p = m19.permitted_project(run, commodity)
    except LookupError:
        return
    from tst.sim.mining.actions import BuildMine, StaffMine, quote

    q = quote(run.state, p, None, loaded.balance, loaded.game_data)
    if run.act(BuildMine(run.founder, p.id, q.design_t * capacity)) is None:
        return
    mine = run.state.mines[-1]
    uid = m19.add_engineers(run, q.staff_needed, 11.0)
    run.act(StaffMine(run.founder, mine.id, uid))
    _check(run)
    for month in range(close_at + 30):
        if month == transfer_at:
            run.act(TransferAsset(run.founder, sub, facility_id=mine.id))
        if month == care_at:
            run.act(CareMaintenance(run.founder, mine.id))
        if month == care_at + 4:
            run.act(CareMaintenance(run.founder, mine.id, restart=True))
        if month == close_at:
            run.act(CloseMine(run.founder, mine.id))
        run.month()
        _check(run)
    final = m19.mine_of(run, mine.id)
    assert final.status == "closed"
    assert final.aro_paid_cents == final.aro_cents  # reclaimed in full after closure
    assert replace(final, history=()) is not None
