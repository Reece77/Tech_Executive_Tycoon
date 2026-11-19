"""Schema for M43's conglomerate view (`conglomerate.*` in balance.yaml): the industries a group
is reported in, and the words the capital-allocation panel uses. Model definitions only (no
imports from the rest of the sim), so `tst.sim.data_models` can import them without a cycle."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class IndustryDef(_Frozen):
    """One industry of the conglomerate view: the product categories, facility kinds (and
    power plants, `plants`), mines (`mines`) and revenue accounts whose lines it reports."""

    key: str
    label: str
    categories: tuple[str, ...] = ()
    facility_kinds: tuple[str, ...] = ()
    accounts: tuple[str, ...] = ()  # revenue accounts not tied to a product (foundry, energy)
    plants: bool = False  # power plants (46)
    mines: bool = False  # mines (35)


class RiskWord(_Frozen):
    below: float = Field(ge=0)  # the spread of yearly revenue growth below which `word` applies
    word: str


class ConglomerateBalance(_Frozen):
    industries: tuple[IndustryDef, ...]
    trend_years: int = Field(ge=1)  # years of trends shown
    risk_years: int = Field(ge=2)  # years of growth whose spread reads as risk
    risk_words: tuple[RiskWord, ...]
    risk_top_word: str  # a spread at or above the last `below`
    letter_from_year: int = Field(ge=2010)  # tunable-exempt: the game's first year

    @model_validator(mode="after")
    def _check(self) -> ConglomerateBalance:
        keys = [i.key for i in self.industries]
        if len(set(keys)) != len(keys):
            raise ValueError("conglomerate.industries keys must be unique")
        for field in ("categories", "facility_kinds", "accounts"):
            seen: list[str] = [x for i in self.industries for x in getattr(i, field)]
            dupes = sorted({x for x in seen if seen.count(x) > 1})
            if dupes:
                raise ValueError(f"conglomerate.industries: {field} in two industries: {dupes}")
        plants, mines = (
            sum(i.plants for i in self.industries),
            sum(i.mines for i in self.industries),
        )
        if plants != 1 or mines != 1:
            raise ValueError("conglomerate.industries: exactly one industry has plants and mines")
        belows = [w.below for w in self.risk_words]
        if belows != sorted(belows):
            raise ValueError("conglomerate.risk_words must rise")
        return self
