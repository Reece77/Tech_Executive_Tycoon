"""The recorded known misses (tst/balance/known_misses.py): within the bound a miss is known,
beyond it or unlisted it fails (2026-11-05)."""

from __future__ import annotations

from tst.balance.known_misses import KNOWN_MISSES, known_miss, verdict
from tst.balance.report import Row, table


def _t2(most: int, seeds: int = 10) -> Row:
    cap = 6 * seeds / 10
    return Row(
        "T2",
        "wins per strategy",
        f"steady {most}",
        "each <= 6/10",
        most <= cap,
        True,
        score=most / seeds,
    )


def test_t2_is_known_to_m15() -> None:
    k = known_miss("T2")
    assert k is not None and k.owner == "M15"
    assert [m.target for m in KNOWN_MISSES] == ["T2", "M10.T3"]


def test_covenant_guard_known_until_90_percent() -> None:
    """M10's 20.5 target 3 (product manager, 2026-11-04): known while under 90%."""

    def row(rate: float) -> Row:
        return Row("M10.T3", "covenants", f"{rate:.0%}", "20-60%", rate <= 0.6, True, score=rate)

    assert verdict(row(0.6)) == "ok"
    assert [verdict(row(r)) for r in (0.7, 0.8, 21 / 30)] == ["known"] * 3
    assert verdict(row(0.9)) == "fail"


def test_t2_fails_only_when_one_strategy_wins_every_seed() -> None:
    assert verdict(_t2(6)) == "ok"
    assert [verdict(_t2(n)) for n in (7, 8, 9)] == ["known"] * 3
    assert verdict(_t2(10)) == "fail"


def test_other_misses_still_fail_and_the_table_says_known() -> None:
    other = Row("T1", "do-nothing fails", "9/10", "all", False, True, score=0.9)
    assert verdict(other) == "fail"
    assert verdict(Row("T8", "printed", "$1", "printed", None)) == "printed"
    assert verdict(Row("T2", "wins", "x", "y", False, True)) == "fail"  # no score: no pass
    text = table([_t2(8), other])
    assert "MISS T2" in text and text.splitlines()[0].endswith("KNOWN MISS (M15)")
    assert text.splitlines()[1].startswith("FAIL T1")
