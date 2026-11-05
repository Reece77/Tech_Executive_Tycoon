"""docs/formulas.md 29.7 targets 2-5 (M14b), printed with their values. Target 1 (nothing else
moves) is the nightly guard suite itself.

- T2 promises matter: a listed company (M13's e2e scale-up, listed) over 24 months on 10
  seeds in three arms: no promises, three kept, three broken (made and resolved in months 14,
  17 and 20 so their effects run at month 24). Brand is the product's at month 24; the
  sentiment is the listed company's.
- T3 the inbox stays calm: press moments shown a year (median) in 10-year steady runs.
- T4 rivalries happen: 10-year steady runs whose founder answers every press moment boldly;
  seeds where a feud reaches rivalry, and how much that rival's moves against the player's
  products rise in a rivalry over its months before.
- T5 Replace helps: months from a resignation to the replacement's hire, Replace with a
  recruiter against a normal recruiter-channel plan, 10 seeds.
"""

from __future__ import annotations

import os
import statistics
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.m13 import _loaded, listed_game
from tst.balance.strategies import steady
from tst.sim.actions import ChooseEvent, CreatePlan, ReplaceLeaver, SetMarketing
from tst.sim.hiring.models import PersonState
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.press import promises
from tst.sim.press.models import Promise
from tst.sim.rivals.characters import SELLING
from tst.sim.rng import RngFactory
from tst.sim.state import (
    public_of,
    with_employment,
    with_person,
    with_person_state,
    with_promise,
)

SEEDS: tuple[int, ...] = tuple(range(1, 11))
T2_MONTHS = 24
T2_AT = (14, 17, 20)
T2_AMBITION = 0.5
T2_MARKETING = 10_000_000  # cents a month a product: $100,000
YEARS = 10
TURNS = 12 * YEARS
AGAINST = ("price_cut", "feature_push", "quality_push", "brand_push", "poach")
T5_MONTHS = 8


# --- T2 ----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PromiseRun:
    arm: str
    seed: int
    brands: tuple[tuple[int, float], ...]  # (product id, brand) at month 24
    sentiment: float


def target_2_run(job: tuple[str, int]) -> PromiseRun:
    """Marketing is held at T2_MARKETING a product in every arm, so a product's brand sits
    below the cap and a brand-target change can show."""
    arm, seed = job
    game = listed_game(seed)
    for month in range(T2_MONTHS):
        if arm != "none" and month in T2_AT:
            pid, ids = game.state.next_ids.take("promise")
            p = Promise(
                pid,
                PLAYER,
                "no_layoffs",
                game.state.turn,
                game.state.turn,
                ambition=T2_AMBITION,
                audience=1.5,  # tunable-exempt: listed
            )
            game.state = with_promise(replace(game.state, next_ids=ids), p)
            game.state, _ = promises.resolve(
                game.state,
                p,
                "kept" if arm == "kept" else "broken",
                game.loaded.balance,
                game.loaded.game_data,
                reminder_in=1,
            )
        for product in game.state.company_products(PLAYER):
            if product.status in SELLING:
                game.act(SetMarketing(game.founder_id, product.id, T2_MARKETING))
        game.turn()
    live = [p for p in game.state.company_products(PLAYER) if p.status in SELLING]
    public = public_of(game.state, PLAYER)
    return PromiseRun(
        arm,
        seed,
        tuple((p.id, p.brand) for p in live),
        public.sentiment if public else 1.0,
    )


# --- T3 and T4 ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PressRun:
    bold: bool
    seed: int
    moments_a_year: float
    rivalry: bool
    lift: float | None  # that rival's moves against the player a month, in rivalry / before


def _answer_press(game: Game, tone: str) -> None:
    for event in game.state.open_events(PLAYER):
        if event.category == "press" and event.status == "open" and event.choices:
            key = next(
                (c.key for c in event.choices for e in c.effects if e.stat == tone),
                event.choices[0].key,
            )
            game.act(ChooseEvent(game.founder_id, event.id, key))


def target_34_run(job: tuple[bool, int]) -> PressRun:
    bold, seed = job
    game = start_game(_loaded(), seed, "funded_spinout", "standard")
    moves: list[tuple[int, int, str]] = []  # (turn, rival, action) against the player
    for _ in range(TURNS):
        if game.state.ended:
            break
        _answer_press(game, "bold" if bold else "measured")
        steady(game)
        game.turn()
        mine = {
            (p.category, s.segment)
            for p in game.state.company_products(PLAYER)
            if p.status in SELLING
            for s in game.state.segments_of(p.id)
        }
        for m in game.state.rival_moves:
            if m.turn != game.state.turn - 1 or m.action not in AGAINST:
                continue
            product = game.state.product(m.product_id) if m.product_id else None
            if m.action == "poach" or (product and (product.category, m.segment) in mine):
                moves.append((m.turn, m.company_id, m.action))
    years = max(1.0, game.state.turn / 12)  # tunable-exempt: months a year
    feud = max(
        (f for f in game.state.feuds if f.rivalry_turn is not None),
        key=lambda f: f.score,
        default=None,
    )
    lift = None
    if feud is not None and feud.rivalry_turn is not None:
        at = feud.rivalry_turn
        before = sum(1 for t, r, _ in moves if r == feud.rival_id and t < at) / max(1, at)
        span = max(1, game.state.turn - at)
        after = sum(1 for t, r, _ in moves if r == feud.rival_id and t >= at) / span
        lift = after / before - 1 if before > 0 else None
    shown = sum(1 for e in game.state.events if e.category == "press")  # in memory: all kept
    return PressRun(bold, seed, shown / years, feud is not None, lift)


# --- T5 ----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FillRun:
    replace: bool
    seed: int
    months: int | None


def _staffed(seed: int) -> tuple[Game, int, int]:
    """A company with a senior engineer about to leave and a recruiter on staff."""
    game = start_game(_loaded(), seed, "funded_spinout", "standard")
    data, balance = game.loaded.game_data, game.loaded.balance
    ids = []
    state = game.state
    for role, level in (("software_engineer", "senior"), ("recruiter", "mid")):
        pid, nids = state.next_ids.take("person")
        eid, nids = nids.take("employment")
        state = replace(state, next_ids=nids)
        gen = RngFactory(seed).stream(0, "misc", pid)
        person = generate_person(
            gen, data, balance, state.turn, data.role(role), level, "north_america", person_id=pid
        )
        state = with_person(state, person)
        state = with_employment(
            state,
            Employment(
                id=eid,
                person_id=pid,
                company_id=PLAYER,
                role=role,
                level=level,
                salary_cents=12_000_000,
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
            ),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=65.0))
        ids.append(pid)
    leaver, recruiter = ids
    e = state.employment_of(leaver)
    assert e is not None
    state = with_employment(
        state, replace(e, status="notice", end_turn=state.turn + 1, end_reason="resigned")
    )
    game.state = state
    return game, leaver, recruiter


def target_5_run(job: tuple[bool, int]) -> FillRun:
    use_replace, seed = job
    game, leaver, recruiter = _staffed(seed)
    start = game.state.turn
    if use_replace:
        assert game.act(ReplaceLeaver(game.founder_id, leaver))
    else:
        ratio = game.loaded.balance.recruit.replace_ratio_bp
        plan = CreatePlan(game.founder_id, recruiter, "software_engineer", 1, "recruiter", ratio)
        assert game.act(plan)
    for _ in range(T5_MONTHS):
        game.turn()
        hired = [
            e
            for e in game.state.staff(PLAYER)
            if e.role == "software_engineer" and e.person_id != leaver and e.start_turn > start
        ]
        if hired:
            return FillRun(use_replace, seed, min(e.start_turn for e in hired) - start)
    return FillRun(use_replace, seed, None)


# --- Run and report -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Results:
    t2: tuple[PromiseRun, ...]
    t34: tuple[PressRun, ...]
    t5: tuple[FillRun, ...]


def run(seeds: Sequence[int] = SEEDS, jobs: int = os.cpu_count() or 1) -> Results:
    with ProcessPoolExecutor(max(1, jobs)) as pool:
        arms = [(a, n) for a in ("none", "kept", "broken") for n in seeds]
        t2 = tuple(pool.map(target_2_run, arms))
        t34 = tuple(pool.map(target_34_run, [(b, n) for b in (False, True) for n in seeds]))
        t5 = tuple(pool.map(target_5_run, [(r, n) for r in (False, True) for n in seeds]))
    return Results(t2, t34, t5)


def _median(xs: Sequence[float]) -> float:
    return statistics.median(xs) if xs else float("nan")


def t2_brand(r: Results, arm: str) -> float:
    """Per seed, the product with the most headroom in the no-promise arm (the lowest brand),
    compared across arms."""
    out = []
    for x in r.t2:
        if x.arm != arm:
            continue
        base = dict(next(b.brands for b in r.t2 if b.arm == "none" and b.seed == x.seed))
        if not base:
            continue
        pid = min(base, key=lambda k: base[k])
        out.append(dict(x.brands).get(pid, 0.0) - base[pid])
    return _median(out)


def t2_sentiment(r: Results) -> float:
    base = {x.seed: x.sentiment for x in r.t2 if x.arm == "none"}
    return _median([1 - x.sentiment / base[x.seed] for x in r.t2 if x.arm == "broken"])


def t3_moments(r: Results) -> float:
    return _median([x.moments_a_year for x in r.t34 if not x.bold])


def t4_rivalries(r: Results) -> int:
    return sum(1 for x in r.t34 if x.bold and x.rivalry)


def t4_lift(r: Results) -> float:
    return _median([x.lift for x in r.t34 if x.bold and x.lift is not None])


def t5_shorter(r: Results) -> float:
    normal = _median([float(x.months) for x in r.t5 if not x.replace and x.months is not None])
    fast = _median([float(x.months) for x in r.t5 if x.replace and x.months is not None])
    return 1 - fast / normal if normal else float("nan")


def report(r: Results) -> str:
    fills = [(x.replace, x.months) for x in r.t5]
    return "\n".join(
        [
            f"T2 three kept promises: brand {t2_brand(r, 'kept'):+.1f} at 24 months (+5 to +15); "
            f"three broken {t2_brand(r, 'broken'):+.1f} (-10 to -25), sentiment "
            f"{t2_sentiment(r):.0%} lower (5-15%)",
            f"T3 press moments a year (median, steady): {t3_moments(r):.1f} (<= 6)",
            f"T4 bold steady runs with a rivalry: {t4_rivalries(r)}/"
            f"{sum(1 for x in r.t34 if x.bold)} (5-9); that rival's moves against the player "
            f"{t4_lift(r):+.0%} in rivalry (20-60%)",
            f"T5 Replace fills {t5_shorter(r):.0%} sooner (30-50%); months {fills}",
        ]
    )
