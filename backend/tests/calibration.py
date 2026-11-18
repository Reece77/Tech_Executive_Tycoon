"""A runner's speed beside a wall-time guard (M35a, M36p's follow-up): a fixed CPU-bound
workload in pure Python, timed the same way as the month it sits next to, so a slow runner
shows in the log. The guards stay in milliseconds; M30's 500 ms guard on the V6 saves reads the
median divided by the runner's ratio (product manager, 2026-11-17)."""

from __future__ import annotations

import hashlib
import statistics
import time
from fractions import Fraction

# The workload's median on the M35a container (4 CPUs, Linux, Python 3.12), in seconds: a
# runner's ratio to it says how much faster or slower that runner is.
REFERENCE_S = 0.070
REPEATS = 5


def _workload() -> int:
    """Dict, tuple, Fraction and hashing work in the proportions a month does."""
    acc: dict[int, tuple[int, ...]] = {}
    total = Fraction(0)
    digest = hashlib.sha256()
    for i in range(400_000):
        acc[i % 997] = (i, i * 7 % 13, len(acc))
        if i % 50 == 0:
            total += Fraction(i, 97)
        digest.update(i.to_bytes(4, "little"))
    return len(acc) + int(total) + digest.digest()[0]


def calibrate() -> float:
    """The workload's median wall time in seconds."""
    times = []
    for _ in range(REPEATS):
        start = time.perf_counter()
        _workload()
        times.append(time.perf_counter() - start)
    return statistics.median(times)


def runner_note(month_s: float, workload_s: float | None = None) -> str:
    """'runner x1.20 (workload 120 ms against 100 ms); month = 3.1 workloads'. Pass the
    workload's time from `calibrate()` to reuse it rather than time it again."""
    w = calibrate() if workload_s is None else workload_s
    return (
        f"runner x{w / REFERENCE_S:.2f} (workload {w * 1000:.0f} ms against "
        f"{REFERENCE_S * 1000:.0f} ms); month = {month_s / w:.1f} workloads"
    )
