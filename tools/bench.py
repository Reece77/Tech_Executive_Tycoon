"""M30's benchmark (docs/tasks/M30-performance-at-scale.md sub-task 1; a measuring tool, never
used by the game). It never fails on a slow number: it writes a table to docs/perf/.

`build` makes three saves at January 2039 through the normal save path (every month and action
goes through `repository`, as tools/v6_save.py):

- integrator: M23b's full_integrator, January 2010 to January 2039 (tools/v6_save.py);
- software: the v2 integrator, the largest software company the scripts build (its own data
  centres), over the same years (acquirer, which buys companies, ends its game before 2039);
- world: a do-nothing player with $50B of cash moved to January 2026 (as tst.balance.m28_world)
  and played to January 2039 in the living world: every M28 chain company and 13 years of its
  facilities, deals and news;
- v6, v6i (M45): the two saves M30's 2039 guard times (tools/v6_save.py; research_heavy and
  full_integrator), January 2010 to January 2039;
- dynasty (M45): M37's save, full_integrator in dynasty mode with a family (children 2 and 5),
  January 2010 to January 2069 (708 months; the weekly-m37 job's save).

`run` copies each save and measures, on the copy:

- turns: 12 months played one Continue at a time (`repository.run_turn`, open critical events
  answered first, as the player must): median and 95th percentile;
- holiday: 12 months of Holiday (`holiday.run_holiday`, stopping only for critical events;
  any stop is answered and the holiday goes on until 12 months are played);
- save: size on disk (WAL checkpointed), a full `load_state` in a fresh session, and a cold
  start (a new process: import the API, open the save, answer Overview);
- screens: the API endpoints behind the ten largest screens after one month is played: the
  first request (nothing read since the month) and 20 more (warm), their 95th percentile;
- digest: the full state after the 12 turns and after the holiday (tst.balance.m30's digest),
  which must be the same before and after any speed-up.

    uv run --project backend python tools/bench.py build <save dir>
    uv run --project backend python tools/bench.py run <save dir> --label baseline
"""

from __future__ import annotations

import argparse
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
BACKEND: Final = ROOT / "backend"
PERF_DIR: Final = ROOT / "docs" / "perf"
SAVES: Final = ("integrator", "software", "world", "v6", "v6i", "dynasty")
STRATEGY: Final = {
    "integrator": "full_integrator",
    "software": "integrator",
    "v6": "research_heavy",
    "v6i": "full_integrator",
    "dynasty": "full_integrator",
}
JANUARY_2039: Final = 348
# M45: the saves M30's and M37's guards time, built as the weekly jobs build them (Makefile)
TURNS: Final = {"v6": 360, "v6i": 360, "dynasty": 708}
LENGTH: Final = {"dynasty": "dynasty"}
CHILDREN: Final = {"dynasty": (2, 5)}
WORLD_FROM: Final = 192  # January 2026
WORLD_CASH: Final = 5_000_000_000_000  # $50B, as tst.balance.m28_world
SEED: Final = 1
MONTHS: Final = 12
WARM_CALLS: Final = 20
# screen -> its endpoints (paths under /api/saves/{save_id}); "{category}" is the player's
# largest market. Overview carries the layout's own calls (every screen makes them).
SCREENS: Final[dict[str, tuple[str, ...]]] = {
    "Overview": ("/overview", "/events", "/finance/summary"),
    "People": ("/people",),
    "Products": ("/products", "/portfolio"),
    "Market": ("/markets/{category}",),
    "Rivals": ("/rivals", "/news"),
    "World news": ("/world-news",),
    "Group": ("/group",),
    "Fabs": ("/fabs",),
    "Mines": ("/mines",),
    "Automation": ("/automation", "/automation/digest"),
}

os.environ.setdefault("TST_LLM_ADAPTER", "mock")
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "tools"))


def save_path(save_dir: Path, name: str) -> Path:
    from tst.db import repository

    return repository.save_path(save_dir, name)


# --- build -------------------------------------------------------------------------------------


def _world(save_dir: Path, data: Any) -> Path:
    """The world save: a new game moved to January 2026 with $50B (one balanced ledger entry
    against common equity), then 156 months of Continue with nothing decided."""
    from tst.db import repository
    from tst.db.mappers import entry_to_row
    from tst.db.state_io import read_meta, sync_state
    from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry, LedgerLine

    path = repository.create_save(
        "world", SEED, "ex_big_tech_founders", company_name="Balance Co", data=data,
        save_dir=save_dir,
    )  # fmt: skip
    with repository.open_session(path) as session, session.begin():
        before = repository.load_state(session)
        sync_state(session, before, replace(before, turn=WORLD_FROM))
        read_meta(session).current_turn = WORLD_FROM
        lines = (LedgerLine(CASH, WORLD_CASH), LedgerLine(COMMON_EQUITY, -WORLD_CASH))
        session.add(entry_to_row(LedgerEntry(WORLD_FROM - 1, 1, "Bench: world cash", lines)))
    started = time.perf_counter()
    while _turn(path) < JANUARY_2039:
        answer_blockers(path, data)
        repository.run_turn(path, data)
        if _turn(path) % 12 == 0:
            print(f"world: turn {_turn(path)}, {time.perf_counter() - started:.0f} s", flush=True)
    return path


def build(save_dir: Path, names: tuple[str, ...]) -> None:
    from tst.loader import load_all
    from v6_save import build as build_v6

    data = load_all(BACKEND / "data")
    save_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{save_path(save_dir, name)}{suffix}").unlink(missing_ok=True)
        if name == "world":
            _world(save_dir, data)
        else:
            build_v6(
                save_dir,
                name,
                TURNS.get(name, JANUARY_2039),
                SEED,
                STRATEGY[name],
                LENGTH.get(name, "standard"),
                CHILDREN.get(name, ()),
            )
        print(f"built {save_path(save_dir, name)}", flush=True)


# --- run ---------------------------------------------------------------------------------------


def _turn(path: Path) -> int:
    from tst.db import repository

    with repository.read_session(path) as session:
        return repository.read_state(session).turn


def answer_blockers(path: Path, data: Any) -> None:
    """Answer what stops a Continue or a Holiday: blocking events with their first choice and
    pending proposals with Approve (as tst.balance.game and the e2e scripts do)."""
    from tst.db import repository
    from tst.sim.actions import ChooseEvent
    from tst.sim.actions.authority import AnswerProposal
    from tst.sim.errors import SimError
    from tst.sim.events.effects import blocking_events

    for _ in range(20):
        with repository.read_session(path) as session:
            state = repository.read_state(session)
        founder = state.founder_of(state.player.id)
        actor = founder.id if founder is not None else 1
        from tst.sim.dynasty.mode import ContinueDynasty, at_standard_end

        if at_standard_end(state, data.balance):  # M37 (52.1): a player plays on past 2039
            repository.run_action(path, data, ContinueDynasty(actor))
            continue
        todo: list[Any] = [
            ChooseEvent(actor, e.id, e.choices[0].key) for e in blocking_events(state) if e.choices
        ]
        todo += [
            AnswerProposal(actor, p.id, True) for p in state.pending_proposals(state.player.id)
        ]
        if not todo:
            return
        for action in todo:
            try:
                repository.run_action(path, data, action)
            except SimError:
                if isinstance(action, AnswerProposal):
                    repository.run_action(path, data, replace(action, approve=False))


def p95(xs: list[float]) -> float:
    """The nearest-rank 95th percentile."""
    s = sorted(xs)
    return s[max(0, -(-len(s) * 95 // 100) - 1)]


def _forget(state_too: bool = True) -> None:
    """Drop what this process remembers of saves: what reads computed since the last commit
    (M30's read memo, where the code has one) and, with `state_too`, the state itself."""
    from tst.db import repository

    getattr(repository, "_READ_MEMOS", {}).clear()
    if state_too:
        repository._LAST.clear()  # the next read loads from the database


def _copy(source: Path, into: Path) -> Path:
    """A copy of the save, upgraded to the code's schema as the app upgrades a save it opens
    (so a turn never carries a migration's one-off work)."""
    from tst.db import migrate

    into.mkdir(parents=True, exist_ok=True)
    for f in source.parent.glob(source.name.split(".")[0] + ".*"):
        if f.is_file():
            shutil.copy(f, into / f.name)
    migrate.ensure_current(into / source.name)
    return into / source.name


def _checkpoint(path: Path) -> None:
    import sqlite3

    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def digest(path: Path) -> str:
    from tst.balance.m30 import Digester
    from tst.db import repository

    with repository.open_session(path) as session:
        state = repository.load_state(session)
        balances = dict(repository.ledger_balances(session, state.turn))
    d = Digester()
    return (d.digest(state) + d.digest(balances)).hex()[:16]


@dataclass(slots=True)
class SaveResult:
    name: str
    turn: int = 0
    turns_ms: list[float] = field(default_factory=list)
    holiday_s: float = 0.0
    holiday_months: int = 0
    size_mb: float = 0.0
    load_s: float = 0.0
    cold_start_s: float = 0.0
    screens: dict[str, tuple[int, float, float]] = field(
        default_factory=dict
    )  # path -> status, first, p95 ms
    turns_digest: str = ""
    holiday_digest: str = ""


def _time_turns(path: Path, data: Any, res: SaveResult) -> None:
    from tst.db import repository

    _forget()
    for _ in range(MONTHS):
        answer_blockers(path, data)
        start = time.perf_counter()
        repository.run_turn(path, data)
        res.turns_ms.append((time.perf_counter() - start) * 1000)
    res.turns_digest = digest(path)


def _time_holiday(path: Path, data: Any, res: SaveResult) -> None:
    from tst import holiday

    _forget()
    done = 0
    elapsed = 0.0
    while done < MONTHS:
        answer_blockers(path, data)
        start = time.perf_counter()
        out = holiday.run_holiday(path, data, MONTHS - done, "critical")
        elapsed += time.perf_counter() - start
        done += max(out.months_played, 1)
    res.holiday_s, res.holiday_months = elapsed, done
    res.holiday_digest = digest(path)


def _time_load(path: Path, res: SaveResult) -> None:
    from tst.db import repository

    _checkpoint(path)
    res.size_mb = sum(f.stat().st_size for f in path.parent.glob(path.name + "*")) / 1e6
    loads = []
    for _ in range(3):
        start = time.perf_counter()
        with repository.open_session(path) as session:
            repository.load_state(session)
        loads.append(time.perf_counter() - start)
    res.load_s = statistics.median(loads)
    code = (
        "import time; t=time.perf_counter()\n"
        "from fastapi.testclient import TestClient\n"
        "from tst.api.app import create_app\n"
        "with TestClient(create_app()) as c:\n"
        f"    r = c.get('/api/saves/{path.name.split('.')[0]}/overview')\n"
        "    assert r.status_code == 200, r.text\n"
        "print(time.perf_counter()-t)\n"
    )
    env = {**os.environ, "TST_SAVE_DIR": str(path.parent)}
    start = time.perf_counter()
    subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, check=True,
                   capture_output=True)  # fmt: skip
    res.cold_start_s = time.perf_counter() - start


def _category(path: Path) -> str:
    from tst.db import repository

    with repository.read_session(path) as session:
        state = repository.read_state(session)
    live = [p for p in state.company_products(state.player.id) if p.status == "live"]
    if live:
        return live[0].category
    return state.products[0].category if state.products else "b2b_saas"


def _time_screens(path: Path, data: Any, res: SaveResult) -> None:
    """Each endpoint as the player meets it: first after a month is played (the turn
    remembers the state it wrote; nothing read since), then warm."""
    from fastapi.testclient import TestClient
    from tst.api.app import create_app
    from tst.api.deps import get_settings
    from tst.config import Settings
    from tst.db import repository

    save_id = path.name.split(".")[0]
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=path.parent)
    category = _category(path)
    with TestClient(app) as client:
        # the app's own first-request costs (its data load: the cold start's), outside them
        client.get(f"/api/saves/{save_id}/overview")
        answer_blockers(path, data)
        repository.run_turn(path, data)
        for paths in SCREENS.values():
            for p in paths:
                url = f"/api/saves/{save_id}" + p.format(category=category)
                _forget(state_too=False)
                start = time.perf_counter()
                status = client.get(url).status_code
                first = (time.perf_counter() - start) * 1000
                warm = []
                for _ in range(WARM_CALLS):
                    start = time.perf_counter()
                    client.get(url)
                    warm.append((time.perf_counter() - start) * 1000)
                res.screens[p] = (status, first, p95(warm))


@contextmanager
def _scratch() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="tst-bench-") as tmp:
        yield Path(tmp)


def measure(source: Path, name: str, data: Any, parts: set[str]) -> SaveResult:
    res = SaveResult(name)
    steps: list[tuple[str, Callable[[Path], None]]] = [
        ("save", lambda p: _time_load(p, res)),
        ("screens", lambda p: _time_screens(p, data, res)),
        ("turns", lambda p: _time_turns(p, data, res)),
        ("holiday", lambda p: _time_holiday(p, data, res)),
    ]
    for part, step in steps:
        if part not in parts:
            continue
        with _scratch() as tmp:
            path = _copy(source, tmp / "saves")
            res.turn = _turn(path)
            step(path)
            _forget()
        print(f"{name}: {part} done", flush=True)
    return res


def _env() -> str:
    import platform

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    return (
        f"commit {commit}, Python {platform.python_version()}, {platform.system()} "
        f"{platform.machine()}, {os.cpu_count()} CPUs"
    )


def table(results: list[SaveResult], label: str) -> str:
    from tst.sim.calendar import format_turn

    out = [f"# Benchmark: {label}", "", f"{_env()}. Written by `tools/bench.py run`.", ""]
    out += ["## Turns, Holiday and saves", ""]
    out += [
        "| Save | From | Turn median ms | Turn p95 ms | Turn max ms | Holiday s (months) "
        "| Size MB | Load s | Cold start s | Digest after turns | Digest after Holiday |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for r in results:
        t = r.turns_ms
        out.append(
            f"| {r.name} | {format_turn(r.turn)} "
            f"| {statistics.median(t):.0f} | {p95(t):.0f} | {max(t):.0f} "
            if t
            else f"| {r.name} | {format_turn(r.turn)} | - | - | - "
        )
        out[-1] += (
            f"| {r.holiday_s:.1f} ({r.holiday_months}) | {r.size_mb:.1f} | {r.load_s:.2f} "
            f"| {r.cold_start_s:.2f} | `{r.turns_digest}` | `{r.holiday_digest}` |"
        )
    out += ["", "## Screens (API, ms: first request after a month is played / warm p95)", ""]
    header = "| Screen | Endpoint | " + " | ".join(r.name for r in results) + " |"
    out += [header, "|---|---|" + "---:|" * len(results)]
    for screen, paths in SCREENS.items():
        for p in paths:
            cells = []
            for r in results:
                if p not in r.screens:
                    cells.append("-")
                    continue
                status, first, warm = r.screens[p]
                cells.append(
                    f"{first:.0f} / {warm:.0f}" + ("" if status == 200 else f" ({status})")
                )
            out.append(f"| {screen} | `{p}` | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def run(save_dir: Path, label: str, names: tuple[str, ...], parts: set[str]) -> Path:
    from tst.loader import load_all

    data = load_all(BACKEND / "data")
    results = [measure(save_path(save_dir, n), n, data, parts) for n in names]
    PERF_DIR.mkdir(parents=True, exist_ok=True)
    out = PERF_DIR / f"{label}.md"
    out.write_text(table(results, label), encoding="utf-8", newline="\n")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("build", "run"))
    parser.add_argument("save_dir", type=Path)
    parser.add_argument("--saves", default=",".join(SAVES))
    parser.add_argument("--label", default="bench")
    parser.add_argument("--parts", default="save,screens,turns,holiday")
    args = parser.parse_args()
    names = tuple(args.saves.split(","))
    if args.command == "build":
        build(args.save_dir.resolve(), names)
    else:
        print(run(args.save_dir.resolve(), args.label, names, set(args.parts.split(","))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
