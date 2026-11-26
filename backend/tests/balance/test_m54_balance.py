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
