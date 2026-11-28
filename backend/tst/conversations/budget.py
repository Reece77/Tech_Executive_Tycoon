"""The conversations' monthly cap, reserved before each call (M57r-B, review 10 item 22).

Before an LLM call a conversation reserves the call's bounded cost (its prompt at one token a
character, and the adapter's most output tokens) against the save folder's cap for the
calendar month, atomically across threads and processes (the API, the CLI beside it, two
saves in one folder): the month's recorded spend plus every open reservation plus this one
must fit. The call is refused when it does not, so the cap is never overspent. Afterwards, in a
`finally`, the reservation is released and the call's actual cost recorded at once, whatever
happens to the save's transaction after it.

A reservation a crashed process never released lapses after `STALE_S`, so a crash costs at
most a few minutes of the cap. Wall-clock time is fine here: none of this is the simulation.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from tst.llm.settings import add_spend, month_key, month_spend

log = logging.getLogger(__name__)

RESERVE_FILE = "llm_reservations.json"
LOCK_FILE = "llm_spend.lock"
STALE_S = 600.0  # tunable-exempt: a reservation older than this was left by a crash
MAX_OUTPUT_TOKENS = 1500  # tunable-exempt: the adapter's most output tokens a conversation call
_thread_lock = threading.Lock()


@dataclass(frozen=True, slots=True)
class Reservation:
    id: str
    month: str
    cents: float


def _os_lock(handle: IO[bytes]) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        for _ in range(600):  # tunable-exempt: up to a minute of other writers
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                time.sleep(0.1)
        raise OSError("the conversation budget is locked by another process")
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _os_unlock(handle: IO[bytes]) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def folder_lock(save_dir: Path) -> Iterator[None]:
    """The save folder's budget lock: one holder across this process's threads and others."""
    save_dir.mkdir(parents=True, exist_ok=True)
    with _thread_lock, (save_dir / LOCK_FILE).open("a+b") as handle:
        _os_lock(handle)
        try:
            yield
        finally:
            _os_unlock(handle)


def _read(save_dir: Path) -> dict[str, dict[str, list[float]]]:
    """{month: {id: [cents, unix time]}}"""
    try:
        raw = json.loads((save_dir / RESERVE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write(save_dir: Path, data: dict[str, dict[str, list[float]]]) -> None:
    tmp = save_dir / f"{RESERVE_FILE}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    tmp.replace(save_dir / RESERVE_FILE)


def outstanding(save_dir: Path, month: str | None = None) -> float:
    """Cents reserved this month by calls still running (stale ones aside)."""
    key = month or month_key()
    now = time.time()
    held = _read(save_dir).get(key, {})
    return sum(c for c, at in held.values() if now - at < STALE_S)


def reserve(save_dir: Path, cap_cents: float, cents: float) -> Reservation | None:
    """Reserve `cents` of this month's cap, or None when the spend, the open reservations and
    this one would pass it."""
    with folder_lock(save_dir):
        key = month_key()
        data = _read(save_dir)
        now = time.time()
        held = {k: v for k, v in data.get(key, {}).items() if now - v[1] < STALE_S}
        spent = month_spend(save_dir).conversation_cents
        if spent + sum(c for c, _ in held.values()) + cents > cap_cents:
            return None
        rid = secrets.token_hex(8)
        held[rid] = [cents, now]
        data = {key: held}  # earlier months' reservations are over
        _write(save_dir, data)
        return Reservation(rid, key, cents)


def settle(save_dir: Path, reservation: Reservation, actual_cents: float, calls: int) -> None:
    """Release the reservation and record what the call cost (in the reservation's month)."""
    with folder_lock(save_dir):
        data = _read(save_dir)
        data.get(reservation.month, {}).pop(reservation.id, None)
        _write(save_dir, data)
        if actual_cents or calls:
            add_spend(
                save_dir,
                0.0,
                conversation_cents=actual_cents,
                conversation_calls=calls,
            )
