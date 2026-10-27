"""Turn phases for hiring, payroll, morale and departures (formulas.md sections 6-10)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, make_person, mark_interviewed, with_candidates, with_employee
from tst.loader import LoadedData
from tst.sim.actions import Action, MakeOffer, OpenSearch, apply_action
from tst.sim.decisions import Decisions
from tst.sim.hiring import phases
from tst.sim.hiring.formulas import acceptance_probability, offer_score
from tst.sim.hiring.models import Offer, PersonState
from tst.sim.ledger import CASH, apply_entries
from tst.sim.log import LogItem
from tst.sim.people.models import PA_KEY
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_offer, with_person_state
from tst.sim.turn import TurnResult, advance_turn

START_CASH = 40_000_000  # ex-big-tech founders


class Game:
    """Drives a state through actions and turns in memory, tracking ledger balances."""

    def __init__(self, loaded: LoadedData, state: GameState, cash: int = START_CASH) -> None:
        self.loaded = loaded
        self.state = state
        self.balances: dict[tuple[int, str], int] = {(1, CASH): cash}
        self.seq = 0
        self.results: list[TurnResult] = []
        self.action_logs: list[LogItem] = []

    @property
    def rng(self) -> RngFactory:
        return RngFactory(self.state.save_meta.master_seed)

    def act(self, action: Action) -> None:
        self.seq += 1
        out = apply_action(
            self.state,
            action,
            self.rng,
            self.loaded.balance,
            self.loaded.game_data,
            self.balances,
            seq=self.seq,
        )
        self.state = out.new_state
        self.balances = apply_entries(self.balances, out.ledger_entries)
        self.action_logs += out.log_items

    def turn(self) -> TurnResult:
        result = advance_turn(
            self.state,
            Decisions(),
            self.rng,
            self.loaded.balance,
            self.loaded.game_data,
            self.balances,
        )
        self.balances = apply_entries(self.balances, result.ledger_entries)
        self.state = live(result.new_state)
        self.seq = 0
        self.results.append(result)
        return result

    @property
    def cash(self) -> int:
        return self.balances.get((1, CASH), 0)


def live(state: GameState) -> GameState:
    """What a reload keeps: staff, open candidates and searches, pending offers."""
    staff = {e.person_id for e in state.employments if e.counts_as_staff}
    open_c = {c.person_id for c in state.candidates if c.status == "open"}
    keep = staff | open_c
    return replace(
        state,
        people=tuple(p for p in state.people if p.id in keep),
        employments=tuple(e for e in state.employments if e.counts_as_staff),
        candidates=tuple(c for c in state.candidates if c.status == "open"),
        searches=tuple(s for s in state.searches if s.status == "open"),
        offers=tuple(o for o in state.offers if o.status == "pending"),
        reveals=tuple(r for r in state.reveals if r.person_id in keep),
        person_states=tuple(p for p in state.person_states if p.person_id in keep),
    )


# --- Phase 12: batches, expiry; energy reset --------------------------------------------------


@pytest.mark.parametrize(
    ("channel", "lo", "hi", "stays_open"),
    [("network", 2, 5, False), ("job_post", 6, 10, True), ("recruiter", 4, 6, False)],
)
def test_batches_arrive_in_phase_12(
    loaded: LoadedData, channel: str, lo: int, hi: int, stays_open: bool
) -> None:
    for seed in range(1, 8):
        game = Game(loaded, fresh_game(loaded, seed))
        game.act(OpenSearch(1, "software_engineer", channel))  # type: ignore[arg-type]
        result = game.turn()
        candidates = game.state.candidates
        assert lo <= len(candidates) <= hi
        assert all(c.channel == channel and c.created_turn == 0 for c in candidates)
        assert all(c.expires_turn == 3 for c in candidates)
        assert (len(game.state.searches) == 1) is stays_open
        arrived = [i for i in result.log_items if i.template == "candidates_arrived"]
        assert len(arrived) == 1 and arrived[0].link_kind == "search"
        for c in candidates:
            person = game.state.person(c.person_id)
            assert person.role == "software_engineer" and person.level in (
                "junior",
                "mid",
                "senior",
                "staff",
            )
            reveal = game.state.reveal(1, c.person_id)
            assert reveal is not None
            assert reveal.record("software_engineering").hw < loaded.balance.reveal.initial_hw.skill
            assert (reveal.profile_revealed_turn == 0) is (channel == "network")


def test_network_bonus_for_a_sociable_actor(loaded: LoadedData) -> None:
    sizes = {}
    for sociability in (14.0, 15.0):
        state = fresh_game(loaded, 4)
        founder = state.people[0]
        state = replace(
            state,
            people=(
                replace(
                    founder, personality=founder.personality.updated({"sociability": sociability})
                ),
            ),
        )
        game = Game(loaded, state)
        game.act(OpenSearch(1, "designer", "network"))
        game.turn()
        sizes[sociability] = len(game.state.candidates)
    assert sizes[15.0] == sizes[14.0] + 1  # same draws, plus the bonus


def test_candidates_expire_and_energy_resets(loaded: LoadedData) -> None:
    game = Game(loaded, fresh_game(loaded))
    game.act(OpenSearch(1, "software_engineer", "network"))
    assert game.state.person_state(1).energy == 90
    game.turn()
    assert game.state.person_state(1).energy == 100
    first_batch = {c.person_id for c in game.state.candidates}
    assert first_batch
    for _ in range(2):
        game.turn()
    assert {c.person_id for c in game.state.candidates} == first_batch  # turns 1 and 2
    game.turn()  # phase 12 of turn 3: they leave
    assert game.state.candidates == ()


# --- Phase 1: offers --------------------------------------------------------------------------


def _offer_all(game: Game, ratio: float, equity: int = 0) -> None:
    game.state = mark_interviewed(game.state)  # offers need an interview (ADR-0016)
    for c in game.state.candidates:
        expectation = game.state.person(c.person_id).salary_expectation_cents or 0
        game.act(MakeOffer(1, c.person_id, round(expectation * ratio), equity))


def test_accepted_offer_hires_and_moves_stage(loaded: LoadedData) -> None:
    game = Game(loaded, fresh_game(loaded, 6))
    game.act(OpenSearch(1, "software_engineer", "job_post"))
    game.turn()
    _offer_all(game, 1.5, 50)
    result = game.turn()
    hires = [e for e in game.state.employments if e.role != "founder"]
    assert hires, "a 1.5x offer should be accepted"
    for e in hires:
        person = game.state.person(e.person_id)
        assert (e.start_turn, e.status, e.equity_bp, e.level) == (1, "active", 50, person.level)
        assert e.salary_cents == round((person.salary_expectation_cents or 0) * 1.5)
    assert game.state.player.stage == 1
    accepted = [i for i in result.log_items if i.template == "offer_accepted"]
    assert len(accepted) == len(hires)
    # Everyone hired got morale from new_hire (65) then one monthly update in phase 8.
    assert all(game.state.person_state(e.person_id).morale is not None for e in hires)
    assert game.state.offers == ()
    assert all(c.person_id not in {e.person_id for e in hires} for c in game.state.candidates)


def test_hiring_reveals_interests_and_work_style(loaded: LoadedData) -> None:
    """Job-post candidates arrive without a known profile; hiring reveals it that turn."""
    game = Game(loaded, fresh_game(loaded, 6))
    game.act(OpenSearch(1, "software_engineer", "job_post"))
    game.turn()
    unknown = [c.person_id for c in game.state.candidates]
    assert all(game.state.reveal(1, pid).profile_revealed_turn is None for pid in unknown)  # type: ignore[union-attr]
    _offer_all(game, 1.5)
    game.turn()
    hired = [e.person_id for e in game.state.employments if e.role != "founder"]
    assert hired
    for pid in hired:
        reveal = game.state.reveal(1, pid)
        assert reveal is not None and reveal.profile_revealed_turn == 1
    for pid in set(unknown) - set(hired):  # declined candidates stay unknown
        reveal = game.state.reveal(1, pid)
        assert reveal is None or reveal.profile_revealed_turn is None


def test_lowball_offers_are_always_declined(loaded: LoadedData) -> None:
    game = Game(loaded, fresh_game(loaded, 6))
    game.act(OpenSearch(1, "software_engineer", "job_post"))
    game.turn()
    count = len(game.state.candidates)
    _offer_all(game, 0.84)
    result = game.turn()
    assert [e.role for e in game.state.employments] == ["founder"]
    declined = [i for i in result.log_items if i.template == "offer_declined"]
    assert len(declined) == count
    assert game.state.player.stage == 0


def test_recruiter_fee_on_hire(loaded: LoadedData) -> None:
    game = Game(loaded, fresh_game(loaded, 8))
    game.act(OpenSearch(1, "data_scientist", "recruiter"))
    game.turn()
    _offer_all(game, 1.6)
    result = game.turn()
    hires = [e for e in game.state.employments if e.role != "founder"]
    assert hires
    fees = [e for e in result.ledger_entries if e.memo.startswith("Recruiter fee")]
    assert len(fees) == len(hires)
    for hire, fee in zip(sorted(hires, key=lambda e: e.person_id), fees, strict=True):
        lines = {ln.account: ln.amount for ln in fee.lines}
        assert lines["6200_recruiting"] == hire.salary_cents // 5  # 20% of annual salary


def test_acceptance_gap_over_1000_seeded_offers(loaded: LoadedData) -> None:
    """Acceptance at 1.10x the ask beats 0.95x by at least 30 points (engine resolution).

    Uses the formulas.md section 7 reference candidate: stage 0 company, 50 bp equity, one
    matching mission interest, risk appetite 10, ambition 10 (expected 42.6% vs 81.8%).
    """
    base = with_candidates(loaded, fresh_game(loaded, 21, mission=("ai", "enterprise")), 1)
    reference = base.person(2)
    reference = replace(
        reference,
        interests=("ai", "gaming"),
        personality=reference.personality.updated({"risk_appetite": 10, "ambition": 10}),
    )
    base = replace(base, people=tuple(reference if p.id == 2 else p for p in base.people))
    assert base.player.stage == 0
    expectation = reference.salary_expectation_cents or 0
    rates = {}
    for ratio in (0.95, 1.10):
        accepted = 0
        for i in range(1000):
            state = replace(base, save_meta=replace(base.save_meta, master_seed=1000 + i))
            state = with_offer(
                state,
                Offer(
                    id=1,
                    company_id=1,
                    candidate_id=2,
                    actor_id=1,
                    salary_cents=round(expectation * ratio),
                    equity_bp=50,
                    made_turn=0,
                ),
            )
            result = advance_turn(
                state,
                Decisions(),
                RngFactory(1000 + i),
                loaded.balance,
                loaded.game_data,
                {(1, CASH): START_CASH},
            )
            accepted += any(e.person_id == 2 for e in result.new_state.employments)
        rates[ratio] = accepted / 1000
    print(f"acceptance 0.95x={rates[0.95]:.3f} 1.10x={rates[1.10]:.3f}")
    assert rates[1.10] - rates[0.95] >= 0.30


# --- Phase 6: payroll -------------------------------------------------------------------------


def test_payroll_posts_every_cost(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    engineer = replace(make_person(loaded, 20, "software_engineer", "senior"), tags=())
    state = with_employee(loaded, state, engineer, 11_500_000)
    game = Game(loaded, state)
    game.act(OpenSearch(1, "designer", "job_post"))
    result = game.turn()
    (costs,) = [e for e in result.ledger_entries if e.memo.startswith("Monthly costs")]
    lines = {ln.account: ln.amount for ln in costs.lines}
    assert lines == {
        "6000_salaries": 958_333,
        "6010_benefits": 191_667,
        "6100_rent": 120_000,  # founder + engineer
        "6900_general_admin": 50_000,
        "6200_recruiting": 50_000,  # one job post
        CASH: -(958_333 + 191_667 + 120_000 + 50_000 + 50_000),
    }
    assert sum(ln.amount for e in result.ledger_entries for ln in e.lines) == 0
    snap = result.snapshot.for_company(1)
    assert snap.payroll_cents == 958_333 + 191_667
    assert snap.headcount == 2
    assert snap.cash_cents == game.cash


def test_monthly_costs_project_phase_6(loaded: LoadedData) -> None:
    """The Overview's projection uses the same lines phase 6 posts (formulas.md section 8)."""
    state = fresh_game(loaded)
    engineer = replace(make_person(loaded, 20, "software_engineer", "senior"), tags=())
    state = with_employee(loaded, state, engineer, 11_500_000)
    game = Game(loaded, state)
    game.act(OpenSearch(1, "designer", "job_post"))
    projected = {
        account: amount
        for _, account, amount in phases.monthly_costs(
            game.state, 1, loaded.balance, loaded.game_data
        )
        if amount
    }
    (costs,) = [e for e in game.turn().ledger_entries if e.memo.startswith("Monthly costs")]
    assert projected == {ln.account: ln.amount for ln in costs.lines if ln.account != CASH}
    employment = game.state.employment_of(engineer.id)
    assert employment is not None
    # $115,000 senior engineer: $12,100.00 a month (formulas.md section 8 worked example).
    assert phases.employment_monthly_cost_cents(employment, loaded.balance) == 1_210_000


def test_notice_is_paid_then_ends(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    state = with_employee(loaded, state, make_person(loaded, 20), 9_000_000)
    emp = state.employment_of(20)
    assert emp is not None
    from tst.sim.state import with_employment

    state = with_employment(state, replace(emp, status="notice", end_turn=1, end_reason="resigned"))
    game = Game(loaded, state)
    first = game.turn()  # turn 0: still on notice, paid
    costs = next(e for e in first.ledger_entries if e.memo.startswith("Monthly costs"))
    assert {ln.account for ln in costs.lines} >= {"6000_salaries"}
    assert first.snapshot.for_company(1).headcount == 2
    second = game.turn()  # turn 1: ends in phase 1
    assert game.state.employment_of(20) is None
    assert second.snapshot.for_company(1).headcount == 1
    left = [i for i in second.log_items if i.template == "employee_left"]
    assert dict(left[0].params)["reason"] == "resigned"


# --- Phase 8: morale, departures, reveals ------------------------------------------------------


def _staff_game(
    loaded: LoadedData, seed: int, salary_ratio: float, fit: bool, count: int = 10
) -> Game:
    """A company with `count` engineers paid salary_ratio x market mid, fitting or not."""
    mission = ("ai", "open_source")
    state = fresh_game(loaded, seed, mission=mission)
    data = loaded.game_data
    role = data.role("software_engineer")
    for i in range(count):
        person = make_person(loaded, 20 + i, "software_engineer", "mid")
        person = replace(
            person,
            region="north_america",
            interests=mission if fit else ("crypto", "mining"),
            work_style=role.work_style if fit else "seller",
            tags=(),
        )
        mid = role.salary_band_mid_cents["mid"]
        state = with_employee(loaded, state, person, round(mid * salary_ratio))
    return Game(loaded, state, cash=10**12)


def test_underpaid_misfits_lose_morale_and_resign_more(loaded: LoadedData) -> None:
    """Acceptance: over 60 turns, underpaid misfits end with lower morale and more departures."""
    happy_left = sad_left = 0
    happy_morale: list[float] = []
    sad_morale: list[float] = []
    for seed in range(1, 6):
        happy, sad = _staff_game(loaded, seed, 1.15, True), _staff_game(loaded, seed, 0.75, False)
        for game, morale in ((happy, happy_morale), (sad, sad_morale)):
            for _ in range(60):
                game.turn()
                morale.append(game.results[-1].snapshot.for_company(1).avg_morale or 0)
        happy_left += 10 - (len(happy.state.staff(1)) - 1)
        sad_left += 10 - (len(sad.state.staff(1)) - 1)
    print(f"departures: well paid & fit {happy_left}, underpaid misfits {sad_left}")
    assert sum(sad_morale) / len(sad_morale) < sum(happy_morale) / len(happy_morale) - 20
    assert sad_left > happy_left


def test_morale_converges_toward_target(loaded: LoadedData) -> None:
    game = _staff_game(loaded, 3, 1.0, True, count=1)
    for _ in range(24):
        game.turn()
    # target = 50 + pay 0 + fit 2 x 5 = 60 with healthy runway; noise sd is small
    morale = game.state.person_state(20).morale
    assert morale is not None and 52 <= morale <= 68


def test_retirement_from_60(loaded: LoadedData) -> None:
    state = fresh_game(loaded, 2)
    retirees = 0
    for i in range(30):
        person = replace(make_person(loaded, 20 + i), birth_turn=-12 * 70, tags=())  # age 70
        state = with_employee(loaded, state, person, 20_000_000, morale=100)
        state = with_person_state(state, PersonState(person_id=person.id, morale=100))
    game = Game(loaded, state, cash=10**12)
    result = game.turn()
    retirees = sum(1 for i in result.log_items if i.template == "retired")
    # 550 bp a month each at age 70: expect ~1.6 of 30; resignations are rare at morale ~100
    assert 0 <= retirees <= 6
    ended_reasons = {e.end_reason for e in game.state.employments if e.status == "notice"}
    assert ended_reasons <= {"retired", "resigned"}
    assert game.state.founder_of(1) is not None  # the founder never retires in M1


def test_monthly_tag_reveals_and_employed_month(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    person = replace(make_person(loaded, 20), tags=("mentor", "maverick"))
    state = with_employee(loaded, state, person, 9_000_000)
    from tst.sim.people.reveal import new_reveal_state
    from tst.sim.state import with_reveal

    state = with_reveal(
        state,
        new_reveal_state(
            observer_company_id=1,
            person=person,
            turn=0,
            rng=RngFactory(3),
            data=loaded.game_data,
            balance=loaded.balance,
        ),
    )
    game = Game(loaded, state)
    hws = []
    for _ in range(36):
        game.turn()
        reveal = game.state.reveal(1, 20)
        assert reveal is not None
        hws.append(reveal.record("software_engineering").hw)
    assert hws == sorted(hws, reverse=True) and hws[-1] < hws[0]
    reveal = game.state.reveal(1, 20)
    assert reveal is not None
    assert {t for t, _ in reveal.revealed_tags} <= {"mentor", "maverick"}
    reveals = [i for r in game.results for i in r.log_items if i.template == "tag_revealed"]
    assert len(reveals) == len(reveal.revealed_tags)
    # 5% a month each: after 36 months at least one of two tags is almost certainly known
    assert reveal.revealed_tags
    assert reveal.record(PA_KEY).hw < loaded.balance.reveal.initial_hw.pa


def test_runway_term_uses_cash_this_month(loaded: LoadedData) -> None:
    """Out of cash: every employee's target drops by 20 (cash <= 0 counts as critical)."""
    rich = _staff_game(loaded, 5, 1.0, True, count=3)
    broke = _staff_game(loaded, 5, 1.0, True, count=3)
    broke.balances = {(1, CASH): 0}
    rich.turn()
    broke.turn()
    for pid in (20, 21, 22):
        assert (broke.state.person_state(pid).morale or 0) < (
            rich.state.person_state(pid).morale or 0
        )
    assert any(i.template == "insolvent" for i in broke.results[-1].log_items)  # M4 (14.7)


def test_score_helpers_match_formula(loaded: LoadedData) -> None:
    offer = loaded.balance.hiring.offer
    score = offer_score(
        ratio=1.0,
        equity_bp=0,
        matching_interests=0,
        risk_appetite=10,
        ambition=10,
        stage=1,
        offer=offer,
    )
    assert acceptance_probability(score, offer) == pytest.approx(0.5)
