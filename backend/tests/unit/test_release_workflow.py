"""M57r-B (review 10 items 1, 23 and 24): the release workflow publishes only from a commit on
main with green check and e2e, and its smoke test runs the in-game update end to end and the
uninstall sentinel; the installer never deletes its whole folder."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
INSTALLER = ROOT / "packaging" / "installer.iss"
SMOKE = ROOT / "packaging" / "smoke.ps1"


def _jobs() -> dict[str, Any]:
    jobs: dict[str, Any] = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    return jobs


def test_publishing_needs_the_gate_and_the_gate_checks_main_and_both_summaries() -> None:
    jobs = _jobs()
    publish, gate = jobs["publish"], jobs["gate"]
    assert "gate" in publish["needs"] and "build" in publish["needs"]
    assert "needs.gate.result == 'success'" in publish["if"]
    script = "\n".join(step.get("run", "") for step in gate["steps"])
    assert "merge-base --is-ancestor" in script and "origin/main" in script
    assert "for name in check e2e" in script and '!= "success"' in script
    assert jobs["build"]["needs"] == "gate"


def test_the_smoke_test_runs_the_in_game_update_and_the_sentinel() -> None:
    steps = _jobs()["build"]["steps"]
    smoke = next(s for s in steps if s.get("name") == "Smoke test on this clean machine")
    assert "-NextInstaller" in smoke["run"] and "-NextVersion" in smoke["run"]
    text = SMOKE.read_text(encoding="utf-8")
    assert "TST_UPDATE_SOURCE" in text and "/api/desktop/update" in text
    assert "X-TST-Instance" in text and "$NextVersion" in text
    assert "the uninstaller deleted a file it did not install" in text
    assert "overlaps the saves" in text


def test_the_uninstaller_never_deletes_the_install_folder_wholesale() -> None:
    text = INSTALLER.read_text(encoding="utf-8")
    section = text.split("[UninstallDelete]", 1)[1].split("\n[", 1)[0]
    entries = [ln for ln in section.splitlines() if ln.strip() and not ln.startswith(";")]
    assert entries == ['Type: filesandordirs; Name: "{app}\\_internal"']
    assert "function PrepareToInstall" in text and "OverlapsGameData" in text
