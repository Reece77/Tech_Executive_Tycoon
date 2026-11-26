"""The editor and custom scenarios (M52, formulas.md 66.1-66.2, ADR-0026). A custom scenario
travels as `tst.sim.modes.custom_config.CustomScenario` itself (the file's fields): the editor
can set only what that schema has, and it has no hidden value (ADR-0026 point 3)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.scenarios import ScenarioResultOut


class RangeOut(BaseModel):
    lo: float
    hi: float


class OptionOut(BaseModel):
    key: str
    label: str


class RoleOptionOut(BaseModel):
    key: str
    label: str
    levels: list[str]


class CategoryOptionOut(BaseModel):
    key: str
    label: str
    segments: list[str]
    market_editable: bool = Field(description="False: its market follows its own data")


class IncumbentOptionOut(BaseModel):
    name: str
    categories: list[str]


class NodeOptionOut(BaseModel):
    key: str
    label: str
    first_year: int = Field(description="The year it first ran in volume anywhere")


class StartOptionOut(BaseModel):
    key: str = Field(description="A scenarios.yaml key, or blank_<year>")
    label: str
    year: int


class EditorOut(BaseModel):
    """Everything the Editor screen offers, from the loaded data and `editor.*`."""

    ranges: dict[str, RangeOut] = Field(description="Each editable field's range (editor.*)")
    macro_from_year: int
    starts: list[StartOptionOut]
    backgrounds: list[OptionOut]
    roles: list[RoleOptionOut]
    categories: list[CategoryOptionOut]
    incumbents: list[IncumbentOptionOut]
    domains: list[OptionOut]
    lenders: list[OptionOut]
    nodes: list[NodeOptionOut]
    regions: list[OptionOut]
    cities: list[OptionOut]
    commodities: list[OptionOut]
    challenges: list[OptionOut]
    goal_kinds: dict[str, list[str]] = Field(description="Each goal kind's required fields")
    lengths: list[str]


class CheckOut(BaseModel):
    """A spec's refusals (empty: valid) and its hash."""

    valid: bool
    reasons: list[str]
    sha256: str | None = Field(description="The canonical text's SHA-256 when valid")


class CustomCardOut(BaseModel):
    """A custom scenario on the Scenarios screen's Custom section (66.2)."""

    slug: str
    label: str
    description: str
    year: int
    goal: str | None
    deadline_label: str | None
    opened_from: str | None
    sha256: str
    played: int = Field(description="Custom games with a verdict (kept apart from M51's)")
    best: ScenarioResultOut | None


class ImportIn(BaseModel):
    text: str = Field(description="A custom scenario file's YAML")
    slug: str | None = Field(default=None, description="Save under this name; omit for its own")
    overwrite: bool = False


class ExportOut(BaseModel):
    filename: str
    text: str = Field(description="The canonical YAML (ADR-0026 point 7)")


class ProductLineOut(BaseModel):
    name: str
    category: str
    status: str
    quality: float
    customers: float


class RivalLineOut(BaseModel):
    name: str
    category: str
    quality: float
    customers: float
    added: bool


class PreviewOut(BaseModel):
    """The start month's summary (66.1): built in memory, no turn played, nothing saved."""

    label: str
    start_label: str
    cash_cents: int
    debt_cents: int
    staff: dict[str, int]
    products: list[ProductLineOut]
    research: dict[str, float]
    rivals: list[RivalLineOut]
    removed: list[str]
    goal: str | None
    deadline_label: str | None
    challenges: list[str]
    length: str


class SeedResultOut(BaseModel):
    seed: int
    result: str | None
    month_label: str
    score: int | None


class DifficultyOut(BaseModel):
    """The sensible script's estimate on `editor.preview_seeds`, run in the background."""

    job_id: str
    status: str = Field(description="running | done | failed")
    seeds: list[int]
    results: list[SeedResultOut]
    wins: int
    difficulty: str | None = Field(description="easy | medium | hard; None without a goal")
    error: str | None = None
