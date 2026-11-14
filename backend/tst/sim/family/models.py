"""M36 state (docs/formulas.md 45): the founder's family and its members. Family members are
people (`GameState.people`): their skills, personality, potential and hidden traits live on
the Person and are hidden as for anyone (45.9). These records hold only public facts:
relations, closeness, education, mentoring, the relationship, and the dynasty's history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

PARTNER: Final = "partner"
CHILD: Final = "child"
EX_PARTNER: Final = "ex_partner"
RELATIONS: Final = (PARTNER, CHILD, EX_PARTNER)
FAMILY_ROLE: Final = "family"  # a family member's Person.role while outside any company
TRUST_HOLDER: Final = "Family trust"  # the trust's cap-table entry (holder_kind "group")
FOUNDATION_HOLDER: Final = "Foundation"  # shares given to the foundation (45.6)
ESTATE_BUYERS: Final = "Estate sale buyers"  # a private company's estate sale (45.6)


@dataclass(frozen=True, slots=True)
class FamilyMember:
    """One member of the player's family (45.1). `parent_ids`: a child's founder and partner.
    `closeness` (0-100) is a child's bond with the family head (45.2)."""

    person_id: int
    relation: str  # RELATIONS
    member_index: int  # stream family's key (founder_id, member_index)
    head_id: int  # the family head (founder) when the member joined the family
    joined_turn: int
    parent_ids: tuple[int, ...] = ()
    closeness: float = 0.0
    school: str | None = None  # config.SCHOOLS, chosen at 12
    university: str | None = None  # config.UNIVERSITIES, chosen at 18
    degree: str | None = None  # config.DEGREES
    mba: bool = False
    mba_turn: int | None = None  # the MBA's start: mba_skills grow faster for two years
    milestones: tuple[int, ...] = ()  # ages whose milestone has passed
    mentored: bool = False
    company_id: int | None = None  # the group company they joined (45.4)
    company_turn: int | None = None
    seats_held: tuple[str, ...] = ()  # executive seats held, for readiness (45.4)
    own_way: str | None = None  # "rival" or "founded" (45.4)
    left_turn: int | None = None  # an ex-partner's divorce month


@dataclass(frozen=True, slots=True)
class Generation:
    """One head of the family and their years (45.7)."""

    person_id: int
    from_turn: int
    to_turn: int | None = None
    legacy: int | None = None  # 32.6's score for their years, set when they hand over
    how: str | None = None  # "choice", "health", "board" (how they handed over)


@dataclass(frozen=True, slots=True)
class Opinion:
    """The adviser's view of one proposal or one-off (45.5)."""

    turn: int
    subject: str  # "proposal", "pitch", "one_off"
    subject_id: int
    title: str
    stance: str  # "support" or "oppose"
    text: str
    overruled: bool = False


@dataclass(frozen=True, slots=True)
class FamilyNote:
    """A family event for History (45.1-45.6)."""

    turn: int
    kind: str
    text: str


@dataclass(frozen=True, slots=True)
class Family:
    """The player's family (45.1-45.7). One per game, created by the Family setting. Its
    `id` is the first head's person id and never changes; `head_id` is the current head,
    the player's founder."""

    id: int
    setting: str  # config.SETTINGS, never "none" (no Family record then)
    head_id: int
    created_turn: int
    family_time: int = 0
    relationship: float = 0.0  # 0-100 with the head's partner (45.2)
    partner_since: int | None = None
    married: bool = False
    marriage_asked: bool = False
    low_months: int = 0  # consecutive months below family.divorce_below
    strain_turn: int | None = None  # the last strain event
    strain_until: int | None = None  # "more time": family time held at strain_time until
    next_index: int = 0  # member_index for the next member
    step_back_delays: int = 0
    step_back_open: bool = False  # a health event asks the head to step back
    succession_open: str | None = None  # "choice", "health" or "board" while the choice is open
    head_mode: str = "founder"  # "founder" or "family_head" (a professional CEO, 45.5)
    adviser_id: int | None = None
    adviser_seat_id: int | None = None
    opinions: tuple[Opinion, ...] = ()
    generations: tuple[Generation, ...] = ()
    lifetime_gifts_cents: int = 0  # taxable gifts made (45.6)
    gift_tax_cents: int = 0
    estate_tax_cents: int = 0
    trust_turn: int | None = None  # the trust's set-up month
    foundation_share_cents: int = 0  # shares given to the foundation, at value (45.6)
    control_losses: int = 0
    had_control: bool = True
    notes: tuple[FamilyNote, ...] = ()
