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
DEFERRED: dict[tuple[str, str], str] = {
    ("fabs/actions.py", "capex = round(q.capex_cents * fb.upgrade.capex_share)"): "M33",
    (
        "fabs/plants.py",
        "return mwh * balance.refining.power_cents_per_mwh * power.index(state, facility.region,"
        " data)",
    ): "M32 (a rate)",
    (
        "mining/phase.py",
        "sustaining = mb.sustaining_share * mine.capex_paid_cents / CENTS / 12 if running else 0.0",
    ): "M32",
    ("mining/phase.py", "sustaining = mb.sustaining_share * mine.capex_cents / CENTS"): "M32",
    (
        "refining/quote.py",
        "rg.price_cents(state, r.input_good, balance, data) * per_in if r.input_good else 0.0",
    ): "M32 (a rate)",
    ("refining/quote.py", "fixed = size * r.fixed_cents / out_year if out_year else 0.0"): (
        "M32 (a rate)"
    ),
    (
        "refining/quote.py",
        "dep = q.capex_cents / (kind.life_months / MONTHS) / out_year if out_year else 0.0",
    ): "M32 (a rate)",
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
