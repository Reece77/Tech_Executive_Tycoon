"""M25 sub-tasks 1-2: every metric explains on a played save (breakdown, trend, drivers and a
template explanation); Ask why answers through the mock adapter within the budget, falls
back to the template offline, and never changes the game."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.helpers import FIRST_PRODUCT, play_turn
from tests.integration.test_api_hiring import Client
from tests.integration.test_api_products import staff
from tst.advisor import ask as advisor
from tst.advisor.metrics import METRICS
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db import repository
from tst.db.models import LLMCallLogRow
from tst.db.state_io import sync_state
from tst.llm.offline import MockLLMAdapter
from tst.llm.settings import LLMSettings, month_spend, save_settings
from tst.loader import LoadedData
from tst.sim.state import with_person

SAVE = "m25"
BASE = f"/api/saves/{SAVE}"
PRODUCT = FIRST_PRODUCT


@pytest.fixture(scope="module")
def played(tmp_path_factory: pytest.TempPathFactory, loaded: LoadedData) -> Path:
    """A funded spin-out with a live product, played until it has a few months of customers."""
    save_dir = tmp_path_factory.mktemp("m25") / "saves"
    path = repository.create_save(
        SAVE, 8, "funded_spinout", company_name="Explain Co", data=loaded, save_dir=save_dir
    )
    staff(path, loaded, ("software_engineer",) * 3 + ("account_executive", "marketer"))
    with _client(save_dir) as api:
        body = {"name": "Pipeline", "category": "b2b_saas", "segments": ["smb", "mid_market"]}
        api.post(f"{BASE}/products", body, status=201)
        api.post(f"{BASE}/products/{PRODUCT}/price", {"segment": "smb", "price_cents": 4000})
        api.post(
            f"{BASE}/products/{PRODUCT}/price", {"segment": "mid_market", "price_cents": 70_000}
        )
        api.post(f"{BASE}/products/{PRODUCT}/assign", {"unit_id": None})
        api.post(f"{BASE}/products/{PRODUCT}/marketing", {"budget_cents": 1_000_000})
        for _ in range(12):
            if api.get(f"{BASE}/products/{PRODUCT}")["launch"]["ready"]:
                break
            play_turn(path, loaded)
        api.post(f"{BASE}/products/{PRODUCT}/launch")
        for _ in range(4):
            play_turn(path, loaded)
    return path


def _client(save_dir: Path) -> Any:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)

    class _Ctx:
        def __enter__(self) -> Client:
            self.tc = TestClient(app)
            self.tc.__enter__()
            return Client(self.tc)

        def __exit__(self, *exc: object) -> None:
            self.tc.__exit__(*exc)

    return _Ctx()


@pytest.fixture
def api(played: Path) -> Iterator[Client]:
    with _client(played.parent) as client:
        yield client


def _entity(metric: str, api: Client) -> str | None:
    scope = METRICS[metric].scope
    if scope == "product":
        return str(PRODUCT)
    if scope == "person":
        people = api.get(f"{BASE}/people")
        return str(next(p["person_id"] for p in people if not p["is_founder"]))
    if scope == "account":
        return "6000_salaries"
    if scope == "market":
        return "b2b_saas"
    return None


def test_every_metric_explains(api: Client) -> None:
    for metric in METRICS:
        entity = _entity(metric, api)
        url = f"{BASE}/explain/{metric}" + (f"?entity={entity}" if entity else "")
        out = api.get(url)
        assert out["metric"] == metric and out["explanation"], metric
        assert out["items"] or out["note"], metric
        assert len(out["trend"]) <= 12, metric
        if metric in ("cash", "mrr", "customers", "churn", "cost_line", "market_customers"):
            assert len(out["trend"]) >= 2, metric


def test_churn_names_two_drivers_with_sizes(api: Client) -> None:
    out = api.get(f"{BASE}/explain/churn?entity={PRODUCT}")
    assert out["unit"] == "percent" and out["items"]
    if out["drivers"]:
        effects = [d["effect"] for d in out["drivers"] if d["effect"] is not None]
        before, after = out["trend"][-2]["value"], out["trend"][-1]["value"]
        assert sum(effects) == pytest.approx(after - before, abs=1e-6)  # the split is whole
        assert out["explanation"].startswith("Churn ")


def test_cash_drivers_sum_to_the_change(api: Client) -> None:
    out = api.get(f"{BASE}/explain/cash")
    before, after = out["trend"][-2]["value"], out["trend"][-1]["value"]
    assert sum(d["effect"] for d in out["drivers"]) == pytest.approx(after - before)
    top = sorted(out["drivers"], key=lambda d: -abs(d["effect"]))[:2]
    assert all(d["label"] in out["explanation"] for d in top)


def test_unknown_metric_and_bad_entity(api: Client) -> None:
    assert api.get(f"{BASE}/explain/nope", status=404)["code"] == "unknown_metric"
    assert api.get(f"{BASE}/explain/churn", status=400)["code"] == "invalid_entity"
    assert api.get(f"{BASE}/explain/morale?entity=1", status=400)["code"] == "invalid_entity"


def test_ask_why_with_the_mock_then_offline(api: Client, played: Path) -> None:
    before = api.get(f"{BASE}/overview")
    spent = month_spend(played.parent).calls
    out = api.post(
        f"{BASE}/explain/churn/ask", {"question": "Why did churn move?", "entity": str(PRODUCT)}
    )
    assert out["source"] == "mock" and out["answer"].startswith("[mock]")
    assert api.get(f"{BASE}/overview") == before  # read-only: no state, no energy
    assert month_spend(played.parent).calls == spent + 1
    with repository.open_session(played) as session:
        logs = list(
            session.scalars(select(LLMCallLogRow).where(LLMCallLogRow.purpose == "explain"))
        )
    assert logs and logs[-1].outcome == "ok"
    save_settings(played.parent, LLMSettings(monthly_budget_cents=0))
    try:
        offline = api.post(f"{BASE}/explain/cash/ask", {"question": "Why?"})
        template = api.get(f"{BASE}/explain/cash")["explanation"]
        assert offline["source"] == "template" and offline["answer"] == template
    finally:
        save_settings(played.parent, LLMSettings())
    api.post(f"{BASE}/explain/cash/ask", {"question": "x" * 301}, status=400)


# --- No hidden value reaches an Explain prompt (ADR-0005 section 4, formulas.md 16.5) ------

PLANTED = ("187.6", "19.87", "3.1415", "18.27", "toxic", "Toxic", "potential")


def _copy(src: Path, dst_dir: Path) -> Path:
    """A consistent copy of a save (SQLite's backup API, so the WAL comes along)."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    with sqlite3.connect(src) as a, sqlite3.connect(dst) as b:
        a.backup(b)
    return dst


def _plant(path: Path, potential: float, hidden: float, tag: str | None) -> int:
    """Give the first non-founder employee planted hidden values; returns their id."""
    with repository.open_session(path) as session, session.begin():
        before = repository.load_state(session)
        e = next(
            e for e in before.staff(before.player.id) if not before.person(e.person_id).is_founder
        )
        p = before.person(e.person_id)
        planted = replace(
            p,
            potential_ability=potential,
            hidden=p.hidden.updated(dict.fromkeys(p.hidden.keys(), hidden)),
            personality=p.personality.updated({"loyalty": hidden / 6.3, "ambition": hidden - 1.6}),
            tags=(tag,) if tag else (),
        )
        sync_state(session, before, with_person(before, planted))
    repository.forget(path)
    return e.person_id


def _prompts(path: Path, loaded: LoadedData, person: int) -> list[str]:
    ents = {"product": str(PRODUCT), "person": str(person), "account": "6000_salaries"}
    ents["market"] = "b2b_saas"
    adapter = MockLLMAdapter()
    for metric, m in METRICS.items():
        advisor.ask(path, loaded, metric, ents.get(m.scope), "Why is it this?", adapter=adapter)
    return [c.system + "\n" + c.user for c in adapter.calls]


def test_no_explain_prompt_contains_a_hidden_value(
    played: Path, loaded: LoadedData, tmp_path: Path
) -> None:
    path = _copy(played, tmp_path / "saves")
    person = _plant(path, 187.6543, 19.8765, "toxic_high_performer")
    texts = _prompts(path, loaded, person)
    assert len(texts) == len(METRICS)
    blob = "\n".join(texts)
    for planted in PLANTED:
        assert planted not in blob, planted
    with repository.read_session(path) as session:
        named = repository.read_state(session).person(person).first_name
    assert named in blob  # the person's own numbers do reach their prompts, by name


def test_same_shown_values_give_identical_prompts(
    played: Path, loaded: LoadedData, tmp_path: Path
) -> None:
    """The differential test: two saves the player sees identically (same revealed values)
    but with different hidden ones (potential, hidden traits, unnoticed tags) build
    byte-identical prompts for every metric."""
    low = _copy(played, tmp_path / "low")
    high = _copy(played, tmp_path / "high")
    person = _plant(low, 40.0, 3.0, None)
    assert _plant(high, 195.0, 19.0, "toxic_high_performer") == person
    assert _prompts(low, loaded, person) == _prompts(high, loaded, person)
