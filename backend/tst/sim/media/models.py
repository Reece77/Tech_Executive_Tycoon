"""Frozen media records (docs/formulas.md 65). GameState holds one `MediaState`: titles (series,
films and games, each a content asset), creative leads' profiles and the leads on offer, line
settings (an ad tier, ad load, a social network's format and moderation, consumer apps' ad
pricing), licences in, divest-or-ban laws, service months and the game-wide world rows (growth,
ad spend's growth, seeded format eras, console generations and strikes, and the ad market's
calibration at 2026), all hidden until they come. Persisted in `media_record` (migration
0070_m55), one row a record.

Hidden values (65.8, the brief's hidden-value test): a title's audience is drawn at release (stream
media (0, title id)) and never before; a lead's `ego` and `loyalty` live here only, never in the
API or a prompt (their effects do: morale, walks); seeded rows are engine-only until they arrive."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Title:
    """A series, film or game (65.2): a project with a budget (game cents, total), its creative
    lead and unit, and its kind's development months. Its cost is capitalised as spent
    (`book_cents`, 1560) and amortised from release on the kind's schedule; a cancelled or failed
    title is written off. `audience` (millions, real) is drawn at release only."""

    id: int
    company_id: int
    name: str
    kind: str  # series, film or game
    genre: str
    budget_cents: int
    greenlit_turn: int
    dev_months: int
    release_turn: int  # planned (a move or a strike shifts it)
    lead_person_id: int | None = None
    unit_id: int | None = None
    sequel_of: int | None = None
    platforms: tuple[str, ...] = ()  # games: pc, console, mobile
    monetisation: str = "premium"  # games: premium or free_to_play
    live_service: bool = False
    store: str = "default"  # games on pc: default or epic
    window: str = "licensed"  # series and films: own (the company's streaming line) or licensed
    service_product_id: int | None = None
    stage: str = "development"  # development, released, cancelled
    months_done: int = 0
    spent_cents: int = 0
    book_cents: int = 0  # capitalised less amortised and written off
    amortised_cents: int = 0
    written_off_cents: int = 0
    overrules: int = 0
    cuts: int = 0
    moves: int = 0
    events: int = 0  # overrules, cuts and moves: the n of a lead's reaction draw
    reach: float = 1.0  # x the audience: overrules' broader cuts
    morale_sum: float = 0.0  # the lead's morale summed over production months
    grievance: float = 0.0  # morale its lead lost to this title's overrules, cuts and moves
    released_turn: int | None = None
    quality: float | None = None  # the multiplier at release
    expected: float | None = None  # the audience expected at release (millions, real)
    audience: float | None = None  # drawn at release (millions, real)
    players: float = 0.0  # a game's current players (millions, real): free-to-play
    revenue_cents: int = 0  # booked
    attributed_cents: int = 0  # a share of its own service's revenue (shown; not booked)
    walked_turn: int | None = None  # its lead walked during it


@dataclass(frozen=True, slots=True)
class CreativeLead:
    """A creative lead's profile (65.6), keyed by person: `creative` and `vision` (1-20, shown as
    ranges until a title together is released), the hidden `ego` and `loyalty`, reputation from
    past titles, and the overall deal (`company_id` while signed)."""

    person_id: int
    creative: float
    vision: float
    ego: float  # hidden
    loyalty: float  # hidden
    reputation: float = 0.0
    creative_off: float = 0.0  # the shown range's centre is creative + this x its half-width
    vision_off: float = 0.0
    company_id: int | None = None
    deal_from: int | None = None
    deal_to: int | None = None
    fee_cents: int = 0  # a year
    titles: int = 0  # released titles with the current company
    walked_turn: int | None = None
    walked_to: int | None = None  # a rival company id


@dataclass(frozen=True, slots=True)
class LeadOffer:
    """A creative lead on offer (65.6): the n-th of `year`'s pool, regenerated from stream media
    (4, year, n) until signed (then `person_id`)."""

    year: int
    n: int
    turn: int
    status: str = "open"  # open, signed, expired
    person_id: int | None = None


@dataclass(frozen=True, slots=True)
class LineSetting:
    """A media line's settings (65.1, 65.3, 65.5)."""

    product_id: int
    ad_tier: bool = False  # streaming: an ad tier from media.yaml's ad_tier_from
    ad_load: float = 1.0  # social: x the default ad load
    format: str | None = None  # social: its format (media.yaml formats or a seeded era)
    format_turn: int | None = None  # when it moved to that format
    moderation: str = "standard"
    ad_pricing: bool = False  # consumer apps from 2026: revenue a user from the ad market


@dataclass(frozen=True, slots=True)
class Licence:
    """Titles licensed in by a video service (65.3): a fee a year for a term, worth catalogue value
    of the fee x streaming_service.licence_value x the year's availability."""

    id: int
    company_id: int
    product_id: int
    fee_cents: int  # a year
    from_turn: int
    to_turn: int


@dataclass(frozen=True, slots=True)
class DivestLaw:
    """A divest-or-ban law against a social line in a region (65.5): divest by the deadline or the
    line's users there go to zero."""

    id: int
    product_id: int
    region: str
    announced_turn: int
    deadline_turn: int
    status: str = "pending"  # pending, divested, banned


@dataclass(frozen=True, slots=True)
class ServiceMonth:
    """A player media line's month (shown; 65.8 target 3's cash): customers, revenue (with ads),
    content spent for it (its own titles' production and licences) and running costs, and the
    cumulative cash."""

    turn: int
    product_id: int
    customers: float
    revenue_cents: int
    ad_revenue_cents: int
    content_cents: int
    costs_cents: int
    cash_cents: int
    engagement: float = 0.0  # streaming: catalogue value over the median service's
    churn_mult: float = 1.0
    share: float = 0.0  # social: users over the region's internet users (largest region)
    advantage: bool = False  # social: on the newest format within its window


@dataclass(frozen=True, slots=True)
class AdMonth:
    """A region's ad market in a month (65.1, shown): spend and digital spend (game cents a month,
    x scale), impressions offered by the game's sellers (millions) and the price a thousand."""

    turn: int
    region: str
    spend_cents: int
    digital_cents: int
    impressions_m: float
    cpm_cents: float


@dataclass(frozen=True, slots=True)
class WorldDraw:
    """A seeded value (hidden until it applies): `kind` growth (key category, region), ad_growth,
    format (key: the era's key; value: its turn), generation, strike (value: months)."""

    kind: str
    year: int
    key: str
    value: float


@dataclass(frozen=True, slots=True)
class AdRef:
    """The ad market's calibration at media.start (65.1): a region's impressions and price a
    thousand in December 2025, so the price follows spend over impressions from then."""

    region: str
    impressions_m: float
    cpm_cents: float
    digital_cents: float


@dataclass(frozen=True, slots=True)
class RivalFormat:
    """A rival social line's format after 2025 (65.5): it moves to a new era after a delay."""

    product_id: int
    format: str
    since_turn: int


@dataclass(frozen=True, slots=True)
class RivalBonus:
    """A walked lead's next title at a rival (65.6): catalogue value its video lines gain."""

    company_id: int
    value_cents: int
    turn: int


@dataclass(frozen=True, slots=True)
class PaidBack:
    """A player media line's first month with cumulative cash at or above zero after a negative
    one (65.8 target 3)."""

    product_id: int
    turn: int


@dataclass(frozen=True, slots=True)
class MediaState:
    titles: tuple[Title, ...] = ()
    leads: tuple[CreativeLead, ...] = ()
    offers: tuple[LeadOffer, ...] = ()
    settings: tuple[LineSetting, ...] = ()
    licences: tuple[Licence, ...] = ()
    laws: tuple[DivestLaw, ...] = ()
    months: tuple[ServiceMonth, ...] = ()
    ad_months: tuple[AdMonth, ...] = ()
    draws: tuple[WorldDraw, ...] = ()
    ad_refs: tuple[AdRef, ...] = ()
    rival_formats: tuple[RivalFormat, ...] = ()
    rival_bonus: tuple[RivalBonus, ...] = ()
    paid_back: tuple[PaidBack, ...] = ()

    def title(self, title_id: int) -> Title | None:
        return next((t for t in self.titles if t.id == title_id), None)

    def lead(self, person_id: int) -> CreativeLead | None:
        return next((x for x in self.leads if x.person_id == person_id), None)

    def setting(self, product_id: int) -> LineSetting | None:
        return next((s for s in self.settings if s.product_id == product_id), None)

    def draw(self, kind: str, year: int, key: str = "") -> float | None:
        # M60: an index of the draws, built once per tuple (the first match, as a scan finds)
        from tst.sim.state import from_inputs

        def index() -> dict[tuple[str, int, str], float]:
            out: dict[tuple[str, int, str], float] = {}
            for d in self.draws:
                out.setdefault((d.kind, d.year, d.key), d.value)
            return out

        return from_inputs(self.draws, "media_draws", index).get((kind, year, key))

    def next_title_id(self) -> int:
        return max((t.id for t in self.titles), default=0) + 1

    def next_licence_id(self) -> int:
        return max((x.id for x in self.licences), default=0) + 1

    def next_law_id(self) -> int:
        return max((x.id for x in self.laws), default=0) + 1

    def last_month(self, product_id: int) -> ServiceMonth | None:
        rows = [m for m in self.months if m.product_id == product_id]
        return rows[-1] if rows else None
