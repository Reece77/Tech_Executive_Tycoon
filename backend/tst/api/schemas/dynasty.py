"""The dynasty score and its family tree (M36, formulas.md 45.7); its own module so the
History schemas can embed it without importing the people schemas."""

from __future__ import annotations

from pydantic import BaseModel


class GenerationOut(BaseModel):
    person_id: int
    name: str
    from_label: str
    to_label: str | None
    legacy: int
    how: str | None


class DynastyOut(BaseModel):
    generations: list[GenerationOut]
    legacies: int
    family_value_cents: int
    value_points: float
    control_losses: int
    loss_points: float
    total: int
