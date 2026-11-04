"""M10c data and formulas (docs/formulas.md 24): decision quality from the true seat score,
the exec_authority keys and every seat's default guardrails, and the executive event
templates with modifiers."""

from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.data_models import AUTHORITY_SEATS
from tst.sim.org.formulas import decision_quality


@pytest.mark.parametrize(
    ("score", "p"),
    [(8.0, 0.79), (15.0, 0.98), (1.0, 0.6), (12.0, 0.91), (14.0, 0.97)],
)
def test_decision_quality(loaded: LoadedData, score: float, p: float) -> None:
    """clamp(0.55 + 0.03 s, 0.6, 0.98) (24.2)."""
    assert decision_quality(score, loaded.balance.exec_authority.quality) == pytest.approx(p)


def test_exec_authority_keys(loaded: LoadedData) -> None:
    ea = loaded.balance.exec_authority
    assert (ea.change_energy, ea.energy_per_month, ea.report_months) == (2, 100, 3)
    assert ea.mistake_budget_off == 0.20
    assert sorted(ea.defaults) == sorted(AUTHORITY_SEATS)
    assert sorted(AUTHORITY_SEATS) == ["cfo", "cmo", "coo", "cpo", "cro", "cto"]  # CPO: M13b
    assert ea.defaults["cro"]["price_band_pct"] == 10
    assert ea.defaults["cfo"] == {"runway_months": 9, "repay_above_months": 24}
    assert ea.defaults["coo"]["coverage_target"] == 1.0


def test_executive_event_templates(loaded: LoadedData) -> None:
    templates = [t for t in loaded.game_data.event_templates if t.category == "executive"]
    assert {t.trigger for t in templates} == {
        "exec_cto",
        "exec_cro",
        "exec_cmo",
        "exec_cfo",
        "exec_clash",
    }
    for t in templates:
        assert "minor" in t.severities
        if t.trigger != "exec_cfo":
            assert t.modifier_stats(), t.id  # their choices carry modifiers (24.3)
    for key in ("exec_report", "exec_decisions", "exec_proposal"):
        assert key in loaded.game_data.inbox_templates
