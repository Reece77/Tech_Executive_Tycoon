"""Save files: create, load, and run turns in one transaction each (ADR-0004)."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tst.db import migrate
from tst.db.backup import SAVE_SUFFIX, periodic_backup, slug_of
from tst.db.inbox import inbox_rows
from tst.db.mappers import (
    company_snapshot_from_row,
    decisions_to_row,
    entry_to_row,
    log_item_to_row,
    snapshot_to_rows,
)
from tst.db.models import (
    SCHEMA_VERSION,
    AccountRow,
    DecisionLogRow,
    LedgerEntryRow,
    LedgerLineRow,
    PersonMoraleLogRow,
    SaveMetaRow,
    TurnSnapshotRow,
)
from tst.db.session import make_engine, make_sessionmaker
from tst.db.state_io import META_ID, load_state, read_meta, sync_state
from tst.loader import LoadedData
from tst.sim.actions import (
    Action,
    ActionResult,
    action_from_payload,
    action_payload,
    apply_action,
)
from tst.sim.calendar import format_turn
from tst.sim.data_models import DEFAULT_DIFFICULTY, Balance
from tst.sim.decisions import Decisions
from tst.sim.errors import (
    InvalidSaveNameError,
    InvalidSeedError,
    ReplayMismatchError,
    SaveExistsError,
    SaveNotFoundError,
    UnknownScenarioError,
)
from tst.sim.hiring.phases import monthly_costs
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
NEW_GAME_KIND = "new_game"  # decision_log row holding the new-game choices (for replay)
PLAYER_SOURCE = "player"  # decision_log.source of player actions (re-applied by replay)
DELEGATE_SOURCE = "delegate"  # delegate actions: recomputed by replay, never re-applied


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
    mission: tuple[str, ...] | None = None,
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
        mission=mission,
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
                    next_person_id=state.next_ids.person,
                    next_search_id=state.next_ids.search,
                    next_offer_id=state.next_ids.offer,
                    next_employment_id=state.next_ids.employment,
                    next_unit_id=state.next_ids.unit,
                    next_plan_id=state.next_ids.plan,
                )
            )
            session.add_all(
                AccountRow(code=a.code, name=a.name, type=a.type) for a in data.game_data.accounts
            )
            session.flush()
            sync_state(session, None, state)
            session.add_all(entry_to_row(e) for e in entries)
            session.add(
                DecisionLogRow(
                    turn=state.turn,
                    company_id=state.player.id,
                    kind=NEW_GAME_KIND,
                    payload=new_game_payload(
                        company_name, scenario_def.id, difficulty, founder, state.player.mission
                    ),
                    seq=0,
                )
            )
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


def costs_for_turn(session: Session, company_id: int, turn: int) -> list[tuple[str, str, Cents]]:
    """(account code, account name, amount) of expenses posted in one turn, largest first."""
    stmt = (
        select(
            LedgerLineRow.account_code,
            AccountRow.name,
            func.sum(LedgerLineRow.amount_cents),
        )
        .join(LedgerLineRow.entry)
        .join(AccountRow, AccountRow.code == LedgerLineRow.account_code)
        .where(
            LedgerEntryRow.company_id == company_id,
            LedgerEntryRow.turn == turn,
            AccountRow.type == "expense",
        )
        .group_by(LedgerLineRow.account_code, AccountRow.name)
    )
    rows = [(code, name, int(total)) for code, name, total in session.execute(stmt)]
    return sorted(rows, key=lambda r: (-r[2], r[0]))


def expenses_by_memo(session: Session, company_id: int, turn: int) -> list[tuple[str, str, Cents]]:
    """(memo label, account code, amount) of expenses posted in one turn, in posting order.

    The label is the memo up to its first colon ("Severance: Ada Byron" -> "Severance").
    """
    stmt = (
        select(LedgerEntryRow.memo, LedgerLineRow.account_code, LedgerLineRow.amount_cents)
        .join(LedgerLineRow.entry)
        .join(AccountRow, AccountRow.code == LedgerLineRow.account_code)
        .where(
            LedgerEntryRow.company_id == company_id,
            LedgerEntryRow.turn == turn,
            AccountRow.type == "expense",
        )
        .order_by(LedgerEntryRow.id, LedgerLineRow.id)
    )
    return [(memo.split(":")[0], code, int(amount)) for memo, code, amount in session.execute(stmt)]


@dataclass(frozen=True, slots=True)
class Overview:
    slug: str
    company_name: str
    scenario_id: str
    turn: int  # next turn to play
    date_label: str
    cash_cents: Cents
    monthly_burn_cents: Cents  # from the last month-end snapshot; 0 before the first turn
    runway_months: int | None  # at this month's projected phase-6 costs (M1c decision)
    history: list[tuple[int, CompanySnapshot]]  # last N snapshots, oldest first


def player_overview(session: Session, history: int, balance: Balance) -> Overview:
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
        runway_months=runway_months(
            cash, sum(amount for _, _, amount in monthly_costs(state, player.id, balance))
        ),
        history=snaps,
    )


# --- Turns ----------------------------------------------------------------------------------


def apply_turn_result(
    session: Session,
    result: TurnResult,
    decisions: Decisions,
    before: GameState,
    data: LoadedData,
) -> None:
    """Write one turn's results. Must run inside the caller's transaction.

    `before` is the state the turn started from; only the differences are written.
    """
    meta = read_meta(session)
    played = result.snapshot.turn
    if meta.current_turn != played:
        raise RuntimeError(f"save is at turn {meta.current_turn}, result is for turn {played}")

    sync_state(session, before, result.new_state)
    staff = {e.person_id for e in result.new_state.employments if e.counts_as_staff}
    session.add_all(
        PersonMoraleLogRow(person_id=ps.person_id, turn=played, morale=ps.morale)
        for ps in result.new_state.person_states
        if ps.morale is not None and ps.person_id in staff
    )

    player = result.new_state.player
    session.add(decisions_to_row(played, player.id, decisions))
    first = next_action_seq(session, played)
    session.add_all(
        DecisionLogRow(
            turn=played,
            company_id=company_id,
            kind=action.kind,
            payload=action_payload(action),
            seq=first + i,
            source=DELEGATE_SOURCE,
            actor_id=action.actor_id,
        )
        for i, (company_id, action) in enumerate(result.delegate_actions)
    )
    session.add_all(entry_to_row(e) for e in result.ledger_entries)
    session.add_all(snapshot_to_rows(result.snapshot))
    session.add_all(log_item_to_row(i) for i in result.log_items)
    session.add_all(
        inbox_rows(result.log_items, result.new_state.player.id, data.game_data.inbox_templates)
    )
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
        apply_turn_result(session, result, decisions, state, data)

    committed = result.new_state.turn
    backup = data.balance.backup
    if committed % backup.every_n_turns == 0:
        periodic_backup(save_path, committed, backup.keep_periodic)
    refresh_index(save_path.parent)
    return result


# --- Player actions (ADR-0014) --------------------------------------------------------------


def next_action_seq(session: Session, turn: int) -> int:
    """1, 2, 3... for the actions of one turn (decision_log.seq)."""
    current = session.scalar(
        select(func.max(DecisionLogRow.seq)).where(
            DecisionLogRow.turn == turn, DecisionLogRow.kind != NEW_GAME_KIND
        )
    )
    return (current or 0) + 1


def run_action(save_path: Path, data: LoadedData, action: Action) -> ActionResult:
    """Apply one player action in its own short transaction and log it to decision_log."""
    migrate.ensure_current(save_path)
    with open_session(save_path) as session, session.begin():
        state = load_state(session)
        balances = ledger_balances(session, state.turn)
        seq = next_action_seq(session, state.turn)
        result = apply_action(
            state,
            action,
            RngFactory(state.save_meta.master_seed),
            data.balance,
            data.game_data,
            balances,
            seq=seq,
        )
        sync_state(session, state, result.new_state)
        session.add_all(entry_to_row(e) for e in result.ledger_entries)
        session.add_all(log_item_to_row(i) for i in result.log_items)
        session.add_all(
            inbox_rows(result.log_items, state.player.id, data.game_data.inbox_templates)
        )
        employment = state.employment_of(action.actor_id)
        company_id = employment.company_id if employment else state.player.id
        session.add(
            DecisionLogRow(
                turn=state.turn,
                company_id=company_id,
                kind=action.kind,
                payload=action_payload(action),
                seq=seq,
                source=PLAYER_SOURCE,
                actor_id=action.actor_id,
            )
        )
    return result


def new_game_payload(
    company_name: str,
    scenario: str,
    difficulty: str,
    founder: FounderSpec,
    mission: tuple[str, ...],
) -> dict[str, Any]:
    spec = asdict(founder)
    spec["allocation"] = None if founder.allocation is None else dict(founder.allocation)
    spec["interests"] = None if founder.interests is None else list(founder.interests)
    return {
        "company_name": company_name,
        "scenario": scenario,
        "difficulty": difficulty,
        "founder": spec,
        "mission": list(mission),
    }


def replay_save(source: Path, save_dir: Path, name: str, data: LoadedData) -> Path:
    """Rebuild a save from its seed, new-game choices, logged actions and turns (ADR-0014).

    Player actions are re-applied. Delegate actions are not: each turn recomputes them from
    the plans in state, and they must equal the logged ones (ADR-0015), else
    ReplayMismatchError.
    """
    with open_session(source) as session:
        meta = read_meta(session)
        seed, target_turn = meta.master_seed, meta.current_turn
        start = session.scalars(
            select(DecisionLogRow).where(DecisionLogRow.kind == NEW_GAME_KIND)
        ).one()
        logged = session.scalars(
            select(DecisionLogRow)
            .where(DecisionLogRow.seq.is_not(None), DecisionLogRow.kind != NEW_GAME_KIND)
            .order_by(DecisionLogRow.turn, DecisionLogRow.seq)
        ).all()
        actions = [
            (row.turn, action_from_payload(row.payload))
            for row in logged
            if row.source == PLAYER_SOURCE
        ]
        delegated: dict[int, list[tuple[int, Action]]] = {}
        for row in logged:
            if row.source == DELEGATE_SOURCE:
                delegated.setdefault(row.turn, []).append(
                    (row.company_id, action_from_payload(row.payload))
                )
    setup = start.payload
    founder = dict(setup["founder"])
    if founder.get("interests") is not None:
        founder["interests"] = tuple(founder["interests"])
    path = create_save(
        name,
        seed,
        setup["scenario"],
        company_name=setup["company_name"],
        data=data,
        save_dir=save_dir,
        difficulty=setup["difficulty"],
        founder=FounderSpec(**founder),
        mission=tuple(setup["mission"]),
    )
    for turn in range(target_turn + 1):
        for _, action in (a for a in actions if a[0] == turn):
            run_action(path, data, action)
        if turn < target_turn:
            result = run_turn(path, data)
            if list(result.delegate_actions) != delegated.get(turn, []):
                raise ReplayMismatchError(
                    f"turn {turn}: recomputed delegate actions differ from the logged ones"
                )
    return path


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
    """Rebuild saves/index.json from the save files. The files are the source of truth.

    Older saves are upgraded first (after a pre-migration backup, ADR-0004). A save that
    cannot be upgraded or read is skipped with a one-line warning, not a traceback.
    """
    summaries = []
    for path in sorted(save_dir.glob(f"*{SAVE_SUFFIX}")):
        slug = slug_of(path)
        try:
            migrate.ensure_current(path)
        except Exception as exc:
            log.warning("Skipping save %s: needs upgrade (%s)", slug, type(exc).__name__)
            continue
        try:
            summaries.append(summarize(path))
        except Exception as exc:
            log.warning("Skipping save %s: unreadable (%s)", slug, type(exc).__name__)
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
