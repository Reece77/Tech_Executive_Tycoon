"""M54's balance targets and guards (docs/formulas.md 64.6), printed by tools/m54_targets.py.

Target 1's currency guard (sub-task 2): a company that sells and spends only in North America
plays exactly as before currencies existed. `na_only_digests` plays the `steady` script (one
North American product, no regions) on a seed with the data as loaded and with `fx` removed (every
index 1, nothing translated), digesting each month (M30's canonical digest) the full state and
ledger balances to December 2025, and from January 2026 the company's currency footprint (its
translation marks, currency months, forwards, programmes, FX and hedge account balances and the
translation entries posted for it), which must stay empty: from 2026 rivals' regional lines
translate (ADR-0025 point 4) and the indexes walk, so the world around it, and through
competition the company itself, moves by design (seed 3 differs from October 2026), while the
currency system never touches it (M54 decision 6).
"""

from __future__ import annotations

import hashlib
from functools import cache
from pathlib import Path
from typing import Any, Final

from tst.balance.game import Game, start_game
from tst.balance.m30 import Digester, month_digest
from tst.balance.strategies import STRATEGIES
from tst.loader import LoadedData, load_all
from tst.sim.finserv.models import BankMonth
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

DATA: Final = Path(__file__).resolve().parents[2] / "data"
NA_SEEDS: Final = (1, 2, 3)
NA_TURNS: Final = 240  # January 2010 to December 2029: history and four seeded years
WORLD_TURNS: Final = 192  # the full state is compared to December 2025


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


@cache
def without_fx() -> LoadedData:
    base = loaded()
    from dataclasses import replace

    return replace(base, game_data=base.game_data.model_copy(update={"fx": None}))


def na_only_digests(seed: int, turns: int = NA_TURNS, *, fx: bool = True) -> list[str]:
    """The steady script's month digests on a seed, with or without currencies."""
    data = loaded() if fx else without_fx()
    game = start_game(data, seed)
    script = STRATEGIES["steady"]
    digester = Digester()
    out: list[str] = []
    while game.state.turn < turns and not game.state.ended:
        script(game)
        game.turn()
        if game.state.turn <= WORLD_TURNS:
            out.append(month_digest(digester, game))
        else:
            out.append(_player_digest(digester, game))
    return out


FX_ACCOUNTS: Final = ("4940_fx_gains", "4945_fx_losses")
TRANSLATION_MEMO: Final = "Currency translation"


def footprint(game: Game) -> tuple[object, ...]:
    """The player company's currency footprint this month (module docstring): empty for a
    company that sells and spends only in North America."""
    s = game.state
    pid = s.player.id
    mine = {p.id for p in s.products if p.company_id == pid}
    entries = game.last_result.ledger_entries if game.last_result is not None else ()
    return (
        tuple(m for m in s.fx.marks if m.product_id in mine),
        tuple(m for m in s.fx.months if m.company_id == pid),
        tuple(h for h in s.fx.hedges if h.company_id == pid),
        tuple(p for p in s.fx.programmes if p.company_id == pid),
        tuple(v for (c, a), v in game.balances.items() if c == pid and a in FX_ACCOUNTS and v),
        tuple(e for e in entries if e.company_id == pid and e.memo.startswith(TRANSLATION_MEMO)),
    )


def _player_digest(digester: Digester, game: Game) -> str:
    out = digester.digest(footprint(game))
    digester.next_month()
    return hashlib.sha256(out).hexdigest()[:16]


# --- 64.6 targets 2, 3 and 5: harnesses --------------------------------------------------------
#
# Each is measured on the engine's own phases (tst.sim.finserv, tst.sim.fx) in a harness: a new
# game's state moved to the target's years, the player's lines held at fixed customers (a
# business that neither grows nor shrinks: M54 decision 9), the macro layer stepping each month
# (the history to 2025, then its seeded cycles), so each measure isolates what its target asks: a
# bank's margin and rate sensitivity, a run's conditions, currency risk and its hedge.

PLAYER: Final = 1
NA: Final = "north_america"
SEEDS: Final = tuple(range(1, 11))
BANK_LINE: Final = 990_001
FOREIGN_LINE: Final = 990_002


def _state(seed: int, turn: int) -> GameState:
    from dataclasses import replace

    return replace(start_game(loaded(), seed).state, turn=turn)


def _line(
    state: GameState, pid: int, category: str, rows: list[tuple[str, str, int, float]]
) -> GameState:
    """A live player line with (region, segment, price, customers) rows."""
    from tst.sim.geo.models import RegionalSegment
    from tst.sim.products.models import Product, ProductSegment
    from tst.sim.state import with_product, with_segments

    p = Product(
        id=pid,
        company_id=PLAYER,
        category=category,
        name=f"Line {pid}",
        status="live",
        quality=70.0,
        feature_points=0.0,
        brand=60.0,
        marketing_budget_cents=0,
        created_turn=0,
        launched_turn=0,
    )
    home = [ProductSegment(pid, seg, price, n) for r, seg, price, n in rows if r == NA]
    away = [RegionalSegment(pid, r, seg, price, n) for r, seg, price, n in rows if r != NA]
    return with_segments(with_product(state, p), home, away)


def _month(state: GameState, rng: RngFactory) -> GameState:
    from tst.sim.finance import macro

    b, d = loaded().balance, loaded().game_data
    return macro.macro_phase(state, rng, b, d)


def bank_run(
    seed: int,
    first: int,
    last: int,
    *,
    consumers: float = 300_000.0,
    businesses: float = 20_000.0,
    beta: float | None = None,
    securities_share: float | None = None,
    loan_to_deposit: float | None = None,
    duration: float | None = None,
    capital_share: float = 0.09,
) -> tuple[GameState, list[BankMonth]]:
    """A chartered bank of fixed accounts from January `first` to December `last` (default
    settings: a sensible player's), opening capital `capital_share` of its first year's deposits."""
    from dataclasses import replace

    from tst.sim.calendar import ym_to_turn
    from tst.sim.finserv import banks, phase
    from tst.sim.finserv.models import Bank

    b, d = loaded().balance, loaded().game_data
    bb = b.finserv.bank
    start = ym_to_turn(first, 1)
    state = _state(seed, start)
    state = _line(
        state,
        BANK_LINE,
        b.finserv.banking_category,
        [(NA, "bank_consumer", 800, consumers), (NA, "bank_business", 6000, businesses)],
    )
    deposits = sum(
        banks.balance_per_account(state, seg, NA, b, d) * n
        for seg, n in (("bank_consumer", consumers), ("bank_business", businesses))
    )
    capital = round(deposits * capital_share)
    bank = Bank(
        id=1,
        company_id=PLAYER,
        region=NA,
        status="chartered",
        applied_turn=start,
        charter_turn=start,
        beta=bb.default_beta if beta is None else beta,
        loan_to_deposit=bb.loan_to_deposit if loan_to_deposit is None else loan_to_deposit,
        securities_share=bb.securities_share if securities_share is None else securities_share,
        duration=bb.default_duration if duration is None else duration,
        reserves_cents=capital,
        capital_in_cents=capital,
    )
    state = replace(state, finserv=replace(state.finserv, banks=(bank,)))
    rng = RngFactory(seed)
    records: list[BankMonth] = []
    for turn in range(start, ym_to_turn(last, 12) + 1):
        state = _month(replace(state, turn=turn), rng)
        state, _, _ = phase.after_sales(state, rng, b, d)
        records += [m for m in state.finserv.bank_months if m.turn == turn]
    return state, records


def target2(seed: int) -> dict[str, float]:
    """64.6 target 2 on a seed: the sensible bank's NIM in 2015-2025 (assets-weighted), and the
    correlation of its yearly profit with the year's policy rate at a deposit beta of 0.3."""
    from statistics import correlation

    from tst.sim.calendar import turn_to_ym

    _, months = bank_run(seed, 2015, 2025)
    nii = sum(m.nii_cents for m in months)
    assets = sum(m.loans_cents + m.securities_cents + m.reserves_cents for m in months)
    _, low = bank_run(seed, 2015, 2025, beta=0.3)
    years: dict[int, list[BankMonth]] = {}
    for m in low:
        years.setdefault(turn_to_ym(m.turn)[0], []).append(m)
    profit = [
        sum(x.profit_cents for x in ms) / max(1, sum(x.deposits_cents for x in ms))
        for ms in years.values()
    ]
    rate = [sum(x.policy_rate for x in ms) / len(ms) for ms in years.values()]
    return {"nim": 12 * nii / assets, "profit_rate_corr": correlation(rate, profit)}


def target3(seed: int, uninsured_high: bool) -> bool:
    """64.6 target 3 on a seed: a bank that buys long securities through 2020-2021 and holds them
    through 2022's rise, with mostly business deposits (over 50% uninsured) or consumer ones
    (under 20%): whether it has a run by December 2023."""
    state, _ = bank_run(
        seed,
        2019,
        2023,
        consumers=50_000.0 if uninsured_high else 400_000.0,
        businesses=40_000.0 if uninsured_high else 0.0,
        securities_share=0.55,
        loan_to_deposit=0.35,
        duration=8.0,
        capital_share=0.08,
    )
    return any(bank.runs for bank in state.finserv.banks)


FOREIGN_MIX: Final = (  # (region, share of revenue): 60% outside North America
    (NA, 0.40),
    ("europe", 0.30),
    ("east_asia", 0.15),
    ("latin_america", 0.15),
)
FX_FIRST: Final = 2026
FX_LAST: Final = 2035
MONTHLY_REVENUE_CENTS: Final = 1_000_000_000  # $10M a month
COST_SHARE: Final = 0.7  # costs in US dollars, of the first month's revenue


def target5_profits(seed: int, hedge_share: float) -> list[int]:
    """64.6 target 5's yearly operating profit after currency results, 2026-2035, for a player
    with 60% of its revenue abroad (FOREIGN_MIX, prices set in January 2026), costs in dollars,
    with a layered rolling hedge of `hedge_share` (0: none) 24 months ahead (M57: the ADR-0025 amendment)."""
    from dataclasses import replace

    from tst.sim.calendar import turn_to_ym, ym_to_turn
    from tst.sim.fx import phase as fx_phase
    from tst.sim.fx.actions import with_programme
    from tst.sim.money import times

    b, d = loaded().balance, loaded().game_data
    start = ym_to_turn(FX_FIRST, 1)
    state = _state(seed, start)
    price = 10_000
    rows = [(r, "smb", price, MONTHLY_REVENUE_CENTS * share / price) for r, share in FOREIGN_MIX]
    state = _line(state, FOREIGN_LINE, "b2b_saas", rows)
    if hedge_share > 0:
        state = with_programme(state, PLAYER, hedge_share, 24)
    cost = times(MONTHLY_REVENUE_CENTS, COST_SHARE)
    rng = RngFactory(seed)
    years: dict[int, int] = {}
    for turn in range(start, ym_to_turn(FX_LAST, 12) + 1):
        state = _month(replace(state, turn=turn), rng)
        state, prices = fx_phase.before_markets(state, rng, b, d)
        revenue = sum(times(prices.get((FOREIGN_LINE, r, seg), p), n) for r, seg, p, n in rows)
        booked: dict[tuple[int, str], tuple[int, int]] = {}  # phase 5's (M57r-A, item 11)
        for r, seg, p, n in rows:
            a, c = booked.get((PLAYER, r), (0, 0))
            booked[(PLAYER, r)] = (
                a + times(prices.get((FOREIGN_LINE, r, seg), p), n),
                c + times(p, n),
            )
        state, entries = fx_phase.after_sales(state, b, d, booked)
        fx = -sum(
            x.amount
            for e in entries
            for x in e.lines
            if x.account in ("4940_fx_gains", "4945_fx_losses")
        )
        year = turn_to_ym(turn)[0]
        years[year] = years.get(year, 0) + revenue - cost + fx
    return [years[y] for y in sorted(years)]


def target5(seed: int) -> dict[str, float]:
    from statistics import pstdev

    none = pstdev(target5_profits(seed, 0.0))
    hedged = pstdev(target5_profits(seed, 0.8))
    return {"std_none": none, "std_hedged": hedged, "reduction": 1 - hedged / none if none else 0.0}


NETWORK_LINE: Final = 990_003
NETWORK_SHARE: Final = 0.10
NETWORK_YEARS: Final = 5


def target4(seed: int) -> list[float]:
    """64.6 target 4 on a seed: a do-nothing game to December 2025, then a player network holding
    10% of North America's card programmes (its acceptance at that share's level, its line
    maintained: fixed scores, M54 decision 11), played five more years; its share each December."""
    from dataclasses import replace

    from tst.sim.finserv import payments
    from tst.sim.finserv.models import Network
    from tst.sim.products.models import Product, ProductSegment
    from tst.sim.state import with_product, with_segments

    b, d = loaded().balance, loaded().game_data
    pb = b.finserv.payments
    game = start_game(loaded(), seed)
    start = b.finserv.start_turn
    while game.state.turn < start:
        game.turn()
    s = game.state
    market = next(
        m.addressable for m in s.markets if m.category == "payments" and m.segment == "pay_networks"
    )
    p = Product(
        id=NETWORK_LINE,
        company_id=PLAYER,
        category="payments",
        name="Player Network",
        status="live",
        quality=82.0,
        feature_points=0.0,
        brand=80.0,
        marketing_budget_cents=0,
        created_turn=s.turn,
        launched_turn=s.turn,
        held_feature=78.0,
    )
    s = with_segments(
        with_product(s, p),
        [ProductSegment(NETWORK_LINE, "pay_networks", 208333, market * NETWORK_SHARE)],
        [],
    )
    net = Network(1, PLAYER, NA, s.turn, acceptance=NETWORK_SHARE**pb.acceptance_exponent)
    game.state = replace(s, finserv=replace(s.finserv, networks=(net,)))
    shares = []
    for _ in range(NETWORK_YEARS * 12):
        game.turn()
        if game.state.turn % 12 == 0:
            shares.append(payments.network_share(game.state, PLAYER, NA, b, d))
    return shares


# --- the report (tools/m54_targets.py) ---------------------------------------------------------

NIM_BAND: Final = (0.025, 0.040)
RUN_MIN: Final = 3  # of 10 seeds: the runnable bank has a run on at least this many
NETWORK_MIN: Final = 7  # of 10 seeds: the network keeps or grows its share
HEDGE_CUT: Final = 0.15  # the hedged spread of yearly profit is at least this much lower


def _seed_row(seed: int) -> dict[str, Any]:
    return {
        "seed": seed,
        "t2": target2(seed),
        "t3_high": target3(seed, True),
        "t3_low": target3(seed, False),
        "t4": target4(seed),
        "t5": target5(seed),
    }


def run(seeds: tuple[int, ...] = SEEDS, workers: int = 1) -> list[dict[str, Any]]:
    if workers <= 1:
        return [_seed_row(s) for s in seeds]
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_seed_row, seeds))


def _yes(ok: bool) -> str:
    return "yes" if ok else "no"


def report(rows: list[dict[str, Any]]) -> str:
    from statistics import median

    n = len(rows)
    nims = [r["t2"]["nim"] for r in rows]
    corrs = [r["t2"]["profit_rate_corr"] for r in rows]
    high = sum(bool(r["t3_high"]) for r in rows)
    low = sum(bool(r["t3_low"]) for r in rows)
    kept = sum(1 for r in rows if r["t4"] and r["t4"][-1] >= NETWORK_SHARE)
    shares = [r["t4"][-1] for r in rows if r["t4"]]
    cuts = [r["t5"]["reduction"] for r in rows]
    lo, hi = NIM_BAND
    nim_ok = all(lo <= x <= hi for x in nims)
    rows_out = [
        ("2 NIM 2015-2025", f"{lo:.1%}-{hi:.1%}",
         f"{min(nims):.2%}-{max(nims):.2%} (median {median(nims):.2%})", nim_ok),
        ("2 profit rises with the rate (beta 0.3)", "correlation > 0",
         f"{min(corrs):.2f}-{max(corrs):.2f}", all(c > 0 for c in corrs)),
        ("3 runs, over 50% uninsured", f">= {RUN_MIN} of {n}", str(high), high >= RUN_MIN),
        ("3 runs, under 20% uninsured", "none", str(low), low == 0),
        ("4 network keeps 10% for 5 years", f">= {NETWORK_MIN} of {n}",
         f"{kept} (after 5 years {min(shares):.1%}-{max(shares):.1%})", kept >= NETWORK_MIN),
        ("5 80% hedge cuts yearly profit's spread", f">= {HEDGE_CUT:.0%} (median)",
         f"{median(cuts):.1%} ({min(cuts):.1%}-{max(cuts):.1%})", median(cuts) >= HEDGE_CUT),
    ]  # fmt: skip
    seeds = ", ".join(str(r["seed"]) for r in rows)
    lines = [
        f"M54 targets (docs/formulas.md 64.6), seeds {seeds}",
        "",
        "| Target | Band | Reading | Met |",
        "| --- | --- | --- | --- |",
    ]
    lines += [f"| {a} | {b} | {c} | {_yes(ok)} |" for a, b, c, ok in rows_out]
    return "\n".join(lines)
