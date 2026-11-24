"""docs/formulas.md 59.4 targets 2 and 3 (M48), printed with their values. Target 1 (skip is
today's game) is M30's state cache and the golden snapshots: a game that never holds a meeting
runs no meeting code. Target 4 (no leak) is tests/integration/test_m48_meetings.py.

- T2 talking helps, within limits: M13's listed company (the steady script) played 60 months
  on 10 seeds three ways: skipping every meeting; holding every board meeting and earnings call
  with a sensible script as a good communicator (score 16); and as a poor one (score 6). The
  mean over the 60 month ends of the board's average confidence and of sentiment, against
  skipping: good +3 to +10 points and +2% to +6%; poor 0 to 8 points lower.
- T3 credibility matters: the same company raising guidance on every call until three guidance
  promises have broken within 24 months; the next call's gains against the same call at the
  neutral credibility (press.cred_start, 50): at most half.

The sensible script: explain each question with its first fact; concede a real problem; commit
to the board's plan figure only when last quarter's revenue already reaches it; on the call,
reaffirm guidance, or lower it after a miss.
"""

from __future__ import annotations

import os
import statistics
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from typing import Final

from tst.balance.game import PLAYER, Game
from tst.balance.m13 import listed_game
from tst.balance.strategies import steady
from tst.sim.finance.board import average_confidence
from tst.sim.meetings import agenda, engine
from tst.sim.meetings.actions import outcome_action
from tst.sim.meetings.agenda import founder_factor
from tst.sim.meetings.models import Item, Meeting, Move
from tst.sim.press.moments import credibility
from tst.sim.rng import RngFactory
from tst.sim.state import guidance_for, public_of

SEEDS: tuple[int, ...] = tuple(range(1, 11))
MONTHS: Final = 60
STRONG: Final = 16.0
WEAK: Final = 6.0
T2_GOOD_CONF: Final = (3.0, 10.0)
T2_GOOD_SENT: Final = (0.02, 0.06)
T2_POOR_CONF: Final = (0.0, 8.0)  # points lower than skipping
T3_BROKEN: Final = 3
T3_WINDOW: Final = 24
T3_CUT: Final = 0.5
ROUNDING: Final = (
    1e-3  # a share is stored to 6 digits (engine.SHARE_DIGITS): the ratio of two small ones
)

type Script = Callable[[Meeting, Item, Game], tuple[Move, ...]]


def sensible(m: Meeting, item: Item, game: Game) -> tuple[Move, ...]:
    moves = [Move("explain", 0)]
    if item.problem:
        moves.append(Move("concede"))
    if item.guidance:
        g = guidance_for(game.state, PLAYER, game.state.turn - 3)
        moves.append(Move("lower" if g is not None and g.result == "miss" else "reaffirm"))
    elif item.figure is not None and item.figure.metric == "revenue" and m.kind == "board":
        if agenda.quarter_revenue(game.state, PLAYER) >= item.figure.value:
            moves.append(Move("commit"))
    return tuple(moves)


def raiser(m: Meeting, item: Item, game: Game) -> tuple[Move, ...]:
    return (Move("explain", 0), Move("raise")) if item.guidance else (Move("explain", 0),)


def hold(game: Game, kind: str, score: float, script: Script) -> Meeting | None:
    """This month's meeting of `kind` played by `script` at founder score `score`, its outcome
    applied; None when none is due."""
    state = game.state
    b = game.loaded.balance
    if agenda.problem(state, kind, b) is not None:  # type: ignore[arg-type]
        return None
    m = agenda.open_meeting(
        state,
        kind,  # type: ignore[arg-type]
        RngFactory(state.save_meta.master_seed),
        b,
        game.loaded.game_data,
        game.cash,
    )
    skills = {k: score for k in b.meetings.skill.weights}
    m = replace(m, hidden=replace(m.hidden, skill=founder_factor(skills, b.meetings)))
    while m.status == "open":
        item = m.next_item
        assert item is not None
        m = engine.play_item(m, script(m, item, game), b.meetings)
    game.act(outcome_action(m, game.founder_id))
    return m


@dataclass(frozen=True, slots=True)
class Run:
    seed: int
    mode: str
    confidence: float  # mean of the month ends' average board confidence
    sentiment: float  # mean of the month ends' sentiment
    meetings: int


def run_one(job: tuple[int, str]) -> Run:
    seed, mode = job
    game = listed_game(seed)
    conf: list[float] = []
    sent: list[float] = []
    held = 0
    for _ in range(MONTHS):
        if mode != "skip":
            score = STRONG if mode == "strong" else WEAK
            for kind in ("board", "call"):
                if hold(game, kind, score, sensible) is not None:
                    held += 1
        steady(game)
        game.turn()
        if game.state.ended:
            break
        avg = average_confidence(game.state, PLAYER)
        public = public_of(game.state, PLAYER)
        conf.append(avg if avg is not None else 0.0)
        sent.append(public.sentiment if public is not None else 1.0)
    return Run(seed, mode, statistics.fmean(conf), statistics.fmean(sent), held)


@dataclass(frozen=True, slots=True)
class CredRun:
    seed: int
    broken: int  # guidance promises broken in the window
    credibility: float  # when the measured call opened
    ratio: float | None  # its gains against the same call at the starting credibility


def _gain(m: Meeting, game: Game) -> float:
    """One answer's sentiment gain (the first question, explained): below the call's clamp."""
    played = replace(m, items=m.items[:1])
    b = game.loaded.balance.meetings
    while played.status == "open":
        item = played.next_item
        assert item is not None
        played = engine.play_item(played, (Move("explain", 0),), b)
    assert played.effects is not None
    return played.effects.sentiment


def run_cred(seed: int) -> CredRun:
    game = listed_game(seed)
    b = game.loaded.balance
    start = float(b.press.cred_start)  # whole gains (59.2: full from meetings.credibility.full_at)
    first = game.state.turn
    while game.state.turn - first < T3_WINDOW + 3:
        broken = [
            p
            for p in game.state.promises
            if p.kind == "guidance" and p.status == "broken" and p.resolved_turn is not None
        ]
        if len(broken) >= T3_BROKEN and agenda.problem(game.state, "call", b) is None:
            span = max(p.resolved_turn or 0 for p in broken) - min(
                p.resolved_turn or 0 for p in broken
            )
            if span <= T3_WINDOW:
                m = agenda.open_meeting(
                    game.state,
                    "call",
                    RngFactory(game.state.save_meta.master_seed),
                    b,
                    game.loaded.game_data,
                    game.cash,
                )
                low = _gain(m, game)
                full = _gain(replace(m, credibility=start), game)
                ratio = low / full if full > 0 else None
                return CredRun(seed, len(broken), m.credibility, ratio)
        hold(game, "call", STRONG, raiser)
        steady(game)
        game.turn()
        if game.state.ended:
            break
    broken_n = sum(1 for p in game.state.promises if p.kind == "guidance" and p.status == "broken")
    return CredRun(seed, broken_n, credibility(game.state, PLAYER, b), None)


@dataclass(frozen=True, slots=True)
class Results:
    runs: tuple[Run, ...]
    cred: tuple[CredRun, ...]


def run(seeds: Sequence[int] = SEEDS, jobs: int = os.cpu_count() or 1) -> Results:
    todo = [(s, mode) for s in seeds for mode in ("skip", "strong", "weak")]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        runs = tuple(pool.map(run_one, todo))
        cred = tuple(pool.map(run_cred, seeds))
    return Results(runs, cred)


def _by(r: Results, mode: str) -> dict[int, Run]:
    return {x.seed: x for x in r.runs if x.mode == mode}


def t2(r: Results) -> tuple[float, float, float, float]:
    """(good's confidence gain, good's sentiment gain, poor's confidence loss, poor's
    sentiment change), medians over the seeds."""
    skip, good, poor = _by(r, "skip"), _by(r, "strong"), _by(r, "weak")
    seeds = sorted(skip)
    return (
        statistics.median(good[s].confidence - skip[s].confidence for s in seeds),
        statistics.median(good[s].sentiment / skip[s].sentiment - 1 for s in seeds),
        statistics.median(skip[s].confidence - poor[s].confidence for s in seeds),
        statistics.median(poor[s].sentiment / skip[s].sentiment - 1 for s in seeds),
    )


def t3(r: Results) -> float | None:
    ratios = [c.ratio for c in r.cred if c.ratio is not None]
    return max(ratios) if ratios else None


def report(r: Results) -> str:
    gc, gs, pc, ps = t2(r)
    rows = [
        f"T2 good communicator (score {STRONG:g}): board confidence {gc:+.1f} points "
        f"({T2_GOOD_CONF[0]:g} to {T2_GOOD_CONF[1]:g}), sentiment {gs:+.1%} "
        f"({T2_GOOD_SENT[0]:.0%} to {T2_GOOD_SENT[1]:.0%}) over {MONTHS} months against skipping",
        f"T2 poor communicator (score {WEAK:g}): board confidence {pc:.1f} points lower "
        f"({T2_POOR_CONF[0]:g} to {T2_POOR_CONF[1]:g}), sentiment {ps:+.1%}",
    ]
    worst = t3(r)
    reached = sum(1 for c in r.cred if c.ratio is not None)
    rows.append(
        f"T3 after {T3_BROKEN} broken guidance promises within {T3_WINDOW} months ({reached}/"
        f"{len(r.cred)} seeds reached it): the next call's gains at most "
        + ("-" if worst is None else f"{worst:.0%}")
        + f" of the same call's at credibility 50 (<= {T3_CUT:.0%}); credibility then "
        + str([round(c.credibility) for c in r.cred])
    )
    return "\n".join(rows)


def met(r: Results) -> dict[str, bool]:
    gc, gs, pc, _ps = t2(r)
    worst = t3(r)
    return {
        "t2_good": T2_GOOD_CONF[0] <= gc <= T2_GOOD_CONF[1]
        and T2_GOOD_SENT[0] <= gs <= T2_GOOD_SENT[1],
        "t2_poor": T2_POOR_CONF[0] <= pc <= T2_POOR_CONF[1],
        "t3": worst is not None and worst <= T3_CUT + ROUNDING,  # exactly half meets it
    }


if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else len(SEEDS)
    results = run(SEEDS[:n])
    print(report(results))
    print(met(results))
