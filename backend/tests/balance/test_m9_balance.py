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


AFRICA_BROADBAND = ("africa", "fixed_broadband")  # M57r-B: M9.spread.africa, a known miss


@pytest.mark.nightly
def test_target_5_rivals_spread() -> None:
    """Every (region, category) cell has a live rival product at month 120 on every seed.
    M57r-B (ruling 6): Africa's fixed broadband, empty since M53 (no fixed-broadband rival
    there), is the known miss M9.spread.africa (owner M57, bound 10/10 seeds); any other empty
    cell, on any seed, still fails."""
    from tst.balance.known_misses import Reading, known_miss, verdict

    spreads = m9.run_spread(m9.SEEDS, _jobs())
    missing = {s.seed: s.missing for s in spreads if s.missing}
    print(f"19.8 target 5: {len(spreads) - len(missing)}/{len(spreads)} seeds fully covered")
    others = {seed: [c for c in cells if c != AFRICA_BROADBAND] for seed, cells in missing.items()}
    assert {seed: cells for seed, cells in others.items() if cells} == {}
    africa = sum(AFRICA_BROADBAND in cells for cells in missing.values())
    reading = Reading("M9.spread.africa", africa == 0, float(africa), f"{africa}/{len(spreads)}")
    assert verdict(reading) != "fail", reading
    if verdict(reading) == "known":
        known = known_miss(reading.target)
        assert known is not None
        pytest.xfail(f"KNOWN MISS ({known.owner}): {known.reason}")
