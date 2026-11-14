"""docs/formulas.md 45.8 targets (M36), printed by tools/m36_targets.py and checked nightly
(tests/balance/test_m36_balance.py). Target 1 (nothing moves without a family) is the golden
snapshots, the state-cache check and every earlier guard, run as they are.

- Target 2 (family time matters): a new funded spinout with a partner and two children, the
  steady script for 120 months. Arm `time10`: family time 10, critical events answered with
  their first choice. Arm `neglect`: family time 0, the founder spending every point of energy
  each month (burnout follows), and strain answered "carry on".
- Target 3 (upbringing matters): each seed's two children of the same potential develop from
  5 to 22 by 45.3 (stream family's noise), one with elite school, a top university and closeness
  80, the other with standard schooling and closeness 30; the CEO-seat score at 22 from true
  skills (a tool reads them).
- Target 4 (succession is a real choice): each seed's steady game at its first month of stage
  3, the founder aged to 60 with a child of 30 in the company; the child and an outside
  executive set to every skill 15, known exactly (equal displayed fit, a strong heir). Arm
  `heir` hands over (45.5); arm `ceo` appoints the executive. Then 120 months of the steady
  script; 28.1's company value at the end.
- Target 5 (estate planning pays): a founder of 70 in 2030 holding $10B of a listed company's
  shares, a seeded stake of 26-50% of the company (above family control), no other wealth; a health
  succession to the heir with no planning, and with 80% of the shares in a trust set up ten
  years before.

True values are read here; this is a tool. Draws for the tool's own choices use stream misc.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from statistics import median
from typing import Final

from tst.balance.game import PLAYER, Game
from tst.balance.m8 import add_staff, fork, steady_at_stage_3
from tst.balance.strategies import steady
from tst.config import Settings
from tst.loader import LoadedData, load_all
from tst.sim.actions.events import ChooseEvent
from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.family import answers, estate, rules, succession
from tst.sim.family.people import develop
from tst.sim.family.setup import FamilySpec, start_family
from tst.sim.finance.captable import fd_shares, person_shares
from tst.sim.ledger import apply_entries
from tst.sim.markets_public.models import PublicCompany
from tst.sim.people.founder import FounderSpec
from tst.sim.people.models import PA_KEY, RevealRecord
from tst.sim.rng import RngFactory
from tst.sim.setup import new_game
from tst.sim.state import GameState, family_partner, with_person, with_person_state, with_reveal

SEEDS: Final = tuple(range(1, 11))
YEARS: Final = 10
MONTHS: Final = YEARS * MONTHS_PER_YEAR
HEIR_SKILL: Final = 15.0
STAKE: Final = (0.26, 0.50)
TRUST_SHARE: Final = 0.8
TEN_BILLION: Final = 10_000_000_000_00  # cents
ESTATE_TURN: Final = 20 * MONTHS_PER_YEAR  # January 2030
SHARES: Final = 1_000_000_000  # the listed company's fully diluted shares (target 5)


def _loaded() -> LoadedData:
    return load_all(Settings().data_dir)


def _family_game(loaded: LoadedData, seed: int, age: int, ages: tuple[int, ...]) -> Game:
    scenario = loaded.game_data.scenario("funded_spinout")
    assert scenario is not None
    state, entries = new_game(
        save_name="m36",
        master_seed=seed,
        scenario=scenario,
        difficulty="standard",
        company_name="Family Co",
        founder=FounderSpec(background="engineer", age=age),
        balance=loaded.balance,
        data=loaded.game_data,
        family=FamilySpec("children", ages),
    )
    return Game(loaded, state, apply_entries({}, entries))


# --- Target 2 --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TimeRun:
    seed: int
    arm: str
    relationship_low: float
    divorced: bool
    burnouts: int


def play_time(args: tuple[int, str]) -> TimeRun:
    seed, arm = args
    loaded = _loaded()
    game = _family_game(loaded, seed, 32, (2, 5))
    time = 10 if arm == "time10" else 0
    game.state = answers.set_family_time(game.state, time, loaded.balance)
    low = 100.0
    for _ in range(MONTHS):
        if game.state.ended:
            break
        steady(game)
        if arm == "neglect":
            for e in game.state.open_events(PLAYER):
                if e.template_id == "family_strain" and e.status == "open":
                    game.act(ChooseEvent(game.founder_id, e.id, "C"))  # carry on
            ps = game.state.person_state(game.founder_id)
            game.state = with_person_state(game.state, replace(ps, energy=0))
        game.turn()
        family = game.state.family
        assert family is not None
        if family_partner(game.state) is not None:
            low = min(low, family.relationship)
    divorced = any(m.relation == "ex_partner" for m in game.state.family_members)
    life = next((x for x in game.state.founder_lives if x.person_id == game.founder_id), None)
    return TimeRun(seed, arm, low, divorced, life.burnouts if life else 0)


# --- Target 3 --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UpbringingRun:
    seed: int
    good: float
    poor: float


def play_upbringing(seed: int) -> UpbringingRun:
    loaded = _loaded()
    b, d = loaded.balance, loaded.game_data
    game = _family_game(loaded, seed, 45, (0,))
    kid = rules.children(game.state)[0]
    person = game.state.person(kid.person_id)
    good = replace(kid, school="elite", university="top", degree="business")
    poor = replace(kid, school="standard", university="standard", degree="business")
    rng = RngFactory(seed)
    a, p = person, person
    start = person.birth_turn + MONTHS_PER_YEAR * b.family.develop_from
    end = person.birth_turn + MONTHS_PER_YEAR * 22
    for t in range(start, end):
        gen_a = rng.stream(t, "family", person.id, 1)
        gen_p = rng.stream(t, "family", person.id, 1)  # the same noise: only upbringing differs
        a = develop(a, good, t, gen_a, 80.0, b, d)
        p = develop(p, poor, t, gen_p, 30.0, b, d)
    return UpbringingRun(seed, rules.true_ceo_fit(a, b), rules.true_ceo_fit(p, b))


# --- Target 4 --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SuccessionRun:
    seed: int
    heir_cents: int
    ceo_cents: int


def _exact(state: GameState, pid: int) -> GameState:
    rev = state.reveal(PLAYER, pid)
    assert rev is not None
    attrs = tuple(
        (k, RevealRecord(0.0 if k != PA_KEY else r.hw, r.offset, state.turn))
        for k, r in rev.attributes
    )
    return with_reveal(state, replace(rev, attributes=attrs))


def _skilled(state: GameState, pid: int) -> GameState:
    p = state.person(pid)
    skills = p.skills.updated(dict.fromkeys(p.skills.keys(), HEIR_SKILL))
    return _exact(with_person(state, replace(p, skills=skills)), pid)


def _value(game: Game) -> int:
    from tst.sim.mna.valuation import fundamental_value_cents

    if game.state.ended:
        return 0
    b, d = game.loaded.balance, game.loaded.game_data
    return fundamental_value_cents(game.state, PLAYER, game.balances, b, d)


def _play(game: Game, months: int) -> None:
    for _ in range(months):
        if game.state.ended:
            return
        steady(game)
        game.turn()


def play_succession(seed: int) -> SuccessionRun | None:
    base = steady_at_stage_3(seed)
    if base is None:
        return None
    loaded = base.loaded
    b, d = loaded.balance, loaded.game_data
    state = base.state
    founder = state.person(base.founder_id)
    state = with_person(state, replace(founder, birth_turn=state.turn - 60 * MONTHS_PER_YEAR))
    rng = RngFactory(seed)
    state = start_family(state, FamilySpec("children", (30,)), rng, b, d)
    base.state = state
    heir = rules.children(state)[0].person_id
    base.state = _close(state, heir)
    role = next(r.key for r in d.roles if r.founder_fit and rules.roles_match(
        base.state.person(heir), r.key, d))  # fmt: skip
    base.state, _ = answers.offer_job(base.state, heir, PLAYER, role, "exec", b, d)
    base.state = _skilled(base.state, heir)
    (ceo,) = add_staff(base, "product_manager", "exec", 1, HEIR_SKILL)
    base.state = _exact(base.state, ceo)
    a, c = fork(base), fork(base)
    a.state, _ = succession.hand_to_heir(a.state, heir, "choice", rng, a.balances, b, d)
    c.state, _ = succession.appoint_professional(c.state, ceo, "choice", rng, b, d)
    _play(a, MONTHS)
    _play(c, MONTHS)
    return SuccessionRun(seed, _value(a), _value(c))


def _close(state: GameState, pid: int) -> GameState:
    from tst.sim.state import with_family_member

    return with_family_member(state, replace(rules.member_of(state, pid), closeness=90.0))


# --- Target 5 --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EstateRun:
    seed: int
    stake: float
    lost_plain: bool
    lost_trust: bool


def _listed(state: GameState, stake: float) -> GameState:
    """The founder holds `stake` of SHARES; the rest is the public float; the price makes the
    founder's shares worth $10B."""
    from tst.sim.family.transfers import give_shares, take_person_shares
    from tst.sim.markets_public.ipo import PUBLIC_HOLDERS

    head = state.family.head_id  # type: ignore[union-attr]
    held = person_shares(state, PLAYER, head)
    state = take_person_shares(state, PLAYER, head, held)
    others = fd_shares(state, PLAYER)
    mine = round(stake * SHARES)
    state = give_shares(state, PLAYER, mine, person_id=head)
    state = give_shares(state, PLAYER, max(0, SHARES - mine - others), group=PUBLIC_HOLDERS)
    price = TEN_BILLION // mine
    public = PublicCompany(PLAYER, state.turn, "FAM", False, price, price, 0.0, price * SHARES)
    return replace(state, public_companies=(public,))


def play_estate(seed: int) -> EstateRun:
    loaded = _loaded()
    b, d = loaded.balance, loaded.game_data
    game = _family_game(loaded, seed, 50, (20,))
    u = float(RngFactory(seed).stream(0, "misc", 36).random())
    stake = STAKE[0] + (STAKE[1] - STAKE[0]) * u
    state = replace(game.state, turn=ESTATE_TURN)  # the founder is 70 in 2030 (today's rules)
    state = _listed(state, stake)
    heir = rules.children(state)[0].person_id
    head = state.family.head_id  # type: ignore[union-attr]
    plain, _ = estate.settle(state, head, heir, None, b, d)
    from tst.sim.founder import personal

    planned = personal.credit(state, head, b.family.trust_setup_cents, "secondary")
    shares = int(person_shares(planned, PLAYER, head) * TRUST_SHARE)
    planned, _ = estate.fund_trust(planned, shares, b)
    planned, _ = estate.settle(planned, head, heir, None, b, d)
    return EstateRun(
        seed,
        stake,
        plain.family is not None and plain.family.control_losses > 0,
        planned.family is not None and planned.family.control_losses > 0,
    )


# --- Running and reporting -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Results:
    time: tuple[TimeRun, ...]
    upbringing: tuple[UpbringingRun, ...]
    succession: tuple[SuccessionRun, ...]
    estate: tuple[EstateRun, ...]


def run(seeds: tuple[int, ...] = SEEDS, jobs: int = 1, only: tuple[str, ...] = ()) -> Results:
    want = set(only) or {"time", "upbringing", "succession", "estate"}
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        time = (
            tuple(pool.map(play_time, [(s, a) for s in seeds for a in ("time10", "neglect")]))
            if "time" in want
            else ()
        )
        up = tuple(pool.map(play_upbringing, seeds)) if "upbringing" in want else ()
        succ = (
            tuple(r for r in pool.map(play_succession, seeds) if r is not None)
            if "succession" in want
            else ()
        )
        est = tuple(pool.map(play_estate, seeds)) if "estate" in want else ()
    return Results(time, up, succ, est)


def target_2(r: Results) -> tuple[int, int, int]:
    """(time-10 seeds above 50, neglect seeds divorced, runs per arm)."""
    above = sum(1 for t in r.time if t.arm == "time10" and t.relationship_low > 50)
    divorced = sum(1 for t in r.time if t.arm == "neglect" and t.divorced)
    return above, divorced, sum(1 for t in r.time if t.arm == "time10")


def target_3(r: Results) -> tuple[float, float, float]:
    good = median(u.good for u in r.upbringing)
    poor = median(u.poor for u in r.upbringing)
    return good, poor, good - poor


def target_4(r: Results) -> tuple[int, int, float, int]:
    heir = int(median(s.heir_cents for s in r.succession))
    ceo = int(median(s.ceo_cents for s in r.succession))
    ratio = heir / ceo if ceo else float("inf")
    return heir, ceo, ratio, len(r.succession)


def target_5(r: Results) -> tuple[int, int, int]:
    plain = sum(1 for e in r.estate if e.lost_plain)
    trust = sum(1 for e in r.estate if e.lost_trust)
    return plain, trust, len(r.estate)


def report(r: Results) -> str:
    lines = ["M36 (formulas.md 45.8) targets"]
    if r.time:
        above, divorced, n = target_2(r)
        lines.append(
            f"T2 family time: time 10 keeps the relationship above 50 on {above}/{n} seeds "
            f"(>= 8); neglect with burnout divorces on {divorced}/{n} (>= 3) "
            f"{'PASS' if above >= 8 and divorced >= 3 else 'FAIL'}"
        )
    if r.upbringing:
        good, poor, gap = target_3(r)
        lines.append(
            f"T3 upbringing: median CEO-seat score at 22 {good:.2f} vs {poor:.2f}, gap "
            f"{gap:.2f} (>= 3) {'PASS' if gap >= 3 else 'FAIL'}"
        )
    if r.succession:
        heir, ceo, ratio, n = target_4(r)
        ok = 0.8 <= ratio <= 1.2
        lines.append(
            f"T4 succession: median value 10 years on, heir ${heir / 100:,.0f} vs CEO "
            f"${ceo / 100:,.0f}, ratio {ratio:.2f} over {n} seeds (0.8-1.2) "
            f"{'PASS' if ok else 'FAIL'}"
        )
    if r.estate:
        plain, trust, n = target_5(r)
        lines.append(
            f"T5 estate: control lost without planning {plain}/{n} (>= half), with a trust "
            f"{trust}/{n} (<= 1) {'PASS' if plain * 2 >= n and trust <= 1 else 'FAIL'}"
        )
    return "\n".join(lines)
