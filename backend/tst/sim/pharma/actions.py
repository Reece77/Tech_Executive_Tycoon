"""The Pharma screen's actions (docs/formulas.md 55), immediate (ADR-0014).

- `StartProgramme`: a new molecule in discovery for an indication, with AI discovery or not.
- `StartTrial`: start a ready programme's next trial with a design (lean, standard, large), or
  re-run a failed stage with a new design (a redesign).
- `StopProgramme`: stop a programme (its stage's spending ends).
- `FileDrug`: file a programme with a drug regulator.
- `SetDrugPrice`: a marketed drug's US list price and commercial support.
- `BuildPharmaPlant`, `SetPharmaPlantQuality`, `ChooseCmo`: manufacturing.
- `LicenseAsset`, `OutLicense`, `LicensePlatform`: licensing and partnering."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import PharmaRuleError
from tst.sim.pharma import approval, licensing, pipeline, supply
from tst.sim.pharma import data as pd
from tst.sim.pharma.config import DESIGNS, MODALITIES, Design, Modality, PlantKind
from tst.sim.pharma.models import Programme, Supply
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class StartProgramme:
    actor_id: int
    name: str
    indication: str
    modality: Modality
    ai: bool = False
    kind: Literal["pharma_start"] = "pharma_start"


@dataclass(frozen=True, slots=True)
class StartTrial:
    actor_id: int
    programme_id: int
    design: Design = "standard"
    kind: Literal["pharma_trial"] = "pharma_trial"


@dataclass(frozen=True, slots=True)
class StopProgramme:
    actor_id: int
    programme_id: int
    kind: Literal["pharma_stop"] = "pharma_stop"


@dataclass(frozen=True, slots=True)
class FileDrug:
    actor_id: int
    programme_id: int
    regulator: str
    kind: Literal["pharma_file"] = "pharma_file"


@dataclass(frozen=True, slots=True)
class SetDrugPrice:
    actor_id: int
    programme_id: int
    list_cents: int  # real US list price a patient-year
    support: float = 1.0
    kind: Literal["pharma_price"] = "pharma_price"


@dataclass(frozen=True, slots=True)
class BuildPharmaPlant:
    actor_id: int
    plant: PlantKind
    region: str
    kind: Literal["pharma_plant"] = "pharma_plant"


@dataclass(frozen=True, slots=True)
class SetPharmaPlantQuality:
    actor_id: int
    plant_id: int
    level: Literal["low", "standard", "high"]
    kind: Literal["pharma_plant_quality"] = "pharma_plant_quality"


@dataclass(frozen=True, slots=True)
class ChooseCmo:
    actor_id: int
    plant: PlantKind
    cmo: str
    kind: Literal["pharma_cmo"] = "pharma_cmo"


@dataclass(frozen=True, slots=True)
class LicenseAsset:
    actor_id: int
    asset_id: int
    acquire: bool = False
    upfront_cents: int | None = None  # M47 (58.4): a negotiated upfront (set by an agreement)
    kind: Literal["pharma_license_in"] = "pharma_license_in"


@dataclass(frozen=True, slots=True)
class OutLicense:
    actor_id: int
    programme_id: int
    rival_id: int
    co_develop: bool = False
    upfront_cents: int | None = None  # M47 (58.4): a negotiated upfront (set by an agreement)
    kind: Literal["pharma_license_out"] = "pharma_license_out"


@dataclass(frozen=True, slots=True)
class LicensePlatform:
    actor_id: int
    rival_id: int
    kind: Literal["pharma_platform"] = "pharma_platform"


type PharmaAction = (
    StartProgramme
    | StartTrial
    | StopProgramme
    | FileDrug
    | SetDrugPrice
    | BuildPharmaPlant
    | SetPharmaPlantQuality
    | ChooseCmo
    | LicenseAsset
    | OutLicense
    | LicensePlatform
)
ACTION_TYPES: Final[dict[str, type]] = {
    "pharma_start": StartProgramme,
    "pharma_trial": StartTrial,
    "pharma_stop": StopProgramme,
    "pharma_file": FileDrug,
    "pharma_price": SetDrugPrice,
    "pharma_plant": BuildPharmaPlant,
    "pharma_plant_quality": SetPharmaPlantQuality,
    "pharma_cmo": ChooseCmo,
    "pharma_license_in": LicenseAsset,
    "pharma_license_out": OutLicense,
    "pharma_platform": LicensePlatform,
}
MAX_SUPPORT: Final = 2.0  # tunable-exempt: the screen's slider's end (twice the full level)


def own(state: GameState, company_id: int, programme_id: int) -> Programme:
    p = next((q for q in state.pharma_programmes if q.id == programme_id), None)
    if p is None or p.company_id != company_id:
        raise PharmaRuleError(f"no programme {programme_id} of the company")
    return p


def _energy(state: GameState, actor_id: int, what: str, balance: Balance) -> GameState:
    return spend_energy(
        state, actor_id, f"pharma_{what}", balance, cost=balance.pharma.energy[what]
    )


def apply_pharma(
    state: GameState, action: PharmaAction, rng: RngFactory, balance: Balance, data: GameData
) -> Outcome:
    if not pd.enabled(data):
        raise PharmaRuleError("pharmaceuticals are not in this game")
    company_id = acting_company(state, action.actor_id)
    match action:
        case StartProgramme():
            if action.modality not in MODALITIES:
                raise PharmaRuleError(f"unknown modality {action.modality!r}")
            if action.indication not in {i.key for i in pd.file(data).indications}:
                raise PharmaRuleError(f"unknown indication {action.indication!r}")
            name = action.name.strip()[: pd.NAME_MAX] or "Programme"
            state = _energy(state, action.actor_id, "start", balance)
            state, logs = pipeline.start_programme(
                state,
                company_id,
                name,
                action.indication,
                action.modality,
                action.ai,
                rng,
                balance,
                data,
            )
            return Outcome(state, (), tuple(logs))
        case StartTrial():
            p = own(state, company_id, action.programme_id)
            if action.design not in DESIGNS:
                raise PharmaRuleError(f"unknown design {action.design!r}")
            stage: str
            if p.status == "failed":
                stage, redo = p.stage, True
            elif p.status == "ready" and (nxt := pipeline.next_trial(p)) is not None:
                stage, redo = nxt, False
            else:
                raise PharmaRuleError(f"{p.name} has no trial to start now")
            state = _energy(state, action.actor_id, "trial", balance)
            p2 = pipeline.begin_stage(state, p, stage, action.design, balance, data, redo=redo)
            return Outcome(pipeline.with_programme(state, p2))
        case StopProgramme():
            p = own(state, company_id, action.programme_id)
            if p.status in ("stopped", "marketed", "out"):
                raise PharmaRuleError(f"{p.name} cannot be stopped")
            state = _energy(state, action.actor_id, "stop", balance)
            p2 = replace(p, status="stopped", ended_turn=state.turn)
            return Outcome(pipeline.with_programme(state, p2))
        case FileDrug():
            p = own(state, company_id, action.programme_id)
            state = _energy(state, action.actor_id, "submit", balance)
            state, logs = approval.file(state, p, action.regulator, rng, balance, data)
            return Outcome(state, (), tuple(logs))
        case SetDrugPrice():
            p = own(state, company_id, action.programme_id)
            drug = next((d for d in state.pharma_drugs if d.programme_id == p.id), None)
            if drug is None:
                raise PharmaRuleError(f"{p.name} is not marketed")
            if action.list_cents <= 0 or not 0 <= action.support <= MAX_SUPPORT:
                raise PharmaRuleError("a price must be positive and support within 0-2")
            state = _energy(state, action.actor_id, "price", balance)
            new = replace(drug, list_cents=action.list_cents, support=action.support)
            state = replace(
                state,
                pharma_drugs=tuple(
                    new if d.programme_id == p.id else d for d in state.pharma_drugs
                ),
            )
            return Outcome(approval.reprice_hta(state, p, balance, data))
        case BuildPharmaPlant():
            state = _energy(state, action.actor_id, "plant", balance)
            state, entries, logs = supply.build(
                state, company_id, action.plant, action.region, balance, data
            )
            return Outcome(state, tuple(entries), tuple(logs))
        case SetPharmaPlantQuality():
            plant = next((q for q in state.pharma_plants if q.id == action.plant_id), None)
            if plant is None or plant.company_id != company_id:
                raise PharmaRuleError(f"no plant {action.plant_id} of the company")
            state = _energy(state, action.actor_id, "plant", balance)
            rows = tuple(
                replace(q, quality=action.level) if q.id == plant.id else q
                for q in state.pharma_plants
            )
            return Outcome(replace(state, pharma_plants=rows))
        case ChooseCmo():
            cmo = next((c for c in pd.file(data).cmos if c.name == action.cmo), None)
            if cmo is None or action.plant not in cmo.kinds:
                raise PharmaRuleError(f"{action.cmo} does not make {action.plant}")
            ended = tuple(
                replace(s, ended_turn=state.turn)
                if s.company_id == company_id and s.kind == action.plant and s.ended_turn is None
                else s
                for s in state.pharma_supply
            )
            sid = max((s.id for s in state.pharma_supply), default=0) + 1
            row = Supply(
                sid, company_id, cmo.name, action.plant, cmo.capacity[action.plant], state.turn
            )
            return Outcome(replace(state, pharma_supply=(*ended, row)))
        case LicenseAsset():
            state = _energy(state, action.actor_id, "deal", balance)
            state, entries, logs = licensing.take_asset(
                state,
                company_id,
                action.asset_id,
                action.acquire,
                balance,
                data,
                upfront_cents=action.upfront_cents,
            )
            return Outcome(state, tuple(entries), tuple(logs))
        case OutLicense():
            p = own(state, company_id, action.programme_id)
            state = _energy(state, action.actor_id, "deal", balance)
            state, entries, logs = licensing.out_license(
                state,
                p,
                action.rival_id,
                action.co_develop,
                balance,
                data,
                upfront_cents=action.upfront_cents,
            )
            return Outcome(state, tuple(entries), tuple(logs))
        case LicensePlatform():
            state = _energy(state, action.actor_id, "deal", balance)
            return Outcome(licensing.platform(state, company_id, action.rival_id, balance, data))
