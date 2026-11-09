"""39.4 target 7 (M22): a software-only company in North America and Europe plays exactly as
before. The same seed run through 2018-2023 with and without M22's data gives the same ledger,
snapshots, events and products."""

from __future__ import annotations

from tst.balance import m22


def test_a_software_company_plays_exactly_as_before() -> None:
    assert m22.target_7(seed=2, turns=24)
