"""The player's platform actions (ADR-0014; docs/formulas.md 44.1, 44.5-44.7). They take effect
at once and spend the founder's energy.

- **SetDevicePlatform**: a device line runs another platform (Android, or the group's own
  launched OS). A one-off (40.2): devices already sold stay on the old one and are replaced at
  the market's pace; the line loses `switch_energy_months` of feature gain.
- **SetPlatformRules**: an own platform's standard fee (within `own_fee_range`), review
  strictness, self-preferencing, anti-steering, side-loading and its OS licence for other OEMs
  (None = not licensed).
- **CreateDeveloperPlatform**: a live `ai_models`, `cloud_hosting` or `dev_tools` product becomes
  a developer platform's base (44.1).
- **OpenSourceProduct**: open (a one-off) or close again (44.6).
- **SetSteering**: an app links its users to pay outside the stores (lower fees, more reviews).
- **ComplyListing**: comply with a removal (44.5): relisted at once.
- **AdoptStandard**: move a product to a tipped contest's winner (44.7): `adopt_months`.

An `os` product's launch founds its platform (`on_launch`, from products' launch).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import PlatformRuleError
from tst.sim.geopolitics import world
from tst.sim.log import inbox_item
from tst.sim.platforms import data as pdata
from tst.sim.platforms import gatekeep, opensource
from tst.sim.platforms.models import DeviceRun, Platform, PlatformRegion
from tst.sim.products.models import SELLING, Product
from tst.sim.state import GameState, with_product

DEVELOPER_CATEGORIES: Final = ("ai_models", "cloud_hosting", "dev_tools")  # tunable-exempt: 44.1
OS: Final = "os"  # tunable-exempt: the pseudo-category


@dataclass(frozen=True, slots=True)
class SetDevicePlatform:
    actor_id: int
    product_id: int
    platform_id: int
    kind: Literal["set_device_platform"] = "set_device_platform"


@dataclass(frozen=True, slots=True)
class SetPlatformRules:
    actor_id: int
    platform_id: int
    fee: float | None = None
    strictness: Literal["lenient", "standard", "strict"] | None = None
    self_pref: Literal["off", "mild", "strong"] | None = None
    anti_steering: bool | None = None
    side_loading: bool | None = None
    licence_cents: int | None = None
    stop_licensing: bool = False
    kind: Literal["set_platform_rules"] = "set_platform_rules"


@dataclass(frozen=True, slots=True)
class CreateDeveloperPlatform:
    actor_id: int
    product_id: int
    kind: Literal["create_developer_platform"] = "create_developer_platform"


@dataclass(frozen=True, slots=True)
class OpenSourceProduct:
    actor_id: int
    product_id: int
    open: bool = True
    kind: Literal["open_source"] = "open_source"


@dataclass(frozen=True, slots=True)
class SetSteering:
    actor_id: int
    product_id: int
    on: bool = True
    kind: Literal["set_steering"] = "set_steering"


@dataclass(frozen=True, slots=True)
class ComplyListing:
    actor_id: int
    product_id: int
    kind: Literal["comply_listing"] = "comply_listing"


@dataclass(frozen=True, slots=True)
class AdoptStandard:
    actor_id: int
    product_id: int
    standard_id: int
    kind: Literal["adopt_standard"] = "adopt_standard"


type PlatformAction = (
    SetDevicePlatform
    | SetPlatformRules
    | CreateDeveloperPlatform
    | OpenSourceProduct
    | SetSteering
    | ComplyListing
    | AdoptStandard
)
ACTION_TYPES: Final[dict[str, type]] = {
    "set_device_platform": SetDevicePlatform,
    "set_platform_rules": SetPlatformRules,
    "create_developer_platform": CreateDeveloperPlatform,
    "open_source": OpenSourceProduct,
    "set_steering": SetSteering,
    "comply_listing": ComplyListing,
    "adopt_standard": AdoptStandard,
}


def _group_product(state: GameState, product_id: int) -> Product:
    product = state.product(product_id)
    group = {c.id for c in world.group(state)}
    if product is None or product.company_id not in group or product.status == "retired":
        raise PlatformRuleError(f"no product {product_id} in the group")
    return product


def _own_platform(state: GameState, platform_id: int) -> Platform:
    p = state.platform(platform_id)
    group = {c.id for c in world.group(state)}
    if p is None or p.owner_id not in group:
        raise PlatformRuleError(f"platform {platform_id} is not the group's")
    return p


def _found(
    state: GameState, product: Product, kind: Literal["device", "developer"], data: GameData
) -> GameState:
    pid = pdata.next_platform_id(state)
    platform = Platform(
        id=pid,
        key=f"own_{pid}",
        name=product.name,
        store=f"{product.name} Store" if kind == "device" else f"{product.name} platform",
        kind=kind,
        owner_id=product.company_id,
        owner_label=state.company(product.company_id).name,
        regions=tuple(data.region_keys),
        launched_turn=state.turn,
        historical=False,
        product_id=product.id,
        licensable=kind == "device",
        fee=0.30,  # tunable-exempt: the industry's standard rate, the owner's to change
    )
    rows = tuple(PlatformRegion(pid, region, 0.0, 0.0, 0.0) for region in data.region_keys)
    return replace(
        state,
        platforms=(*state.platforms, platform),
        platform_regions=(*state.platform_regions, *rows),
    )


def on_launch(state: GameState, product: Product, data: GameData) -> GameState:
    """An `os` product's launch founds its device platform (44.1)."""
    if product.category != OS or not pdata.enabled(data) or not state.platforms:
        return state
    if any(p.product_id == product.id for p in state.platforms):
        return state
    return _found(state, product, "device", data)


def apply_platforms(
    state: GameState, action: PlatformAction, balance: Balance, data: GameData
) -> Outcome:
    if not pdata.enabled(data) or not state.platforms:
        raise PlatformRuleError("platforms are not running in this game yet")
    acting_company(state, action.actor_id)
    pb = balance.platforms
    match action:
        case SetDevicePlatform():
            product = _group_product(state, action.product_id)
            if product.category != pdata.DEVICES:
                raise PlatformRuleError(f"{product.name} is not a device line")
            target = state.platform(action.platform_id)
            if target is None or target.kind != "device" or target.ended_turn is not None:
                raise PlatformRuleError("no such device platform")
            group = {c.id for c in world.group(state)}
            if target.historical and not target.licensable:
                raise PlatformRuleError(f"{target.name} is not licensed to other makers")
            if (
                not target.historical
                and target.owner_id not in group
                and target.licence_cents is None
            ):
                raise PlatformRuleError(f"{target.name} is not licensed")
            run = state.device_run(product.id)
            if run is not None and run.platform_id == target.id:
                raise PlatformRuleError(f"{product.name} already runs {target.name}")
            state = spend_energy(
                state,
                action.actor_id,
                "set_device_platform",
                balance,
                cost=pb.energy["set_device_platform"],
            )
            old = run.platform_id if run is not None else None
            runs = tuple(d for d in state.device_runs if d.product_id != product.id)
            state = replace(
                state,
                device_runs=(
                    *runs,
                    DeviceRun(
                        product.id, target.id, state.turn, old, 1.0 if old is not None else 0.0
                    ),
                ),
            )
            lost = pb.switch_energy_months * data.category(product.category).features_per_month
            state = with_product(
                state, replace(product, feature_points=max(0.0, product.feature_points - lost))
            )
            return Outcome(state)
        case SetPlatformRules():
            p = _own_platform(state, action.platform_id)
            lo, hi = pb.own_fee_range
            if action.fee is not None and not lo <= action.fee <= hi:
                raise PlatformRuleError(f"a store's fee must be between {lo:.0%} and {hi:.0%}")
            if action.licence_cents is not None and (
                action.licence_cents < 0 or p.kind != "device"
            ):
                raise PlatformRuleError(
                    "only a device platform's licence can be set, at 0 or more cents"
                )
            state = spend_energy(
                state,
                action.actor_id,
                "set_platform_rules",
                balance,
                cost=pb.energy["set_platform_rules"],
            )
            updated = replace(
                p,
                fee=action.fee if action.fee is not None else p.fee,
                strictness=action.strictness or p.strictness,
                self_pref=action.self_pref or p.self_pref,
                anti_steering=p.anti_steering
                if action.anti_steering is None
                else action.anti_steering,
                side_loading=p.side_loading if action.side_loading is None else action.side_loading,
                licence_cents=None
                if action.stop_licensing
                else (
                    action.licence_cents if action.licence_cents is not None else p.licence_cents
                ),
            )
            return Outcome(
                replace(
                    state, platforms=tuple(updated if x.id == p.id else x for x in state.platforms)
                )
            )
        case CreateDeveloperPlatform():
            product = _group_product(state, action.product_id)
            if product.category not in DEVELOPER_CATEGORIES or product.status not in SELLING:
                raise PlatformRuleError(
                    "a developer platform needs a live model API, cloud or developer tool"
                )
            if any(p.product_id == product.id for p in state.platforms):
                raise PlatformRuleError(f"{product.name} is already a platform")
            state = spend_energy(
                state,
                action.actor_id,
                "create_developer_platform",
                balance,
                cost=pb.energy["create_developer_platform"],
            )
            return Outcome(_found(state, product, "developer", data))
        case OpenSourceProduct():
            product = _group_product(state, action.product_id)
            is_open = opensource.open_of(state, product.id) is not None
            if action.open == is_open:
                raise PlatformRuleError(
                    f"{product.name} is already {'open' if is_open else 'closed'}"
                )
            if action.open and any(o.product_id == product.id for o in state.open_sources):
                raise PlatformRuleError(f"{product.name} was opened before: opening is a one-off")
            state = spend_energy(
                state, action.actor_id, "open_source", balance, cost=pb.energy["open_source"]
            )
            if action.open:
                return Outcome(opensource.open_product(state, product, balance, data))
            state, logs = opensource.close_product(state, product, balance, data)
            return Outcome(state, log=tuple(logs))
        case SetSteering():
            product = _group_product(state, action.product_id)
            if product.category not in pb.app_categories:
                raise PlatformRuleError(f"{product.name} is not sold through app stores")
            on = product.id in state.steering_products
            if action.on == on:
                raise PlatformRuleError("that is already the setting")
            state = spend_energy(
                state, action.actor_id, "set_steering", balance, cost=pb.energy["set_steering"]
            )
            steering = tuple(x for x in state.steering_products if x != product.id)
            return Outcome(
                replace(state, steering_products=(*steering, product.id) if action.on else steering)
            )
        case ComplyListing():
            product = _group_product(state, action.product_id)
            rows = gatekeep.removed_of(state, product.id)
            if not rows:
                raise PlatformRuleError(f"{product.name} is not removed from any store")
            state = spend_energy(
                state, action.actor_id, "comply_listing", balance, cost=pb.energy["comply_listing"]
            )
            state = gatekeep.relist(state, rows, balance)
            steering = tuple(x for x in state.steering_products if x != product.id)
            note = inbox_item(
                state.turn,
                product.company_id,
                "platform_complied",
                link_kind="product",
                link_id=product.id,
                product=product.name,
            )
            return Outcome(replace(state, steering_products=steering), log=(note,))
        case AdoptStandard():
            product = _group_product(state, action.product_id)
            s = next((x for x in state.standards if x.id == action.standard_id), None)
            row = next(
                (
                    x
                    for x in state.product_standards
                    if x.product_id == product.id and x.standard_id == action.standard_id
                ),
                None,
            )
            if s is None or s.winner is None or row is None:
                raise PlatformRuleError("no tipped contest for that product")
            if row.format == s.winner or row.adopting_until is not None:
                raise PlatformRuleError(f"{product.name} is already on (or moving to) {s.winner}")
            state = spend_energy(
                state, action.actor_id, "adopt_standard", balance, cost=pb.energy["adopt_standard"]
            )
            until = state.turn + pb.standards.adopt_months
            formats = tuple(
                replace(x, adopting_until=until) if x is row else x for x in state.product_standards
            )
            return Outcome(replace(state, product_standards=formats))
    raise PlatformRuleError("unknown platform action")
