"""M57r-B sub-task 5 (review 10 items 33 and 34): a custom scenario's stored copy is checked
against its hash at load, results are kept by scenario and hash, `0071_m57rb` corrects 0066's
start month, and a save from a newer build is refused with a domain error, untouched."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db import migrate
from tst.db.custom_io import CustomScenarioMismatchError, stored_custom
from tst.db.repository import create_save
from tst.loader import LoadedData
from tst.profile import results


@pytest.fixture
def save_dir(tmp_path: Path) -> Path:
    return tmp_path / "saves"


@pytest.fixture
def client(save_dir: Path) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as c:
        yield c


def _custom_game(client: TestClient, save_dir: Path) -> Path:
    spec = client.get("/api/editor/open/platform_war").json()
    spec["key"] = "phones"
    assert client.post("/api/scenarios/custom", json=spec).status_code == 201
    body = {
        "name": "phones",
        "seed": 4,
        "scenario": "garage_bootstrap",
        "company_name": "Kestrel",
        "custom": "phones",
    }
    assert client.post("/api/saves", json=body).status_code == 201
    return save_dir / "phones.tst.sqlite"


def _sql(path: Path, statement: str) -> None:
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(statement)
        conn.commit()


def test_a_tampered_or_missing_custom_copy_is_refused_at_load(
    client: TestClient, save_dir: Path
) -> None:
    """Item 33 (F34): the turn no longer silently runs the base world when the stored copy is
    gone or changed: the load raises a domain error and the API refuses the save."""
    path = _custom_game(client, save_dir)
    assert stored_custom(path) is not None
    _sql(path, "UPDATE custom_scenario SET yaml = yaml || ' '")  # a changed copy
    with pytest.raises(CustomScenarioMismatchError, match="does not match"):
        stored_custom(path)
    r = client.post("/api/saves/phones/advance")
    assert r.status_code == 409 and r.json()["code"] == "custom_scenario_mismatch"
    _sql(path, "DELETE FROM custom_scenario")  # a missing copy
    with pytest.raises(CustomScenarioMismatchError, match="missing"):
        stored_custom(path)


def test_a_plain_save_is_not_custom(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "plain", 3, "garage_bootstrap", company_name="P", data=loaded, save_dir=tmp_path
    )
    assert stored_custom(path) is None


def test_custom_results_are_kept_by_scenario_and_hash(tmp_path: Path) -> None:
    """Item 33 (F32): edit a scenario to be trivial, win, edit it back: the easy win is kept
    under the easy version's hash and is never the best of the hard one."""
    assert results.result_key("custom/phones", "abc") == "custom/phones@abc"
    assert results.result_key("garage_bootstrap", None) == "garage_bootstrap"
    path = results.results_path(tmp_path, "default", custom=True)
    path.parent.mkdir(parents=True)
    old = {
        "custom/phones": {
            "easy:1": {"save": "easy", "sha256": "easyhash", "result": "success", "adjusted": 9},
            "hard:2": {"save": "hard", "sha256": "hardhash", "result": "failure", "adjusted": 1},
        }
    }
    results._write(path, "default", old)  # written before M57r-B: by scenario alone
    got = results.load(tmp_path, "default", custom=True)
    assert set(got) == {"custom/phones@easyhash", "custom/phones@hardhash"}
    best = results.best(got["custom/phones@hardhash"])
    assert best is not None and best["save"] == "hard"


def test_0071_sets_a_late_start_saves_start_month(tmp_path: Path, loaded: LoadedData) -> None:
    """Item 34 (F35, reproduced: a v6.0.0 Sandbox begun in 2015 migrated with start_turn 0 and
    created_turn 60): 0071 sets start_turn = created_turn where created_turn > 0."""
    path = create_save(
        "late", 3, "garage_bootstrap", company_name="L", data=loaded, save_dir=tmp_path
    )
    plain = create_save(
        "plain", 3, "garage_bootstrap", company_name="P", data=loaded, save_dir=tmp_path
    )
    for p in (path, plain):
        migrate.downgrade(p, "0070_m55")
    _sql(path, "UPDATE save_meta SET created_turn = 60, start_turn = 0")
    for p in (path, plain):
        migrate.ensure_current(p)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT start_turn, schema_version FROM save_meta").fetchone() == (
            60,
            71,
        )
    with closing(sqlite3.connect(plain)) as conn:
        assert conn.execute("SELECT start_turn FROM save_meta").fetchone() == (0,)


def test_a_save_from_a_newer_build_is_refused_untouched(
    client: TestClient, save_dir: Path, loaded: LoadedData
) -> None:
    """Item 34: a save whose schema revision this build does not know (made by a newer
    version, then opened by an older one) raises "made by a newer version", not Alembic's raw
    error, and is neither migrated nor backed up."""
    path = create_save(
        "future", 3, "garage_bootstrap", company_name="F", data=loaded, save_dir=save_dir
    )
    _sql(path, "UPDATE alembic_version SET version_num = '0099_future'")
    migrate._AT_HEAD.clear()
    before = path.read_bytes()
    with pytest.raises(migrate.SaveTooNewError, match="newer version"):
        migrate.ensure_current(path)
    assert path.read_bytes() == before
    assert not list((save_dir / "backups").glob("*")) if (save_dir / "backups").exists() else True
    r = client.post("/api/saves/future/advance")
    assert r.status_code == 409 and r.json()["code"] == "save_too_new", r.text
