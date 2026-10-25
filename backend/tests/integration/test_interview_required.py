"""ADR-0016 through the API and the CLI: an offer needs an interview by the company."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.integration.test_api_hiring import BASE, hiring_client
from tst.cli import app

runner = CliRunner()


def test_api_refuses_an_offer_without_an_interview(tmp_path: Path) -> None:
    with hiring_client(tmp_path) as api:
        api.post(
            f"{BASE}/recruitment/searches",
            {"role": "software_engineer", "channel": "job_post"},
            201,
        )
        api.post(f"{BASE}/advance")
        candidate = api.get(f"{BASE}/recruitment/candidates")[0]
        pid = candidate["person_id"]
        assert candidate["candidacy"]["offer_blocked_reason"] == "interview_required"
        ask = candidate["candidacy"]["salary_expectation_cents"]
        body = {"salary_cents": ask, "equity_bp": 0}
        error = api.post(f"{BASE}/recruitment/candidates/{pid}/offer", body, 409)
        assert error["code"] == "interview_required"
        api.post(f"{BASE}/recruitment/candidates/{pid}/reference-check")
        api.post(f"{BASE}/recruitment/candidates/{pid}/offer", body, 409)
        profile = api.post(f"{BASE}/recruitment/candidates/{pid}/interview")
        assert profile["candidacy"]["offer_blocked_reason"] is None
        api.post(f"{BASE}/recruitment/candidates/{pid}/offer", body, 201)


@pytest.fixture
def save_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "saves"
    monkeypatch.setenv("TST_SAVE_DIR", str(path))
    return path


def test_cli_refuses_an_offer_without_an_interview(save_dir: Path) -> None:
    def run(*args: str, code: int = 0) -> str:
        result = runner.invoke(app, list(args))
        assert result.exit_code == code, result.output
        return result.output

    run("new-game", "--seed", "11", "--name", "cli", "--company-name", "Co")
    run("search", "open", "--save", "cli", "--role", "designer", "--channel", "job_post")
    run("advance", "--save", "cli")
    listing = run("candidates", "--save", "cli")
    pid = re.findall(r"^\s+(\d+)\s{2}", listing, flags=re.MULTILINE)[0]
    assert "interview first" in listing
    out = run("offer", "--save", "cli", "--candidate", pid, "--salary", "90000", code=1)
    assert "interview" in out and "before making an offer" in out
    run("interview", "--save", "cli", "--candidate", pid)
    assert "sent" in run("offer", "--save", "cli", "--candidate", pid, "--salary", "90000")
