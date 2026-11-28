"""M36r sub-task 2 (Codex review 7; ADR-0003): no new float arithmetic on money in tst/sim/.

The scan is tests/money_guard.py (an AST check). A new occurrence fails here: fix it with
tst.sim.money's exact helpers (`exact`, `times`, `pct_of`, Fraction), or, when it is not a
money amount or is provably exact, add `# money-exact: <why>` on its line or the line above.
"""

from __future__ import annotations

from pathlib import Path

from tests.money_guard import Hit, scan

# Lines in files another lane is editing in flight (M36r decision: not edited here, to keep
# their merges clean; each is in the M36r audit table and handed to that lane). Keyed by the
# line's code, so a line moving does not break the guard; a deferred line that is fixed
# drops out (see the last test).
# M57r-A: lane B (M57r-B) owns tst/sim/talks/; this line's `value` is a hidden trait (a ratio,
# not money), named by review 10's extended aliases. Lane B annotates it, then it leaves the list.
DEFERRED: dict[tuple[str, str], str] = {
    (
        "talks/opening.py",
        "out.append((move, max(lo, min(hi, 1 + weight * (value - MID_TRAIT) / TRAIT_SPAN))))",
    ): "M57r-B: a trait's weight (ratio), not money",
}


def _key(h: Hit) -> tuple[str, str]:
    return (h.path, h.code)


def test_no_float_money_arithmetic_in_the_sim() -> None:
    new = [str(h) for h in scan() if _key(h) not in DEFERRED]
    assert new == [], "float arithmetic on money (see tests/money_guard.py):\n" + "\n".join(new)


def test_every_deferred_line_is_still_there() -> None:
    """A deferred line that has been fixed (or moved) leaves the list: keep it current."""
    found = {_key(h) for h in scan()}
    assert set(DEFERRED) <= found, set(DEFERRED) - found


SNIPPET = """
from dataclasses import dataclass
from fractions import Fraction


@dataclass
class App:
    paid_share: float
    users: float


def fee_for(app: App) -> float:
    return 0.15


def f(revenue_cents: int, app: App, rate: float, n: int, q: Fraction) -> None:
    a = round(revenue_cents * 0.15)  # flag
    b = round(revenue_cents * app.paid_share * app.users)  # flag
    c = round(revenue_cents * fee_for(app))  # flag
    d = round(revenue_cents * rate)  # flag
    e = revenue_cents / 12  # flag
    share = float(n)
    g = round(revenue_cents * share)  # flag
    h = round(revenue_cents * exact(app.paid_share) * exact(app.users))
    i = times(revenue_cents, rate)
    j = round(Fraction(revenue_cents, 12))
    k = round(exact(rate) * revenue_cents / 12)
    m = revenue_cents * n // 12
    o = round(revenue_cents * q)
    t = f"{revenue_cents / 100:,.0f}"
"""


def test_the_scan_catches_floats_and_passes_exact_arithmetic(tmp_path: Path) -> None:
    pkg = tmp_path / "sim"
    pkg.mkdir()
    (pkg / "snippet.py").write_text(SNIPPET, encoding="utf-8")
    flagged = [i + 1 for i, line in enumerate(SNIPPET.splitlines()) if line.endswith("# flag")]
    assert [h.line for h in scan(pkg)] == flagged


def test_the_allow_comment_and_the_line_above_are_honoured(tmp_path: Path) -> None:
    pkg = tmp_path / "sim"
    pkg.mkdir()
    (pkg / "x.py").write_text(
        "def f(price_cents: int) -> float:\n"
        "    a = price_cents * 0.5  # money-exact: ratio\n"
        "    # money-exact: rate\n"
        "    b = price_cents * 0.25\n"
        "    return price_cents * 0.75\n",
        encoding="utf-8",
    )
    assert [h.line for h in scan(pkg)] == [5]


# --- M43r (Codex review 9 finding 10): money under other names, unpacking, mapping iteration --

ALIASES_SNIPPET = """
from dataclasses import dataclass


@dataclass
class Rates:
    cost_shares: dict[str, float]
    royalty: float


def rate_pair() -> tuple[float, float]:
    return 0.1, 0.2


def f(cents: int, rates: Rates, revenue: dict[int, int], sales: int, pid: int) -> None:
    for account, s in sorted(rates.cost_shares.items()):
        cost = round(cents * s)  # flag
    for s in rates.cost_shares.values():
        a = round(cents * s)  # flag
    b = round(sales * rates.royalty)  # flag
    got = revenue.get(pid, 0)
    c = round(got * rates.royalty)  # flag
    lo, hi = rate_pair()
    d = round(cents * hi)  # flag
    e = round(revenue[pid] * rates.royalty)  # flag
    g = times(sales, rates.royalty)
    for account, n in sorted(revenue.items()):
        h = round(cents * n)
"""


def test_the_scan_follows_money_aliases_unpacking_and_mapping_iteration(tmp_path: Path) -> None:
    """Each flagged line is one the M36r guard passed (review 9's rival COGS line is the first)."""
    pkg = tmp_path / "sim"
    pkg.mkdir()
    (pkg / "snippet.py").write_text(ALIASES_SNIPPET, encoding="utf-8")
    flagged = [
        i + 1 for i, line in enumerate(ALIASES_SNIPPET.splitlines()) if line.endswith("# flag")
    ]
    assert [h.line for h in scan(pkg)] == flagged
