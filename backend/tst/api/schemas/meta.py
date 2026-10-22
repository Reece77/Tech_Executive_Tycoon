from __future__ import annotations

from pydantic import BaseModel


class ScenarioOut(BaseModel):
    id: str
    name: str
    description: str
    available_in: str
    selectable: bool
    starting_cash_cents: int  # at standard difficulty
