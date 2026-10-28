"""M4c playtest fixes: the numbers the brief's acceptance criteria name."""

from __future__ import annotations

from tst.loader import LoadedData
from tst.sim.hiring.formulas import energy_cost


def test_a_typical_hiring_month_costs_45_of_60(loaded: LoadedData) -> None:
    """formulas.md 6 (M4c): one job post, four interviews and two reference checks."""
    b = loaded.balance
    month = (
        energy_cost("job_post", b)
        + 4 * energy_cost("interview", b)
        + 2 * energy_cost("reference_check", b)
    )
    assert (month, b.founder.energy_per_month) == (45, 60)
    assert b.delegates.energy_per_month == 100  # delegates keep their whole month
