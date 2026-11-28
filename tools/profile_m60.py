"""Profile a late save's months by phase (M60 sub-task 1; a measuring tool, never part of the
game): it plays a copy. Each of the turn's twelve phases, the v6 steps inside them (FX, banks and
insurers, telecom, media, the markets) and the save's write are wrapped in a timer; a second pass
wraps them in `tracemalloc` for the bytes each allocates. Writes `phases.json` and a text table.

    uv run --project backend python tools/profile_m60.py <save.tst.sqlite> <out dir>
        [--warm-up 2] [--timed 8] [--alloc 2]

Times are wall-clock means a month in ms, nested (a step's time is inside its phase's).
"""

from __future__ import annotations

import argparse
import functools
import importlib
import json
import shutil
import statistics
import sys
import time
import tracemalloc
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

# (module, attribute): the steps timed besides the twelve phases. Patched on the module, so
# calls through `module.attr` (as turn.py's `fx_phase.before_markets`) and names imported from
# it into tst.sim.turn (patched there too) both pass through the timer.
STEPS: tuple[tuple[str, str], ...] = (
    ("tst.sim.fx.phase", "before_markets"),
    ("tst.sim.fx.phase", "after_sales"),
    ("tst.sim.fx.phase", "cost_entries"),
    ("tst.sim.fx.phase", "with_effects"),
    ("tst.sim.finserv.phase", "open_month"),
    ("tst.sim.finserv.phase", "with_effects"),
    ("tst.sim.finserv.phase", "after_sales"),
    ("tst.sim.finserv.phase", "demand_month"),
    ("tst.sim.media.phase", "open_month"),
    ("tst.sim.media.phase", "with_effects"),
    ("tst.sim.media.phase", "after_sales"),
    ("tst.sim.media.phase", "demand_month"),
    ("tst.sim.telecom.phase", "open_month"),
    ("tst.sim.telecom.phase", "with_effects"),
    ("tst.sim.telecom.phase", "after_sales"),
    ("tst.sim.telecom.phase", "demand_month"),
    ("tst.sim.space.phase", "after_sales"),
    ("tst.sim.vehicles.phase", "after_sales"),
    ("tst.sim.robotics.phase", "after_sales"),
    ("tst.sim.platforms.month", "before_markets"),
    ("tst.sim.platforms.month", "after_markets"),
    ("tst.sim.government.phase", "month"),
    ("tst.sim.products.phases", "run_markets"),
    ("tst.sim.products.phases", "brand_and_demand"),
    ("tst.sim.mining.phase", "operate_month"),
    ("tst.sim.pharma.month", "sales_month"),
    ("tst.sim.world.phase", "world_month"),
    ("tst.db.repository", "load_current"),
    ("tst.db.repository", "current_balances"),
    ("tst.db.repository", "month_so_far"),
    ("tst.db.repository", "apply_turn_result"),
    ("tst.db.repository", "publish"),
    ("tst.db.repository", "_after_commit"),
    ("tst.db.state_io", "sync_state"),
    ("tst.db.state_io", "_sync_geo"),
    ("tst.db.state_io", "_sync_research"),
    ("tst.db.state_io", "_insert_reveals"),
    ("tst.db.state_io", "insert_entries"),
    ("tst.db.state_io", "insert_rows"),
    ("tst.db.world_io", "sync_world"),
    ("tst.db.regulation_io", "sync_regulation"),
    ("tst.db.government_io", "sync_government"),
    ("tst.db.finserv_io", "sync_finserv"),
    ("tst.db.media_io", "sync_media"),
    ("tst.db.telecom_io", "sync_telecom"),
    ("tst.db.history", "prune_candidates"),
    ("sqlalchemy.orm.session", "Session.commit"),
)


class Meter:
    def __init__(self) -> None:
        self.ms: dict[str, list[float]] = defaultdict(list)
        self.bytes: dict[str, list[int]] = defaultdict(list)
        self.alloc = False
        self.month: dict[str, float] = defaultdict(float)
        self.month_bytes: dict[str, int] = defaultdict(int)

    def wrap(self, name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def timed(*args: Any, **kwargs: Any) -> Any:
            if self.alloc:
                before, _ = tracemalloc.get_traced_memory()
                tracemalloc.reset_peak()
                try:
                    return fn(*args, **kwargs)
                finally:
                    _, peak = tracemalloc.get_traced_memory()
                    self.month_bytes[name] += peak - before
            start = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                self.month[name] += (time.perf_counter() - start) * 1000

        return timed

    def end_month(self) -> None:
        for k, v in self.month.items():
            self.ms[k].append(v)
        for k, b in self.month_bytes.items():
            self.bytes[k].append(b)
        self.month.clear()
        self.month_bytes.clear()


def install(meter: Meter) -> None:
    from tst.db import repository
    from tst.sim import turn

    turn.PHASES = tuple((n, meter.wrap(n, f)) for n, f in turn.PHASES)  # type: ignore[misc]
    for mod_name, attr in STEPS:
        mod = importlib.import_module(mod_name)
        owner: Any = mod
        name = attr
        if "." in attr:  # a method: Class.method
            cls, name = attr.split(".")
            owner = getattr(mod, cls)
        original = getattr(owner, name)
        label = f"{mod_name.removeprefix('tst.').removeprefix('sim.')}.{attr}"
        wrapped = meter.wrap(label, original)
        setattr(owner, name, wrapped)
        if owner is not mod:
            continue
        for user in list(sys.modules.values()):  # names imported elsewhere
            if (
                getattr(user, "__name__", "").startswith("tst.")
                and getattr(user, name, None) is original
            ):
                setattr(user, name, wrapped)
    repository.advance_turn = meter.wrap("advance_turn", repository.advance_turn)  # type: ignore[attr-defined]
    repository.run_turn = meter.wrap("run_turn", repository.run_turn)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("save", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--warm-up", type=int, default=2)
    parser.add_argument("--timed", type=int, default=8)
    parser.add_argument("--alloc", type=int, default=2)
    args = parser.parse_args()

    from tests.helpers import answer_critical, continue_at_end
    from tst.db import migrate, repository
    from tst.db.repository import load_state, open_session
    from tst.loader import load_all

    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "copy" / args.save.name
    path.parent.mkdir(exist_ok=True)
    shutil.copy(args.save, path)
    migrate.ensure_current(path)
    data = load_all(BACKEND / "data")
    continue_at_end(path, data)
    with open_session(path) as session:
        state = load_state(session)
    turn0, companies = state.turn, len(state.companies)
    meter = Meter()
    install(meter)
    for _ in range(args.warm_up):
        answer_critical(path, data)
        repository.run_turn(path, data)
    meter.ms.clear()
    meter.month.clear()
    for _ in range(args.timed):
        answer_critical(path, data)
        repository.run_turn(path, data)
        meter.end_month()
    meter.alloc = True
    tracemalloc.start()
    for _ in range(args.alloc):
        answer_critical(path, data)
        repository.run_turn(path, data)
        meter.end_month()
    tracemalloc.stop()
    rows = {
        k: {
            "mean_ms": round(statistics.fmean(v), 1),
            "median_ms": round(statistics.median(v), 1),
            "alloc_mb": round(statistics.fmean(meter.bytes.get(k, [0])) / 2**20, 1),
        }
        for k, v in meter.ms.items()
    }
    total = rows["run_turn"]["median_ms"]
    report = {"save": str(args.save), "from_turn": turn0, "companies": companies, "rows": rows}
    (args.out / "phases.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    lines = [f"{args.save.name} from turn {turn0}, {companies} companies; run_turn {total} ms"]
    for k, r in sorted(rows.items(), key=lambda kv: -kv[1]["mean_ms"]):
        share = r["mean_ms"] / rows["run_turn"]["mean_ms"]
        lines.append(f"{k:48s} {r['mean_ms']:8.1f} ms {share:6.1%} {r['alloc_mb']:7.1f} MB")
    text = "\n".join(lines)
    (args.out / "phases.txt").write_text(text + "\n", encoding="utf-8")
    print(text)
    shutil.rmtree(path.parent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
