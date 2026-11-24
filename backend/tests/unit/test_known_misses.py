"""The recorded known misses (tst/balance/known_misses.py): within the bound a miss is known,
beyond it or unlisted it fails (2026-11-05). M15a closed T2 and M10.T3 and recorded V3.ai
(owner M23) and V5's launch clauses (owner M23); M23b recorded I1 at year 30 (owner M28); M43
owned all four from its sub-task 1; M46 moved every entry M43 owned to M57, tightened bounds
and closed V3.margin and M10b.T1.spacing."""

from __future__ import annotations

from tst.balance.known_misses import KNOWN_MISSES, known_miss, verdict
from tst.balance.report import Row, table


def _ai(gap: float) -> Row:
    """30.7 V3's AI arm: integrator_ai's margin gap over ai_regions, +3 to +10 points."""
    return Row(
        "V3.ai", "margin gap", f"{gap:+.1%}", "+3 to +10 pts", 0.03 <= gap <= 0.10, score=-gap
    )


def test_the_list_after_m46() -> None:
    """M46 sub-task 3: no entry is owned by a finished milestone; every one M43 owned (and the
    "v6 balance" pass's) moves to M57; M37's 2069 month stays with v6's performance pass."""
    assert [m.target for m in KNOWN_MISSES][:4] == ["V3.ai", "V5.cells", "V5.cats", "I1"]
    owners = {m.target: m.owner for m in KNOWN_MISSES}
    assert set(owners.values()) == {"M57", "v6 performance"}
    assert owners["M37.2069_month"] == "v6 performance"
    for closed in ("T2", "M10.T3", "V3.margin", "M10b.T1.spacing"):
        assert known_miss(closed) is None


def test_v3_ai_known_until_two_points_below() -> None:
    assert verdict(_ai(0.05)) == "ok"
    assert [verdict(_ai(g)) for g in (0.009, 0.0, -0.02)] == ["known"] * 3
    assert verdict(_ai(-0.03)) == "fail"


def test_i1_known_until_its_year_30_reading_minus_two_points() -> None:
    """formulas 43 I1 at year 30: -1.1 points on M46, known down to -1.5 (M46; was -2.0)."""

    def i1(gap: float) -> Row:
        return Row("I1", "margin gap", f"{gap:+.1%}", "+3 to +10", 0.03 <= gap <= 0.10, score=-gap)

    assert verdict(i1(0.04)) == "ok"
    assert [verdict(i1(g)) for g in (0.001, -0.011, -0.015)] == ["known"] * 3
    assert verdict(i1(-0.016)) == "fail"


def test_closed_and_unlisted_misses_fail_and_the_table_says_known() -> None:
    t2 = Row("T2", "wins per strategy", "steady 8", "each <= 6/10", False, True, score=0.8)
    covenant = Row("M10.T3", "covenants", "70%", "20-60%", False, True, score=0.7)
    assert verdict(t2) == "fail" and verdict(covenant) == "fail"
    assert verdict(Row("T8", "printed", "$1", "printed", None)) == "printed"
    assert verdict(Row("V3.ai", "gap", "x", "y", False)) == "fail"  # no score: no pass
    text = table([_ai(0.009), t2])
    assert text.splitlines()[0].endswith("KNOWN MISS (M57)") and "FAIL T2" in text


def test_m35b_carries_t1_2_and_t4_to_m57() -> None:
    """M35b's v4 misses (docs/tasks/M35b-v4-balance.md): T1.2 known down to 0.80x, T4 known
    while power_hyperscaler's capacity is never later than cloud_steady's."""
    assert [m.target for m in KNOWN_MISSES][4:6] == ["V4.T1.2", "V4.T4"]
    assert {known_miss(t).owner for t in ("V4.T1.2", "V4.T4")} == {"M57"}  # type: ignore[union-attr]

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


def test_m37_money_is_closed_by_m43a() -> None:
    """The PM's money guard (2026-11-17; M37's brief, decision 22) passes since M43a's market
    ceilings (1.48e16 cents at most by 2069, seeds 1-4): no known miss, so any value over
    1.0e18 cents fails."""
    from tst.balance.m37 import MoneyRow

    assert "M37.money" not in [m.target for m in KNOWN_MISSES]

    def money(cents: float) -> MoneyRow:
        return MoneyRow("M37.money", cents < 1.0e18, cents / 1.0e18, f"{cents:.1e}")

    assert verdict(money(9.0e17)) == "ok"
    assert verdict(money(1.1e18)) == "fail"


def test_m43a_misses_are_known_to_m57_within_their_bounds() -> None:
    """PM, 2026-11-18 (M43a brief, decision 10): earlier guards moved by M43a's targeted
    recalibrations, owned by M43 and from M46 by M57, each with its bound (M22's tightened to
    21% and V3.margin closed in M46)."""
    from tst.balance.known_misses import Reading
    from tst.balance.report import Row

    for target in ("M13b.T1", "M22.T2.variant", "V4.T1.1"):
        assert known_miss(target).owner == "M57"  # type: ignore[union-attr]
    # V2.wins closed by steady_regions' once-a-month marketing (PM ruling 2026-11-21): 4/10
    assert known_miss("V2.wins") is None
    # closed by M43 sub-task 3 (25.1's floor at the game's economy): 10/10 listed

    def reading(target: str, score: float) -> str:
        return verdict(Reading(target, False, score))

    assert known_miss("M13.T2.blitzscale") is None
    assert reading("M13.T2.blitzscale", -1.0) == "fail"
    assert verdict(Reading("M13.T2.steady", False, -3.0)) == "fail"  # steady is not covered
    assert reading("M13b.T1", -6.0) == "known" and reading("M13b.T1", -5.0) == "fail"
    assert reading("M22.T2.variant", 0.21) == "known" and reading("M22.T2.variant", 0.22) == "fail"

    def row(target: str, score: float) -> str:
        return verdict(Row(target, "", "", "", False, score=score))

    assert row("V2.wins", 5.0) == "fail"
    assert row("V3.margin", 0.001) == "fail"  # closed in M46: +0.4 pts
    assert row("V4.T1.1", 0.30) == "known" and row("V4.T1.1", 0.31) == "fail"  # 0.85x
