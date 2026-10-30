"""History (docs/formulas.md 17.2; M7b sub-task 3): the timeline with search, filters and month
lines; charts; storylines; the hall of fame; and no hidden value in any History response."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, update

from tests.helpers import play_turn
from tests.integration.test_api import find_forbidden_keys
from tst.api.app import create_app
from tst.api.history_views import short_money
from tst.config import Settings, get_settings
from tst.db import repository
from tst.db.models import (
    CompanyRow,
    PersonHiddenRow,
    PersonRatingLogRow,
    PersonSkillRow,
    PersonTagRow,
)
from tst.loader import LoadedData
from tst.sim.actions import (
    AssignUnit,
    CreateProduct,
    Interview,
    LaunchProduct,
    MakeOffer,
    OpenSearch,
    SetPrice,
)
from tst.sim.actions.products import launch_problems
from tst.sim.people.reveal import revealed_range

SAVE = "hist"
BASE = f"/api/saves/{SAVE}/history"
FOUNDER = 1
PRICES = {"smb": 4000, "mid_market": 70_000}
MONTHS = 14


def _state(path: Path) -> Any:
    with repository.open_session(path) as session:
        return repository.load_state(session)


def _build(loaded: LoadedData, save_dir: Path) -> Path:
    """A funded spinout hires three engineers, builds a product and plays 14 months."""
    path = repository.create_save(
        SAVE, 16, "funded_spinout", company_name="Kestrel", data=loaded, save_dir=save_dir
    )
    repository.run_action(path, loaded, OpenSearch(FOUNDER, "software_engineer", "job_post"))
    play_turn(path, loaded)
    state = _state(path)
    for c in [c for c in state.candidates if c.company_id == 1][:3]:
        ask = state.person(c.person_id).salary_expectation_cents or 0
        repository.run_action(path, loaded, Interview(FOUNDER, c.person_id))
        repository.run_action(path, loaded, MakeOffer(FOUNDER, c.person_id, 2 * ask, 0))
    product_id = state.next_ids.product
    repository.run_action(
        path, loaded, CreateProduct(FOUNDER, "Kestrel CRM", "b2b_saas", tuple(PRICES))
    )
    for segment, price in PRICES.items():
        repository.run_action(path, loaded, SetPrice(FOUNDER, product_id, segment, price))
    repository.run_action(path, loaded, AssignUnit(FOUNDER, product_id, None))
    for _ in range(MONTHS):
        play_turn(path, loaded)
        state = _state(path)
        product = state.product(product_id)
        if (
            product is not None
            and product.status == "in_development"
            and not launch_problems(state, product, loaded.balance, loaded.game_data)
        ):
            repository.run_action(path, loaded, LaunchProduct(FOUNDER, product_id))
    return path


@pytest.fixture(scope="module")
def built(loaded: LoadedData, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _build(loaded, tmp_path_factory.mktemp("history"))


@pytest.fixture
def api(built: Path) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=built.parent)
    with TestClient(app) as client:
        yield client


def _get(api: TestClient, url: str, **params: Any) -> Any:
    res = api.get(url, params=params)
    assert res.status_code == 200, (url, res.text)
    body = res.json()
    assert find_forbidden_keys(body) == [], url
    return body


def test_timeline_has_entries_and_month_lines_newest_first(api: TestClient) -> None:
    body = _get(api, f"{BASE}/timeline", limit=500)
    rows = body["rows"]
    turns = [r["turn"] for r in rows]
    assert turns == sorted(turns, reverse=True)
    months = [r for r in rows if r["kind"] == "month"]
    assert len(months) == MONTHS + 1  # one per played month
    assert months[0]["title"].startswith("Mar 2011 · ARR $")
    assert " staff" in months[0]["title"] and "cash $" in months[0]["title"]
    # Within a month its summary line comes first, then that month's entries.
    first_month = next(i for i, r in enumerate(rows) if r["kind"] == "month")
    later = [r for r in rows[first_month + 1 :] if r["kind"] == "month"]
    assert all(r["turn"] < rows[first_month]["turn"] for r in later)
    entries = [r for r in rows if r["kind"] == "entry"]
    kinds = {r["key"].split("-")[0] for r in entries}
    assert kinds == {"event", "decision", "inbox"}
    hires = [r for r in entries if r["title"].endswith("accepted your offer")]
    assert hires and all(r["person_id"] and r["category"] == "people" for r in hires)
    offers = [r for r in entries if r["title"].startswith("Offered ")]
    assert offers and all(r["actor"] == "You" and r["source"] == "player" for r in offers)
    events = [r for r in entries if r["category"] == "events"]
    assert events and all(r["actor"] in ("You", "Default (at Continue)") for r in events)
    assert body["years"] == [2011, 2010]
    assert body["total"] == len(rows)


def test_search_and_filters(api: TestClient) -> None:
    hire = next(
        r
        for r in _get(api, f"{BASE}/timeline", limit=500)["rows"]
        if r["title"].endswith("accepted your offer")
    )
    name = hire["person_name"]
    found = _get(api, f"{BASE}/timeline", search=name.split()[0].upper())["rows"]
    assert any(r["key"] == hire["key"] for r in found)
    entries = [r for r in found if r["kind"] == "entry"]
    assert all(name.split()[0].lower() in json.dumps(r).lower() for r in entries)
    person = _get(api, f"{BASE}/timeline", person_id=hire["person_id"], limit=500)["rows"]
    assert {r["person_id"] for r in person if r["kind"] == "entry"} == {hire["person_id"]}
    assert any(r["title"].startswith("Interviewed") for r in person)
    products = _get(api, f"{BASE}/timeline", category="products", limit=500)["rows"]
    assert {r["category"] for r in products if r["kind"] == "entry"} == {"products"}
    assert any(r["title"] == "Started building Kestrel CRM" for r in products)
    default = _get(api, f"{BASE}/timeline", source="default", limit=500)["rows"]
    assert {r["actor"] for r in default if r["kind"] == "entry"} == {"Default (at Continue)"}
    year = _get(api, f"{BASE}/timeline", year=2010, limit=500)["rows"]
    assert year and all(r["date_label"].endswith("2010") for r in year)
    page = _get(api, f"{BASE}/timeline", limit=5, offset=5)
    assert len(page["rows"]) == 5 and page["offset"] == 5
    assert api.get(f"{BASE}/timeline", params={"category": "nonsense"}).status_code == 422


def test_charts_cover_every_month_and_the_product(api: TestClient) -> None:
    body = _get(api, f"{BASE}/charts")
    assert [p["turn"] for p in body["kpis"]] == list(range(MONTHS + 1))
    assert body["kpis"][0]["cash_cents"] > 0
    (crm,) = body["products"]
    assert crm["name"] == "Kestrel CRM" and crm["points"]


def test_storylines_and_hall_of_fame(api: TestClient) -> None:
    for story in _get(api, f"{BASE}/storylines"):
        assert story["steps"], story
        assert all(s["title"] for s in story["steps"])
    fame = _get(api, f"{BASE}/hall-of-fame")
    staff = max(p["headcount"] for p in _get(api, f"{BASE}/charts")["kpis"])
    assert fame["peak_headcount"]["value"] == staff
    assert [f["label"] for f in fame["firsts"]] == [
        "First launch",
        "First paying customer",
        "First enterprise customer",
        "First $1M ARR",
        "First round closed",
    ]
    serving = fame["longest_serving"]
    assert serving and all(s["months"] > 0 for s in serving)
    assert [s["months"] for s in serving] == sorted((s["months"] for s in serving), reverse=True)
    hires = fame["best_hires"]
    assert hires and all("→" in (h["detail"] or "") for h in hires)
    assert [h["value"] for h in hires] == sorted((h["value"] for h in hires), reverse=True)


def test_the_rating_log_holds_shown_values(built: Path, loaded: LoadedData) -> None:
    """The last month's ratings are the mean midpoints of the displayed primary-skill ranges."""
    state = _state(built)
    played = state.turn - 1
    with repository.open_session(built) as session:
        logged = {
            r.person_id: r.rating
            for r in session.query(PersonRatingLogRow).filter(PersonRatingLogRow.turn == played)
        }
    expected = {}
    for e in state.staff(1):
        person = state.person(e.person_id)
        if person.is_founder:
            continue
        primary = loaded.game_data.role(e.role).primary
        mids = [sum(revealed_range(person, state.reveal(1, person.id), k)) / 2 for k in primary]
        expected[person.id] = sum(mids) / len(mids)
    assert logged == expected and all(1 <= r <= 20 for r in logged.values())


def test_no_history_response_contains_a_hidden_value(loaded: LoadedData, tmp_path: Path) -> None:
    """Plant unmistakable hidden values (potential, hidden traits, true skills, an unnoticed
    tag, a rival's builder skill and margin) and read every History route: none appear."""
    path = _build(loaded, tmp_path)
    with repository.open_session(path) as session, session.begin():
        session.execute(update(PersonHiddenRow).values(value=19.8765))
        session.execute(
            update(PersonHiddenRow)
            .where(PersonHiddenRow.trait == "potential_ability")
            .values(value=187.6543)
        )
        session.execute(update(PersonSkillRow).values(value=17.3456))
        staff = [e.person_id for e in _state(path).staff(1) if e.person_id != FOUNDER]
        session.execute(delete(PersonTagRow).where(PersonTagRow.person_id.in_(staff)))
        session.add_all(
            PersonTagRow(person_id=p, tag="toxic_high_performer", position=0) for p in staff
        )
        session.execute(
            update(CompanyRow)
            .where(CompanyRow.is_player.is_(False))
            .values(builder_skill=0.98765, target_margin_bp=8642)
        )
    play_turn(path, loaded)  # a month under the planted values: ratings and texts written
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=tmp_path)
    blobs = []
    with TestClient(app) as client:
        for route in ("timeline?limit=500", "charts", "storylines", "hall-of-fame"):
            res = client.get(f"{BASE}/{route}")
            assert res.status_code == 200, res.text
            assert find_forbidden_keys(res.json()) == []
            blobs.append(res.text)
    blob = "\n".join(blobs)
    for planted in ("187.6", "19.87", "17.34", "0.987", "8642", "toxic", "Toxic", "potential"):
        assert planted not in blob, planted


def test_short_money() -> None:
    assert short_money(123_456_789) == "$1.2M"
    assert short_money(64_000_000) == "$640k"
    assert short_money(90_000) == "$900"
    assert short_money(-250_000_00) == "-$250k"
