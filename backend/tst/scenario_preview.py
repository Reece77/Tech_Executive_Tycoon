"""The editor's preview and difficulty estimate (M52 sub-task 3, docs/formulas.md 66.1).

**Preview:** a custom scenario's start month built in memory as a new save would build it (no
turn is played and nothing is saved): the company (cash, debt, staff, products, research), its
rivals by category (incumbents present or removed, added ones) and the markets it sells in.
Everything shown is what the player could see in that game.

**Difficulty:** on request, the scripted sensible player (`tst.balance.m51`'s script for the
scenario it was opened from; v1's steady for any other) plays the start on each of
`editor.preview_seeds` until the goal's verdict or `editor.preview_months`, in memory. The
estimate is the wins of those seeds (rated as M51 rates ten: `challenges.difficulty_wins`
scaled to the seeds), with the company score each reached. It runs in a background thread
(`start_job`, `job`), one job a spec hash at a time.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Final, Literal

from tst import scenario_files as sf
from tst.balance.game import Game
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.ledger import CASH
from tst.sim.modes.custom import custom_key
from tst.sim.modes.custom_config import CustomScenario
from tst.sim.products.models import SELLING

log = logging.getLogger(__name__)

DEBT: Final = "2500_debt"  # accounts.yaml: loans' principal
TOP_RIVALS: Final = 6  # rivals shown a category in the preview, by customers

type JobStatus = Literal["running", "done", "failed"]


@dataclass(frozen=True, slots=True)
class ProductLine:
    name: str
    category: str
    status: str
    quality: float
    customers: float


@dataclass(frozen=True, slots=True)
class RivalLine:
    name: str
    category: str
    quality: float  # its best product's in the category
    customers: float
    added: bool  # added by the editor


@dataclass(frozen=True, slots=True)
class Preview:
    label: str
    start_label: str
    cash_cents: int
    debt_cents: int
    staff: dict[str, int]  # role -> people (the founder included)
    products: tuple[ProductLine, ...]
    research: dict[str, float]
    rivals: tuple[RivalLine, ...]
    removed: tuple[str, ...]  # incumbents the scenario removes
    goal: str | None
    deadline_label: str | None
    challenges: tuple[str, ...]
    length: str


def start(loaded: LoadedData, spec: CustomScenario, seed: int) -> Game:
    from tst.balance.m52 import start_custom

    return start_custom(loaded, spec, seed)


def _customers(game: Game, product_id: int) -> float:
    s = game.state
    return sum(x.customers for x in s.segments_of(product_id)) + sum(
        x.customers for x in s.regional_segments_of(product_id)
    )


def summary(game: Game, spec: CustomScenario) -> Preview:
    s = game.state
    pid = s.player.id
    staff = Counter(e.role for e in s.employments if e.company_id == pid and e.end_turn is None)
    products = tuple(
        ProductLine(p.name, p.category, p.status, p.quality, _customers(game, p.id))
        for p in s.company_products(pid)
    )
    research = {r.domain: r.lead for r in s.research_leads if r.company_id == pid}
    mine = {p.category for p in s.company_products(pid)}
    from tst.sim.modes.custom import CUSTOM_KEY

    rivals: list[RivalLine] = []
    for category in sorted(mine):
        lines = []
        for c in s.rivals():
            if not c.alive:
                continue
            sold = [
                p
                for p in s.company_products(c.id)
                if p.category == category and p.status in SELLING
            ]
            if sold:
                best = max(sold, key=lambda p: p.quality)
                lines.append(
                    RivalLine(
                        c.name,
                        category,
                        best.quality,
                        sum(_customers(game, p.id) for p in sold),
                        c.rival_key[:1] == (CUSTOM_KEY,),
                    )
                )
        lines.sort(key=lambda r: (-r.customers, r.name))
        rivals.extend(lines[:TOP_RIVALS])
    removed = tuple(sorted(n for n, r in spec.overrides.rivals.items() if not r.present))
    deadline = None
    if spec.deadline is not None:
        from tst.sim.calendar import ym_to_turn

        deadline = format_turn(ym_to_turn(*spec.deadline))
    return Preview(
        label=spec.label,
        start_label=format_turn(s.turn),
        cash_cents=game.balances.get((pid, CASH), 0),
        debt_cents=-game.balances.get((pid, DEBT), 0),
        staff=dict(sorted(staff.items())),
        products=products,
        research=dict(sorted(research.items())),
        rivals=tuple(rivals),
        removed=removed,
        goal=spec.goal.text if spec.goal is not None else None,
        deadline_label=deadline,
        challenges=spec.overrides.rules.challenges,
        length=spec.length,
    )


def preview(loaded: LoadedData, spec: CustomScenario, seed: int = 1) -> Preview:
    """The start month's summary (66.1): built in memory, no turn played, nothing saved."""
    return summary(start(loaded, spec, seed), spec)


# --- The difficulty estimate (background) -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class SeedResult:
    seed: int
    result: str | None  # success | failure | None (no goal, or no verdict in the months played)
    month_label: str
    score: int | None


@dataclass
class Job:
    id: str
    sha256: str
    seeds: tuple[int, ...]
    status: JobStatus = "running"
    results: list[SeedResult] = field(default_factory=list)
    error: str | None = None

    @property
    def wins(self) -> int:
        return sum(1 for r in self.results if r.result == "success")

    def difficulty(self, loaded: LoadedData) -> str | None:
        """easy | medium | hard, M51's ten-seed bands scaled to the seeds played; None until
        done, or when the scenario has no goal."""
        if self.status != "done" or not self.results or all(r.result is None for r in self.results):
            return None
        hard, medium = loaded.balance.challenges.difficulty_wins
        per_ten = self.wins * 10 / len(self.seeds)  # tunable-exempt: M51's bands are of ten
        if per_ten <= hard:
            return "hard"
        return "medium" if per_ten <= medium else "easy"


_JOBS: dict[str, Job] = {}
_LOCK = threading.Lock()


def script_for(spec: CustomScenario) -> object:
    from tst.balance import m51
    from tst.balance.strategies import steady

    scripts = m51.SCRIPTS.get(spec.opened_from or "")
    return scripts["sensible"] if scripts is not None else steady


def play_seed(loaded: LoadedData, spec: CustomScenario, seed: int) -> SeedResult:
    script = script_for(spec)
    assert callable(script)
    game = start(loaded, spec, seed)
    first = game.state.turn
    months = loaded.balance.editor.preview_months
    while game.state.turn < first + months and not game.state.ended:
        mode = game.state.mode
        if mode is not None and mode.result is not None:
            break
        script(game)
        game.turn()
    mode = game.state.mode
    pid = game.state.player.id
    score = next((x.score for x in reversed(game.state.scores) if x.company_id == pid), None)
    turn = (
        mode.result_turn if mode is not None and mode.result_turn is not None else game.state.turn
    )
    return SeedResult(seed, mode.result if mode is not None else None, format_turn(turn), score)


def _run(job: Job, loaded: LoadedData, spec: CustomScenario) -> None:
    try:
        for seed in job.seeds:
            result = play_seed(loaded, spec, seed)
            with _LOCK:
                job.results.append(result)
        job.status = "done"
    except Exception as exc:  # a job never takes the app down; the editor shows the reason
        log.exception("Difficulty estimate for %s failed", custom_key(spec.key))
        job.error = str(exc)
        job.status = "failed"


def start_job(loaded: LoadedData, spec: CustomScenario) -> Job:
    """The estimate for `spec`: the running or finished job for the same file text, else a new
    one in a background thread."""
    digest = sf.sha256(spec)
    with _LOCK:
        for j in _JOBS.values():
            if j.sha256 == digest and j.status != "failed":
                return j
        job = Job(uuid.uuid4().hex, digest, tuple(loaded.balance.editor.preview_seeds))
        _JOBS[job.id] = job
    threading.Thread(target=_run, args=(job, loaded, spec), daemon=True).start()
    return job


def job(job_id: str) -> Job | None:
    with _LOCK:
        return _JOBS.get(job_id)
