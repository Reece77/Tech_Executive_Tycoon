"""Save files: create, load, and run turns in one transaction each (ADR-0004)."""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from tst.db import inbox, migrate
from tst.db.backup import SAVE_SUFFIX, periodic_backup, slug_of
from tst.db.events import has_pending, write_pending
from tst.db.inbox import inbox_rows
from tst.db.mappers import (
    company_snapshot_from_row,
    decisions_to_row,
    log_item_to_row,
    product_month_from_row,
    product_month_to_row,
    snapshot_to_rows,
)
from tst.db.models import (
    SCHEMA_VERSION,
    AccountRow,
    CompanyRow,
    DecisionLogRow,
    DivisionMonthRow,
    InboxItemRow,
    LedgerEntryRow,
    LedgerLineRow,
    LLMTextRow,
    PersonMoraleLogRow,
    PersonRatingLogRow,
    PersonRow,
    ProductMonthRow,
    SaveMetaRow,
    TurnSnapshotRow,
)
from tst.db.session import make_sessionmaker, shared_engine
from tst.db.state_io import (
    META_ID,
    has_table,
    insert_entries,
    insert_rows,
    live_view,
    load_state,
    read_meta,
    sync_state,
)
from tst.llm.base import LLMAdapter
from tst.loader import LoadedData
from tst.sim.actions import (
    Action,
    ActionResult,
    action_from_payload,
    action_payload,
    apply_action,
)
from tst.sim.calendar import format_turn
from tst.sim.data_models import DEFAULT_DIFFICULTY
from tst.sim.decisions import Decisions
from tst.sim.errors import (
    InvalidSaveNameError,
    InvalidSeedError,
    ReplayMismatchError,
    SaveBusyError,
    SaveExistsError,
    SaveNotFoundError,
    UnknownScenarioError,
    UpgradeNeededError,
)
from tst.sim.finance.statements import cash_before_financing, profit_and_loss, projected_runway
from tst.sim.ledger import AccountCode, apply_entries
from tst.sim.modes.continue_until import MAX_MONTHS, StopReason, needs_player
from tst.sim.modes.world import ModeSpec, start_mode
from tst.sim.money import Cents
from tst.sim.people.founder import FounderSpec
from tst.sim.people.reveal import shown_rating
from tst.sim.products.models import ProductMonth
from tst.sim.rivals.models import RivalMove
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.snapshot import CompanySnapshot, DivisionMonth
from tst.sim.state import GameState, company_cash
from tst.sim.turn import TurnResult, advance_turn

log = logging.getLogger(__name__)

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
MAX_STORED_SEED = 2**63 - 1  # SQLite INTEGER is signed 64-bit
INDEX_FILE = "index.json"
NEW_GAME_KIND = "new_game"  # decision_log row holding the new-game choices (for replay)
PLAYER_SOURCE = "player"  # decision_log.source of player actions (re-applied by replay)
DELEGATE_SOURCE = "delegate"  # delegate actions: recomputed by replay, never re-applied
RIVAL_SOURCE = "rival"  # rival moves (M5, 15.3): recomputed by replay, never re-applied


def rival_move_payload(move: RivalMove) -> dict[str, Any]:
    return {
        "id": move.id,
        "action": move.action,
        "product_id": move.product_id,
        "segment": move.segment,
        "detail": move.detail,
    }


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
    """The path of an existing save, upgraded to the latest migration first (as the save
    index does), so no route reads a save with an old schema (M6 sub-task 0)."""
    path = save_path(save_dir, slug)
    if not path.is_file():
        raise SaveNotFoundError(f"no save named {slug!r}")
    if migrate.is_current(path):
        return path
    lock = _lock(path)
    if not lock.acquire(blocking=False):
        raise SaveBusyError(BUSY_MESSAGE)
    try:
        migrate.ensure_current(path)
    except Exception as exc:
        log.warning("Save %s needs an upgrade that failed: %s", slug, exc)
        raise UpgradeNeededError(
            f"save {slug!r} was made by an older version and could not be upgraded"
            f" ({type(exc).__name__}); its pre-upgrade backup is in the backups folder"
        ) from exc
    finally:
        lock.release()
    return path


@contextmanager
def open_session(path: Path) -> Iterator[Session]:
    """A session on one save file; its connection closes on exit (the engine is shared)."""
    with make_sessionmaker(shared_engine(path))() as session:
        yield session


_LOCKS: dict[Path, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
BUSY_MESSAGE = "This save is busy with another change; try again when it finishes."


def _lock(path: Path) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(path.resolve(), threading.Lock())


# Saves reserved by a long job (M7b Holiday): each month is its own write transaction, and
# any other write to the save between them is refused as busy. Keyed by resolved path; the
# value is the job's token, which the job's thread sets in `_HOLDER` to write.
_HOLDS: dict[str, object] = {}
_HOLDER: ContextVar[object | None] = ContextVar("tst_save_holder", default=None)


def reserve(path: Path) -> object:
    """Reserve a save for a job; SaveBusyError if a write or another job has it."""
    key = str(path.resolve())
    with _LOCKS_GUARD:
        if key in _HOLDS or _LOCKS.get(path.resolve(), threading.Lock()).locked():
            raise SaveBusyError(BUSY_MESSAGE)
        token = object()
        _HOLDS[key] = token
        return token


def release(path: Path, token: object) -> None:
    with _LOCKS_GUARD:
        if _HOLDS.get(str(path.resolve())) is token:
            del _HOLDS[str(path.resolve())]


@contextmanager
def holding(token: object) -> Iterator[None]:
    """Write as the job that reserved the save (in the job's own thread)."""
    reset = _HOLDER.set(token)
    try:
        yield
    finally:
        _HOLDER.reset(reset)


def is_reserved(path: Path) -> bool:
    with _LOCKS_GUARD:
        return str(path.resolve()) in _HOLDS


def _check_reserved(path: Path) -> None:
    with _LOCKS_GUARD:
        held = _HOLDS.get(str(path.resolve()))
    if held is not None and held is not _HOLDER.get():
        raise SaveBusyError(BUSY_MESSAGE)


def is_locked_error(exc: BaseException) -> bool:
    """SQLite's answer when another connection (another process) holds the write lock."""
    return isinstance(exc, OperationalError) and "locked" in str(exc).lower()


def _stamp(path: Path) -> tuple[int, int, int, int]:
    """The save file and its WAL as they are on disk: any commit changes one of them. An
    empty WAL counts as none: any connection creates one, and only a commit writes to it."""
    main = path.stat()
    try:
        w = path.with_name(path.name + "-wal").stat()
    except FileNotFoundError:
        w = None
    if w is None or w.st_size == 0:
        return (main.st_size, main.st_mtime_ns, -1, -1)
    return (main.st_size, main.st_mtime_ns, w.st_size, w.st_mtime_ns)


Balances = dict[tuple[int, AccountCode], Cents]
_LAST: dict[str, tuple[tuple[int, int, int, int], GameState, Balances | None]] = {}
CACHED_STATE = "tst_cached_state"
CACHED_BALANCES = "tst_cached_balances"


def remember(path: Path, state: GameState, balances: Balances | None = None) -> None:
    """Keep the state just written to a save (after its session closed), as `load_state`
    would read it back (M6 sub-task 0: a turn or action then skips a full load), and the
    ledger balances through its turn when the writer knows them (M7a: summing the whole
    ledger cost about 10 ms a call by turn 120, and grows every month).

    Only `write_session` calls this, while it still holds the save's write lock, so no other
    write can land between the commit and the stamp (M8r, Codex review 1 finding 1)."""
    _LAST[str(path.resolve())] = (_stamp(path), live_view(state), balances)


PUBLISH = "tst_publish"


def publish(session: Session, state: GameState, balances: Balances | None = None) -> None:
    """Ask `write_session` to remember `state` (and its balances) once this write commits,
    before it releases the lock. A write that publishes nothing clears what was remembered."""
    session.info[PUBLISH] = (state, balances)


def _recall(path: Path) -> tuple[GameState, Balances | None] | None:
    entry = _LAST.get(str(path.resolve()))
    if entry is None or not path.exists() or entry[0] != _stamp(path):
        return None
    return entry[1], entry[2]


def _cache(session: Session, recalled: tuple[GameState, Balances | None] | None) -> None:
    session.info[CACHED_STATE] = recalled[0] if recalled else None
    session.info[CACHED_BALANCES] = recalled[1] if recalled else None


def load_current(session: Session) -> GameState:
    """The save's state: the one this process last wrote if the file has not changed since,
    else read from the database. TST_STATE_CACHE_CHECK=1 reads it anyway and compares."""
    cached = session.info.get(CACHED_STATE)
    if cached is None:
        return load_state(session)
    if os.environ.get("TST_STATE_CACHE_CHECK") == "1":
        fresh = load_state(session)
        if fresh != cached:
            raise RuntimeError("the remembered state differs from the save")
    return cast(GameState, cached)


def current_balances(session: Session, turn: int) -> Balances:
    """`ledger_balances(session, turn)` for the save's current turn: the balances remembered
    with the state when they are for that turn, else summed from the ledger.
    TST_STATE_CACHE_CHECK=1 sums anyway and compares."""
    cached = session.info.get(CACHED_BALANCES)
    state = session.info.get(CACHED_STATE)
    if cached is None or state is None or state.turn != turn:
        return ledger_balances(session, turn)
    check = os.environ.get("TST_STATE_CACHE_CHECK") == "1"
    if check and ledger_balances(session, turn) != cached:
        raise RuntimeError("the remembered ledger balances differ from the save")
    return dict(cached)


_READ_LOCKS: dict[Path, threading.Lock] = {}
LOADED_STATE = "tst_loaded_state"


@contextmanager
def read_session(path: Path) -> Iterator[Session]:
    """A session for a read-only route. Reads of one save take turns in this process, and the
    file's stamp is taken only while none of them has a connection open (a reader's
    connection creates the WAL and its close removes it), so `read_state` can reuse the state
    this process remembers. A screen's parallel requests then share one load instead of each
    making their own (M6: seven concurrent loads took about 6 s each)."""
    with _LOCKS_GUARD:
        lock = _READ_LOCKS.setdefault(path.resolve(), threading.Lock())
    with lock:
        before = _stamp(path)
        cached = _recall(path)
        with open_session(path) as session:
            _cache(session, cached)
            yield session
            loaded = session.info.get(LOADED_STATE)
        if cached is None and loaded is not None and _stamp(path) == before:
            _LAST[str(path.resolve())] = (before, loaded, None)  # no commit landed meanwhile


def read_state(session: Session) -> GameState:
    """The save's state on a read: the remembered one when `read_session` found it current
    (TST_STATE_CACHE_CHECK=1 compares), else loaded, for `read_session` to remember."""
    if session.info.get(CACHED_STATE) is not None:
        return load_current(session)
    if (loaded := session.info.get(LOADED_STATE)) is not None:
        return cast(GameState, loaded)  # a route that reads the state twice loads it once
    state = load_state(session)
    session.info[LOADED_STATE] = state
    return state


@contextmanager
def write_session(path: Path) -> Iterator[Session]:
    """A session in one write transaction on a save. A second write to the same save while
    one is in progress raises SaveBusyError at once instead of waiting or failing deep inside
    SQLite (M6 sub-task 0). A save reserved by a job (Holiday) is busy to every other writer."""
    _check_reserved(path)
    lock = _lock(path)
    if not lock.acquire(blocking=False):
        raise SaveBusyError(BUSY_MESSAGE)
    try:
        cached = _recall(path)  # before the connection opens (it can create the WAL file)
        with open_session(path) as session, session.begin():
            _cache(session, cached)
            yield session
            published = session.info.pop(PUBLISH, None)
        # Committed and closed, and the lock is still ours: publish now or forget (M8r).
        if published is not None:
            remember(path, *published)
        else:
            _LAST.pop(str(path.resolve()), None)
    except OperationalError as exc:
        if is_locked_error(exc):
            raise SaveBusyError(BUSY_MESSAGE) from exc
        raise
    finally:
        lock.release()


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
    hq_city: str | None = None,
    mode: ModeSpec | None = None,
) -> Path:
    """Create `<save_dir>/<name>.tst.sqlite` at schema head with the turn-0 state.
    `hq_city` (M9, 19.1): None for geo.default_hq_city. `mode` (M15b, 30.2-30.3): a Sandbox
    or scenario start, the world built to its start month."""
    path = save_path(save_dir, name)
    if path.exists():
        raise SaveExistsError(f"a save named {name!r} already exists")
    if isinstance(seed, bool) or not 0 <= seed <= MAX_STORED_SEED:
        raise InvalidSeedError(f"seed must be in 0..2**63-1, got {seed}")
    if mode is not None and mode.kind == "scenario" and mode.scenario is not None:
        from tst.sim.modes.scenarios import scenario as historical

        scenario = historical(data.game_data, mode.scenario).background  # its start (30.3)
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
        hq_city=hq_city,
    )
    if mode is not None:
        state, entries = start_mode(
            state, entries, mode, founder, RngFactory(seed), data.balance, data.game_data
        )

    save_dir.mkdir(parents=True, exist_ok=True)
    try:
        migrate.upgrade_new(path)
        with write_session(path) as session:
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
                    next_product_id=state.next_ids.product,
                )
            )
            session.add_all(
                AccountRow(code=a.code, name=a.name, type=a.type) for a in data.game_data.accounts
            )
            session.flush()
            sync_state(session, None, state)
            insert_entries(session, entries)
            session.add(
                DecisionLogRow(
                    turn=state.turn,
                    company_id=state.player.id,
                    kind=NEW_GAME_KIND,
                    payload=new_game_payload(
                        company_name,
                        scenario_def.id,
                        difficulty,
                        founder,
                        state.player.mission,
                        state.player.hq_city,
                        mode,
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
    update_index(path)
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


def ledger_lines(session: Session, company_id: int) -> list[tuple[int, str, Cents]]:
    """Every ledger line of a company as (turn, account, amount): the statements' input."""
    stmt = (
        select(LedgerEntryRow.turn, LedgerLineRow.account_code, LedgerLineRow.amount_cents)
        .join(LedgerLineRow.entry)
        .where(LedgerEntryRow.company_id == company_id)
        .order_by(LedgerEntryRow.id, LedgerLineRow.id)
    )
    return [(int(t), str(a), int(c)) for t, a, c in session.execute(stmt)]


def division_lines(session: Session, company_id: int) -> list[tuple[int, str, Cents, int | None]]:
    """Every ledger line of a company as (turn, account, amount, division id) (M8, 18.1)."""
    stmt = (
        select(
            LedgerEntryRow.turn,
            LedgerLineRow.account_code,
            LedgerLineRow.amount_cents,
            LedgerLineRow.division_id,
        )
        .join(LedgerLineRow.entry)
        .where(LedgerEntryRow.company_id == company_id)
        .order_by(LedgerEntryRow.id, LedgerLineRow.id)
    )
    return [
        (int(t), str(a), int(c), None if d is None else int(d))
        for t, a, c, d in session.execute(stmt)
    ]


REPORTS_READ = 24  # tunable-exempt: enough recent reports to find each seat's latest


def exec_reports(session: Session, company_id: int) -> list[InboxItemRow]:
    """Executives' quarterly reports (M10c, 24.3), newest first."""
    return list(
        session.scalars(
            select(InboxItemRow)
            .where(InboxItemRow.company_id == company_id, InboxItemRow.template == "exec_report")
            .order_by(InboxItemRow.turn.desc(), InboxItemRow.id.desc())
            .limit(REPORTS_READ)
        )
    )


def division_months(session: Session, company_id: int) -> list[DivisionMonth]:
    """Headcount per division at each month's payroll (M8, 18.1)."""
    rows = session.scalars(
        select(DivisionMonthRow)
        .where(DivisionMonthRow.company_id == company_id)
        .order_by(DivisionMonthRow.turn, DivisionMonthRow.id)
    )
    return [
        DivisionMonth(r.turn, r.company_id, r.division_id, r.name, r.headcount, r.embedded)
        for r in rows
    ]


def person_names(session: Session, person_ids: Iterable[int]) -> dict[int, str]:
    """First and last names by id, including people who have left (not in the live state)."""
    ids = sorted(set(person_ids))
    if not ids:
        return {}
    rows = session.execute(
        select(PersonRow.id, PersonRow.first_name, PersonRow.last_name).where(PersonRow.id.in_(ids))
    )
    return {int(i): f"{first} {last}" for i, first, last in rows}


def product_history(session: Session, product_id: int, since_turn: int) -> list[ProductMonth]:
    """A product's month-end rows from `since_turn` on, oldest first, by segment."""
    rows = session.scalars(
        select(ProductMonthRow)
        .where(ProductMonthRow.product_id == product_id, ProductMonthRow.turn >= since_turn)
        .order_by(ProductMonthRow.turn, ProductMonthRow.segment)
    )
    return [product_month_from_row(r) for r in rows]


@dataclass(frozen=True, slots=True)
class Overview:
    slug: str
    company_name: str
    scenario_id: str
    turn: int  # next turn to play
    date_label: str
    cash_cents: Cents
    monthly_burn_cents: Cents  # net cash used before financing last month; 0 before it
    runway_months: int | None  # at this month's projected phase-6 costs (M1c decision)
    history: list[tuple[int, CompanySnapshot]]  # last N snapshots, oldest first


def player_overview(session: Session, history: int, data: LoadedData) -> Overview:
    """What the player sees on the Overview screen and in `tst inspect`."""
    meta = read_meta(session)
    state = read_state(session)
    player = state.player
    cash = company_cash(ledger_balances(session), player.id)
    snaps = recent_snapshots(session, player.id, history)
    # Net cash used before financing over the last month played (14.1; M8r).
    burn = snaps[-1][1].monthly_burn_cents if snaps else 0
    return Overview(
        slug=meta.name,
        company_name=player.name,
        scenario_id=meta.scenario_id,
        turn=state.turn,
        date_label=format_turn(state.turn),
        cash_cents=cash,
        monthly_burn_cents=burn,
        # Cash over this month's projected net burn; None = profitable (formulas.md 14.1).
        runway_months=projected_runway(state, player.id, cash, data.balance, data.game_data),
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
    insert_rows(
        session,
        (
            PersonMoraleLogRow(person_id=ps.person_id, turn=played, morale=ps.morale)
            for ps in result.new_state.person_states
            if ps.morale is not None and ps.person_id in staff
        ),
    )

    player = result.new_state.player
    insert_rows(session, rating_rows(result.new_state, played, data))  # M7b History
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
    first += len(result.delegate_actions)
    session.add_all(
        DecisionLogRow(
            turn=played,
            company_id=move.company_id,
            kind=f"rival_{move.action}",
            payload=rival_move_payload(move),
            seq=first + i,
            source=RIVAL_SOURCE,
        )
        for i, move in enumerate(result.rival_moves)
    )
    if result.text_requests and has_table(session, LLMTextRow):  # M6 (16.8)
        session.add_all(
            LLMTextRow(
                company_id=t.company_id, turn=t.turn, kind=t.kind, ref_id=t.ref_id, status="pending"
            )
            for t in result.text_requests
        )
    insert_entries(session, result.ledger_entries)
    insert_rows(
        session,
        [
            *snapshot_to_rows(result.snapshot),
            *(product_month_to_row(m) for m in result.product_months),
            *(DivisionMonthRow(**asdict(m)) for m in result.division_months),  # M8
            *(log_item_to_row(i) for i in result.log_items),
            *inbox_rows(
                result.log_items,
                result.new_state.player.id,
                data.game_data.inbox_templates,
                frozenset(h.company_id for h in result.new_state.holdings),  # M16
            ),
        ],
    )
    meta.current_turn = result.new_state.turn
    session.flush()


def rating_rows(state: GameState, turn: int, data: LoadedData) -> list[PersonRatingLogRow]:
    """Each player employee's shown rating at this month end (M7b, 17.2): the founder is
    not rated; someone with no role or no reveal record is skipped."""
    rows = []
    player = state.player.id
    for e in state.staff(player):
        person = state.person(e.person_id)
        reveal = state.reveal(player, e.person_id)
        if person.is_founder or reveal is None:
            continue
        role = data.game_data.role(e.role)
        rating = shown_rating(person, reveal, role.primary)
        rows.append(PersonRatingLogRow(person_id=e.person_id, turn=turn, rating=rating))
    return rows


def _month_lines(session: Session, turn: int) -> dict[int, list[tuple[int, str, Cents]]]:
    """`turn`'s ledger lines posted before the turn runs (actions such as a paid event)."""
    rows = session.execute(
        select(LedgerEntryRow.company_id, LedgerLineRow.account_code, LedgerLineRow.amount_cents)
        .join(LedgerLineRow.entry)
        .where(LedgerEntryRow.turn == turn)
    ).all()
    lines: dict[int, list[tuple[int, str, Cents]]] = {}
    for company, account, amount in rows:
        lines.setdefault(int(company), []).append((turn, str(account), int(amount)))
    return lines


def month_so_far(
    session: Session, turn: int, data: LoadedData
) -> tuple[dict[int, Cents], dict[int, Cents]]:
    """(cash flow before financing, operating result) of `turn`'s entries before the turn
    runs, per company, from one ledger read: burn (14.1; M8r) and the debt history's
    operating month (20.3; M10r: a lender's fee is interest, below operating profit)."""
    types = {a.code: a.type for a in data.game_data.accounts}
    lines = _month_lines(session, turn)
    flow = {c: cash_before_financing(ls, types) for c, ls in lines.items()}
    operating = {
        c: profit_and_loss(ls, types, turn, turn).operating_result for c, ls in lines.items()
    }
    return flow, operating


def month_flow_so_far(session: Session, turn: int, data: LoadedData) -> dict[int, Cents]:
    """Cash from operating and investing that `turn`'s entries moved before the turn runs
    (actions such as a paid event), per company: burn covers the whole month (14.1; M8r)."""
    return month_so_far(session, turn, data)[0]


def month_operating_so_far(session: Session, turn: int, data: LoadedData) -> dict[int, Cents]:
    """The operating result (P&L by account) of `turn`'s entries before the turn runs, per
    company: a lender's fee is interest, below operating profit (14.1, 20.3; M10r)."""
    return month_so_far(session, turn, data)[1]


class _PendingEvents(Exception):
    """Events or texts from an earlier turn are still unwritten (the service did not finish)."""


def _play_turn(
    save_path: Path, data: LoadedData, decisions: Decisions, block_major: bool = False
) -> TurnResult:
    with write_session(save_path) as session:
        if has_pending(session):
            raise _PendingEvents
        meta = read_meta(session)
        if meta.data_hashes != data.hashes:
            log.warning("Data files changed since %s was created: %s", meta.name, data.hashes)
        state = load_current(session)
        balances = current_balances(session, state.turn)
        prior_flow, prior_operating = month_so_far(session, state.turn, data)
        result = advance_turn(
            state,
            decisions,
            RngFactory(state.save_meta.master_seed),
            data.balance,
            data.game_data,
            balances,
            prior_flow=prior_flow,
            prior_operating=prior_operating,
            block_major=block_major,
        )
        apply_turn_result(session, result, decisions, state, data)
        _tidy_inbox(session, state, result.new_state, data)
        publish(session, result.new_state, apply_entries(balances, result.ledger_entries))
    return result


def _tidy_inbox(session: Session, before: GameState, after: GameState, data: LoadedData) -> None:
    """Answered events' items archive themselves; at month end (`after` a new turn) read,
    unbookmarked items older than inbox.auto_archive_months archive too (23.1, M10b)."""
    player = after.player.id
    still_open = {e.id for e in after.open_events(player)}
    answered = [e.id for e in before.open_events(player) if e.id not in still_open]
    inbox.archive_events(session, player, answered)
    if after.turn > before.turn:
        inbox.auto_archive(session, player, after.turn, data.balance.inbox.auto_archive_months)


def run_turn(
    save_path: Path,
    data: LoadedData,
    decisions: Decisions | None = None,
    *,
    adapter: LLMAdapter | None = None,
    events_from: Path | None = None,
    block_major: bool = False,
) -> TurnResult:
    """Play one turn in a single transaction; any exception rolls everything back. Then the
    event service writes next month's events and texts in a transaction of its own (M6):
    `adapter` overrides the settings' adapter; replay passes `events_from`, the original save,
    so no adapter is called. `block_major`: the player's own Continue, which open major
    events block (23.1, M10b); Holiday and scripts answer them with their first choice."""
    decisions = decisions or Decisions()
    migrate.ensure_current(save_path)
    # The turn and its event writing hold the save together (M8r, Codex review 1 finding 2):
    # another write between them is refused, so `save_busy` only ever comes before the month
    # commits. A Holiday already holds the save for all its months.
    key = str(save_path.resolve())
    with _LOCKS_GUARD:
        held = _HOLDS.get(key) is not None and _HOLDS.get(key) is _HOLDER.get()
    token = None if held else reserve(save_path)
    try:
        with holding(token) if token is not None else nullcontext():
            try:
                result = _play_turn(save_path, data, decisions, block_major)
            except _PendingEvents:  # an earlier write did not finish: write them, then play
                write_pending(save_path, data, adapter=adapter, copy_from=events_from)
                result = _play_turn(save_path, data, decisions, block_major)
            _after_commit(save_path, data, result, adapter, events_from)
    finally:
        if token is not None:
            release(save_path, token)
    return result


def continue_until(
    save_path: Path, data: LoadedData, max_months: int = MAX_MONTHS
) -> tuple[int, StopReason]:
    """Play months as the player's Continue does until something needs the player, or
    `max_months` (30.5). Returns the months played and why it stopped; it decides nothing."""
    played = 0
    while True:
        with read_session(save_path) as session:
            state = read_state(session)
        reason = needs_player(state)
        if reason is not None:
            return played, reason
        if played >= max_months:
            return played, "months"
        run_turn(save_path, data, block_major=True)
        played += 1


def _after_commit(
    save_path: Path,
    data: LoadedData,
    result: TurnResult,
    adapter: LLMAdapter | None,
    events_from: Path | None,
) -> None:
    """Everything after the month's commit. The month is played whatever happens here, so a
    failure is logged, not raised: an unwritten event stays pending and the next turn or
    request writes it first (`_PendingEvents`)."""
    try:
        if result.event_requests or result.text_requests:
            write_pending(
                save_path, data, adapter=adapter, copy_from=events_from, committed=result.new_state
            )
    except Exception:
        log.exception("Turn %d committed; its events stay pending", result.new_state.turn)
    committed = result.new_state.turn
    backup = data.balance.backup
    try:
        if committed % backup.every_n_turns == 0:
            periodic_backup(save_path, committed, backup.keep_periodic)
        update_index(save_path, result.new_state)
    except Exception:
        log.exception("Turn %d committed; its backup or index update failed", committed)
    from tst.profile.check import check_quietly  # M25: achievements, outside the game

    check_quietly(save_path, data)


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
    with write_session(save_path) as session:
        state = load_current(session)
        balances = current_balances(session, state.turn)
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
        insert_entries(session, result.ledger_entries)
        session.add_all(log_item_to_row(i) for i in result.log_items)
        session.add_all(  # the new state's player: founding again changes it (M15b)
            inbox_rows(
                result.log_items,
                result.new_state.player.id,
                data.game_data.inbox_templates,
                frozenset(h.company_id for h in result.new_state.holdings),  # M16
            )
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
        _tidy_inbox(session, state, result.new_state, data)
        publish(session, result.new_state, apply_entries(balances, result.ledger_entries))
    from tst.profile.check import check_quietly  # M25: achievements, outside the game

    check_quietly(save_path, data)
    return result


def new_game_payload(
    company_name: str,
    scenario: str,
    difficulty: str,
    founder: FounderSpec,
    mission: tuple[str, ...],
    hq_city: str | None = None,
    mode: ModeSpec | None = None,
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
        "hq_city": hq_city,  # M9; older saves' payloads lack it (San Francisco)
        "mode": None if mode is None else asdict(mode),  # M15b; older payloads lack it
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
        first_turn = meta.created_turn  # a Sandbox or scenario save starts later (M15b)
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
        # M24: each turn's Decisions (a Holiday month lowers the founder's stress, 32.1).
        turn_decisions = {
            row.turn: Decisions(**row.payload)
            for row in session.scalars(
                select(DecisionLogRow).where(DecisionLogRow.kind == "turn_decisions")
            )
        }
        delegated: dict[int, list[tuple[int, Action]]] = {}
        for row in logged:
            if row.source == DELEGATE_SOURCE:
                delegated.setdefault(row.turn, []).append(
                    (row.company_id, action_from_payload(row.payload))
                )
        rival_logged: dict[int, list[tuple[int, dict[str, Any]]]] = {}
        for row in logged:
            if row.source == RIVAL_SOURCE:
                rival_logged.setdefault(row.turn, []).append((row.company_id, row.payload))
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
        hq_city=setup.get("hq_city"),
        mode=ModeSpec(**setup["mode"]) if setup.get("mode") else None,
    )
    for turn in range(first_turn, target_turn + 1):
        for _, action in (a for a in actions if a[0] == turn):
            run_action(path, data, action)
        if turn < target_turn:
            result = run_turn(  # events copied, never written
                path, data, turn_decisions.get(turn), events_from=source
            )
            if list(result.delegate_actions) != delegated.get(turn, []):
                raise ReplayMismatchError(
                    f"turn {turn}: recomputed delegate actions differ from the logged ones"
                )
            moves = [(m.company_id, rival_move_payload(m)) for m in result.rival_moves]
            if moves != rival_logged.get(turn, []):
                raise ReplayMismatchError(
                    f"turn {turn}: recomputed rival moves differ from the logged ones"
                )
    return path


# --- Save index (ADR-0004 section 1) --------------------------------------------------------


def summarize(path: Path) -> SaveSummary:
    with open_session(path) as session:
        meta = read_meta(session)
        # Only the player's name is needed; loading the whole state here cost a second full
        # load on every turn (M2a performance check).
        # the operating company: a holding company (M16, 31.2) is also a player company, and
        # always has the higher id
        player = session.scalars(
            select(CompanyRow).where(CompanyRow.is_player.is_(True)).order_by(CompanyRow.id)
        ).first()
        assert player is not None
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


def update_index(path: Path, state: GameState | None = None) -> None:
    """Refresh one save's entry in saves/index.json after it was created or played; the
    whole index is rebuilt only when it is missing or unreadable (M6 sub-task 0: rebuilding
    opened every save after every turn)."""
    save_dir = path.parent
    index = save_dir / INDEX_FILE
    try:
        items = [SaveSummary(**item) for item in json.loads(index.read_text(encoding="utf-8"))]
    except (OSError, ValueError, TypeError):
        refresh_index(save_dir)
        return
    slug = slug_of(path)
    mine = (
        summarize(path)
        if state is None
        else SaveSummary(
            slug=slug,
            company_name=state.player.name,
            scenario_id=state.save_meta.scenario_id,
            difficulty=state.save_meta.difficulty,
            current_turn=state.turn,
        )
    )
    items = sorted([s for s in items if s.slug != slug] + [mine], key=lambda s: s.slug)
    index.write_text(json.dumps([asdict(s) for s in items], indent=2) + "\n", encoding="utf-8")


def remove_from_index(path: Path) -> None:
    """Drop a deleted save's entry from saves/index.json (M7b)."""
    index = path.parent / INDEX_FILE
    try:
        items = [SaveSummary(**item) for item in json.loads(index.read_text(encoding="utf-8"))]
    except (OSError, ValueError, TypeError):
        refresh_index(path.parent)
        return
    slug = slug_of(path)
    kept = [s for s in items if s.slug != slug]
    index.write_text(json.dumps([asdict(s) for s in kept], indent=2) + "\n", encoding="utf-8")


def forget(path: Path) -> None:
    """Forget what this process remembers about a save file that is about to go (M7b)."""
    _LAST.pop(str(path.resolve()), None)
    migrate.forget(path)


def list_saves(save_dir: Path) -> list[SaveSummary]:
    index = save_dir / INDEX_FILE
    if not save_dir.is_dir():
        return []
    try:
        return [SaveSummary(**item) for item in json.loads(index.read_text(encoding="utf-8"))]
    except (OSError, ValueError, TypeError):
        return refresh_index(save_dir)
