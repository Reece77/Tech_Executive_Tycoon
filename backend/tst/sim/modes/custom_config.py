"""The editor's schema (M52, ADR-0026, docs/formulas.md 66.1-66.2): a custom scenario is a
`scenarios.yaml` historical entry plus a closed `overrides` block, and `editor.*` in balance.yaml
holds the ranges every field is checked against. Model definitions only (no imports from the
rest of the sim beyond M15b's scenario schema), so `tst.sim.data_models` can import them.

Structure and types are checked here, by Pydantic, at parse; the ranges (which live in
balance.yaml) and the references to loaded data (categories, roles, incumbents, nodes) are
checked by `tst.sim.modes.custom.check`. Nothing here takes code or a path, and nothing names a
hidden value (a person's potential or traits, a deposit's true grade): ADR-0026 point 3."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.modes.config import GoalSpec, HistoricalScenario

FORMAT: Final = 1  # the custom-scenario file format
SLUG_PATTERN: Final = r"^[a-z0-9][a-z0-9_-]{0,47}$"
CUSTOM_PREFIX: Final = "custom/"  # a custom game's mode.scenario: never a scenarios.yaml key
NAME_MAX: Final = 80  # tunable-exempt: the company name column's width
TEXT_MAX: Final = 600  # tunable-exempt: a label or description's characters on screen

type Length = Literal["standard", "dynasty", "endless"]
type Eras = Literal["historical", "seeded"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Range(_Frozen):
    """A closed range from balance.yaml, written as [low, high]."""

    lo: float
    hi: float

    @model_validator(mode="before")
    @classmethod
    def _pair(cls, value: object) -> object:
        if isinstance(value, list | tuple) and len(value) == 2:  # tunable-exempt: a pair
            return {"lo": value[0], "hi": value[1]}
        return value

    @model_validator(mode="after")
    def _order(self) -> Range:
        if self.hi < self.lo:
            raise ValueError("a range's high end is below its low end")
        return self

    def holds(self, value: float) -> bool:
        return self.lo <= value <= self.hi

    def text(self) -> str:
        return f"{self.lo:g} to {self.hi:g}"


class EditorBalance(_Frozen):
    """`editor.*` (66.1): every editable field's range. A field outside its range is refused."""

    start_years: Range  # calendar years a custom start may begin in
    macro_from_year: int  # macro and commodity starts are editable from this year (history before)
    cash_dollars: Range
    debt_dollars: Range  # the summed principal of the starting loans
    staff_count: Range  # people in one staff line
    staff_total: Range  # people in all staff lines together
    products: Range  # products at the start
    quality: Range  # a product's quality, points
    features: Range  # a product's feature points
    brand: Range  # a product's brand, points
    customers: Range  # customers in one segment at the start
    price_dollars: Range  # a segment's monthly price
    research_lead: Range  # a research lead, points
    fabs: Range  # fabs running at the start
    founder_age: Range  # years
    child_age: Range  # years
    children: Range  # children in the family
    rival_cash_mult_range: Range  # x a rival's cash at the start
    rival_quality_range: Range  # + points on each of a rival's products' quality
    added_rivals: Range  # generic rivals added in one category
    market_mult_range: Range  # x a category's addressable market at the start
    growth_delta_range: Range  # + a category's annual growth, fraction a year
    confidence: Range  # consumer confidence at the start (index, 100 = 2010-2019)
    policy_rate_pct: Range  # the base rate at the start, % a year
    commodity_mult_range: Range  # x a commodity's price level at the start
    deadline_years: Range  # years from the start to a goal's deadline
    preview_seeds: tuple[int, ...] = Field(min_length=1)  # the difficulty estimate's seeds
    preview_months: int = Field(ge=1)  # months the estimate plays at most


# --- The overrides block (ADR-0026 point 2) ---------------------------------------------------


class CompanyOverride(_Frozen):
    """The player's company beyond the scenario fields (66.1): its name."""

    name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX)


class RivalOverride(_Frozen):
    """One incumbent (incumbents.yaml, by name): present or removed, its cash and its products'
    quality."""

    present: bool = True
    cash_mult: float = 1.0
    quality_delta: float = 0.0


class AddedRivals(_Frozen):
    """Generic rivals added in a category, drawn as entrants are (52.3)."""

    category: str
    count: int = Field(ge=1)


class MarketOverride(_Frozen):
    """A category's addressable market and annual growth."""

    market_mult: float = 1.0
    growth_delta: float = 0.0


class WorldOverride(_Frozen):
    """The macro start, eras and commodity price levels (66.1)."""

    confidence: float | None = None
    policy_rate_pct: float | None = None
    eras: Eras = "historical"
    commodities: dict[str, float] = Field(default_factory=dict)  # commodity key -> x its price


class RulesOverride(_Frozen):
    """M51's challenge rules (63.2). The campaign length is the entry's own `length`."""

    challenges: tuple[str, ...] = ()


class Overrides(_Frozen):
    company: CompanyOverride = CompanyOverride()
    rivals: dict[str, RivalOverride] = Field(default_factory=dict)
    added_rivals: tuple[AddedRivals, ...] = ()
    markets: dict[str, MarketOverride] = Field(default_factory=dict)
    world: WorldOverride = WorldOverride()
    rules: RulesOverride = RulesOverride()


class CustomScenario(HistoricalScenario):
    """A custom scenario file's body (ADR-0026 point 1): a historical entry, whose goal and
    deadline may both be left out (no goal: open play), plus `overrides`. `key` is the file's
    slug; `opened_from` names what the editor started from (shown only)."""

    key: str = Field(pattern=SLUG_PATTERN)
    label: str = Field(min_length=1, max_length=TEXT_MAX)
    description: str = Field(default="", max_length=TEXT_MAX)
    goal: GoalSpec | None = None  # type: ignore[assignment]
    deadline: tuple[int, int] | None = None  # type: ignore[assignment]
    # standard and dynasty end as M51's scenarios do (at the goal's verdict, else after
    # December 2069; dynasty is shown as a dynasty game); endless has no end (66.3)
    length: Length = "standard"  # type: ignore[assignment]
    opened_from: str | None = None
    overrides: Overrides = Overrides()
    format: int = FORMAT

    @model_validator(mode="after")
    def _text(self) -> CustomScenario:
        """Names and texts are printable (a brief may break lines): a control character would
        not survive the file's YAML unchanged."""
        texts = [("label", self.label), ("overrides.company.name", self.overrides.company.name)]
        for where, text in texts:
            if text is not None and not text.isprintable():
                raise ValueError(f"{where} may hold only printable characters")
        if not self.description.replace("\n", " ").isprintable():
            raise ValueError("description may hold only printable characters and line breaks")
        return self

    @model_validator(mode="after")
    def _goal(self) -> CustomScenario:
        if (self.goal is None) != (self.deadline is None):
            raise ValueError("a goal needs a deadline, and a deadline a goal")
        if self.format != FORMAT:
            raise ValueError(f"format must be {FORMAT}")
        return self
