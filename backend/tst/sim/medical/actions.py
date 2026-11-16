"""The Medical screen's actions (docs/formulas.md 50), immediate (ADR-0014).

- `DesignDevice`: choose a medical product's intended use (its class and route follow) and
  whether its filings carry a predetermined change control plan (software only).
- `SubmitDevice`: file the device with a health regulator by the route its design takes.
- `StartStudy`: start a feasibility, pivotal or post-market study.
- `RequestCoverage`: ask a region's payers to cover a cleared device.
- `SetMedicalSupport`: a device's monthly clinical education a region and its surveillance.
- `SetPlantQuality`: an assembly plant's quality system."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import MedicalRuleError
from tst.sim.medical import coverage, quality, routes, studies
from tst.sim.medical import data as md
from tst.sim.medical.config import QualityLevel, StudyKind
from tst.sim.medical.models import Design
from tst.sim.products.models import Product
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class DesignDevice:
    actor_id: int
    product_id: int
    use: str
    pccp: bool = False
    kind: Literal["medical_design"] = "medical_design"


@dataclass(frozen=True, slots=True)
class SubmitDevice:
    actor_id: int
    product_id: int
    regulator: str
    kind: Literal["medical_submit"] = "medical_submit"


@dataclass(frozen=True, slots=True)
class StartStudy:
    actor_id: int
    product_id: int
    study: StudyKind
    patients: int | None = None
    kind: Literal["medical_study"] = "medical_study"


@dataclass(frozen=True, slots=True)
class RequestCoverage:
    actor_id: int
    product_id: int
    region: str
    kind: Literal["medical_coverage"] = "medical_coverage"


@dataclass(frozen=True, slots=True)
class SetMedicalSupport:
    actor_id: int
    product_id: int
    training_cents: int
    surveillance: bool
    kind: Literal["medical_support"] = "medical_support"


@dataclass(frozen=True, slots=True)
class SetPlantQuality:
    actor_id: int
    facility_id: int
    level: QualityLevel
    kind: Literal["plant_quality"] = "plant_quality"


type MedicalAction = (
    DesignDevice | SubmitDevice | StartStudy | RequestCoverage | SetMedicalSupport | SetPlantQuality
)
ACTION_TYPES: Final[dict[str, type]] = {
    "medical_design": DesignDevice,
    "medical_submit": SubmitDevice,
    "medical_study": StartStudy,
    "medical_coverage": RequestCoverage,
    "medical_support": SetMedicalSupport,
    "plant_quality": SetPlantQuality,
}


def _own(state: GameState, company_id: int, product_id: int, data: GameData) -> Product:
    product = state.product(product_id)
    if product is None or product.company_id != company_id:
        raise MedicalRuleError(f"no product {product_id} of the company")
    if not md.is_medical(product, data):
        raise MedicalRuleError(f"{product.name} is not a medical device")
    return product


def apply_medical(
    state: GameState,
    action: MedicalAction,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> Outcome:
    if not md.enabled(data):
        raise MedicalRuleError("medical devices are not in this game")
    company_id = acting_company(state, action.actor_id)
    mb = balance.medical
    match action:
        case DesignDevice():
            product = _own(state, company_id, action.product_id, data)
            sub = md.subcategory(data, product.category)
            assert sub is not None
            if action.use not in {u.key for u in sub.uses}:
                raise MedicalRuleError(f"{sub.label} has no intended use {action.use!r}")
            if action.pccp and not sub.software:
                raise MedicalRuleError("a change control plan is for software devices")
            if any(s.product_id == product.id for s in state.med_submissions):
                old = md.design_of(state, product.id)
                if old is not None and old.use != action.use:
                    raise MedicalRuleError("a filed device keeps its intended use")
            old = md.design_of(state, product.id)
            design = (
                replace(old, use=action.use, pccp=action.pccp)
                if old is not None
                else Design(product.id, action.use, action.pccp)
            )
            rest = tuple(d for d in state.med_designs if d.product_id != product.id)
            return Outcome(replace(state, med_designs=(*rest, design)))
        case SubmitDevice():
            product = _own(state, company_id, action.product_id, data)
            state = spend_energy(
                state, action.actor_id, "medical_submit", balance, cost=mb.review.energy
            )
            state, entries, logs = routes.submit(
                state, product, action.regulator, rng, balance, data
            )
            return Outcome(state, tuple(entries), tuple(logs))
        case StartStudy():
            product = _own(state, company_id, action.product_id, data)
            state = spend_energy(
                state, action.actor_id, "medical_study", balance, cost=mb.study.energy
            )
            state, logs = studies.start(state, product, action.study, action.patients, data)
            return Outcome(state, (), tuple(logs))
        case RequestCoverage():
            product = _own(state, company_id, action.product_id, data)
            state = spend_energy(
                state, action.actor_id, "medical_coverage", balance, cost=mb.coverage.energy
            )
            state, logs = coverage.request(state, product, action.region, rng, data)
            return Outcome(state, (), tuple(logs))
        case SetMedicalSupport():
            product = _own(state, company_id, action.product_id, data)
            if action.training_cents < 0:
                raise MedicalRuleError("clinical education cannot be negative")
            old = md.design_of(state, product.id)
            if old is None:
                raise MedicalRuleError("choose the device's intended use first")
            design = replace(
                old, training_cents=action.training_cents, surveillance=action.surveillance
            )
            rest = tuple(d for d in state.med_designs if d.product_id != product.id)
            return Outcome(replace(state, med_designs=(*rest, design)))
        case SetPlantQuality():
            f = state.facility(action.facility_id)
            if f is None or f.company_id != company_id or f.kind != balance.hardware.plant_kind:
                raise MedicalRuleError(f"no assembly plant {action.facility_id} of the company")
            state = spend_energy(
                state, action.actor_id, "plant_quality", balance, cost=mb.quality_energy
            )
            return Outcome(quality.set_level(state, f.id, action.level))
