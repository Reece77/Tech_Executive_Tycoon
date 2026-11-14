"""docs/formulas.md 41.8 target 1 (M28): history holds. A do-nothing game's prices, foundry
market, capacities, dated events and every company's ledger entries to December 2025, hashed by
year, equal main's from before M28 (tests/fixtures/m28_history.json, recorded on main by
tools/m28_targets.py --write-history). Seed 1 runs in `make check`; every seed of the guard set
nightly."""

from __future__ import annotations

import os

import pytest

from tst.balance import m28


def test_history_holds_on_seed_1() -> None:
    got = {"1": m28.history_fingerprint(1)}
    assert m28.history_diffs(got, m28.recorded_history()) == []


@pytest.mark.nightly
def test_history_holds_on_every_seed() -> None:
    got = m28.history_all(m28.SEEDS, os.cpu_count() or 1)
    assert m28.history_diffs(got, m28.recorded_history()) == []
