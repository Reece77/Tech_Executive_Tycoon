"""Investigations (docs/formulas.md 48.3), from `regulation.start`.

**Openings.** Each month each regulator may open a case on each group with books that has at
least `investigation.min_revenue_cents` a year of revenue in its region and at least one cause:
a share above `regulation.dominance_share` in a market there (users of its platforms, or a
category's customers), a designation there, self-preferencing on its platforms there, removals
of other companies' apps from its store in the last year, a duty it breaches, or a complaint
(an app taken to regulators about its store in the last `complaint_months`). The chance is

`base x dominance x designated x self_pref x removals x fee_high x acquisitions x noncompliance x
ruthless x complaint x strictness x (1 - influence_cut x I / 100) x compliant`, at most
`max_chance` (a factor applies only when its cause holds; I is 32.5's influence in the region).

One uniform (stream `regulation`, key (0, regulator index, *stable key)) decides it. The chance
and the draw are never stored or shown (48.6).

**Stages.** An inquiry (6-12 months) ends in a statement of objections (a complaint in the US)
with a chance drawn inside `odds.proceed`, else it closes. The objections stage (6-12 months) ends
in a ruling. A ruling goes against the company with a chance drawn inside `odds.ruling_against`
(the range shown), x (1 - lobby_cut x influence / 100), x (1 - complied_cut) for a company
complying with every duty there. Against: a fine of a share drawn inside `fine.share` of the
group's trailing-year turnover (x `noncompliance_mult` while it breaches a duty), capped by the
regime's `max_fine_share` (its `repeat_fine_share` after another ruling against within 10 years),
posted to 6970; and a behavioural remedy, a duty named by the case's conduct. A ruling may
instead be structural (tst.sim.regulation.structural). An appeal (12-36 months) wins on a chance
drawn inside `odds.appeal_win`: the fine comes back and the remedy lapses.

**The player** answers each stage through an event: at the inquiry (major: cooperate, settle,
lobby), at the objections and the ruling (critical: settle, contest or lobby; comply or appeal).
**Rivals** settle at the objections unless their personality is in `rivals.contest`, which also
appeal a ruling against them.

History's cases to 2025 are regulation.yaml's (data); the model's cases start in 2026."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import QueuedEvent
from tst.sim.founder import influence
from tst.sim.founder.persona import strong
from tst.sim.ledger import CASH, FINES, LOBBYING, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.platforms import data as pdata
from tst.sim.regulation import data as rdata
from tst.sim.regulation import draws
from tst.sim.regulation.config import Conduct, DutyKind, RegulatorDef
from tst.sim.regulation.designate import designated_by
from tst.sim.regulation.duties import add_duty, breaches, platforms_in
from tst.sim.regulation.measure import View
from tst.sim.regulation.models import Case, CaseOutcome, CaseStage
from tst.sim.rivals.models import stream_key
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, owner_of, with_queued

INQUIRY: Final = "regulation_inquiry"  # template ids (data/events/regulation.yaml)
OBJECTIONS: Final = "regulation_objections"
RULING: Final = "regulation_ruling"
LINK: Final = "regulation"
PCT: Final = 100  # tunable-exempt: influence is 0-100
MIDDLE: Final = 0.5  # tunable-exempt: the middle of a range (a settlement's typical fine)
REMEDY: Final[dict[str, DutyKind]] = {  # a ruling's behavioural remedy by conduct (48.3)
    "self_preferencing": "no_self_preferencing",
    "anti_steering": "anti_steering",
    "removals": "interoperability",
    "fees": "fee_cap",
    "acquisitions": "data_portability",
    "tying": "interoperability",
    "exclusivity": "side_loading",
    "dominance": "interoperability",
}


def stable(state: GameState, company_id: int) -> tuple[int, ...]:
    c = state.company(company_id)
    return stream_key(c.id, c.rival_key)


def open_case(state: GameState, company_id: int, regulator: str) -> Case | None:
    return next(
        (
            c
            for c in state.reg_cases
            if c.company_id == company_id and c.regulator == regulator and c.stage != "closed"
        ),
        None,
    )


def next_case_id(state: GameState) -> int:
    return max([0, *(c.id for c in state.reg_cases)]) + 1


def with_case(state: GameState, case: Case) -> GameState:
    cases = tuple(case if c.id == case.id else c for c in state.reg_cases)
    if all(c.id != case.id for c in state.reg_cases):
        cases = (*cases, case)
    return replace(state, reg_cases=cases)


# --- Causes and the chance (engine-side only) -------------------------------------------------


def causes(
    state: GameState, owner: int, reg: RegulatorDef, v: View, balance: Balance, data: GameData
) -> dict[str, float]:
    """The causes that hold for the group in the regulator's region, each with its factor."""
    ib = balance.regulation.investigation
    region = reg.region
    out: dict[str, float] = {}
    share, _ = v.max_share(owner, region)
    if share > balance.regulation.dominance_share:
        out["dominance"] = ib.dominance
    if designated_by(state, data, owner, reg.key):
        out["designated"] = ib.designated
    owned = platforms_in(state, owner, region)
    pref = max((ib.self_pref.get(p.self_pref, 1.0) for p in owned), default=1.0)
    if pref > 1:
        out["self_preferencing"] = pref
    ids = {p.id for p in owned}
    year_ago = state.turn - MONTHS_PER_YEAR
    group = {c.id for c in state.companies if owner_of(state, c.id) == owner}
    if any(
        x.platform_id in ids and x.status == "removed" and x.since_turn > year_ago
        and (prod := state.product(x.product_id)) is not None and prod.company_id not in group
        for x in state.platform_listings
    ):  # fmt: skip
        out["removals"] = ib.removals
    if breaches(state, owner, reg):
        out["noncompliance"] = ib.noncompliance
    complaint_from = state.turn - ib.complaint_months
    if any(
        x.platform_id in ids and x.status == "regulators" and x.since_turn > complaint_from
        and x.region == region
        for x in state.platform_listings
    ):  # fmt: skip
        out["complaint"] = ib.complaint
    if not out:
        return out
    if any(
        pdata.schedule(p, region, state.turn, balance, data).standard > ib.fee_high_above
        for p in owned
    ):
        out["fees"] = ib.fee_high
    since = state.turn - ib.acquisition_months
    if any(a.acquirer_id in group and a.closed_turn > since for a in state.acquisitions):
        out["acquisitions"] = ib.acquisitions
    if strong(state, owner, "ruthless", balance):
        out["ruthless"] = ib.ruthless
    return out


def chance(
    state: GameState,
    owner: int,
    reg: RegulatorDef,
    v: View,
    balance: Balance,
    data: GameData,
    found: dict[str, float] | None = None,
) -> float:
    """The month's chance a regulator opens a case on the group (module docstring)."""
    ib = balance.regulation.investigation
    found = causes(state, owner, reg, v, balance, data) if found is None else found
    if not found or v.region_year(owner, reg.region) < ib.min_revenue_cents:
        return 0.0
    c = ib.base * rdata.strictness(reg, state.turn)
    for factor in found.values():
        c *= factor
    c *= 1 - ib.influence_cut * influence.of(state, owner, reg.region) / PCT
    if "designated" in found and "noncompliance" not in found:
        c *= ib.compliant
    return min(ib.max_chance, max(0.0, c))


def conduct_of(found: dict[str, float]) -> Conduct:
    for key, conduct in (
        ("noncompliance", "noncompliance"),
        ("self_preferencing", "self_preferencing"),
        ("removals", "removals"),
        ("complaint", "anti_steering"),
        ("fees", "fees"),
        ("acquisitions", "acquisitions"),
    ):
        if key in found:
            return conduct  # type: ignore[return-value]
    return "dominance"


# --- Openings ---------------------------------------------------------------------------------


def openings(
    state: GameState, rng: RngFactory, v: View, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    ib = balance.regulation.investigation
    logs: list[LogItem] = []
    owners = sorted({owner_of(state, c.id) for c in state.ledger_companies()})
    for i, reg in enumerate(rdata.file(data).regulators):
        for owner in owners:
            if open_case(state, owner, reg.key) is not None:
                continue
            last = [
                c.closed_turn
                for c in state.reg_cases
                if c.company_id == owner and c.regulator == reg.key and c.closed_turn is not None
            ]
            if last and max(last) > state.turn - ib.cooldown_months:
                continue
            found = causes(state, owner, reg, v, balance, data)
            c = chance(state, owner, reg, v, balance, data, found)
            if c <= 0:
                continue
            gen = draws.gen(rng, state.turn, draws.OPEN, i, *stable(state, owner))
            if float(gen.random()) >= c:
                continue
            _, market = v.max_share(owner, reg.region)
            conduct = conduct_of(found)
            breached = breaches(state, owner, reg)
            remedy = (
                breached[0]
                if conduct == "noncompliance" and breached
                else REMEDY.get(conduct, "interoperability")
            )
            case = Case(
                id=next_case_id(state),
                regulator=reg.key,
                company_id=owner,
                conduct=conduct,
                market=market or "devices",
                opened_turn=state.turn,
                stage="inquiry",
                stage_turn=state.turn,
                due_turn=state.turn,
                remedy=remedy,
                noncompliant=bool(breached),
                steps=(("inquiry", state.turn),),
            )
            case = replace(case, due_turn=state.turn + _length(rng, case, state.turn, balance))
            state = with_case(state, case)
            state, more = _tell(state, case, INQUIRY, data)
            logs += more
    return state, logs


def _length(rng: RngFactory, case: Case, turn: int, balance: Balance) -> int:
    sb = balance.regulation.stages
    lo, hi = {
        "inquiry": sb.inquiry_months,
        "objections": sb.objections_months,
        "appeal": sb.appeal_months,
    }.get(case.stage, (1, 1))
    gen = draws.gen(rng, turn, draws.CASE, case.id, draws.STAGE_LENGTH)
    return lo + int(gen.integers(hi - lo + 1))


def _tell(
    state: GameState, case: Case, template: str, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """The player's event on a stage (queued for next month); a rival's case is news."""
    if case.company_id != state.player.id:
        return state, []
    qid, ids = state.next_ids.take("queued")
    state = with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid,
            company_id=case.company_id,
            template_id=template,
            due_turn=state.turn + 1,
            source_event_id=None,
        ),
    )
    case = replace(case, asked_turn=state.turn + 1, asked_template=template)
    return with_case(state, case), []


# --- Stages -----------------------------------------------------------------------------------


def stages_month(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for case in sorted(state.reg_cases, key=lambda c: c.id):
        case = next(c for c in state.reg_cases if c.id == case.id)
        if case.stage in ("closed", "ruling") or case.due_turn > state.turn:
            continue
        if _waiting(state, case):
            continue  # the player's answer to this stage's event is still open
        if case.stage == "inquiry":
            gen = draws.gen(rng, state.turn, draws.CASE, case.id, draws.OUTCOME)
            lo, hi = balance.regulation.odds.proceed
            odds = lo + (hi - lo) * float(gen.random())
            if float(gen.random()) >= odds:
                state, more = close(state, case, "dismissed", data)
                logs += more
                continue
            case = _advance(state, case, "objections", rng, balance)
            state = with_case(state, case)
            state, more = _tell(state, case, OBJECTIONS, data)
            logs += more
            state, more_e, more_l = rival_answer(state, case, "objections", rng, balance, data)
            entries += more_e
            logs += more_l
        elif case.stage == "objections":
            state, more_e, more_l = rule(state, case, rng, balance, data)
            entries += more_e
            logs += more_l
        elif case.stage == "appeal":
            gen = draws.gen(rng, state.turn, draws.CASE, case.id, draws.OUTCOME)
            lo, hi = balance.regulation.odds.appeal_win
            odds = lo + (hi - lo) * float(gen.random())
            won = float(gen.random()) < odds
            if won:
                if case.fine_cents > 0:
                    entries.append(_refund(state, case))
                state = replace(
                    state,
                    duties=tuple(
                        d
                        for d in state.duties
                        if not (d.case_id == case.id and d.source == "remedy")
                    ),
                )
                state, more = close(state, case, "annulled", data)
            else:
                state, more = close(state, case, case.outcome, data)
            logs += more
    return state, entries, logs


def _waiting(state: GameState, case: Case) -> bool:
    if case.company_id != state.player.id or case.asked_turn is None:
        return False
    if case.asked_turn > state.turn:
        return True
    return any(
        e.company_id == case.company_id
        and e.turn >= case.asked_turn
        and e.template_id == case.asked_template
        and e.is_open
        for e in state.events
    )


def _advance(
    state: GameState, case: Case, stage: CaseStage, rng: RngFactory, balance: Balance
) -> Case:
    case = replace(
        case,
        stage=stage,
        stage_turn=state.turn,
        steps=(*case.steps, (stage, state.turn)),
    )
    return replace(case, due_turn=state.turn + _length(rng, case, state.turn, balance))


def close(
    state: GameState, case: Case, outcome: CaseOutcome, data: GameData
) -> tuple[GameState, list[LogItem]]:
    case = replace(
        case,
        stage="closed",
        outcome=outcome,
        closed_turn=state.turn,
        steps=(*case.steps, (outcome, state.turn)),
    )
    state = with_case(state, case)
    logs = []
    if case.company_id == state.player.id:
        reg = rdata.file(data).regulator(case.regulator)
        logs.append(
            inbox_item(
                state.turn,
                case.company_id,
                "regulation_case_closed",
                link_kind=LINK,
                regulator=reg.name,
                outcome=outcome,
                market=case.market.replace("_", " "),
            )
        )
    return state, logs


def ruling_odds(
    state: GameState, case: Case, reg: RegulatorDef, u: float, balance: Balance
) -> float:
    """A contested ruling's chance against the company, from a uniform `u` in the shown range."""
    ob = balance.regulation.odds
    lo, hi = ob.ruling_against
    odds = lo + (hi - lo) * u
    infl = min(
        float(PCT),
        influence.of(state, case.company_id, reg.region)
        + case.lobbied * balance.regulation.stages.lobby_influence,
    )
    odds *= 1 - ob.lobby_cut * infl / PCT
    if not breaches(state, case.company_id, reg) and any(
        d.from_turn <= state.turn for d in state.duties
        if d.company_id == case.company_id and d.regulator == reg.key
    ):  # fmt: skip
        odds *= 1 - ob.complied_cut
    return odds


def fine_cents(
    state: GameState, case: Case, reg: RegulatorDef, u: float, balance: Balance, data: GameData
) -> int:
    """The fine (module docstring), from a uniform `u` inside `fine.share`."""
    fb = balance.regulation.fine
    lo, hi = fb.share
    share = lo + (hi - lo) * u
    if breaches(state, case.company_id, reg) or case.noncompliant:
        share *= fb.noncompliance_mult
    regime = rdata.regime_of(data, reg.key)
    cap = regime.max_fine_share if regime is not None else fb.default_max_share
    if repeat(state, case, balance, data):
        cap = regime.repeat_fine_share if regime is not None else fb.default_max_share
    turnover = sum(
        sum(c.mrr_history[-MONTHS_PER_YEAR:])
        for c in state.companies
        if owner_of(state, c.id) == case.company_id
    )
    return round(min(share, cap) * turnover)


def rulings_against(state: GameState, data: GameData, company_id: int, regulator: str) -> list[int]:
    """Months of rulings against the company by the regulator: the model's and history's."""
    own = [
        c.ruled_turn
        for c in state.reg_cases
        if c.company_id == company_id and c.regulator == regulator and c.ruled_turn is not None
        and c.outcome != "annulled"
    ]  # fmt: skip
    return sorted(own + rdata.history_rulings(state, data, company_id, regulator, state.turn))


def repeat(state: GameState, case: Case, balance: Balance, data: GameData) -> bool:
    """Another ruling against within `structural.two_rulings_years` (the DMA's repeat window)."""
    ten_years = state.turn - balance.regulation.structural.two_rulings_years * MONTHS_PER_YEAR
    return any(t > ten_years for t in rulings_against(state, data, case.company_id, case.regulator))


def rule(
    state: GameState, case: Case, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """The objections stage ends in a ruling (module docstring)."""
    from tst.sim.regulation import structural

    reg = rdata.file(data).regulator(case.regulator)
    gen = draws.gen(rng, state.turn, draws.CASE, case.id, draws.OUTCOME)
    odds = ruling_odds(state, case, reg, float(gen.random()), balance)
    if float(gen.random()) >= odds:
        state, closed = close(state, case, "dismissed", data)
        return state, [], closed
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    if structural.may_order(state, case, reg, balance, data):
        sgen = draws.gen(rng, state.turn, draws.CASE, case.id, draws.STRUCTURAL)
        if float(sgen.random()) < balance.regulation.structural.chance:
            case = replace(
                case, ruled_turn=state.turn, outcome="structural",
                steps=(*case.steps, ("ruling", state.turn)),
            )  # fmt: skip
            state = with_case(state, case)
            state, more = structural.order(state, case, reg, balance, data)
            state, more_logs = close(state, case, "structural", data)
            return state, [], [*more, *more_logs]
    fgen = draws.gen(rng, state.turn, draws.CASE, case.id, draws.FINE)
    fine = fine_cents(state, case, reg, float(fgen.random()), balance, data)
    outcome: CaseOutcome = "fined" if fine > 0 else "remedied"
    case = replace(
        case,
        stage="ruling",
        stage_turn=state.turn,
        due_turn=state.turn,
        ruled_turn=state.turn,
        fine_cents=fine,
        outcome=outcome,
        steps=(*case.steps, ("ruling", state.turn)),
    )
    state = with_case(state, case)
    if fine > 0:
        entries.append(_fine(state, case, fine, "Fine"))
    if case.remedy is not None:
        state = add_duty(
            state, case.company_id, reg.key, case.remedy, state.turn, "remedy", data, balance,
            case_id=case.id,
        )  # fmt: skip
    state, more = _tell(state, case, RULING, data)
    logs += more
    state, more_e, more_l = rival_answer(state, case, "ruling", rng, balance, data)
    return state, entries + more_e, logs + more_l


def _fine(state: GameState, case: Case, cents: int, what: str) -> LedgerEntry:
    reg = case.regulator.replace("_", " ")
    return LedgerEntry.transfer(
        turn=state.turn,
        company_id=case.company_id,
        memo=f"{what}: {reg} case {case.id}",
        debit=FINES,
        credit=CASH,
        amount=cents,
    )


def _refund(state: GameState, case: Case) -> LedgerEntry:
    return LedgerEntry.transfer(
        turn=state.turn,
        company_id=case.company_id,
        memo=f"Fine annulled on appeal: case {case.id}",
        debit=CASH,
        credit=FINES,
        amount=case.fine_cents,
    )


# --- Answers (the player's through events, rivals' here) -------------------------------------


def settle(
    state: GameState, case: Case, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Commitments end the case: the remedy as a duty now (the breached setting put right), and
    at the objections stage `fine.settle_share` of the fine's middle."""
    reg = rdata.file(data).regulator(case.regulator)
    entries = []
    if case.stage == "objections":
        lo, hi = balance.regulation.fine.share
        full = fine_cents(state, case, reg, MIDDLE, balance, data) if hi > lo else 0
        cents = round(full * balance.regulation.fine.settle_share)
        if cents > 0:
            entries.append(_fine(state, case, cents, "Settlement"))
            case = replace(case, fine_cents=cents)
    if case.remedy is not None:
        state = add_duty(
            state, case.company_id, reg.key, case.remedy, state.turn, "commitment", data, balance,
            case_id=case.id,
        )  # fmt: skip
    for kind in breaches(state, case.company_id, reg):
        state = add_duty(
            state, case.company_id, reg.key, kind, state.turn, "commitment", data, balance,
            case_id=case.id,
        )  # fmt: skip
        from tst.sim.regulation.duties import apply, duties_of

        for d in duties_of(state, case.company_id, reg.key):
            if d.kind == kind:
                state = apply(state, d, balance, data)
    state = with_case(state, case)
    state, logs = close(state, case, "settled", data)
    return state, entries, logs


def contest(state: GameState, case: Case) -> GameState:
    return with_case(state, replace(case, contested=True))


def lobby(state: GameState, case: Case, balance: Balance) -> tuple[GameState, list[LedgerEntry]]:
    sb = balance.regulation.stages
    case = replace(
        case,
        contested=True,
        lobbied=case.lobbied + 1,
        due_turn=case.due_turn + sb.lobby_delay_months,
    )
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=case.company_id,
        memo=f"Lobbying on case {case.id}",
        debit=LOBBYING,
        credit=CASH,
        amount=sb.lobby_cents,
    )
    return with_case(state, case), [entry] if sb.lobby_cents > 0 else []


def appeal(state: GameState, case: Case, rng: RngFactory, balance: Balance) -> GameState:
    case = _advance(state, case, "appeal", rng, balance)
    return with_case(state, case)


def comply(state: GameState, case: Case, data: GameData) -> tuple[GameState, list[LogItem]]:
    return close(state, case, case.outcome, data)


def rival_answer(
    state: GameState,
    case: Case,
    stage: str,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """A rival's answer (module docstring): by personality, no draw."""
    if case.company_id == state.player.id:
        return state, [], []
    case = next(c for c in state.reg_cases if c.id == case.id)
    fights = state.company(case.company_id).personality in balance.regulation.rivals.contest
    if stage == "objections":
        if fights:
            return contest(state, case), [], []
        return settle(state, case, balance, data)
    if stage == "ruling":
        if fights:
            return appeal(state, case, rng, balance), [], []
        state, logs = comply(state, case, data)
        return state, [], logs
    return state, [], []
