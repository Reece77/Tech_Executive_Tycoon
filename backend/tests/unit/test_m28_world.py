"""M28 (docs/formulas.md 41): the chain companies' data, the balance factor, December's
decisions, cycles and China's catch-up, on a game moved to 2026 (tests/world_helpers.py)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.world_helpers import world_state
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.fabs import nodes as nd
from tst.sim.ledger import apply_entries
from tst.sim.rng import RngFactory
from tst.sim.world import cycles, decide, operate
from tst.sim.world import data as wd
from tst.sim.world import formulas as wf
from tst.sim.world.config import FOUNDRY_GOOD

YEARS = range(2010, 2026)
DECEMBER_2026 = 203


def test_capacity_sums_match_world_supply_each_year(loaded: LoadedData) -> None:
    """Sub-task 1: every good's producers' capacity sums to the data's world supply in every
    January and December to 2025, and the named shares are suppliers.yaml's."""
    d = loaded.game_data
    for good in wd.all_goods(d):
        for year in YEARS:
            for month in (1, 12):
                turn = ym_to_turn(year, month)
                caps = wd.capacities(d, good, turn)
                assert sum(caps.values()) == pytest.approx(wd.world_capacity(d, good, turn))
                assert all(v >= -1e-6 for v in caps.values()), (good, turn)
                if good != FOUNDRY_GOOD:
                    world = d.chain_companies.supply_at(good, turn)  # type: ignore[union-attr]
                    for key, share in wd.named_shares(d, good, turn).items():
                        assert caps[key] == pytest.approx(share * world)


def test_foundries_match_nodes_yaml(loaded: LoadedData) -> None:
    d = loaded.game_data
    assert d.nodes is not None
    turn = nd.HISTORY_END
    caps = wd.capacities(d, FOUNDRY_GOOD, turn)
    for f in d.nodes.foundries:
        assert caps[f.key] == pytest.approx(nd.history_capacity(f, turn) * 12_000)


def test_the_world_starts_at_december_2025_capacity(loaded: LoadedData) -> None:
    state, balances = world_state(loaded)
    d = loaded.game_data
    for good in wd.all_goods(d):
        live = sum(f.capacity for f in state.world_facilities if f.good == good)
        assert live == pytest.approx(wd.world_capacity(d, good, nd.HISTORY_END))
    assert {c.id for c in state.chain()} == {r.company_id for r in state.chain_companies}
    assert not any(c.is_chain for c in state.rivals())  # the world's, not 15.3's
    assert not any(c.is_chain for c in state.ledger_companies())
    for rec in state.chain_companies:
        assert rec.executives and rec.executives[0][0] == "CEO"
        assert sum(v for (cid, _), v in balances.items() if cid == rec.company_id) == 0


def test_balance_factor_clamps() -> None:
    """Sub-task 3's unit test of the factor's clamp (41.2)."""
    from tst.balance.m28 import DATA
    from tst.loader import load_all

    wb = load_all(DATA).balance.world
    assert wf.balance_factor(100, 100, wb) == 1.0
    assert wf.balance_factor(1_000, 1, wb) == wb.factor_max
    assert wf.balance_factor(1, 1_000, wb) == wb.factor_min
    assert wf.balance_factor(110, 100, wb) == pytest.approx(1.1**wb.elasticity)
    assert wf.balance_factor(0, 0, wb) == 1.0
    assert wf.balance_factor(5, 0, wb) == wb.factor_max


def test_a_december_s_decisions_are_seeded(loaded: LoadedData) -> None:
    """Sub-task 3's seeded test: the same seed decides the same December; growing goods
    expand; every expansion is a building facility paid for in the books."""
    b, d = loaded.balance, loaded.game_data
    state, balances = world_state(loaded, seed=3, turn=DECEMBER_2026)
    rng = RngFactory(3)
    state, entries, _ = operate.operate(state, b, d, balances)
    balances = apply_entries(balances, entries)
    first = decide.decide(state, rng, b, d, balances)
    again = decide.decide(state, rng, b, d, balances)
    assert first == again
    new = [f for f in first[0].world_facilities if f.status == "building"]
    assert new, "a tight December brings expansions"
    assert {f.good for f in new} & {"lithium_carbonate", "ndpr_oxide", FOUNDRY_GOOD}
    capex = sum(e.lines[0].amount for e in first[1] if "capex" in e.memo)
    assert capex == sum(f.capex_cents for f in new)
    for f in new:
        assert f.ready_turn == DECEMBER_2026 + d.chain_companies.build_months[f.good]  # type: ignore[union-attr]
    other = decide.decide(state, RngFactory(4), b, d, balances)
    sizes = sorted(f.capacity for f in new)
    assert sizes != sorted(f.capacity for f in other[0].world_facilities if f.status == "building")


def test_no_decisions_outside_december(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, balances = world_state(loaded, turn=DECEMBER_2026 - 1)
    assert decide.decide(state, RngFactory(1), b, d, balances) == (state, [], [])


def test_a_facility_under_its_cost_mothballs_then_closes(loaded: LoadedData) -> None:
    """41.2: spot under cash cost for mothball_months mothballs it; close_months later it
    closes."""
    b, d = loaded.balance, loaded.game_data
    wb = b.world
    state, balances = world_state(loaded)
    dear = max(state.world_facilities, key=lambda f: f.cost)
    state = replace(
        state,
        world_facilities=tuple(
            replace(f, cost=1.0, below_months=wb.mothball_months - 1) if f.id == dear.id else f
            for f in state.world_facilities
        ),
    )
    # a cost position of 1 is cost_range.hi of the long-run price; push spot below it
    state = replace(
        state,
        world_facilities=tuple(
            replace(f, cost=1.0) if f.id == dear.id else f for f in state.world_facilities
        ),
    )
    from tst.sim.world import query as wq

    f = next(x for x in state.world_facilities if x.id == dear.id)
    if wq.price_usd(state, f.good, b, d) >= wq.cash_cost_usd(state, f, b, d):
        pytest.skip("this good's December 2025 price tops even the dearest cost")
    out, _, news = operate.operate(state, b, d, balances)
    f2 = next(x for x in out.world_facilities if x.id == dear.id)
    assert f2.status == "mothballed" and any(n.kind == "mothball" for n in news)
    later = replace(out, turn=out.turn + wb.close_months)
    closed, _, _ = operate.operate(later, b, d, balances)
    assert next(x for x in closed.world_facilities if x.id == dear.id).status == "closed"


def test_cycles_are_seeded_and_start_at_one(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _ = world_state(loaded)
    assert all(c.multiplier == 1.0 for c in state.region_cycles)
    a, _ = cycles.cycles_month(state, RngFactory(5), b, d)
    again, _ = cycles.cycles_month(state, RngFactory(5), b, d)
    assert a == again
    assert all(abs(c.multiplier - 1) < 0.1 for c in a.region_cycles)
    assert cycles.growth_ratio(a, "europe", a.turn) == pytest.approx(
        next(c.multiplier for c in a.region_cycles if c.region == "europe")
    )
    assert cycles.growth_ratio(state, "europe", state.turn - 5) == 1.0


def test_phase_effect_arches_to_its_depth() -> None:
    xs = [wf.phase_effect(-0.06, 11, k) for k in range(11)]
    assert min(xs) == pytest.approx(-0.06)
    assert xs[0] > xs[5] < xs[-1]
    assert wf.phase_effect(-0.06, 11, 11) == 0.0


def test_china_s_lost_customers_go_to_a_chinese_rival_from_2026(loaded: LoadedData) -> None:
    """41.5: from 2026 a controlled seller's customers leaving a closed destination go to the
    Chinese rival with most customers on a product of its category there; before, they leave."""
    from tst.sim.geopolitics.sales import _to_chinese_rival

    d = loaded.game_data
    state, _ = world_state(loaded)
    assert d.countries is not None
    chinese = {c.id for c in state.rivals() if d.countries.rivals.get(c.name) == "china"}
    found = None
    for r in state.regional_segments:
        p = state.product(r.product_id)
        if p is not None and p.company_id in chinese and r.region == "east_asia":
            seller = next(
                (
                    x
                    for x in state.products
                    if x.category == p.category and x.company_id not in chinese
                ),
                None,
            )
            if seller is not None:
                found = (r, seller)
                break
    assert found is not None
    target, seller = found
    best = max(
        (x.customers, -x.product_id)
        for x in state.regional_segments
        if x.region == "east_asia"
        and x.segment == target.segment
        and (q := state.product(x.product_id)) is not None
        and q.company_id in chinese
        and q.category == seller.category
    )
    pid = -best[1]
    before = next(
        x.customers
        for x in state.regional_segments_of(pid, "east_asia")
        if x.segment == target.segment
    )
    after_state = _to_chinese_rival(
        state, seller.id, "east_asia", target.segment, "north_america", 100.0, d
    )
    after = next(
        x.customers
        for x in after_state.regional_segments_of(pid, "east_asia")
        if x.segment == target.segment
    )
    assert after == pytest.approx(before + 100.0)
    history = replace(state, chain_companies=())
    assert (
        _to_chinese_rival(
            history, seller.id, "east_asia", target.segment, "north_america", 100.0, d
        )
        == history
    )
