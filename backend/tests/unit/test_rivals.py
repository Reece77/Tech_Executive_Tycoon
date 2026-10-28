"""Rival decisions (formulas.md 15.2-15.3, M5): needs, utility, cooldowns, effects, news."""

from __future__ import annotations

from dataclasses import replace

from tests.helpers import fresh_game, rival_cash
from tst.loader import LoadedData
from tst.sim.ledger import CASH
from tst.sim.rivals.decisions import (
    apply_effects,
    candidates,
    choose,
    market_news,
    rival_month,
)
from tst.sim.rivals.models import SegmentShare
from tst.sim.rivals.startups import found_startups
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_product, with_segment_share


def _by_name(state: GameState, name: str) -> int:
    return next(c.id for c in state.companies if c.name == name)


def _product_of(state: GameState, company_id: int) -> int:
    return state.company_products(company_id)[0].id


def _share_loss(
    state: GameState, product_id: int, segment: str, start: float, now: float
) -> GameState:
    history = (start, start, start, start, start, start, now)
    return with_segment_share(state, SegmentShare(product_id, segment, history))


def scripted(loaded: LoadedData) -> GameState:
    """Zoho lost 6 points of SMB share in six months; Salesforce lost 5 and now trails a
    rival on quality by 15 points."""
    state = fresh_game(loaded)
    zoho = _product_of(state, _by_name(state, "Zoho"))
    sales_cloud = _product_of(state, _by_name(state, "Salesforce"))
    oracle = state.product(_product_of(state, _by_name(state, "Oracle")))
    assert oracle is not None
    state = with_product(state, replace(oracle, quality=85.0))
    state = _share_loss(state, zoho, "smb", 0.47, 0.41)
    return _share_loss(state, sales_cloud, "mid_market", 0.30, 0.25)


def test_a_share_loss_brings_a_price_cut_and_a_push_in_the_news(loaded: LoadedData) -> None:
    state = scripted(loaded)
    balances = {**rival_cash(state, loaded), (1, CASH): 40_000_000}
    rng = RngFactory(3)
    zoho = state.company(_by_name(state, "Zoho"))
    smb = next(s for s in state.segments_of(_product_of(state, zoho.id)) if s.segment == "smb")
    after, moves, _, _ = rival_month(state, rng, balances, loaded.balance, loaded.game_data)
    by_company = {m.company_id: m for m in moves}
    cut = by_company[zoho.id]
    assert (cut.action, cut.segment) == ("price_cut", "smb")
    new_smb = next(s for s in after.segments_of(cut.product_id or 0) if s.segment == "smb")
    assert new_smb.price_cents == round((smb.price_cents or 0) * 0.9)
    push = by_company[_by_name(state, "Salesforce")]
    assert push.action == "quality_push"
    news = market_news(after, moves)
    assert len(news) == 1 and news[0].template == "market_news"
    lines = dict(news[0].params)["lines"]
    assert "Zoho cut SMB prices 10%" in lines and "Salesforce started a quality push" in lines


def test_cooldown_and_running_pushes_block_a_repeat(loaded: LoadedData) -> None:
    state = scripted(loaded)
    balances = {**rival_cash(state, loaded), (1, CASH): 40_000_000}
    rng = RngFactory(3)
    after, _, _, _ = rival_month(state, rng, balances, loaded.balance, loaded.game_data)
    zoho = after.company(_by_name(after, "Zoho"))
    again = choose(
        replace(after, turn=1),
        zoho,
        rng.stream(1, "rivals", zoho.id),
        balances,
        loaded.balance,
        loaded.game_data,
    )
    assert again is None or again[0].action != "price_cut" or again[0].segment != "smb"
    salesforce = after.company(_by_name(after, "Salesforce"))
    pushed = choose(
        replace(after, turn=1),
        salesforce,
        rng.stream(1, "rivals", salesforce.id),
        balances,
        loaded.balance,
        loaded.game_data,
    )
    assert pushed is None or pushed[0].action != "quality_push"


def test_a_quality_push_moves_quality_toward_5d(loaded: LoadedData) -> None:
    state = scripted(loaded)
    balances = {**rival_cash(state, loaded), (1, CASH): 40_000_000}
    after, _, _, _ = rival_month(state, RngFactory(3), balances, loaded.balance, loaded.game_data)
    sales_cloud = _product_of(after, _by_name(after, "Salesforce"))
    before = after.product(sales_cloud).quality  # type: ignore[union-attr]
    for turn in range(8):
        after = apply_effects(replace(after, turn=turn), loaded.balance, loaded.game_data)
    final = after.product(sales_cloud).quality  # type: ignore[union-attr]
    assert final == min(5 * 14, before + 6)  # 1 a month for the push's 6 months, capped at 5 d


def test_premium_ignores_a_small_threat(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    salesforce = state.company(_by_name(state, "Salesforce"))
    product = _product_of(state, salesforce.id)
    state = _share_loss(state, product, "smb", 0.20, 0.19)
    balances = {**rival_cash(state, loaded), (1, CASH): 40_000_000}
    cut = [
        c
        for c in candidates(state, salesforce, balances, loaded.balance, loaded.game_data)
        if c.action == "price_cut" and c.segment == "smb"
    ]
    assert cut and abs(cut[0].need - 0.2) < 1e-9  # U = 0.12 < 0.5: no price cut


# --- Startups (15.4) ---------------------------------------------------------------------------


def _always_found(loaded: LoadedData) -> LoadedData:
    rv = loaded.balance.rivals
    startup = rv.startup.model_copy(update={"found_rate": 1.0, "raise_chance": 0.0})
    balance = loaded.balance.model_copy(
        update={"rivals": rv.model_copy(update={"startup": startup})}
    )
    return replace(loaded, balance=balance)


def test_startups_are_founded_seeded_and_capped(loaded: LoadedData) -> None:
    eager = _always_found(loaded)
    runs = []
    for _ in range(2):
        state = fresh_game(eager)
        _, entries, moves = found_startups(state, RngFactory(5), eager.balance, eager.game_data)
        runs.append([(m.detail, e.lines[0].amount) for m, e in zip(moves, entries, strict=True)])
    assert runs[0] == runs[1]  # same seed, same startups
    assert len(runs[0]) == len(eager.game_data.categories)  # one per category this month
    state = fresh_game(eager)
    for turn in range(3):
        state, _, _ = found_startups(
            replace(state, turn=turn), RngFactory(5), eager.balance, eager.game_data
        )
    startups = [c for c in state.companies if c.is_startup]
    assert len(startups) == eager.balance.rivals.startup.max_alive
    for company in startups:
        staff = state.staff(company.id)
        assert 4 <= len(staff) <= 9  # a founder and 3 to 8 people
        assert company.personality != "premium"
        (product,) = state.company_products(company.id)
        assert product.status == "in_development" and company.root_product_id == product.id


def test_a_startup_out_of_money_fails_and_releases_its_people(loaded: LoadedData) -> None:
    eager = _always_found(loaded)
    state = fresh_game(eager)
    state, _, _ = found_startups(state, RngFactory(5), eager.balance, eager.game_data)
    startup = next(c for c in state.companies if c.is_startup)
    from tests.unit.test_hiring_phases import Game

    game = Game(eager, state, 40_000_000)  # the startup's money was never posted: cash 0
    for _ in range(3):
        game.turn()
    failed = game.state.company(startup.id)
    assert failed.failed_turn == 2
    assert all(p.status == "retired" for p in game.state.company_products(startup.id))
    assert game.state.staff(startup.id) == ()
    news = [i for r in game.results for i in r.log_items if i.template == "market_news"]
    assert any("ran out of money" in dict(i.params)["lines"] for i in news)
