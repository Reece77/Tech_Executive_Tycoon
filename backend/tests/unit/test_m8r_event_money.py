"""M8r finding 6 (Codex review 1, P2): event money is exact. A raise and every cash effect
are computed with integers and Fractions and rounded half-to-even once, at the end
(ADR-0003). A number written as a decimal (a template's share, a percent) means that decimal."""

from __future__ import annotations

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game, make_person, with_employee
from tst.loader import LoadedData
from tst.sim.events.effects import apply_choice
from tst.sim.events.formulas import cash_base_cents, clamp_effect, share_value
from tst.sim.events.models import Effect, EventChoice, GameEvent
from tst.sim.money import BP_DENOMINATOR

EMPLOYEE = 2


def _raised(loaded: LoadedData, salary_cents: int, percent: float) -> int:
    state = with_employee(
        loaded, fresh_game(loaded), make_person(loaded, EMPLOYEE, "software_engineer", "mid"),
        salary_cents,
    )  # fmt: skip
    effect = Effect("salary_change", f"person:{EMPLOYEE}", percent)
    event = GameEvent(
        id=99, company_id=1, turn=state.turn, template_id="m8r", category="personnel",
        severity="major", trigger="test", strength=1.0, person_ids=(EMPLOYEE,),
        status="open", choices=(EventChoice("A", "Raise", (effect,)),),
    )  # fmt: skip
    out, _, _ = apply_choice(state, event, "A", loaded.balance, loaded.game_data, auto=False)
    employment = out.employment_of(EMPLOYEE)
    assert employment is not None
    return employment.salary_cents


def test_a_ten_percent_raise_rounds_the_half_cent_to_even(loaded: LoadedData) -> None:
    """5,242,895 x 1.1 = 5,767,184.5 exactly: half-to-even gives 5,767,184 (floats gave 185)."""
    assert _raised(loaded, 5_242_895, 10) == 5_767_184


def _exact(x: float) -> Fraction:
    return Fraction(repr(x))


@settings(max_examples=200, deadline=None)
@given(
    salary=st.integers(1_000_000, 60_000_000),
    tenths=st.integers(1, 100),  # 0.1% .. 10.0%, within the major cap
)
def test_raises_equal_exact_arithmetic(loaded: LoadedData, salary: int, tenths: int) -> None:
    percent = tenths / 10
    expected = round(salary * (1 + _exact(percent) / 100))
    assert _raised(loaded, salary, percent) == expected


SEVERITIES = st.sampled_from(["minor", "major", "critical"])


@settings(max_examples=300, deadline=None)
@given(
    base=st.integers(0, 5_000_000_000),
    thousandths=st.integers(-1500, 1500),
    severity=SEVERITIES,
)
def test_cash_shares_equal_exact_arithmetic(
    loaded: LoadedData, base: int, thousandths: int, severity: str
) -> None:
    events = loaded.balance.events
    share = thousandths / 1000
    gain = share > 0
    cap = Fraction(base) * _exact(events.cap("cash_delta", severity)) / BP_DENOMINATOR
    if gain:
        cap *= _exact(events.cash_gain_share)
    value = _exact(share) * cap
    expected = round(max(-cap, min(cap, value)))
    got = share_value("cash_delta", share, severity, events, base)  # type: ignore[arg-type]
    assert got == expected and got == int(got)


@settings(max_examples=300, deadline=None)
@given(
    base=st.integers(0, 5_000_000_000),
    halves=st.integers(-400_000_000, 400_000_000),
    severity=SEVERITIES,
)
def test_cash_clamps_equal_exact_arithmetic(
    loaded: LoadedData, base: int, halves: int, severity: str
) -> None:
    """A drafted cash value (cents, possibly a half cent) clamped to its cap, then rounded."""
    events = loaded.balance.events
    value = halves / 2
    gain = value > 0
    cap = Fraction(base) * _exact(events.cap("cash_delta", severity)) / BP_DENOMINATOR
    if gain:
        cap *= _exact(events.cash_gain_share)
    expected = round(max(-cap, min(cap, Fraction(halves, 2))))
    assert clamp_effect("cash_delta", value, severity, events, base) == expected  # type: ignore[arg-type]


@given(cash=st.integers(-(10**9), 10**10), revenue=st.integers(0, 10**9))
def test_the_cash_base_is_exact(loaded: LoadedData, cash: int, revenue: int) -> None:
    events = loaded.balance.events
    months = _exact(events.cash_revenue_months)
    assert cash_base_cents(cash, revenue, events) == max(cash, round(months * revenue), 0)
