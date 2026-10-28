"""M2b backend slice: the PA scout factor (formulas.md 4), the founder's own PA range, and
plan focus "potential" (13.10), including the comparative potential target."""

from __future__ import annotations

from dataclasses import replace
from statistics import mean

import pytest

from tests.helpers import fresh_game, with_candidates
from tests.unit.test_delegates import FOUNDER, RECRUITER, hires, recruiter_game, with_recruiter
from tst.loader import LoadedData
from tst.sim.actions import CreatePlan, UpdatePlan, action_from_payload, action_payload
from tst.sim.errors import InvalidActionError
from tst.sim.org.delegates import activity_text, known_potential, known_score, ranked_candidates
from tst.sim.org.models import PlanActivity
from tst.sim.people.formulas import displayed_range, narrow_pa, pa_scout_factor, potential_phrase
from tst.sim.people.models import PA_KEY
from tst.sim.people.reveal import apply_knowledge_action
from tst.sim.state import with_person

POTENTIAL_RUNS = 400
POTENTIAL_TARGET = 3.0  # PA points, formulas.md 13.10 (revised)


# --- Section 4: PA scout factor and worked example -----------------------------------------


@pytest.mark.parametrize(
    ("judgment", "factor"), [(1, 0.1), (6, 0.375), (12, 0.75), (16, 1.0), (20, 1.0)]
)
def test_pa_scout_factor(loaded: LoadedData, judgment: float, factor: float) -> None:
    assert pa_scout_factor(judgment, loaded.balance.reveal) == pytest.approx(factor)


def test_pa_worked_example(loaded: LoadedData) -> None:
    """formulas.md section 4, PA row (M4c values): true PA 140, offset +0.2, judgment 12."""
    r = loaded.balance.reveal
    hw = r.initial_hw.pa
    rows = [(hw, (60, 193))]
    hw = narrow_pa(hw, r.pa_strength["job_post_screen"], 12, r)
    rows.append((hw, (63, 191)))
    hw = narrow_pa(hw, r.pa_strength["interview"], 12, r)
    rows.append((hw, (75, 184)))
    for _ in range(6):
        hw = narrow_pa(hw, r.pa_strength["employed_month"], 12, r)
    rows.append((hw, (95, 170)))
    expected_hw = [66.0, 63.52, 54.0, 37.25]
    for (got, shown), want in zip(rows, expected_hw, strict=True):
        assert got == pytest.approx(want, abs=5e-3)
        assert displayed_range(140, got, 0.2, 10, 200) == shown
    assert potential_phrase(75, 184, r.pa_phrase_bounds) == "decent to outstanding"


def test_pa_uses_its_own_strength_and_factor(loaded: LoadedData) -> None:
    state = with_candidates(loaded, fresh_game(loaded), 1)
    reveal = state.reveal(1, state.candidates[0].person_id)
    assert reveal is not None
    after = apply_knowledge_action(
        reveal,
        "interview",
        6,
        loaded.balance,
        turn=0,
        skill_keys=frozenset(loaded.game_data.skill_keys),
    )
    r = loaded.balance.reveal
    assert after.record(PA_KEY).hw == pytest.approx(
        reveal.record(PA_KEY).hw * (1 - r.pa_strength["interview"] * 6 / r.pa_scout_divisor)
    )
    skill = loaded.game_data.skill_keys[0]
    assert after.record(skill).hw == pytest.approx(
        reveal.record(skill).hw * (1 - r.strength["interview"] * (0.5 + 6 / 40))
    )


def test_founder_pa_range_stays_at_forty(loaded: LoadedData) -> None:
    state = with_candidates(loaded, fresh_game(loaded), 1)
    founder = state.reveal(1, FOUNDER)
    stranger = state.reveal(1, state.candidates[0].person_id)
    assert founder is not None and stranger is not None
    assert founder.record(PA_KEY).hw == loaded.balance.reveal.founder_pa_hw == 40
    assert stranger.record(PA_KEY).hw == loaded.balance.reveal.initial_hw.pa == 66


# --- Section 13.10: focus potential --------------------------------------------------------


def test_potential_focus_ranks_juniors_and_mids_by_known_pa(loaded: LoadedData) -> None:
    state = with_recruiter(loaded, fresh_game(loaded))
    state = replace(state, next_ids=replace(state.next_ids, person=3))
    state = with_candidates(loaded, state, 8)
    levels = ["junior", "mid", "senior", "staff", "junior", "mid", "junior", "senior"]
    for candidate, level in zip(state.candidates, levels, strict=True):
        state = with_person(state, replace(state.person(candidate.person_id), level=level))
    ranked = ranked_candidates(state, 1, "software_engineer", loaded.game_data, "potential")
    assert {state.person(c.person_id).level for c in ranked} <= {"junior", "mid"}
    assert len(ranked) == 5
    keys = [
        (-known_potential(state, 1, c), -known_score(state, 1, c, loaded.game_data), c.person_id)
        for c in ranked
    ]
    assert keys == sorted(keys)
    assert len(ranked_candidates(state, 1, "software_engineer", loaded.game_data)) == 8


def test_potential_plan_summary_says_so(loaded: LoadedData) -> None:
    game = recruiter_game(loaded)
    game.act(
        CreatePlan(
            FOUNDER, RECRUITER, "software_engineer", 2, "job_post", 11_000, focus="potential"
        )
    )
    assert game.state.plans[0].focus == "potential"
    game.turn()
    game.turn()
    summaries = [
        dict(i.params)["activity"]
        for r in game.results
        for i in r.log_items
        if i.template == "plan_activity"
    ]
    assert summaries and all(s.endswith(", favouring potential") for s in summaries)
    assert activity_text(PlanActivity(0, offers=1), "designer", "potential") == (
        "made 1 offer, favouring potential"
    )


def test_focus_is_validated_and_round_trips(loaded: LoadedData) -> None:
    game = recruiter_game(loaded)
    with pytest.raises(InvalidActionError, match="unknown focus"):
        game.act(CreatePlan(FOUNDER, RECRUITER, "designer", 1, "any", 10_000, focus="hunch"))  # type: ignore[arg-type]
    game.act(CreatePlan(FOUNDER, RECRUITER, "designer", 1, "any", 10_000))
    update = UpdatePlan(FOUNDER, 1, RECRUITER, "designer", 1, "any", 10_000, 0, None, "potential")
    game.act(update)
    assert game.state.plans[0].focus == "potential"
    assert action_from_payload(action_payload(update)) == update
    # An M2a log row without a focus still loads, as "current".
    old = action_payload(update)
    del old["focus"]
    assert action_from_payload(old).focus == "current"  # type: ignore[union-attr]


def test_judgment_spots_potential(loaded: LoadedData) -> None:
    """Acceptance (formulas.md 13.10, revised): over 400 seeded runs of a potential plan for 2
    software engineers, a judgment-16 recruiter's hires have a mean true PA at least 3 points
    higher than a judgment-6 recruiter's on the same seeds. The current-focus CA gap is in
    test_delegates.py::test_better_judgment_narrows_ranges_faster."""
    pas: dict[int, list[float]] = {16: [], 6: []}
    for seed in range(1, POTENTIAL_RUNS + 1):
        for judgment in (16, 6):
            game = recruiter_game(loaded, seed, judgment)
            game.act(
                CreatePlan(
                    FOUNDER,
                    RECRUITER,
                    "software_engineer",
                    2,
                    "job_post",
                    11_000,
                    focus="potential",
                )
            )
            for _ in range(3):
                game.turn()
            pas[judgment] += [game.state.person(p).potential_ability for p in hires(game.state)]
    gap = mean(pas[16]) - mean(pas[6])
    print(
        f"mean true PA of potential-plan hires: judgment 16 {mean(pas[16]):.2f} "
        f"({len(pas[16])}), judgment 6 {mean(pas[6]):.2f} ({len(pas[6])}), gap {gap:+.2f}"
    )
    assert gap >= POTENTIAL_TARGET
