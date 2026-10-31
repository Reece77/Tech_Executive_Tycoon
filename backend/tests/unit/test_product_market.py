"""Phases 5, 6, 9, 10 (formulas.md 11.1, 11.5-11.8, 11.11): appeal, churn, customers won
against the incumbents, awareness and sales capacity, revenue, hosting and marketing, brand
and demand growth, ARR stages, and the month-end history."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import FIRST_PRODUCT, fresh_game, make_person, with_employee, with_product
from tst.loader import LoadedData
from tst.sim.decisions import Decisions
from tst.sim.ledger import CASH, COMPUTE, MARKETING, REVENUE_SUBSCRIPTIONS
from tst.sim.products import formulas as f
from tst.sim.products.phases import (
    brand_and_demand,
    run_markets,
    segment_appeal,
)
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_product_segment
from tst.sim.turn import TurnResult, advance_turn

PRODUCT = FIRST_PRODUCT
CASH_START = 150_000_000


def turn(state: GameState, loaded: LoadedData, seed: int = 4) -> TurnResult:
    return advance_turn(
        state,
        Decisions(),
        RngFactory(seed),
        loaded.balance,
        loaded.game_data,
        {(1, CASH): CASH_START},
    )


def new_customers(result: TurnResult, segment: str = "smb") -> float:
    return next(
        m.new for m in result.product_months if m.product_id == PRODUCT and m.segment == segment
    )


def base(loaded: LoadedData, **kwargs: object) -> GameState:
    defaults: dict[str, object] = {"quality": 40.0, "brand": 20.0, "feature_points": 40.0}
    defaults.update(kwargs)
    return with_product(fresh_game(loaded), **defaults)  # type: ignore[arg-type]


def test_a_lower_price_wins_more_new_customers(loaded: LoadedData) -> None:
    baseline = new_customers(turn(base(loaded), loaded))
    cheaper = new_customers(turn(base(loaded, prices={"smb": 3200}), loaded))
    assert baseline > 0
    assert cheaper > baseline
    print(f"new customers next month: $40 {baseline:.1f}, $32 {cheaper:.1f}")


def test_more_quality_wins_more_new_customers(loaded: LoadedData) -> None:
    baseline = new_customers(turn(base(loaded), loaded))
    better = new_customers(turn(base(loaded, quality=50.0), loaded))
    assert better > baseline
    print(f"new customers next month: quality 40 {baseline:.1f}, quality 50 {better:.1f}")


def smb_shares(state: GameState, loaded: LoadedData) -> dict[int, float]:
    """share* of every live B2B SaaS product in SMB at the phase-5 scores (11.7)."""
    data = loaded.game_data
    products = {p.id: p for p in state.products}
    live = [
        s
        for s in state.product_segments
        if s.segment == "smb" and products[s.product_id].category == "b2b_saas"
    ]
    appeals = [segment_appeal(products[s.product_id], s, data, state.turn) or 0.0 for s in live]
    shares, _ = f.choice_shares(appeals, data.segment("smb").outside_option, loaded.balance.market)
    return {s.product_id: share for s, share in zip(live, shares, strict=True)}


def test_awareness_limits_self_serve_wins(loaded: LoadedData) -> None:
    state = base(loaded, brand=10.0)
    out = run_markets(state, RngFactory(4), loaded.balance, loaded.game_data)
    shares = smb_shares(state, loaded)
    in_play = out.flows[(1, "smb")].new / shares[1]  # Sales Cloud wins share* x P in full
    won = out.flows[(PRODUCT, "smb")].new
    aware = f.awareness(10.0, loaded.balance.market)
    assert aware == pytest.approx(0.05)
    assert won == pytest.approx(in_play * shares[PRODUCT] * aware)
    assert won < in_play * shares[PRODUCT]


def _sales_state(loaded: LoadedData, sellers: int) -> GameState:
    state = fresh_game(loaded)
    for pid in range(2, 2 + sellers):
        state = with_employee(
            loaded, state, make_person(loaded, pid, "account_executive"), 9_000_000, morale=60
        )
    return with_product(
        state, prices={"mid_market": 70_000}, quality=55.0, brand=40.0, feature_points=60.0
    )


def test_sales_capacity_limits_mid_market_wins_and_the_inbox_says_so(
    loaded: LoadedData,
) -> None:
    none = run_markets(_sales_state(loaded, 0), RngFactory(4), loaded.balance, loaded.game_data)
    assert none.flows[(PRODUCT, "mid_market")].new == 0
    seg = none.state.product_segment(PRODUCT, "mid_market")
    assert seg is not None and seg.capacity_limited
    notes = [i for i in none.logs if i.template == "sales_capacity_limited"]
    assert len(notes) == 1 and dict(notes[0].params)["segment"] == "Mid-market"
    again = run_markets(
        replace(none.state, turn=1), RngFactory(4), loaded.balance, loaded.game_data
    )
    assert not [i for i in again.logs if i.template == "sales_capacity_limited"]  # once

    one = _sales_state(loaded, 1)
    out = run_markets(one, RngFactory(4), loaded.balance, loaded.game_data)
    person = one.person(2)
    sell = f.sell_skill(
        person.skills["sales"], person.skills["negotiation"], person.skills["communication"]
    )
    cap = 2 * f.contribution(sell, f.morale_factor(60, loaded.balance.products))
    assert out.flows[(PRODUCT, "mid_market")].new == pytest.approx(cap)


def test_revenue_hosting_and_marketing_post_balanced_entries(loaded: LoadedData) -> None:
    state = base(loaded, customers={"smb": 1000.0}, budget_cents=1_000_000)
    result = turn(state, loaded)
    seg = result.new_state.product_segment(PRODUCT, "smb")
    assert seg is not None
    revenue = [e for e in result.ledger_entries if e.memo == "Revenue: Pipeline"]
    assert len(revenue) == 1
    lines = {ln.account: ln.amount for ln in revenue[0].lines}
    assert lines == {CASH: round(seg.customers * 4000), REVENUE_SUBSCRIPTIONS: -lines[CASH]}
    costs = next(e for e in result.ledger_entries if e.memo.startswith("Monthly costs"))
    cost_lines = {ln.account: ln.amount for ln in costs.lines}
    assert cost_lines[COMPUTE] == round(seg.customers * 400)
    assert cost_lines[MARKETING] == 1_000_000
    assert "Hosting" in costs.memo and "Marketing" in costs.memo
    assert all(sum(ln.amount for ln in e.lines) == 0 for e in result.ledger_entries)
    snap = result.snapshot.for_company(1)
    assert snap.mrr_cents == lines[CASH] and snap.arr_cents == 12 * lines[CASH]
    assert snap.kpis()["mrr_cents"] == snap.mrr_cents


def test_incumbents_keep_books(loaded: LoadedData) -> None:
    """From M5 every rival in business has a ledger and a month-end snapshot (15.1)."""
    state = fresh_game(loaded)
    result = turn(state, loaded)
    ids = {c.id for c in state.companies}
    assert {e.company_id for e in result.ledger_entries} == ids
    assert [s.company_id for s in result.snapshot.companies] == sorted(ids)


def test_one_million_arr_enters_stage_2_and_notes_the_milestone(loaded: LoadedData) -> None:
    state = base(loaded, customers={"smb": 3000.0})  # about $120k MRR
    result = turn(state, loaded)
    assert result.snapshot.for_company(1).arr_cents >= 100_000_000
    assert result.new_state.player.stage == 2
    notes = [i for i in result.log_items if i.template == "arr_milestone"]
    assert len(notes) == 1 and dict(notes[0].params)["milestone_cents"] == 100_000_000
    second = turn(result.new_state, loaded)
    assert not [i for i in second.log_items if i.template == "arr_milestone"]
    assert second.new_state.player.stage == 2


def test_first_paying_customer_is_noted_once(loaded: LoadedData) -> None:
    state = base(loaded, brand=30.0)
    result = turn(state, loaded)
    notes = [i for i in result.log_items if i.template == "first_customer"]
    assert len(notes) == 1
    product = result.new_state.product(PRODUCT)
    assert product is not None and product.first_customer_turn == 0
    later = turn(result.new_state, loaded)
    assert not [i for i in later.log_items if i.template == "first_customer"]


def test_sunset_churns_three_times_faster_and_retires(loaded: LoadedData) -> None:
    live = base(loaded, customers={"smb": 100.0})
    sunset = base(loaded, customers={"smb": 100.0}, status="sunset")
    a = run_markets(live, RngFactory(4), loaded.balance, loaded.game_data)
    b = run_markets(sunset, RngFactory(4), loaded.balance, loaded.game_data)
    assert b.flows[(PRODUCT, "smb")].churned == pytest.approx(3 * a.flows[(PRODUCT, "smb")].churned)
    assert b.flows[(PRODUCT, "smb")].new == 0
    nearly = base(loaded, customers={"smb": 0.4}, status="sunset")
    out = run_markets(nearly, RngFactory(4), loaded.balance, loaded.game_data)
    product = out.state.product(PRODUCT)
    assert product is not None and product.status == "retired" and product.retired_turn == 0


def test_products_in_development_win_nothing(loaded: LoadedData) -> None:
    state = base(loaded, status="in_development")
    out = run_markets(state, RngFactory(4), loaded.balance, loaded.game_data)
    assert (PRODUCT, "smb") not in out.flows
    assert out.revenue[1] == 0


def test_brand_follows_marketing_and_demand_grows(loaded: LoadedData) -> None:
    state = base(loaded, brand=0.0, budget_cents=1_000_000)
    after = brand_and_demand(state, loaded.balance, loaded.game_data)
    product = after.product(PRODUCT)
    assert product is not None
    target = f.target_brand(10, loaded.game_data.category("b2b_saas").brand_constant)
    assert product.brand == pytest.approx(0.1 * target)
    smb = after.market("b2b_saas", "smb")
    assert smb is not None and smb.addressable == pytest.approx(400_000 * 1.2 ** (1 / 12))
    sales_cloud = after.products[0]
    assert sales_cloud.brand == 80  # incumbents keep their brand (ADR-0017)


def test_demand_noise_is_seeded_per_segment(loaded: LoadedData) -> None:
    state = base(loaded)
    a = run_markets(state, RngFactory(4), loaded.balance, loaded.game_data)
    b = run_markets(state, RngFactory(4), loaded.balance, loaded.game_data)
    c = run_markets(state, RngFactory(5), loaded.balance, loaded.game_data)
    assert a.flows == b.flows
    assert a.flows != c.flows


def test_history_rows_cover_every_product_segment(loaded: LoadedData) -> None:
    result = turn(base(loaded, customers={"smb": 50.0}), loaded)
    rows = {(m.product_id, m.segment) for m in result.product_months}
    assert rows == {(s.product_id, s.segment) for s in result.new_state.product_segments}
    row = next(m for m in result.product_months if m.product_id == PRODUCT)
    seg = result.new_state.product_segment(PRODUCT, "smb")
    assert seg is not None and row.customers == seg.customers
    assert row.revenue_cents == round(seg.customers * 4000)


def test_unpriced_segments_do_not_sell(loaded: LoadedData) -> None:
    state = base(loaded, prices={"smb": 4000, "mid_market": None})
    state = with_product_segment(state, replace(state.segments_of(PRODUCT)[0], customers=0.0))
    out = run_markets(state, RngFactory(4), loaded.balance, loaded.game_data)
    flow = out.flows[(PRODUCT, "mid_market")]
    assert (flow.new, flow.churned, flow.revenue_cents) == (0, 0, 0)


def test_retiring_frees_the_units_working_on_it(loaded: LoadedData) -> None:
    state = base(loaded, customers={"smb": 0.2}, status="sunset")
    assert state.player.root_product_id == PRODUCT
    out = run_markets(state, RngFactory(4), loaded.balance, loaded.game_data)
    assert out.state.player.root_product_id is None
