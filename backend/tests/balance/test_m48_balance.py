"""M48's 59.4 targets as a guard (tst.balance.m48): on seeds 1-3, a good communicator holding
every meeting keeps the board's confidence and sentiment above skipping within the bands, a poor
one keeps confidence below skipping within its band, and three broken guidance promises halve
the next call's gains. The full run (seeds 1-10) is `python -m tst.balance.m48`, printed in the
brief."""

from __future__ import annotations

from tst.balance import m48

SEEDS = (1, 2, 3)


def test_59_4_targets_2_and_3() -> None:
    results = m48.run(SEEDS, jobs=3)
    assert m48.met(results) == {"t2_good": True, "t2_poor": True, "t3": True}, m48.report(results)
