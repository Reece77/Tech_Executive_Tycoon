"""docs/formulas.md 37.6 targets (M26, lane C), printed with their values by
tools/m26_targets.py. True values are read here; this is a tool.

- T1 angel investing is skewed: do-nothing games over 10 seeds where the founder (with
  personal cash) writes a $250k cheque into every new startup's founding round (any
  category: a do-nothing company has none of its own) for 10 years. Each stake's multiple
  at year 10: proceeds at an acquisition, shares at market after a listing, the last round
  value while open: its startup's 28.1 value at year 10 (true values; in the game, net
  worth marks an open stake at the last round price, which most startups never move, M26
  decision), 0 when failed. Median, the top decile's mean (its lowest printed beside it),
  and the portfolio's (all value over all cheques).
- T2 backing people you know pays: do-nothing games over 10 seeds; every 6 months from
  month 6 to 54 the founder backs two new startups with $1M each, in turn through the
  categories a startup may start in: one led by the best of six former colleagues by the
  revealed (exact) skills, one by a stranger picked blind from six others. Five-year
  survival (alive, or acquired, 60 months on) of each kind.
- T3 the family office behaves like a fund: the market index of do-nothing games 2010-2025
  (10 seeds), and each mandate's monthly return from the engine's formula on it (a manager
  at alpha_mid skill, the stream's own noise): annual (geometric) returns and volatility.
- T4 insider trading gets caught: do-nothing games, funded like M14's scripted deals; each
  year the company starts diligence on a listed rival, the founder buys its shares that
  month, and two months on the company bids (stepping the premium until the board agrees),
  then walks away. Seeds with an investigation opened within 10 years.
- T5 nothing else moves: steady games for 10 years on 3 seeds, with the M26 phase and with
  it replaced by one that records nothing; every month's company snapshot must match.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from typing import Final

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.m13 import _loaded
from tst.balance.strategies import steady
from tst.sim.actions import BackStartup, JoinRound, TradeShares
from tst.sim.founder import angel, family_office, personal
from tst.sim.founder.draws import OFFICE, personal_draws
from tst.sim.founder.investing_models import STAKE_FULL, NetworkEntry
from tst.sim.founder.wealth import share_price_cents, stake_value_cents
from tst.sim.rng import RngFactory
from tst.sim.state import angel_stake_of, with_network

SEEDS: Final = tuple(range(1, 11))
YEARS: Final = 10
TURNS: Final = 12 * YEARS
ANGEL_CHEQUE: Final = 250_000_00  # $250k (T1)
FOUNDER_CASH: Final = 2_000_000_000_00  # $2B of personal cash for the scripts
BACK_CHEQUE: Final = 1_000_000_00  # $1M (T2)
BACK_FROM, BACK_TO, BACK_EVERY = 6, 54, 6  # T2's backing months
SURVIVE_MONTHS: Final = 60
POOL: Final = 6  # T2: former colleagues to pick from, each kind
INDEX_TURNS: Final = 192  # T3: 2010-2025
DEAL_MONTH: Final = 1  # T4: diligence in February, the bid in April
BID_AFTER: Final = 2
TRADE_CENTS: Final = 1_000_000_00  # T4: $1M of the target's shares
T5_SEEDS: Final = (1, 2, 3)
SCRIPT_KEY: Final = 990_000  # people_gen key part of T2's generated colleagues (never met)


def _cash(game: Game, cents: int = FOUNDER_CASH) -> None:
    game.state = personal.credit(game.state, game.founder_id, cents, "exit", "Script cash")


def _energy(game: Game) -> None:
    from tst.balance.m13b import _energy as top_up

    top_up(game)


# --- T1 ---------------------------------------------------------------------------------------


def _multiple(game: Game, stake_id: int) -> float:
    s = next(x for x in game.state.angel_stakes if x.id == stake_id)
    if s.status == "acquired":
        return s.proceeds_cents / s.cost_cents
    if s.status == "failed":
        return 0.0
    if s.status == "listed":
        from tst.sim.state import holding_in

        held = holding_in(game.state, s.person_id, s.company_id)
        price = share_price_cents(
            game.state, s.company_id, game.balances, game.loaded.balance, game.loaded.game_data
        )
        return (held.shares * (price or 0) if held else 0) / s.cost_cents
    if not game.state.company(s.company_id).alive:
        return stake_value_cents(s) / s.cost_cents
    from fractions import Fraction

    from tst.sim.mna.valuation import fundamental_value_cents

    value = fundamental_value_cents(
        game.state, s.company_id, game.balances, game.loaded.balance, game.loaded.game_data
    )
    return float(Fraction(s.stake_ppm, STAKE_FULL) * value) / s.cost_cents


@dataclass(frozen=True, slots=True)
class AngelRun:
    seed: int
    multiples: tuple[float, ...]
    cost_cents: int
    value_cents: int
    outcomes: tuple[str, ...]


def play_angel(seed: int) -> AngelRun:
    game = start_game(_loaded(), seed)
    _cash(game)
    b = game.loaded.balance
    stakes: list[int] = []
    for _ in range(TURNS):
        if game.state.ended:
            break
        for c in game.state.companies:
            rnd = angel.open_round(game.state, c.id, b)
            if rnd is None or rnd.source != "founded" or rnd.turn != game.state.turn - 1:
                continue
            if angel_stake_of(game.state, game.founder_id, c.id) is not None:
                continue
            _energy(game)
            if game.act(JoinRound(game.founder_id, c.id, min(ANGEL_CHEQUE, rnd.raised_cents))):
                stake = angel_stake_of(game.state, game.founder_id, c.id)
                assert stake is not None
                stakes.append(stake.id)
        game.turn()
    multiples = tuple(_multiple(game, s) for s in stakes)
    costs = [next(x for x in game.state.angel_stakes if x.id == s).cost_cents for s in stakes]
    value = round(sum(m * c for m, c in zip(multiples, costs, strict=True)))
    outcomes = tuple(next(x for x in game.state.angel_stakes if x.id == s).status for s in stakes)
    return AngelRun(seed, multiples, sum(costs), value, outcomes)


# --- T2 ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BackRun:
    seed: int
    known: tuple[bool, ...]  # survived 5 years, by backing
    blind: tuple[bool, ...]
    known_skill: float  # mean true skill of the founders picked
    blind_skill: float


def _colleagues(game: Game, n: int, exact: bool, tag: int) -> list[int]:
    """n generated former colleagues in the network; exact: the player knows their skills."""
    from tst.sim.people.generator import generate_pool, people_gen_stream
    from tst.sim.people.models import Employment
    from tst.sim.people.reveal import new_reveal_state
    from tst.sim.state import with_employment, with_person, with_reveal

    b, d = game.loaded.balance, game.loaded.game_data
    state = game.state
    rng = RngFactory(state.save_meta.master_seed)
    gen = people_gen_stream(rng, state.turn, SCRIPT_KEY, tag)
    role = d.role("software_engineer")
    out: list[int] = []
    for _ in range(n):
        pid, ids = state.next_ids.take("rival_person")
        eid, ids = ids.take("rival_employment")
        (person,) = generate_pool(gen, d, b, state.turn, role, ["senior"], first_person_id=pid)
        state = replace(with_person(state, person), next_ids=ids)
        state = with_employment(
            state,
            Employment(
                eid, pid, PLAYER, role.key, "senior", 0, 0, 0, state.turn, "ended", "resigned"
            ),
        )
        reveal = new_reveal_state(
            observer_company_id=PLAYER,
            person=person,
            turn=state.turn,
            rng=rng,
            data=d,
            balance=b,
            knows_exactly=exact,
        )
        state = with_reveal(state, reveal)
        state = with_network(
            state, [NetworkEntry(pid, state.turn)], b.angel.network_size + POOL * 2
        )
        out.append(pid)
    game.state = state
    return out


def _mean_skill(game: Game, pid: int) -> float:
    return angel.mean_true_skill(game.state.person(pid), game.loaded.game_data)


def play_backing(seed: int) -> BackRun:
    game = start_game(_loaded(), seed)
    _cash(game)
    d = game.loaded.game_data
    cats = [
        c.key for c in d.categories if not (c.capacity_market or c.sells_units or c.assembly_market)
    ]
    backed: list[tuple[int, bool, int, float]] = []  # (company, known, turn, skill)
    n = 0
    for month in range(TURNS):
        if game.state.ended:
            break
        if BACK_FROM <= month <= BACK_TO and month % BACK_EVERY == 0:
            for known in (True, False):
                pool = _colleagues(game, POOL, known, 2 * n + int(known))
                pid = max(pool, key=lambda p: _mean_skill(game, p)) if known else pool[0]
                _energy(game)
                cat = cats[n % len(cats)]
                skill = _mean_skill(game, pid)
                if game.act(BackStartup(game.founder_id, pid, cat, BACK_CHEQUE)):
                    stake = game.state.angel_stakes[-1]
                    backed.append((stake.company_id, known, game.state.turn, skill))
            n += 1
        game.turn()
    survived: dict[bool, list[bool]] = {True: [], False: []}
    skills: dict[bool, list[float]] = {True: [], False: []}
    for cid, known, turn, skill in backed:
        s = next(x for x in game.state.angel_stakes if x.company_id == cid)
        alive_at = s.closed_turn is None or s.closed_turn > turn + SURVIVE_MONTHS
        survived[known].append(alive_at or s.status == "acquired")
        skills[known].append(skill)
    return BackRun(
        seed,
        tuple(survived[True]),
        tuple(survived[False]),
        statistics.fmean(skills[True]) if skills[True] else 0.0,
        statistics.fmean(skills[False]) if skills[False] else 0.0,
    )


# --- T3 ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OfficeRun:
    seed: int
    index_annual: float
    annual: dict[str, float]
    vol: dict[str, float]


def _annual(returns: Sequence[float]) -> float:
    growth = math.prod(1 + r for r in returns)
    return growth ** (12 / len(returns)) - 1 if returns else 0.0


def play_office(seed: int) -> OfficeRun:
    from tst.sim.finance.macro import base_rate

    game = start_game(_loaded(), seed)
    b, d = game.loaded.balance, game.loaded.game_data
    rng = RngFactory(game.state.save_meta.master_seed)
    by_mandate: dict[str, list[float]] = {m: [] for m in b.family_office.mandates}
    index: list[float] = []
    for _ in range(INDEX_TURNS):
        if game.state.ended:
            break
        game.turn()
        point = game.state.market_index[-1]
        if len(game.state.market_index) < 2:
            continue
        r = point.month_return
        index.append(r)
        cash_r = base_rate(game.state, d) / 100 / 12
        z = float(personal_draws(rng, point.turn, OFFICE).standard_normal())
        for m in by_mandate:
            by_mandate[m].append(
                family_office.monthly_return(r, cash_r, b.family_office.alpha_mid, z, m, b)
            )
    return OfficeRun(
        seed,
        _annual(index),
        {m: _annual(rs) for m, rs in by_mandate.items()},
        {m: statistics.pstdev(rs) * math.sqrt(12) for m, rs in by_mandate.items()},
    )


# --- T4 ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InsiderRun:
    seed: int
    trades: int
    insider: int
    investigated: int
    first_turn: int | None


def play_insider(seed: int) -> InsiderRun:
    from tst.balance.m14 import FUNDING, _deal, _fund, buy_listed
    from tst.sim.mna.deals import AbandonDeal, StartDiligence
    from tst.sim.mna.valuation import is_listed

    game = start_game(_loaded(), seed)
    _cash(game)
    _fund(game, FUNDING)
    b, d = game.loaded.balance, game.loaded.game_data
    target: int | None = None
    tried: set[int] = set()
    for _ in range(TURNS):
        if game.state.ended:
            break
        month = game.state.turn % 12
        if month == DEAL_MONTH:
            listed = [
                c.id
                for c in game.state.rivals()
                if is_listed(game.state, c.id, d) and c.id not in tried
            ]
            target = listed[0] if listed else None
            if target is not None:
                tried.add(target)
                _energy(game)
                if game.act(StartDiligence(game.founder_id, target)):
                    price = share_price_cents(game.state, target, game.balances, b, d) or 1
                    _energy(game)
                    game.act(TradeShares(game.founder_id, target, "buy", TRADE_CENTS // price))
        elif month == DEAL_MONTH + BID_AFTER and target is not None:
            buy_listed(game, target)  # M14's friendly bid, stepping the premium
            deal = _deal(game, target)
            if deal is not None and deal.status in ("accepted", "review", "blocked"):
                _energy(game)
                game.act(AbandonDeal(game.founder_id, deal.id))
            target = None
        game.turn()
    trades = [t for t in game.state.personal_trades if t.person_id == game.founder_id]
    opened = [t.investigated_turn for t in trades if t.investigated_turn is not None]
    return InsiderRun(
        seed,
        len(trades),
        sum(1 for t in trades if t.public_turn is not None),
        len(opened),
        min(opened) if opened else None,
    )


# --- T5 ---------------------------------------------------------------------------------------


def play_same(seed: int) -> bool:
    """Steady for 10 years with and without M26's phase: identical company snapshots."""
    import tst.sim.turn as turn_module

    def snapshots(patch: bool) -> list[tuple[int, int, int, int]]:
        names = vars(turn_module)
        real = names["investing_month"]
        if patch:
            names["investing_month"] = lambda state, *a, **k: (state, (), ())
        try:
            game = start_game(_loaded(), seed)
            out = []
            for _ in range(TURNS):
                if game.state.ended:
                    break
                steady(game)
                game.turn()
                c = game.state.player
                out.append(
                    (
                        game.state.turn,
                        game.cash,
                        c.mrr_history[-1] if c.mrr_history else 0,
                        len(game.state.staff(PLAYER)),
                    )
                )
            return out
        finally:
            names["investing_month"] = real

    return snapshots(False) == snapshots(True)


# --- Running and reporting --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Results:
    angel: list[AngelRun]
    backing: list[BackRun]
    office: list[OfficeRun]
    insider: list[InsiderRun]
    same: list[bool]


def _pool(fn: Callable[[int], object], seeds: Sequence[int], jobs: int) -> list[object]:
    if jobs <= 1:
        return [fn(s) for s in seeds]
    with ProcessPoolExecutor(jobs) as ex:
        return list(ex.map(fn, seeds))


def run(seeds: tuple[int, ...] = SEEDS, jobs: int = 1, only: tuple[str, ...] = ()) -> Results:
    want = set(only) or {"1", "2", "3", "4", "5"}
    return Results(
        angel=_pool(play_angel, seeds, jobs) if "1" in want else [],  # type: ignore[arg-type]
        backing=_pool(play_backing, seeds, jobs) if "2" in want else [],  # type: ignore[arg-type]
        office=_pool(play_office, seeds, jobs) if "3" in want else [],  # type: ignore[arg-type]
        insider=_pool(play_insider, seeds, jobs) if "4" in want else [],  # type: ignore[arg-type]
        same=_pool(play_same, T5_SEEDS, jobs) if "5" in want else [],  # type: ignore[arg-type]
    )


def target_1(r: Results) -> tuple[float, float, float, float, int]:
    """(median multiple, the top decile's mean (the measure), its lowest (the 90th
    percentile, printed beside it), portfolio multiple, stakes)."""
    ms = sorted(m for a in r.angel for m in a.multiples)
    if not ms:
        return 0.0, 0.0, 0.0, 0.0, 0
    cut = int(len(ms) * 0.9)
    top = ms[cut:]
    cost = sum(a.cost_cents for a in r.angel)
    value = sum(a.value_cents for a in r.angel)
    return (
        statistics.median(ms),
        statistics.fmean(top),
        ms[cut],
        value / cost if cost else 0.0,
        len(ms),
    )


def target_2(r: Results) -> tuple[float, float, float | None, int, int]:
    """(known survival, blind survival, ratio, backings each)."""
    known = [x for b in r.backing for x in b.known]
    blind = [x for b in r.backing for x in b.blind]
    k = sum(known) / len(known) if known else 0.0
    bl = sum(blind) / len(blind) if blind else 0.0
    return k, bl, (k / bl if bl else None), len(known), len(blind)


def target_3(r: Results) -> tuple[float, dict[str, float], float, dict[str, float]]:
    """(index annual, mean annual by mandate, balanced's largest miss in points, vol)."""
    idx = statistics.fmean(o.index_annual for o in r.office)
    annual = {m: statistics.fmean(o.annual[m] for o in r.office) for m in r.office[0].annual}
    miss = max(abs(o.annual["balanced"] - o.index_annual) for o in r.office) * 100
    vol = {m: statistics.fmean(o.vol[m] for o in r.office) for m in r.office[0].vol}
    return idx, annual, miss, vol


def target_4(r: Results) -> int:
    return sum(1 for i in r.insider if i.investigated)


def report(r: Results) -> str:
    lines = ["M26 targets (formulas.md 37.6)"]
    if r.angel:
        med, top, p90, port, n = target_1(r)
        ok = med < 1.0 and top > 10 and 0.8 <= port <= 3.0
        outcomes: dict[str, int] = {}
        for a in r.angel:
            for o in a.outcomes:
                outcomes[o] = outcomes.get(o, 0) + 1
        lines.append(
            f"T1 angel skew: {n} stakes; median {med:.2f}x (< 1.0), top decile {top:.1f}x "
            f"(> 10; its lowest, the 90th percentile, {p90:.1f}x), portfolio {port:.2f}x "
            f"(0.8-3.0); outcomes {outcomes}: "
            f"{'PASS' if ok else 'MISS'}"
        )
    if r.backing:
        k, bl, ratio, nk, nb = target_2(r)
        ok = ratio is not None and ratio >= 1.3
        ks = statistics.fmean(b.known_skill for b in r.backing)
        bs = statistics.fmean(b.blind_skill for b in r.backing)
        lines.append(
            f"T2 known founders: 5-year survival {k:.0%} of {nk} known vs {bl:.0%} of {nb} "
            f"blind, ratio {ratio if ratio is None else round(ratio, 2)} (>= 1.3); mean true "
            f"skill {ks:.1f} vs {bs:.1f}: {'PASS' if ok else 'MISS'}"
        )
    if r.office:
        idx, annual, miss, vol = target_3(r)
        ok = miss <= 4 and vol["aggressive"] >= 1.5 * vol["conservative"]
        words = ", ".join(f"{m} {annual[m]:.1%} (vol {vol[m]:.1%})" for m in annual)
        lines.append(
            f"T3 family office 2010-2025: index {idx:.1%} a year; {words}; balanced's largest "
            f"miss {miss:.1f} points (<= 4); aggressive/conservative vol "
            f"{vol['aggressive'] / vol['conservative']:.2f} (>= 1.5): "
            f"{'PASS' if ok else 'MISS'}"
        )
    if r.insider:
        n = target_4(r)
        detail = ", ".join(
            f"s{i.seed} {i.insider}/{i.trades}{'*' if i.investigated else ''}" for i in r.insider
        )
        lines.append(
            f"T4 insider trading: investigated on {n} of {len(r.insider)} seeds (6-10); "
            f"insider/trades by seed ({detail}): {'PASS' if 6 <= n <= 10 else 'MISS'}"
        )
    if r.same:
        ok = all(r.same)
        lines.append(
            f"T5 nothing else moves: steady 10 years with and without M26's phase identical on "
            f"{sum(r.same)} of {len(r.same)} seeds: {'PASS' if ok else 'MISS'}"
        )
    return "\n".join(lines)
