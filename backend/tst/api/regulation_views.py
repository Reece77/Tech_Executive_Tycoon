"""The Regulation screen's data (M34, docs/formulas.md 48.6). Public facts only: regulators and
their regimes' thresholds and duties, designations (history's and the model's), duties,
investigations with their stages as visible steps and each stage's window as a range, rulings,
fines, warning signs, orders and precedents; the player's own position against the thresholds.

Never an opening's chance or draw (none is stored), a stage's drawn end (`Case.due_turn`), an
outcome's chance, a regulator's strictness index or path, or a history case's later steps before
their month."""

from __future__ import annotations

from typing import Final

from tst.api.schemas.regulation import (
    CaseOut,
    DesignationOut,
    DutyOut,
    ExplainOut,
    OrderOut,
    PrecedentOut,
    RegimeOut,
    RegulationOut,
    RegulatorOut,
    StepOut,
    TestOut,
    WarningSignOut,
    WatchOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.facilities.config import month_to_turn
from tst.sim.ledger import FINES, LedgerBalances
from tst.sim.regulation import data as rdata
from tst.sim.regulation import structural
from tst.sim.regulation.answers import CONDUCT_WORDS
from tst.sim.regulation.designate import is_designated, ratio
from tst.sim.regulation.duties import breaches
from tst.sim.regulation.measure import view
from tst.sim.state import GameState, group_companies, owner_of

DUTY_WORDS: Final = {
    "side_loading": "allow other app stores and side-loading",
    "alt_payments": "allow alternative payment systems",
    "anti_steering": "let apps link to pay outside",
    "interoperability": "open interfaces to rivals' devices and services",
    "no_self_preferencing": "no self-preferencing of its own apps",
    "data_portability": "let users take their data elsewhere",
    "fee_cap": "cap the store's fee",
}
SIGN_WORDS: Final = {
    "press": "press coverage calls for a break-up",
    "report": "a regulator's report names the remedy",
    "political": "lawmakers press the regulator",
    "board": "the board raises the risk",
}
STAGE_WINDOW: Final = {"inquiry": "inquiry_months", "objections": "objections_months"}


def _name(state: GameState, company_id: int | None, label: str = "") -> str:
    if company_id is None:
        return label
    return next((c.name for c in state.companies if c.id == company_id), label)


def _regulators(data: LoadedData) -> list[RegulatorOut]:
    d, b = data.game_data, data.balance
    labels = {r.key: r.label for r in d.regions}
    out = []
    for r in rdata.file(d).regulators:
        g = rdata.regime_of(d, r.key)
        regime = None
        if g is not None:
            regime = RegimeOut(
                key=g.key,
                name=g.name,
                in_force=format_turn(g.in_force_turn),
                users_share=g.users_share,
                turnover_cents=rdata.threshold_cents(g.turnover_b, g.currency, b),
                turnover_scope=g.turnover_scope,
                value_cents=rdata.threshold_cents(g.value_b, g.currency, b),
                comply_months=g.comply_months,
                duties=[DUTY_WORDS[x] for x in g.duties],
                max_fine_share=g.max_fine_share,
                repeat_fine_share=g.repeat_fine_share,
            )
        out.append(
            RegulatorOut(
                key=r.key,
                name=r.name,
                region=r.region,
                region_label=labels.get(r.region, r.region),
                part=r.part,
                structural=r.structural,
                regime=regime,
            )
        )
    return out


def _tests(state: GameState, balances: LedgerBalances | None, data: LoadedData) -> list[TestOut]:
    d, b = data.game_data, data.balance
    me = owner_of(state, state.player.id)
    v = view(state, b, d)
    out = []
    for g in rdata.file(d).regimes:
        reg = rdata.file(d).regulator(g.regulator)
        warned = [
            w.turn for w in state.designation_warnings if w.regime == g.key and w.company_id == me
        ]
        turnover = (
            v.world_year.get(me, 0)
            if g.turnover_scope == "world"
            else round(v.region_year(me, reg.region) * rdata.part_share(d, reg))
        )
        cap = None
        if balances is not None and g.value_b is not None:
            from tst.sim.mna.valuation import market_cap_cents

            cap = market_cap_cents(state, me, balances, b, d)
        out.append(
            TestOut(
                regime=g.key,
                regime_name=g.name,
                users=v.users.get((me, reg.region), 0.0),
                users_needed=b.regulation.dominance_share
                if g.users_share is None
                else g.users_share,
                turnover_cents=turnover,
                turnover_needed_cents=rdata.threshold_cents(g.turnover_b, g.currency, b),
                value_cents=cap,
                value_needed_cents=rdata.threshold_cents(g.value_b, g.currency, b),
                ratio=min(ratio(state, g, me, v, balances, b, d), 10.0),
                warn_at=b.regulation.warn_ratio,
                designated=is_designated(state, d, me, g.key),
                warned=format_turn(max(warned)) if warned else None,
            )
        )
    return out


def _designations(state: GameState, data: LoadedData) -> list[DesignationOut]:
    d = data.game_data
    rf = rdata.file(d)
    out = []
    for h in rdata.history_designations(state, d, state.turn):
        g = rf.regime(h.regime)
        out.append(
            DesignationOut(
                regime=g.key, regime_name=g.name, regulator=g.regulator,
                company=_name(state, h.company_id, h.label), company_id=h.company_id,
                player=h.company_id == state.player.id, since=format_turn(h.from_turn),
                duties_from=format_turn(h.from_turn + g.comply_months), services=list(h.services),
                historical=True, source=h.source,
            )
        )  # fmt: skip
    for x in state.designations:
        g = rf.regime(x.regime)
        out.append(
            DesignationOut(
                regime=g.key, regime_name=g.name, regulator=g.regulator,
                company=_name(state, x.company_id), company_id=x.company_id,
                player=x.company_id == state.player.id, since=format_turn(x.from_turn),
                duties_from=format_turn(x.duties_from), services=["its platforms"],
                historical=False, source=None,
            )
        )  # fmt: skip
    return out


def _duties(state: GameState, data: LoadedData) -> list[DutyOut]:
    d = data.game_data
    rf = rdata.file(d)
    me = owner_of(state, state.player.id)
    mine = {(r.key, k) for r in rf.regulators for k in breaches(state, me, r)}
    return [
        DutyOut(
            id=x.id,
            regulator=x.regulator,
            regulator_name=rf.regulator(x.regulator).name,
            company=_name(state, x.company_id),
            company_id=x.company_id,
            player=x.company_id == me,
            kind=x.kind,
            label=DUTY_WORDS[x.kind],
            since=format_turn(x.from_turn),
            source=x.source,
            breached=x.company_id == me and (x.regulator, x.kind) in mine,
        )
        for x in state.duties
        if x.from_turn <= state.turn
    ]


def _cases(state: GameState, data: LoadedData) -> list[CaseOut]:
    d, b = data.game_data, data.balance
    rf = rdata.file(d)
    rb = b.regulation
    ids = rdata.company_ids(state)
    out = []
    for h in rdata.history_cases(d, state.turn):
        steps = [s for s in h.stages if s.turn <= state.turn]
        done = steps == list(h.stages) and h.outcome != "open"
        cid = ids.get(h.company) if h.company else None
        out.append(
            CaseOut(
                id=None, key=h.key, regulator=h.regulator,
                regulator_name=h.authority or rf.regulator(h.regulator).name,
                company=_name(state, cid, h.label), company_id=cid,
                player=False, title=h.title, conduct=CONDUCT_WORDS.get(h.conduct, h.conduct),
                market=h.kind, opened=format_turn(h.opened_turn), stage=steps[-1].stage,
                stage_since=format_turn(steps[-1].turn), stage_window=None,
                outcome=h.outcome if done else "open",
                fine_cents=rdata.usd_cents(h.fine, h.currency, b)
                if any(s.stage == "ruling" for s in steps) else 0,
                final_cents=rdata.usd_cents(h.final, h.currency, b) if done else None,
                remedy=DUTY_WORDS[h.remedy] if h.remedy and done else None, odds=None,
                steps=[
                    StepOut(stage=s.stage, month=format_turn(s.turn), note=s.note) for s in steps
                ],
                historical=True,
            )
        )  # fmt: skip
    for c in state.reg_cases:
        window = None
        odds = None
        if c.stage in STAGE_WINDOW:
            lo, hi = getattr(rb.stages, STAGE_WINDOW[c.stage])
            window = f"{lo}-{hi} months"
            alo, ahi = rb.odds.ruling_against
            odds = f"{alo:.0%}-{ahi:.0%} against, if contested"
        elif c.stage == "appeal":
            lo, hi = rb.stages.appeal_months
            window = f"{lo}-{hi} months"
            alo, ahi = rb.odds.appeal_win
            odds = f"{alo:.0%}-{ahi:.0%} to win"
        elif c.stage == "ruling":
            alo, ahi = rb.odds.appeal_win
            odds = f"an appeal wins {alo:.0%}-{ahi:.0%} of the time"
        out.append(
            CaseOut(
                id=c.id, key=None, regulator=c.regulator,
                regulator_name=rf.regulator(c.regulator).name,
                company=_name(state, c.company_id), company_id=c.company_id,
                player=c.company_id == owner_of(state, state.player.id),
                title=f"{CONDUCT_WORDS.get(c.conduct, c.conduct)} ({c.market.replace('_', ' ')})",
                conduct=CONDUCT_WORDS.get(c.conduct, c.conduct),
                market=c.market.replace("_", " "), opened=format_turn(c.opened_turn),
                stage=c.stage, stage_since=format_turn(c.stage_turn), stage_window=window,
                outcome=c.outcome, fine_cents=c.fine_cents, final_cents=None,
                remedy=DUTY_WORDS[c.remedy] if c.remedy else None, odds=odds,
                steps=[StepOut(stage=s, month=format_turn(t)) for s, t in c.steps],
                historical=False,
            )
        )  # fmt: skip
    return out


def _watches(state: GameState, data: LoadedData) -> list[WatchOut]:
    rf = rdata.file(data.game_data)
    me = owner_of(state, state.player.id)
    need = data.balance.regulation.structural.warning_months
    return [
        WatchOut(
            regulator=w.regulator,
            regulator_name=rf.regulator(w.regulator).name,
            market=w.market.replace("_", " "),
            since=format_turn(w.first_turn),
            months=state.turn - w.first_turn,
            needed_months=need,
            signs=[
                WarningSignOut(kind=k, month=format_turn(t), label=SIGN_WORDS[k])
                for k, t in w.signs
            ],
        )
        for w in state.reg_watches
        if w.company_id == me
    ]


def _orders(state: GameState, data: LoadedData) -> list[OrderOut]:
    rf = rdata.file(data.game_data)
    me = owner_of(state, state.player.id)
    return [
        OrderOut(
            id=o.id,
            regulator=o.regulator,
            regulator_name=rf.regulator(o.regulator).name,
            company=_name(state, o.company_id),
            player=o.company_id == me,
            unit=o.unit_label,
            unit_kind=o.unit_kind,
            ordered=format_turn(o.ordered_turn),
            deadline=format_turn(o.deadline_turn),
            status=o.status,
            warned_from=format_turn(o.warned_from),
            can_sell=o.status == "open" and structural.buyer_of(state, o) is not None,
            can_spin_off=o.status == "open" and structural.can_spin_off(state, o),
        )
        for o in state.reg_orders
    ]


def _explain(data: LoadedData) -> ExplainOut:
    rb = data.balance.regulation
    lo, hi = rb.fine.share
    sb = rb.structural
    return ExplainOut(
        fine=(
            f"A fine is {lo:.1%}-{hi:.0%} of the group's turnover over the last year, by the "
            f"case's gravity, x{rb.fine.noncompliance_mult:g} while the company breaks a duty, "
            "capped at the regime's maximum (the DMA's 10%, 20% for a repeat within 10 years). "
            f"Settling after the charges pays {rb.fine.settle_share:.0%} of a typical fine; "
            "settling at the inquiry pays none. An appeal that wins brings it back."
        ),
        thresholds=(
            "Each December a regulator tests the largest share of its region's users on a "
            "platform you own against its users threshold, and your turnover there (or your "
            "market value) against its money threshold. The test's ratio is the smaller of the "
            f"two: from {rb.warn_ratio:.0%} you are warned, and at 100% a year after a warning "
            "you are designated. Duties start a few months later."
        ),
        structural=(
            "A break-up needs a ruling against you in the same market within "
            f"{sb.ruling_years} years whose remedy you are breaking, or two rulings in "
            f"{sb.two_rulings_years} years, a regulator whose law allows it, and at least "
            f"{sb.warning_months // 12} years of warning signs. Even then most rulings are "
            "fines and duties."
        ),
    )


def regulation_out(
    state: GameState, data: LoadedData, balances: LedgerBalances | None = None
) -> RegulationOut:
    d, b = data.game_data, data.balance
    me = owner_of(state, state.player.id)
    group = {c.id for c in group_companies(state, me)}
    fines = (
        sum(v for (cid, acct), v in balances.items() if cid in group and acct == FINES)
        if balances is not None
        else 0
    )
    return RegulationOut(
        month=format_turn(state.turn),
        running=rdata.active(state.turn, b, d),
        regulators=_regulators(data),
        tests=_tests(state, balances, data),
        designations=_designations(state, data),
        duties=_duties(state, data),
        cases=_cases(state, data),
        watches=_watches(state, data),
        orders=_orders(state, data),
        precedents=[
            PrecedentOut(
                label=p.label, month=format_turn(month_to_turn(p.at)), note=p.note, source=p.source
            )
            for p in rdata.file(d).precedents
        ],
        fines_cents=fines,
        breaches=[
            f"{rdata.file(d).regulator(r.key).name}: {DUTY_WORDS[k]}"
            for r in rdata.file(d).regulators
            for k in breaches(state, me, r)
        ],
        explain=_explain(data),
    )
