"""docs/formulas.md 52.5 targets (M37), nightly; tools/m37_targets.py prints the same. Values
are recorded in the M37 brief ("Decisions made").

Target 1 (nothing moves before 2040) replays M30's nine state-cache runs to December 2039 with
dynasty mode off and on, M37's fields left out of the digest, against the digests recorded
before M37 (tests/fixtures/m37_pre_2040_hashes.json: mode parity), and against the same code
with M37's rules disabled (M43r: the same-code differential). Targets 2-4 play ten dynasty
games with a family to December 2069. Target 5 (turn time and save size at 2069) is the
weekly-m37 job's."""

from __future__ import annotations

import os

import pytest

from tst.balance import m37
from tst.balance.known_misses import known_miss, verdict

JOBS = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))


_RUNS: dict[bool, dict[str, list[str]]] = {}  # each setting's runs, played once a session
_REFERENCE: dict[str, list[str]] = {}  # the reference arm's runs (M43r)


def _pre_2040(dynasty: bool) -> dict[str, list[str]]:
    if dynasty not in _RUNS:
        _RUNS[dynasty] = m37.all_pre_2040(JOBS, (dynasty,))
    return _RUNS[dynasty]


@pytest.mark.nightly
@pytest.mark.parametrize("dynasty", [False, True], ids=["standard", "dynasty"])
def test_52_5_target_1_nothing_moves_before_2040(dynasty: bool) -> None:
    """Mode parity: both settings against the recorded digests."""
    runs = _pre_2040(dynasty)
    diff = {k: v for k, v in m37.compare(runs, m37.legacy()).items() if v is not None}
    assert diff == {}


@pytest.mark.nightly
@pytest.mark.parametrize("dynasty", [False, True], ids=["standard", "dynasty"])
def test_52_5_target_1_same_code_differential(dynasty: bool) -> None:
    """M43r (Codex review 9 finding 14): each run against the same code with M37's rules
    disabled (m37.reference_loaded); a change both settings share still shows."""
    if not _REFERENCE:
        _REFERENCE.update(m37.all_reference(JOBS))
    diff = {
        k: v for k, v in m37.differential(_pre_2040(dynasty), _REFERENCE).items() if v is not None
    }
    assert diff == {}


@pytest.mark.nightly
def test_52_5_targets_2_to_4() -> None:
    results = m37.run_all(JOBS)
    print(m37.report(results))
    x = m37.readings(results)
    n = len(results)
    assert x.eras_median >= 4  # target 2
    assert x.rivals_ok_seeds >= 0.9 * n, x.thin  # target 2
    assert x.commodity_ok, x.excursions  # target 2
    assert x.gaps_lengthen and x.cost_ratio_min >= 0.5  # target 3
    assert x.succession_seeds >= 0.9 * n  # target 4
    _money_guard(results)


def _money_guard(results: list[m37.DynastyResult]) -> None:
    """The PM's guard (2026-11-17): no ledger balance (a company's account, the cumulative
    total SQLite sums) passes 1.0e18 cents in a dynasty run to 2069; known miss owned by M43
    while it still fits int64 (tst/balance/known_misses.py)."""
    row = m37.money_row(results)
    print(m37.diagnosis(results, m37.m30.loaded().balance.economy_scale.money))
    v = verdict(row)
    assert v != "fail", row.detail
    if v == "known":
        k = known_miss(row.target)
        assert k is not None
        pytest.xfail(f"KNOWN MISS ({k.owner}): {k.reason}; {row.detail}")


@pytest.mark.nightly
def test_a_short_dynasty_run_repeats() -> None:
    """The same seed continues the same way (sub-task 3's seeded test): two dynasty runs of a
    family game into 2040 on the same seed give the same digests."""
    first = m37.dynasty_digests(4, 366)
    assert first == m37.dynasty_digests(4, 366)
