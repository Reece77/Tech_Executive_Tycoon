"""Product actions and founder scouting (formulas.md 6, 11.2, 11.3, 11.5, 11.12; ADR-0014)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import FIRST_PRODUCT, fresh_game, with_candidates, with_product
from tst.loader import LoadedData
from tst.sim.actions import (
    Action,
    AddSegment,
    AssignUnit,
    CancelProduct,
    CreateProduct,
    CreateUnit,
    LaunchProduct,
    ScoutSearch,
    SetMarketing,
    SetPrice,
    SunsetProduct,
    UnassignUnit,
    action_from_payload,
    action_payload,
    apply_action,
)
from tst.sim.errors import (
    InvalidActionError,
    LaunchNotReadyError,
    ProductRuleError,
    SimError,
    UnknownProductError,
    UnknownSearchError,
)
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

FOUNDER = 1
PRODUCT = FIRST_PRODUCT


def act(state: GameState, action: Action, loaded: LoadedData) -> GameState:
    return apply_action(
        state, action, RngFactory(1), loaded.balance, loaded.game_data, {}, seq=1
    ).new_state


def energy(state: GameState) -> int:
    return state.person_state(FOUNDER).energy or 0


def created(loaded: LoadedData) -> GameState:
    return act(
        fresh_game(loaded),
        CreateProduct(FOUNDER, "Pipeline", "b2b_saas", ("mid_market", "smb")),
        loaded,
    )


def test_energy_costs_match_formulas_section_6(loaded: LoadedData) -> None:
    cost = loaded.balance.founder.energy_cost
    assert cost["scout_search"] == 20 and cost["create_product"] == 4
    assert cost["assign_unit"] == cost["unassign_unit"] == 2
    assert cost["set_price"] == cost["set_marketing"] == 1
    assert cost["add_segment"] == 2
    assert cost["launch_product"] == cost["sunset_product"] == cost["cancel_product"] == 3


def test_create_product(loaded: LoadedData) -> None:
    state = created(loaded)
    product = state.product(PRODUCT)
    assert product is not None
    assert (product.status, product.quality, product.feature_points, product.brand) == (
        "in_development",
        10,
        0,
        0,
    )
    assert [(s.segment, s.price_cents, s.customers) for s in state.segments_of(PRODUCT)] == [
        ("mid_market", None, 0.0),
        ("smb", None, 0.0),
    ]
    assert energy(state) == 60 - 4
    assert state.next_ids.product == PRODUCT + 1


@pytest.mark.parametrize(
    ("action", "message"),
    [
        (CreateProduct(FOUNDER, "X", "hardware", ("smb",)), "unknown category"),
        (CreateProduct(FOUNDER, "X", "b2b_saas", ("consumer",)), "does not sell to"),
        (CreateProduct(FOUNDER, "X", "b2b_saas", ()), "at least one segment"),
        (CreateProduct(FOUNDER, "X", "b2b_saas", ("smb", "smb")), "listed twice"),
        (CreateProduct(FOUNDER, "  ", "b2b_saas", ("smb",)), "needs a name"),
        (CreateProduct(FOUNDER, "pipeline", "b2b_saas", ("smb",)), "already a product"),
        (SetPrice(FOUNDER, PRODUCT, "smb", 0), "positive amount"),
        (SetPrice(FOUNDER, PRODUCT, "enterprise", 900_000), "does not sell to"),
        (AddSegment(FOUNDER, PRODUCT, "smb"), "already sells"),
        (AddSegment(FOUNDER, PRODUCT, "consumer"), "does not sell to"),
        (SetMarketing(FOUNDER, PRODUCT, -1), "zero or more"),
        (SunsetProduct(FOUNDER, PRODUCT), "cancel its development instead"),
        (UnassignUnit(FOUNDER, None), "does not work on a product"),
    ],
)
def test_rule_errors(loaded: LoadedData, action: Action, message: str) -> None:
    state = created(loaded)
    with pytest.raises(ProductRuleError, match=message):
        act(state, action, loaded)


def test_actions_on_another_companys_product_are_refused(loaded: LoadedData) -> None:
    state = created(loaded)
    with pytest.raises(UnknownProductError):
        act(state, SetPrice(FOUNDER, 1, "smb", 100), loaded)  # Salesforce's Sales Cloud
    with pytest.raises(UnknownProductError):
        act(state, LaunchProduct(FOUNDER, 999), loaded)


def test_prices_segments_and_marketing(loaded: LoadedData) -> None:
    state = act(created(loaded), SetPrice(FOUNDER, PRODUCT, "smb", 4000), loaded)
    state = act(state, AddSegment(FOUNDER, PRODUCT, "enterprise"), loaded)
    state = act(state, SetMarketing(FOUNDER, PRODUCT, 1_000_000), loaded)
    assert {s.segment: s.price_cents for s in state.segments_of(PRODUCT)} == {
        "enterprise": None,
        "mid_market": None,
        "smb": 4000,
    }
    product = state.product(PRODUCT)
    assert product is not None and product.marketing_budget_cents == 1_000_000
    assert energy(state) == 60 - 4 - 1 - 2 - 1
    with pytest.raises(ProductRuleError, match="already the price"):
        act(state, SetPrice(FOUNDER, PRODUCT, "smb", 4000), loaded)


def test_a_unit_works_on_at_most_one_product(loaded: LoadedData) -> None:
    state = act(created(loaded), CreateProduct(FOUNDER, "Second", "dev_tools", ("smb",)), loaded)
    state = act(state, AssignUnit(FOUNDER, PRODUCT, None), loaded)
    assert state.player.root_product_id == PRODUCT
    with pytest.raises(ProductRuleError, match="already works on Pipeline"):
        act(state, AssignUnit(FOUNDER, PRODUCT + 1, None), loaded)
    with pytest.raises(ProductRuleError, match="already works on Pipeline"):
        act(state, AssignUnit(FOUNDER, PRODUCT, None), loaded)
    state = act(state, CreateUnit(FOUNDER, "team", "Core"), loaded)
    state = act(state, AssignUnit(FOUNDER, PRODUCT, 1), loaded)  # a product may have several
    assert state.units[0].product_id == PRODUCT
    state = act(state, UnassignUnit(FOUNDER, None), loaded)
    state = act(state, AssignUnit(FOUNDER, PRODUCT + 1, None), loaded)
    assert state.player.root_product_id == PRODUCT + 1
    with pytest.raises(SimError):
        act(state, AssignUnit(FOUNDER, PRODUCT, 99), loaded)


def test_launch_is_refused_below_the_thresholds_naming_what_is_missing(
    loaded: LoadedData,
) -> None:
    state = created(loaded)
    with pytest.raises(LaunchNotReadyError) as info:
        act(state, LaunchProduct(FOUNDER, PRODUCT), loaded)
    message = info.value.message
    assert "quality 10 of the 25 needed" in message
    assert "feature score 0 of the 30 needed" in message
    assert "a price for Mid-market" in message and "a price for SMB" in message
    assert energy(state) == 56  # nothing was spent


def test_launch_and_sunset(loaded: LoadedData) -> None:
    state = with_product(fresh_game(loaded), status="in_development", quality=30, feature_points=40)
    state = replace(state, turn=1)  # feature score 40 / F_exp(0) = 66.7
    state = act(state, LaunchProduct(FOUNDER, PRODUCT), loaded)
    product = state.product(PRODUCT)
    assert product is not None and product.status == "live" and product.launched_turn == 1
    with pytest.raises(ProductRuleError, match="already live"):
        act(state, LaunchProduct(FOUNDER, PRODUCT), loaded)
    result = apply_action(
        state,
        SunsetProduct(FOUNDER, PRODUCT),
        RngFactory(1),
        loaded.balance,
        loaded.game_data,
        {},
        seq=1,
    )
    sunset = result.new_state.product(PRODUCT)
    assert sunset is not None and sunset.status == "sunset" and sunset.sunset_turn == 1
    with pytest.raises(ProductRuleError, match="being sunset"):
        act(result.new_state, AddSegment(FOUNDER, PRODUCT, "enterprise"), loaded)


def test_cancel_retires_a_product_in_development_and_frees_its_units(
    loaded: LoadedData,
) -> None:
    state = act(created(loaded), CreateUnit(FOUNDER, "team", "Core"), loaded)
    unit = state.units[0].id
    state = act(state, AssignUnit(FOUNDER, PRODUCT, None), loaded)
    state = act(state, AssignUnit(FOUNDER, PRODUCT, unit), loaded)
    before = energy(state)
    with pytest.raises(ProductRuleError, match="cancel its development instead"):
        act(state, SunsetProduct(FOUNDER, PRODUCT), loaded)
    state = act(state, CancelProduct(FOUNDER, PRODUCT), loaded)
    product = state.product(PRODUCT)
    assert product is not None and product.status == "retired"
    assert product.retired_turn == state.turn
    assert state.player.root_product_id is None
    assert state.unit(unit) is not None and state.unit(unit).product_id is None  # type: ignore[union-attr]
    assert energy(state) == before - 3
    with pytest.raises(UnknownProductError):
        act(state, CancelProduct(FOUNDER, PRODUCT), loaded)
    # the name is free again and a freed unit can take another product
    state = act(state, CreateProduct(FOUNDER, "Pipeline", "b2b_saas", ("smb",)), loaded)
    assert state.products[-1].name == "Pipeline" and state.products[-1].id != PRODUCT


def test_only_a_product_in_development_can_be_cancelled(loaded: LoadedData) -> None:
    state = with_product(fresh_game(loaded))  # live
    with pytest.raises(ProductRuleError, match="only a product in development"):
        act(state, CancelProduct(FOUNDER, PRODUCT), loaded)
    assert energy(state) == 60


def test_launch_posts_an_inbox_note(loaded: LoadedData) -> None:
    state = with_product(
        fresh_game(loaded),
        status="in_development",
        quality=30,
        feature_points=40,
        prices={"smb": 4000, "mid_market": 70_000},
    )
    result = apply_action(
        state,
        LaunchProduct(FOUNDER, PRODUCT),
        RngFactory(1),
        loaded.balance,
        loaded.game_data,
        {},
        seq=1,
    )
    [note] = result.log_items
    assert note.template == "product_launched" and note.link_kind == "product"
    assert dict(note.params)["segments"] == "Mid-market and SMB"


def test_founder_scouts_a_search_for_20_energy(loaded: LoadedData) -> None:
    state = with_candidates(loaded, fresh_game(loaded), 3)
    search = state.searches[0].id
    before = [state.reveal(1, c.person_id) for c in state.candidates]
    after_state = act(state, ScoutSearch(FOUNDER, search), loaded)
    assert energy(after_state) == 60 - 20
    for old, c in zip(before, after_state.candidates, strict=True):
        new = after_state.reveal(1, c.person_id)
        assert old is not None and new is not None
        assert new.record("software_engineering").hw < old.record("software_engineering").hw
    with pytest.raises(UnknownSearchError):
        act(state, ScoutSearch(FOUNDER, 99), loaded)


def test_scouting_needs_open_candidates(loaded: LoadedData) -> None:
    state = with_candidates(loaded, fresh_game(loaded), 1)
    state = replace(state, candidates=tuple(replace(c, status="hired") for c in state.candidates))
    with pytest.raises(InvalidActionError, match="no open candidates"):
        act(state, ScoutSearch(FOUNDER, state.searches[0].id), loaded)


def test_payloads_round_trip(loaded: LoadedData) -> None:
    actions: list[Action] = [
        CreateProduct(FOUNDER, "Pipeline", "b2b_saas", ("smb",)),
        SetPrice(FOUNDER, PRODUCT, "smb", 4000),
        AddSegment(FOUNDER, PRODUCT, "mid_market"),
        AssignUnit(FOUNDER, PRODUCT, None),
        UnassignUnit(FOUNDER, 3),
        SetMarketing(FOUNDER, PRODUCT, 10),
        LaunchProduct(FOUNDER, PRODUCT),
        SunsetProduct(FOUNDER, PRODUCT),
        ScoutSearch(FOUNDER, 2),
    ]
    for action in actions:
        payload = action_payload(action)
        if isinstance(action, CreateProduct):
            payload = {**payload, "segments": list(payload["segments"])}  # as JSON stores it
        assert action_from_payload(payload) == action
