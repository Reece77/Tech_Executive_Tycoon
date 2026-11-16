"""The recorded known misses (tst/balance/known_misses.py): within the bound a miss is known,
beyond it or unlisted it fails (2026-11-05). M15a closed T2 and M10.T3 and recorded V3.ai
(owner M23) and V5's launch clauses (owner M23); M23b recorded I1 at year 30 (owner M28)."""

from __future__ import annotations

from tst.balance.known_misses import KNOWN_MISSES, known_miss, verdict
from tst.balance.report import Row, table


def _ai(gap: float) -> Row:
    """30.7 V3's AI arm: integrator_ai's margin gap over ai_regions, +3 to +10 points."""
    return Row(
        "V3.ai", "margin gap", f"{gap:+.1%}", "+3 to +10 pts", 0.03 <= gap <= 0.10, score=-gap
    )


def test_the_list_after_m23b() -> None:
    assert [m.target for m in KNOWN_MISSES][:4] == ["V3.ai", "V5.cells", "V5.cats", "I1"]
    owners = {m.target: m.owner for m in KNOWN_MISSES}
    assert {k: owners[k] for k in ("V3.ai", "V5.cells", "V5.cats", "I1")} == {
        "V3.ai": "M28",
        "V5.cells": "M28",
        "V5.cats": "M28",
        "I1": "M28",
    }
    assert known_miss("T2") is None and known_miss("M10.T3") is None


def test_v3_ai_known_until_two_points_below() -> None:
    assert verdict(_ai(0.05)) == "ok"
    assert [verdict(_ai(g)) for g in (0.009, 0.0, -0.02)] == ["known"] * 3
    assert verdict(_ai(-0.03)) == "fail"


def test_i1_known_until_its_year_30_reading_minus_two_points() -> None:
    """formulas 43 I1 at year 30: -0.0 points in M23b, known down to -2.0 (PM, 2026-11-12)."""

    def i1(gap: float) -> Row:
        return Row("I1", "margin gap", f"{gap:+.1%}", "+3 to +10", 0.03 <= gap <= 0.10, score=-gap)

    assert verdict(i1(0.04)) == "ok"
    assert [verdict(i1(g)) for g in (0.001, -0.01, -0.02)] == ["known"] * 3
    assert verdict(i1(-0.021)) == "fail"


def test_closed_and_unlisted_misses_fail_and_the_table_says_known() -> None:
    t2 = Row("T2", "wins per strategy", "steady 8", "each <= 6/10", False, True, score=0.8)
    covenant = Row("M10.T3", "covenants", "70%", "20-60%", False, True, score=0.7)
    assert verdict(t2) == "fail" and verdict(covenant) == "fail"
    assert verdict(Row("T8", "printed", "$1", "printed", None)) == "printed"
    assert verdict(Row("V3.ai", "gap", "x", "y", False)) == "fail"  # no score: no pass
    text = table([_ai(0.009), t2])
    assert text.splitlines()[0].endswith("KNOWN MISS (M28)") and "FAIL T2" in text


def test_m35b_carries_t1_2_and_t4_to_m43() -> None:
    """M35b's v4 misses (docs/tasks/M35b-v4-balance.md): T1.2 known down to 0.80x, T4 known
    while power_hyperscaler's capacity is never later than cloud_steady's."""
    assert [m.target for m in KNOWN_MISSES][4:] == ["V4.T1.2", "V4.T4"]
    assert {known_miss(t).owner for t in ("V4.T1.2", "V4.T4")} == {"M43"}  # type: ignore[union-attr]

    def t12(r: float) -> Row:
        return Row(
            "V4.T1.2", "ratio", f"{r:.2f}x", "0.90-1.40x", 0.9 <= r <= 1.4, score=abs(r - 1.15)
        )

    def t4(gap: float) -> Row:
        return Row("V4.T4", "gap", f"{gap:+.0f}", ">= 12", gap >= 12, score=-gap)

    assert verdict(t12(1.0)) == "ok" and verdict(t4(24)) == "ok"
    assert [verdict(t12(r)) for r in (0.89, 0.82, 0.80)] == ["known"] * 3
    assert verdict(t12(0.79)) == "fail" and verdict(t12(1.51)) == "fail"
    assert [verdict(t4(g)) for g in (11, 0)] == ["known"] * 2
    assert verdict(t4(-1)) == "fail"
