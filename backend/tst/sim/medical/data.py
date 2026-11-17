"""Medical devices' data lookups (docs/formulas.md 50; medical.yaml, regulation.yaml's
health regulators through M34's records and helpers)."""

from __future__ import annotations

from typing import Final

from tst.sim.data_models import GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.medical.config import (
    EuClass,
    MedicalFile,
    RouteDef,
    SubcategoryDef,
    UsClass,
    UseDef,
)
from tst.sim.medical.models import Design
from tst.sim.products.models import Product
from tst.sim.regulation import data as rdata
from tst.sim.regulation.config import HealthRegulatorDef
from tst.sim.state import GameState

RELY: Final = "rely:"  # tunable-exempt: a reliance clearance's authority prefix
FDA: Final = "fda"  # tunable-exempt: the US regulator's key (medical.yaml routes)
EU: Final = "eu_notified_bodies"  # tunable-exempt: the EU's key


def enabled(data: GameData) -> bool:
    return data.medical is not None and data.regulation is not None


def file(data: GameData) -> MedicalFile:
    assert data.medical is not None
    return data.medical


def year_of(turn: int) -> int:
    return rdata.year_of(turn)


def subcategory(data: GameData, category: str) -> SubcategoryDef | None:
    if data.medical is None:
        return None
    return data.medical.subcategory(category)


def is_medical(product: Product, data: GameData) -> bool:
    return subcategory(data, product.category) is not None


def health_regulators(data: GameData) -> tuple[HealthRegulatorDef, ...]:
    rf = data.regulation
    return rf.health_regulators if rf is not None else ()


def regulator(data: GameData, key: str) -> HealthRegulatorDef:
    return next(r for r in health_regulators(data) if r.key == key)


def regulator_index(data: GameData, key: str) -> int:
    return next(i for i, r in enumerate(health_regulators(data)) if r.key == key)


def in_region(data: GameData, region: str) -> tuple[HealthRegulatorDef, ...]:
    return tuple(r for r in health_regulators(data) if r.region == region)


def part_share(data: GameData, reg: HealthRegulatorDef) -> float:
    """The regulator's share of its region's people (M34's helper, platforms.yaml parts)."""
    return rdata.part_share(data, reg)


def reliance_share(data: GameData, region: str) -> float:
    """The share of a region outside every health regulator's part: cleared by reliance."""
    return max(0.0, 1.0 - sum(part_share(data, r) for r in in_region(data, region)))


def design_of(state: GameState, product_id: int) -> Design | None:
    return next((d for d in state.med_designs if d.product_id == product_id), None)


def use_of(state: GameState, product: Product, data: GameData) -> UseDef | None:
    sub = subcategory(data, product.category)
    d = design_of(state, product.id)
    if sub is None or d is None:
        return None
    return sub.use(d.use)


def eu_class(use: UseDef, turn: int, data: GameData) -> EuClass:
    mdr = turn >= month_to_turn(file(data).dates.mdr_applies)
    return use.eu_class.mdr if mdr else use.eu_class.mdd


def us_class(use: UseDef, turn: int) -> UsClass:
    return use.us_class_at(turn)


def needs_pivotal(use: UseDef, regulator: str, turn: int, data: GameData) -> bool:
    """PMA (class III in the US) needs a successful pivotal study; so do class III and
    implantables under the MDR (50.3) and class III elsewhere (A)."""
    if regulator == FDA:
        return us_class(use, turn) == "III"
    if regulator == EU:
        return eu_class(use, turn, data) == "III" and turn >= month_to_turn(
            file(data).dates.mdr_applies
        )
    return us_class(use, turn) == "III"


def predicate(state: GameState, use: UseDef, turn: int) -> bool:
    """A predicate is on the US market (50.2): from the data's month, or once any company's
    product with this use was cleared by the FDA."""
    if use.predicate_from is not None and month_to_turn(use.predicate_from) <= turn:
        return True
    designs = {d.product_id: d.use for d in state.med_designs}
    return any(
        c.authority == FDA and c.from_turn <= turn and designs.get(c.product_id) == use.key
        for c in state.med_clearances
    )


def route_for(state: GameState, use: UseDef, regulator: str, turn: int, data: GameData) -> RouteDef:
    """The route a design takes at a regulator this month (50.2)."""
    mf = file(data)
    if regulator == FDA:
        klass = us_class(use, turn)
        if use.exempt and klass == "I":
            return mf.route("exempt")
        if klass == "III":
            return mf.route("pma")
        return mf.route("k510" if predicate(state, use, turn) else "de_novo")
    if regulator == EU:
        if eu_class(use, turn, data) == "I":
            return mf.route("ce_self")
        mdd = mf.route("ce_mdd")
        return mdd if mdd.open_at(turn) else mf.route("ce_mdr")
    routes = [r for r in mf.routes if r.regulator == regulator and r.open_at(turn)]
    return routes[0]


def window(
    state: GameState, use: UseDef, route: RouteDef, turn: int, data: GameData
) -> tuple[int, int]:
    """The months a review takes with no request for more information (the data's range)."""
    lo, hi = route.window(turn)
    if route.predicate_months is not None and predicate(state, use, turn):
        lo, hi = route.predicate_months
    if route.class_iii_months and (
        eu_class(use, turn, data) == "III" or needs_pivotal(use, route.regulator, turn, data)
    ):
        lo, hi = lo + route.class_iii_months, hi + route.class_iii_months
    return lo, hi


def shown_range(
    state: GameState, use: UseDef, route: RouteDef, turn: int, data: GameData, pccp: bool
) -> tuple[int, int]:
    """The range a filing's total time is shown as (50.2): the review window to its end plus
    a request for more information, and a change control plan's extra months."""
    lo, hi = window(state, use, route, turn, data)
    extra = route.more_info.months[1] if route.more_info.chance > 0 else 0
    return lo, hi + extra


def cleared(state: GameState, product_id: int, authority: str, turn: int) -> bool:
    return any(
        c.product_id == product_id and c.authority == authority and c.from_turn <= turn
        for c in state.med_clearances
    )


def medical_companies(state: GameState) -> set[int]:
    products = {p.id: p.company_id for p in state.products}
    return {products[d.product_id] for d in state.med_designs if d.product_id in products}
