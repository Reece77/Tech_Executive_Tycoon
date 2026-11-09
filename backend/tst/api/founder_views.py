"""Views of the founder's life (M24, formulas.md 32.8). Only public values: the scandal risk
leaves the engine as an exposure word, and a pending second story never leaves it."""

from __future__ import annotations

from tst.api.schemas.founder import (
    FoundationFormOut,
    FoundationOut,
    FounderOut,
    GovernmentOut,
    InfluenceOut,
    PersonalEntryOut,
    PersonalOut,
    PersonaOut,
    RegionOptionOut,
    ScandalOut,
    TraitCauseOut,
    TraitOut,
)
from tst.api.schemas.founder_parts import CauseOut, LegacyOut, StressOut
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.finance.captable import person_shares
from tst.sim.founder import effects, influence, legacy, personal, stress
from tst.sim.founder.config import CAUSES, TRAITS
from tst.sim.founder.foundation import CAUSE_WORDS
from tst.sim.founder.models import PERSONAL_CASH, FounderLife
from tst.sim.founder.persona import top_trait
from tst.sim.state import GameState, foundation_of, life_of, listed_id, public_of

ENTRIES_SHOWN = 12  # tunable-exempt: rows on the Personal tab
PCT = 100  # tunable-exempt: percent
TRAIT_LABELS = {
    "visionary": "Visionary",
    "ruthless": "Ruthless",
    "beloved": "Beloved",
    "reckless": "Reckless",
}
TRAIT_EFFECTS = {  # 32.4's table, in words (investor heat and lenders' rates: a follow-up)
    "visionary": "builders are easier to hire",
    "ruthless": "rival feuds build faster, staff morale -2, regulators stricter",
    "beloved": "fewer resignations; bold press answers lift the brand more",
    "reckless": "credibility drifts toward 45 instead of 50",
}


def _life(state: GameState, data: LoadedData) -> FounderLife:
    founder = state.founder_of(state.player.id)
    if founder is not None:
        life = life_of(state, founder.id)
        if life is not None:
            return life
        return stress.new_life(founder.id, data.balance)
    if state.founder_lives:  # after an exit the founder's employment has ended
        return state.founder_lives[0]
    return stress.new_life(0, data.balance)


def stress_out(state: GameState, data: LoadedData) -> StressOut:
    sb = data.balance.stress
    life = _life(state, data)
    return StressOut(
        stress=round(life.stress, 1),
        burnout=life.burnout,
        burnout_at=sb.burnout_at,
        recover_below=sb.recover_below,
        energy_cut_pct=sb.burnout_cut * PCT,
        burnouts=life.burnouts,
        causes=[
            CauseOut(turn=t, date_label=format_turn(t), change=round(v, 1), cause=why)
            for t, v, why in life.causes
        ],
    )


def persona_out(state: GameState, data: LoadedData) -> PersonaOut:
    pb = data.balance.persona
    life = _life(state, data)
    return PersonaOut(
        traits=[
            TraitOut(
                key=t,
                label=TRAIT_LABELS[t],
                value=round(life.trait(t), 1),
                strong=life.trait(t) >= pb.effect_at,
                effects=TRAIT_EFFECTS[t],
            )
            for t in TRAITS
        ],
        top=top_trait(life),
        effect_at=pb.effect_at,
        causes=[
            TraitCauseOut(
                turn=t, date_label=format_turn(t), trait=trait, change=round(v, 1), cause=why
            )
            for t, trait, v, why in reversed(life.trait_causes)
        ],
    )


def personal_out(state: GameState, data: LoadedData) -> PersonalOut:
    life = _life(state, data)
    pid = life.person_id
    totals = personal.book_balances(state.personal_book, pid)
    f = foundation_of(state, pid)
    listed = listed_id(state)  # M16 (31.2): the holding company's, once formed
    shares = person_shares(state, listed, pid)
    public = public_of(state, listed)
    mine = [e for e in state.personal_book if e.person_id == pid]
    return PersonalOut(
        cash_cents=totals.get(PERSONAL_CASH, 0),
        endowment_cents=personal.endowment_cents(state, pid),
        income=personal.income_by_source(state, pid),
        gifts_cents=f.gifts_cents if f is not None else 0,
        grants_cents=f.grants_cents if f is not None else 0,
        stake_shares=shares,
        stake_value_cents=shares * public.price_cents if public is not None else None,
        can_sell=public is not None and shares > 0 and not state.ended,
        entries=[
            PersonalEntryOut(
                turn=e.turn,
                date_label=format_turn(e.turn),
                memo=e.memo,
                source=e.source,
                amount_cents=sum(x.amount for x in e.lines if x.account == PERSONAL_CASH),
            )
            for e in reversed(mine[-ENTRIES_SHOWN:])
        ],
    )


def _effect_words(state: GameState, data: LoadedData) -> str | None:
    b = data.balance
    cid = state.player.id
    if pts := effects.education_points(state, cid, b):
        return f"hiring appeal +{pts:.3f} in your home region"
    if pts := effects.climate_points(state, cid, b):
        return f"brand target +{pts:g} on consumer products"
    if pts := effects.health_points(state, cid, b):
        return f"staff morale +{pts:g}"
    if effects.pool_city(state, cid, b):
        return f"hiring pools +{b.foundation.pool:.0%} in the foundation's city"
    return None


def foundation_out(state: GameState, data: LoadedData) -> FoundationOut | None:
    life = _life(state, data)
    f = foundation_of(state, life.person_id)
    if f is None:
        return None
    words = _effect_words(state, data)
    until = (
        f.last_grant_turn + data.balance.foundation.effect_months
        if f.last_grant_turn is not None and words
        else None
    )
    return FoundationOut(
        name=f.name,
        cause=f.cause,
        cause_label=CAUSE_WORDS[f.cause],
        city=data.game_data.city(f.city).label if f.city else None,
        region=data.game_data.region(f.region).label if f.region else None,
        created_label=format_turn(f.created_turn),
        endowment_cents=personal.endowment_cents(state, f.person_id),
        gifts_cents=f.gifts_cents,
        grants_cents=f.grants_cents,
        last_grant_cents=f.last_grant_cents,
        last_grant_label=format_turn(f.last_grant_turn) if f.last_grant_turn is not None else None,
        effect=words,
        effect_until_label=format_turn(until - 1) if until is not None else None,
    )


def government_out(state: GameState, data: LoadedData) -> GovernmentOut:
    b = data.balance
    cid = state.player.id
    regions = []
    scandals = []
    for record in state.influence:
        if record.company_id != cid:
            continue
        label = data.game_data.region(record.region).label
        regions.append(
            InfluenceOut(
                region=record.region,
                region_label=label,
                influence=round(record.value, 1),
                monthly_cents=record.spend_cents,
                spent_cents=record.spent_cents,
                exposure=influence.exposure(record.risk, b),
                antitrust_cut_pct=round(b.influence.antitrust * record.value, 1),
                scandals=len(record.scandal_turns),
            )
        )
        scandals += [
            ScandalOut(turn=t, date_label=format_turn(t), region=record.region, region_label=label)
            for t in record.scandal_turns
        ]
    return GovernmentOut(
        regions=regions,
        scandals=sorted(scandals, key=lambda s: -s.turn),
        energy=b.influence.energy,
        max_monthly_cents=b.influence.max_monthly_dollars * PCT,
        region_options=[RegionOptionOut(key=r.key, label=r.label) for r in data.game_data.regions],
    )


def legacy_out(state: GameState, data: LoadedData) -> LegacyOut:
    out = legacy.legacy_of(state, data.balance)
    best = state.company(out.best_company_id).name if out.best_company_id is not None else None
    return LegacyOut(
        total=out.total,
        best_score=out.best_score,
        best_company=best,
        giving=round(out.giving, 1),
        persona=round(out.persona, 1),
        grants_cents=out.grants_cents,
        wealth=round(out.wealth, 1),
        net_worth_cents=out.net_worth_cents,
    )


def founder_out(state: GameState, data: LoadedData) -> FounderOut:
    b = data.balance
    life = _life(state, data)
    person = state.person(life.person_id) if life.person_id else None
    return FounderOut(
        founder_name=f"{person.first_name} {person.last_name}" if person else "",
        stress=stress_out(state, data),
        persona=persona_out(state, data),
        personal=personal_out(state, data),
        foundation=foundation_out(state, data),
        foundation_form=FoundationFormOut(
            can_create=foundation_of(state, life.person_id) is None
            and personal.cash_cents(state, life.person_id) >= b.foundation.min_cents,
            min_cents=b.foundation.min_cents,
            energy=b.foundation.energy,
            causes=list(CAUSES),
        ),
        government=government_out(state, data),
        legacy=legacy_out(state, data),
    )
