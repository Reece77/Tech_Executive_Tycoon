"""M23r (Codex review 6) through the HTTP API: each finding's regression test, written first and
seen failing on m23a-done."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_hiring import Client
from tests.unit.test_m23a_group import found
from tst.api.app import create_app
from tst.balance.game import Game
from tst.config import Settings, get_settings
from tst.db.mappers import entry_to_row
from tst.db.repository import ledger_balances, load_state, open_session
from tst.db.state_io import sync_state
from tst.loader import LoadedData
from tst.sim.fabs import market as fm
from tst.sim.fabs.actions import BuildFab
from tst.sim.ledger import CASH, PPE, LedgerEntry, LedgerLine
from tst.sim.research.models import ResearchLead
from tst.sim.state import (
    GameState,
    with_fab,
    with_facility,
    with_person_state,
    with_research_lead,
)

TOOLS = Path(__file__).resolve().parents[3] / "tools"
BASE = "/api/saves/{}"


def tool(name: str) -> Any:
    sys.path.insert(0, str(TOOLS))
    return __import__(name)


@pytest.fixture
def saves(tmp_path: Path) -> Path:
    return tmp_path / "saves"


def client(saves: Path) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    return TestClient(app)


@pytest.fixture
def api(saves: Path) -> Iterator[Client]:
    with client(saves) as c:
        yield Client(c)


def edit(path: Path, data: LoadedData, step: Callable[[Game], None]) -> GameState:
    """Run `step(game)` on the save in memory and write it back: the state, and every account
    the step moved, one balanced entry a company (the actions' entries, and the cash a fab made
    ready at once moved to PPE)."""
    with open_session(path) as session, session.begin():
        before = load_state(session)
        game = Game(data, before, dict(ledger_balances(session)))
        start = dict(game.balances)
        step(game)
        sync_state(session, before, replace(game.state, turn=before.turn))
        moved: dict[int, list[LedgerLine]] = {}
        for (cid, account), v in sorted(game.balances.items()):
            if v != start.get((cid, account), 0):
                moved.setdefault(cid, []).append(
                    LedgerLine(account, v - start.get((cid, account), 0))
                )
        for cid, lines in moved.items():
            entry = LedgerEntry(
                turn=before.turn, company_id=cid, memo="Test setup", lines=tuple(lines)
            )
            session.add(entry_to_row(entry))
        return game.state


def balances(path: Path) -> dict[tuple[int, str], int]:
    with open_session(path) as session:
        return dict(ledger_balances(session))


# --- Finding 2: a group fab is managed from the Fabs view ---------------------------------------


def _ready_for(game: Game, fid: int, owner: int) -> None:
    """A fab built and paid for now by `owner` (m21.make_ready for any company)."""
    f = game.state.facility(fid)
    fab = fm.fab_of(game.state, fid)
    assert f is not None and fab is not None
    turn = game.state.turn
    game.state = with_facility(
        game.state,
        replace(f, ordered_turn=turn - fab.build_months, capex_paid_cents=f.capex_cents),
    )
    game.state = with_fab(game.state, replace(fab, live_turn=turn, tools_turn=None))
    game.balances[(owner, CASH)] = game.balances.get((owner, CASH), 0) - f.capex_cents
    game.balances[(owner, PPE)] = game.balances.get((owner, PPE), 0) + f.capex_cents


def group_fabs(saves: Path, name: str, data: LoadedData) -> tuple[Path, dict[str, int]]:
    """M21's `mature` save (a staffed, live 28 nm fab and a spare team of fab engineers), with a
    subsidiary that the fab is transferred to and that built a second fab of its own. The
    subsidiary has its own process lead (a fab's process level is its owner's, 38.2)."""
    from tst.sim.mining.actions import TransferAsset

    path = tool("e2e_m21_save").mature(saves, name, data)
    ids: dict[str, int] = {}

    def step(game: Game) -> None:
        moved = next(f.facility_id for f in game.state.fabs)
        sub = found(game, "Wafer Works", cents=2_000_000_000_000)  # $20B
        domain = game.loaded.balance.refining.domain
        game.state = with_research_lead(game.state, ResearchLead(sub, domain, 30.0))
        ps = game.state.person_state(game.founder_id)
        game.state = with_person_state(game.state, replace(ps, energy=100))
        assert game.act(TransferAsset(game.founder_id, sub, facility_id=moved)), game.refused
        game.state = with_person_state(game.state, replace(ps, energy=100))
        built = game.state.next_ids.facility
        size = game.loaded.balance.facility.kinds["fab"].sizes[0]  # type: ignore[index]
        action = BuildFab(game.founder_id, "n28", "north_america", size, company_id=sub)
        assert game.act(action), game.refused
        _ready_for(game, built, sub)
        team = next(u for u in game.state.units if u.name == "Fab team")
        ids.update(sub=sub, moved=moved, built=built, team=team.id)

    edit(path, data, step)
    return path, ids


def test_a_subsidiarys_fabs_are_visible_and_managed(
    api: Client, saves: Path, loaded: LoadedData
) -> None:
    """Codex's reproduction: a fab transferred to a subsidiary, and one the subsidiary built, are
    on the Fabs view with their owner; the founder staffs, converts and sells them, and the costs
    and proceeds are the owner's."""
    path, ids = group_fabs(saves, "g", loaded)
    sub, moved, built = ids["sub"], ids["moved"], ids["built"]
    base = BASE.format("g")
    fabs = {f["id"]: f for f in api.get(f"{base}/fabs")["fabs"]}
    assert set(fabs) == {moved, built}
    assert {f["company_id"] for f in fabs.values()} == {sub}
    assert fabs[moved]["company"] == "Wafer Works"
    # staffing: off and back on (its crew moved with it), and the spare team onto the new fab
    api.post(f"{base}/fabs/{moved}/staff", json={"unit_id": None})
    crew = load_state_of(path).facility(moved)
    assert crew is not None and crew.unit_id is None
    api.post(f"{base}/fabs/{built}/staff", json={"unit_id": ids["team"]})
    state = load_state_of(path)
    f = state.facility(built)
    team = state.unit(ids["team"])
    assert f is not None and f.unit_id == ids["team"]
    assert team is not None and team.company_id == sub  # its owner pays the crew
    staff = [e for e in state.employments if e.unit_id == ids["team"] and e.status == "active"]
    assert staff and all(e.company_id == sub for e in staff)
    # conversion, once the new fab is in production (the next month): the owner pays
    api.post(f"{base}/advance")
    out = api.post(f"{base}/fabs/{built}/upgrade")
    converting = next(x for x in out["fabs"]["fabs"] if x["id"] == built)
    assert converting["status"] == "converting"
    before = balances(path)
    api.post(f"{base}/advance")
    after = balances(path)
    player = load_state_of(path).player.id
    assert after.get((sub, PPE), 0) > before.get((sub, PPE), 0)
    assert after.get((player, PPE), 0) == before.get((player, PPE), 0)
    # sale: the proceeds are the owner's
    before = balances(path)
    api.post(f"{base}/fabs/{moved}/sell")
    after = balances(path)
    assert after.get((sub, CASH), 0) > before.get((sub, CASH), 0)
    assert after.get((player, CASH), 0) == before.get((player, CASH), 0)
    # a cold reload (a new app and session) shows the same
    with client(saves) as fresh:
        again = Client(fresh).get(f"{base}/fabs")["fabs"]
    assert {(x["id"], x["company_id"], x["status"]) for x in again} == {(built, sub, "converting")}


def load_state_of(path: Path) -> GameState:
    with open_session(path) as session:
        return load_state(session)


# --- Finding 4: an open critical event makes the save read only, at the server -------------------


def _snapshot(path: Path) -> tuple[Any, ...]:
    """Everything a refused action must leave alone: the state, the ledger, the decision log."""
    from sqlalchemy import func, select

    from tst.db.models import DecisionLogRow, LedgerEntryRow

    with open_session(path) as session:
        state = load_state(session)
        entries = session.scalar(select(func.count()).select_from(LedgerEntryRow))
        decisions = session.scalar(select(func.count()).select_from(DecisionLogRow))
        return state, dict(ledger_balances(session)), entries, decisions


def test_a_critical_event_makes_every_action_read_only_through_the_api(
    api: Client, saves: Path, loaded: LoadedData
) -> None:
    """Codex's reproduction: with the critical mine_price_crash open, POST .../safety was 200 and
    changed the mine. Now every action is refused with 409 read_only and leaves the state (energy
    included), the ledger and the decision log as they were; answering the event, reading and
    the inbox's marks still work."""
    path = tool("e2e_m19_save").crash(saves, "crash", loaded)
    base = BASE.format("crash")
    crash = next(e for e in api.get(f"{base}/events")["open"] if e["severity"] == "critical")
    mine = api.get(f"{base}/mines")["mines"][0]
    before = _snapshot(path)
    refused = [
        (f"{base}/mines/{mine['id']}/safety", {"safety": "high"}),
        (f"{base}/mines/{mine['id']}/care", {"restart": False}),
        (f"{base}/mines/{mine['id']}/close", None),
        (f"{base}/mines/subsidiaries", {"name": "Late Co", "region": "africa", "cents": 100}),
    ]
    for url, body in refused:
        res = api.client.post(url, json=body)
        assert res.status_code == 409, (url, res.status_code, res.text)
        assert res.json()["code"] == "read_only", (url, res.text)
        assert res.json()["event_id"] == crash["event_id"]
    assert _snapshot(path) == before
    assert api.get(f"{base}/mines")["mines"][0]["safety"] == mine["safety"]
    # allowed: reading, the inbox's marks and answering the event
    item = api.get(f"{base}/inbox")["items"][0]
    api.post(f"{base}/inbox/{item['item_id']}/read")
    api.get("/api/settings/ui")  # settings are the app's, outside any save
    api.post(
        f"{base}/events/{crash['event_id']}/choose", json={"choice": crash["choices"][0]["key"]}
    )
    # once answered, actions work again
    api.post(f"{base}/mines/{mine['id']}/safety", json={"safety": "high"})
    assert api.get(f"{base}/mines")["mines"][0]["safety"] == "high"


SET_ASIDE = Path(__file__).resolve().parents[3] / "frontend" / "src" / "lib" / "setAside.ts"


def _routes() -> list[Any]:
    """Every API route, from the routers themselves (each carries its full path)."""
    import importlib
    import pkgutil

    from fastapi import APIRouter
    from fastapi.routing import APIRoute

    import tst.api.routers as package

    out = []
    for info in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        for value in vars(module).values():
            if isinstance(value, APIRouter):
                out += [r for r in value.routes if isinstance(r, APIRoute)]
    return out


def test_the_front_ends_read_only_allowlist_follows_the_servers() -> None:
    """Every request the front end lets through while a critical event is set aside is one the
    server allows too: none runs an action (repository.run_action) except answering the event."""
    import inspect
    import re

    block = SET_ASIDE.read_text(encoding="utf8").split("const ALLOWED")[1].split("];")[0]
    allowed = [re.compile(p) for p in re.findall(r"^\s*/(.+)/,\s*$", block, re.MULTILINE)]
    assert len(allowed) >= 5, block
    matched = 0
    for route in _routes():
        if not route.methods - {"GET", "HEAD"}:
            continue
        sample = re.sub(r"\{[^}]+\}", "1", route.path)
        if not any(p.search(sample) for p in allowed):
            continue
        matched += 1
        source = inspect.getsource(route.endpoint)
        acts = "run_action" in source or "_act(" in source or "_check(" in source
        assert acts == sample.endswith("/events/1/choose"), route.path
    assert matched >= 10
