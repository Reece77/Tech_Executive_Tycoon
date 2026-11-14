"""M28r (docs/formulas.md 41.2, "the world starts with its pipeline"): each opening facility grows
month by month along its good's pre-M28 path until the first December decisions can land, then
holds; rivals plan on the pipeline still to arrive; its capex is in the opening books."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.world_helpers import WORLD_START, world_state
from tst.loader import LoadedData
from tst.sim.fabs import nodes as nd
from tst.sim.world import operate, pipeline
from tst.sim.world import data as wd
from tst.sim.world.config import FOUNDRY_GOOD

DECEMBER_2026 = 203


def _run(loaded: LoadedData, months: int, seed: int = 2) -> list[dict[tuple[int, str], float]]:
    """Capacity by (company, good) after each of `months` world months from January 2026."""
    b, d = loaded.balance, loaded.game_data
    state, balances = world_state(loaded, seed=seed)
    out = []
    for m in range(months):
        state = replace(state, turn=WORLD_START + m)
        state, _, _ = operate.operate(state, b, d, balances)
        caps: dict[tuple[int, str], float] = {}
        for f in state.world_facilities:
            if pipeline.is_opening(f):
                k = (f.company_id, f.good)
                caps[k] = caps.get(k, 0.0) + f.capacity
        out.append(caps)
    return out


def test_end_is_the_month_before_the_first_decisions_land(loaded: LoadedData) -> None:
    d = loaded.game_data
    build = wd.chain_file(d).build_months
    assert pipeline.first_december(WORLD_START) == DECEMBER_2026
    for g in wd.all_goods(d):
        assert pipeline.end_turn(WORLD_START, g, d) == DECEMBER_2026 + build[g] - 1


def test_foundries_follow_38_3_s_seeded_path_then_hold(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    assert d.nodes is not None
    seed = 2
    tl = nd.timeline(seed, d.nodes, b.fab)
    end = pipeline.end_turn(WORLD_START, FOUNDRY_GOOD, d)
    months = end - WORLD_START + 3
    runs = _run(loaded, months, seed)
    state, _ = world_state(loaded, seed=seed)
    ids = {r.key: r.company_id for r in state.chain_companies}
    for f in d.nodes.foundries:
        cid = ids[f.key]
        for m, caps in enumerate(runs):
            t = min(WORLD_START + m, end)
            want = nd.capacity(tl, f, t, b.fab) * 12_000
            assert caps[(cid, FOUNDRY_GOOD)] == pytest.approx(want, rel=1e-9), (f.key, m)
        assert runs[-1][(cid, FOUNDRY_GOOD)] == pytest.approx(runs[-3][(cid, FOUNDRY_GOOD)])


def test_commodities_grow_with_demand_then_hold(loaded: LoadedData) -> None:
    """A commodity's pipeline keeps supply at base_utilisation level with the baseline demand,
    so its balance factor stays at 1 (absent cycles and the player) while the pipeline runs."""
    b, d = loaded.balance, loaded.game_data
    g = "gallium"  # the shortest build: the pipeline ends December 2027
    end = pipeline.end_turn(WORLD_START, g, d)
    runs = _run(loaded, end - WORLD_START + 3)
    state, _ = world_state(loaded)
    start = sum(f.capacity for f in state.world_facilities if f.good == g)
    growth = wd.chain_file(d).demand_growth[g]
    for m, caps in enumerate(runs):
        t = min(WORLD_START + m, end)
        total = sum(v for (_, good), v in caps.items() if good == g)
        assert total == pytest.approx(start * (1 + growth) ** ((t - (WORLD_START - 1)) / 12))
        demand = operate.baseline(state, g, t, b, d)
        assert total * b.world.base_utilisation == pytest.approx(demand)


def test_rivals_plan_on_the_pipeline_still_to_arrive(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _ = world_state(loaded)
    names = pipeline.keys(state)
    for f in state.world_facilities[:20]:
        end = pipeline.end_turn(f.ordered_turn, f.good, d)
        key = names[f.company_id]
        final = pipeline.ratio(state, f.good, key, f.ordered_turn, end, b, d)
        now = pipeline.ratio(state, f.good, key, f.ordered_turn, state.turn, b, d)
        # in a turn, decisions read capacity after the month's step (capacity at `now`)
        want = f.capacity * final / now
        assert pipeline.committed(state, f, b, d, names) == pytest.approx(want)
        assert final > now > 1
        later = replace(state, turn=end)
        assert pipeline.committed(later, f, b, d, names) == f.capacity


def test_the_pipeline_s_capex_is_in_the_opening_books(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    wb = b.world
    state, _ = world_state(loaded)
    from tst.sim.world import query as wq

    names = pipeline.keys(state)
    for f in state.world_facilities[:20]:
        lr = wq.long_run_usd(state, f.good, b, d)
        replacement = f.capacity * lr * wb.capex_years * wq.CENTS
        final = pipeline.ratio(
            state,
            f.good,
            names[f.company_id],
            f.ordered_turn,
            pipeline.end_turn(f.ordered_turn, f.good, d),
            b,
            d,
        )
        want = replacement * wb.open_book + replacement * (final - 1)
        assert f.capex_cents == pytest.approx(want, abs=1)


def test_no_pipeline_share_keeps_capacity_flat(loaded: LoadedData) -> None:
    b = loaded.balance
    flat = b.model_copy(update={"world": b.world.model_copy(update={"pipeline_share": 0.0})})
    state, balances = world_state(loaded)
    before = {f.id: f.capacity for f in state.world_facilities}
    out, _, _ = operate.operate(state, flat, loaded.game_data, balances)
    assert {f.id: f.capacity for f in out.world_facilities} == before
