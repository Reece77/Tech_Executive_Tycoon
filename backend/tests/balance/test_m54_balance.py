"""M54's guards and targets (formulas.md 64.6). Sub-task 2: a North-America-only company's game is
identical with and without currencies: the full state to December 2025 and, to December 2029, its
currency footprint, empty (seeds 1-3, 240 months, M30's digest; tst.balance.m54 and M54 decision
6); in the regular suite on seed 1 for 36 months."""

from __future__ import annotations

import pytest

from tst.balance import m54


def test_north_america_only_is_unchanged_by_currencies_short() -> None:
    assert m54.na_only_digests(1, 36) == m54.na_only_digests(1, 36, fx=False)


@pytest.mark.nightly
@pytest.mark.parametrize("seed", m54.NA_SEEDS)
def test_north_america_only_is_unchanged_by_currencies(seed: int) -> None:
    got = m54.na_only_digests(seed)
    want = m54.na_only_digests(seed, fx=False)
    assert len(got) == m54.NA_TURNS
    assert got == want
    empty = m54.Digester().digest(((), (), (), (), (), ()))
    assert all(g == m54.hashlib.sha256(empty).hexdigest()[:16] for g in got[m54.WORLD_TURNS :])


@pytest.mark.nightly
def test_64_6_targets_2_to_5() -> None:
    """64.6 targets 2-5 on seeds 1-10 (tst.balance.m54, tools/m54_targets.py); target 5 is a
    known miss owned by M57 (PM ruling 2026-11-26, M54 decision 13)."""
    import os
    from statistics import median

    from tst.balance.known_misses import Reading, known_miss, verdict

    rows = m54.run(m54.SEEDS, os.cpu_count() or 1)
    lo, hi = m54.NIM_BAND
    assert all(lo <= r["t2"]["nim"] <= hi for r in rows)  # target 2
    assert all(r["t2"]["profit_rate_corr"] > 0 for r in rows)
    assert sum(bool(r["t3_high"]) for r in rows) >= m54.RUN_MIN  # target 3
    assert not any(r["t3_low"] for r in rows)
    kept = sum(1 for r in rows if r["t4"] and r["t4"][-1] >= m54.NETWORK_SHARE)
    assert kept >= m54.NETWORK_MIN  # target 4
    cut = median(r["t5"]["reduction"] for r in rows)  # target 5
    reading = Reading("M54.T5", cut >= m54.HEDGE_CUT, m54.HEDGE_CUT - cut, f"{cut:.1%}")
    v = verdict(reading)
    assert v != "fail", f"{reading.target}: {reading.detail}"
    if v == "known":
        owner = known_miss(reading.target).owner  # type: ignore[union-attr]
        pytest.xfail(f"KNOWN MISS M54.T5 ({owner}): {reading.detail}")
