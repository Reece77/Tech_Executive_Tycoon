"""SQLAlchemy ORM models for a save file. Column reference: docs/data-dictionary.md.

History tables (ledger_entry, ledger_line, turn_snapshot, decision_log, turn_log) are
append-only (ADR-0004 section 6). Schema changes need an Alembic migration.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Bumped by any migration that changes the schema; stored in save_meta.schema_version.
SCHEMA_VERSION = 1


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


class CompanyRow(Base):
    __tablename__ = "company"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_player: Mapped[bool] = mapped_column(Boolean, nullable=False)
    stage: Mapped[int] = mapped_column(Integer, nullable=False)
    founded_turn: Mapped[int] = mapped_column(Integer, nullable=False)


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


class TurnLogRow(Base):
    __tablename__ = "turn_log"
    __table_args__ = (Index("ix_turn_log_turn", "turn"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("company.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
