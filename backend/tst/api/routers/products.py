"""Save-scoped product and market routes (M3a): categories, markets, the player's products,
product actions with a launch-readiness check, a price preview, and founder scouting.

Actions run through `repository.run_action` with the founder as actor (ADR-0014). Responses
carry public scores only (formulas.md 11.13): never Q_cap, development skill, team output,
sales capacity or per-person contributions.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import product_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _act, _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.people import ActionOut
from tst.api.schemas.products import (
    AssignIn,
    CategoryOut,
    CreateProductIn,
    MarketingIn,
    MarketOut,
    PriceIn,
    PricePreviewOut,
    ProductActionOut,
    ProductOut,
    SegmentIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import (
    Action,
    AddSegment,
    AssignUnit,
    CancelProduct,
    CreateProduct,
    LaunchProduct,
    ScoutSearch,
    SetMarketing,
    SetPrice,
    SunsetProduct,
    UnassignUnit,
)
from tst.sim.actions.products import assignment_of, own_product
from tst.sim.errors import ProductRuleError
from tst.sim.products.models import Product
from tst.sim.state import GameState

router = APIRouter(prefix="/api/saves/{save_id}", tags=["products"])

HISTORY_MONTHS = 12  # months of history in a product response


def _history_since(state: GameState, data: LoadedData) -> int:
    """Enough months for the history and the growth label (11.2)."""
    months = max(HISTORY_MONTHS, data.balance.products.growth_label_months + 1)
    return state.turn - months


def _product(path: Path, state: GameState, product: Product, data: LoadedData) -> ProductOut:
    with repository.open_session(path) as session:
        history = repository.product_history(session, product.id, _history_since(state, data))
    return product_views.product_out(state, product, history, data)


def _product_act(path: Path, data: LoadedData, action: Action, product_id: int) -> ProductActionOut:
    result = repository.run_action(path, data, action)
    state = result.new_state
    product = own_product(state, state.player.id, product_id)
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return ProductActionOut(
        product=_product(path, state, product, data),
        energy=views.energy(state, data),
        unread_inbox=unread,
    )


# --- Markets --------------------------------------------------------------------------------


@router.get(
    "/categories", response_model=list[CategoryOut], responses=ERRORS, operation_id="listCategories"
)
def list_categories(save_id: str, settings: SettingsDep, data: DataDep) -> list[CategoryOut]:
    """Categories and their segments, with today's addressable demand."""
    return product_views.categories_out(_state(_path(settings, save_id)), data)


@router.get(
    "/markets/{category}", response_model=MarketOut, responses=ERRORS, operation_id="getMarket"
)
def get_market(save_id: str, category: str, settings: SettingsDep, data: DataDep) -> MarketOut:
    """Every product selling in the category: owner, public scores, appeal, customers and
    share of served customers, per segment."""
    return product_views.market_out(_state(_path(settings, save_id)), category, data)


# --- The player's products ------------------------------------------------------------------


@router.get(
    "/products", response_model=list[ProductOut], responses=ERRORS, operation_id="listProducts"
)
def list_products(save_id: str, settings: SettingsDep, data: DataDep) -> list[ProductOut]:
    """The player's products that are not retired, by id."""
    path = _path(settings, save_id)
    state = _state(path)
    return [_product(path, state, p, data) for p in state.company_products(state.player.id)]


@router.get(
    "/products/{product_id}",
    response_model=ProductOut,
    responses=ERRORS,
    operation_id="getProduct",
)
def get_product(save_id: str, product_id: int, settings: SettingsDep, data: DataDep) -> ProductOut:
    path = _path(settings, save_id)
    state = _state(path)
    return _product(path, state, own_product(state, state.player.id, product_id), data)


@router.post(
    "/products",
    response_model=ProductActionOut,
    status_code=201,
    responses=ERRORS,
    operation_id="createProduct",
)
def create_product(
    save_id: str, body: CreateProductIn, settings: SettingsDep, data: DataDep
) -> ProductActionOut:
    path = _path(settings, save_id)
    state = _state(path)
    action = CreateProduct(_founder_id(state), body.name, body.category, tuple(body.segments))
    return _product_act(path, data, action, state.next_ids.product)


@router.post(
    "/products/{product_id}/price",
    response_model=ProductActionOut,
    responses=ERRORS,
    operation_id="setProductPrice",
)
def set_price(
    save_id: str, product_id: int, body: PriceIn, settings: SettingsDep, data: DataDep
) -> ProductActionOut:
    path = _path(settings, save_id)
    action = SetPrice(_founder_id(_state(path)), product_id, body.segment, body.price_cents)
    return _product_act(path, data, action, product_id)


@router.post(
    "/products/{product_id}/price-preview",
    response_model=PricePreviewOut,
    responses=ERRORS,
    operation_id="previewProductPrice",
)
def preview_price(
    save_id: str, product_id: int, body: PriceIn, settings: SettingsDep, data: DataDep
) -> PricePreviewOut:
    """Appeal and share* at a price against the current competitors. Nothing is saved."""
    state = _state(_path(settings, save_id))
    product = own_product(state, state.player.id, product_id)
    return product_views.price_preview(state, product, body.segment, body.price_cents, data)


@router.post(
    "/products/{product_id}/segments",
    response_model=ProductActionOut,
    responses=ERRORS,
    operation_id="addProductSegment",
)
def add_segment(
    save_id: str, product_id: int, body: SegmentIn, settings: SettingsDep, data: DataDep
) -> ProductActionOut:
    path = _path(settings, save_id)
    action = AddSegment(_founder_id(_state(path)), product_id, body.segment)
    return _product_act(path, data, action, product_id)


@router.post(
    "/products/{product_id}/assign",
    response_model=ProductActionOut,
    responses=ERRORS,
    operation_id="assignUnitToProduct",
)
def assign_unit(
    save_id: str, product_id: int, body: AssignIn, settings: SettingsDep, data: DataDep
) -> ProductActionOut:
    """Put a unit (or, with a null unit, the company root) on the product."""
    path = _path(settings, save_id)
    action = AssignUnit(_founder_id(_state(path)), product_id, body.unit_id)
    return _product_act(path, data, action, product_id)


@router.post(
    "/products/{product_id}/unassign",
    response_model=ProductActionOut,
    responses=ERRORS,
    operation_id="unassignUnitFromProduct",
)
def unassign_unit(
    save_id: str, product_id: int, body: AssignIn, settings: SettingsDep, data: DataDep
) -> ProductActionOut:
    path = _path(settings, save_id)
    state = _state(path)
    product = own_product(state, state.player.id, product_id)
    if assignment_of(state, state.player.id, body.unit_id) != product.id:
        raise ProductRuleError(f"that unit does not work on {product.name}")
    return _product_act(path, data, UnassignUnit(_founder_id(state), body.unit_id), product_id)


@router.post(
    "/products/{product_id}/marketing",
    response_model=ProductActionOut,
    responses=ERRORS,
    operation_id="setProductMarketing",
)
def set_marketing(
    save_id: str, product_id: int, body: MarketingIn, settings: SettingsDep, data: DataDep
) -> ProductActionOut:
    path = _path(settings, save_id)
    action = SetMarketing(_founder_id(_state(path)), product_id, body.budget_cents)
    return _product_act(path, data, action, product_id)


@router.post(
    "/products/{product_id}/launch",
    response_model=ProductActionOut,
    responses=ERRORS,
    operation_id="launchProduct",
)
def launch(save_id: str, product_id: int, settings: SettingsDep, data: DataDep) -> ProductActionOut:
    """Refused with `launch_not_ready`, naming what is missing, below the thresholds."""
    path = _path(settings, save_id)
    return _product_act(
        path, data, LaunchProduct(_founder_id(_state(path)), product_id), product_id
    )


@router.post(
    "/products/{product_id}/sunset",
    response_model=ProductActionOut,
    responses=ERRORS,
    operation_id="sunsetProduct",
)
def sunset(save_id: str, product_id: int, settings: SettingsDep, data: DataDep) -> ProductActionOut:
    path = _path(settings, save_id)
    return _product_act(
        path, data, SunsetProduct(_founder_id(_state(path)), product_id), product_id
    )


@router.post(
    "/products/{product_id}/cancel",
    response_model=ActionOut,
    responses=ERRORS,
    operation_id="cancelProduct",
)
def cancel(save_id: str, product_id: int, settings: SettingsDep, data: DataDep) -> ActionOut:
    """Cancel a product in development: it retires at once and its units are freed."""
    path = _path(settings, save_id)
    _, out = _act(path, data, CancelProduct(_founder_id(_state(path)), product_id))
    return out


# --- Founder scouting -----------------------------------------------------------------------


@router.post(
    "/recruitment/searches/{search_id}/scout",
    response_model=ActionOut,
    responses=ERRORS,
    operation_id="scoutSearch",
)
def scout_search(save_id: str, search_id: int, settings: SettingsDep, data: DataDep) -> ActionOut:
    """The founder scouts every open candidate of the search (20 energy, formulas.md 11.12)."""
    path = _path(settings, save_id)
    _, out = _act(path, data, ScoutSearch(_founder_id(_state(path)), search_id))
    return out
