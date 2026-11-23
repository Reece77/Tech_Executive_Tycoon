"""M47's 58.5 targets as a guard (tst.balance.m47): on seeds 1-3, the scripted strong and weak
negotiators land in their bands, nobody beats a reservation, always threatening loses at least
30% of deals, and an acquisition's skip is today's second counter. The full run (seeds 1-10)
is tools/m47_targets.py, printed in the brief."""

from __future__ import annotations

from statistics import mean, median

from tst.balance import m47

SEEDS = (1, 2, 3)


def test_talking_matters_within_limits() -> None:
    for name in ("strong", "weak"):
        rows = m47.play(name, SEEDS, 20)
        lo, hi = m47.BANDS[name]
        assert lo <= mean(x for r in rows for x in r.shares) <= hi, name
        assert sum(r.beyond for r in rows) == 0


def test_always_threatening_loses_deals() -> None:
    rows = m47.play("threat", SEEDS, 20)
    lost = sum(r.walked for r in rows) / sum(r.deals for r in rows)
    assert lost >= m47.WALKS


def test_an_acquisitions_skip_is_todays_second_counter() -> None:
    assert median(m47.acquisition_skip_gaps((1,))) <= m47.SKIP_GAP
