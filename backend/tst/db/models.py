"""SQLAlchemy ORM models for a save file. Column reference: docs/data-dictionary.md.

History tables (ledger_entry, ledger_line, turn_snapshot, decision_log, turn_log) are
append-only (ADR-0004 section 6). Schema changes need an Alembic migration.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Bumped by any migration that changes the schema; stored in save_meta.schema_version.
SCHEMA_VERSION = 3


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
    next_person_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_search_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_offer_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    next_employment_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class CompanyRow(Base):
    __tablename__ = "company"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_player: Mapped[bool] = mapped_column(Boolean, nullable=False)
    stage: Mapped[int] = mapped_column(Integer, nullable=False)
    founded_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    mission: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default="[]")


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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("ledger_entry.id"), nullable=False)
    account_code: Mapped[str] = mapped_column(ForeignKey("account.code"), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)

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


class RelationshipRow(Base):
    __tablename__ = "relationship"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    other_person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    affinity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0 = neutral
    updated_turn: Mapped[int] = mapped_column(Integer, nullable=False)


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


class CandidateRow(Base):
    __tablename__ = "candidate"
    __table_args__ = (Index("ix_candidate_company_status", "company_id", "status"),)

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), nullable=False)
    search_id: Mapped[int] = mapped_column(ForeignKey("search.id"), nullable=False)
    created_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    resolved_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)


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


class PersonMoraleLogRow(Base):
    """Month-end morale per employee, append-only (for the profile's 12-turn history)."""

    __tablename__ = "person_morale_log"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, primary_key=True)
    morale: Mapped[float] = mapped_column(Float, nullable=False)
