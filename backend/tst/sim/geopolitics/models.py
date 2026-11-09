"""M22 records (docs/formulas.md 39): seeded tension and rules, licences, compliant variants,
the entity list, where companies and facilities sit, blocked customers leaving, and notices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type ShockKind = Literal["none", "escalation", "detente"]
type LicenceStatus = Literal["pending", "approved", "denied", "expired", "grey"]
type SiteKind = Literal["company", "facility"]


@dataclass(frozen=True, slots=True)
class TensionMonth:
    """A seeded month of US-China tension after 2025 (39.1); history months are data."""

    turn: int
    value: float
    shock: ShockKind = "none"


@dataclass(frozen=True, slots=True)
class SeededRule:
    """A rule an escalation added after 2025 (39.2): export_controls.yaml `seeded` key."""

    rule_key: str
    start_turn: int
    end_turn: int | None = None


@dataclass(frozen=True, slots=True)
class Suspension:
    """A seeded détente's suspension of a rule (39.2): it does not apply from `start_turn` to
    `end_turn` inclusive."""

    rule_key: str
    start_turn: int
    end_turn: int


@dataclass(frozen=True, slots=True)
class Licence:
    """A licence request for a product's sales to a country under a rule (39.3). `grey`:
    the company sells unlicensed through distributors (listing risk), no request."""

    id: int
    company_id: int
    product_id: int
    rule_key: str
    country: str
    requested_turn: int
    decide_turn: int
    status: LicenceStatus = "pending"
    until_turn: int | None = None  # an approved licence's last month


@dataclass(frozen=True, slots=True)
class Variant:
    """A compliant variant of a chip product (39.3), launched at `turn`."""

    product_id: int
    turn: int


@dataclass(frozen=True, slots=True)
class EntityListing:
    """A company on an actor's entity list (39.3) from `turn`."""

    company_id: int
    actor: str  # the listing actor (a country or bloc)
    turn: int
    reason: str


@dataclass(frozen=True, slots=True)
class Site:
    """Where a company (a subsidiary) or a facility sits when not its city's or region's
    default country (39.1); `local_partner`: a company's local partnership (39.3)."""

    kind: SiteKind
    id: int
    country: str
    local_partner: bool = False


@dataclass(frozen=True, slots=True)
class Exit:
    """A product's customers in a blocked destination still on its books (M22 decision):
    `remaining` of a segment's customers in `region` leave at geopolitics.exit_rate a month."""

    product_id: int
    region: str
    segment: str
    remaining: float
    share: float  # the blocked share of the region's demand last month


@dataclass(frozen=True, slots=True)
class Notice:
    """A geopolitical notice queued for a company: what an event's {rule} placeholder names."""

    turn: int  # the month the event is shown
    company_id: int
    template_id: str
    rule_key: str
