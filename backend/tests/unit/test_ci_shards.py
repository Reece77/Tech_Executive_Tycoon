"""M59 sub-task 5: the CI shards stay inside their limits as tests are added.

From the measured durations (`tests/durations.json` for the backend, `frontend/e2e/durations.json`
for Playwright) and the matrix sizes and limits in `.github/workflows/check.yml` and `e2e.yml`,
predict each shard's job minutes. The slowest shard over 70% of its job's limit is a warning
(in the GitHub job summary and as a pytest warning); over 90% the test fails. Either way the
cure is a rebalance (`make test-durations`, the nightly's `e2e-durations.json`) or a fifth shard,
never a longer limit (docs/ci.md).

The backend split is tests/conftest.py's `shard_of`; the Playwright split is
frontend/e2e/shard-reporter.ts's `assignShards`, which `playwright_shards` below repeats (keep
the two in step).
"""

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path

import pytest
import yaml

from tests.conftest import CHECK_TESTS, DURATIONS_FILE, SHARD_OVERHEAD_S, shard_of

REPO = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO / ".github" / "workflows"
E2E_DIR = REPO / "frontend" / "e2e"

WARN_SHARE = 0.70  # of the job's limit: a warning in the job summary
FAIL_SHARE = 0.90  # of the job's limit: the test fails

# Backend shard minutes on CI: CHECK_FIXED_MIN (setup, collection and xdist start) plus the
# shard's other work, plus CHECK_FACTOR x its weighted minutes (`shard_of`'s weights: duration +
# SHARD_OVERHEAD_S). Fitted on main's d6d61fb (two shards, 116.6 weighted minutes each, ran
# pytest in 28:56 and 28:55 on 2 workers; setup 0.4 and collection 1.3 minutes).
CHECK_FACTOR = 28.9 / 116.6
CHECK_FIXED_MIN = 1.7
CHECK_EXTRA_MIN = {1: 1.1, 2: 0.3, 3: 1.0}  # mypy and ruff; the API sync; the front end
# Playwright shard minutes on CI: E2E_FIXED_MIN (setup, Chromium, the three servers, teardown;
# main's d6d61fb spent 3.2 minutes outside its tests) plus the shard's summed file minutes.
E2E_FIXED_MIN = 3.2


def _job(workflow: str, job: str) -> tuple[int, int]:
    """(matrix size, timeout-minutes) of a workflow's sharded job."""
    spec = yaml.safe_load((WORKFLOWS / workflow).read_text())["jobs"][job]
    return len(spec["strategy"]["matrix"]["shard"]), int(spec["timeout-minutes"])


def verdict(name: str, minutes: list[float], limit: int) -> tuple[str, str]:
    """('ok' | 'warn' | 'fail', a line for the summary) for a job's predicted shard minutes."""
    worst = max(minutes)
    mean = sum(minutes) / len(minutes)
    share = worst / limit
    level = "fail" if share > FAIL_SHARE else "warn" if share > WARN_SHARE else "ok"
    line = (
        f"{name}: slowest shard {worst:.1f} of {limit} minutes ({share:.0%}), "
        f"slowest / mean {worst / mean:.2f}; shards " + ", ".join(f"{m:.1f}" for m in minutes)
    )
    return level, line


def _report(level: str, line: str) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if level != "ok":
        text = f"{line}. Over {WARN_SHARE:.0%}: rebalance or add a shard (docs/ci.md)."
        if summary:
            with open(summary, "a") as f:
                f.write(f"**CI shard guard ({level})**: {text}\n\n")
        warnings.warn(text, stacklevel=2)
    assert level != "fail", line


def backend_minutes(nodeids: list[str], durations: dict[str, float], shards: int) -> list[float]:
    known = [durations[n] for n in nodeids if n in durations]
    default = sum(known) / len(known) if known else 1.0
    weight = [0.0] * shards
    for n, k in shard_of(nodeids, durations, shards).items():
        weight[k] += durations.get(n, default) + SHARD_OVERHEAD_S
    return [
        CHECK_FIXED_MIN + CHECK_EXTRA_MIN.get(k + 1, 0.0) + CHECK_FACTOR * w / 60
        for k, w in enumerate(weight)
    ]


def playwright_shards(files: list[str], seconds: dict[str, float], total: int) -> dict[str, int]:
    """frontend/e2e/shard-reporter.ts's assignShards: heaviest first (ties by name), each to the
    lightest shard so far (ties: the lowest)."""
    known = [seconds[f] for f in files if f in seconds]
    fallback = sum(known) / len(known) if known else 1.0
    sums = [0.0] * total
    out: dict[str, int] = {}
    for f in sorted(files, key=lambda f: (-seconds.get(f, fallback), f)):
        k = min(range(total), key=lambda i: (sums[i], i))
        out[f] = k
        sums[k] += seconds.get(f, fallback)
    return out


def e2e_files() -> list[str]:
    return sorted(
        p.relative_to(E2E_DIR).as_posix()
        for p in E2E_DIR.rglob("*.spec.ts")
        if "playtest" not in p.relative_to(E2E_DIR).parts
    )


def playwright_minutes(files: list[str], seconds: dict[str, float], shards: int) -> list[float]:
    known = [seconds[f] for f in files if f in seconds]
    fallback = sum(known) / len(known) if known else 1.0
    sums = [0.0] * shards
    for f, k in playwright_shards(files, seconds, shards).items():
        sums[k] += seconds.get(f, fallback)
    return [E2E_FIXED_MIN + s / 60 for s in sums]


def test_check_shards_fit_their_limit(request: pytest.FixtureRequest) -> None:
    nodeids = request.config.stash.get(CHECK_TESTS, [])
    if len(nodeids) < 1000:
        pytest.skip("a partial run: the guard needs the whole `check` collection")
    shards, limit = _job("check.yml", "shard")
    durations = json.loads(DURATIONS_FILE.read_text())
    _report(*verdict("check", backend_minutes(nodeids, durations, shards), limit))


def test_e2e_shards_fit_their_limit() -> None:
    shards, limit = _job("e2e.yml", "shard")
    seconds = json.loads((E2E_DIR / "durations.json").read_text())
    _report(*verdict("e2e", playwright_minutes(e2e_files(), seconds, shards), limit))


def test_every_e2e_file_has_a_measured_time() -> None:
    """A new spec file counts as the mean file until the nightly measures it: a warning."""
    seconds = json.loads((E2E_DIR / "durations.json").read_text())
    files = e2e_files()
    missing = [f for f in files if f not in seconds]
    gone = [f for f in seconds if f not in files]
    if missing or gone:
        _report("warn", f"e2e/durations.json: no time for {missing}, times for removed {gone}")


@pytest.mark.parametrize(
    ("minutes", "level"),
    [
        ([10.0, 20.0, 21.0], "ok"),  # 70% of 30 exactly
        ([10.0, 21.1], "warn"),
        ([27.0, 20.0], "warn"),  # 90% exactly
        ([27.1, 20.0], "fail"),
    ],
)
def test_the_guard_warns_at_70_and_fails_at_90_percent(minutes: list[float], level: str) -> None:
    assert verdict("x", minutes, 30)[0] == level


def test_a_warning_reaches_the_job_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    with pytest.warns(UserWarning, match="rebalance"):
        _report(*verdict("check", [22.0, 10.0], 30))
    assert "CI shard guard (warn)" in summary.read_text()
    with pytest.raises(AssertionError), pytest.warns(UserWarning):
        _report(*verdict("check", [28.0, 10.0], 30))
    assert "CI shard guard (fail)" in summary.read_text()


def test_the_e2e_split_covers_every_file_once() -> None:
    files = e2e_files()
    seconds = json.loads((E2E_DIR / "durations.json").read_text())
    split = playwright_shards(files, seconds, 4)
    assert sorted(split) == files
    assert set(split.values()) == {0, 1, 2, 3}
