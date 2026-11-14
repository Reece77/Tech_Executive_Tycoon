"""M31 sub-tasks 4-7 (docs/formulas.md 44.4-44.8): fees on a seller, gatekeepers' reviews and
removals with their answers, removals' losses and win-backs (44.9 target 4's mechanics), open
source, standards and the rivals' December (tests/platform_helpers.py)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.platform_helpers import START, platform_state
from tst.loader import LoadedData
from tst.sim.data_models import Balance
from tst.sim.events.models import GameEvent
from tst.sim.platforms import fees, gatekeep, opensource, standards
from tst.sim.platforms.models import PlatformListing
from tst.sim.platforms.phase import home_of, platforms_month
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_product, with_product_segment

APP_ID = 990_001
CUSTOMERS = 1_000_000.0


def _with_app(loaded: LoadedData, turn: int = START) -> GameState:
    state, _ = platform_state(loaded, turn=turn)
    state = platforms_month(state, RngFactory(1), loaded.balance, loaded.game_data)
    app = Product(
        id=APP_ID,
        company_id=state.player.id,
        category="consumer_apps",
        name="Test App",
        status="live",
        quality=60.0,
        feature_points=100.0,
        brand=40.0,
        marketing_budget_cents=0,
        created_turn=turn - 12,
        launched_turn=turn - 6,
    )
    state = with_product(state, app)
    return with_product_segment(state, ProductSegment(APP_ID, "consumer", 40, CUSTOMERS))


def _always(balance: Balance, action: str) -> Balance:
    rb = balance.platforms.review
    weights = {a: (1.0 if a == action else 0.0) for a in rb.weights}
    review = rb.model_copy(update={"base": {k: 1.0 for k in rb.base}, "weights": weights})
    return balance.model_copy(
        update={"platforms": balance.platforms.model_copy(update={"review": review})}
    )


def test_an_app_pays_store_fees(loaded: LoadedData) -> None:
    state = _with_app(loaded)
    due = {
        k: v
        for k, v in fees.fees_due(state, loaded.balance, loaded.game_data).items()
        if k[0] == APP_ID
    }
    assert due
    revenue = CUSTOMERS * 40
    total = sum(due.values())
    # paid share 0.4 x an effective fee between 15% and 30% x every platform's users (about all)
    assert 0.4 * 0.15 * revenue * 0.9 <= total <= 0.4 * 0.30 * revenue
    entries = fees.fee_entries(state, loaded.balance, loaded.game_data)
    mine = [e for e in entries if e.company_id == state.player.id]
    assert sum(e.lines[0].amount for e in mine) == total


def test_fees_wait_for_fees_from(loaded: LoadedData) -> None:
    state = _with_app(loaded, turn=START - 1)
    assert fees.fee_entries(state, loaded.balance, loaded.game_data) == []


def test_a_removal_queues_a_critical_event_and_comply_relists(loaded: LoadedData) -> None:
    balance = _always(loaded.balance, "removal")
    state = _with_app(loaded)
    state, _, _ = gatekeep.reviews_month(state, RngFactory(1), balance, loaded.game_data)
    removed = gatekeep.removed_of(state, APP_ID)
    assert removed and {x.status for x in removed} == {"removed"}
    queued = [q for q in state.queued if q.template_id == gatekeep.REMOVAL]
    assert queued and queued[0].product_id == APP_ID
    event = GameEvent(
        id=1,
        company_id=state.player.id,
        turn=state.turn,
        template_id=gatekeep.REMOVAL,
        category="platforms",
        severity="critical",
        trigger="platforms",
        strength=1.0,
        product_id=APP_ID,
    )
    names = gatekeep.removal_names(state, loaded.game_data, event)
    assert names["platform"] in {"App Store", "Google Play"}
    state, _, _ = gatekeep.platform_step(
        state, event, "comply", RngFactory(1), loaded.balance, loaded.game_data
    )
    assert gatekeep.removed_of(state, APP_ID) == []
    assert all(
        x.winback_until is not None for x in state.platform_listings if x.product_id == APP_ID
    )


def test_an_appeal_is_decided_on_its_month(loaded: LoadedData) -> None:
    balance = _always(loaded.balance, "removal")
    state = _with_app(loaded)
    state, _, _ = gatekeep.reviews_month(state, RngFactory(1), balance, loaded.game_data)
    event = GameEvent(
        id=1,
        company_id=state.player.id,
        turn=state.turn,
        template_id=gatekeep.REMOVAL,
        category="platforms",
        severity="critical",
        trigger="platforms",
        strength=1.0,
        product_id=APP_ID,
    )
    state, _, _ = gatekeep.platform_step(
        state, event, "appeal", RngFactory(1), loaded.balance, loaded.game_data
    )
    rows = [x for x in state.platform_listings if x.product_id == APP_ID]
    assert {x.status for x in rows} == {"appealing"}
    until = rows[0].until_turn
    assert until is not None and state.turn + 1 <= until <= state.turn + 3
    state, logs = gatekeep.answers_month(
        replace(state, turn=until), RngFactory(1), loaded.balance, loaded.game_data
    )
    assert {x.status for x in state.platform_listings if x.product_id == APP_ID} <= {
        "listed",
        "removed",
    }
    assert logs and logs[0].template in ("platform_appeal_won", "platform_appeal_lost")


def test_removal_loses_and_compliance_wins_back(loaded: LoadedData) -> None:
    """44.9 target 4's mechanics, the listing step alone (markets left out): removed from a
    platform with half the region's users, (1 - removed_loss / 2)^3 of the app's customers stay
    after 3 months (the markets' lost reach on new customers takes the rest of target 4's
    30-50%: tst.balance.m31); complying wins 85%+ back within 6 months."""
    state = _with_app(loaded)
    home = home_of(state, loaded.balance, loaded.game_data)
    ios = next(p for p in state.platforms if p.key == "ios")
    rows = tuple(
        replace(r, users=0.5) if r.platform_id == ios.id and r.region == home else r
        for r in state.platform_regions
    )
    state = replace(
        state,
        platform_regions=rows,
        platform_listings=(PlatformListing(APP_ID, ios.id, home or "", "removed", state.turn),),
    )
    for _ in range(3):
        state = gatekeep.listing_effects(state, loaded.balance, loaded.game_data)
        state = replace(state, turn=state.turn + 1)
    left = state.product_segment(APP_ID, "consumer").customers  # type: ignore[union-attr]
    loss = loaded.balance.platforms.review.removed_loss
    assert left / CUSTOMERS == pytest.approx((1 - loss * 0.5) ** 3)
    state = gatekeep.relist(state, gatekeep.removed_of(state, APP_ID), loaded.balance)
    for _ in range(6):
        state = gatekeep.listing_effects(state, loaded.balance, loaded.game_data)
        state = replace(state, turn=state.turn + 1)
    back = state.product_segment(APP_ID, "consumer").customers  # type: ignore[union-attr]
    assert back / CUSTOMERS >= 0.85
    assert not [x for x in state.platform_listings if x.product_id == APP_ID]


def test_a_rejected_update_costs_a_month_of_features(loaded: LoadedData) -> None:
    balance = _always(loaded.balance, "rejected_update")
    state = _with_app(loaded)
    before = state.product(APP_ID).feature_points  # type: ignore[union-attr]
    state, _, logs = gatekeep.reviews_month(state, RngFactory(1), balance, loaded.game_data)
    assert state.product(APP_ID).feature_points < before  # type: ignore[union-attr]
    assert logs and logs[0].template == "platform_rejected"


def test_the_chance_rises_with_competition_and_steering(loaded: LoadedData) -> None:
    state = _with_app(loaded)
    ios = next(p for p in state.platforms if p.key == "ios")
    app = state.product(APP_ID)
    assert app is not None
    base = gatekeep.chance(state, ios, app, loaded.balance, loaded.game_data)
    rb = loaded.balance.platforms.review
    assert base == pytest.approx(rb.base["standard"] * rb.first_party)  # Apple Music since 2015
    steering = replace(state, steering_products=(APP_ID,))
    assert gatekeep.chance(steering, ios, app, loaded.balance, loaded.game_data) == pytest.approx(
        base * rb.steering
    )


def test_open_source_books_the_paid_tier_and_adopts(loaded: LoadedData) -> None:
    state = _with_app(loaded)
    app = state.product(APP_ID)
    assert app is not None
    state = opensource.open_product(state, app, loaded.balance, loaded.game_data)
    shares = opensource.revenue_shares(state, loaded.balance)
    assert shares[APP_ID] == loaded.balance.platforms.open_source.paid_share["consumer_apps"]
    for _ in range(24):
        state = opensource.adoption_month(state, loaded.balance, loaded.game_data)
        state = replace(state, turn=state.turn + 1)
    grown = state.product_segment(APP_ID, "consumer").customers  # type: ignore[union-attr]
    assert grown > 2 * CUSTOMERS
    state, logs = opensource.close_product(state, app, loaded.balance, loaded.game_data)
    assert opensource.open_of(state, APP_ID) is None
    assert any(p.name == "Test App fork" for p in state.products)
    assert logs and logs[0].template == "platform_forked"


def test_a_standards_contest_tips_and_penalises_the_loser(loaded: LoadedData) -> None:
    from tst.sim.platforms.models import ProductStandard, Standard

    state = _with_app(loaded)
    s = Standard(
        id=99,
        key="t",
        category="consumer_apps",
        label="T",
        formats=("a", "b"),
        sponsors=(None, None),
        adoption=0.59,
        started_turn=state.turn,
    )
    rows = tuple(
        ProductStandard(p.id, 99, "b" if p.id == APP_ID else "a")
        for p in state.products
        if p.category == "consumer_apps" and p.status != "retired"
    )
    state = replace(state, standards=(*state.standards, s), product_standards=rows)
    state, logs = standards.standards_month(state, RngFactory(1), loaded.balance, loaded.game_data)
    tipped = next(x for x in state.standards if x.id == 99)
    assert tipped.winner == "a"
    penalties = standards.penalties(state, loaded.balance, loaded.game_data)
    assert penalties[(APP_ID, "europe")] == loaded.balance.platforms.standards.penalty
    assert any(x.template == "standard_tipped" for x in logs)
