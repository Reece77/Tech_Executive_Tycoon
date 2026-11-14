"""Holiday: ordinary Continues until a stop reason (docs/formulas.md 17.1; M7b).

Outside the sim: each month is `repository.run_turn`, its own transaction with its events
written after the commit, exactly as a Continue. While a holiday runs its save is reserved
(`repository.reserve`), so every other write gets 409 `save_busy`. The API runs a holiday
as a background job the front end follows (`start_job`); the CLI runs it in place.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from sqlalchemy import select

from tst.db import repository
from tst.db.models import InboxEventLinkRow, InboxItemRow
from tst.llm.base import LLMAdapter
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance
from tst.sim.decisions import Decisions
from tst.sim.errors import CriticalEventOpenError, GameOverError, SimError
from tst.sim.events.effects import blocking_events
from tst.sim.finance.statements import projected_runway
from tst.sim.money import Cents, format_money
from tst.sim.state import GameState, company_cash
from tst.sim.turn import TurnResult

log = logging.getLogger(__name__)

type StopLevel = Literal["minor", "major", "critical"]
type StopReason = Literal[
    "game_over", "event", "pitch", "approval", "runway", "offer", "months", "stopped"
]

STOP_LEVELS: tuple[StopLevel, ...] = ("minor", "major", "critical")  # rank: the index
SUMMARY_TEMPLATE = "holiday_summary"
LINK_LABEL_MAX = 200  # inbox_event_link.label column width
# Runway always stops a holiday below this many months, whatever happened before (17.1;
# a fixed rule of the spec, like the three severities, not a tunable).
RUNWAY_FLOOR_MONTHS = 3
# Inbox templates whose arrival stops a holiday: money the player must decide on (17.1.4).
OFFER_TEMPLATES = frozenset({"term_sheets_arrived", "safe_filled", "bridge_offered"})
HIRE_TEMPLATES = frozenset({"offer_accepted"})
DEPARTURE_TEMPLATES = frozenset(
    {"resigned", "retired", "employee_left", "fired", "poach_accepted", "founder_removed"}
)
LAUNCH_TEMPLATES = frozenset({"product_launched"})
ROUND_TEMPLATES = frozenset({"round_closed", "safe_filled", "bridge_funded"})

REASON_TEXT: dict[StopReason, str] = {
    "game_over": "the game is over",
    "event": "an event needs your answer",
    "pitch": "an executive pitched a move above your auto-approve limit",
    "approval": "someone running an area needs your approval",  # M27a (40.2)
    "runway": "runway is getting short",
    "offer": "investors made an offer",
    "months": "the months you chose have passed",
    "stopped": "you stopped it",
}


class HolidayError(SimError):
    code = "invalid_holiday"


@dataclass(frozen=True, slots=True)
class Vitals:
    """What the summary compares on leaving and on return (values the player sees)."""

    turn: int
    cash_cents: Cents
    arr_cents: Cents
    headcount: int
    avg_morale: float | None
    runway_months: int | None


@dataclass(frozen=True, slots=True)
class HolidayResult:
    months_played: int
    reason: StopReason
    start: Vitals
    end: Vitals
    summary_item_id: int | None


def _vitals(path: Path, data: LoadedData) -> tuple[GameState, Vitals]:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        cash = company_cash(repository.current_balances(session, state.turn), state.player.id)
        snap = repository.latest_snapshot(session, state.player.id)
    staff = state.staff(state.player.id)
    morale = [
        m
        for e in staff
        if not state.person(e.person_id).is_founder
        and (m := state.person_state(e.person_id).morale) is not None
    ]
    return state, Vitals(
        turn=state.turn,
        cash_cents=cash,
        arr_cents=snap.arr_cents if snap else 0,
        headcount=len(staff),
        avg_morale=sum(morale) / len(morale) if morale else None,
        runway_months=projected_runway(state, state.player.id, cash, data.balance, data.game_data),
    )


def check_start(
    path: Path, data: LoadedData, months: int, stop: str, *, stop_for_approvals: bool = True
) -> None:
    """Refuse a holiday that cannot start (17.1): bad months or stop level, the game over,
    or an open critical event. An area owner's proposal waits through a holiday when
    `stop_for_approvals` is off (M27a, 40.2)."""
    limit = data.balance.holiday.max_months
    if not 1 <= months <= limit:
        raise HolidayError(f"a holiday lasts 1 to {limit} months, not {months}")
    if stop not in STOP_LEVELS:
        raise HolidayError(f"stop must be one of {', '.join(STOP_LEVELS)}, not {stop!r}")
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    if state.ended:
        raise GameOverError(f"the game is over ({state.save_meta.game_state.replace('_', ' ')})")
    for proposal in state.pending_proposals(state.player.id):  # M10c (24.1)
        if proposal.kind == "auto" and not stop_for_approvals:
            continue
        raise CriticalEventOpenError(f"answer the proposal: {proposal.text}", 0)
    from tst.sim.automation.events import answered_for_player

    routine = answered_for_player(state, data.balance)  # an owner answers these (M27a, 40.5)
    for event in blocking_events(state):  # major ones too (23.1, M10b)
        if event.id in routine:
            continue
        raise CriticalEventOpenError(
            f"answer the {event.severity} event {event.title or event.template_id!r} first",
            event.id,
        )


@dataclass
class HolidayJob:
    """A holiday running in the API process; the front end polls it."""

    save_id: str
    months: int
    stop: StopLevel
    start_turn: int
    months_done: int = 0
    turn: int = 0
    status: Literal["running", "finished", "failed"] = "running"
    reason: StopReason | None = None
    summary_item_id: int | None = None
    error: str | None = None
    stop_requested: threading.Event = field(default_factory=threading.Event)


def run_holiday(
    path: Path,
    data: LoadedData,
    months: int,
    stop: StopLevel,
    *,
    adapter: LLMAdapter | None = None,
    should_stop: Callable[[], bool] = lambda: False,
    on_month: Callable[[int, int], None] | None = None,
    stop_for_approvals: bool = True,
) -> HolidayResult:
    """Play up to `months` Continues and write the summary. The caller holds the save's
    reservation (or nobody does, in a single-threaded CLI). `stop_for_approvals` (M27a, 40.2):
    a one-off from an area owner stops the holiday; off, it waits and the holiday goes on."""
    check_start(path, data, months, stop, stop_for_approvals=stop_for_approvals)
    _, start = _vitals(path, data)
    limit = data.balance.holiday.stop_runway_months
    warned = start.runway_months is not None and start.runway_months < limit
    done = 0
    reason: StopReason | None = None
    end = start
    while reason is None:
        # M24 (32.1): a month on Holiday lowers the founder's stress.
        result = repository.run_turn(path, data, Decisions(holiday=True), adapter=adapter)
        done += 1
        _, end = _vitals(path, data)
        if on_month is not None:
            on_month(done, end.turn)
        reason = _reason(
            result,
            end,
            stop,
            limit,
            warned,
            done,
            months,
            should_stop(),
            data.balance,
            stop_for_approvals=stop_for_approvals,
        )
        if end.runway_months is not None and end.runway_months < limit:
            warned = True  # only the first fall below the limit stops a holiday
    item_id = write_summary(path, data, done, reason, start, end)
    return HolidayResult(done, reason, start, end, item_id)


def big_pitch_waiting(state: GameState, cash: Cents, balance: Balance) -> bool:
    """A pitch above the auto-approve limit waits and the player ticked "stop for big
    pitches" (27.1); below the limit pitches go ahead, and without the tick they wait."""
    from tst.sim.org.formulas import auto_approve_limit

    player = state.player.id
    policy = state.pitch_policy(player)
    if not policy.stop_for_big:
        return False
    limit = auto_approve_limit(cash, policy.auto_approve_cents, balance.pitch)
    return any(p.cost_cents >= limit for p in state.pending_pitches(player))


def approval_waiting(state: GameState) -> bool:
    """An area owner's proposal, or a one-off pitch, waits for the player (40.2)."""
    from tst.sim.automation.config import ONE_OFF_PITCHES

    player = state.player.id
    return any(p.kind == "auto" for p in state.pending_proposals(player)) or any(
        p.kind in ONE_OFF_PITCHES for p in state.pending_pitches(player)
    )


def _reason(
    result: TurnResult,
    end: Vitals,
    stop: StopLevel,
    limit: int,
    warned: bool,
    done: int,
    months: int,
    pressed: bool,
    balance: Balance | None = None,
    *,
    stop_for_approvals: bool = True,
) -> StopReason | None:
    """The first stop reason after a month, in the order of 17.1 (None: keep going)."""
    state = result.new_state
    player = state.player.id
    if state.ended:
        return "game_over"
    rank = STOP_LEVELS.index(stop)
    if any(
        r.company_id == player and STOP_LEVELS.index(r.severity) >= rank
        for r in result.event_requests
    ):
        return "event"
    major = STOP_LEVELS.index("major")
    proposals = state.pending_proposals(player)
    if rank <= major and any(p.kind != "auto" for p in proposals):  # major (24.1)
        return "event"
    if stop_for_approvals and approval_waiting(state):  # M27a (40.2)
        return "approval"
    if balance is not None and big_pitch_waiting(state, end.cash_cents, balance):  # M13b
        return "pitch"
    runway = end.runway_months
    if runway is not None and (runway < RUNWAY_FLOOR_MONTHS or (runway < limit and not warned)):
        return "runway"
    if any(i.company_id == player and i.template in OFFER_TEMPLATES for i in result.log_items):
        return "offer"
    if done >= months:
        return "months"
    if pressed:
        return "stopped"
    return None


def _morale(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0f}"


def write_summary(
    path: Path,
    data: LoadedData,
    months_played: int,
    reason: StopReason,
    start: Vitals,
    end: Vitals,
) -> int:
    """The "While you were away" inbox item (17.1), written in its own transaction."""
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        player = state.player.id
        rows = session.scalars(
            select(InboxItemRow)
            .where(
                InboxItemRow.company_id == player,
                InboxItemRow.turn >= start.turn,
                InboxItemRow.turn < end.turn,
            )
            .order_by(InboxItemRow.id)
        ).all()
        items = [(r.template, r.title) for r in rows]
    events = sorted(
        (
            e
            for e in state.events
            if e.company_id == player
            and e.status == "auto"
            and e.resolved_turn is not None
            and start.turn <= e.resolved_turn <= end.turn
        ),
        key=lambda e: e.id,
    )
    lines = [
        f"Away {months_played} month{'' if months_played == 1 else 's'}, "
        f"{format_turn(start.turn)} to {format_turn(end.turn)}. "
        f"Stopped because {REASON_TEXT[reason]}.",
        "",
        f"Cash: {format_money(start.cash_cents)} -> {format_money(end.cash_cents)}",
        f"ARR: {format_money(start.arr_cents)} -> {format_money(end.arr_cents)}",
        f"Staff: {start.headcount} -> {end.headcount}",
        f"Average morale: {_morale(start.avg_morale)} -> {_morale(end.avg_morale)}",
    ]
    sections: list[tuple[str, list[str]]] = [
        (
            "Events decided for you",
            [
                f"{e.title or e.template_id}: {choice.label if choice else e.chosen}"
                for e in events
                if (choice := e.choice(e.chosen or "")) is not None or e.chosen
            ],
        ),
        ("Hires", [t for k, t in items if k in HIRE_TEMPLATES]),
        ("Departures", [t for k, t in items if k in DEPARTURE_TEMPLATES]),
        ("Launches", [t for k, t in items if k in LAUNCH_TEMPLATES]),
        ("Funding", [t for k, t in items if k in ROUND_TEMPLATES]),
    ]
    for heading, entries in sections:
        if entries:
            lines += ["", f"{heading}:", *(f"- {entry}" for entry in entries)]
    title = f"While you were away: {months_played} month{'' if months_played == 1 else 's'}"
    with repository.write_session(path) as session:
        row = InboxItemRow(
            turn=max(end.turn - 1, 0),
            company_id=player,
            template=SUMMARY_TEMPLATE,
            title=title,
            body="\n".join(lines),
            link_kind="history",
            link_id=None,
            read=False,
            archived=False,
            bookmarked=False,
        )
        session.add(row)
        session.flush()
        item_id = int(row.id)
        session.add_all(  # each decided event opens its card (M7c)
            InboxEventLinkRow(
                item_id=item_id,
                position=i,
                event_id=e.id,
                label=(e.title or e.template_id)[:LINK_LABEL_MAX],
            )
            for i, e in enumerate(events)
        )
    return item_id


# --- Jobs (API) -----------------------------------------------------------------------------

_JOBS: dict[str, HolidayJob] = {}
_JOBS_GUARD = threading.Lock()


def job_for(path: Path) -> HolidayJob | None:
    with _JOBS_GUARD:
        return _JOBS.get(str(path.resolve()))


def start_job(
    path: Path,
    save_id: str,
    data: LoadedData,
    months: int,
    stop: StopLevel,
    *,
    adapter: LLMAdapter | None = None,
    stop_for_approvals: bool = True,
) -> HolidayJob:
    """Check the holiday can start, reserve the save, and play it in a background thread.
    The reservation is taken before this returns, so the next write is already busy."""
    check_start(path, data, months, stop, stop_for_approvals=stop_for_approvals)
    token = repository.reserve(path)
    with repository.read_session(path) as session:
        turn = repository.read_state(session).turn
    job = HolidayJob(save_id=save_id, months=months, stop=stop, start_turn=turn, turn=turn)
    with _JOBS_GUARD:
        _JOBS[str(path.resolve())] = job

    def progress(done: int, now: int) -> None:
        job.months_done, job.turn = done, now

    def play() -> None:
        result: HolidayResult | None = None
        error: str | None = None
        try:
            with repository.holding(token):
                result = run_holiday(
                    path,
                    data,
                    months,
                    stop,
                    adapter=adapter,
                    should_stop=job.stop_requested.is_set,
                    on_month=progress,
                    stop_for_approvals=stop_for_approvals,
                )
        except Exception as exc:  # the job reports it; the months played stay committed
            log.exception("Holiday on %s failed", save_id)
            error = exc.message if isinstance(exc, SimError) else type(exc).__name__
        finally:
            repository.release(path, token)  # before "finished": the next write is free
        if result is not None:
            job.reason, job.summary_item_id = result.reason, result.summary_item_id
            job.status = "finished"
        else:
            job.error = error
            job.status = "failed"

    threading.Thread(target=play, name=f"holiday-{save_id}", daemon=True).start()
    return job
