"""Frozen organization models: units and hiring plans (docs/formulas.md section 13).

The company root is implicit: it has no row, `parent_id` and `unit_id` are None for it, its
leader is the founder, and its work-location policy lives on the company. GameState holds
live records only: active units and plans that are not closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type UnitKind = Literal["department", "team"]
type UnitStatus = Literal["active", "dissolved"]
type WorkPolicy = Literal["office", "remote"]
type PlanChannel = Literal["network", "job_post", "recruiter", "any"]
# active: the delegate works it; paused: its owner left; filled: target reached; closed.
type PlanStatus = Literal["active", "paused", "filled", "closed"]

UNIT_KINDS: tuple[UnitKind, ...] = ("department", "team")
WORK_POLICIES: tuple[WorkPolicy, ...] = ("office", "remote")
PLAN_CHANNELS: tuple[PlanChannel, ...] = ("job_post", "recruiter", "network", "any")


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
