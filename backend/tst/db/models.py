"""SQLAlchemy ORM models for a save file. Column reference: docs/data-dictionary.md.

History tables (ledger_entry, ledger_line, turn_snapshot, decision_log, turn_log) are
append-only (ADR-0004 section 6). Schema changes need an Alembic migration.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Bumped by any migration that changes the schema; stored in save_meta.schema_version.
SCHEMA_VERSION = 49  # M25: 0040; M17: 0041; M18: 0042; M19: 0043; M26: 0044; M20: 0045; M21: 0046
# M22: 0047; M23a: 0048; M28: 0049


class Base(DeclarativeBase):
    pass


class SaveMetaRow(Base):
    __tablename__ = "save_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # always 1
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    master_seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False)
    created_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    current_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    data_hashes: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    # M25 (section 3): the data-editor mod a game started with; all NULL without one. Deferred,
    # as display_name is: older migrations read save_meta through the current models.
    mod_name: Mapped[str | None] = mapped_column(String(64), nullable=True, deferred=True)
    mod_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, deferred=True)
    mod_overlay: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, deferred=True)
    next_person_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_search_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_offer_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_employment_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_unit_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_plan_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_product_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    # M4 (ADR-0018): how the game stands, and the finance id counters
    game_state: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    ended_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_cap_entry_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_grant_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_safe_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_round_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_term_sheet_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_seat_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_rival_effect_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_rival_move_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_approach_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    # M7b: the Saves screen's name for the save; null shows the slug. Deferred: migration 0013
    # reads save_meta through these models, before 0017 adds the column.
    display_name: Mapped[str | None] = mapped_column(String(80), nullable=True, deferred=True)
    next_rival_person_id: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1000001"
    )
    next_rival_employment_id: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1000001"
    )


class CompanyRow(Base):
    __tablename__ = "company"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_player: Mapped[bool] = mapped_column(Boolean, nullable=False)
    stage: Mapped[int] = mapped_column(Integer, nullable=False)
    founded_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    mission: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default="[]")
    work_policy: Mapped[str] = mapped_column(String(16), nullable=False, server_default="office")
    root_product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # product (no FK)
    arr_milestone_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    mrr_history: Mapped[list[int]] = mapped_column(JSON, nullable=False, server_default="[]")
    insolvent_months: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    stage_history: Mapped[list[list[int]]] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    # Rivals (M5, migration 0013_rivals; formulas.md 15)
    personality: Mapped[str | None] = mapped_column(String(16), nullable=True)
    builder_skill: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_margin_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_startup: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    failed_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_raise_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AccountRow(Base):
    __tablename__ = "account"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)


class LedgerEntryRow(Base):
    __tablename__ = "ledger_entry"
    __table_args__ = (Index("ix_ledger_entry_company_turn", "company_id", "turn"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    memo: Mapped[str] = mapped_column(String(200), nullable=False)

    lines: Mapped[list[LedgerLineRow]] = relationship(
        back_populates="entry", order_by="LedgerLineRow.id", cascade="all"
    )


class LedgerLineRow(Base):
    __tablename__ = "ledger_line"
    __table_args__ = (Index("ix_ledger_line_entry", "entry_id"),)
    __mapper_args__ = {"eager_defaults": False}  # noqa: RUF012 -- no RETURNING (M8)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("ledger_entry.id"), nullable=False)
    account_code: Mapped[str] = mapped_column(ForeignKey("account.code"), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # M8 (0020): the division a line reports to; null = corporate. Deferred: migration 0013
    # posts ledger lines through these models on saves that do not have the column yet.
    # The server default keeps the column out of an ORM INSERT that does not set it.
    division_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, deferred=True, server_default=text("NULL")
    )

    entry: Mapped[LedgerEntryRow] = relationship(back_populates="lines")


class TurnSnapshotRow(Base):
    __tablename__ = "turn_snapshot"
    __table_args__ = (Index("ux_turn_snapshot_turn_company", "turn", "company_id", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    kpis: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class DecisionLogRow(Base):
    __tablename__ = "decision_log"
    __table_args__ = (Index("ix_decision_log_turn", "turn"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    seq: Mapped[int | None] = mapped_column(Integer, nullable=True)  # action order in a turn
    source: Mapped[str] = mapped_column(String(16), nullable=False, server_default="player")
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # person id (no FK, 0005)


class TurnLogRow(Base):
    __tablename__ = "turn_log"
    __table_args__ = (Index("ix_turn_log_turn", "turn"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("company.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)


# --- People (M1a, migration 0002_people) ----------------------------------------------------
# Current-state tables, updated in place each turn. True values are never sent to the API.


class PersonRow(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(40), nullable=False)
    last_name: Mapped[str] = mapped_column(String(40), nullable=False)
    region: Mapped[str] = mapped_column(String(32), nullable=False)
    birth_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    work_style: Mapped[str] = mapped_column(String(16), nullable=False)
    salary_expectation_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_founder: Mapped[bool] = mapped_column(Boolean, nullable=False)


class PersonSkillRow(Base):
    __tablename__ = "person_skill"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    skill: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)


class PersonPersonalityRow(Base):
    __tablename__ = "person_personality"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    trait: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)


class PersonHiddenRow(Base):
    __tablename__ = "person_hidden"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    trait: Mapped[str] = mapped_column(String(64), primary_key=True)  # incl. potential_ability
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)


class PersonInterestRow(Base):
    __tablename__ = "person_interest"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    interest: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class PersonTagRow(Base):
    __tablename__ = "person_tag"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    tag: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class PersonTagRevealRow(Base):
    __tablename__ = "person_tag_reveal"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    observer_company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    tag: Mapped[str] = mapped_column(String(64), primary_key=True)
    revealed_turn: Mapped[int] = mapped_column(Integer, nullable=False)


class PersonRevealRow(Base):
    __tablename__ = "person_reveal"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    observer_company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    attribute: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    hw: Mapped[float] = mapped_column(Float, nullable=False)
    center_offset: Mapped[float] = mapped_column(Float, nullable=False)
    last_updated_turn: Mapped[int] = mapped_column(Integer, nullable=False)


class PersonProfileRevealRow(Base):
    __tablename__ = "person_profile_reveal"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    observer_company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    revealed_turn: Mapped[int] = mapped_column(Integer, nullable=False)


class PersonStateRow(Base):
    __tablename__ = "person_state"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    energy: Mapped[float | None] = mapped_column(Float, nullable=True)
    stress: Mapped[float | None] = mapped_column(Float, nullable=True)
    morale: Mapped[float | None] = mapped_column(Float, nullable=True)


class EmploymentRow(Base):
    __tablename__ = "employment"
    __table_args__ = (Index("ix_employment_company_status", "company_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    salary_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    equity_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    start_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    end_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    end_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)
    unit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # org_unit id (no FK, 0005)
    last_raise_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)


class RelationshipRow(Base):
    """A tracked pair in the player's company (16.7), person_id < other_person_id. Rebuilt
    with these columns by migration 0015_relationships (M6); the M1a table was never used."""

    __tablename__ = "relationship"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    other_person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)  # true value, -100..100
    start_value: Mapped[float] = mapped_column(Float, nullable=False)  # drift target
    since_turn: Mapped[int] = mapped_column(Integer, nullable=False)


# --- Hiring (M1b, migration 0003_hiring) -----------------------------------------------------


class SearchRow(Base):
    __tablename__ = "search"
    __table_args__ = (Index("ix_search_company_status", "company_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False)
    opened_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    closed_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # hiring_plan id (0006)
    rival_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # poach search (0013)


class CandidateRow(Base):
    __tablename__ = "candidate"
    __table_args__ = (Index("ix_candidate_company_status", "company_id", "status"),)

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    search_id: Mapped[int] = mapped_column(ForeignKey("search.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    created_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    resolved_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interviewed_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)


class OfferRow(Base):
    __tablename__ = "offer"
    __table_args__ = (Index("ix_offer_company_status", "company_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False)
    salary_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    equity_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    made_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    resolved_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # hiring_plan id (no FK)
    unit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # org_unit id (no FK)


class PersonMoraleLogRow(Base):
    """Month-end morale per employee, append-only (for the profile's 12-turn history)."""

    __tablename__ = "person_morale_log"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, primary_key=True)
    morale: Mapped[float] = mapped_column(Float, nullable=False)


class PersonRatingLogRow(Base):
    """Month-end shown rating per player employee, append-only (M7b, 0018): the mean
    midpoint of the displayed ranges of the role's primary skills. History's best hires and
    notable departures read it; it holds only what the player could see (ADR-0007)."""

    __tablename__ = "person_rating_log"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, primary_key=True)
    rating: Mapped[float] = mapped_column(Float, nullable=False)


# --- Inbox (M1b, migration 0004_inbox) -------------------------------------------------------


class InboxItemRow(Base):
    """A rendered message for the player company. Text is fixed when written (ADR-0004)."""

    __tablename__ = "inbox_item"
    __table_args__ = (Index("ix_inbox_item_company_read", "company_id", "read"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    template: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    link_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    # Hidden from the inbox unless asked for (M4c, migration 0012); a UI flag, no game effect.
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    # Kept in the inbox: never auto-archived (M10b, migration 0024); a UI flag.
    bookmarked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")


# --- Organization (M2a, migration 0005_org) --------------------------------------------------


class OrgUnitRow(Base):
    """A department or team. The company root has no row (formulas.md 13.1)."""

    __tablename__ = "org_unit"
    __table_args__ = (Index("ix_org_unit_company_status", "company_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("org_unit.id"), nullable=True)
    leader_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"), nullable=True)
    policy: Mapped[str | None] = mapped_column(String(16), nullable=True)  # None = inherit
    created_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    dissolved_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # product (no FK, 0008)


class HiringPlanRow(Base):
    """Delegated hiring for one unit and role (formulas.md 13.10, ADR-0015)."""

    __tablename__ = "hiring_plan"
    __table_args__ = (Index("ix_hiring_plan_company_status", "company_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("org_unit.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    ratio_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    equity_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    created_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    hired: Mapped[int] = mapped_column(Integer, nullable=False)
    closed_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_activity: Mapped[dict[str, int] | None] = mapped_column(JSON, nullable=True)
    focus: Mapped[str] = mapped_column(String(16), nullable=False, server_default="current")


# --- Products and markets (M3a, migration 0008_products) ------------------------------------


class ProductRow(Base):
    """A product of the player or an incumbent (formulas.md 11.2, ADR-0017)."""

    __tablename__ = "product"
    __table_args__ = (Index("ix_product_company_status", "company_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    quality: Mapped[float] = mapped_column(Float, nullable=False)
    feature_points: Mapped[float] = mapped_column(Float, nullable=False)
    brand: Mapped[float] = mapped_column(Float, nullable=False)
    marketing_budget_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    launched_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sunset_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retired_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    held_feature: Mapped[float | None] = mapped_column(Float, nullable=True)
    first_customer_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rotting: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")


class ProductSegmentRow(Base):
    __tablename__ = "product_segment"

    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), primary_key=True)
    segment: Mapped[str] = mapped_column(String(32), primary_key=True)
    price_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    customers: Mapped[float] = mapped_column(Float, nullable=False)
    capacity_limited: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    added_turn: Mapped[int] = mapped_column(Integer, nullable=False)


class MarketSegmentRow(Base):
    __tablename__ = "market_segment"

    category: Mapped[str] = mapped_column(String(32), primary_key=True)
    segment: Mapped[str] = mapped_column(String(32), primary_key=True)
    addressable: Mapped[float] = mapped_column(Float, nullable=False)


class ProductMonthRow(Base):
    """Month-end history per product and segment, append-only."""

    __tablename__ = "product_month"
    __table_args__ = (Index("ix_product_month_turn", "turn"),)

    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), primary_key=True)
    segment: Mapped[str] = mapped_column(String(32), primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, primary_key=True)
    quality: Mapped[float] = mapped_column(Float, nullable=False)
    feature_score: Mapped[float] = mapped_column(Float, nullable=False)
    brand: Mapped[float] = mapped_column(Float, nullable=False)
    appeal: Mapped[float | None] = mapped_column(Float, nullable=True)
    customers: Mapped[float] = mapped_column(Float, nullable=False)
    new: Mapped[float] = mapped_column(Float, nullable=False)
    churned: Mapped[float] = mapped_column(Float, nullable=False)
    revenue_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)


# --- Finance (M4, ADR-0018) -------------------------------------------------------------------


class CapTableEntryRow(Base):
    __tablename__ = "cap_table_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    holder_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    share_class: Mapped[str] = mapped_column(String(24), nullable=False)
    shares: Mapped[int] = mapped_column(BigInteger, nullable=False)
    acquired_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    firm: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    round_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class OptionGrantRow(Base):
    __tablename__ = "option_grant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False)
    employment_id: Mapped[int] = mapped_column(ForeignKey("employment.id"), nullable=False)
    granted: Mapped[int] = mapped_column(BigInteger, nullable=False)
    start_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    vested: Mapped[int] = mapped_column(BigInteger, nullable=False)
    forfeited: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class SafeRow(Base):
    __tablename__ = "safe"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cap_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    raised_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    resolved_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    converted_round_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class FundingRoundRow(Base):
    __tablename__ = "funding_round"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    series: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    target_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    opened_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_sheet_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    closed_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_firm: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pre_money_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    amount_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fd_before: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pool_shares: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    safe_shares: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    new_shares: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fd_pre: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    down_round: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")


class TermSheetRow(Base):
    __tablename__ = "term_sheet"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("funding_round.id"), nullable=False)
    firm: Mapped[str] = mapped_column(String(32), nullable=False)
    pre_money_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    offered_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_turn: Mapped[int] = mapped_column(Integer, nullable=False)


class BoardSeatRow(Base):
    __tablename__ = "board_seat"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # Null for an empty common seat (M4c, migration 0011).
    person_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"), nullable=True)
    seated_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    firm: Mapped[str | None] = mapped_column(String(32), nullable=True)
    round_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    months_below: Mapped[int] = mapped_column(Integer, nullable=False)


class RoundNomineeRow(Base):
    """The founder's board nominee for a round that adds a common seat (M4c). Its own table,
    not a column on funding_round: migration 0009 builds funding_round rows from the current
    models."""

    __tablename__ = "round_nominee"

    round_id: Mapped[int] = mapped_column(ForeignKey("funding_round.id"), primary_key=True)
    person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class BoardSeatHistoryRow(Base):
    """A director's confidence at the last month ends (M4b). Its own table, not a column on
    board_seat: migration 0009 builds board_seat rows from the current models."""

    __tablename__ = "board_seat_history"

    seat_id: Mapped[int] = mapped_column(ForeignKey("board_seat.id"), primary_key=True)
    history: Mapped[list[float]] = mapped_column(JSON, nullable=False)


# --- Rivals (M5, migration 0013_rivals; formulas.md 15) -------------------------------------


class WorkforcePoolRow(Base):
    """A rival's aggregate staff in one function (15.1, ADR-0010)."""

    __tablename__ = "workforce_pool"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    function: Mapped[str] = mapped_column(String(16), primary_key=True)
    headcount: Mapped[float] = mapped_column(Float, nullable=False)
    skill: Mapped[float] = mapped_column(Float, nullable=False)
    morale: Mapped[float] = mapped_column(Float, nullable=False)


class RivalEffectRow(Base):
    """A push, a cost cut's drag or a departed builder's quality loss (15.2)."""

    __tablename__ = "rival_effect"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    start_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    end_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class RivalMoveRow(Base):
    """A rival action or startup event (15.3-15.5); append-only."""

    __tablename__ = "rival_move"
    __table_args__ = (Index("ix_rival_move_turn", "turn"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    segment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    detail: Mapped[str] = mapped_column(String(200), nullable=False)


class PoachApproachRow(Base):
    """A rival's offer to one of the player's people (15.6)."""

    __tablename__ = "poach_approach"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rival_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False)
    offer_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    made_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    resolved_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SegmentShareRow(Base):
    """A product's share of a segment's served customers at the last month ends (15.3)."""

    __tablename__ = "segment_share"

    product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    segment: Mapped[str] = mapped_column(String(32), primary_key=True)
    history: Mapped[list[float]] = mapped_column(JSON, nullable=False)


class FreeAgentRow(Base):
    """A failed rival's employee waiting for the player's next search for their role
    (M6 sub-task 0, migration 0014_free_agents)."""

    __tablename__ = "free_agent"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    released_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    until_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)


# --- Events (M6, migration 0016_events) -----------------------------------------------------


class StorylineRow(Base):
    __tablename__ = "storyline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    started_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    person_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rival_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    segment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    next_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_template: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    ended_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)


class EventRow(Base):
    __tablename__ = "event"
    __table_args__ = (Index("ix_event_turn", "turn"), Index("ix_event_status", "status"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    template_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    strength: Mapped[float] = mapped_column(Float, nullable=False)
    person_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    unit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    segment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rival_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cash_base_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tone: Mapped[str] = mapped_column(String(16), nullable=False)
    storyline_id: Mapped[int | None] = mapped_column(ForeignKey("storyline.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    choices: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    chosen: Mapped[str | None] = mapped_column(String(1), nullable=True)
    resolved_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    loan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # M10 (0022)


class EventQueueRow(Base):
    __tablename__ = "event_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    template_id: Mapped[str] = mapped_column(String(64), nullable=False)
    due_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    # None: queued by the engine, not by answering an event (a lender event, M10)
    source_event_id: Mapped[int | None] = mapped_column(ForeignKey("event.id"), nullable=True)
    person_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rival_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    segment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    loan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # M10 (0022)


class EventModifierRow(Base):
    """An event choice's lasting effect on one stat (M10b, formulas.md 23.2; 0025). Rows stay
    after they expire, for history; the state loads those still running."""

    __tablename__ = "event_modifier"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("event.id"), nullable=True)
    target: Mapped[str] = mapped_column(String(32), nullable=False)
    stat: Mapped[str] = mapped_column(String(32), nullable=False)
    value_pct: Mapped[float] = mapped_column(Float, nullable=False)
    start_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    end_turn: Mapped[int] = mapped_column(Integer, nullable=False, index=True)


class LLMTextRow(Base):
    __tablename__ = "llm_text"
    __table_args__ = (Index("ix_llm_text_turn_kind", "turn", "kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    source: Mapped[str] = mapped_column(String(16), nullable=False, server_default="")


class LLMCallLogRow(Base):
    __tablename__ = "llm_call_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(16), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_cents: Mapped[float] = mapped_column(Float, nullable=False)  # real cents, not game money
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)


class CooAnswerRow(Base):
    """One "Ask my COO" question and answer (M7b, 0019; formulas.md 17.3): read-only, never
    fed into events; the newest `coo.keep_answers` per save are kept."""

    __tablename__ = "coo_answer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"), nullable=True)
    speaker: Mapped[str] = mapped_column(String(120), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # claude|mock|offline
    cost_cents: Mapped[float] = mapped_column(Float, nullable=False)  # real cents, not game money
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


# --- Divisions, executives and new markets (M8, migration 0020_divisions) -------------------
# Side tables, not columns on org_unit, product or search: migration 0013 loads and syncs
# those tables through the current models on older saves (see RoundNomineeRow).


class UnitServicesRow(Base):
    """A division's shared services, central or embedded (formulas.md 18.4)."""

    __tablename__ = "unit_services"

    unit_id: Mapped[int] = mapped_column(ForeignKey("org_unit.id"), primary_key=True)
    services: Mapped[str] = mapped_column(String(16), nullable=False)


class ProductDivisionRow(Base):
    """The division a product belongs to (18.1); no row or null = corporate."""

    __tablename__ = "product_division"

    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), primary_key=True)
    division_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # org_unit (no FK)


class SearchLevelRow(Base):
    """An exec-level search (18.3): every candidate is generated at this level."""

    __tablename__ = "search_level"

    search_id: Mapped[int] = mapped_column(ForeignKey("search.id"), primary_key=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False)


class ExecSeatRow(Base):
    """An executive seat filled at least once (18.3); person_id null = vacant."""

    __tablename__ = "exec_seat"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    seat: Mapped[str] = mapped_column(String(8), primary_key=True)
    person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # person (no FK)
    since_turn: Mapped[int] = mapped_column(Integer, nullable=False)


class DivisionMonthRow(Base):
    """Headcount per division (and corporate, division_id null) at each month's payroll, for
    the shared-services allocation of the division statements (18.1)."""

    __tablename__ = "division_month"
    __table_args__ = (Index("ix_division_month_company_turn", "company_id", "turn"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    division_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    headcount: Mapped[int] = mapped_column(Integer, nullable=False)
    embedded: Mapped[bool] = mapped_column(Boolean, nullable=False)


# --- Former staff (M7c, migration 0021_former_staff) ---------------------------------------


class FormerStaffRow(Base):
    """What the player knew of an employee when they left (M7c): displayed ranges and noticed
    tags frozen at departure, so a later change at a rival never moves them. Never a true
    value (ADR-0007)."""

    __tablename__ = "former_staff"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    employment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    unit_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    end_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)
    rival_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # poached by
    # {"ranges": {attr: [lo, hi]}, "tags": [[tag, turn]], "interests": [...] | null,
    #  "work_style": str | null}; potential is a range under "potential_ability"
    knowledge: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class InboxEventLinkRow(Base):
    """An event an inbox message links to (M7c): the "While you were away" summary lists the
    events decided for the player, each opening that event's card."""

    __tablename__ = "inbox_event_link"

    item_id: Mapped[int] = mapped_column(ForeignKey("inbox_item.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, nullable=False)  # event (no FK)
    label: Mapped[str] = mapped_column(String(200), nullable=False)


# --- Capital and macro (M10, migration 0022_capital_macro) -----------------------------------


class MacroMonthRow(Base):
    """One month's macro indicators (20.1). Rows exist only for months already played."""

    __tablename__ = "macro_month"

    turn: Mapped[int] = mapped_column(Integer, primary_key=True)
    base_rate: Mapped[float] = mapped_column(Float, nullable=False)
    climate: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    ai_index: Mapped[float] = mapped_column(Float, nullable=False)
    ai_change: Mapped[float] = mapped_column(Float, nullable=False)
    downturn_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)


class LoanRow(Base):
    """Venture debt or a bank loan (20.3)."""

    __tablename__ = "loan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    instrument: Mapped[str] = mapped_column(String(16), nullable=False)
    lender: Mapped[str] = mapped_column(String(32), nullable=False)
    principal_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rate_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    signed_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    interest_only_months: Mapped[int] = mapped_column(Integer, nullable=False)
    round_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warrant_shares: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    closed_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interest_paid_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    principal_paid_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    breach_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    breaches: Mapped[int] = mapped_column(Integer, nullable=False)


class FinanceHistoryRow(Base):
    """The player's operating result and burn at the last month ends (20.3 covenants)."""

    __tablename__ = "finance_history"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    op_history: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    burn_history: Mapped[list[int]] = mapped_column(JSON, nullable=False)


# --- Cities, offices and regions (M9, formulas.md 19) --------------------------------------
# Side tables, like M8's: migration 0013 loads company, person, org_unit and search through
# the current models on older saves, so their new values live in tables of their own.


class CompanyHqRow(Base):
    """A company's HQ city (19.1); the player's only. No row: geo.default_hq_city."""

    __tablename__ = "company_hq"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    city: Mapped[str] = mapped_column(String(32), nullable=False)


class PersonCityRow(Base):
    """A person's home city (19.1). No row: the first city of their region."""

    __tablename__ = "person_city"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    city: Mapped[str] = mapped_column(String(32), nullable=False)


class OfficeRow(Base):
    """A leased office (19.2); closed offices keep their row."""

    __tablename__ = "office"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    city: Mapped[str] = mapped_column(String(32), nullable=False)
    seats: Mapped[int] = mapped_column(Integer, nullable=False)
    opened_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    closed_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)


class UnitOfficeRow(Base):
    """A unit's home office (19.2); office_id null = its parent's, up to flexible HQ space."""

    __tablename__ = "unit_office"

    unit_id: Mapped[int] = mapped_column(ForeignKey("org_unit.id"), primary_key=True)
    office_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CandidateRelocationRow(Base):
    """A candidate who lives outside their search's city and would move there (19.3)."""

    __tablename__ = "candidate_relocation"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    city: Mapped[str] = mapped_column(String(32), nullable=False)


class SearchCityRow(Base):
    """The city a search's candidates live in, or "anywhere" (19.3)."""

    __tablename__ = "search_city"

    search_id: Mapped[int] = mapped_column(ForeignKey("search.id"), primary_key=True)
    city: Mapped[str] = mapped_column(String(32), nullable=False)


class RegionalMarketRow(Base):
    """Addressable customers in a region other than the home region (19.5)."""

    __tablename__ = "regional_market"

    category: Mapped[str] = mapped_column(String(32), primary_key=True)
    segment: Mapped[str] = mapped_column(String(32), primary_key=True)
    region: Mapped[str] = mapped_column(String(32), primary_key=True)
    addressable: Mapped[float] = mapped_column(Float, nullable=False)


class AuthorityRow(Base):
    """A seat's authority and guardrails (M10c, formulas.md 24.1; 0027)."""

    __tablename__ = "exec_authority"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    seat: Mapped[str] = mapped_column(String(8), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    guardrails: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    since_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    price_anchors: Mapped[list[Any]] = mapped_column(JSON, nullable=False)


class ExecDecisionRow(Base):
    """What an executive with authority did, or got wrong (M10c, 24.1-24.2; 0027)."""

    __tablename__ = "exec_decision"
    __table_args__ = (Index("ix_exec_decision_turn", "turn"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    seat: Mapped[str] = mapped_column(String(8), nullable=False)
    person_id: Mapped[int] = mapped_column(Integer, nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    mistake: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ProposalRow(Base):
    """A CFO or COO proposal for the player's Approve or Decline (M10c, 24.1; 0027)."""

    __tablename__ = "exec_proposal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    seat: Mapped[str] = mapped_column(String(8), nullable=False)
    person_id: Mapped[int] = mapped_column(Integer, nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    resolved_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PitchRow(Base):
    """An executive's pitch (M13b, 27.1; 0032): its numbers, the answer and how it turned
    out. Every pitch stays: executives' records count them all."""

    __tablename__ = "exec_pitch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    seat: Mapped[str] = mapped_column(String(8), nullable=False)
    person_id: Mapped[int] = mapped_column(Integer, nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    why: Mapped[str] = mapped_column(Text, nullable=False)
    cost_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    capex_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    monthly_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    hires: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    low: Mapped[int] = mapped_column(BigInteger, nullable=False)
    high: Mapped[int] = mapped_column(BigInteger, nullable=False)
    risk: Mapped[str] = mapped_column(Text, nullable=False)
    central: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    resolved_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    baseline: Mapped[int] = mapped_column(BigInteger, nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    outcome_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    measured: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class EraWindowRow(Base):
    """A player first mover's era window and the baseline its report compares against
    (M13b, 27.3; 0032)."""

    __tablename__ = "era_window"

    era_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    start_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    products: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    trend: Mapped[float] = mapped_column(Float, nullable=False)
    demand: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    reported: Mapped[bool] = mapped_column(Boolean, nullable=False)


class PitchPolicyRow(Base):
    """The player's pitch settings per company (M13b, 27.1; 0032)."""

    __tablename__ = "pitch_policy"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    auto_approve_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    stop_for_big: Mapped[bool] = mapped_column(Boolean, nullable=False)


class MarketingSplitRow(Base):
    """A product's marketing budget share in one region, bp (23.5, M10b; 0026). No rows: the
    budget follows revenue by region."""

    __tablename__ = "product_marketing_split"

    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), primary_key=True)
    region: Mapped[str] = mapped_column(String(32), primary_key=True)
    share_bp: Mapped[int] = mapped_column(Integer, nullable=False)


class ProductRegionRow(Base):
    """A product launched in a region other than the home region (19.5)."""

    __tablename__ = "product_region"

    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), primary_key=True)
    region: Mapped[str] = mapped_column(String(32), primary_key=True)
    launched_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    live_turn: Mapped[int] = mapped_column(Integer, nullable=False)


class RegionalSegmentRow(Base):
    """A product's price and customers in one segment of another region (19.5)."""

    __tablename__ = "regional_segment"

    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), primary_key=True)
    region: Mapped[str] = mapped_column(String(32), primary_key=True)
    segment: Mapped[str] = mapped_column(String(32), primary_key=True)
    price_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    customers: Mapped[float] = mapped_column(Float, nullable=False)
    capacity_limited: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    added_turn: Mapped[int] = mapped_column(Integer, nullable=False)


# --- Facilities, market goods and contracts (M12a, formulas.md 22) --------------------------


class FacilityRow(Base):
    """A facility (22.2; ADR-0020 2): a data centre now, more kinds later. Closed ones keep
    their row."""

    __tablename__ = "facility"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    region: Mapped[str] = mapped_column(String(32), nullable=False)
    city: Mapped[str | None] = mapped_column(String(32), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    on_time: Mapped[int] = mapped_column(Integer, nullable=False)
    ordered_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    ready_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    late_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    capex_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    input_index: Mapped[float] = mapped_column(Float, nullable=False)
    capex_paid_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    depreciated_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    unit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contract_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    closed_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # M12b (26.2; 0031): an assembly plant's yield this month and last month's units run
    yield_rate: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    run_units: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    sold_units: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")


class SupplyMonthRow(Base):
    """One market good's month (22.4): index, allocation, trend and the latest shock. Rows
    exist only for months already played."""

    __tablename__ = "supply_month"

    good: Mapped[str] = mapped_column(String(32), primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, primary_key=True)
    price_index: Mapped[float] = mapped_column(Float, nullable=False)
    allocation: Mapped[float] = mapped_column(Float, nullable=False)
    base: Mapped[float] = mapped_column(Float, nullable=False)
    change: Mapped[float] = mapped_column(Float, nullable=False)
    shock_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shock_months: Mapped[int] = mapped_column(Integer, nullable=False)
    shock_rise: Mapped[float] = mapped_column(Float, nullable=False)
    shock_allocation: Mapped[float] = mapped_column(Float, nullable=False)
    shock_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)  # M17 (33.1)


class SupplyContractRow(Base):
    """A component contract (22.4): a locked index on a volume of builds, take-or-pay."""

    __tablename__ = "supply_contract"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    good: Mapped[str] = mapped_column(String(32), nullable=False)
    price_index: Mapped[float] = mapped_column(Float, nullable=False)
    signed_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    end_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_value_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    used: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    settled_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)


class FacilityOutageRow(Base):
    """A data-centre outage (22.5), kept as history."""

    __tablename__ = "facility_outage"
    __table_args__ = (Index("ix_facility_outage_turn", "turn"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    customers_lost: Mapped[float] = mapped_column(Float, nullable=False)


class ProductionContractRow(Base):
    """A contract-manufacturing or wafer contract (26.2, 26.3; 0031)."""

    __tablename__ = "production_contract"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    supplier: Mapped[str] = mapped_column(String(32), nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    # thousandths of a cent, exact (0038_m15r; was a FLOAT price_cents)
    price_millicents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    signed_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    end_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    city: Mapped[str | None] = mapped_column(String(32), nullable=True)
    delivered: Mapped[float] = mapped_column(Float, nullable=False)
    used: Mapped[float] = mapped_column(Float, nullable=False)
    charged_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    node: Mapped[str | None] = mapped_column(String(16), nullable=True)  # M21 (38.1; 0046)


class ProductionMonthRow(Base):
    """One unit-sale product's month of production and cost of goods (26.2, 26.3; 0031),
    append-only history."""

    __tablename__ = "production_month"

    turn: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    capacity: Mapped[float] = mapped_column(Float, nullable=False)
    units: Mapped[float] = mapped_column(Float, nullable=False)
    plant_units: Mapped[float] = mapped_column(Float, nullable=False)
    contract_units: Mapped[float] = mapped_column(Float, nullable=False)
    own_chips: Mapped[float] = mapped_column(Float, nullable=False)
    bought_chips: Mapped[float] = mapped_column(Float, nullable=False)
    internal_units: Mapped[float] = mapped_column(Float, nullable=False)
    bom_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chip_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    assembly_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    lost_units: Mapped[float] = mapped_column(Float, nullable=False)
    fab_chips: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")  # 0048


class CompanyRivalKeyRow(Base):
    """A rival's stable identity for its RNG keys (ADR-0013 amendment, M12a; 0028). Companies
    without a row (the player, rivals of older saves) are keyed by their id."""

    __tablename__ = "company_rival_key"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    rival_key: Mapped[list[int]] = mapped_column(JSON, nullable=False)


# --- Research (M11, formulas.md 21; 0028) ---------------------------------------------------


class ResearchLeadRow(Base):
    """A company's lead in one research domain beyond the world's baseline (21.1)."""

    __tablename__ = "research_lead"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    domain: Mapped[str] = mapped_column(String(32), primary_key=True)
    lead: Mapped[float] = mapped_column(Float, nullable=False)


class ResearchProjectRow(Base):
    """A research project (21.3), or a rival's research action without a unit (21.6)."""

    __tablename__ = "research_project"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    domain: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False)
    budget_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    end_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recent: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    gained: Mapped[float] = mapped_column(Float, nullable=False)
    last_event: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_event_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)


class EraArrivalRow(Base):
    """An era milestone that has arrived (21.4); company_id NULL on its historical date."""

    __tablename__ = "era_arrival"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    months_early: Mapped[int] = mapped_column(Integer, nullable=False)


class LicenseRow(Base):
    """A licence of research lead between two companies (21.5)."""

    __tablename__ = "research_license"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    licensor_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    licensee_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    domain: Mapped[str] = mapped_column(String(32), nullable=False)
    points: Mapped[float] = mapped_column(Float, nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    royalty_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    royalty_end_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)


# --- Going public and the Chair (M13, formulas.md 25; 0030) ---------------------------------


class ListingRow(Base):
    """A company's IPO chain (25.2), from hiring the banks to the listing or a pull. One per
    company: hiring banks again after a pull replaces it."""

    __tablename__ = "listing"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    bank: Mapped[str] = mapped_column(String(32), nullable=False)
    hired_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    filed_late: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    roadshow_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ambition: Mapped[str | None] = mapped_column(String(8), nullable=True)
    share_choice: Mapped[str | None] = mapped_column(String(8), nullable=True)
    dual_class: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    demand: Mapped[float | None] = mapped_column(Float, nullable=True)  # hidden (25.8)
    price_choice: Mapped[str | None] = mapped_column(String(8), nullable=True)
    shares_before: Mapped[int] = mapped_column(BigInteger, nullable=False)
    new_shares: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    gross_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fee_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    first_day_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    close_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    listed_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pulled_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)


class PublicCompanyRow(Base):
    """A listed company's market state (25.3-25.5). `sentiment` and `value_cents` are hidden
    (25.8)."""

    __tablename__ = "public_company"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    listed_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    dual_class: Mapped[bool] = mapped_column(Boolean, nullable=False)
    listing_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sentiment: Mapped[float] = mapped_column(Float, nullable=False)
    value_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    analysts: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    below_value_months: Mapped[int] = mapped_column(Integer, nullable=False)
    below_takeover_months: Mapped[int] = mapped_column(Integer, nullable=False)
    last_activist_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_takeover_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    beat_streak: Mapped[int] = mapped_column(Integer, nullable=False)
    miss_streak: Mapped[int] = mapped_column(Integer, nullable=False)
    results: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    quarter_revenue_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quarter_op_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dividend_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    lapsed_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    pending: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class GuidanceRow(Base):
    """One quarter's guidance and, once reported, its result (25.4)."""

    __tablename__ = "guidance"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    quarter_turn: Mapped[int] = mapped_column(Integer, primary_key=True)
    revenue_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    margin_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    consensus_revenue_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    consensus_margin_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    by_player: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actual_revenue_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actual_margin_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[str | None] = mapped_column(String(8), nullable=True)
    price_before_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    price_after_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class ShareMonthRow(Base):
    """A listed company's month end (25.3). Every month is kept; the state holds the last
    `public.history_months`."""

    __tablename__ = "share_month"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, primary_key=True)
    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shares: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mark: Mapped[str] = mapped_column(String(16), nullable=False)


class CeoRow(Base):
    """An appointed CEO (25.6); ended ones keep their row."""

    __tablename__ = "ceo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    person_id: Mapped[int] = mapped_column(Integer, nullable=False)
    since_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    ended_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)
    low_months: Mapped[int] = mapped_column(Integer, nullable=False)
    price_anchors: Mapped[list[Any]] = mapped_column(JSON, nullable=False)


class CeoDecisionRow(Base):
    """One decision a CEO took (25.6). The state holds the last `ceo.memory_months`."""

    __tablename__ = "ceo_decision"
    __table_args__ = (Index("ix_ceo_decision_turn", "turn"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    person_id: Mapped[int] = mapped_column(Integer, nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    mistake: Mapped[bool] = mapped_column(Boolean, nullable=False)
    undo: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    overridden_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)


# --- Mergers and acquisitions (M14, formulas.md 28; 0034) -------------------------------------


class RivalListingRow(Base):
    """A listed rival's sentiment S (28.1; 0034): its market cap is V_f x S."""

    __tablename__ = "rival_listing"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    sentiment: Mapped[float] = mapped_column(Float, nullable=False)


class CompanyParentRow(Base):
    """A kept brand's parent company (28.5, ADR-0020; 0034)."""

    __tablename__ = "company_parent"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)


class TargetFileRow(Base):
    """What one acquirer knows of one target (28.2-28.3; 0034). `data` holds TargetFile's
    other fields, hidden ones included (never sent to the API)."""

    __tablename__ = "mna_target_file"

    acquirer_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class DealRow(Base):
    """A deal (28.3-28.4; 0034). `data` holds the Deal's fields."""

    __tablename__ = "mna_deal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class AcquisitionRow(Base):
    """A closed acquisition (28.5; 0034). `data` holds the Acquisition's fields."""

    __tablename__ = "mna_acquisition"

    deal_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class AcquiredPersonRow(Base):
    """An acquired key person during culture clash (28.5; 0034)."""

    __tablename__ = "mna_acquired_person"

    person_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


# --- The founder in public (M14b, formulas.md 29; 0033) --------------------------------------


class PressMomentRow(Base):
    """A press moment (29.1). Every moment keeps its row; the state holds the pending and
    queued ones and those raised in the last 12 months."""

    __tablename__ = "press_moment"
    __table_args__ = (Index("ix_press_moment_turn", "turn"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    event_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rival_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    facts: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    tone: Mapped[str | None] = mapped_column(String(16), nullable=True)
    answered_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    share_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    backfired: Mapped[bool] = mapped_column(Boolean, nullable=False)


class PromiseRow(Base):
    """A public promise (29.2). The state holds every promise."""

    __tablename__ = "press_promise"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    made_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    moment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rival_product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    domain: Mapped[str | None] = mapped_column(String(32), nullable=True)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    baseline: Mapped[int] = mapped_column(Integer, nullable=False)
    prices: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    ambition: Mapped[float] = mapped_column(Float, nullable=False)
    audience: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    resolved_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reminder_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CredibilityRow(Base):
    """A company's public credibility, 0-100, with its last changes (29.3)."""

    __tablename__ = "credibility"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    history: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    fired_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fired: Mapped[int] = mapped_column(Integer, nullable=False)
    staff_start: Mapped[int] = mapped_column(Integer, nullable=False)


class FeudRow(Base):
    """The player's founder against one rival's CEO, 0-100 (29.4)."""

    __tablename__ = "feud"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    rival_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    causes: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    rivalry_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)


class StatementRow(Base):
    """A rival CEO's public statement (29.4). The state holds the last 24 months."""

    __tablename__ = "rival_statement"
    __table_args__ = (Index("ix_rival_statement_turn", "turn"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rival_id: Mapped[int] = mapped_column(Integer, nullable=False)
    person_id: Mapped[int] = mapped_column(Integer, nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DepartureRow(Base):
    """Someone who resigned or was poached (29.5): Replace's source. One row per person (a
    later departure replaces it); the state holds the last `recruit.replace_window` months."""

    __tablename__ = "departure"
    __table_args__ = (Index("ix_departure_turn", "turn"),)

    person_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    unit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")


class SearchInterestRow(Base):
    """A search for candidates with one interest only (29.5). No row: any interest."""

    __tablename__ = "search_interest"

    search_id: Mapped[int] = mapped_column(ForeignKey("search.id"), primary_key=True)
    interest: Mapped[str] = mapped_column(String(32), nullable=False)


class HiringPlanDetailRow(Base):
    """A hiring plan's M14b fields (29.5): its interest filter, and for a Replace plan the
    leaver it replaces and their level. No row: all null."""

    __tablename__ = "hiring_plan_detail"

    plan_id: Mapped[int] = mapped_column(ForeignKey("hiring_plan.id"), primary_key=True)
    interest: Mapped[str | None] = mapped_column(String(32), nullable=True)
    replace_of: Mapped[int | None] = mapped_column(Integer, nullable=True)
    level: Mapped[str | None] = mapped_column(String(16), nullable=True)


# --- Game modes and polish (M15b, formulas.md 30; 0035) -------------------------------------


class CompanyScoreRow(Base):
    """A company's score at a December or a game's end (30.1). `data` holds the parts."""

    __tablename__ = "company_score"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class GameModeRow(Base):
    """The save's mode, Sandbox or a scenario (30.2-30.3); no row: a campaign."""

    __tablename__ = "game_mode"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # always 1
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class RankingRow(Base):
    """One place in one January's list (30.4). `data` holds company_id and value."""

    __tablename__ = "ranking"

    turn: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    place: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class QuarterMarkRow(Base):
    """A product's quality and customers at the last quarterly reports (M15b; 0035)."""

    __tablename__ = "product_quarter_mark"

    product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class VentureRow(Base):
    """A company the player sold before founding again (M15b addendum 10, migration 0035)."""

    __tablename__ = "venture"

    company_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class StartupSmallRow(Base):
    """A rival startup's first month of its current run below rivals.startup.small_staff
    people (formulas.md 30.7 V5, M15a, 0036). No row: not small."""

    __tablename__ = "startup_small"

    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), primary_key=True)
    since_turn: Mapped[int] = mapped_column(Integer, nullable=False)


class FounderLifeRow(Base):
    """A founder's stress, burnout and persona (M24, 32.1 and 32.4; migration 0037)."""

    __tablename__ = "founder_life"

    person_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class PersonalEntryRow(Base):
    """One entry in a founder's own book (32.2): never in `ledger_entry`, which holds only
    companies' books. `lines` is a list of [account, cents] pairs that sums to zero."""

    __tablename__ = "personal_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    person_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    memo: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    lines: Mapped[list[Any]] = mapped_column(JSON, nullable=False)


class FoundationRow(Base):
    """A founder's foundation (32.3)."""

    __tablename__ = "foundation"

    person_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class InfluenceRow(Base):
    """A company's influence in one region (32.5). `data` holds the hidden scandal risk too:
    the API reads it only through the exposure band."""

    __tablename__ = "influence"

    company_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region: Mapped[str] = mapped_column(String(40), primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


# --- The founder's own investments (M26, formulas.md 37; 0044) ------------------------------


class StartupRoundRow(Base):
    """A rival startup's funding round, its price (post-money) and source (37.2)."""

    __tablename__ = "startup_round"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class AngelStakeRow(Base):
    """The founder's stake in one private startup (37.2). `data` holds a concealed
    conflict's hidden discovery month too (never in the API)."""

    __tablename__ = "angel_stake"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class PersonalTradeRow(Base):
    """One trade of listed shares by the founder (37.3). `data` holds the hidden regulatory
    risk and the investigation's draw and timing too (never in the API)."""

    __tablename__ = "personal_trade"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class PublicHoldingRow(Base):
    """Listed shares the founder holds and their book cost (37.3)."""

    __tablename__ = "public_holding"

    person_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class FamilyOfficeRow(Base):
    """The founder's family office: manager, mandate and monthly returns (37.4)."""

    __tablename__ = "family_office"

    person_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class WealthPointRow(Base):
    """The founder's net worth and its parts at a month end (37.5)."""

    __tablename__ = "wealth_point"

    person_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class MarketIndexRow(Base):
    """The market index at a month end, with every listed company's cap (37.4)."""

    __tablename__ = "market_index"

    turn: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class NetworkRow(Base):
    """Someone in the founder's network: they left the player's companies (37.2). Their
    person record stays loaded while they are listed here."""

    __tablename__ = "founder_network"

    person_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


# --- The holding company and its subsidiaries (M16, formulas.md 31; 0039) --------------------


class OwnershipRow(Base):
    """One company's holding of another over a run of turns (31.1; 0039): `data` holds the
    Ownership's other fields (from_turn, to_turn, book_cents, equity_cents, stake_bp,
    end_reason)."""

    __tablename__ = "group_ownership"
    __table_args__ = (Index("ix_group_ownership_company", "company_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class HoldingRow(Base):
    """The player's holding company (31.2; 0039): `data` holds operating_id, formed_turn and
    chair_id."""

    __tablename__ = "group_holding"

    company_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class StakeRow(Base):
    """A stake the group does not control (31.3, 31.5; 0039): `data` holds the Stake's other
    fields (stake_bp, cost_cents, carrying_cents, from_turn, kind, to_turn, disclosed_bp)."""

    __tablename__ = "group_stake"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class MandateRow(Base):
    """A subsidiary's mandate (31.4; 0039): `data` holds the Mandate's other fields."""

    __tablename__ = "group_mandate"

    company_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class GroupPitchRow(Base):
    """A subsidiary CEO's request to the group for capital (31.4; 0039)."""

    __tablename__ = "group_pitch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class GroupListingRow(Base):
    """A company the group listed: a carve-out or a spin-off (31.5; 0039)."""

    __tablename__ = "group_listing"

    company_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class PersonalStakeRow(Base):
    """Shares the founder holds personally in a spun-off company (31.5; 0039)."""

    __tablename__ = "group_personal_stake"

    person_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class TransferFlowRow(Base):
    """One group company supplying another at a transfer price (31.6; 0039)."""

    __tablename__ = "group_transfer_flow"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class CommodityDealRow(Base):
    """A company's commodity contract or offtake agreement (formulas.md 33.3; 0041). Its
    fields are in `data` (tst.db.commodity_io)."""

    __tablename__ = "commodity_deal"
    __table_args__ = (Index("ix_commodity_deal_company", "company_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


# --- M18 (formulas.md 34; migration 0042): exploration ---------------------------------------


class GeoBlockRow(Base):
    """A block and its hidden deposit (34.1; 0042). `data` holds the true_* fields: hidden
    values (ADR-0007), read only by the sim, never by the API."""

    __tablename__ = "exploration_block"

    region: Mapped[str] = mapped_column(String(32), primary_key=True)
    idx: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class SupplierLicenceRow(Base):
    """A supplier's exploration licence (34.4; 0042)."""

    __tablename__ = "exploration_supplier_licence"

    region: Mapped[str] = mapped_column(String(32), primary_key=True)
    block: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class DeskStudyRow(Base):
    """A desk study and its heat-map bands (34.2; 0042)."""

    __tablename__ = "exploration_desk_study"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class ExplorationProjectRow(Base):
    """A licensed block's pipeline (34.2; 0042): revealed results, and the hidden permit
    month (`hidden_due_turn`)."""

    __tablename__ = "exploration_project"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class DrillHoleRow(Base):
    """A drill hole's assay (34.2; 0042): public once drilled."""

    __tablename__ = "exploration_hole"

    project_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    n: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


# --- M19 (formulas.md 35; migration 0044): mining operations ---------------------------------


class MineRow(Base):
    """A mine (35.2-35.4; 0043), keyed by its facility's id. `data` holds the hidden_* fields
    (the overrun and the deposit's truth: ADR-0007), read only by the sim, never by the API."""

    __tablename__ = "mine"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class MineDealRow(Base):
    """A contract or offtake a mine signed as seller (35.3; 0043)."""

    __tablename__ = "mine_deal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mine_id: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class RivalBidRow(Base):
    """A rival's bid for a group project or mine (35.5; 0043)."""

    __tablename__ = "mine_rival_bid"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


# --- M20 (formulas.md 36; migration 0045): refining and wafers -----------------------------


class FabRow(Base):
    """A fab's own state beside its facility row (38.2; 0046): node, quoted capex, EUV tools,
    yield, capex parts, a conversion, its latest month and history. The true capex (with the
    hidden overrun) is the facility row's `capex_cents`."""

    __tablename__ = "fab"

    facility_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class RefineryRow(Base):
    """A refinery's own state beside its facility row (36; 0045): recipe, quoted capex, curbs,
    incidents, its latest month and history. The true capex (with the hidden overrun) is the
    facility row's `capex_cents`."""

    __tablename__ = "refinery"

    facility_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class RefiningDealRow(Base):
    """A refinery contract (36.1; 0045): buy an input or sell an output at a fixed price."""

    __tablename__ = "refining_deal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class RefiningSupplyRow(Base):
    """One of the latest month's own-group supply lots (36.1-36.2; 0045), in order `n`."""

    __tablename__ = "refining_supply"

    n: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


# --- M22 (formulas.md 39; migration 0046): geopolitics and export controls -----------------


class GeoRecordRow(Base):
    """One geopolitical record (39; 0046): `kind` names its GameState collection (tension,
    seeded_rules, suspensions, licences, variants, listings, sites, exits, geo_notices) and
    `data` its fields; rows keep each collection's order."""

    __tablename__ = "geo_record"

    n: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


# --- M28 (formulas.md 41; migration 0049): a living world ------------------------------------


class WorldRecordRow(Base):
    """One living-world record (41; 0049): `kind` names its GameState collection
    (chain_companies, world_facilities, world_goods, region_cycles, world_news, rival_deals,
    rival_mandates, world_offtakes, world_bids, china_lags) and `data` its fields; rows keep
    each collection's order."""

    __tablename__ = "world_record"

    n: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
