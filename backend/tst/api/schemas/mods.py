"""The data editor (M25 section 3): editable files with their form specs and comments, and
named mods as overlays of changed values."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EditorFileRefOut(BaseModel):
    file: str
    label: str


class EditorFileOut(BaseModel):
    file: str
    label: str
    spec: dict[str, Any] = Field(description="Form spec from the loader's Pydantic schema")
    base: Any = Field(description="The base file's values")
    value: Any = Field(description="The values with the chosen mod merged in")
    comments: dict[str, str] = Field(description="Each field's YAML comment: unit and intent")


class ModChangeOut(BaseModel):
    file: str
    path: list[str] = Field(description="Keys, and @field=value for a list item")
    value: Any


class ModOut(BaseModel):
    name: str
    description: str
    files: list[str]
    changes: list[ModChangeOut]


class ModChangeIn(BaseModel):
    file: str
    path: list[str]
    value: Any


class ModIn(BaseModel):
    description: str = ""
    changes: list[ModChangeIn]
