"""docs/formulas.md 25.9 targets 2-5 (M13), nightly; tools/m13_targets.py prints the same.
Values recorded in the M13 brief ("Decisions made") and docs/balance-targets.md."""

from __future__ import annotations

import os

import pytest

from tst.balance import m13
from tst.balance.known_misses import Reading, known_miss, verdict


@pytest.mark.nightly
def test_25_9_targets() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    r = m13.run(m13.SEEDS, jobs)
    print(m13.report(r))
    known: list[Reading] = []
    for strategy in ("steady", "blitzscale"):  # target 2
        n = len(m13.t2_listed(r, strategy))
        _judge(known, Reading(f"M13.T2.{strategy}", n >= 4, -float(n), f"{n}/10 listed"))
    assert 0.0 <= m13.t2_first_day(r) <= 0.30
    assert m13.t3_miss_share(r) >= 0.60  # target 3
    assert m13.t3_price_ratio(r) <= 0.85
    m = r.t4  # target 4
    assert 4 <= m.early <= 15 and 8 <= m.late <= 25
    assert m.dec_2022 <= 0.70 * m.jan_2022
    assert 0.85 <= m13.t5_arr_ratio(r) <= 1.15  # target 5
    assert m13.t5_spent(r) <= 0.40
    _known(known)


def _known(known: list[Reading]) -> None:
    """Known misses (tst/balance/known_misses.py) within their bounds: xfail, naming them."""
    if known:
        text = "; ".join(f"{k.target} ({known_miss(k.target).owner}): {k.detail}" for k in known)  # type: ignore[union-attr]
        pytest.xfail(f"KNOWN MISS {text}")


def _judge(known: list[Reading], reading: Reading) -> None:
    v = verdict(reading)
    assert v != "fail", f"{reading.target}: {reading.detail}"
    if v == "known":
        known.append(reading)
