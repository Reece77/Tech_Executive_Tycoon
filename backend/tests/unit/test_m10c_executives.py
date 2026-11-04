"""M10c executives with authority in phase 2 (docs/formulas.md 24.1-24.2): each seat's rule
through the player's actions with the executive as actor, decision quality from the true
score (seeded), mistakes logged by name, and guardrails never exceeded (property test)."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import DATA_DIR
from tests.helpers import fresh_game, make_person, with_employee, with_product
from tst.loader import LoadedData, load_all
from tst.sim.actions.authority import guardrails_for
from tst.sim.data_models import Balance
from tst.sim.ledger import CASH
from tst.sim.org.authority import run_executives
from tst.sim.org.delegates import delegate_draws
from tst.sim.org.formulas import decision_quality
from tst.sim.org.models import Authority, ExecSeat
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    reach_stage,
    with_authority,
    with_company,
    with_exec_seat,
    with_product_segment,
)
from tst.sim.state import (
    with_product as put_product,
)

LOADED = load_all(DATA_DIR)
EXEC = 2  # the executive's person id
CASH_CENTS = 500_000_000


def _company(loaded: LoadedData, seat: str, role: str, staff: int = 0) -> GameState:
    state = fresh_game(loaded)
    state = with_employee(loaded, state, make_person(loaded, EXEC, role, "senior"), 15_000_000)
    for pid in range(3, 3 + staff):
        state = with_employee(loaded, state, make_person(loaded, pid), 9_000_000)
    state = with_company(state, reach_stage(state.player, 3, 0))
    return with_exec_seat(state, ExecSeat(1, seat, EXEC, 0))


def _give(state: GameState, seat: str, balance: Balance, **guards: object) -> GameState:
    rails = guardrails_for(None, seat, tuple(guards.items()), state, 1, balance)  # type: ignore[arg-type]
    anchors = tuple(
        (p.id, s.segment, s.price_cents)
        for p in state.company_products(1)
        for s in state.segments_of(p.id)
        if s.price_cents is not None
    )
    return with_authority(state, Authority(1, seat, True, rails, 0, anchors))


def _run(loaded: LoadedData, state: GameState, seed: int = 1, cash: int = CASH_CENTS):  # type: ignore[no-untyped-def]
    return run_executives(
        state, RngFactory(seed), loaded.balance, loaded.game_data, {(1, CASH): cash}
    )


def _right_seed(loaded: LoadedData, state: GameState, seat: str, right: bool) -> int:
    """A seed whose quality draw makes this month's choice right (or wrong)."""
    from tst.sim.org.executives import true_score

    p = decision_quality(
        true_score(state, EXEC, seat, loaded.balance), loaded.balance.exec_authority.quality
    )
    for seed in range(1, 500):
        u = float(delegate_draws(RngFactory(seed), state.turn, EXEC, 1_000_000).random())
        if (u < p) == right:
            return seed
    raise AssertionError("no seed")


def test_cto_hires_builders_for_a_product_below_its_maintenance_line(loaded: LoadedData) -> None:
    state = _company(loaded, "cto", "software_engineer")
    state = with_product(state, root=False)  # nobody works on it
    state = _give(state, "cto", loaded.balance)
    seed = _right_seed(loaded, state, "cto", right=True)
    out, _, logs, taken = _run(loaded, state, seed)
    (plan,) = out.plans
    assert (plan.role, plan.owner_id, plan.unit_id) == ("software_engineer", EXEC, None)
    assert plan.target == 2  # plan_hires; about 2 typical builders reach 1.5 (24.1)
    assert [a.actor_id for _, a in taken] == [EXEC]  # through the player's action path
    (decision,) = out.exec_decisions
    assert decision.seat == "cto" and not decision.mistake
    assert any(i.template == "exec_decisions" for i in logs)


def test_a_cto_mistake_is_a_slower_pace_and_is_logged_by_name(loaded: LoadedData) -> None:
    state = _company(loaded, "cto", "software_engineer")
    state = _give(state, "cto", loaded.balance)
    state = with_product(state, root=False)
    seed = _right_seed(loaded, state, "cto", right=False)
    out, _, logs, _ = _run(loaded, state, seed)
    (plan,) = out.plans
    assert plan.target == 1  # one hire fewer: a slower pace (24.2)
    (decision,) = out.exec_decisions
    assert decision.mistake
    summary = dict(next(i for i in logs if i.template == "exec_decisions").params)["summary"]
    person = out.person(EXEC)
    assert f"{person.first_name} {person.last_name} (CTO)" in summary and "misstep" in summary


def test_cro_hires_sellers_and_raises_a_capacity_limited_price(loaded: LoadedData) -> None:
    state = _company(loaded, "cro", "account_executive")
    state = with_product(state, prices={"mid_market": 70_000}, customers={"mid_market": 10.0})
    seg = state.segments_of(state.company_products(1)[0].id)[0]
    state = with_product_segment(state, replace(seg, capacity_limited=True))
    state = _give(state, "cro", loaded.balance)
    seed = _right_seed(loaded, state, "cro", right=True)
    out, _, _, _ = _run(loaded, state, seed)
    assert [p.role for p in out.plans] == ["account_executive"]
    price = out.segments_of(seg.product_id)[0].price_cents
    assert price == round(70_000 * 1.05)  # one step, within +10% of the anchor


def test_cro_never_prices_beyond_its_band(loaded: LoadedData) -> None:
    state = _company(loaded, "cro", "account_executive")
    state = with_product(state, prices={"mid_market": 70_000}, customers={"mid_market": 10.0})
    pid = state.company_products(1)[0].id
    state = _give(state, "cro", loaded.balance, price_band_pct=10)
    seg = state.segments_of(pid)[0]
    state = with_product_segment(state, replace(seg, capacity_limited=True, price_cents=76_500))
    for seed in range(1, 6):
        out, _, _, _ = _run(loaded, state, seed)
        assert (out.segments_of(pid)[0].price_cents or 0) <= 77_000


def test_cmo_spends_its_share_of_revenue(loaded: LoadedData) -> None:
    state = _company(loaded, "cmo", "marketer")
    state = with_product(state, customers={"smb": 1000.0}, brand=20.0)
    state = with_company(state, replace(state.player, mrr_history=(4_000_000,)))
    state = _give(state, "cmo", loaded.balance, marketing_pct_of_revenue=15)
    out, _, _, _ = _run(loaded, state, _right_seed(loaded, state, "cmo", right=True))
    assert out.company_products(1)[0].marketing_budget_cents == 600_000


def test_coo_opens_support_plans_below_target(loaded: LoadedData) -> None:
    state = _company(loaded, "coo", "operations_manager", staff=30)
    state = _give(state, "coo", loaded.balance)
    out, _, _, _ = _run(loaded, state, _right_seed(loaded, state, "coo", right=True))
    assert [p.role for p in out.plans] == ["operations_manager"]


def test_cfo_proposes_funding_when_runway_is_short(loaded: LoadedData) -> None:
    state = _company(loaded, "cfo", "finance_manager", staff=10)
    state = _give(state, "cfo", loaded.balance)
    out, _, logs, _ = _run(loaded, state, cash=10_000_000)
    assert out.pending_proposals(1)
    proposal = out.pending_proposals(1)[0]
    assert proposal.seat == "cfo" and proposal.kind in ("round", "loan")
    assert any(i.template == "exec_proposal" for i in logs)
    again, _, _, _ = _run(loaded, out, cash=10_000_000)
    assert len(again.pending_proposals(1)) == 1  # one at a time


def test_decision_quality_follows_the_true_score(loaded: LoadedData) -> None:
    """Seeded: the share of right choices over 400 seeds is near clamp(0.55 + 0.03 s)."""
    q = loaded.balance.exec_authority.quality
    for score in (8.0, 15.0):
        p = decision_quality(score, q)
        right = sum(
            float(delegate_draws(RngFactory(seed), 0, EXEC, 1_000_000).random()) < p
            for seed in range(400)
        )
        assert abs(right / 400 - p) < 0.06, (score, right)


@settings(max_examples=40, deadline=None)
@given(st.integers(0, 6), st.integers(1, 8), st.integers(1, 30))
def test_hiring_never_exceeds_the_headcount_cap(staff: int, cap: int, seed: int) -> None:
    state = _company(LOADED, "cto", "software_engineer", staff=staff)
    state = with_product(state, root=False)
    state = _give(state, "cto", LOADED.balance, headcount_cap=cap)
    out, _, _, _ = _run(LOADED, state, seed)
    builders = sum(
        1
        for e in out.staff(1)
        if not out.person(e.person_id).is_founder
        and LOADED.game_data.role(e.role).product_function == "builder"
    )
    planned = sum(p.target for p in out.plans)
    assert builders + planned <= max(cap, builders)


# --- Reports and executive events (24.3) ------------------------------------------------------


def test_a_quarterly_report_says_what_the_holder_did(loaded: LoadedData) -> None:
    from tst.sim.org.reports import EXEC_REPORT

    state = _company(loaded, "cto", "software_engineer")
    state = _give(replace(with_product(state, root=False), turn=2), "cto", loaded.balance)
    product = state.company_products(1)[0]
    state = put_product(state, replace(product, rotting=True))
    seed = _right_seed(loaded, state, "cto", right=False)
    _, _, logs, _ = _run(loaded, state, seed)
    (report,) = [i for i in logs if i.template == EXEC_REPORT]
    params = dict(report.params)
    assert report.link_id == EXEC and params["seat"] == "CTO"
    text = str(params["report"])
    # M13b (27.2): decisions first, in the holder's voice, then pitches, worries, numbers
    assert text.startswith("Q1 2010")
    assert "opened a plan for" in text and "could have been better" in text
    assert "has nobody working on it" in text  # a concern
    assert text.index("could have been better") < text.index("has nobody working on it")
    assert text.endswith("1 builder on 1 product (1 live, 0 in development).")
    off = replace(state, turn=3)  # not a quarter end
    assert not [i for i in _run(loaded, off, seed)[2] if i.template == EXEC_REPORT]


def test_a_seat_without_authority_still_reports(loaded: LoadedData) -> None:
    from tst.sim.org.reports import quarterly_reports

    state = replace(_company(loaded, "cfo", "finance_manager", staff=2), turn=5)
    (report,) = quarterly_reports(state, 10_000_000, loaded.balance, loaded.game_data)
    text = str(dict(report.params)["report"])
    assert "Q2 2010" in text and "cash $100,000.00; debt $0.00" in text  # 27.2 layout
    assert "no authority" in text


def _hits(loaded: LoadedData, state: GameState, cash: int) -> dict[str, list[tuple[int, ...]]]:
    from tst.sim.events.triggers import triggers

    out: dict[str, list[tuple[int, ...]]] = {}
    for h in triggers(state, state, loaded.balance, loaded.game_data, cash, ()):
        out.setdefault(h.trigger, []).append(h.person_ids)
    return out


def test_executives_with_authority_raise_their_events(loaded: LoadedData) -> None:
    from tst.sim.people.relationships import Relationship
    from tst.sim.state import with_relationship

    state = _company(loaded, "cfo", "finance_manager", staff=10)
    assert "exec_cfo" not in _hits(loaded, state, 10_000_000)  # no authority yet
    state = _give(state, "cfo", loaded.balance)
    assert _hits(loaded, state, 10_000_000)["exec_cfo"] == [(EXEC,)]
    assert "exec_cfo" not in _hits(loaded, state, 10**12)  # runway above the guardrail
    state = with_exec_seat(state, ExecSeat(1, "cto", 3, 0))
    state = with_authority(state, Authority(1, "cto", True, (), 0, ()))
    hits = _hits(loaded, state, 10**12)
    assert hits["exec_cto"] == [(3,)]
    state = with_relationship(state, Relationship(EXEC, 3, -25.0, 0.0, 0))
    assert _hits(loaded, state, 10**12)["exec_clash"] == [(EXEC, 3)]


def test_the_named_coo_answers_ask_my_coo(loaded: LoadedData) -> None:
    from tst.events.coo import offline_reply
    from tst.sim.coo import coo_of

    state = _company(loaded, "coo", "software_engineer", staff=2)
    assert coo_of(state) == EXEC  # the seat holder, not the longest-serving employee
    reply = offline_reply((), "Q1 2010: 3 staff.")
    assert "From my last report: Q1 2010: 3 staff." in reply


@settings(max_examples=30, deadline=None)
@given(st.integers(0, 6), st.integers(1, 8), st.integers(1, 30))
def test_seller_hiring_never_exceeds_the_cro_cap(sellers: int, cap: int, seed: int) -> None:
    state = _company(LOADED, "cro", "account_executive")
    for pid in range(3, 3 + sellers):
        state = with_employee(
            LOADED, state, make_person(LOADED, pid, "account_executive"), 9_000_000
        )
    state = with_product(state, prices={"mid_market": 70_000}, customers={"mid_market": 10.0})
    seg = state.segments_of(state.company_products(1)[0].id)[0]
    state = with_product_segment(state, replace(seg, capacity_limited=True))
    state = _give(state, "cro", LOADED.balance, headcount_cap=cap)
    out, _, _, _ = _run(LOADED, state, seed)
    on_staff = sum(
        1
        for e in out.staff(1)
        if not out.person(e.person_id).is_founder
        and LOADED.game_data.role(e.role).product_function == "seller"
    )
    planned = sum(p.target for p in out.plans)
    assert on_staff + planned <= max(cap, on_staff)
