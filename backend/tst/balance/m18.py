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
from tst.sim.ledger import CASH, COMMON_EQUITY, apply_entries
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
    role = loaded.game_data.role(loaded.balance.exploration.geologist_role)
    rng = RngFactory(seed)
    for i in range(geologists):
        pid, ids = state.next_ids.take("person")
        eid, ids = ids.take("employment")
        state = replace(state, next_ids=ids)
        person = generate_person(
            rng.stream(0, "misc", 300 + i),
            loaded.game_data,
            loaded.balance,
            0,
            role,
            "senior",
            "oceania",
            person_id=pid,
        )
        person = replace(person, skills=person.skills.updated({"geology": skill, "data": skill}))
        state = with_person(state, person)
        state = with_employment(
            state,
            Employment(eid, pid, PLAYER, role.key, "senior", 10_000_000, 0, 0, None, "active"),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=65.0))
    balances = dict(game.balances)
    balances[(PLAYER, CASH)] = balances.get((PLAYER, CASH), 0) + cash
    balances[(PLAYER, COMMON_EQUITY)] = balances.get((PLAYER, COMMON_EQUITY), 0) - cash
    return state, balances


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

    def _post(self, state: GameState, entries: tuple) -> None:  # type: ignore[type-arg]
        self.state = state
        self.balances = apply_entries(self.balances, entries)
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


def _npv_if(
    run: Run, project: xp.Project, grade: float, tonnage: float | None = None
) -> float:
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
            project = xp.Project(0, PLAYER, block.region, block.index, 0, 60,
                                 commodity=block.true_commodity)
            for n in range(1, 41):
                hole = _hole(state, project, n, f, loaded)
                assays.append(hole)
                factors.append(f)
                if n in out:
                    _, hw = xf.grade_estimate(assays, factors, c.hole_sd, b.geology.cells,
                                              b.exploration.confidence)
                    out[n].append(xf.half_width_pct(hw))
    return {n: statistics.median(v) for n, v in out.items()}


def _hole(state: GameState, project: xp.Project, n: int, f: float, loaded: LoadedData) -> float:
    from tst.sim.exploration.geology import GEOLOGY_TURN, cell_deviations

    b, d = loaded.balance, loaded.game_data
    assert d.geology is not None and project.commodity is not None
    block = xp.block_of(state, project.region, project.block)
    assert block is not None
    c = d.geology.commodity(project.commodity)
    r = d.region_keys.index(project.region)
    rng = RngFactory(state.save_meta.master_seed)
    devs = cell_deviations(rng, r, project.block, b.geology.cells)
    perm = rng.stream(GEOLOGY_TURN, "geology", r, project.block, xp.PERM_TAG).permutation(
        b.geology.cells
    )
    return math.exp(math.log(block.true_grade) + f * c.hole_sd * devs[int(perm[(n - 1) % len(devs)])])


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
    return Summary(len(feasible), len(permitted), run.spent, run.spent - run.study_spent, len(surveyed), len(nothing), months,
                   run.log)


def permit_months(loaded: LoadedData, seeds: range) -> dict[str, float]:
    """34.6 target 5: the median months from application to decision, by region, over every
    block on `seeds` (the hidden draw, before protests)."""
    out: dict[str, list[int]] = {}
    b, d = loaded.balance, loaded.game_data
    for seed in seeds:
        state = start_game(loaded, seed).state
        rng = RngFactory(seed)
        for i, block in enumerate(state.geo_blocks):
            project = xp.Project(i + 1, PLAYER, block.region, block.index, 0, 60)
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
        ec = [x for x in state.geo_blocks
              if x.true_commodity and xp.true_npv_usd(state, x, b, d) > 0]
        for c in ("copper", "lithium_carbonate", "cobalt", "ndpr_oxide"):
            cnt = Counter(x.region for x in ec if x.true_commodity == c).most_common(2)
            top = cnt[0][0] if cnt and (len(cnt) == 1 or cnt[0][1] > cnt[1][1]) else "tie"
            out.setdefault(c, Counter())[top] += 1
    return out
