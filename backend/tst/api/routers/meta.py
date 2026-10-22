from __future__ import annotations

from fastapi import APIRouter

from tst.api.deps import DataDep
from tst.api.schemas.meta import ScenarioOut
from tst.sim.data_models import DEFAULT_DIFFICULTY
from tst.sim.setup import starting_cash_cents

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/scenarios", response_model=list[ScenarioOut], operation_id="listScenarios")
def list_scenarios(data: DataDep) -> list[ScenarioOut]:
    return [
        ScenarioOut(
            id=s.id,
            name=s.name,
            description=s.description,
            available_in=s.available_in,
            selectable=s.selectable,
            starting_cash_cents=starting_cash_cents(data.balance, s.id, DEFAULT_DIFFICULTY),
        )
        for s in data.game_data.scenarios
    ]
