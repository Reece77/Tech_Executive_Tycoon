"""Frozen organization models: units and hiring plans (docs/formulas.md section 13).

The company root is implicit: it has no row, `parent_id` and `unit_id` are None for it, its
leader is the founder, and its work-location policy lives on the company. GameState holds
live records only: active units and plans that are not closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type UnitKind = Literal["division", "department", "team"]  # division: M8 (18.1)
type SharedServices = Literal["central", "embedded"]  # a division's shared services (18.4)
type UnitStatus = Literal["active", "dissolved"]
type WorkPolicy = Literal["office", "remote"]
type PlanChannel = Literal["network", "job_post", "recruiter", "any"]
type PlanFocus = Literal["current", "potential"]  # 13.10: best now, or spot potential (M2b)
# active: the delegate works it; paused: its owner left; filled: target reached; closed.
type PlanStatus = Literal["active", "paused", "filled", "closed"]

UNIT_KINDS: tuple[UnitKind, ...] = ("division", "department", "team")
SHARED_SERVICES: tuple[SharedServices, ...] = ("central", "embedded")
SEATS: tuple[str, ...] = ("coo", "cfo", "cto", "cpo", "cmo", "cro")  # 18.3, display order
WORK_POLICIES: tuple[WorkPolicy, ...] = ("office", "remote")
PLAN_CHANNELS: tuple[PlanChannel, ...] = ("job_post", "recruiter", "network", "any")
PLAN_FOCUSES: tuple[PlanFocus, ...] = ("current", "potential")
POTENTIAL_LEVELS = ("junior", "mid")  # focus potential considers only these (13.10)


@dataclass(frozen=True, slots=True)
class OrgUnit:
    id: int
    company_id: int
    kind: UnitKind
    name: str
    parent_id: int | None  # None = the company root
    leader_id: int | None  # a member of this unit, or None
    policy: WorkPolicy | None  # None = use the parent's policy
    created_turn: int
    status: UnitStatus = "active"
    dissolved_turn: int | None = None
    product_id: int | None = None  # the product its members work on (formulas.md 11.3, M3)
    services: SharedServices | None = None  # a division's shared services; None = central (18.4)
    office_id: int | None = None  # its home office; None = the parent's, up to the HQ (M9, 19.2)

    @property
    def embedded(self) -> bool:
        return self.kind == "division" and self.services == "embedded"


@dataclass(frozen=True, slots=True)
class ExecSeat:
    """An executive seat that has been filled at least once (18.3). person_id None: vacant."""

    company_id: int
    seat: str  # one of SEATS
    person_id: int | None
    since_turn: int


@dataclass(frozen=True, slots=True)
class PlanActivity:
    """What a plan's delegate did in one turn (for the plan list and the inbox summary)."""

    turn: int
    searches: int = 0
    interviews: int = 0
    scouted: int = 0
    offers: int = 0

    @property
    def acted(self) -> bool:
        return bool(self.searches or self.interviews or self.scouted or self.offers)


@dataclass(frozen=True, slots=True)
class HiringPlan:
    id: int
    company_id: int
    owner_id: int  # the delegate: a staff member other than the founder
    unit_id: int | None  # where hires join; None = the company root
    role: str
    target: int  # hires wanted in total
    channel: PlanChannel
    ratio_bp: int  # offered salary as bp of the candidate's ask
    equity_bp: int  # equity per offer
    created_turn: int
    status: PlanStatus = "active"
    hired: int = 0  # accepted offers made under this plan
    closed_turn: int | None = None
    last_activity: PlanActivity | None = None
    focus: PlanFocus = "current"


# --- Executives with authority (formulas.md 24, M10c) -----------------------------------------

type GuardValue = int | float | tuple[int, ...] | tuple[str, ...]
type ProposalKind = Literal["round", "loan", "lease"]
type ProposalStatus = Literal["pending", "approved", "declined", "lapsed"]


@dataclass(frozen=True, slots=True)
class Authority:
    """A seat's authority (24.1): on or off, with the guardrails the player set. The CRO's
    price anchors are the prices when authority was given: it moves a sales-led price only
    within its band of these."""

    company_id: int
    seat: str
    enabled: bool
    guardrails: tuple[tuple[str, GuardValue], ...]
    since_turn: int
    price_anchors: tuple[tuple[int, str, int], ...] = ()  # (product id, segment, cents)

    def guard(self, key: str) -> GuardValue:
        return dict(self.guardrails)[key]

    def number(self, key: str) -> float:
        value = self.guard(key)
        assert not isinstance(value, tuple)
        return float(value)


@dataclass(frozen=True, slots=True)
class ExecDecision:
    """One thing an executive with authority did, or got wrong (24.1, 24.2)."""

    id: int
    company_id: int
    seat: str
    person_id: int
    turn: int
    text: str
    mistake: bool = False


@dataclass(frozen=True, slots=True)
class Proposal:
    """A CFO or COO proposal waiting for the player's Approve or Decline (24.1)."""

    id: int
    company_id: int
    seat: str
    person_id: int
    turn: int
    kind: ProposalKind
    params: tuple[tuple[str, int | str], ...]
    text: str
    status: ProposalStatus = "pending"
    resolved_turn: int | None = None

    def param(self, key: str) -> int | str:
        return dict(self.params)[key]
