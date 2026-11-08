"""docs/formulas.md 31.9 targets 3-5 (M16), printed with their values. Targets 1 and 2 are the
golden snapshots and the consolidation tests (tests/property/test_m16_consolidation.py,
tests/unit/test_m16_*.py).

Each seed starts from M13's listed company (tst.balance.m13.listed_game) that keeps two rival
companies as brands through the closing path: U, in a category the company does not sell in
(unrelated), and I, which supplies the company's compute at cost (integrated, 31.6).

- T3 spin-offs sometimes pay: form the holding company and play 12 months three ways: as it
  is, spinning off U, or spinning off I. The founder's total value: their shares of the
  holding at its share price, plus their own shares of the spun-off company at its market cap.
- T4 mandates matter: the same brand (U) under "grow" and under "return cash" for 3 years:
  revenue growth, and the cash it paid up to its owner.
- T5 fairness bites: 30% of I sold, I supplying at cost (20% under market): the months to the
  minority complaint.
"""

from __future__ import annotations

import copy
import os
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from fractions import Fraction

from tst.balance.game import PLAYER, Game
from tst.balance.m13 import listed_game
from tst.balance.strategies import steady
from tst.sim.finance.captable import person_shares
from tst.sim.group.capital import SellStake, SpinOff
from tst.sim.group.holding import FormHolding
from tst.sim.group.models import FULL_STAKE_BP
from tst.sim.group.ownership import equity_cents
from tst.sim.group.subsidiaries import SetMandate
from tst.sim.group.transfer import SetTransferPrice
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry, apply_entries
from tst.sim.mna import deals as mna_deals
from tst.sim.mna import integration, valuation
from tst.sim.mna.closing import settle
from tst.sim.mna.models import Deal
from tst.sim.products.models import SELLING
from tst.sim.rng import RngFactory
from tst.sim.state import listed_id, public_of, with_acquisition, with_person_state

SEEDS: tuple[int, ...] = tuple(range(1, 11))
SPIN_MONTHS = 12
MANDATE_MONTHS = 36
FAIR_MONTHS = 8


def _fund(game: Game, cents: int) -> None:
    entry = LedgerEntry.transfer(
        turn=game.state.turn,
        company_id=PLAYER,
        memo="Target funding",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=cents,
    )
    game.balances = apply_entries(game.balances, (entry,))


def _keep(game: Game, target: int) -> None:
    """Buy `target` as a brand at its public value (28.1's displayed midpoint), at least its
    book, through the closing path (28.3, 28.5)."""
    from tst.sim.group.capital import value_cents

    g, b = game.loaded.game_data, game.loaded.balance
    book = sum(v for _, v in mna_deals.net_assets(game.balances, target, g))
    price = max(value_cents(game.state, target, game.balances, b, g), book, 1_000_000_00)
    _fund(game, price)
    deal_id, ids = game.state.next_ids.take("deal")
    deal = Deal(
        deal_id,
        PLAYER,
        target,
        price,
        1.0,
        game.state.turn,
        "closed",
        resolved_turn=game.state.turn,
        mode="brand",
    )
    state, posted, acq = settle(replace(game.state, next_ids=ids), deal, (), game.balances, b, g)
    rng = RngFactory(game.state.save_meta.master_seed)
    state, acq, more, _ = integration.after_closing(
        state, acq, rng, apply_entries(game.balances, posted), b, g
    )
    game.state = with_acquisition(state, acq)
    game.balances = apply_entries(game.balances, (*posted, *more))


def _energy(game: Game) -> None:
    from tst.sim.hiring.models import PersonState

    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(
        game.state, replace(ps, energy=PersonState(ps.person_id).energy or 60)
    )


def group_game(seed: int) -> tuple[Game, int, int]:
    """The listed company with brands U (unrelated) and I (integrated, supplying compute)."""
    game = listed_game(seed)
    state = game.state
    mine = {p.category for p in state.company_products(PLAYER) if p.status in SELLING}
    candidates = [
        c
        for c in state.rivals()
        if c.parent_id is None
        and c.alive
        and not valuation.is_listed(state, c.id, game.loaded.game_data)
        and any(p.status in SELLING for p in state.company_products(c.id))
    ]
    # small companies with revenue: what a group would keep as subsidiaries
    candidates = [c for c in candidates if c.mrr_history and c.mrr_history[-1] > 0]
    candidates.sort(key=lambda c: (c.mrr_history[-1], c.id))
    unrelated = next(
        c.id for c in candidates if not {p.category for p in state.company_products(c.id)} & mine
    )
    integrated = next(c.id for c in candidates if c.id != unrelated)
    _keep(game, unrelated)
    _keep(game, integrated)
    _energy(game)
    game.act(SetTransferPrice(game.founder_id, integrated, PLAYER, "compute", "cost"))
    return game, unrelated, integrated


def _play(game: Game, months: int) -> None:
    for _ in range(months):
        steady(game)
        game.turn()


def founder_value(game: Game) -> int:
    """The founder's shares of the listed entity at its price, plus their own shares of any
    spun-off company at its market cap (31.9 T3)."""
    state, b, g = game.state, game.loaded.balance, game.loaded.game_data
    listed = listed_id(state)
    public = public_of(state, listed)
    held = person_shares(state, listed, game.founder_id)
    total = held * public.price_cents if public is not None else 0
    for x in state.personal_stakes:
        cap = valuation.market_cap_cents(state, x.company_id, game.balances, b, g) or 0
        total += round(Fraction(x.stake_bp, FULL_STAKE_BP) * cap)
    return total


@dataclass(frozen=True, slots=True)
class SpinRun:
    seed: int
    keep: int
    unrelated: int
    integrated: int


def target_3_run(seed: int) -> SpinRun:
    game, u, i = group_game(seed)
    _energy(game)
    game.act(FormHolding(game.founder_id))
    out = []
    for spin in (None, u, i):
        run = copy.deepcopy(game)
        if spin is not None:
            _energy(run)
            assert run.act(SpinOff(run.founder_id, spin, 0)), spin
        _play(run, SPIN_MONTHS)
        out.append(founder_value(run))
    return SpinRun(seed, *out)


@dataclass(frozen=True, slots=True)
class MandateRun:
    seed: int
    growth_grow: float
    growth_return: float
    paid_grow: int
    paid_return: int


def _mandate(game: Game, company: int, kind: str) -> tuple[float, int]:
    _energy(game)
    assert game.act(SetMandate(game.founder_id, company, kind))  # type: ignore[arg-type]
    start = game.state.company(company).mrr_history[-1]
    equity = equity_cents(game.balances, company, game.loaded.game_data)
    _play(game, MANDATE_MONTHS)
    end = game.state.company(company).mrr_history[-1]
    paid = equity_cents(game.balances, company, game.loaded.game_data) - equity
    return (end / start - 1 if start > 0 else 0.0), paid


def target_4_run(seed: int) -> MandateRun:
    game, u, _ = group_game(seed)
    g_grow, p_grow = _mandate(copy.deepcopy(game), u, "grow")
    g_ret, p_ret = _mandate(copy.deepcopy(game), u, "return_cash")
    return MandateRun(seed, g_grow, g_ret, p_grow, p_ret)


def target_5_run(seed: int) -> int | None:
    """Months to the complaint (None: none in FAIR_MONTHS)."""
    game, _, i = group_game(seed)
    _energy(game)
    assert game.act(SellStake(game.founder_id, i, 3_000))
    for month in range(1, FAIR_MONTHS + 1):
        steady(game)
        game.turn()
        if any(f.complaint for f in game.state.transfer_flows):
            return month
    return None


@dataclass(frozen=True, slots=True)
class Results:
    spins: tuple[SpinRun, ...]
    mandates: tuple[MandateRun, ...]
    complaints: tuple[int | None, ...]


def run(seeds: Sequence[int] = SEEDS, jobs: int = os.cpu_count() or 1) -> Results:
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        spins = tuple(pool.map(target_3_run, seeds))
        mandates = tuple(pool.map(target_4_run, seeds))
        complaints = tuple(pool.map(target_5_run, seeds))
    return Results(spins, mandates, complaints)


def report(r: Results) -> str:
    n = len(r.spins)
    up = sum(1 for s in r.spins if s.unrelated > s.keep)
    down = sum(1 for s in r.spins if s.integrated < s.keep)
    rows = [
        "M16 31.9 targets",
        f"T3 spin off the unrelated subsidiary: founder's value up on {up} of {n} (band 40-80%)",
        f"T3 spin off the integrated one: down on {down} of {n} (band: most)",
    ]
    for s in r.spins:
        rows.append(
            f"   seed {s.seed}: keep {s.keep / 100:,.0f}, unrelated {s.unrelated / 100:,.0f}, "
            f"integrated {s.integrated / 100:,.0f}"
        )
    # revenue after 3 years under grow over revenue under return cash, less 1
    faster = [(1 + m.growth_grow) / (1 + m.growth_return) - 1 for m in r.mandates]
    cash = [m.paid_return / m.paid_grow if m.paid_grow > 0 else float("inf") for m in r.mandates]
    rows.append(
        "T4 grow vs return cash over 3 years: revenue higher by "
        + ", ".join(f"{x:+.0%}" for x in faster)
        + " (band +20% to +60%); returns "
        + ", ".join(f"{x:.1f}x" for x in cash)
        + " the cash (band 2-4x)"
    )
    for m in r.mandates:
        rows.append(
            f"   seed {m.seed}: growth {m.growth_grow:+.0%} vs {m.growth_return:+.0%}; paid up "
            f"{m.paid_grow / 100:,.0f} vs {m.paid_return / 100:,.0f}"
        )
    hit = sum(1 for c in r.complaints if c is not None and c <= 6)
    rows.append(
        f"T5 a complaint within 6 months: {hit} of {len(r.complaints)} seeds (band: every); "
        f"months {list(r.complaints)}"
    )
    return "\n".join(rows)
