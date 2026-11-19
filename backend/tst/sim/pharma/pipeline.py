"""Molecules and the pipeline (docs/formulas.md 55.1-55.2).

A programme starts in discovery, moves through preclinical work and Phase I-III trials, and is
filed (approval.py). Discovery and preclinical flow on by themselves; each trial starts when the
company chooses its design (lean, standard or large: patients, months and a small lift to the
chance). A stage's cost (patients x cost per patient by area and modality, plus fixed, at the
game's scale) is spent evenly to its planned end; then it reads out.

The readout's chance (hidden; never shown):

    p = sigmoid(logit(T_area,stage) + w_e,stage x (efficacy - mean) / sd
                + w_s,stage x (safety - mean) / sd + design + AI lift (Phase I and II))

and it observes efficacy with noise (shown once read out). The chance shown is the same formula
on the estimate so far (the prior's mean before any readout) +/- `readout.shown_band`.

A failed readout leaves the programme to be redesigned (the stage re-run at its cost x (1 +
`redesign_cost_share`), with a fresh draw) or stopped. Programmes a rival owns (licensed out)
run on their own: each trial starts at the standard design, a failure stops it."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.ledger import CASH, LICENSE_REVENUE, RESEARCH, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.pharma import data as pd
from tst.sim.pharma import draws
from tst.sim.pharma.config import TRIALS, Design
from tst.sim.pharma.models import Programme, Readout
from tst.sim.research import levels
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

DOMAIN: Final = "drug_discovery"  # tunable-exempt: tech_frontier.yaml domain key
AI_CATEGORY: Final = "ai_models"  # tunable-exempt: categories.yaml key (55.2)
AUTO: Final = ("discovery",)  # stages that move on without a choice when they succeed
DESIGN_POS: Final = {"lean": 0.0, "standard": 0.5, "large": 1.0}  # tunable-exempt: range positions


def logit(p: float) -> float:
    return dmath.log(p / (1 - p))


def sigmoid(x: float) -> float:
    return 1 / (1 + dmath.exp(-x))


def clamp01(x: float) -> float:
    return min(1.0, max(0.0, x))


# --- the company's capabilities (55.1, 55.2) ------------------------------------------------


def dd_level(state: GameState, company_id: int, balance: Balance, data: GameData) -> float:
    """The company's drug_discovery level over the world's baseline (0 without the domain)."""
    if data.tech is None or not any(d.key == DOMAIN for d in data.tech.domains):
        return 0.0
    return levels.lead(state, company_id, DOMAIN)


def best_ai_quality(state: GameState, company_id: int) -> float:
    return max(
        (
            p.quality
            for p in state.company_products(company_id)
            if p.category == AI_CATEGORY and p.status in ("live", "sunset")
        ),
        default=0.0,
    )


def ai_ready(state: GameState, company_id: int, balance: Balance, data: GameData) -> bool:
    """AI discovery (55.2): from AlphaFold 2's month, with an ai_models product of at least
    `ai.min_quality` or a drug_discovery lead of at least `ai.min_level`."""
    ab = balance.pharma.ai
    if state.turn < month_to_turn(pd.file(data).ai.from_month):
        return False
    return (
        best_ai_quality(state, company_id) >= ab.min_quality
        or dd_level(state, company_id, balance, data) >= ab.min_level
    )


def researchers(state: GameState, company_id: int, balance: Balance) -> int:
    roles = set(balance.pharma.discovery.roles)
    return sum(1 for e in state.staff(company_id) if e.role in roles)


def discovery_slots(state: GameState, company_id: int, balance: Balance, data: GameData) -> int:
    """Programmes the company can hold in discovery at once (55.1): a base, one more for every
    `researchers_per_slot` research scientists and data scientists, more with drug_discovery
    lead, and x (1 + `ai_slots`) with AI discovery."""
    db = balance.pharma.discovery
    n = db.slots_base + researchers(state, company_id, balance) / db.researchers_per_slot
    n += db.level_slots * dd_level(state, company_id, balance, data) / pd.CENTS
    if ai_ready(state, company_id, balance, data):
        n *= 1 + db.ai_slots
    return int(n)


def in_discovery(state: GameState, company_id: int) -> int:
    return sum(
        1
        for p in state.pharma_programmes
        if p.company_id == company_id and p.stage == "discovery" and p.status == "active"
    )


# --- stages ---------------------------------------------------------------------------------


def stage_months(p: Programme, stage: str, design: Design, balance: Balance, data: GameData) -> int:
    """A stage's planned months (the design, shown): the range's midpoint x the area's factor x
    the design's, cut by AI discovery (preclinical, 55.2) and breakthrough (Phase III)."""
    sd = pd.file(data).stages.of(stage)
    m = (sd.months[0] + sd.months[1]) / 2
    if stage in TRIALS:
        m *= pd.area(data, p.area).months_mult * balance.pharma.readout.design_months[design]
    ab = balance.pharma.ai
    if p.ai and stage == "preclinical":
        m *= 1 - ab.preclinical_cut
    if p.breakthrough and stage == "phase3":
        m *= 1 - balance.pharma.approval.breakthrough_cut
    return max(1, round(m))


def stage_patients(stage: str, design: Design, data: GameData) -> int:
    lo, hi = pd.file(data).stages.of(stage).patients
    return round(lo + (hi - lo) * DESIGN_POS[design])


def stage_cost_cents(
    p: Programme, stage: str, patients: int, months: int, balance: Balance, data: GameData
) -> int:
    """Real cost x pharma.scale: patients x cost per patient x the area's and the modality's
    factors, plus fixed (discovery and preclinical: fixed a month)."""
    sd = pd.file(data).stages.of(stage)
    if stage in TRIALS:
        mult = pd.area(data, p.area).cost_mult * pd.modality(data, p.modality).cost_mult
        return pd.cents(patients * sd.cost_per_patient * mult + sd.fixed, balance)
    return pd.cents(sd.fixed * months, balance)


def base_rate(p: Programme, stage: str, data: GameData) -> float:
    if stage == "preclinical":
        return pd.file(data).preclinical_success
    return pd.area(data, p.area).transitions.of(stage)


def _logit(
    p: Programme,
    stage: str,
    design: Design,
    efficacy: float,
    safety: float,
    balance: Balance,
    data: GameData,
) -> float:
    rb = balance.pharma.readout
    eb, sb = balance.pharma.efficacy, balance.pharma.safety
    x = logit(base_rate(p, stage, data))
    x += rb.efficacy_weight.get(stage, 0.0) * (efficacy - eb.mean) / eb.sd
    x += rb.safety_weight.get(stage, 0.0) * (safety - sb.mean) / sb.sd
    x += rb.design_logit[design] if stage in TRIALS else 0.0
    if p.ai and stage in ("phase1", "phase2"):
        x += balance.pharma.ai.transition_lift
    return x


def chance(p: Programme, stage: str, design: Design, balance: Balance, data: GameData) -> float:
    """The readout's true chance from the hidden values (never shown, 55.7)."""
    lo, hi = balance.pharma.readout.bounds
    return min(hi, max(lo, sigmoid(_logit(p, stage, design, p.efficacy, p.safety, balance, data))))


def estimate(p: Programme, balance: Balance) -> tuple[float, float]:
    """The public efficacy and safety estimates: the readouts' means, or the prior's."""
    if p.obs_n == 0:
        return balance.pharma.efficacy.mean, balance.pharma.safety.mean
    return p.obs_eff, p.obs_safety


def estimate_range(p: Programme, balance: Balance) -> tuple[float, float]:
    """Efficacy shown as a range (55.7): the estimate +/- two standard errors of the readouts'
    noise, or the prior's two sds before any readout."""
    est, _ = estimate(p, balance)
    if p.obs_n == 0:
        half = 2 * balance.pharma.efficacy.sd
    else:
        sd = balance.pharma.readout.noise[p.stage if p.stage in TRIALS else "phase1"]
        half = 2 * sd / dmath.pow(p.obs_n, 0.5)  # tunable-exempt: a standard error's root
    return clamp01(est - half), clamp01(est + half)


def shown_chance(
    p: Programme, stage: str, design: Design, balance: Balance, data: GameData
) -> tuple[float, float]:
    """The chance shown (55.7): the readout formula on the public estimates, +/- the band."""
    rb = balance.pharma.readout
    eff, saf = estimate(p, balance)
    c = sigmoid(_logit(p, stage, design, eff, saf, balance, data))
    lo, hi = rb.bounds
    return max(lo, c - rb.shown_band), min(hi, c + rb.shown_band)


# --- starting and running -------------------------------------------------------------------


def draw_molecule(
    gen_turn: int,
    rng: RngFactory,
    family: int,
    key: tuple[int, ...],
    *,
    ai: bool,
    lead: float,
    balance: Balance,
) -> tuple[float, float]:
    """A molecule's hidden efficacy and safety (55.1): normal around the means, efficacy's lifted
    by drug_discovery lead and AI discovery, clamped to [0, 1]."""
    g = draws.gen(rng, gen_turn, family, *key)
    eb, sb = balance.pharma.efficacy, balance.pharma.safety
    mean = eb.mean + eb.level_lift * lead / pd.CENTS + (eb.ai_lift if ai else 0.0)
    eff = clamp01(mean + eb.sd * float(g.standard_normal()))
    saf = clamp01(sb.mean + (sb.ai_lift if ai else 0.0) + sb.sd * float(g.standard_normal()))
    return eff, saf


def next_id(state: GameState) -> int:
    return max((p.id for p in state.pharma_programmes), default=0) + 1


def start_programme(
    state: GameState,
    company_id: int,
    name: str,
    indication: str,
    modality: str,
    use_ai: bool,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LogItem]]:
    """A new programme in discovery (55.1)."""
    from tst.sim.errors import PharmaRuleError

    ind = pd.indication(data, indication)
    pd.modality(data, modality)
    if in_discovery(state, company_id) >= discovery_slots(state, company_id, balance, data):
        raise PharmaRuleError("no discovery capacity: hire research scientists or wait")
    if use_ai and not ai_ready(state, company_id, balance, data):
        raise PharmaRuleError("AI discovery needs a strong AI model or drug discovery research")
    pid = next_id(state)
    eff, saf = draw_molecule(
        state.turn,
        rng,
        draws.MOLECULE,
        (pid,),
        ai=use_ai,
        lead=dd_level(state, company_id, balance, data),
        balance=balance,
    )
    p = Programme(
        id=pid,
        company_id=company_id,
        name=name,
        indication=ind.key,
        area=ind.area,
        modality=modality,  # type: ignore[arg-type]
        stage="discovery",
        start_turn=state.turn,
        due_turn=state.turn,
        efficacy=eff,
        safety=saf,
        ai=use_ai,
    )
    months = stage_months(p, "discovery", "standard", balance, data)
    p = replace(
        p,
        due_turn=state.turn + months,
        cost_cents=stage_cost_cents(p, "discovery", 0, months, balance, data),
    )
    state = replace(state, pharma_programmes=(*state.pharma_programmes, p))
    log = inbox_item(
        state.turn,
        company_id,
        "pharma_programme_started",
        link_kind="pharma",
        link_id=pid,
        name=name,
        indication=ind.label,
        months=months,
    )
    return state, [log]


def begin_stage(
    state: GameState,
    p: Programme,
    stage: str,
    design: Design,
    balance: Balance,
    data: GameData,
    *,
    redo: bool = False,
) -> Programme:
    """The programme starts `stage` this month with `design` (a trial) or as planned."""
    turn = state.turn
    patients = stage_patients(stage, design, data) if stage in TRIALS else 0
    months = stage_months(p, stage, design, balance, data)
    cost = stage_cost_cents(p, stage, patients, months, balance, data)
    if redo:
        cost = round(cost * (1 + balance.pharma.redesign_cost_share))
    return replace(
        p,
        stage=stage,  # type: ignore[arg-type]
        status="active",
        design=design,
        patients=patients,
        start_turn=turn,
        due_turn=turn + months,
        cost_cents=cost,
        spent_cents=0,
        attempt=p.attempt + 1 if redo else 0,
        patent_turn=turn if stage == "preclinical" and p.patent_turn is None else p.patent_turn,
        ind_turn=turn if stage == "phase1" and p.ind_turn is None else p.ind_turn,
    )


def with_programme(state: GameState, p: Programme) -> GameState:
    return replace(
        state,
        pharma_programmes=tuple(p if q.id == p.id else q for q in state.pharma_programmes),
    )


def _spend(state: GameState, p: Programme) -> tuple[Programme, list[LedgerEntry]]:
    """A running stage's month of spending (and a partner's share back, 55.5)."""
    months = max(1, p.due_turn - p.start_turn)
    left = p.cost_cents - p.spent_cents
    amount = left if state.turn >= p.due_turn - 1 else min(left, p.cost_cents // months)
    if amount <= 0:
        return p, []
    entries = [
        LedgerEntry.transfer(
            turn=state.turn,
            company_id=p.company_id,
            memo=f"{p.name}: {p.stage}",
            debit=RESEARCH,
            credit=CASH,
            amount=amount,
        )
    ]
    if p.partner_id is not None and p.partner_share > 0:
        share = round(amount * p.partner_share)
        entries += [
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=p.partner_id,
                memo=f"Co-development: {p.name}",
                debit=RESEARCH,
                credit=CASH,
                amount=share,
            ),
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=p.company_id,
                memo=f"Partner's share: {p.name}",
                debit=CASH,
                credit=LICENSE_REVENUE,
                amount=share,
            ),
        ]
    return replace(p, spent_cents=p.spent_cents + amount), entries


def read_out(
    state: GameState, p: Programme, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """The stage reads out (55.1): success drawn from the hidden values; efficacy observed."""
    stage = p.stage
    turn = state.turn
    if stage == "discovery":  # a candidate is found: preclinical work starts
        nxt = begin_stage(state, p, "preclinical", "standard", balance, data)
        log = inbox_item(
            turn, p.company_id, "pharma_candidate", link_kind="pharma", link_id=p.id, name=p.name
        )
        return with_programme(state, nxt), [log]
    lo, hi = shown_chance(p, stage, p.design, balance, data)
    g = draws.gen(rng, turn, draws.READOUT, p.id, pd.stage_index(stage), p.attempt)
    ok = float(g.random()) < chance(p, stage, p.design, balance, data)
    noise = balance.pharma.readout.noise.get(stage, 0.0)
    seen = clamp01(p.efficacy + noise * float(g.standard_normal()))
    seen_safety = clamp01(p.safety + noise * float(g.standard_normal()))
    n = p.obs_n + 1
    p2 = replace(
        p,
        obs_n=n,
        obs_eff=(p.obs_eff * p.obs_n + seen) / n,
        obs_safety=(p.obs_safety * p.obs_n + seen_safety) / n,
        spent_cents=p.cost_cents,
    )
    rid = max((r.id for r in state.pharma_readouts), default=0) + 1
    rec = Readout(rid, p.id, stage, turn, ok, lo, hi, seen, p.design)
    state = replace(state, pharma_readouts=(*state.pharma_readouts, rec))
    if ok:
        p2 = replace(p2, status="ready")
        p2 = _designations(p2, stage, balance, data, turn)
        template = "pharma_readout_success"
    else:
        p2 = replace(p2, status="failed")
        template = "pharma_readout_failed"
    log = inbox_item(
        turn,
        p.company_id,
        template,
        link_kind="pharma",
        link_id=p.id,
        name=p.name,
        stage=stage,
    )
    return with_programme(state, p2), [log]


def _designations(
    p: Programme, stage: str, balance: Balance, data: GameData, turn: int
) -> Programme:
    """Breakthrough therapy after a strong Phase II (from FDASIA's month; 55.3)."""
    if stage != "phase2":
        return p
    ind = pd.indication(data, p.indication)
    rev = pd.review_def(data, pd.us_regulator(data).key)
    if rev.breakthrough_from is None or turn < month_to_turn(rev.breakthrough_from):
        return p
    if p.obs_eff - ind.soc >= balance.pharma.approval.breakthrough_margin:
        return replace(p, breakthrough=True)
    return p


def next_trial(p: Programme) -> str | None:
    """The stage a ready programme may start next (None: it is ready to file)."""
    if p.stage == "preclinical":
        return "phase1"
    if p.stage in ("phase1", "phase2"):
        return pd.next_stage(p.stage)
    return None


def month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Every running stage spends its month and reads out at its planned end; rivals' licensed
    programmes start their next trial or stop."""
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    players = {c.id for c in state.companies if c.is_player}
    for p in sorted(state.pharma_programmes, key=lambda q: q.id):
        p = next(q for q in state.pharma_programmes if q.id == p.id)
        if p.status == "active" and p.stage in ("discovery", "preclinical", *TRIALS):
            p, e = _spend(state, p)
            entries += e
            state = with_programme(state, p)
            if state.turn >= p.due_turn:
                state, lg = read_out(state, p, rng, balance, data)
                logs += lg
        elif p.company_id not in players:
            state = _rival_step(state, p, balance, data)
    return state, entries, logs


def _rival_step(state: GameState, p: Programme, balance: Balance, data: GameData) -> GameState:
    """A rival's licensed programme: the next trial at the standard design, or stop."""
    if p.status == "failed":
        return with_programme(state, replace(p, status="stopped", ended_turn=state.turn))
    if p.status == "ready" and (nxt := next_trial(p)) is not None:
        return with_programme(state, begin_stage(state, p, nxt, "standard", balance, data))
    return state
