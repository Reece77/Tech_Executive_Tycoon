"""backend/data/achievements.yaml (M25), validated at startup by the loader."""

from __future__ import annotations

import dataclasses
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.profile.kinds import Facts

ACHIEVEMENTS_FILE: Final = "achievements.yaml"

NUMBER_KINDS: Final = frozenset(
    f.name for f in dataclasses.fields(Facts) if f.type in ("int", "float")
)
FLAG_KINDS: Final = frozenset(f.name for f in dataclasses.fields(Facts) if f.type == "bool")
SET_KINDS: Final = frozenset(
    f.name for f in dataclasses.fields(Facts) if str(f.type).startswith("frozenset")
)


class AchievementDef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=40)
    title: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=200)
    kind: str
    threshold: float | None = None
    param: str | None = None
    hidden: bool = False

    @model_validator(mode="after")
    def _check(self) -> AchievementDef:
        if self.kind in NUMBER_KINDS:
            if self.threshold is None or self.param is not None:
                raise ValueError(f"{self.key}: kind {self.kind} takes a threshold and no param")
        elif self.kind in SET_KINDS:
            if self.param is None or self.threshold is not None:
                raise ValueError(f"{self.key}: kind {self.kind} takes a param and no threshold")
        elif self.kind in FLAG_KINDS:
            if self.param is not None or self.threshold is not None:
                raise ValueError(f"{self.key}: kind {self.kind} takes no threshold or param")
        else:
            known = sorted(NUMBER_KINDS | FLAG_KINDS | SET_KINDS)
            raise ValueError(f"{self.key}: unknown kind {self.kind!r}; kinds are {known}")
        return self


class AchievementsFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    achievements: tuple[AchievementDef, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> AchievementsFile:
        keys = [a.key for a in self.achievements]
        if dupes := sorted({k for k in keys if keys.count(k) > 1}):
            raise ValueError(f"duplicate achievement keys {dupes}")
        return self


def earned(a: AchievementDef, facts: Facts) -> bool:
    """Whether the facts meet the achievement's condition."""
    value = getattr(facts, a.kind)
    if a.kind in SET_KINDS:
        return a.param in value
    if a.kind in FLAG_KINDS:
        return bool(value)
    assert a.threshold is not None
    return float(value) >= a.threshold
