"""docs/formulas.md 19.8 targets 2, 3 and 5 (M9); tools/m9_targets.py prints the same.
Target 3 is quick and runs in PR CI; 2 and 5 play 120 turns per seed and are nightly."""

from __future__ import annotations

import os

import pytest

from tst.balance import m9

EXPANSION_NEEDED = 1.4
SAVING_NEEDED = 0.5


def _jobs() -> int:
    return int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))


def test_target_3_cheap_talent_has_a_cost() -> None:
    cost = m9.team_cost()
    print(
        f"19.8 target 3: SF {cost.sf_cents}, Bangalore {cost.bangalore_cents} cents a month, "
        f"{cost.saving:.1%} less; split factor {cost.split_factor:.2f}"
    )
    assert cost.saving >= SAVING_NEEDED
    assert cost.split_factor == pytest.approx(0.95)


@pytest.mark.nightly
def test_target_2_expansion_lifts_the_ceiling() -> None:
    runs = m9.run_expansion(m9.SEEDS, _jobs())
    value = m9.expansion_ratio([r for r, _ in runs])
    print(f"19.8 target 2: {value:.3f} (needs >= {EXPANSION_NEEDED})")
    assert value >= EXPANSION_NEEDED


@pytest.mark.nightly
def test_target_5_rivals_spread() -> None:
    spreads = m9.run_spread(m9.SEEDS, _jobs())
    missing = {s.seed: s.missing for s in spreads if s.missing}
    print(f"19.8 target 5: {len(spreads) - len(missing)}/{len(spreads)} seeds fully covered")
    assert missing == {}
