"""Political influence (docs/formulas.md 32.5, M24): a company's monthly lobbying spend by
region (posted to 6950_lobbying) builds influence over that region's regulators, which
lowers an antitrust review's block probability. Lobbying also builds a hidden scandal risk;
each month a scandal may break (stream `founder_life`, id 46, key (company_id,)). The API shows
only an exposure band, never the risk or a scandal's chance (32.8)."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Final, Literal

import numpy as np

from tst.sim.data_models import SCORE_MAX, Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.founder.events import queue
from tst.sim.founder.models import Influence
from tst.sim.founder.persona import raise_trait, strong
from tst.sim.founder.stress import add_stress
from tst.sim.ledger import CASH, GENERAL_ADMIN, LOBBYING, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.press.moments import adjust_credibility
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    influence_of,
    life_of,
    with_influence,
    with_life,
    with_product,
)

CENTS_A_DOLLAR: Final = 100  # tunable-exempt: cents in a dollar
DOLLARS_A_K: Final = 1000  # tunable-exempt: risk_rate is per $1k
PCT: Final = 100  # tunable-exempt: influence is 0-100
TRAILING_MONTHS: Final = 12  # tunable-exempt: the fine is on a year's revenue
SCANDAL_TEMPLATE: Final = "founder_scandal"
type Exposure = Literal["low", "medium", "high"]


def founder_gen(rng: RngFactory, turn: int, company_id: int) -> np.random.Generator:
    """Stream `founder_life` (id 46, ADR-0013): the one call site, keyed (company_id,)."""
    return rng.stream(turn, "founder_life", company_id)


def of(state: GameState, company_id: int, region: str) -> float:
    """The company's influence in `region`, 0-100 (32.5's hook; M22's export licences)."""
    record = influence_of(state, company_id, region)
    return record.value if record is not None else 0.0


def exposure(risk: float, balance: Balance) -> Exposure:
    """The only form the scandal risk ever leaves the engine in (32.5, 32.8)."""
    lo, hi = balance.influence.exposure
    return "low" if risk < lo else "medium" if risk < hi else "high"


def antitrust_factor(state: GameState, company_id: int, region: str, balance: Balance) -> float:
    """An antitrust review's block probability x (1 - antitrust x I / 100) (32.5), x the
    Ruthless strictness (32.4)."""
    factor = 1 - balance.influence.antitrust * of(state, company_id, region) / PCT
    if strong(state, company_id, "ruthless", balance):
        factor *= balance.persona.antitrust_mult
    return factor


def set_lobbying(
    state: GameState, company_id: int, region: str, dollars: int, balance: Balance, data: GameData
) -> tuple[GameState, LogItem]:
    ib = balance.influence
    if region not in data.region_keys:
        raise InvalidActionError(f"unknown region {region!r}")
    if dollars < 0 or dollars > ib.max_monthly_dollars:
        raise InvalidActionError(
            f"monthly lobbying is $0 to ${ib.max_monthly_dollars:,} in one region"
        )
    record = influence_of(state, company_id, region)
    if record is None:
        record = Influence(company_id=company_id, region=region)
    started = record.started_turn if record.started_turn is not None or not dollars else state.turn
    record = replace(record, spend_cents=dollars * CENTS_A_DOLLAR, started_turn=started)
    state = with_influence(state, record)
    label = data.region(region).label
    log = inbox_item(
        state.turn,
        company_id,
        "lobbying_set",
        region=label,
        amount_cents=dollars * CENTS_A_DOLLAR,
    )
    return state, log


def _gain(spend_cents: int, balance: Balance) -> float:
    ib = balance.influence
    return ib.rate * math.sqrt(spend_cents / CENTS_A_DOLLAR / ib.unit_dollars)


def lobbying_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Phase 12 (32.5): spend posts, influence decays and grows, risk builds, and a scandal
    may break. One uniform per region record a month, in region order (records are sorted),
    then one for a second story when a scandal breaks."""
    ib = balance.influence
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    by_company: dict[int, list[str]] = {}
    for held in state.influence:
        by_company.setdefault(held.company_id, []).append(held.region)
    for cid, regions in by_company.items():
        company = state.company(cid)
        if not company.is_player or not company.alive:
            continue
        gen = founder_gen(rng, state.turn, cid)
        ruthless = strong(state, cid, "ruthless", balance)
        for region in regions:
            record = influence_of(state, cid, region)
            assert record is not None
            spend = record.spend_cents
            if spend:
                entries.append(
                    LedgerEntry.transfer(
                        turn=state.turn,
                        company_id=cid,
                        memo=f"Lobbying: {data.region(region).label}",
                        debit=LOBBYING,
                        credit=CASH,
                        amount=spend,
                    )
                )
            value = min(ib.cap, record.value * (1 - ib.decay) + _gain(spend, balance))
            risk_gain = spend / CENTS_A_DOLLAR / DOLLARS_A_K * ib.risk_rate
            if ruthless:
                risk_gain *= ib.risk_ruthless
            risk = record.risk * (1 - ib.risk_decay) + risk_gain
            record = replace(record, value=value, risk=risk, spent_cents=record.spent_cents + spend)
            state = with_influence(state, record)
            u = float(gen.random())
            if u < min(ib.chance_cap, risk / ib.risk_scale):
                second = float(gen.random()) < ib.fight_chance
                state, posted, logged = break_scandal(state, cid, region, second, balance, data)
                entries += posted
                logs += logged
    return state, entries, logs


def break_scandal(
    state: GameState, company_id: int, region: str, second: bool, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """A scandal (32.5): credibility, every product's brand, the region's influence, a fine,
    and the persona; then a critical event next month asks how the founder answers.
    `second`: drawn now, whether fighting it brings a second story (hidden)."""
    ib = balance.influence
    cid, turn = company_id, state.turn
    record = influence_of(state, cid, region)
    assert record is not None
    state = with_influence(
        state,
        replace(
            record, value=0.0, scandal_turns=(*record.scandal_turns, turn), second_story=second
        ),
    )
    state = _hit(state, cid, balance)
    revenue = sum(state.company(cid).mrr_history[-TRAILING_MONTHS:])
    fine = round(revenue * ib.scandal_fine)
    entries = []
    if fine > 0:
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=cid,
                memo=f"Fine after the lobbying scandal in {data.region(region).label}",
                debit=GENERAL_ADMIN,
                credit=CASH,
                amount=fine,
            )
        )
    founder = state.founder_of(cid)
    life = life_of(state, founder.id) if founder is not None else None
    if life is not None:
        why = "a lobbying scandal"
        life = raise_trait(life, "ruthless", ib.scandal_ruthless, why, turn, balance)
        life = raise_trait(life, "reckless", ib.scandal_reckless, why, turn, balance)
        state = with_life(state, life)
    state = queue(state, cid, SCANDAL_TEMPLATE, turn + 1)
    log = inbox_item(
        turn,
        cid,
        "scandal_broke",
        region=data.region(region).label,
        fine_cents=fine,
    )
    return state, entries, [log]


def _hit(state: GameState, company_id: int, balance: Balance) -> GameState:
    ib = balance.influence
    state = adjust_credibility(state, company_id, ib.scandal_cred, "a lobbying scandal", balance)
    for product in state.company_products(company_id):
        if product.status != "retired":
            brand = max(0.0, min(float(SCORE_MAX), product.brand + ib.scandal_brand))
            state = with_product(state, replace(product, brand=brand))
    return state


def scandal_for_event(state: GameState, company_id: int, event_turn: int) -> str | None:
    """The region of the scandal an event (shown the month after it broke) answers."""
    for record in state.influence:
        if record.company_id == company_id and event_turn - 1 in record.scandal_turns:
            return record.region
    return None


def answer_scandal(
    state: GameState, company_id: int, event_turn: int, step: str, balance: Balance
) -> tuple[GameState, list[LogItem]]:
    """The founder's answer (32.5): apologize (credibility and stress), drop the lobbyists
    (the region's lobbying stops), or fight it (a second story, if drawn: the hit again)."""
    ib = balance.influence
    region = scandal_for_event(state, company_id, event_turn)
    founder = state.founder_of(company_id)
    logs: list[LogItem] = []
    if step == "apologize":
        state = adjust_credibility(
            state, company_id, ib.apologize_cred, "apologized for a scandal", balance
        )
        life = life_of(state, founder.id) if founder is not None else None
        if life is not None:
            life = add_stress(
                life, state.turn, ib.apologize_stress, "a public apology", balance.stress
            )
            state = with_life(state, life)
    elif step == "drop_lobbyists" and region is not None:
        record = influence_of(state, company_id, region)
        if record is not None:
            state = with_influence(state, replace(record, spend_cents=0))
    elif step == "fight" and region is not None:
        record = influence_of(state, company_id, region)
        if record is not None and record.second_story:
            state = _hit(state, company_id, balance)
            logs.append(inbox_item(state.turn, company_id, "scandal_second_story"))
    if region is not None:  # the second story's draw is spent either way
        record = influence_of(state, company_id, region)
        if record is not None and record.second_story:
            state = with_influence(state, replace(record, second_story=False))
    return state, logs
