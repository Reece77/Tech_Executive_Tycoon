"""M43r finding 3 (Codex review 9): the conglomerate view's planned capital shows only public
construction figures.

For every facility kind mapped into the panel, two states that differ only in a build's hidden
overrun give the same allocation, and the allocation is what the kind's own screen projects:
its shown total (the quote, a mine's estimate or revision, else the open capex) less payments."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.fabs.models import Fab
from tst.sim.facilities.models import Facility
from tst.sim.group.conglomerate import Books, industry_maps
from tst.sim.mining.models import Mine
from tst.sim.power.models import Plant
from tst.sim.refining.models import Refinery
from tst.sim.state import GameState
from tst.sim.vehicles.models import CellPlant

FID = 9_000_001
QUOTE = 90_000_000_00  # the public quote
PAID = 20_000_000_00
NO_BOOKS = Books(cells={}, company={}, uses={}, years=())


def _kinds(loaded: LoadedData) -> list[str]:
    _, kinds, _, _, _ = industry_maps(loaded.balance.conglomerate)
    return sorted(kinds)


def _build(loaded: LoadedData, kind: str, overrun: float) -> tuple[GameState, int]:
    """A building facility of `kind` with `overrun` hidden in it; returns the state and the
    total its screen shows."""
    b, d = loaded.balance, loaded.game_data
    state = fresh_game(loaded)
    cid = state.player.id
    true = round(QUOTE * (1 + overrun))
    facility = Facility(
        id=FID,
        company_id=cid,
        kind=kind,
        region="north_america",
        capacity=10,
        on_time=10,
        ordered_turn=0,
        ready_turn=24,
        late_turn=24,
        capex_cents=true,
        input_index=1.0,
        capex_paid_cents=PAID,
        status="building",
    )
    shown = QUOTE
    if kind == "fab":
        from tst.sim.fabs import market as fm

        node = fm.nodes_file(d).nodes[0].key  # any node
        state = replace(state, fabs=(Fab(FID, cid, node, QUOTE, 24),))
    elif kind in b.refining.kinds:
        recipe = b.refining.recipes_of(kind)[0]
        state = replace(state, refineries=(Refinery(FID, cid, recipe, QUOTE),))
    elif kind == "plant":
        assert d.power is not None
        plant = Plant(FID, cid, d.power.plant_types[0].key, 10.0, QUOTE, 24, 1)
        state = replace(state, plants=(plant,))
    elif kind == "cell_plant":
        state = replace(state, cell_plants=(CellPlant(FID, cid, "lfp", QUOTE, overrun=overrun),))
    elif kind == "mine":
        facility = replace(facility, capex_cents=QUOTE, capex_paid_cents=0)
        mine = Mine(
            id=FID, company_id=cid, project_id=1, region="north_america", block=0,
            commodity="copper", subtype="open_pit", level="definitive", capacity_t=1.0,
            design_grade=1.0, design_recovery=0.9, ordered_turn=0, ready_turn=24,
            estimate_cents=QUOTE, hidden_overrun=overrun, hidden_ore_mt=1.0, hidden_grade=1.0,
            hidden_recovery=0.9, capex_paid_cents=PAID,
        )  # fmt: skip
        state = replace(state, mines=(mine,))
    else:  # priced in the open: no hidden overrun, the screen shows the facility's capex
        shown = true
    return replace(state, facilities=(*state.facilities, facility)), shown


@pytest.mark.parametrize("kind", ["fab", "plant", "cell_plant", "mine", "li_converter"])
def test_overrun_kinds_are_in_the_panel(loaded: LoadedData, kind: str) -> None:
    assert kind in _kinds(loaded)


def test_planned_capital_never_moves_with_a_hidden_overrun(loaded: LoadedData) -> None:
    from tst.api.app import create_app  # the API's import order (the module alone cycles)

    create_app()
    from tst.api.conglomerate_views import _planned
    from tst.db.conglomerate import members

    _, kinds, _, _, _ = industry_maps(loaded.balance.conglomerate)
    for kind in _kinds(loaded):
        low, shown_low = _build(loaded, kind, 0.05)
        high, shown_high = _build(loaded, kind, 0.40)
        a = _planned(low, members(low), NO_BOOKS, loaded)[kinds[kind]][0]
        z = _planned(high, members(high), NO_BOOKS, loaded)[kinds[kind]][0]
        assert a == shown_low - PAID, kind
        assert z == shown_high - PAID, kind
        if shown_low == shown_high:  # a quoted kind: only the hidden overrun differs
            assert a == z, kind
