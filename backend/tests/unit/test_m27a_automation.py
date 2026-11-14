"""M27a automation everywhere (docs/formulas.md 40): data, owners and eligibility, limits and
one-offs (property tests), decision quality (seeded), the new area rules, routine events
(critical never), the digest (no hidden value) and 40.9 (no owners: nothing moves)."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from tests.conftest import DATA_DIR
from tests.helpers import fresh_game, make_person, with_employee, with_product
from tst.loader import LoadedData, automation_problems, load_all
from tst.sim.actions import BuildFacility, SetPrice, StartRound, action_payload
from tst.sim.actions.authority import AnswerProposal, proposal_action
from tst.sim.automation import digest, limits, owners, rules
from tst.sim.automation.actions import SetAreaOwner, SetAreaSettings, TakeBackArea
from tst.sim.automation.config import KPIS, ONE_OFF_ACTIONS, RULES
from tst.sim.automation.events import answer_routine, owner_for, ranked_choices
from tst.sim.automation.models import AreaOwner
from tst.sim.automation.run import AutoRun, automation_month
from tst.sim.data_models import AutomationArea
from tst.sim.errors import OrgRuleError
from tst.sim.events.models import Effect, EventChoice, GameEvent
from tst.sim.ledger import CASH
from tst.sim.org.formulas import decision_quality
from tst.sim.org.models import ExecSeat
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    reach_stage,
    with_area_owner,
    with_company,
    with_employment,
    with_event,
    with_exec_seat,
    with_person,
    with_product_segment,
)

LOADED = load_all(DATA_DIR)
B = LOADED.balance
FOUNDER = 1
LEAD = 2
SEAT = 3
CASH_CENTS = 500_000_000
LIMIT = 5_000_000


def _skilled(person, value: float):  # type: ignore[no-untyped-def]
    return replace(person, skills=person.skills.updated(dict.fromkeys(person.skills.keys(), value)))


def _company(
    loaded: LoadedData = LOADED,
    *,
    lead_role: str = "recruiter",
    lead_level: str = "senior",
    skill: float = 15.0,
    seat: str | None = None,
    staff: int = 0,
) -> GameState:
    state = fresh_game(loaded)
    person = _skilled(make_person(loaded, LEAD, lead_role, lead_level), skill)
    state = with_employee(loaded, state, person, 12_000_000)
    if seat is not None:
        holder = _skilled(make_person(loaded, SEAT, "operations_manager", "senior"), skill)
        state = with_employee(loaded, state, holder, 15_000_000)
        state = with_exec_seat(state, ExecSeat(1, seat, SEAT, 0))
    for pid in range(10, 10 + staff):
        state = with_employee(loaded, state, make_person(loaded, pid), 9_000_000)
    return with_company(state, reach_stage(state.player, 3, 0))


def _own(state: GameState, area: str, person: int = LEAD, limit: int = LIMIT) -> GameState:
    return with_area_owner(state, AreaOwner(1, area, person, limit, 0, state.turn))


def _month(state: GameState, seed: int = 1, cash: int = CASH_CENTS):  # type: ignore[no-untyped-def]
    return automation_month(state, RngFactory(seed), B, LOADED.game_data, {(1, CASH): cash})


# --- 1. Data and the model -------------------------------------------------------------------


def test_area_weights_must_sum_to_one() -> None:
    with pytest.raises(ValidationError, match="sum to 1"):
        AutomationArea(
            label="Bad",
            roles=(),
            energy=10,
            weights={"finance": 0.5},
            kpis=("cash_cents",),
            rule="hiring",
        )


def test_every_area_has_a_rule_known_kpis_and_roles() -> None:
    assert automation_problems(B, LOADED.game_data) == []
    for area in B.automation.areas.values():
        assert area.rule in RULES
        assert set(area.kpis) <= KPIS
        assert abs(sum(area.weights.values()) - 1) < 1e-9


def test_the_loader_names_an_area_without_a_rule() -> None:
    areas = dict(B.automation.areas)
    areas["hiring"] = areas["hiring"].model_copy(update={"rule": "nothing"})
    bad = B.model_copy(update={"automation": B.automation.model_copy(update={"areas": areas})})
    assert any("no rule 'nothing'" in p for p in automation_problems(bad, LOADED.game_data))


def test_lead_roles_are_never_the_founders_best_fit() -> None:
    from tst.sim.people.models import best_fit_role

    for role in ("engineering_manager", "research_scientist", "communications_manager"):
        assert not LOADED.game_data.role(role).founder_fit
    state = fresh_game(LOADED)
    founder = state.founder_of(1)
    assert founder is not None
    assert best_fit_role(founder.skills, LOADED.game_data)[0].founder_fit


# --- 2. Owners and eligibility (40.1) -------------------------------------------------------


def test_eligibility_for_each_owner_kind() -> None:
    state = _company(seat="coo")
    assert owners.owner_kind(state, 1, "support", SEAT, B) == "seat"  # the seat's area
    assert owners.owner_kind(state, 1, "hiring", LEAD, B) == "lead"  # a senior recruiter
    assert owners.owner_kind(state, 1, "treasury", LEAD, B) is None  # not a finance role
    junior = _company(lead_level="mid")
    assert owners.owner_kind(junior, 1, "hiring", LEAD, B) is None  # below senior
    from tst.sim.markets_public.models import Ceo

    ceo = replace(state, ceos=(Ceo(1, 1, LEAD, 0, ("cto",)),))
    assert owners.owner_kind(ceo, 1, "treasury", LEAD, B) == "ceo"  # the CEO, any area


def test_the_founder_can_never_own_an_area() -> None:
    state = _company()
    assert owners.owner_kind(state, 1, "hiring", FOUNDER, B) is None
    with pytest.raises(OrgRuleError, match="founder"):
        SetAreaOwnerApply(state, "hiring", FOUNDER)


def SetAreaOwnerApply(state: GameState, area: str, person: int):  # type: ignore[no-untyped-def]
    from tst.sim.automation.actions import set_area_owner

    return set_area_owner(
        state, SetAreaOwner(FOUNDER, area, person), B, LOADED.game_data, {(1, CASH): CASH_CENTS}
    )


def test_cant_automate_names_the_fix() -> None:
    state = _company()
    reason = owners.cant_automate(state, 1, "treasury", B, LOADED.game_data)
    assert reason == "hire a senior finance manager or fill the CFO seat"
    assert owners.cant_automate(state, 1, "hiring", B, LOADED.game_data) is None


def test_default_limit_is_two_percent_of_cash_rounded_down_with_a_floor() -> None:
    assert owners.default_limit(500_000_000, B) == 10_000_000  # 2% of $5M = $100,000
    assert owners.default_limit(123_456_789, B) == 2_500_000  # $24,691 -> $20,000 -> the floor
    assert owners.default_limit(260_000_000, B) == 5_000_000  # $52,000 -> $50,000
    assert owners.default_limit(0, B) == B.automation.min_limit_cents


def test_giving_and_taking_back_an_area_with_the_ego_rule() -> None:
    state = _company()
    lead = state.person(LEAD)
    state = with_person(state, replace(lead, personality={**lead.personality, "ego": 18.0}))
    out = SetAreaOwnerApply(state, "hiring", LEAD).state
    owner = out.area_owner(1, "hiring")
    assert owner is not None and owner.limit_cents == 10_000_000
    from tst.sim.automation.actions import take_back_area

    before = out.person_state(LEAD).morale
    back = take_back_area(out, TakeBackArea(FOUNDER, "hiring"), B)
    assert back.state.area_owner(1, "hiring") is None
    assert back.state.person_state(LEAD).morale == pytest.approx((before or 0) - 2)
    assert back.log[0].template == "area_taken_back"


def test_giving_a_seat_area_to_its_holder_gives_the_seat_authority() -> None:
    state = _company(seat="coo")
    out = SetAreaOwnerApply(state, "support", SEAT).state
    a = out.authority(1, "coo")
    assert a is not None and a.enabled


# --- 3. Limits and one-offs (40.2) ----------------------------------------------------------


def _priced(state: GameState, limited: bool = True) -> GameState:
    state = with_product(state, prices={"mid_market": 70_000}, customers={"mid_market": 10.0})
    seg = state.segments_of(state.company_products(1)[0].id)[0]
    return with_product_segment(state, replace(seg, capacity_limited=limited))


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    limit=st.integers(min_value=0, max_value=60_000_000),
    area=st.sampled_from(["hiring", "pricing", "marketing", "engineering", "support"]),
    seed=st.integers(min_value=1, max_value=10_000),
    leaving=st.booleans(),
)
def test_no_owner_commits_above_its_limit(limit: int, area: str, seed: int, leaving: bool) -> None:
    role = {
        "hiring": "recruiter",
        "pricing": "sales_manager",
        "marketing": "marketing_manager",
        "engineering": "engineering_manager",
        "support": "operations_manager",
    }[area]
    state = _priced(_company(lead_role=role, staff=3))
    if leaving:
        e = state.employment_of(10)
        assert e is not None
        state = with_employment(state, replace(e, status="notice", end_turn=state.turn + 1))
    state = _own(state, area, limit=limit)
    out, _, _, taken = _month(state, seed)
    total = 0
    for _, action in taken:
        cost = limits.commitment(state, action, B, LOADED.game_data)
        assert cost < limit or cost == 0
        assert not limits.is_one_off(state, 1, action, B)
        total += cost
    assert total <= B.automation.monthly_limit_mult * limit
    for d in out.area_decisions:
        if d.kind in ("decision", "mistake"):
            assert d.commitment_cents < limit or d.commitment_cents == 0


@settings(max_examples=30, deadline=None)
@given(
    kind=st.sampled_from(
        [
            BuildFacility(LEAD, "data_centre", "north_america", 100),
            StartRound(LEAD, "a", 500_000_000),
        ]
    ),
    limit=st.integers(min_value=0, max_value=10**12),
)
def test_no_one_off_runs_without_approval(kind: object, limit: int) -> None:
    state = _own(_company(lead_role="finance_manager"), "treasury", limit=limit)
    run = AutoRun(
        state=state,
        balances={(1, CASH): CASH_CENTS},
        rng=RngFactory(1),
        balance=B,
        data=LOADED.game_data,
        owner=state.area_owner(1, "treasury"),
    )
    assert not run.attempt(1, kind)  # type: ignore[arg-type]
    assert run.taken == []
    (proposal,) = run.state.pending_proposals(1)
    assert proposal.kind == "auto" and dict(proposal.params)["why"] == "it is a one-off"
    # the same move is not proposed twice while one waits
    run.propose(kind, 0, "it is a one-off")  # type: ignore[arg-type]
    assert len(run.state.pending_proposals(1)) == 1


def test_every_listed_one_off_kind_is_a_one_off() -> None:
    class _A:
        actor_id = LEAD

    state = _company()
    for k in ONE_OFF_ACTIONS:
        a = _A()
        a.kind = k  # type: ignore[attr-defined]
        assert limits.is_one_off(state, 1, a, B)  # type: ignore[arg-type]


def test_a_decision_at_the_limit_becomes_a_proposal_and_approving_runs_it() -> None:
    state = _priced(_company(lead_role="sales_manager"))
    product = state.company_products(1)[0].id
    state = _own(state, "pricing", limit=0)
    run = AutoRun(
        state=state,
        balances={(1, CASH): CASH_CENTS},
        rng=RngFactory(1),
        balance=B,
        data=LOADED.game_data,
        owner=state.area_owner(1, "pricing"),
    )
    run.propose(SetPrice(LEAD, product, "mid_market", 80_000), 1, "it is at or above the limit")
    (p,) = run.state.pending_proposals(1)
    assert json.loads(str(p.param("action"))) == action_payload(
        SetPrice(LEAD, product, "mid_market", 80_000)
    )
    from tst.sim.actions import apply_action

    out = apply_action(
        run.state, AnswerProposal(FOUNDER, p.id, True), RngFactory(1), B, LOADED.game_data,
        {(1, CASH): CASH_CENTS}, seq=1,
    )  # fmt: skip
    assert out.new_state.segments_of(product)[0].price_cents == 80_000
    assert next(x for x in out.new_state.proposals if x.id == p.id).status == "approved"
    assert proposal_action  # the old kinds keep their own path


def test_an_unanswered_proposal_expires_and_old_kinds_still_lapse() -> None:
    from tst.sim.turn import apply_player_decisions  # noqa: F401  (phase 1's rule)

    state = _own(_company(lead_role="finance_manager"), "treasury")
    run = AutoRun(
        state=state, balances={(1, CASH): CASH_CENTS}, rng=RngFactory(1), balance=B,
        data=LOADED.game_data, owner=state.area_owner(1, "treasury"),
    )  # fmt: skip
    run.propose(StartRound(LEAD, "a", 1), 0, "it is a one-off")
    (p,) = run.state.pending_proposals(1)
    assert int(p.param("expires_turn")) == state.turn + B.automation.proposal_months


# --- 4. Quality and workload (40.3) ---------------------------------------------------------


def _leaving(skill: float) -> GameState:
    state = _company(skill=skill, staff=1)
    e = state.employment_of(10)
    assert e is not None
    state = with_employment(state, replace(e, status="notice", end_turn=state.turn + 1))
    return _own(state, "hiring")


def test_the_same_seed_gives_the_same_decisions() -> None:
    state = _leaving(12.0)
    a, _, _, _ = _month(state, 7)
    b, _, _, _ = _month(state, 7)
    assert a.area_decisions == b.area_decisions and a.plans == b.plans


def test_a_weak_owner_makes_more_logged_mistakes() -> None:
    def mistakes(skill: float) -> int:
        state = _leaving(skill)
        n = 0
        for seed in range(1, 101):
            out, _, _, _ = _month(state, seed)
            n += sum(1 for d in out.area_decisions if d.kind == "mistake")
        return n

    weak, strong = mistakes(8.0), mistakes(15.0)
    assert weak > strong
    assert weak >= 2 * max(strong, 1)


def test_an_owner_without_energy_gets_no_time() -> None:
    state = _company(lead_role="operations_manager")
    for i, area in enumerate(("hiring", "support", "events", "engineering")):
        if owners.owner_kind(state, 1, area, LEAD, B) is None:
            continue
        state = with_area_owner(state, AreaOwner(1, area, LEAD, LIMIT, i, 0))
    big = {a: B.automation.areas[a].energy for a in ("hiring", "support", "events")}
    assert sum(big.values()) <= B.automation.owner_energy  # 20 + 20 + 15 fits in 100
    lean = B.model_copy(update={"automation": B.automation.model_copy(update={"owner_energy": 30})})
    out, _, _, _ = automation_month(
        state, RngFactory(1), lean, LOADED.game_data, {(1, CASH): CASH_CENTS}
    )
    kinds = {(d.area, d.kind) for d in out.area_decisions}
    assert ("support", "no_time") in kinds and ("hiring", "no_time") not in kinds


def test_quality_follows_the_true_area_score() -> None:
    weak = owners.true_area_score(_company(skill=8.0), 1, "hiring", LEAD, B)
    strong = owners.true_area_score(_company(skill=15.0), 1, "hiring", LEAD, B)
    q = B.automation.quality
    assert decision_quality(weak, q) < decision_quality(strong, q)


# --- 5. The new area rules (40.6) -----------------------------------------------------------


def _run_for(state: GameState, area: str, seed: int) -> AutoRun:
    o = state.area_owner(1, area)
    return AutoRun(
        state=state, balances={(1, CASH): CASH_CENTS}, rng=RngFactory(seed), balance=B,
        data=LOADED.game_data, owner=o, area_index=owners.area_index(B, area),
    )  # fmt: skip


def _seed(state: GameState, area: str, right: bool) -> int:
    score = owners.true_area_score(state, 1, area, LEAD, B)
    p = decision_quality(score, B.automation.quality)
    from tst.sim.automation.run import automation_draws

    for seed in range(1, 500):
        u = float(
            automation_draws(
                RngFactory(seed), state.turn, LEAD, owners.area_index(B, area), 0
            ).random()
        )
        if (u < p) == right:
            return seed
    raise AssertionError("no seed")


def test_pricing_steps_a_supply_limited_self_serve_price_up_and_a_mistake_holds_it() -> None:
    state = with_product(_company(lead_role="sales_manager"), prices={"smb": 4000})
    seg = state.segments_of(state.company_products(1)[0].id)[0]
    state = with_product_segment(state, replace(seg, capacity_limited=True))
    state = _own(state, "pricing")
    run = _run_for(state, "pricing", _seed(state, "pricing", True))
    rules.pricing(run, state.area_owner(1, "pricing"), LOADED.game_data)  # type: ignore[arg-type]
    assert run.state.segments_of(seg.product_id)[0].price_cents == 4200  # +5%
    run = _run_for(state, "pricing", _seed(state, "pricing", False))
    rules.pricing(run, state.area_owner(1, "pricing"), LOADED.game_data)  # type: ignore[arg-type]
    assert run.state.segments_of(seg.product_id)[0].price_cents == 4000
    assert [d[0] for d in run.decisions] == ["mistake"]


def test_pricing_waits_for_a_quarter_start() -> None:
    state = with_product(_company(lead_role="sales_manager"), prices={"smb": 4000})
    state = _own(replace(state, turn=1), "pricing")
    run = _run_for(state, "pricing", 1)
    rules.pricing(run, state.area_owner(1, "pricing"), LOADED.game_data)  # type: ignore[arg-type]
    assert run.decisions == []


def test_research_stops_a_project_no_live_product_draws_on() -> None:
    from tst.sim.research.models import ResearchProject

    state = _own(_company(lead_role="research_scientist"), "research")
    state = with_product(state)  # b2b_saas
    domains = [
        d.key
        for d in LOADED.game_data.tech.domains  # type: ignore[union-attr]
        if "b2b_saas"
        not in __import__("tst.sim.research.levels", fromlist=["feeds"]).feeds(
            LOADED.game_data, d.key
        )
    ]
    from tst.sim.org.models import OrgUnit

    unit = OrgUnit(1, 1, "team", "Lab", None, None, None, 0)
    state = replace(
        state,
        units=(unit,),
        research_projects=(ResearchProject(1, 1, domains[0], 1, 0),),
    )
    run = _run_for(replace(state, turn=1), "research", 1)
    rules.research(run, state.area_owner(1, "research"), LOADED.game_data)  # type: ignore[arg-type]
    assert not run.state.active_projects(1)
    assert run.decisions and run.decisions[0][0] == "decision"


def test_regions_goes_ahead_under_the_limit_and_waits_above_it() -> None:
    state = with_product(_company(lead_role="sales_manager"), customers={"smb": 500.0})
    for limit, went in ((10**12, True), (1, False)):
        s = _own(state, "regions", limit=limit)
        run = _run_for(s, "regions", _seed(s, "regions", True))
        rules.regions(run, s.area_owner(1, "regions"), LOADED.game_data)  # type: ignore[arg-type]
        kinds = [d[0] for d in run.decisions]
        if not kinds:
            pytest.skip("no region candidate in this fixture")
        assert kinds == (["decision"] if went else ["proposal"])
        statuses = {p.status for p in run.state.pitches}
        assert statuses == ({"auto_approved"} if went else {"pending"})


def test_press_takes_the_measured_answer_unless_bold_claims_are_allowed() -> None:
    state = _own(_company(lead_role="communications_manager"), "press")
    event = _press_event()
    owner = state.area_owner(1, "press")
    assert owner is not None
    assert ranked_choices(state, event, owner, B)[0].key == "A"  # measured
    bold = replace(owner, allow_bold=True)
    grown = with_company(state, replace(state.player, mrr_history=(1, 2, 3, 4)))
    assert ranked_choices(grown, event, bold, B)[0].key == "B"
    assert ranked_choices(grown, event, owner, B)[1].key == "B"  # the mistake: bolder


def _press_event(severity: str = "minor", category: str = "press") -> GameEvent:
    def tone(stat: str) -> tuple[Effect, ...]:
        return (Effect("press_step", "company", stat=stat),)

    return GameEvent(
        id=99, company_id=1, turn=0, template_id="press_interview", category=category,
        severity=severity, trigger="t", strength=1.0, status="open", title="Interview",
        choices=(
            EventChoice("A", "Measured", tone("measured")),
            EventChoice("B", "Bold", tone("bold")),
            EventChoice("C", "No comment", tone("deflect")),
        ),
    )  # type: ignore[arg-type]  # fmt: skip


def test_the_events_rule_picks_the_best_shown_effect_ties_to_caution() -> None:
    state = _own(_company(lead_role="operations_manager"), "support")
    owner = state.area_owner(1, "support")
    assert owner is not None
    event = replace(
        _press_event(category="operations"),
        choices=(
            EventChoice("A", "Spend", (Effect("cash_delta", "company", -5_000_000),)),
            EventChoice("B", "Morale", (Effect("morale_delta", "company", 3),)),
            EventChoice("C", "Nothing", (), do_nothing=True),
        ),
    )
    ranked = [c.key for c in ranked_choices(state, event, owner, B)]
    assert ranked[0] == "B" and ranked[1] == "C"


# --- 6. Routine events (40.5) ---------------------------------------------------------------


def test_a_routine_event_is_answered_by_its_owner_and_logged() -> None:
    state = _own(_company(lead_role="communications_manager"), "press")
    state = with_event(state, _press_event())
    out, _, logs = answer_routine(
        state, RngFactory(1), B, LOADED.game_data, {(1, CASH): CASH_CENTS}
    )
    event = next(e for e in out.events if e.id == 99)
    assert event.status == "auto" and event.chosen in ("A", "B")
    assert any(d.ref_id == 99 for d in out.area_decisions)
    assert all(i.in_digest for i in logs)


@pytest.mark.parametrize("severity", ["critical"])
def test_a_critical_event_is_never_resolved_by_automation(severity: str) -> None:
    state = _own(_company(lead_role="communications_manager"), "press")
    state = with_event(state, _press_event(severity))
    assert owner_for(state, state.events[-1], B) is None
    out, entries, logs = answer_routine(
        state, RngFactory(1), B, LOADED.game_data, {(1, CASH): CASH_CENTS}
    )
    assert next(e for e in out.events if e.id == 99).status == "open"
    assert entries == () and logs == ()


def test_answer_events_off_leaves_the_event_to_the_player() -> None:
    state = _own(_company(lead_role="communications_manager"), "press")
    owner = state.area_owner(1, "press")
    assert owner is not None
    state = with_event(with_area_owner(state, replace(owner, answer_events=False)), _press_event())
    assert owner_for(state, state.events[-1], B) is None


# --- 7. The digest (40.4, 40.11) ------------------------------------------------------------


def test_the_digest_reports_the_month_without_a_hidden_value() -> None:
    state = _leaving(13.37)  # an odd true score, easy to spot
    out, _, _, _ = _month(state, 3)
    d = digest.build(out, state.turn, B, LOADED.game_data)
    assert d is not None and d.areas[0].area == "hiring"
    text = digest.body_text(d) + "\n".join(digest.facts(d))
    score = owners.true_area_score(state, 1, "hiring", LEAD, B)
    p = decision_quality(score, B.automation.quality)
    for hidden in (f"{score:.2f}", f"{score:.1f}", f"{p:.2f}", f"{p:.0%}", f"{p * 100:.1f}"):
        assert hidden not in text
    item = digest.digest_item(out, state.turn, B, LOADED.game_data)
    assert item is not None and item.template == "digest" and item.link_kind == "automation"


def test_no_digest_without_an_automated_area() -> None:
    assert digest.build(_company(), 0, B, LOADED.game_data) is None


# --- 40.9: nothing moves without owners -----------------------------------------------------


def test_a_company_with_no_owners_is_returned_untouched() -> None:
    state = _leaving(12.0)
    state = replace(state, area_owners=())
    out, entries, logs, taken = _month(state)
    assert out is state and entries == () and logs == () and taken == ()
    routine, e2, l2 = answer_routine(state, RngFactory(1), B, LOADED.game_data, {})
    assert routine is state and e2 == () and l2 == ()


def test_settings_change_only_what_they_name() -> None:
    from tst.sim.automation.actions import set_area_settings

    state = _own(_company(), "hiring")
    out = set_area_settings(state, SetAreaSettings(FOUNDER, "hiring", limit_cents=7), B).state
    owner = out.area_owner(1, "hiring")
    assert owner is not None and owner.limit_cents == 7 and owner.answer_events
