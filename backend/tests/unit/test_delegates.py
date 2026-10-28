"""Delegated hiring in phase 2 (formulas.md 13.10, ADR-0015)."""

from __future__ import annotations

from dataclasses import replace
from statistics import mean

import pytest

from tests.helpers import fresh_game, make_person, with_candidates, with_employee
from tests.unit.test_hiring_phases import Game
from tst.loader import LoadedData
from tst.sim.actions import (
    ClosePlan,
    CloseSearch,
    CreatePlan,
    CreateUnit,
    Interview,
    MakeOffer,
    OpenSearch,
    Scout,
)
from tst.sim.data_models import GameData
from tst.sim.org.delegates import (
    activity_text,
    known_score,
    plan_offer_salary,
    ranked_candidates,
    run_delegates,
)
from tst.sim.org.models import PlanActivity
from tst.sim.people.models import current_ability
from tst.sim.people.reveal import revealed_range
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

FOUNDER = 1
RECRUITER = 2


def with_recruiter(
    loaded: LoadedData, state: GameState, judgment: float = 15, recruiting: float = 15
) -> GameState:
    person = make_person(loaded, RECRUITER, "recruiter", "senior")
    person = replace(
        person,
        skills=person.skills.updated({"judgment_of_talent": judgment, "recruiting": recruiting}),
    )
    return with_employee(loaded, state, person, 10_000_000)


def recruiter_game(loaded: LoadedData, seed: int = 3, judgment: float = 15) -> Game:
    game = Game(loaded, with_recruiter(loaded, fresh_game(loaded, seed), judgment))
    game.state = replace(game.state, next_ids=replace(game.state.next_ids, person=3))
    return game


def hires(state: GameState) -> list[int]:
    return [
        e.person_id
        for e in state.staff(1)
        if e.person_id not in (FOUNDER, RECRUITER) and e.status == "active"
    ]


def test_recruiter_plan_fills_four_hires_within_four_turns(loaded: LoadedData) -> None:
    """Acceptance: four hires in four turns, none of it on the founder's energy."""
    game = recruiter_game(loaded)
    game.act(CreateUnit(FOUNDER, "team", "Platform"))
    game.act(CreatePlan(FOUNDER, RECRUITER, "software_engineer", 4, "any", 11_000, 0, 1))
    assert game.state.person_state(FOUNDER).energy == 56
    for _ in range(4):
        before = game.state.person_state(FOUNDER).energy
        state, _, _, _ = run_delegates(
            game.state, game.rng, loaded.balance, loaded.game_data, game.balances
        )
        assert state.person_state(FOUNDER).energy == before  # phase 2 never spends it
        result = game.turn()
        assert all(action.actor_id == RECRUITER for _, action in result.delegate_actions)
    hired = hires(game.state)
    assert len(hired) == 4
    assert all(game.state.employment_of(p).unit_id == 1 for p in hired)  # type: ignore[union-attr]
    plan = game.state.plans[0]
    assert (plan.hired, plan.status) == (4, "filled")
    kinds = [i.template for r in game.results for i in r.log_items]
    assert "plan_filled" in kinds and "plan_activity" in kinds


def _role_skill_width(state: GameState, data: GameData, role: str) -> list[float]:
    """Displayed range widths (max - min) of the role's skills, for every person of that role
    the company has a knowledge record for (candidates and hires alike)."""
    skills = (*data.role(role).primary, *data.role(role).secondary)
    widths = []
    for reveal in state.reveals:
        person = state.person(reveal.person_id)
        if reveal.observer_company_id != 1 or person.role != role:
            continue
        for skill in skills:
            lo, hi = revealed_range(person, reveal, skill)
            widths.append(float(hi - lo))
    return widths


def test_better_judgment_narrows_ranges_faster(loaded: LoadedData) -> None:
    """Acceptance (revised): over 200 seeded runs, a judgment-16 recruiter's plan leaves the
    company with narrower ranges on the candidates it worked than a judgment-6 recruiter's
    (same seeds, so the same candidate pools).

    The hires' mean true CA is printed too. The gap is about 0.1 CA: every candidate gets
    interviewed and scouted either way, and ranking by role-skill midpoints is already close
    to the truth, so judgment barely changes who is hired (brief follow-up).
    """
    widths: dict[float, list[float]] = {16: [], 6: []}
    cas: dict[float, list[float]] = {16: [], 6: []}
    for seed in range(1, 201):
        for judgment in (16, 6):
            game = recruiter_game(loaded, seed, judgment)
            game.act(CreatePlan(FOUNDER, RECRUITER, "software_engineer", 2, "job_post", 11_000))
            for _ in range(3):
                game.turn()
            widths[judgment] += _role_skill_width(game.state, loaded.game_data, "software_engineer")
            cas[judgment] += [
                current_ability(game.state.person(p), loaded.game_data) for p in hires(game.state)
            ]
    print(
        f"mean role-skill range width: judgment 16 {mean(widths[16]):.2f}, "
        f"judgment 6 {mean(widths[6]):.2f}; mean CA of hires: judgment 16 "
        f"{mean(cas[16]):.2f} ({len(cas[16])}), judgment 6 {mean(cas[6]):.2f} "
        f"({len(cas[6])}), gap {mean(cas[16]) - mean(cas[6]):+.2f}"
    )
    assert mean(widths[16]) < mean(widths[6])


def test_first_turn_opens_a_job_post_for_channel_any(loaded: LoadedData) -> None:
    game = recruiter_game(loaded)
    game.act(CreatePlan(FOUNDER, RECRUITER, "designer", 1, "any", 10_000))
    result = game.turn()
    assert [a for _, a in result.delegate_actions] == [
        OpenSearch(RECRUITER, "designer", "job_post", plan_id=1)
    ]
    assert game.state.plans[0].last_activity == PlanActivity(turn=0, searches=1)
    # No second search while one is open for the role.
    result = game.turn()
    assert not any(isinstance(a, OpenSearch) for _, a in result.delegate_actions)


def test_delegate_steps_on_a_known_pool(loaded: LoadedData) -> None:
    state = with_candidates(loaded, with_recruiter(loaded, fresh_game(loaded)), 15)
    game = Game(loaded, state)
    game.act(CreatePlan(FOUNDER, RECRUITER, "software_engineer", 2, "network", 11_000, 5))
    ranked = ranked_candidates(game.state, 1, "software_engineer", loaded.game_data)
    scores = [known_score(game.state, 1, c, loaded.game_data) for c in ranked]
    assert scores == sorted(scores, reverse=True)
    state, _, logs, taken = run_delegates(
        game.state, game.rng, loaded.balance, loaded.game_data, game.balances
    )
    actions = [a for _, a in taken]
    interviews = [a for a in actions if isinstance(a, Interview)]
    # 100 energy: interview while more than 20 would remain (9 x 8 = 72), then scout (20).
    assert len(interviews) == 9
    assert [a.candidate_id for a in interviews] == [c.person_id for c in ranked[:9]]
    assert actions[9] == Scout(RECRUITER, "software_engineer")
    offers = [a for a in actions if isinstance(a, MakeOffer)]
    assert len(offers) == 2 and all(o.plan_id == 1 and o.equity_bp == 5 for o in offers)
    for offer in offers:
        ask = state.person(offer.candidate_id).salary_expectation_cents or 0
        assert offer.salary_cents == plan_offer_salary(ask, 11_000)
        assert state.candidate(offer.candidate_id).interviewed_turn == 0  # type: ignore[union-attr]
    assert state.person_state(RECRUITER).energy == 100 - 72 - 20
    assert [i.template for i in logs if i.template == "plan_activity"] == ["plan_activity"]
    summary = next(i for i in logs if i.template == "plan_activity")
    assert dict(summary.params)["activity"] == (
        "interviewed 9 software engineers, scouted 15 candidates and made 2 offers"
    )


def test_delegate_randomness_is_keyed_per_delegate(loaded: LoadedData) -> None:
    """The same plan gives the same actions; the player's stream is not used."""
    state = with_candidates(loaded, with_recruiter(loaded, fresh_game(loaded)), 6)
    game = Game(loaded, state)
    game.act(CreatePlan(FOUNDER, RECRUITER, "software_engineer", 1, "network", 11_000))
    rng = RngFactory(state.save_meta.master_seed)
    first = run_delegates(game.state, rng, loaded.balance, loaded.game_data, game.balances)
    second = run_delegates(game.state, rng, loaded.balance, loaded.game_data, game.balances)
    assert first == second


def test_paused_and_filled_plans_do_nothing(loaded: LoadedData) -> None:
    state = with_candidates(loaded, with_recruiter(loaded, fresh_game(loaded)), 4)
    game = Game(loaded, state)
    game.act(CreatePlan(FOUNDER, RECRUITER, "software_engineer", 1, "network", 11_000))
    for status in ("paused", "filled"):
        plans = (replace(game.state.plans[0], status=status),)
        _, _, logs, taken = run_delegates(
            replace(game.state, plans=plans),
            game.rng,
            loaded.balance,
            loaded.game_data,
            game.balances,
        )
        assert taken == () and logs == ()


def test_short_energy_skips_interviews(loaded: LoadedData) -> None:
    state = with_candidates(loaded, with_recruiter(loaded, fresh_game(loaded)), 4)
    game = Game(loaded, state)
    game.act(CreatePlan(FOUNDER, RECRUITER, "software_engineer", 1, "network", 11_000))
    tired = replace(
        game.state,
        person_states=tuple(
            replace(ps, energy=26) if ps.person_id == RECRUITER else ps
            for ps in game.state.person_states
        ),
    )
    _, _, _, taken = run_delegates(tired, game.rng, loaded.balance, loaded.game_data, {})
    assert [a.kind for _, a in taken] == ["scout"]  # 26 - 6 = 20 is not more than 20


def test_energy_resets_for_delegates(loaded: LoadedData) -> None:
    game = recruiter_game(loaded)
    game.act(CreatePlan(FOUNDER, RECRUITER, "designer", 1, "any", 10_000))
    game.turn()
    assert game.state.person_state(RECRUITER).energy == loaded.balance.delegates.energy_per_month
    assert game.state.person_state(FOUNDER).energy == loaded.balance.founder.energy_per_month


@pytest.mark.parametrize(
    ("activity", "text"),
    [
        (PlanActivity(0, searches=1), "opened a new search"),
        (PlanActivity(0, interviews=1, offers=1), "interviewed 1 designer and made 1 offer"),
        (
            PlanActivity(0, 1, 4, 7, 2),
            "opened a new search, interviewed 4 designers, scouted 7 candidates and made 2 offers",
        ),
    ],
)
def test_activity_text(activity: PlanActivity, text: str) -> None:
    assert activity_text(activity, "designer") == text


# --- Closing a plan's job posts (13.10) -------------------------------------------------------


def _job_posts(state: GameState) -> list[tuple[int, int | None, str]]:
    return [(s.id, s.plan_id, s.status) for s in state.searches if s.channel == "job_post"]


def test_filled_plan_delegate_closes_its_job_post(loaded: LoadedData) -> None:
    game = recruiter_game(loaded)
    game.act(OpenSearch(FOUNDER, "software_engineer", "job_post"))  # the player's own
    game.act(CreatePlan(FOUNDER, RECRUITER, "designer", 1, "any", 12_000))
    game.turn()
    assert _job_posts(game.state) == [(1, None, "open"), (2, 1, "open")]
    closed = None
    for _ in range(4):
        result = game.turn()
        closes = [a for _, a in result.delegate_actions if isinstance(a, CloseSearch)]
        if closes:
            closed = closes
            break
    assert game.state.plans[0].status == "filled"
    assert closed == [CloseSearch(RECRUITER, 2)]
    assert [s.id for s in game.state.open_searches(1)] == [1]  # the player's stays open


def test_closing_a_plan_closes_its_job_post(loaded: LoadedData) -> None:
    game = recruiter_game(loaded)
    game.act(CreatePlan(FOUNDER, RECRUITER, "designer", 3, "any", 10_000))
    game.turn()
    assert _job_posts(game.state) == [(1, 1, "open")]
    game.act(ClosePlan(FOUNDER, 1))
    assert game.state.open_searches(1) == ()


def test_job_post_passes_to_another_open_plan_for_the_role(loaded: LoadedData) -> None:
    game = recruiter_game(loaded)
    other = make_person(loaded, 3, "recruiter", "mid")
    game.state = with_employee(loaded, game.state, other, 9_000_000)
    game.state = replace(game.state, next_ids=replace(game.state.next_ids, person=4))
    game.act(CreatePlan(FOUNDER, RECRUITER, "designer", 3, "any", 10_000))
    game.act(CreatePlan(FOUNDER, 3, "designer", 3, "any", 10_000))
    game.turn()  # plan 1 opens the job post; plan 2 sees it open and opens nothing
    assert _job_posts(game.state) == [(1, 1, "open")]
    game.act(ClosePlan(FOUNDER, 1))
    assert _job_posts(game.state) == [(1, 2, "open")]  # plan 2 uses it, so it stays
    game.act(ClosePlan(FOUNDER, 2))
    assert _job_posts(game.state) == [(1, 2, "closed")]
