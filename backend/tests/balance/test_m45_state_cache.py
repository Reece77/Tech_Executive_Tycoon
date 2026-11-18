"""M45's long state-cache check (docs/tasks/M45-performance-at-scale-part-two.md sub-task 1):
M37's dynasty game on seeds 1-3, 720 months each (January 2010 to December 2069), every month's
full-state digest equal to the one recorded before any M45 change
(tests/fixtures/m45_dynasty_hashes.json, tools/m45_state_hashes.py). A speed-up never changes a
result. Weekly (`make weekly-m45`): each run takes about 14 minutes.

`--update-state-cache` re-records this fixture too, by M30's rule: only for an intentional
change of results, with the reason in CHANGELOG.md.
"""

from __future__ import annotations

import os

import pytest

from tst.balance import m30, m45


def _updating(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-state-cache"))


@pytest.mark.weekly
def test_update_the_fixture(request: pytest.FixtureRequest) -> None:
    """With --update-state-cache: play the three runs and write the fixture."""
    if not _updating(request):
        pytest.skip("only with --update-state-cache")
    m45.write(m45.all_hashes(os.cpu_count() or 1))


@pytest.mark.weekly
@pytest.mark.parametrize("seed", m45.SEEDS)
def test_720_months_identical_to_the_fixture(seed: int, request: pytest.FixtureRequest) -> None:
    if _updating(request):
        pytest.skip("re-recording the fixture (test_update_the_fixture)")
    want = m45.recorded()[m45.key(seed)]
    got = m45.run_hashes(seed)
    assert m30.first_difference(got, want) is None, m30.first_difference(got, want)


def test_the_fixture_covers_720_months_of_three_seeds() -> None:
    got = m45.recorded()
    assert sorted(got) == sorted(m45.key(s) for s in m45.SEEDS)
    assert all(len(v) == m45.TURNS for v in got.values())


def test_a_short_dynasty_run_matches_the_fixture(request: pytest.FixtureRequest) -> None:
    """The first months of seed 1, against the fixture (fast enough for every check)."""
    first = m45.run_hashes(1, turns=4)
    assert first == m45.run_hashes(1, turns=4)
    if not _updating(request):
        assert first == m45.recorded()[m45.key(1)][:4]
