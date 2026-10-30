"""M6 balance targets (formulas.md 16.10), printed and checked over 120 turns on 10 seeds of the
M3a earn-and-burn script, with MockLLMAdapter writing events and the first choice taken (Continue
answers minor and major events; the script answers a critical one with its first choice). Run
with `-s` for the table; the M6 brief's Decisions made records it.

- 1.0 to 1.6 events a month on average (Reece, 2026-10-29: aim for about 1.2);
- at most one critical event in any 6 months;
- events' combined cash effect within 5% of cumulative revenue;
- events' combined effect on average employee morale within 3 points on every seed (each run's
  average morale against the same seed without events; docs/balance-targets.md E2, M7a: every
  seed, not only the mean);
- at least 40 distinct templates used across the 10 runs;
- the M5 targets still hold (tests/integration/test_rival_balance.py, unchanged).
"""

from __future__ import annotations

from collections import Counter
from itertools import pairwise
from statistics import mean

import pytest

from tests.balance_scripts import earn_and_burn
from tst.loader import LoadedData

SEEDS = range(1, 11)
TURNS = 120
RATE = (1.0, 1.6)
CRITICAL_GAP = 6
CASH_SHARE = 0.05
MORALE_POINTS = 3.0
DISTINCT = 40


@pytest.mark.nightly  # statistical balance target (M7a: nightly, D4a)
def test_event_balance(loaded: LoadedData) -> None:
    rates, cash_shares, morale_effects = [], [], []
    templates: Counter[str] = Counter()
    for seed in SEEDS:
        run = earn_and_burn(loaded, seed, TURNS, events=True)
        base = earn_and_burn(loaded, seed, TURNS, events=False)
        months = len(run.snapshots)
        events = [e for e in run.state.events if e.company_id == 1]
        criticals = sorted(e.turn for e in events if e.severity == "critical")
        assert all(b - a >= CRITICAL_GAP for a, b in pairwise(criticals))
        cash = sum(
            effect.value
            for e in events
            if (choice := e.choice(e.chosen or "")) is not None
            for effect in choice.effects
            if effect.type == "cash_delta"
        )
        revenue = sum(s.mrr_cents for s in run.snapshots)
        morale = mean(s.avg_morale for s in run.snapshots if s.avg_morale is not None) - mean(
            s.avg_morale for s in base.snapshots if s.avg_morale is not None
        )
        rates.append(run.event_requests / months)
        cash_shares.append(cash / revenue if revenue else 0.0)
        morale_effects.append(morale)
        templates.update(e.template_id for e in events)
        print(
            f"\nseed {seed:2d}: {run.event_requests} events in {months} months "
            f"({rates[-1]:.2f} a month), critical {criticals}, event cash "
            f"${cash / 100:,.0f} = {cash_shares[-1]:+.1%} of revenue, morale {morale:+.2f}"
        )
    print(
        f"\nevents a month {mean(rates):.2f} | cash {mean(cash_shares):+.2%} of revenue "
        f"(worst {max(cash_shares, key=abs):+.2%}) | morale {mean(morale_effects):+.2f} "
        f"(worst {max(morale_effects, key=abs):+.2f}) | distinct templates {len(templates)}"
    )
    assert RATE[0] <= mean(rates) <= RATE[1]
    assert all(abs(share) <= CASH_SHARE for share in cash_shares)
    assert all(abs(effect) <= MORALE_POINTS for effect in morale_effects)
    assert len(templates) >= DISTINCT
