"""M53's 62.5 targets 2-4 (nightly; tst.balance.m53), on seeds 1-10: contested auctions clear at
1.5x the reserve or more (T2a), a network without mid-band holds 20% less of the mobile market
(T2b), a national 5G network pays back in 60 months or more (T3) and rip-and-replace costs 10%
of the network or more (T4). T1 is M28's history fingerprint and M30's state cache; T5 is `make
check-timing`. M57r-B (review 10 item 27): these printed and exited 0, with no test."""

from __future__ import annotations

import os
from statistics import median

import pytest

from tst.balance import m53


@pytest.mark.nightly
def test_62_5_targets_2_to_4() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    runs = m53.run(m53.SEEDS, workers=jobs)
    text = m53.report(runs)
    print(text)
    ratios = [r for x in runs for r in x.ratios]
    losses = [m53._loss(x.without_mid, x.with_mid) for x in runs]
    paid = [x.payback_months for x in runs]
    known = sorted(p for p in paid if p is not None)
    never = len(paid) - len(known)
    payback = median(known) if known and never < len(paid) / 2 else None
    assert median(ratios) >= m53.PRICE_RATIO, text
    assert median(losses) >= m53.SHARE_LOSS, text
    assert payback is None or payback >= m53.PAYBACK_MONTHS, text
    assert median(x.ban_share for x in runs) >= m53.BAN_SHARE, text
