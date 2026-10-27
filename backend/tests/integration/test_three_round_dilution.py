"""The spec's M4 criterion: a scripted SAFE, seed, Series A and Series B reproduce the
formulas.md 14.10 dilution table to the share, through the actions and turns that play the
game (a round is started and accepted with the founder's actions and closes in phase 1).

Firms' quotes are random, so each round's accepted term sheet is set to the table's terms;
the SAFE is set to have filled. Option grants of the table's sizes come out of the pool."""

from __future__ import annotations

from dataclasses import replace

from tests.helpers import fresh_game
from tests.unit.test_hiring_phases import Game
from tst.loader import LoadedData
from tst.sim.actions import AcceptTermSheet, StartRound
from tst.sim.finance.captable import fd_shares, person_shares, pool_entry, unallocated
from tst.sim.finance.models import OptionGrant, Safe, TermSheet
from tst.sim.state import GameState, with_cap_entry, with_company, with_grant, with_safe

FOUNDER = 1
CASH = 10**12  # the script is about shares, not solvency


def grant(state: GameState, shares: int) -> GameState:
    """Options out of the unallocated pool (the table's "more options granted")."""
    pool = pool_entry(state, 1)
    assert pool is not None
    grant_id, ids = state.next_ids.take("grant")
    state = with_cap_entry(replace(state, next_ids=ids), replace(pool, shares=pool.shares - shares))
    return with_grant(state, OptionGrant(grant_id, 1, FOUNDER, 1, shares, state.turn))


def priced_round(game: Game, series: str, pre: int, amount: int, mrr: int) -> None:
    """Start the round, receive one term sheet at the table's terms, accept it, Continue."""
    game.state = with_company(game.state, replace(game.state.player, mrr_history=(mrr,) * 13))
    game.act(StartRound(FOUNDER, series, amount))
    rnd = next(r for r in game.state.rounds if r.status == "open")
    sheet_id, ids = game.state.next_ids.take("term_sheet")
    sheet = TermSheet(
        sheet_id, rnd.id, "founders_fund", pre, amount, "offered", game.state.turn, rnd.expires_turn
    )
    game.state = replace(game.state, term_sheets=(*game.state.term_sheets, sheet), next_ids=ids)
    game.act(AcceptTermSheet(FOUNDER, sheet_id))
    game.turn()
    game.state = replace(
        game.state,
        person_states=tuple(
            replace(p, energy=100) if p.person_id == FOUNDER else p
            for p in game.state.person_states
        ),
    )


def founder_pct(game: Game) -> float:
    return round(100 * person_shares(game.state, 1, FOUNDER) / fd_shares(game.state, 1), 2)


def test_safe_seed_a_and_b_reproduce_the_table(loaded: LoadedData) -> None:
    game = Game(loaded, fresh_game(loaded, scenario="garage_bootstrap"), CASH)
    game.state = grant(game.state, 400_000)
    safe_id, ids = game.state.next_ids.take("safe")
    game.state = with_safe(
        replace(game.state, next_ids=ids),
        Safe(safe_id, 1, "safe", 50_000_000, 500_000_000, "outstanding", 0, resolved_turn=0),
    )  # $500,000 at a $5M post-money cap: f = 0.10
    assert (fd_shares(game.state, 1), founder_pct(game)) == (10_000_000, 90.0)

    priced_round(game, "seed", 600_000_000, 200_000_000, 0)
    seed = next(r for r in game.state.rounds if r.series == "seed")
    assert (seed.pool_shares, seed.safe_shares, seed.new_shares) == (
        1_034_783,
        1_226_087,
        4_086_957,
    )
    assert f"{float(seed.price or 0) / 100:.5f}" == "0.48936"
    assert fd_shares(game.state, 1) == 16_347_827 and founder_pct(game) == 55.05
    assert round(unallocated(game.state, 1) / 16_347_827, 4) == 0.1
    assert game.state.safes[0].status == "converted"

    game.state = grant(game.state, 800_000)
    priced_round(game, "a", 1_600_000_000, 500_000_000, 10_000_000)  # ARR $1.2M
    a = next(r for r in game.state.rounds if r.series == "a")
    assert (a.pool_shares, a.safe_shares, a.new_shares) == (1_508_914, 0, 5_580_232)
    assert f"{float(a.price or 0) / 100:.5f}" == "0.89602"
    assert fd_shares(game.state, 1) == 23_436_973 and founder_pct(game) == 38.40

    game.state = grant(game.state, 1_000_000)
    priced_round(game, "b", 6_000_000_000, 1_500_000_000, 50_000_000)  # ARR $6M
    b = next(r for r in game.state.rounds if r.series == "b")
    assert (b.pool_shares, b.safe_shares, b.new_shares) == (1_812_485, 0, 6_312_364)
    assert f"{float(b.price or 0) / 100:.5f}" == "2.37629"
    assert fd_shares(game.state, 1) == 31_561_822 and founder_pct(game) == 28.52
    investor_b = next(
        e for e in game.state.cap_entries if e.round_id == b.id and e.holder_kind == "firm"
    )
    assert round(investor_b.shares / 31_561_822, 4) == 0.2
    assert round(unallocated(game.state, 1) / 31_561_822, 4) == 0.1
    assert [s.kind for s in game.state.board(1)].count("independent") == 1
