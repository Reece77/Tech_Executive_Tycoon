"""Save files: create, load, and run turns in one transaction each (ADR-0004)."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tst.db import migrate
from tst.db.backup import SAVE_SUFFIX, periodic_backup, slug_of
from tst.db.mappers import (
    company_snapshot_from_row,
    company_to_row,
    decisions_to_row,
    entry_to_row,
    game_state_from_rows,
    log_item_to_row,
    snapshot_to_rows,
    update_company_row,
)
from tst.db.models import (
    SCHEMA_VERSION,
    AccountRow,
    CompanyRow,
    LedgerEntryRow,
    LedgerLineRow,
    SaveMetaRow,
    TurnSnapshotRow,
)
from tst.db.session import make_engine, make_sessionmaker
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.data_models import DEFAULT_DIFFICULTY
from tst.sim.decisions import Decisions
from tst.sim.errors import (
    InvalidSaveNameError,
    InvalidSeedError,
    SaveExistsError,
    SaveNotFoundError,
    UnknownScenarioError,
)
from tst.sim.ledger import AccountCode
from tst.sim.money import Cents
from tst.sim.people.founder import FounderSpec
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.snapshot import CompanySnapshot, runway_months
from tst.sim.state import GameState, company_cash
from tst.sim.turn import TurnResult, advance_turn

log = logging.getLogger(__name__)

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
MAX_STORED_SEED = 2**63 - 1  # SQLite INTEGER is signed 64-bit
INDEX_FILE = "index.json"
META_ID = 1


@dataclass(frozen=True, slots=True)
class SaveSummary:
    slug: str
    company_name: str
    scenario_id: str
    difficulty: str
    current_turn: int


# --- Paths and sessions --------------------------------------------------------------------


def save_path(save_dir: Path, slug: str) -> Path:
    if not SLUG_RE.match(slug):
        raise InvalidSaveNameError(
            f"save name {slug!r} must be 1-64 chars of a-z, 0-9, '-' or '_', starting with a-z/0-9"
        )
    return save_dir / f"{slug}{SAVE_SUFFIX}"


def existing_save_path(save_dir: Path, slug: str) -> Path:
    path = save_path(save_dir, slug)
    if not path.is_file():
        raise SaveNotFoundError(f"no save named {slug!r}")
    return path


@contextmanager
def open_session(path: Path) -> Iterator[Session]:
    """A session on one save file. The engine is disposed (file closed) on exit."""
    engine = make_engine(path)
    try:
        with make_sessionmaker(engine)() as session:
            yield session
    finally:
        engine.dispose()


# --- Creation -------------------------------------------------------------------------------


def create_save(
    name: str,
    seed: int,
    scenario: str,
    *,
    company_name: str,
    data: LoadedData,
    save_dir: Path,
    difficulty: str = DEFAULT_DIFFICULTY,
    founder: FounderSpec = DEFAULT_FOUNDER,
) -> Path:
    """Create `<save_dir>/<name>.tst.sqlite` at schema head with the turn-0 state."""
    path = save_path(save_dir, name)
    if path.exists():
        raise SaveExistsError(f"a save named {name!r} already exists")
    if isinstance(seed, bool) or not 0 <= seed <= MAX_STORED_SEED:
        raise InvalidSeedError(f"seed must be in 0..2**63-1, got {seed}")
    scenario_def = data.game_data.scenario(scenario)
    if scenario_def is None:
        raise UnknownScenarioError(f"unknown scenario {scenario!r}")
    state, entries = new_game(
        save_name=name,
        master_seed=seed,
        scenario=scenario_def,
        difficulty=difficulty,
        company_name=company_name,
        founder=founder,
        balance=data.balance,
        data=data.game_data,
    )

    save_dir.mkdir(parents=True, exist_ok=True)
    try:
        migrate.upgrade_new(path)
        with open_session(path) as session, session.begin():
            session.add(
                SaveMetaRow(
                    id=META_ID,
                    name=name,
                    master_seed=seed,
                    scenario_id=scenario_def.id,
                    difficulty=difficulty,
                    created_turn=state.turn,
                    current_turn=state.turn,
                    data_hashes=data.hashes,
                    schema_version=SCHEMA_VERSION,
                )
            )
            session.add_all(
                AccountRow(code=a.code, name=a.name, type=a.type) for a in data.game_data.accounts
            )
            session.add_all(company_to_row(c) for c in state.companies)
            session.flush()
            session.add_all(entry_to_row(e) for e in entries)
    except BaseException:
        for leftover in (
            path,
            path.with_name(path.name + "-wal"),
            path.with_name(path.name + "-shm"),
        ):
            leftover.unlink(missing_ok=True)
        raise
    refresh_index(save_dir)
    return path


# --- Reads ----------------------------------------------------------------------------------


def read_meta(session: Session) -> SaveMetaRow:
    meta = session.get(SaveMetaRow, META_ID)
    if meta is None:
        raise SaveNotFoundError("save file has no save_meta row")
    return meta


def load_state(session: Session) -> GameState:
    meta = read_meta(session)
    companies = list(session.scalars(select(CompanyRow)))
    return game_state_from_rows(meta, companies)


def ledger_balances(
    session: Session, through_turn: int | None = None
) -> dict[tuple[int, AccountCode], Cents]:
    """Balance per (company, account) over entries with turn <= through_turn (all if None).

    At the start of turn T no entries for T exist yet except turn-0 starting cash, so
    `ledger_balances(session, T)` is the opening balance for turn T and the closing balance
    once T has been played.
    """
    stmt = (
        select(
            LedgerEntryRow.company_id,
            LedgerLineRow.account_code,
            func.sum(LedgerLineRow.amount_cents),
        )
        .join(LedgerLineRow.entry)
        .group_by(LedgerEntryRow.company_id, LedgerLineRow.account_code)
        .order_by(LedgerEntryRow.company_id, LedgerLineRow.account_code)
    )
    if through_turn is not None:
        stmt = stmt.where(LedgerEntryRow.turn <= through_turn)
    return {(cid, acc): int(total) for cid, acc, total in session.execute(stmt)}


def recent_snapshots(
    session: Session, company_id: int, limit: int
) -> list[tuple[int, CompanySnapshot]]:
    """The last `limit` month-end snapshots for a company as (turn, snapshot), oldest first."""
    rows = session.scalars(
        select(TurnSnapshotRow)
        .where(TurnSnapshotRow.company_id == company_id)
        .order_by(TurnSnapshotRow.turn.desc())
        .limit(limit)
    ).all()
    return [(r.turn, company_snapshot_from_row(r)) for r in reversed(rows)]


def latest_snapshot(session: Session, company_id: int) -> CompanySnapshot | None:
    found = recent_snapshots(session, company_id, 1)
    return found[0][1] if found else None


@dataclass(frozen=True, slots=True)
class Overview:
    slug: str
    company_name: str
    scenario_id: str
    turn: int  # next turn to play
    date_label: str
    cash_cents: Cents
    monthly_burn_cents: Cents  # from the last month-end snapshot; 0 before the first turn
    runway_months: int | None
    history: list[tuple[int, CompanySnapshot]]  # last N snapshots, oldest first


def player_overview(session: Session, history: int) -> Overview:
    """What the player sees on the Overview screen and in `tst inspect`."""
    meta = read_meta(session)
    state = load_state(session)
    player = state.player
    cash = company_cash(ledger_balances(session), player.id)
    snaps = recent_snapshots(session, player.id, history)
    burn = snaps[-1][1].monthly_burn_cents if snaps else 0
    return Overview(
        slug=meta.name,
        company_name=player.name,
        scenario_id=meta.scenario_id,
        turn=state.turn,
        date_label=format_turn(state.turn),
        cash_cents=cash,
        monthly_burn_cents=burn,
        runway_months=runway_months(cash, burn),
        history=snaps,
    )


# --- Turns ----------------------------------------------------------------------------------


def apply_turn_result(session: Session, result: TurnResult, decisions: Decisions) -> None:
    """Write one turn's results. Must run inside the caller's transaction."""
    meta = read_meta(session)
    played = result.snapshot.turn
    if meta.current_turn != played:
        raise RuntimeError(f"save is at turn {meta.current_turn}, result is for turn {played}")

    rows = {r.id: r for r in session.scalars(select(CompanyRow))}
    for company in result.new_state.companies:
        row = rows.get(company.id)
        if row is None:
            session.add(company_to_row(company))
        else:
            update_company_row(row, company)

    player = result.new_state.player
    session.add(decisions_to_row(played, player.id, decisions))
    session.add_all(entry_to_row(e) for e in result.ledger_entries)
    session.add_all(snapshot_to_rows(result.snapshot))
    session.add_all(log_item_to_row(i) for i in result.log_items)
    meta.current_turn = result.new_state.turn
    session.flush()


def run_turn(save_path: Path, data: LoadedData, decisions: Decisions | None = None) -> TurnResult:
    """Play one turn in a single transaction; any exception rolls everything back."""
    decisions = decisions or Decisions()
    migrate.ensure_current(save_path)
    with open_session(save_path) as session, session.begin():
        meta = read_meta(session)
        if meta.data_hashes != data.hashes:
            log.warning("Data files changed since %s was created: %s", meta.name, data.hashes)
        state = load_state(session)
        balances = ledger_balances(session, state.turn)
        result = advance_turn(
            state,
            decisions,
            RngFactory(state.save_meta.master_seed),
            data.balance,
            data.game_data,
            balances,
        )
        apply_turn_result(session, result, decisions)

    committed = result.new_state.turn
    backup = data.balance.backup
    if committed % backup.every_n_turns == 0:
        periodic_backup(save_path, committed, backup.keep_periodic)
    refresh_index(save_path.parent)
    return result


# --- Save index (ADR-0004 section 1) --------------------------------------------------------


def summarize(path: Path) -> SaveSummary:
    with open_session(path) as session:
        meta = read_meta(session)
        player = load_state(session).player
        return SaveSummary(
            slug=slug_of(path),
            company_name=player.name,
            scenario_id=meta.scenario_id,
            difficulty=meta.difficulty,
            current_turn=meta.current_turn,
        )


def refresh_index(save_dir: Path) -> list[SaveSummary]:
    """Rebuild saves/index.json from the save files. The files are the source of truth."""
    summaries = []
    for path in sorted(save_dir.glob(f"*{SAVE_SUFFIX}")):
        try:
            summaries.append(summarize(path))
        except Exception:
            log.exception("Skipping unreadable save %s", path.name)
    (save_dir / INDEX_FILE).write_text(
        json.dumps([asdict(s) for s in summaries], indent=2) + "\n", encoding="utf-8"
    )
    return summaries


def list_saves(save_dir: Path) -> list[SaveSummary]:
    index = save_dir / INDEX_FILE
    if not save_dir.is_dir():
        return []
    try:
        return [SaveSummary(**item) for item in json.loads(index.read_text(encoding="utf-8"))]
    except (OSError, ValueError, TypeError):
        return refresh_index(save_dir)
