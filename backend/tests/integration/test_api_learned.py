"""M4c: interviews, reference checks and scouting say what they taught.

Every response goes through the hidden-field check (ADR-0007) in `Client.call`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.integration.test_api_hiring import BASE, Client, hiring_client

KEY_PERSONALITY = ("loyalty", "professionalism", "ambition", "risk_appetite")


def _width(attr: dict[str, Any]) -> int:
    return int(attr["range"]["max"] - attr["range"]["min"])


def _first_candidate(api: Client) -> dict[str, Any]:
    api.post(
        f"{BASE}/recruitment/searches", {"role": "software_engineer", "channel": "job_post"}, 201
    )
    api.post(f"{BASE}/advance")
    candidates = api.get(f"{BASE}/recruitment/candidates")
    assert candidates
    return dict(candidates[0])


def test_interview_and_references_say_what_narrowed(tmp_path: Path) -> None:
    with hiring_client(tmp_path) as api:
        first = _first_candidate(api)
        pid = first["person_id"]
        # The candidate table carries personality ranges (M4c).
        assert {p["key"] for p in first["personality"]} >= set(KEY_PERSONALITY)

        out = api.post(f"{BASE}/recruitment/candidates/{pid}/interview")
        learned = out["learned"]
        assert learned["person_id"] == pid and learned["action"] == "interview"
        assert learned["ranges"], "an interview narrows something"
        for change in learned["ranges"]:
            before, after = change["before"], change["after"]
            assert after["min"] >= before["min"] and after["max"] <= before["max"]
            assert (after["min"], after["max"]) != (before["min"], before["max"])
        groups = {c["group"] for c in learned["ranges"]}
        assert "personality" in groups and groups - {"personality"}
        assert learned["interests"] is not None and learned["work_style"] is not None
        assert learned["potential_before"] and learned["potential_after"]
        # The "after" side is exactly what the profile now shows.
        now = {a["key"]: a["range"] for a in out["skills"] + out["personality"]}
        assert all(now[c["key"]] == c["after"] for c in learned["ranges"])

        refs = api.post(f"{BASE}/recruitment/candidates/{pid}/reference-check")["learned"]
        assert refs["action"] == "reference_check"
        assert {c["group"] for c in refs["ranges"]} <= {"personality"}  # references: personality
        assert refs["interests"] is None and refs["work_style"] is None  # already known
        row = next(c for c in api.get(f"{BASE}/recruitment/candidates") if c["person_id"] == pid)
        widths = {p["key"]: _width(p) for p in row["personality"]}
        before = {p["key"]: _width(p) for p in first["personality"]}
        assert sum(widths[k] for k in KEY_PERSONALITY) < sum(before[k] for k in KEY_PERSONALITY)


def test_scout_says_what_it_taught_each_candidate(tmp_path: Path) -> None:
    with hiring_client(tmp_path) as api:
        first = _first_candidate(api)
        search = first["candidacy"]["search_id"]
        count = len(api.get(f"{BASE}/recruitment/candidates"))
        out = api.post(f"{BASE}/recruitment/searches/{search}/scout")
        assert len(out["learned"]) == count
        assert all(entry["action"] == "scout" for entry in out["learned"])
        assert any(entry["ranges"] for entry in out["learned"])
