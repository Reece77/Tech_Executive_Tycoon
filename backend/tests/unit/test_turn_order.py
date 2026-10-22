"""The turn pipeline order is fixed by ADR-0006."""

from tst.sim.turn import PHASES


def test_phase_order_matches_adr_0006() -> None:
    assert [name for name, _ in PHASES] == [
        "apply_player_decisions",
        "rival_decisions",
        "research_progress",
        "production_and_capacity",
        "sales_revenue_churn",
        "payroll_and_operating_costs",
        "financing",
        "people_updates",
        "market_and_macro_update",
        "stage_checks",
        "snapshot_and_month_end_report",
        "event_director_requests",
    ]


def test_phase_names_match_functions() -> None:
    for name, phase in PHASES:
        assert phase.__name__ == name
