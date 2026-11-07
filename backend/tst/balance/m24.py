"""docs/formulas.md 32.7 targets (M24, lane C), printed with their values. Target 1 (a founder
who never strains changes nothing) is the property test in tests/unit/test_m24_stress.py
plus the nightly guard suite itself; here it is the share of the scripted strategies' months
above stress.comfort and their burnouts.

- T2 burnout is real but avoidable: the `burnout_test` script arm, a founder alone who spends
  a share of each month's energy (do-nothing's company, so only stress differs): `all` spends
  everything every month; `holiday` spends at most 0.8 and takes a Holiday month twice a
  year (months 5 and 11). Months to the first burnout; burnouts in 10 years.
- T3 personas diverge: blitzscale and steady, 10 seeds, the top trait at year 10, counted
  only when it leads the next trait by T3_LEAD (5) points (product manager, 2026-11-07).
- T4 influence helps, with a price: $500k a month of lobbying in North America for 5 years
  (then stopped) on 10 seeds: the antitrust cut there at year 5, and seeds with a scandal in
  10 years. Lobbying's phase alone (it reads only the company and its founder's traits).
- T5 giving is visible but small: a foundation granting $10M a year: hiring appeal and Beloved.
"""

from __future__ import annotations

import os
import statistics
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.m13 import _loaded
from tst.balance.strategies import STRATEGIES
from tst.sim.decisions import Decisions
from tst.sim.founder import foundation, influence
from tst.sim.founder.effects import education_points
from tst.sim.founder.models import Foundation, Influence
from tst.sim.founder.stress import new_life
from tst.sim.ledger import apply_entries
from tst.sim.rng import RngFactory
from tst.sim.state import (
    influence_of,
    life_of,
    with_foundation,
    with_influence,
    with_life,
    with_person_state,
)
from tst.sim.turn import advance_turn

SEEDS: tuple[int, ...] = tuple(range(1, 11))
YEARS = 10
TURNS = 12 * YEARS
HOLIDAY_MONTHS = (5, 11)  # turn % 12: a Holiday month twice a year (T2)
HOLIDAY_USE = 0.8
LOBBY_DOLLARS = 500_000
LOBBY_YEARS = 5
LOBBY_REGION = "north_america"
GRANT_CENTS = 10_000_000_00  # $10M a year (T5)
# T3's measure (product manager, 2026-11-07): a top trait counts only when it leads the next
# by at least this many points; a tie or a near-tie counts for neither half. Without it, a
# founder whose traits all sat at 20 "had" Visionary by the tie order.
T3_LEAD = 5.0
REAL = ("reckless", "ruthless")
KIND = ("beloved", "visionary")


# --- T2: the burnout_test arm ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BurnRun:
    arm: str
    seed: int
    first_burnout: int | None  # months played to the first burnout
    burnouts: int


def _spend(game: Game, use: float) -> None:
    """The founder spends `use` of this month's budget (as a month of work would)."""
    founder = game.founder_id
    life = life_of(game.state, founder)
    ps = game.state.person_state(founder)
    budget = life.budget if life is not None and life.budget is not None else ps.energy or 0
    left = round(budget * (1 - use))
    game.state = with_person_state(game.state, replace(ps, energy=min(ps.energy or 0, left)))


def _turn(game: Game, holiday: bool) -> None:
    """Game.turn with the month's Holiday flag (Decisions.holiday); events as Game.turn."""
    from tst.sim.actions import ChooseEvent

    for event in game.state.open_events(PLAYER):
        if event.severity == "critical" and event.status == "open":
            game.act(ChooseEvent(game.founder_id, event.id, event.choices[0].key))
    result = advance_turn(
        game.state,
        Decisions(holiday=holiday),
        RngFactory(game.state.save_meta.master_seed),
        game.loaded.balance,
        game.loaded.game_data,
        game.balances,
    )
    game.state = result.new_state
    game.balances = apply_entries(game.balances, result.ledger_entries)
    game._write_events(result.snapshot.for_company(PLAYER))


def play_burnout(arm: str, seed: int) -> BurnRun:
    game = start_game(_loaded(), seed)
    first: int | None = None
    for month in range(TURNS):
        if game.state.ended:
            break
        away = arm == "holiday" and game.state.turn % 12 in HOLIDAY_MONTHS
        if not away:
            _spend(game, 1.0 if arm == "all" else HOLIDAY_USE)
        _turn(game, away)
        life = life_of(game.state, game.founder_id)
        if first is None and life is not None and life.burnouts:
            first = month + 1
        if arm == "all" and first is not None:
            break
    life = life_of(game.state, game.founder_id)
    return BurnRun(arm, seed, first, life.burnouts if life is not None else 0)


# --- T1 and T3: the scripted strategies ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PersonaRun:
    strategy: str
    seed: int
    top: str | None  # None: no trait leads the next by T3_LEAD
    traits: tuple[tuple[str, float], ...]
    strained: int  # months above stress.comfort (T1)
    months: int
    burnouts: int


def play_persona(strategy: str, seed: int) -> PersonaRun:
    game = start_game(_loaded(), seed)
    comfort = game.loaded.balance.stress.comfort
    strained = months = 0
    for _ in range(TURNS):
        if game.state.ended:
            break
        STRATEGIES[strategy](game)
        life = life_of(game.state, game.founder_id)
        ps = game.state.person_state(game.founder_id)
        budget = life.budget if life is not None and life.budget else None
        if budget:
            months += 1
            strained += (budget - (ps.energy or 0)) / budget > comfort
        game.turn()
    life = life_of(game.state, game.founder_id) or new_life(0, game.loaded.balance)
    traits = tuple(
        (t, round(life.trait(t), 1)) for t in ("visionary", "ruthless", "beloved", "reckless")
    )
    return PersonaRun(strategy, seed, clear_top(traits), traits, strained, months, life.burnouts)


def clear_top(traits: Sequence[tuple[str, float]]) -> str | None:
    """The top trait when it leads the next by at least T3_LEAD, else None (T3)."""
    ranked = sorted(traits, key=lambda kv: -kv[1])
    if len(ranked) < 2 or ranked[0][1] - ranked[1][1] < T3_LEAD:
        return None
    return ranked[0][0]


def run_personas(seeds: Sequence[int] = SEEDS, jobs: int = os.cpu_count() or 1) -> list[PersonaRun]:
    persona_jobs = [(st, s) for st in ("blitzscale", "steady") for s in seeds]
    with ProcessPoolExecutor(max(1, jobs)) as ex:
        return list(ex.map(_persona, persona_jobs))


# --- T4: lobbying --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LobbyRun:
    seed: int
    influence_at_5: float
    cut_at_5: float  # the antitrust block chance's cut there at year 5
    scandals: int


def play_lobby(seed: int) -> LobbyRun:
    loaded = _loaded()
    b, d = loaded.balance, loaded.game_data
    state = start_game(loaded, seed).state
    state = with_influence(
        state,
        Influence(PLAYER, LOBBY_REGION, spend_cents=LOBBY_DOLLARS * 100, started_turn=0),
    )
    scandals = 0
    at5 = 0.0
    cut = 0.0
    for t in range(TURNS):
        if t == 12 * LOBBY_YEARS:
            record = influence_of(state, PLAYER, LOBBY_REGION)
            assert record is not None
            at5 = record.value
            cut = 1 - influence.antitrust_factor(state, PLAYER, LOBBY_REGION, b)
            state = with_influence(state, replace(record, spend_cents=0))
        state = replace(state, turn=t)
        state, _, logs = influence.lobbying_month(state, RngFactory(seed), b, d)
        scandals += sum(1 for log in logs if log.template == "scandal_broke")
    return LobbyRun(seed, at5, cut, scandals)


# --- T5: giving ---------------------------------------------------------------------------------


def giving() -> tuple[float, float]:
    """A foundation granting $10M in a December: (hiring appeal, Beloved gained)."""
    loaded = _loaded()
    b = loaded.balance
    state = start_game(loaded, 1).state
    fid = state.founder_of(PLAYER).id  # type: ignore[union-attr]
    state = with_life(state, new_life(fid, b))
    state = with_foundation(state, Foundation(fid, "F", "education", 0, region=LOBBY_REGION))
    from tst.sim.founder import personal

    state = personal.credit(state, fid, round(GRANT_CENTS / b.foundation.payout), "exit")
    state = personal.gift(state, fid, round(GRANT_CENTS / b.foundation.payout))
    state = replace(state, turn=11)
    out, _ = foundation.grants_month(state, b)
    life = life_of(out, fid)
    assert life is not None
    return education_points(out, PLAYER, b), life.beloved - b.persona.start


# --- Run and report ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Results:
    burn: tuple[BurnRun, ...]
    personas: tuple[PersonaRun, ...]
    lobby: tuple[LobbyRun, ...]
    hiring: float
    beloved: float


def _burn(args: tuple[str, int]) -> BurnRun:
    return play_burnout(*args)


def _persona(args: tuple[str, int]) -> PersonaRun:
    return play_persona(*args)


def run(seeds: Sequence[int] = SEEDS, jobs: int = os.cpu_count() or 1) -> Results:
    burn_jobs = [(arm, s) for arm in ("all", "holiday") for s in seeds]
    persona_jobs = [(st, s) for st in ("blitzscale", "steady") for s in seeds]
    with ProcessPoolExecutor(max(1, jobs)) as ex:
        burn = tuple(ex.map(_burn, burn_jobs))
        personas = tuple(ex.map(_persona, persona_jobs))
        lobby = tuple(ex.map(play_lobby, seeds))
    hiring, beloved = giving()
    return Results(burn, personas, lobby, hiring, beloved)


def t1_strained(r: Results) -> float:
    months = sum(p.months for p in r.personas)
    return sum(p.strained for p in r.personas) / months if months else 0.0


def t1_burnouts(r: Results) -> int:
    return sum(p.burnouts for p in r.personas)


def t2_all(r: Results) -> list[int | None]:
    return [b.first_burnout for b in r.burn if b.arm == "all"]


def t2_holiday_max(r: Results) -> int:
    return max(b.burnouts for b in r.burn if b.arm == "holiday")


def t3_count(r: Results, strategy: str, traits: tuple[str, ...]) -> int:
    return sum(1 for p in r.personas if p.strategy == strategy and p.top in traits)


def t4_cut(r: Results) -> float:
    return statistics.mean(x.cut_at_5 for x in r.lobby)


def t4_scandal_seeds(r: Results) -> int:
    return sum(1 for x in r.lobby if x.scandals)


def report(r: Results) -> str:
    lines = ["formulas.md 32.7 targets (M24)"]
    lines.append(
        f"T1 scripted strategies: {t1_strained(r):.1%} of months above comfort; "
        f"{t1_burnouts(r)} burnouts in {len(r.personas)} 10-year runs"
    )
    lines.append(f"T2 all energy: first burnout in months {t2_all(r)} (target 3-6)")
    lines.append(
        f"T2 holiday twice a year, use 0.8: at most {t2_holiday_max(r)} burnout(s) in 10 years "
        "(target <= 1)"
    )
    for st, want in (("blitzscale", REAL), ("steady", KIND)):
        tops = [p.top for p in r.personas if p.strategy == st]
        lines.append(
            f"T3 {st}: top trait {'/'.join(want)} on {t3_count(r, st, want)} of {len(tops)} "
            f"(target >= 6); tops {tops}"
        )
    for p in r.personas:
        lines.append(f"   {p.strategy:<10} seed {p.seed:>2}: {dict(p.traits)}")
    lines.append(
        f"T4 antitrust cut at year 5: {t4_cut(r):.0%} (target 20-40%); influence "
        f"{[round(x.influence_at_5, 1) for x in r.lobby]}"
    )
    lines.append(
        f"T4 seeds with a scandal in 10 years: {t4_scandal_seeds(r)} of {len(r.lobby)} "
        f"(target 3-7); scandals {[x.scandals for x in r.lobby]}"
    )
    lines.append(
        f"T5 $10M a year: hiring appeal +{r.hiring:.3f} (target <= 0.03); Beloved "
        f"+{r.beloved:.1f} (target 5-10)"
    )
    return "\n".join(lines)
