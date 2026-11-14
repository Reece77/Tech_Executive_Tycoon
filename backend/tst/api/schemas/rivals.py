"""Rivals, market news and approaches (M5, docs/formulas.md 15.5-15.6).

Never carries a rival's utilities, needs, noise, cash in cents, its key people's true values
or an approach's acceptance probability: money is a label, approaches a band (ADR-0007).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.modes import ScoreOut
from tst.api.schemas.people import AttributeOut
from tst.api.schemas.world import WorldCompanyOut


class RivalRowOut(BaseModel):
    score: int | None = Field(default=None, description="The company score (M15b, 30.1)")
    company_id: int
    name: str
    is_startup: bool
    personality: str = Field(description="aggressive | fast_follower | premium | cost_leader")
    personality_label: str
    competes_in: list[str] = Field(description="Segments shared with the player, as labels")
    staff_estimate: int = Field(description="Rounded to the nearest 10 above 100")
    money_label: str | None = Field(
        description="deep pockets | comfortable | tight; null for startups"
    )
    stance: str = Field(description="responding | watching | not competing")
    last_move: str | None
    last_move_date_label: str | None
    failed: bool


class RivalsOut(BaseModel):
    established: int
    startups_alive: int
    startups_failed: int
    rivals: list[RivalRowOut]


class RivalSegmentOut(BaseModel):
    product_id: int
    product_name: str
    category_label: str
    segment: str
    segment_label: str
    quality: float
    feature_score: float
    brand: float
    price_cents: int | None
    customers: float
    shared_with_player: bool
    running: str | None = Field(description="A push or cost cut running now, in words")
    running_until_label: str | None


class RivalProductMarketOut(BaseModel):
    """Where one rival product sells (Reece's playtest 3): its category, segments and
    regions, in words."""

    product_id: int
    name: str
    category_label: str
    segment_labels: list[str]
    region_labels: list[str]


class KeyPersonOut(BaseModel):
    person_id: int
    name: str
    role: str
    role_label: str
    level: str
    top_skills: list[AttributeOut] = Field(description="The player's ranges, strongest first")
    potential_phrase: str


class RivalMoveOut(BaseModel):
    turn: int
    date_label: str
    tag: str = Field(
        description="Price, Push, Enter, Cut, Approach, Launch, Funding, Founded, Failed"
    )
    detail: str
    approach: bool = Field(description="An approach to one of the player's people")


class RivalProfileOut(BaseModel):
    score: ScoreOut | None = Field(default=None, description="The company score (M15b, 30.1)")
    company_id: int
    name: str
    is_startup: bool
    personality: str
    personality_label: str
    style_text: str
    founded_label: str
    staff_estimate: int
    staff_in_your_markets: int = Field(description="Estimated staff on products you compete with")
    revenue_in_your_markets_cents: int = Field(description="Public prices x customers")
    money_label: str | None
    stance: str
    stance_reason: str
    failed: bool
    segments: list[RivalSegmentOut]
    products: list[RivalProductMarketOut] = Field(
        description="Each product's market: category, segments and regions"
    )
    key_people: list[KeyPersonOut]
    recent_moves: list[RivalMoveOut]
    poach_energy: int
    world: WorldCompanyOut | None = Field(
        default=None,
        description="M28 (41.7): owner and group, executives, facilities, financials, deals",
    )


class NewsMonthOut(BaseModel):
    turn: int
    date_label: str
    moves: list[RivalMoveOut]


class NewsOut(BaseModel):
    headlines: list[str] = Field(
        default_factory=list, description="This month's headlines, by AI or a template (M6)"
    )
    months: list[NewsMonthOut]


class ApproachOut(BaseModel):
    approach_id: int
    person_id: int
    name: str
    role_label: str
    rival_id: int
    rival_name: str
    offer_cents: int
    salary_cents: int
    unvested_options: int
    band: str = Field(description="likely to stay | might go | likely to go")
    made_date_label: str
    answer_date_label: str


class CounterIn(BaseModel):
    salary_cents: int = Field(gt=0)


class CounterPreviewOut(BaseModel):
    band_now: str
    band_after: str
