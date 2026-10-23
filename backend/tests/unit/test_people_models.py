from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tst.loader import LoadedData
from tst.sim.people.models import (
    Employment,
    Personality,
    Skills,
    best_fit_role,
    role_ability,
)
from tst.sim.scale import ATTR_MAX, ATTR_MIN, clamp_attr

values = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False)


@given(values)
def test_clamp_attr_bounds(value: float) -> None:
    assert ATTR_MIN <= clamp_attr(value) <= ATTR_MAX


@given(st.lists(values, min_size=3, max_size=3), st.lists(values, min_size=3, max_size=3))
def test_attr_sets_always_in_range(first: list[float], second: list[float]) -> None:
    keys = ("a", "b", "c")
    skills = Skills.build(keys, dict(zip(keys, first, strict=True)))
    updated = skills.updated(dict(zip(keys, second, strict=True)))
    for attrs in (skills, updated):
        assert all(ATTR_MIN <= v <= ATTR_MAX for _, v in attrs.items)
        assert attrs.keys() == keys


def test_attr_set_is_immutable_and_ordered() -> None:
    p = Personality.build(["x", "y"], {"y": 3.0, "x": 25.0})
    assert p.items == (("x", 20.0), ("y", 3.0))
    q = p.updated({"y": 4.0})
    assert p["y"] == 3.0 and q["y"] == 4.0
    with pytest.raises(KeyError):
        p["z"]
    with pytest.raises(AttributeError):
        p.items = ()  # type: ignore[misc]


def test_best_fit_role(loaded: LoadedData) -> None:
    data = loaded.game_data
    keys = data.skill_keys
    base = {k: 5.0 for k in keys}
    sales = Skills.build(keys, {**base, "sales": 18.0, "negotiation": 16.0})
    role, ca = best_fit_role(sales, data)
    # Both sales roles have primaries sales and negotiation. The rep has 3 secondaries at 5
    # (CA 10 x (3 x 34 + 15) / 9 = 130); the account executive has 4 (10 x 122 / 10 = 122).
    assert role.key == "sales_representative"
    assert ca == pytest.approx(130)
    assert ca == pytest.approx(role_ability(sales, data.role("sales_representative")))

    uniform = Skills.build(keys, base)
    assert best_fit_role(uniform, data)[0].key == data.roles[0].key  # all tie at CA 50


def test_employment_staff_status() -> None:
    def emp(status: str) -> Employment:
        return Employment(
            id=1,
            person_id=1,
            company_id=1,
            role="founder",
            level="exec",
            salary_cents=0,
            equity_bp=0,
            start_turn=0,
            end_turn=None,
            status=status,  # type: ignore[arg-type]
        )

    assert emp("active").counts_as_staff
    assert emp("notice").counts_as_staff
    assert not emp("ended").counts_as_staff
