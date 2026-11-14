"""M30 sub-task 4: old history rows are summarised, not lost (tst.db.history). Snapshots past
retention.snapshot_months keep quarter ends, the first year and record highs, so the Hall of Fame
shows exactly what it showed; log items past retention.log_months become yearly counts; major
World news items leaving the state's window go to the archive and World news shows them."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from tst.api.app import create_app
from tst.api.deps import get_settings
from tst.api.history_views import hall_of_fame
from tst.config import Settings
from tst.db import history, migrate
from tst.db.models import (
    SaveMetaRow,
    TurnLogRow,
    TurnLogSummaryRow,
    TurnSnapshotRow,
    WorldNewsArchiveRow,
)
from tst.db.repository import create_save, open_session
from tst.loader import LoadedData
from tst.sim.world.models import WorldNews

COMPANY = 1
MONTHS = 130  # played through November 2020


def _save(tmp_path: Path, loaded: LoadedData) -> Path:
    path = create_save(
        "hist", 5, "funded_spinout", company_name="Hist Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session, session.begin():
        session.execute(delete(TurnSnapshotRow))
        for t in range(MONTHS):
            arr = [100, 300, 200, 300, 900, 50][t % 6] * (1 + t // 60)  # records, ties, falls
            kpis = {"arr_cents": arr, "headcount": 5 + t % 7, "cash_cents": t}
            session.add(TurnSnapshotRow(turn=t, company_id=COMPANY, kpis=kpis))
            for k in range(t % 3 + 1):
                session.add(TurnLogRow(turn=t, company_id=COMPANY, kind="month_end", message="x"))
            session.add(TurnLogRow(turn=t, company_id=None, kind="world", message=f"m{k}"))
        meta = session.scalars(select(SaveMetaRow)).one()
        meta.current_turn = MONTHS
    return path


def _turns(path: Path) -> list[int]:
    with open_session(path) as session:
        return list(session.scalars(select(TurnSnapshotRow.turn).order_by(TurnSnapshotRow.turn)))


def test_snapshots_thin_and_the_hall_of_fame_holds(tmp_path: Path, loaded: LoadedData) -> None:
    path = _save(tmp_path, loaded)
    with open_session(path) as session:
        before = hall_of_fame(session, COMPANY, MONTHS, loaded)
    with open_session(path) as session, session.begin():
        history.prune(session, MONTHS - 1, loaded.balance.retention)
    kept = _turns(path)
    window = MONTHS - 1 - loaded.balance.retention.snapshot_months
    assert [t for t in range(window + 1, MONTHS)] == [t for t in kept if t > window]  # all recent
    old = [t for t in kept if t <= window]
    assert set(range(2, window + 1, 3)) <= set(old)  # every quarter's last month
    assert len(old) < window + 1  # something went
    with open_session(path) as session:
        assert hall_of_fame(session, COMPANY, MONTHS, loaded) == before
        assert session.scalars(select(SaveMetaRow)).one().history_pruned_through == window
    # the next month thins one more month, and only that one
    with open_session(path) as session, session.begin():
        history.prune(session, MONTHS, loaded.balance.retention)
    assert [t for t in _turns(path) if t <= window] == old


def test_log_items_become_yearly_counts(tmp_path: Path, loaded: LoadedData) -> None:
    path = _save(tmp_path, loaded)
    per_year: Counter[tuple[int, int | None, str]] = Counter()
    with open_session(path) as session:
        for turn, company, kind in session.execute(
            select(TurnLogRow.turn, TurnLogRow.company_id, TurnLogRow.kind)
        ):
            per_year[(turn // 12, company, kind)] += 1
    with open_session(path) as session, session.begin():
        history.prune(session, MONTHS - 1, loaded.balance.retention)
    window = MONTHS - 1 - loaded.balance.retention.log_months
    full_years = (window + 1) // 12
    with open_session(path) as session:
        summary = {
            (r.year, r.company_id, r.kind): r.items
            for r in session.scalars(select(TurnLogSummaryRow))
        }
        left = session.scalar(select(func.min(TurnLogRow.turn)))
    assert summary == {k: n for k, n in per_year.items() if k[0] < full_years}
    assert left == full_years * 12  # whole years only


def test_major_news_leaving_the_window_is_archived_and_shown(
    tmp_path: Path, loaded: LoadedData
) -> None:
    path = _save(tmp_path, loaded)
    major = loaded.balance.retention.major_news[0]
    items = (
        WorldNews(id=1, turn=0, kind=major, message="a deal"),
        WorldNews(id=2, turn=0, kind="review", message="a review"),
        WorldNews(id=3, turn=1, kind=major, message="a later deal"),
    )
    with open_session(path) as session, session.begin():
        history.archive_news(session, items, items[2:], loaded.balance.retention)
        history.archive_news(session, items, items[2:], loaded.balance.retention)  # once only
    with open_session(path) as session:
        archived = list(session.scalars(select(WorldNewsArchiveRow.id)))
        assert archived == [1]
        assert history.archived_news(session) == [items[0]]

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=tmp_path)
    with TestClient(app) as client:
        body = client.get("/api/saves/hist/world-news").json()
        assert body["total"] == 1 and [x["news_id"] for x in body["items"]] == [1]
        assert client.get("/api/saves/hist/world-news?kind=review").json()["total"] == 0


def test_a_save_from_before_0051_is_thinned_once_on_upgrade(
    tmp_path: Path, loaded: LoadedData
) -> None:
    path = _save(tmp_path, loaded)
    migrate.downgrade(path, "0050_m28")
    migrate.ensure_current(path)
    assert migrate.current_revision(path) == migrate.head_revision()
    with open_session(path) as session:
        meta = session.scalars(select(SaveMetaRow)).one()
        assert meta.history_pruned_through == MONTHS - 1 - loaded.balance.retention.snapshot_months
        assert session.scalar(select(func.count()).select_from(TurnLogSummaryRow)) > 0
    assert len(_turns(path)) < MONTHS


def test_world_news_pages(tmp_path: Path, loaded: LoadedData) -> None:
    from tst.api import world_views
    from tst.db.repository import load_state

    path = _save(tmp_path, loaded)
    with open_session(path) as session:
        state = load_state(session)
    news = tuple(WorldNews(id=i, turn=i, kind="deal", message=f"n{i}") for i in range(1, 8))
    state = replace(state, world_news=news)
    page = world_views.world_news(state, loaded, offset=2, limit=3)
    assert page.total == 7
    assert [x.news_id for x in page.items] == [5, 4, 3]
