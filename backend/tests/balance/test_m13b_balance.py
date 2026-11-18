"""docs/formulas.md 27.5 targets 1-5 (M13b), nightly; tools/m13b_targets.py prints the same.
Values recorded in the M13b brief and docs/balance-targets.md."""

from __future__ import annotations

import os

import pytest

from tst.balance import m13b
from tst.balance.known_misses import Reading, known_miss, verdict


@pytest.mark.nightly
def test_27_5_targets() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    results = m13b.run(m13b.SEEDS, jobs)
    print(m13b.report(results))
    assert len(m13b.arm(results, "pitches")) >= 7  # enough seeds reach stage 3
    known: list[Reading] = []
    t1 = m13b.target_1(results)  # a new product and a new region
    _judge(known, Reading("M13b.T1", t1 >= 7, -float(t1), f"{t1}/10 seeds"))
    assert m13b.target_2(results) >= 1.10  # and it pays
    good, weak = m13b.target_3(results)
    assert good - weak >= m13b.T3_POINTS  # good executives pitch better (+10 points)
    assert m13b.target_4(results) <= 8  # the inbox stays calm
    n, _ = m13b.target_5(results)
    assert n >= 7  # the first-mover window adds 25-60% customers
    assert m13b.target_7(results) <= m13b.T7_RATIO  # pitches don't outplay the founder by far
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
