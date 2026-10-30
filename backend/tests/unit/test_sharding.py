"""CI's matrix jobs split the backend tests by measured duration (tests/conftest.py)."""

from __future__ import annotations

from tests.conftest import shard_of


def test_every_test_runs_in_exactly_one_shard_and_the_split_is_balanced() -> None:
    durations = {"a": 10.0, "b": 7.0, "c": 6.0, "d": 4.0, "e": 3.0}
    ids = [*durations, "new"]  # "new" has no timing yet: it counts as the mean (6.0)
    shard = shard_of(ids, durations, 2)
    assert set(shard) == set(ids) and set(shard.values()) == {0, 1}
    totals = [sum(durations.get(n, 6.0) for n in ids if shard[n] == k) for k in (0, 1)]
    assert abs(totals[0] - totals[1]) <= 2.0
    assert shard_of(list(reversed(ids)), durations, 2) == shard  # same split in every worker


def test_without_timings_tests_are_spread_evenly() -> None:
    shard = shard_of([f"t{i}" for i in range(9)], {}, 3)
    assert sorted(list(shard.values()).count(k) for k in range(3)) == [3, 3, 3]
