"""M18's balance targets (docs/formulas.md 34.6), printed by tools/m18_targets.py.

An explorer is a stage-3 player company with a team of geologists at a chosen skill and cash to
spend. The scripted explorer plays the pipeline as a sensible player would: a desk study per
(region, commodity) it targets, licences on the high-band blocks, a survey on each, sampling
where an anomaly shows, drilling where the sample's upper grade could pay, and studies and a
permit while the NPV range stays above zero. Only the exploration phase runs each month (with
the founder's energy reset), so the targets measure exploration alone; the full turn is covered
by the integration tests."""

from __future__ import annotations

import math
import statistics
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Final

from tst.balance.game import start_game
from tst.loader import LoadedData
from tst.sim.actions import Action, ActionResult, apply_action
from tst.sim.errors import SimError
from tst.sim.exploration import formulas as xf
from tst.sim.exploration import pipeline as xp
from tst.sim.exploration.geology import block_of
from tst.sim.exploration.models import Project
from tst.sim.exploration.phase import exploration_month, exploration_step
from tst.sim.exploration.pipeline import (
    OrderDrilling,
    RelinquishProject,
    RenewLicence,
    StartDeskStudy,
    StartStage,
    TakeLicence,
)
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry, apply_entries
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    reach_stage,
    with_company,
    with_employment,
    with_person,
    with_person_state,
)

PLAYER: Final = 1
ENERGY: Final = 10_000  # the script's founder never runs out (exploration alone)
CASH_CENTS: Final = 100_000_000_000  # $1B: the script never runs short (spend is measured)
# Where a sensible explorer looks for each commodity first: dossier 2's leading regions.
TARGETS: Final = (
    ("latin_america", "copper"),
    ("oceania", "lithium_carbonate"),
    ("africa", "cobalt"),
    ("east_asia", "ndpr_oxide"),
    ("africa", "copper"),
    ("latin_america", "lithium_carbonate"),
    ("north_america", "quartz_hp"),
    ("south_southeast_asia", "tin"),
    ("africa", "tantalum"),
    ("north_america", "ndpr_oxide"),
    ("latin_america", "tin"),
    ("north_america", "copper"),
)
LICENCES_PER_STUDY: Final = 4
FIRST_HOLES: Final = 20
INFILL_HOLES: Final = 20
STUDY_MEMOS: Final = (
    "Exploration scoping",
    "Exploration pre-feasibility",
    "Exploration definitive",
    "Community and permits",
)


def explorer(
    loaded: LoadedData, seed: int, skill: float, geologists: int = 4, cash: int = CASH_CENTS
) -> tuple[GameState, dict[tuple[int, str], int]]:
    """A new game's player at stage 3 with `geologists` geologists whose geology and data
    skills are `skill`, and `cash` more in the bank."""
    game = start_game(loaded, seed)
    state = with_company(game.state, reach_stage(game.state.player, 3, 0))
    state = add_geologists(state, loaded, skill, geologists)
    balances = dict(game.balances)
    balances[(PLAYER, CASH)] = balances.get((PLAYER, CASH), 0) + cash
    balances[(PLAYER, COMMON_EQUITY)] = balances.get((PLAYER, COMMON_EQUITY), 0) - cash
    return state, balances


def add_geologists(state: GameState, loaded: LoadedData, skill: float, n: int) -> GameState:
    """`n` senior geologists on the player's staff, their geology and data at `skill`."""
    role = loaded.game_data.role(loaded.balance.exploration.geologist_role)
    rng = RngFactory(state.save_meta.master_seed)
    for i in range(n):
        pid, ids = state.next_ids.take("person")
        eid, ids = ids.take("employment")
        state = replace(state, next_ids=ids)
        person = generate_person(
            rng.stream(0, "misc", 300 + i),
            loaded.game_data,
            loaded.balance,
            state.turn,
            role,
            "senior",
            "oceania",
            person_id=pid,
        )
        person = replace(person, skills=person.skills.updated({"geology": skill, "data": skill}))
        state = with_person(state, person)
        state = with_employment(
            state,
            Employment(
                eid, pid, PLAYER, role.key, "senior", 10_000_000, 0, state.turn, None, "active"
            ),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=65.0))
    return state


@dataclass
class Run:
    loaded: LoadedData
    state: GameState
    balances: dict[tuple[int, str], int]
    seq: int = 0
    spent: int = 0
    study_spent: int = 0  # feasibility studies and permits: development, not discovery
    protest_answer: str = "benefit"
    log: Counter[str] = field(default_factory=Counter)
    posted: list[LedgerEntry] = field(default_factory=list)

    @property
    def founder(self) -> int:
        f = self.state.founder_of(PLAYER)
        assert f is not None
        return f.id

    def act(self, action: Action) -> ActionResult | None:
        self.seq += 1
        try:
            out = apply_action(
                self.state,
                action,
                RngFactory(self.state.save_meta.master_seed),
                self.loaded.balance,
                self.loaded.game_data,
                self.balances,
                seq=self.seq,
            )
        except SimError:
            self.log[f"refused {action.kind}"] += 1
            return None
        self._post(out.new_state, out.ledger_entries)
        return out

    def _post(self, state: GameState, entries: tuple[LedgerEntry, ...]) -> None:
        self.state = state
        self.balances = apply_entries(self.balances, entries)
        self.posted += entries
        for e in entries:
            if e.company_id != PLAYER:
                continue
            cents = sum(x.amount for x in e.lines if x.account == "6600_exploration")
            self.spent += cents
            if e.memo.startswith(STUDY_MEMOS):
                self.study_spent += cents

    def month(self) -> None:
        b, d = self.loaded.balance, self.loaded.game_data
        ps = self.state.person_state(self.founder)
        self.state = with_person_state(self.state, replace(ps, energy=ENERGY))
        state, entries, _ = exploration_month(
            self.state, RngFactory(self.state.save_meta.master_seed), b, d
        )
        self._post(state, entries)
        # A protest is answered at once (the event's month is the next one).
        for p in self.state.projects:
            if p.protest_turn is not None:
                from tst.sim.events.models import GameEvent

                event = GameEvent(
                    id=0,
                    company_id=p.company_id,
                    turn=p.protest_turn,
                    template_id="community_blockade",
                    category="exploration",
                    severity="critical",
                    trigger="exploration",
                    strength=1.0,
                )
                nxt = replace(self.state, turn=p.protest_turn)
                state, posted, _ = exploration_step(nxt, event, self.protest_answer, b, d)
                self._post(replace(state, turn=self.state.turn), tuple(posted))
        self.state = replace(self.state, turn=self.state.turn + 1)


def _npv_if(run: Run, project: Project, grade: float, tonnage: float | None = None) -> float:
    d, b = run.loaded.game_data, run.loaded.balance
    assert d.geology is not None and project.commodity is not None
    c = d.geology.commodity(project.commodity)
    kind = project.kind or next(iter(d.geology.kinds_of(project.region, c.key)))
    infra = math.sqrt(b.geology.infra_km[0] * b.geology.infra_km[1])
    depth = sum(b.geology.depth_m) / 2
    return xp.mine_npv_usd(
        run.state,
        c,
        tonnage if tonnage is not None else c.tonnage_median_mt,
        grade,
        sum(c.recovery) / 2,
        kind,
        infra,
        depth,
        1.0,
        1.0,
        b,
        d,
    )


def step_projects(run: Run) -> None:
    """The script's decisions for each open project with nothing running."""
    for project in list(run.state.projects):
        project = xp.project_of(run.state, project.id)
        if not project.is_open or project.stage is not None or project.holes_left:
            continue
        pid, me = project.id, run.founder
        holes = len(xp.holes_of(run.state, pid))
        if project.expires_turn - run.state.turn <= 6 and not project.renewals:
            run.act(RenewLicence(me, pid))
        if project.reading is None:
            run.act(StartStage(me, pid, "survey"))
        elif project.reading == "none":
            run.act(RelinquishProject(me, pid))
            run.log["nothing: no anomaly"] += 1
        elif project.sample_center is None:
            run.act(StartStage(me, pid, "sampling"))
        elif holes == 0:
            assert project.sample_hw is not None
            upper = math.exp(project.sample_center + project.sample_hw)
            if _npv_if(run, project, upper) > 0:
                run.act(OrderDrilling(me, pid, FIRST_HOLES))
            else:
                run.act(RelinquishProject(me, pid))
                run.log["nothing: low sample"] += 1
        elif project.category is None:
            run.act(StartStage(me, pid, "estimate"))
        elif project.category == "indicated" and project.level is None:
            run.act(StartStage(me, pid, "scoping"))
        elif project.level == "scoping":
            if (project.npv_mid_cents or 0) > 0:
                if holes < FIRST_HOLES + INFILL_HOLES:
                    run.act(OrderDrilling(me, pid, INFILL_HOLES))
                elif project.category != "measured":
                    run.act(StartStage(me, pid, "estimate"))
                else:  # a scoping study that pays goes straight to the definitive study
                    run.act(StartStage(me, pid, "definitive"))
            else:
                run.act(RelinquishProject(me, pid))
                run.log["nothing: scoping"] += 1
        elif project.level == "pre_feasibility":
            if (project.npv_mid_cents or 0) > 0:
                run.act(StartStage(me, pid, "definitive"))
            else:
                run.act(RelinquishProject(me, pid))
                run.log["nothing: pre-feasibility"] += 1
        elif project.level == "definitive" and project.permit_start is None:
            if (project.npv_mid_cents or 0) > 0:
                run.act(StartStage(me, pid, "permitting"))
            else:
                run.act(RelinquishProject(me, pid))
                run.log["nothing: definitive"] += 1


def play(
    loaded: LoadedData,
    seed: int,
    skill: float,
    years: int = 14,
    targets: tuple[tuple[str, str], ...] = TARGETS,
    geologists: int = 4,
    search_years: int = 7,
) -> Run:
    """`search_years` of desk studies and new licences, then play to `years` so the projects
    found finish their studies and permits."""
    state, balances = explorer(loaded, seed, skill, geologists)
    run = Run(loaded, state, balances)
    pending = list(targets)
    for month in range(years * 12):
        me = run.founder
        if month >= search_years * 12:
            pending = []
        if pending:
            region, commodity = pending[0]
            if run.act(StartDeskStudy(me, region, commodity)) is not None:
                pending.pop(0)
        for study in run.state.desk_studies if month < search_years * 12 else ():
            if study.done and not run.log[f"licenced {study.id}"]:
                run.log[f"licenced {study.id}"] = 1
                order = [i for i, band in enumerate(study.bands) if band == "high"]
                taken = 0
                for i in order:
                    if taken >= LICENCES_PER_STUDY:
                        break
                    if run.act(TakeLicence(me, study.region, i)) is not None:
                        taken += 1
        step_projects(run)
        run.month()
    return run


# --- Targets ---------------------------------------------------------------------------------


def convergence(loaded: LoadedData, seeds: range, skill: float = 10.0) -> dict[int, float]:
    """34.6 target 1: the median +/-% of the grade range after n holes over every deposit of
    the explored commodities on `seeds`, drilled by a team at `skill`."""
    b, d = loaded.balance, loaded.game_data
    assert d.geology is not None
    out: dict[int, list[float]] = {20: [], 40: []}
    f = xf.range_factor(skill, b.exploration)
    for seed in seeds:
        state = start_game(loaded, seed).state
        for block in state.geo_blocks:
            if block.true_commodity is None:
                continue
            c = d.geology.commodity(block.true_commodity)
            assays, factors = [], []
            project = Project(
                0, PLAYER, block.region, block.index, 0, 60, commodity=block.true_commodity
            )
            for n in range(1, 41):
                hole = _hole(state, project, n, f, loaded)
                assays.append(hole)
                factors.append(f)
                if n in out:
                    _, hw = xf.grade_estimate(
                        assays, factors, c.hole_sd, b.geology.cells, b.exploration.confidence
                    )
                    out[n].append(xf.half_width_pct(hw))
    return {n: statistics.median(v) for n, v in out.items()}


def _hole(state: GameState, project: Project, n: int, f: float, loaded: LoadedData) -> float:
    from tst.sim.exploration.geology import GEOLOGY_TURN, cell_deviations

    b, d = loaded.balance, loaded.game_data
    assert d.geology is not None and project.commodity is not None
    block = block_of(state, project.region, project.block)
    assert block is not None
    c = d.geology.commodity(project.commodity)
    r = d.region_keys.index(project.region)
    rng = RngFactory(state.save_meta.master_seed)
    devs = cell_deviations(rng, r, project.block, b.geology.cells)
    perm = rng.stream(GEOLOGY_TURN, "geology", r, project.block, xp.PERM_TAG).permutation(
        b.geology.cells
    )
    return math.exp(
        math.log(block.true_grade) + f * c.hole_sd * devs[int(perm[(n - 1) % len(devs)])]
    )


@dataclass(frozen=True)
class Summary:
    feasible: int  # projects whose definitive study's NPV midpoint is above zero
    permitted: int
    spent: int  # cents on exploration
    discovery: int  # of which before feasibility studies (desk, licences, survey to estimate)
    surveyed: int
    nothing: int  # surveyed blocks that ended without a feasible project
    permit_months: tuple[int, ...]  # licence to permit, per permitted project
    log: Counter[str]


def summarise(run: Run) -> Summary:
    projects = run.state.projects
    surveyed = [p for p in projects if p.reading is not None]
    feasible = [p for p in projects if p.level == "definitive" and (p.npv_mid_cents or 0) > 0]
    permitted = [p for p in projects if p.status == "permitted"]
    nothing = [p for p in surveyed if p not in feasible]
    months = tuple((p.permit_turn or 0) - p.licence_turn + 1 for p in permitted)
    return Summary(
        len(feasible),
        len(permitted),
        run.spent,
        run.spent - run.study_spent,
        len(surveyed),
        len(nothing),
        months,
        run.log,
    )


def permit_months(loaded: LoadedData, seeds: range) -> dict[str, float]:
    """34.6 target 5: the median months from application to decision, by region, over every
    block on `seeds` (the hidden draw, before protests)."""
    out: dict[str, list[int]] = {}
    b, d = loaded.balance, loaded.game_data
    for seed in seeds:
        state = start_game(loaded, seed).state
        rng = RngFactory(seed)
        for i, block in enumerate(state.geo_blocks):
            project = Project(i + 1, PLAYER, block.region, block.index, 0, 60)
            got = xp._apply_permit(state, project, rng, b, d)
            assert got.hidden_due_turn is not None
            out.setdefault(block.region, []).append(got.hidden_due_turn + 1)
    return {r: statistics.median(v) for r, v in out.items()}


def leaders(loaded: LoadedData, seeds: range) -> dict[str, Counter[str]]:
    """34.6 target 4: per commodity, the region with the most feasible deposits (true NPV at
    the deck above zero) on each seed; a tie counts for no region."""
    b, d = loaded.balance, loaded.game_data
    out: dict[str, Counter[str]] = {}
    for seed in seeds:
        state = start_game(loaded, seed).state
        ec = [
            x for x in state.geo_blocks if x.true_commodity and xp.true_npv_usd(state, x, b, d) > 0
        ]
        for c in ("copper", "lithium_carbonate", "cobalt", "ndpr_oxide"):
            cnt = Counter(x.region for x in ec if x.true_commodity == c).most_common(2)
            top = cnt[0][0] if cnt and (len(cnt) == 1 or cnt[0][1] > cnt[1][1]) else "tie"
            out.setdefault(c, Counter())[top] += 1
    return out


# --- The report (tools/m18_targets.py) ---------------------------------------------------------

SKILLS: Final = (8.0, 12.0, 15.0)
TYPICAL: Final = 12.0  # target 3's team
TEAM: Final = 6  # geologists in the scripted explorer's team


def _play_one(args: tuple[int, float]) -> tuple[int, float, Summary]:
    from pathlib import Path

    from tst.loader import load_all

    seed, skill = args
    loaded = load_all(Path(__file__).resolve().parents[2] / "data")
    return seed, skill, summarise(play(loaded, seed, skill, geologists=TEAM))


def unchanged(loaded: LoadedData, seeds: tuple[int, ...], turns: int = 24) -> bool:
    """Target 6: a company that never explores plays exactly as before. The same game played
    with its geology and without (as a save from before M18): identical month ends."""
    for seed in seeds:
        runs = []
        for strip in (False, True):
            game = start_game(loaded, seed)
            if strip:
                game.state = replace(game.state, geo_blocks=(), supplier_licences=())
            for _ in range(turns):
                game.turn()
            runs.append(game.snapshots)
        if runs[0] != runs[1]:
            return False
    return True


@dataclass(frozen=True)
class Results:
    seeds: tuple[int, ...]
    convergence: dict[int, float]
    plays: dict[float, list[Summary]]
    leaders: dict[str, Counter[str]]
    permit: dict[str, float]
    unchanged: bool
    coverage_note: str = "tests/property/test_m18_estimates.py (30 seeds)"


def run(seeds: tuple[int, ...], jobs: int) -> Results:
    from concurrent.futures import ProcessPoolExecutor
    from pathlib import Path

    from tst.loader import load_all

    loaded = load_all(Path(__file__).resolve().parents[2] / "data")
    plays: dict[float, list[Summary]] = {s: [] for s in SKILLS}
    tasks = [(seed, skill) for skill in SKILLS for seed in seeds]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for _, skill, summary in pool.map(_play_one, tasks):
            plays[skill].append(summary)
    return Results(
        seeds=seeds,
        convergence=convergence(loaded, range(seeds[0], seeds[-1] + 1), skill=10.0),
        plays=plays,
        leaders=leaders(loaded, range(seeds[0], seeds[-1] + 1)),
        permit=permit_months(loaded, range(seeds[0], seeds[-1] + 1)),
        unchanged=unchanged(loaded, seeds[:2]),
    )


def _per_dollar(rows: list[Summary], discovery: bool) -> float:
    spent = sum(r.discovery if discovery else r.spent for r in rows)
    return sum(r.feasible for r in rows) / spent if spent else 0.0


def report(r: Results) -> str:
    def mark(ok: bool) -> str:
        return "PASS" if ok else "MISS"

    out = [f"M18 targets (docs/formulas.md 34.6), seeds {r.seeds[0]}-{r.seeds[-1]}"]
    c20, c40 = r.convergence[20], r.convergence[40]
    out.append(
        f"1. Estimates converge (skill-10 team, every deposit): 20 holes +/-{c20:.1%} (<= 15%), "
        f"40 holes +/-{c40:.1%} (<= 8%)  {mark(c20 <= 0.15 and c40 <= 0.08)}"
    )
    weak, strong = r.plays[8.0], r.plays[15.0]
    disc = _per_dollar(strong, True) / max(_per_dollar(weak, True), 1e-12)
    total = _per_dollar(strong, False) / max(_per_dollar(weak, False), 1e-12)
    from pathlib import Path

    from tst.loader import load_all

    eb = load_all(Path(__file__).resolve().parents[2] / "data").balance.exploration
    narrower = 1 - xf.range_factor(15, eb) / xf.range_factor(8, eb)
    out.append(
        f"2. Geologists matter: skill 15 vs 8 finds feasible projects {disc:.2f}x as often per "
        f"dollar of discovery spend ({total:.2f}x per dollar of all spend), ranges "
        f"{narrower:.0%} narrower  {mark(1.5 <= disc <= 2.5 and 0.25 <= narrower <= 0.40)}"
    )
    typical = r.plays[TYPICAL]
    per = sorted(x.spent / x.permitted / 100 / 1e6 for x in typical if x.permitted)
    months = sorted(m for x in typical for m in x.permit_months)
    surveyed = sum(x.surveyed for x in typical)
    nothing = sum(x.nothing for x in typical) / surveyed if surveyed else 0.0
    med = statistics.median(per) if per else float("inf")
    med_years = statistics.median(months) / 12 if months else float("inf")
    feasible = sum(x.feasible for x in typical)
    out.append(
        f"3. A gamble (skill-12 team): median spend ${med:.0f}M per permitted project "
        f"($20-60M), licence to permit {med_years:.1f} years (3-8), {nothing:.0%} of surveyed "
        f"blocks end in nothing (>= 40%); 1 in {surveyed / max(feasible, 1):.0f} surveyed blocks "
        f"becomes feasible  {mark(20 <= med <= 60 and 3 <= med_years <= 8 and nothing >= 0.4)}"
    )
    expected = {
        "copper": "latin_america",
        "lithium_carbonate": "oceania",
        "cobalt": "africa",
        "ndpr_oxide": "east_asia",
    }
    n = len(r.seeds)
    parts, ok4 = [], True
    for c, region in expected.items():
        hits = r.leaders[c][region]
        ok4 &= hits >= 0.7 * n
        parts.append(f"{c} {region} {hits}/{n}")
    out.append(f"4. Geography is real: {', '.join(parts)} (>= 7 of 10)  {mark(ok4)}")
    na, la = r.permit["north_america"], r.permit["latin_america"]
    out.append(
        f"5. Permits vary: median {na:.0f} months in North America vs {la:.0f} in Latin "
        f"America ({na / la:.2f}x, >= 1.5x)  {mark(na >= 1.5 * la)}"
    )
    out.append(
        f"6. Nothing else moves: a game that never explores plays identically with and without "
        f"geology (24 months, 2 seeds); golden snapshots unchanged  {mark(r.unchanged)}"
    )
    out.append(f"Ranges hold their stated confidence: {r.coverage_note}")
    return "\n".join(out)
