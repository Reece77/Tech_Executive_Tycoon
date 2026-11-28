"""M51's 63.4 targets 1-2 (nightly; tst.balance.m51): each new scenario won by the sensible
script on 3-8 of seeds 1-10 and by the passive one on at most 2, and each challenge rule lowering
the scripted player's median score by at least 10% (three rules carried by Reece's decision).
Target 3 is M30's state cache. The full run is `tools/m51_targets.py`, printed in the brief."""

from __future__ import annotations

import os

import pytest

from tst.balance import m51


@pytest.mark.nightly
def test_63_4_targets_1_and_2() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    runs = m51.run_table(m51.NEW, workers=jobs)
    rows = m51.target_2(workers=jobs)
    print(m51.report(runs, rows))
    from tst.balance.known_misses import Reading, known_miss, verdict

    one = all(ok for *_, ok in m51.target_1([r for r in runs if r.key in m51.NEW]))
    assert one, m51.report(runs, rows)
    # M57r-B (review 10 item 36): each rule's drop is judged; a carried rule is a known miss
    # within its bound, never a skip
    readings = [
        Reading(f"M51.T2.{rule}", drop >= m51.TARGET2_DROP, m51.TARGET2_DROP - drop)
        for rule, _base, _hit, drop in rows
    ]
    failed = [r for r in readings if verdict(r) == "fail"]
    assert not failed, (failed, m51.report(runs, rows))
    known = [known_miss(r.target) for r in readings if verdict(r) == "known"]
    if known:
        pytest.xfail("; ".join(f"KNOWN MISS ({k.owner}): {k.reason}" for k in known if k))
