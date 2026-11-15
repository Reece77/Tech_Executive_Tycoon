"""Frozen platform records (docs/formulas.md 44, ADR-0021).

GameState holds every platform (historical ones from platforms.yaml, and those founded in
play), each platform's per-region state, device lines' platforms, listings (gatekeeping),
open-sourced products and standards contests. Persisted in `platform_record` (migration 0051).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type ListingStatus = Literal["listed", "removed", "appealing", "regulators"]
type ReviewAction = Literal["rejected_update", "fee_dispute", "removal"]


@dataclass(frozen=True, slots=True)
class Platform:
    """A platform (44.1): owned by one company (or an owner outside the game)."""

    id: int  # historical: its platforms.yaml position; founded in play: from next_ids
    key: str  # platforms.yaml key, or "own_<id>"
    name: str
    store: str
    kind: Literal["device", "developer"]
    owner_id: int | None  # a company id; None = an owner outside the game
    owner_label: str
    regions: tuple[str, ...]
    launched_turn: int
    ended_turn: int | None = None
    historical: bool = True
    product_id: int | None = None  # the OS or developer product it is built on (founded in play)
    licensable: bool = False
    licence_cents: int | None = (
        None  # an own OS's licence a unit for other OEMs; None = not offered
    )
    side_loading: bool = False
    fee: float | None = None  # the owner's standard fee after the history; None = the data's
    strictness: Literal["lenient", "standard", "strict"] = "standard"
    self_pref: Literal["off", "mild", "strong"] = "off"
    anti_steering: bool = True  # forbids links to pay outside, where the law lets it
    tools: float = 1.0  # T_p (44.2)
    open_turn: int | None = None  # its base was open-sourced (44.6)
    # M34 (48.2, ADR-0021 3): rule and fee rows regulators' duties add, as (region, part or "",
    # kind, from turn, rate): kind alt_payments adds a regulated path at `rate`; side_loading and
    # anti_steering_banned count as dated rules (`rule_active`). Data rows for the same part win.
    regulated: tuple[tuple[str, str, str, int, float], ...] = ()


@dataclass(frozen=True, slots=True)
class PlatformRegion:
    """A platform's month in one region (ADR-0021 2): shares are of the region's users and of its
    developers' attention."""

    platform_id: int
    region: str
    users: float  # share of the region's device users (developer platforms: of their category)
    dev_share: float  # share of developer attention
    catalogue: float  # C_p: accumulated developer months, decaying
    goodwill: float = 1.0  # G_p
    rest: float = 0.0  # its share of the rest of the market (devices not modelled in the game)


@dataclass(frozen=True, slots=True)
class DeviceRun:
    """The platform a device line runs (44.1). Switching is a one-off: devices already sold keep
    the old platform (`previous_share` of the line's customers), replaced at the market's pace."""

    product_id: int
    platform_id: int
    since_turn: int
    previous_id: int | None = None
    previous_share: float = 0.0


@dataclass(frozen=True, slots=True)
class PlatformListing:
    """A product's standing on a platform in a region it sells in (ADR-0021 5). Only products
    something has happened to have a row; no row = listed."""

    product_id: int
    platform_id: int
    region: str
    status: ListingStatus
    since_turn: int
    until_turn: int | None = None  # an appeal's or a regulator's answer month
    lost: float = 0.0  # customers lost while removed (won back after relisting)
    winback_until: int | None = None  # relisted: winning `lost` back until this month
    event_id: int | None = None  # the critical event answering it


@dataclass(frozen=True, slots=True)
class Review:
    """A gatekeeper's action on a product (44.5): kept a year for the API and the player's notes.
    The draw and the chance behind it are never stored."""

    turn: int
    product_id: int
    platform_id: int
    action: ReviewAction


@dataclass(frozen=True, slots=True)
class OpenSource:
    """An open-sourced product (44.6)."""

    product_id: int
    turn: int
    base_customers: float  # customers when opened (the adoption curve's start)
    closed_turn: int | None = None


@dataclass(frozen=True, slots=True)
class Standard:
    """A standards contest (44.7). `adoption` is the share of new products on the first format."""

    id: int
    key: str
    category: str
    label: str
    formats: tuple[str, str]
    sponsors: tuple[int | None, int | None]  # each format's sponsoring platform id, if any
    adoption: float  # share of new products on formats[0]
    started_turn: int
    winner: str | None = None
    tipped_turn: int | None = None
    historical: bool = False


@dataclass(frozen=True, slots=True)
class ProductStandard:
    """The format a product uses in a contest; `adopting_until` while it switches."""

    product_id: int
    standard_id: int
    format: str
    adopting_until: int | None = None


@dataclass(frozen=True, slots=True)
class RivalStore:
    """An alternative store on a platform in a region that allows one (44.8): it takes
    `platforms.alternative_share` of the side-loading share's sales at its own rate."""

    platform_id: int
    region: str
    name: str
    rate: float
    opened_turn: int
