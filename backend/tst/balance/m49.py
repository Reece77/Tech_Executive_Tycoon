"""docs/formulas.md 61.3 targets 2-4 (M49), printed with their values. Target 1 (skip is today's
game) is M30's state cache and the golden snapshots: a game that never holds a talk runs no talk
code. Target 5 (no leak) is tests/integration/test_m49_talks.py.

- T2 talks retain people: the steady script's company from January 2010, 120 months, 10 seeds.
  Each month the founder holds a one-to-one with every person a rival has approached (flagged;
  answered at the next Continue), while energy lasts, with the sensible script (listen and
  praise on how things are and where they want to go; on the approach, offer a raise, listen
  and praise). Each approach is measured paired: its answer with the talk and, from the same
  state and the same draw, without it (skip), so the two founders face the same approaches.
  In real games most approached people turn a rival down whatever the founder does (about 93%
  on seed 1), so the measure is the people the rival wins when the founder skips: the talking
  founder keeps at least 30% of them (median over seeds), at the talks' energy cost.
- T3 promises bite: a promotion promised in a one-to-one at month 24 to the company's best
  non-executive and never given; at the deadline (12 months on) the judging costs them at least
  8 morale and doubles their monthly resignation chance.
- T4 crises reward candour: a medical device (a cleared glucose monitor with users) given a
  class I recall in month 60; the next month a press conference answered with apologise and
  take_responsibility, against the same conference answered with deflect. The device's brand
  regained 12 months later: candour at least 1.25x deflection's; and deflection's chance of a
  for-cause inspection is above candour's.
"""

from __future__ import annotations

import copy
import os
import statistics
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from typing import Final

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.m30 import loaded
from tst.balance.report import SCENARIO
from tst.balance.strategies_v2 import STRATEGIES
from tst.sim.actions import apply_action
from tst.sim.errors import SimError
from tst.sim.rivals.poaching import answer_key, approach_probability, poach_draw
from tst.sim.rng import RngFactory
from tst.sim.state import GameState
from tst.sim.talks import engine, opening
from tst.sim.talks.actions import outcome_action
from tst.sim.talks.models import Move, Talk

SEEDS: tuple[int, ...] = tuple(range(1, 11))
MONTHS: Final = 120
STRATEGY: Final = "steady"
T2_KEPT: Final = 0.30  # share of the people the rival wins on skip that talks keep
T3_MORALE: Final = 8.0
T3_LEAVE: Final = 2.0
T3_AT: Final = 24  # the month the promise is made
T4_AT: Final = 60  # the recall's month
T4_AFTER: Final = 12  # months the brand is followed
T4_FASTER: Final = 1.25
RECALL_PRICE: Final = 15_000  # cents a month a user (the fixture's glucose monitor)
RECALL_USERS: Final = 40_000.0
EPS: Final = 1e-9  # tunable-exempt: float tolerance


def _script(talk: Talk) -> tuple[Move, ...]:
    q = talk.next_question
    assert q is not None
    if q.topic == "approach":
        return (Move("offer_raise"), Move("listen"), Move("praise"))
    return (Move("listen"), Move("praise"))


def _play(talk: Talk, game: Game) -> Talk:
    tb = game.loaded.balance.talks
    while talk.status == "open":
        talk = engine.play(talk, _script(talk), tb)
    return talk


def _one_to_one(game: Game, person_id: int, script: tuple[str, ...] | None = None) -> Talk:
    b = game.loaded.balance
    morale = game.state.person_state(person_id).morale
    talk = opening.open_one_to_one(
        game.state,
        person_id,
        RngFactory(game.state.save_meta.master_seed),
        b,
        game.loaded.game_data,
        morale_shown=round(morale) if morale is not None else None,
    )
    if script is None:
        return _play(talk, game)
    while talk.status == "open":
        talk = engine.play(talk, tuple(Move(m) for m in script), b.talks)
    return talk


def _action(game: Game, talk: Talk) -> object:
    pid = talk.counterpart.person_id
    e = game.state.employment_of(pid) if pid is not None else None
    salary = e.salary_cents if e is not None else 0
    return outcome_action(
        talk, game.founder_id, salary, game.loaded.balance.talks.one_to_one.raise_share
    )


def _applied(game: Game, action: object) -> GameState | None:
    try:
        out = apply_action(
            game.state,
            action,  # type: ignore[arg-type]
            RngFactory(game.state.save_meta.master_seed),
            game.loaded.balance,
            game.loaded.game_data,
            game.balances,
            seq=game.seq + 1,
        )
    except SimError:
        return None
    return out.new_state


# --- T2 ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RetainRun:
    seed: int
    approaches: int  # approaches answered while the founder could talk
    lost_skip: int  # of them, the rival won on skip
    lost_talk: int  # ...and with the talk
    talks: int
    energy: int  # founder energy the talks cost (talks and their raises)


def _answer(state: GameState, approach_id: int, rng: RngFactory, game: Game) -> bool:
    """Whether phase 1 next month would see the person accept (the same draw either way)."""
    a = next(x for x in state.approaches if x.id == approach_id)
    if a.status != "pending":
        return False  # turned the rival down after the talk
    p = approach_probability(state, a, game.loaded.balance)
    return poach_draw(rng, state.turn + 1, *answer_key(state, a)) < p


def run_retain(seed: int) -> RetainRun:
    game = start_game(loaded(), seed, SCENARIO)
    rng = RngFactory(game.state.save_meta.master_seed)
    approaches = lost_skip = lost_talk = talks = energy = 0
    for _ in range(MONTHS):
        STRATEGIES[STRATEGY](game)
        pending = [
            a
            for a in sorted(game.state.approaches, key=lambda a: a.id)
            if a.status == "pending"
            and a.made_turn < game.state.turn
            and (e := game.state.employment_of(a.person_id)) is not None
            and e.company_id == PLAYER
            and e.status == "active"
        ]
        for a in pending:
            before = game.energy()
            need = game.loaded.balance.talks.energy["one_to_one"]
            if before < need + game.loaded.balance.founder.energy_cost["give_raise"]:
                continue  # out of energy this month: the approach goes unanswered by a talk
            talked = _applied(game, _action(game, _one_to_one(game, a.person_id)))
            if talked is None:
                continue
            approaches += 1
            lost_skip += _answer(game.state, a.id, rng, game)
            game.state = talked
            game.seq += 1
            lost_talk += _answer(game.state, a.id, rng, game)
            talks += 1
            energy += before - game.energy()
        game.turn()
        if game.state.ended:
            break
    return RetainRun(seed, approaches, lost_skip, lost_talk, talks, energy)


# --- T3 ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PromiseRun:
    seed: int
    morale_cost: float | None  # morale the broken promise cost at its judging
    leave_ratio: float | None  # resignation chance after / before


def _best(game: Game) -> int | None:
    from tst.sim.people.models import current_ability

    seats = {s.person_id for s in game.state.exec_seats if s.company_id == PLAYER}
    founder = game.founder_id
    people = [
        e
        for e in game.state.staff(PLAYER)
        if e.status == "active"
        and e.person_id not in seats
        and e.person_id != founder
        and e.level in opening.LADDER[:-1]
        and game.state.person_state(e.person_id).morale is not None
    ]
    if not people:
        return None
    best = max(
        people,
        key=lambda e: (
            current_ability(game.state.person(e.person_id), game.loaded.game_data),
            -e.person_id,
        ),
    )
    return best.person_id


def run_promise(seed: int) -> PromiseRun:
    from tst.sim.hiring.formulas import resignation_bp
    from tst.sim.press import promises

    game = start_game(loaded(), seed, SCENARIO)
    b = game.loaded.balance
    for _ in range(T3_AT):
        STRATEGIES[STRATEGY](game)
        game.turn()
    pid = _best(game)
    if pid is None:
        return PromiseRun(seed, None, None)
    talk = _one_to_one(game, pid, ("listen", "promise_promotion"))
    if not game.act(_action(game, talk)):  # type: ignore[arg-type]
        return PromiseRun(seed, None, None)
    promise = next(p for p in game.state.promises if p.kind == "promotion" and p.level == pid)
    while game.state.turn < promise.deadline_turn:
        STRATEGIES[STRATEGY](game)
        game.turn()
        if game.state.ended:
            return PromiseRun(seed, None, None)
    state = game.state
    now = next(p for p in state.promises if p.id == promise.id)
    e = state.employment_of(pid)
    if now.status != "open" or e is None or e.status != "active":
        return PromiseRun(seed, None, None)  # kept by the script's own promotions, or left
    before = state.person_state(pid).morale or 0.0
    judged, _ = promises.check(
        state, RngFactory(state.save_meta.master_seed), b, game.loaded.game_data
    )
    after = judged.person_state(pid).morale or 0.0
    loyalty = judged.person(pid).personality["loyalty"]
    was = resignation_bp(before, state.person(pid).personality["loyalty"], False, b.resign)
    now_bp = resignation_bp(after, loyalty, False, b.resign)
    mult = promises.leave_mult(judged, b).get(pid, 1.0)
    return PromiseRun(seed, before - after, min(now_bp * mult, b.resign.cap_bp) / was)


# --- T4 ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CrisisRun:
    seed: int
    hit: float  # brand points the recall cost
    candour: float  # brand regained in T4_AFTER months after an apology
    deflect: float  # ...after a deflection
    inspect_candour: float  # the conference's inspection chance
    inspect_deflect: float


def _device(game: Game) -> int:
    """A cleared glucose monitor with users (as tools/e2e_m49_save.py's)."""
    from tst.sim.medical.models import Clearance, Design
    from tst.sim.products.formulas import held_feature_points
    from tst.sim.products.models import Product, ProductSegment
    from tst.sim.state import with_product, with_product_segment

    data = game.loaded.game_data
    state = game.state
    pid, ids = state.next_ids.take("product")
    category = "wearables_diagnostics"
    cat = data.category(category)
    held = 65.0  # tunable-exempt: the fixture's feature level
    product = Product(
        id=pid,
        company_id=PLAYER,
        category=category,
        name="Glucose",
        status="live",
        quality=72.0,  # tunable-exempt: the fixture's quality
        feature_points=held_feature_points(held, cat, state.turn),
        brand=45.0,  # tunable-exempt: the fixture's brand
        marketing_budget_cents=0,
        created_turn=state.turn - 24,
        launched_turn=state.turn - 12,
    )
    state = replace(with_product(state, product), next_ids=ids)
    segment = cat.markets[0].segment
    state = with_product_segment(state, ProductSegment(pid, segment, RECALL_PRICE, RECALL_USERS))
    state = replace(
        state,
        med_designs=(*state.med_designs, Design(pid, "glucose_monitoring")),
        med_clearances=(
            *state.med_clearances,
            Clearance(pid, "fda", "north_america", state.turn - 12, "k510"),
        ),
    )
    game.state = state
    return pid


def _fork(game: Game) -> Game:
    out = copy.copy(game)
    out.balances = dict(game.balances)
    out.snapshots = list(game.snapshots)
    out.month_lines = list(game.month_lines)
    out.group_lines = list(game.group_lines)
    out.refused = copy.copy(game.refused)
    out.notes = dict(game.notes)
    out.pnl = dict(game.pnl)
    out.group_pnl = dict(game.group_pnl)
    out.founder_value = dict(game.founder_value)
    out.traction_above_floor = dict(game.traction_above_floor)
    return out


def run_crisis(seed: int) -> CrisisRun:
    from tst.sim.medical import quality

    game = start_game(loaded(), seed, SCENARIO)
    b, d = game.loaded.balance, game.loaded.game_data
    for _ in range(T4_AT):
        STRATEGIES[STRATEGY](game)
        game.turn()
    pid = _device(game)
    product = game.state.product(pid)
    assert product is not None
    before = product.brand
    game.state, _, _, _ = quality.recall(game.state, product, "I", False, b, d)
    STRATEGIES[STRATEGY](game)
    game.turn()
    subject = next(s for s in opening.crisis_subjects(game.state, b.talks) if s.product_id == pid)
    talk = opening.open_press(
        game.state, "crisis", subject, RngFactory(game.state.save_meta.master_seed), b, d
    )
    hit_brand = game.state.product(pid).brand  # type: ignore[union-attr]
    regained: dict[str, float] = {}
    chance: dict[str, float] = {}
    for arm, moves in (
        ("candour", ("apologise", "take_responsibility")),
        ("deflect", ("deflect",)),
    ):
        g = _fork(game)
        played = talk
        while played.status == "open":
            played = engine.play(played, tuple(Move(m) for m in moves), b.talks)
        assert played.effects is not None
        chance[arm] = played.effects.inspection_chance
        g.act(_action(g, played))  # type: ignore[arg-type]
        for _ in range(T4_AFTER):
            STRATEGIES[STRATEGY](g)
            g.turn()
        now = g.state.product(pid)
        regained[arm] = (now.brand if now is not None else 0.0) - hit_brand
    return CrisisRun(
        seed,
        before - hit_brand,
        regained["candour"],
        regained["deflect"],
        chance["candour"],
        chance["deflect"],
    )


# --- Running and reporting --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Results:
    retain: tuple[RetainRun, ...]
    promise: tuple[PromiseRun, ...]
    crisis: tuple[CrisisRun, ...]


def run(seeds: Sequence[int] = SEEDS, jobs: int = os.cpu_count() or 1) -> Results:
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        retain = pool.map(run_retain, seeds)
        promise = pool.map(run_promise, seeds)
        crisis = pool.map(run_crisis, seeds)
        return Results(tuple(retain), tuple(promise), tuple(crisis))


def t2(r: Results) -> tuple[float | None, float, float]:
    """(median share of skip's losses the talks keep, kept share on skip, with talks)."""
    shares = [(x.lost_skip - x.lost_talk) / x.lost_skip for x in r.retain if x.lost_skip]
    n = sum(x.approaches for x in r.retain) or 1
    kept_skip = 1 - sum(x.lost_skip for x in r.retain) / n
    kept_talk = 1 - sum(x.lost_talk for x in r.retain) / n
    return (statistics.median(shares) if shares else None), kept_skip, kept_talk


def t3(r: Results) -> tuple[float | None, float | None]:
    costs = [x.morale_cost for x in r.promise if x.morale_cost is not None]
    ratios = [x.leave_ratio for x in r.promise if x.leave_ratio is not None]
    return (min(costs) if costs else None), (min(ratios) if ratios else None)


def t4(r: Results) -> tuple[float | None, float, float]:
    """(median ratio of brand regained, candour against deflection; inspection chances)."""
    ratios = [x.candour / x.deflect for x in r.crisis if x.deflect > EPS]
    worse = [x for x in r.crisis if x.deflect <= EPS < x.candour]
    ratio = statistics.median(ratios) if ratios else (float("inf") if worse else None)
    c = statistics.fmean(x.inspect_candour for x in r.crisis) if r.crisis else 0.0
    dfl = statistics.fmean(x.inspect_deflect for x in r.crisis) if r.crisis else 0.0
    return ratio, c, dfl


def report(r: Results) -> str:
    kept, on_skip, on_talk = t2(r)
    talks = sum(x.talks for x in r.retain)
    energy = sum(x.energy for x in r.retain)
    months = MONTHS * len(r.retain)
    rows = [
        "T2 of the approached people the rival wins on skip, talks keep "
        + ("-" if kept is None else f"{kept:.0%}")
        + f" (median, at least {T2_KEPT:.0%}); kept overall {on_skip:.1%} skipping, "
        f"{on_talk:.1%} talking; {sum(x.approaches for x in r.retain)} approaches, "
        f"{talks} talks costing {energy} energy ({energy / months:.2f} a month); per seed "
        + str([(x.seed, x.lost_skip, x.lost_talk) for x in r.retain]),
    ]
    cost, ratio = t3(r)
    reached = sum(1 for x in r.promise if x.morale_cost is not None)
    rows.append(
        f"T3 a broken promised promotion ({reached}/{len(r.promise)} seeds reached it): morale "
        + ("-" if cost is None else f"-{cost:.1f}")
        + f" at least (>= {T3_MORALE:g}), resignation chance x"
        + ("-" if ratio is None else f"{ratio:.2f}")
        + f" at least (>= {T3_LEAVE:g})"
    )
    brand, ic, idf = t4(r)
    rows.append(
        "T4 a class I recall: brand regained in "
        f"{T4_AFTER} months, candour / deflection "
        + ("-" if brand is None else f"{brand:.2f}x")
        + f" (median, >= {T4_FASTER:g}x); inspection chance {ic:.0%} after candour, {idf:.0%} "
        "after deflection; per seed (hit, candour, deflect) "
        + str(
            [(x.seed, round(x.hit, 1), round(x.candour, 1), round(x.deflect, 1)) for x in r.crisis]
        )
    )
    return "\n".join(rows)


def met(r: Results) -> dict[str, bool]:
    kept, _s, _t = t2(r)
    cost, ratio = t3(r)
    brand, ic, idf = t4(r)
    return {
        "t2": kept is not None and kept >= T2_KEPT,
        "t3": cost is not None
        and cost >= T3_MORALE - EPS
        and ratio is not None
        and ratio >= T3_LEAVE - EPS,
        "t4": brand is not None and brand >= T4_FASTER and idf > ic,
    }


if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else len(SEEDS)
    results = run(SEEDS[:n])
    print(report(results))
    print(met(results))
