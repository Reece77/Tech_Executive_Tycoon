"""M11 state and persistence: leads, projects, era arrivals and licences round-trip
(migration 0028_research)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.research.models import EraArrival, License, ResearchLead, ResearchProject


def test_research_state_round_trips(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "rnd", 3, "ex_big_tech_founders", company_name="Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session, session.begin():
        before = load_state(session)
        assert before.research_leads == () and before.era_arrivals == ()
        project_id, ids = before.next_ids.take("research_project")
        rival_project, ids = ids.take("research_project")
        licence_id, ids = ids.take("license")
        state = replace(
            before,
            next_ids=ids,
            research_leads=(ResearchLead(1, "ai", 12.5), ResearchLead(2, "software_platform", 3.0)),
            research_projects=(
                ResearchProject(
                    project_id,
                    1,
                    "ai",
                    7,
                    0,
                    budget_cents=360_000,
                    recent=(1.5, 1.25),
                    gained=2.75,
                    last_event="breakthrough",
                    last_event_turn=0,
                ),
                ResearchProject(rival_project, 2, "software_platform", None, 0, end_turn=5),
            ),
            era_arrivals=(EraArrival("mobile_first", 0, 1, 12),),
            licenses=(License(licence_id, 2, 1, "software_platform", 4.0, 0, 600_000_00),),
        )
        sync_state(session, before, state)
    with open_session(path) as session:
        again = load_state(session)
    assert again.research_leads == state.research_leads
    assert again.research_projects == state.research_projects
    assert again.era_arrivals == state.era_arrivals
    assert again.licenses == state.licenses
    assert again.next_ids.research_project == 3 and again.next_ids.license == 2


def test_cli_research_project_and_license(
    tmp_path: Path, loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from tests.integration.test_api_research import IBM, _build, _plant
    from tst.cli import app as cli_app

    save_dir = tmp_path / "saves"
    path = _build(save_dir, loaded)
    monkeypatch.setenv("TST_SAVE_DIR", str(save_dir))
    runner = CliRunner()
    out = runner.invoke(cli_app, ["research", "--save", "lab"])
    assert out.exit_code == 0, out.output
    assert "Software platform" in out.output and "Units free for a project: AI lab" in out.output
    with open_session(path) as session:
        unit = load_state(session).active_units(1)[0].id
    out = runner.invoke(
        cli_app, ["project", "--save", "lab", "--unit", str(unit), "--domain", "ai"]
    )
    assert out.exit_code == 0, out.output
    assert "researches ai" in out.output
    _plant(path, ResearchLead(IBM, "devices", 40.0))
    out = runner.invoke(
        cli_app,
        ["license", "--save", "lab", "--from", str(IBM), "--domain", "devices", "--points", "5"],
    )
    assert out.exit_code == 0, out.output
    assert "your lead is now 5.0" in out.output
