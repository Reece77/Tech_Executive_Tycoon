"""docs/formulas.md 39.4 targets (M22), nightly; tools/m22_targets.py prints the same. Values
recorded in docs/balance-targets.md (M22) and the M22 brief. Target 7 also has a fast test
(tests/unit/test_m22_domestic.py)."""

from __future__ import annotations

import os

import pytest

from tst.balance import m22
from tst.balance.known_misses import Reading, known_miss, verdict


@pytest.mark.nightly
def test_39_4_targets() -> None:
    r = m22.run(m22.SEEDS, os.cpu_count() or 1)
    print(m22.report(r))
    _checked, misses, follows = r.t1
    assert misses == 0 and follows  # target 1
    assert all(0.15 <= x.loss <= 0.30 for x in r.t2)  # target 2
    known: list[Reading] = []
    v_lo, v_hi = min(x.loss_variant for x in r.t2), max(x.loss_variant for x in r.t2)
    ok = all(0.05 <= x.loss_variant <= 0.15 for x in r.t2)
    score = v_hi if v_lo >= 0.05 else 1.0  # below 5% is not what the bound covers
    _judge(known, Reading("M22.T2.variant", ok, score, f"{v_lo:.1%}-{v_hi:.1%}"))
    assert all(0.30 <= p <= 0.80 for p in r.t3)  # target 3
    lo, hi = r.t4
    assert hi >= 1.2 * lo  # target 4
    assert all(0.08 <= v <= 0.20 for y, v in r.t5 if y >= 2019)  # target 5
    assert 7 <= sum(1 for _, e, d in r.t6 if e and d) <= 10  # target 6
    assert r.t7  # target 7
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
