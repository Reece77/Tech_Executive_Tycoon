"""Convert between ORM rows and sim dataclasses. The sim never sees ORM objects."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from tst.db.models import (
    CompanyRow,
    DecisionLogRow,
    LedgerEntryRow,
    LedgerLineRow,
    SaveMetaRow,
    TurnLogRow,
    TurnSnapshotRow,
)
from tst.sim.decisions import Decisions
from tst.sim.ledger import LedgerEntry, LedgerLine
from tst.sim.snapshot import CompanySnapshot, TurnSnapshot
from tst.sim.state import CompanyState, GameState, SaveMeta
from tst.sim.turn import LogItem


def company_to_state(row: CompanyRow) -> CompanyState:
    return CompanyState(
        id=row.id,
        name=row.name,
        is_player=row.is_player,
        stage=row.stage,
        founded_turn=row.founded_turn,
    )


def company_to_row(company: CompanyState) -> CompanyRow:
    return CompanyRow(
        id=company.id,
        name=company.name,
        is_player=company.is_player,
        stage=company.stage,
        founded_turn=company.founded_turn,
    )


def update_company_row(row: CompanyRow, company: CompanyState) -> None:
    row.name = company.name
    row.is_player = company.is_player
    row.stage = company.stage
    row.founded_turn = company.founded_turn


def game_state_from_rows(meta: SaveMetaRow, companies: list[CompanyRow]) -> GameState:
    return GameState(
        save_meta=SaveMeta(
            name=meta.name,
            master_seed=meta.master_seed,
            scenario_id=meta.scenario_id,
            difficulty=meta.difficulty,
        ),
        turn=meta.current_turn,
        companies=tuple(company_to_state(r) for r in sorted(companies, key=lambda r: r.id)),
    )


def entry_to_row(entry: LedgerEntry) -> LedgerEntryRow:
    return LedgerEntryRow(
        turn=entry.turn,
        company_id=entry.company_id,
        memo=entry.memo,
        lines=[
            LedgerLineRow(account_code=ln.account, amount_cents=ln.amount) for ln in entry.lines
        ],
    )


def entry_from_row(row: LedgerEntryRow) -> LedgerEntry:
    return LedgerEntry(
        turn=row.turn,
        company_id=row.company_id,
        memo=row.memo,
        lines=tuple(LedgerLine(ln.account_code, ln.amount_cents) for ln in row.lines),
    )


def snapshot_to_rows(snapshot: TurnSnapshot) -> list[TurnSnapshotRow]:
    return [
        TurnSnapshotRow(turn=snapshot.turn, company_id=s.company_id, kpis=s.kpis())
        for s in snapshot.companies
    ]


def company_snapshot_from_row(row: TurnSnapshotRow) -> CompanySnapshot:
    kpis: dict[str, Any] = row.kpis
    return CompanySnapshot(
        company_id=row.company_id,
        cash_cents=int(kpis["cash_cents"]),
        monthly_burn_cents=int(kpis["monthly_burn_cents"]),
        headcount=int(kpis["headcount"]),
    )


def log_item_to_row(item: LogItem) -> TurnLogRow:
    return TurnLogRow(
        turn=item.turn, company_id=item.company_id, kind=item.kind, message=item.message
    )


def decisions_to_row(turn: int, company_id: int, decisions: Decisions) -> DecisionLogRow:
    return DecisionLogRow(
        turn=turn, company_id=company_id, kind="turn_decisions", payload=asdict(decisions)
    )
