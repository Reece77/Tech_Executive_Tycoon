"""M28 persistence (migration 0049): chain companies (company rows with rival key (7, i)) and
every living-world record survive a save and reload, and a turn played on that save keeps
the remembered state equal to a fresh load (TST_STATE_CACHE_CHECK)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import text

from tests.helpers import play_turn
from tst.db.repository import create_save, open_session
from tst.db.state_io import insert_entries, live_view, load_state, sync_state
from tst.loader import LoadedData
from tst.sim.rng import RngFactory
from tst.sim.world.setup import materialise

JAN_2026 = 192


def test_world_records_round_trip(
    tmp_path: Path, loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TST_STATE_CACHE_CHECK", "1")
    path = create_save(
        "world", 5, "ex_big_tech_founders", company_name="World Co", data=loaded,
        save_dir=tmp_path,
    )  # fmt: skip
    with open_session(path) as session:
        old = load_state(session)
        moved = replace(old, turn=JAN_2026)
        new, entries = materialise(moved, RngFactory(5), loaded.balance, loaded.game_data)
        sync_state(session, old, new)
        insert_entries(session, entries)
        session.execute(text("UPDATE save_meta SET current_turn = :t"), {"t": JAN_2026})
        session.commit()
    with open_session(path) as session:
        back = load_state(session)
    assert back.chain_companies == new.chain_companies
    assert back.world_facilities == new.world_facilities
    assert back.world_goods == new.world_goods
    assert back.region_cycles == new.region_cycles
    assert {c.id: c for c in back.companies if c.is_chain} == {
        c.id: c for c in new.companies if c.is_chain
    }
    assert live_view(new) == back
    play_turn(path, loaded)  # the world's first month on a save: cached and fresh agree
    with open_session(path) as session:
        after = load_state(session)
    assert after.turn == JAN_2026 + 1
    assert after.world_news or after.world_goods[0].turn == JAN_2026
