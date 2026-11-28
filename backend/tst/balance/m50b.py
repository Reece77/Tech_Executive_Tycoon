"""M50b (the 2000 start, formulas.md 60.4-60.7): readings and the 2008/2010 guard.

The guard (brief, "Lane"): a 2008 game and a 2010 game are identical to `main` before M50b.
`identity_hashes` plays M30's strategies from January 2008 and January 2010 on seeds 1-2 in
memory and digests the full state and ledger balances after every month (M30's digester);
`tests/fixtures/m50b_identity_hashes.json` holds the digests recorded on `main` before any
M50b change (`tools/m50b_identity.py --write`), and the nightly test compares with them.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Final

from tst.balance import m30, m50
from tst.balance.game import Game
from tst.loader import LoadedData
from tst.sim.calendar import format_turn, ym_to_turn

IDENTITY_SEEDS: Final = (1, 2)
IDENTITY_STRATEGIES: Final = ("full_integrator", "research_heavy")
IDENTITY_YEARS: Final = (2008, 2010)
IDENTITY_MONTHS: Final = 120  # ten years from each start (2008-2017, 2010-2019)
IDENTITY_FILE: Final = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "m50b_identity_hashes.json"
)

type Job = tuple[str, int, int]  # strategy, seed, start year


def identity_key(job: Job) -> str:
    name, seed, year = job
    return f"{year}/{name}/{seed}"


def identity_jobs() -> list[Job]:
    return [
        (name, seed, year)
        for year in IDENTITY_YEARS
        for name in IDENTITY_STRATEGIES
        for seed in IDENTITY_SEEDS
    ]


def identity_run(job: Job, months: int = IDENTITY_MONTHS) -> list[str]:
    """One strategy's game from January of its start year: a digest after every month."""
    name, seed, year = job
    game = m50.start(seed, year)
    script = m30.strategy(name)
    digester = m30.Digester()
    out: list[str] = []
    while len(out) < months and not game.state.ended:
        script(game)
        game.turn()
        out.append(m30.month_digest(digester, game))
    return out


def identity_hashes(workers: int = 1, months: int = IDENTITY_MONTHS) -> m30.Hashes:
    todo = identity_jobs()
    if workers <= 1:
        return {identity_key(j): identity_run(j, months) for j in todo}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        runs = pool.map(identity_run, todo, [months] * len(todo))
        return {identity_key(j): r for j, r in zip(todo, runs, strict=True)}


def identity_recorded() -> m30.Hashes:
    out: m30.Hashes = json.loads(IDENTITY_FILE.read_text(encoding="utf-8"))
    return out


def identity_write(hashes: m30.Hashes) -> None:
    text = json.dumps(hashes, indent=0, sort_keys=True) + "\n"
    IDENTITY_FILE.write_text(text, encoding="utf-8", newline="\n")


def identity_differences(got: m30.Hashes, want: m30.Hashes) -> list[str]:
    return [
        f"{k}: {d}"
        for k in sorted(want)
        if (d := m30.first_difference(got.get(k, []), want[k])) is not None
    ]


# --- 60.7 targets ------------------------------------------------------------------------------

SEEDS: Final = tuple(range(1, 11))
BAND: Final = (0.7, 1.3)  # 60.7 target 1, as 60.3 target 3
JAN_2008: Final = ym_to_turn(2008, 1)
JAN_2010: Final = ym_to_turn(2010, 1)
BUST: Final = "survive_the_bust"  # scenarios.yaml (60.6)
BUST_IPO_FAILS: Final = 6  # 60.7 target 2: the IPO-dependent passive plan fails on >= 6 of 10
BUST_SURVIVES: Final = 7  # ... and the sensible one survives on >= 7
CAMPAIGN_SEEDS: Final = (1, 2, 3)  # 60.7 target 3
CAMPAIGN_END: Final = ym_to_turn(2029, 12)  # a 2000 campaign's standard end
CAMPAIGN_STRATEGY: Final = "steady+cuts"  # v1's steady founder, cutting when short (60.7 T3)


@dataclass(slots=True)
class Snapshot:
    """A world's category sizes and the named rivals' customers in one month."""

    markets: dict[str, float] = field(default_factory=dict)
    customers: dict[str, float] = field(default_factory=dict)


def snapshot(game: Game) -> Snapshot:
    st = game.state
    out = Snapshot()
    sizes = [(m.category, m.addressable) for m in st.markets]
    sizes += [(m.category, m.addressable) for m in st.regional_markets]
    for category, addressable in sizes:
        out.markets[category] = out.markets.get(category, 0.0) + addressable
    named = _named(game.loaded)
    by_company = {c.id: c.name for c in st.companies if c.name in named and c.alive}
    for p in st.products:
        name = by_company.get(p.company_id)
        if name is None:
            continue
        n = sum(s.customers for s in st.segments_of(p.id))
        n += sum(s.customers for s in st.regional_segments_of(p.id))
        out.customers[name] = out.customers.get(name, 0.0) + n
    return out


def _named(data: LoadedData) -> set[str]:
    """M50's named v1 incumbents, less the 2000 world's own companies."""
    from tst.balance.m50 import _named as m50_named

    own = {i.name for i in data.game_data.incumbents if i.history_only}
    return m50_named(data) - own


def world_job(job: tuple[int, int]) -> dict[int, Snapshot]:
    """An idle world from January of `year`: snapshots in January 2008 and January 2010."""
    seed, year = job
    game = m50.start(seed, year)
    out: dict[int, Snapshot] = {}
    while game.state.turn <= JAN_2010:
        if game.state.turn in (JAN_2008, JAN_2010):
            out[game.state.turn] = snapshot(game)
        if game.state.turn == JAN_2010:
            break
        game.turn()
    return out


def _ratio(a: dict[str, float], b: dict[str, float]) -> float | None:
    rs = [a[k] / b[k] for k in b if b[k] > 0 and a.get(k, 0) > 0]
    return median(rs) if rs else None


def history_readings(seeds: Sequence[int] = SEEDS, workers: int = 4) -> list[m50.Reading]:
    """60.7 target 1: a 2000 world against a 2008 world in January 2008 and a 2010 world in
    January 2010 (the median of each seed's median ratio)."""
    plan = [(s, y) for s in seeds for y in (2000, 2008, 2010)]
    with ProcessPoolExecutor(workers) as pool:
        runs = dict(zip(plan, pool.map(world_job, plan), strict=True))
    out = []
    for at, later in ((JAN_2008, 2008), (JAN_2010, 2010)):
        for label, pick in (
            ("category sizes", lambda s: s.markets),
            ("named rivals' customers", lambda s: s.customers),
        ):
            per_seed = [
                r
                for s in seeds
                if (r := _ratio(pick(runs[(s, 2000)][at]), pick(runs[(s, later)][at]))) is not None
            ]
            v = median(per_seed) if per_seed else None
            out.append(
                m50.Reading(
                    "60.7 T1",
                    f"{label}, {format_turn(at)} in a 2000 game over a {later} game",
                    v,
                    f"{BAND[0]}-{BAND[1]}x",
                    None if v is None else BAND[0] <= v <= BAND[1],
                )
            )
    return out


def ipo_passive(game: Game) -> None:
    """The passive player with an IPO-dependent plan: keeps the team and spend the scenario
    gave, raises no venture round and lists as soon as a bank will take it."""
    from tst.balance.strategies import go_public

    go_public(game)


BUST_CUT_RUNWAY: Final = 12  # months of runway under which the sensible plan cuts staff
BUST_CORE: Final = 8  # ... down to this many people (engineers first kept)
KEEP_ROLES: Final = ("software_engineer", "product_manager")


def bust_sensible(game: Game) -> None:
    """The sensible plan in the bust: raise when a round is open (steady's rounds), launch,
    keep marketing to 10% of revenue, never hire, and when runway falls under a year cut one
    person a month (sales and marketing first, the most expensive first) down to a core."""
    from tst.balance.strategies import (
        STEADY_ROUNDS,
        accept_bridges,
        fundraise,
        last_revenue,
        launch_ready,
        set_marketing,
    )

    accept_bridges(game)
    fundraise(game, STEADY_ROUNDS, pick="pre")
    launch_ready(game)
    set_marketing(game, round(0.1 * last_revenue(game)))
    cut_when_short(game)


def cut_when_short(game: Game) -> None:
    """When runway falls under BUST_CUT_RUNWAY months, let one person go (sales and
    marketing first, the most expensive first), down to BUST_CORE."""
    from tst.balance.strategies import runway
    from tst.sim.actions.hiring import Fire
    from tst.sim.errors import SimError

    months = runway(game)
    staff = [e for e in game.state.staff(game.state.player.id) if e.status == "active"]
    staff = [e for e in staff if e.person_id != game.founder_id]
    if months is not None and months < BUST_CUT_RUNWAY and len(staff) > BUST_CORE:
        victim = max(staff, key=lambda e: (e.role not in KEEP_ROLES, e.salary_cents, -e.id))
        with contextlib.suppress(SimError):
            game.act(Fire(game.founder_id, victim.person_id))


def campaign_script(game: Game) -> None:
    """60.7 target 3's founder: v1's steady, cutting staff when runway is short (the bust)."""
    from tst.balance.strategies import steady

    steady(game)
    cut_when_short(game)


def bust_job(job: tuple[int, str]) -> tuple[int, str, str | None, bool]:
    """(seed, script, scenario result, bankrupt) for one Survive-the-bust run."""
    from tst.balance import m51

    seed, script = job
    game = m51.start_scenario(m30.loaded(), BUST, seed)
    fn = {"ipo_passive": ipo_passive, "sensible": bust_sensible}[script]
    run = m51.play(game, fn, BUST, seed, script)
    return seed, script, run.result, game.state.save_meta.game_state == "bankrupt"


def bust_readings(seeds: Sequence[int] = SEEDS, workers: int = 4) -> list[m50.Reading]:
    """60.7 target 2, on the Survive-the-bust scenario (January 2000 to December 2003)."""
    plan = [(s, sc) for sc in ("ipo_passive", "sensible") for s in seeds]
    with ProcessPoolExecutor(workers) as pool:
        runs = list(pool.map(bust_job, plan))
    failed = sum(1 for _, sc, res, _ in runs if sc == "ipo_passive" and res != "success")
    survived = sum(1 for _, sc, _, bk in runs if sc == "sensible" and not bk)
    won = sum(1 for _, sc, res, _ in runs if sc == "sensible" and res == "success")
    n = len(seeds)
    return [
        m50.Reading(
            "60.7 T2",
            "IPO-dependent passive plan fails (Survive the bust)",
            float(failed),
            f">= {BUST_IPO_FAILS}/{n}",
            failed >= BUST_IPO_FAILS * n / 10,
        ),
        m50.Reading(
            "60.7 T2",
            "sensible plan survives (not bankrupt by December 2003)",
            float(survived),
            f">= {BUST_SURVIVES}/{n}",
            survived >= BUST_SURVIVES * n / 10,
        ),
        m50.Reading(
            "60.7 T2 (M51 band)",
            "sensible plan meets the scenario's goal",
            float(won),
            "3-8 (M51 63.4)",
            3 * n / 10 <= won <= 8 * n / 10,
        ),
    ]


def campaign_job(seed: int) -> tuple[int, int, str]:
    """(seed, last month played, game state) of a 2000 campaign to December 2029."""
    game = m50.start(seed, 2000)
    script = campaign_script
    while game.state.turn <= CAMPAIGN_END and not game.state.ended:
        script(game)
        game.turn()
    return seed, game.state.turn - 1, game.state.save_meta.game_state


def campaign_readings(
    seeds: Sequence[int] = CAMPAIGN_SEEDS, workers: int = 3
) -> tuple[list[m50.Reading], str]:
    """60.7 target 3: a 2000 campaign plays to December 2029 with no error (an exception
    fails the run; a bankrupt founder ends it early and is reported)."""
    with ProcessPoolExecutor(workers) as pool:
        runs = list(pool.map(campaign_job, seeds))
    full = sum(1 for _, last, _ in runs if last >= CAMPAIGN_END)
    lines = ", ".join(f"seed {s}: {format_turn(t)} ({g})" for s, t, g in runs)
    return [
        m50.Reading(
            "60.7 T3",
            f"2000 campaigns ({CAMPAIGN_STRATEGY}) reaching December 2029 with no error",
            float(full),
            f"{len(seeds)}/{len(seeds)}",
            full == len(seeds),
        )
    ], lines


def report(seeds: Sequence[int] = SEEDS, workers: int = 4, campaign: bool = True) -> str:
    readings = history_readings(seeds, workers) + bust_readings(seeds, workers)
    extra = ""
    if campaign:
        more, extra = campaign_readings()
        readings += more
    return f"{m50.table(readings)}\n{extra}\n"
