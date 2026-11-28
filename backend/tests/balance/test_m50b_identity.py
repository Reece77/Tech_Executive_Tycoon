"""M50b's guard (docs/tasks/M50b-the-2000-start.md, "Lane"): a 2008 game and a 2010 game are
identical to `main` before M50b. M30's strategies full_integrator and research_heavy on seeds
1-2, 120 months from each start, every month's full-state digest equal to the one recorded on
`main` before any M50b change (tests/fixtures/m50b_identity_hashes.json, tst.balance.m50b)."""

from __future__ import annotations

import pytest

from tst.balance import m50b


@pytest.mark.nightly
@pytest.mark.parametrize("job", m50b.identity_jobs(), ids=m50b.identity_key)
def test_2008_and_2010_games_identical_to_main_before_m50b(job: m50b.Job) -> None:
    want = m50b.identity_recorded()[m50b.identity_key(job)]
    got = m50b.identity_run(job)
    assert (
        d := m50b.identity_differences(
            {m50b.identity_key(job): got}, {m50b.identity_key(job): want}
        )
    ) == [], d


def test_the_first_months_of_each_start_match_main() -> None:
    """Fast form (make check): twelve months of a 2008 and a 2010 game."""
    for job in [("research_heavy", 1, 2008), ("research_heavy", 1, 2010)]:
        want = m50b.identity_recorded()[m50b.identity_key(job)][:12]
        assert m50b.identity_run(job, months=12) == want, m50b.identity_key(job)


@pytest.mark.nightly
def test_the_2000_world_holds_its_history() -> None:
    """Sub-task 4: M28's fingerprint of a do-nothing 2000 game, 2000-2009 on seeds 1-10, equals
    the one M50b recorded (tests/fixtures/m50b_history_2000.json): later changes to the 2000
    world are seen."""
    got = m50b.history_all(m50b.HISTORY_SEEDS)
    want = m50b.recorded_history()
    diffs = [
        f"seed {seed} {series} {year}"
        for seed, by_series in got.items()
        for series, years in by_series.items()
        for year, h in years.items()
        if want.get(seed, {}).get(series, {}).get(year) != h
    ]
    assert diffs == []
