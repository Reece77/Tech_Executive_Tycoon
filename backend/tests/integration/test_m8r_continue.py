"""M8r finding 2 (Codex review 1, P1): Continue never answers a retryable `save_busy` once
its month has committed, so one click never plays two months; a Holiday month that committed
is counted even if writing its events then fails. Faults are injected after the commit."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from tests.integration.test_api_hiring import BASE, hiring_client
from tst import holiday
from tst.db import repository
from tst.db.events import has_pending
from tst.loader import LoadedData
from tst.sim.errors import SaveBusyError

SEED = 42
MONTHS = 6


def _new(loaded: LoadedData, save_dir: Path, name: str) -> Path:
    return repository.create_save(
        name, SEED, "garage_bootstrap", company_name="Kestrel", data=loaded, save_dir=save_dir
    )


def _turn(path: Path) -> int:
    with repository.open_session(path) as session:
        return repository.load_state(session).turn


class FailAfterCommit:
    """Stands in for the event service after a turn's commit: it raises, as a competing write
    or an adapter failure would. The recovery call (`committed` absent) works normally."""

    def __init__(self, exc: Exception, monkeypatch: pytest.MonkeyPatch) -> None:
        self.exc, self.fired = exc, 0
        self.real = repository.write_pending
        monkeypatch.setattr(repository, "write_pending", self)

    def __call__(self, *args: Any, **kwargs: Any) -> int:
        if kwargs.get("committed") is not None:
            self.fired += 1
            raise self.exc
        return int(self.real(*args, **kwargs))


def test_one_click_plays_one_month_when_events_fail_after_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The front end retries a retryable busy; a month must not be played twice."""
    with hiring_client(tmp_path) as api:
        path = repository.existing_save_path(tmp_path / "saves", "m1b")
        fault = FailAfterCommit(SaveBusyError(repository.BUSY_MESSAGE), monkeypatch)
        for click in range(MONTHS):
            before = _turn(path)
            for _attempt in range(5):  # retryBusy: up to five tries while retryable
                status, body = api.client.post(f"{BASE}/advance"), None
                body = status.json()
                if status.status_code == 409 and body.get("retryable"):
                    continue
                break
            assert status.status_code == 200, body
            assert _turn(path) == before + 1, f"click {click} played {_turn(path) - before}"
        assert fault.fired, "no month had events to write; pick another seed"


def test_the_months_events_stay_pending_and_are_written_next(
    loaded: LoadedData, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _new(loaded, tmp_path, "pending")
    fault = FailAfterCommit(RuntimeError("the adapter fell over"), monkeypatch)
    while not fault.fired:
        repository.run_turn(path, loaded)  # returns: the month committed
    with repository.open_session(path) as session:
        assert has_pending(session)
    monkeypatch.setattr(repository, "write_pending", fault.real)
    turn = _turn(path)
    repository.run_turn(path, loaded)
    assert _turn(path) == turn + 1


def test_a_competing_write_waits_for_the_months_events(
    loaded: LoadedData, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another writer arriving between the commit and the event write is refused (it changes
    nothing), and the Continue still writes its events."""
    path = _new(loaded, tmp_path, "compete")
    real = repository.write_pending
    refused: list[bool] = []

    def write_pending(*args: Any, **kwargs: Any) -> int:
        if kwargs.get("committed") is not None:

            def other() -> None:
                try:
                    with repository.write_session(path):
                        refused.append(False)
                except SaveBusyError:
                    refused.append(True)

            t = threading.Thread(target=other)
            t.start()
            t.join(10)
        return int(real(*args, **kwargs))

    monkeypatch.setattr(repository, "write_pending", write_pending)
    while not refused:
        repository.run_turn(path, loaded)
    assert refused == [True]
    with repository.open_session(path) as session:
        assert not has_pending(session)


def test_a_holiday_counts_a_month_whose_events_failed(
    loaded: LoadedData, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _new(loaded, tmp_path, "away")
    fault = FailAfterCommit(RuntimeError("the adapter fell over"), monkeypatch)
    start = _turn(path)
    result = holiday.run_holiday(path, loaded, MONTHS, "critical")
    assert fault.fired
    assert result.months_played == _turn(path) - start
