"""Each deal kind's place in a negotiation (docs/formulas.md 58.1, 58.4): what the engine's
existing pricing says today (the median, the skip outcome), the counterpart's public facts,
and the existing action that executes agreed terms. Pure: state and the deal's parameters in.

Every kind negotiates its price-like term (58.1 allows up to four; M47 decision: one each, so
`package` is never valid yet). A quoted price (commodities, PPAs, foundry slots) is a `bp` term,
basis points of the quote; a sum (a price, salary, contract value, fine or upfront) is `cents`.
An acquisition's zone is the existing first counter and reservation (28.3): its median is the
midpoint, today's second counter, and an agreed price at or above the reservation is accepted
by `bid_for_company` as it stands."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from tst.sim.actions.commodities import SignCommodityContract, SignOfftake
from tst.sim.actions.hiring import MakeOffer
from tst.sim.calendar import format_turn, turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import NegotiationRuleError, SimError
from tst.sim.fabs.foundry import SignFoundryContract
from tst.sim.ledger import LedgerBalances
from tst.sim.mna.deals import BidForCompany
from tst.sim.money import format_money, times
from tst.sim.negotiation.actions import (
    AgreeContractValue,
    AgreeRetention,
    AgreeSettlement,
    WalkAway,
    new_contract,
    pending_approach,
)
from tst.sim.negotiation.config import DealKind
from tst.sim.negotiation.models import BP, Counterpart, DealRef, TermSpec
from tst.sim.pharma.actions import LicenseAsset, OutLicense
from tst.sim.power.actions import SignPpa
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, target_file

type Params = Mapping[str, Any]
type Agreement = (
    BidForCompany
    | MakeOffer
    | AgreeRetention
    | SignCommodityContract
    | SignOfftake
    | SignFoundryContract
    | SignPpa
    | AgreeContractValue
    | AgreeSettlement
    | LicenseAsset
    | OutLicense
)

PRICE: Final = "price"  # tunable-exempt: the one term's key


@dataclass(frozen=True, slots=True)
class Deal:
    """A deal set up for talks: its kind, the parameters its action takes, and its reference."""

    kind: DealKind
    params: Params
    ref: DealRef
    deal_id: int  # what a walk-away loses (WalkAway.deal_id), 0 for a quote


def _int(params: Params, key: str) -> int:
    try:
        return int(params[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise NegotiationRuleError(f"the deal needs {key}") from exc


def _float(params: Params, key: str, default: float | None = None) -> float:
    if key not in params and default is not None:
        return default
    try:
        return float(params[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise NegotiationRuleError(f"the deal needs {key}") from exc


def _str(params: Params, key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value:
        raise NegotiationRuleError(f"the deal needs {key}")
    return value


def _person_name(state: GameState, person_id: int) -> str:
    p = state.person(person_id)
    return f"{p.first_name} {p.last_name}"


def _cents(label: str, wants: str) -> TermSpec:
    return TermSpec(PRICE, label, "cents", "lower" if wants == "lower" else "higher")


def _bp(label: str, wants: str, base: float, unit: str, cents: bool = False) -> TermSpec:
    return TermSpec(
        PRICE, label, "bp", "lower" if wants == "lower" else "higher", base, unit, cents
    )


# --- References (58.1-58.2) -------------------------------------------------------------------


def _acquisition(
    state: GameState,
    params: Params,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Deal:
    from tst.sim.mna import deals as md
    from tst.sim.mna import formulas as mf
    from tst.sim.mna import valuation
    from tst.sim.mna.draws import mna_draws

    target = _int(params, "target_id")
    player = state.player.id
    try:
        md._target(state, player, target)
    except SimError as exc:
        raise NegotiationRuleError(exc.message) from exc
    company = state.company(target)
    found = target_file(state, player, target)
    if found is not None and found.blocked_until is not None and state.turn < found.blocked_until:
        raise NegotiationRuleError(f"talks with {company.name} are closed for now")
    if md.open_deal(state, target) is not None:
        raise NegotiationRuleError(f"{company.name} already has a deal agreed")
    mb = balance.mna
    key = md.key_of(state, target)
    if valuation.is_listed(state, target, data):
        cap = valuation.market_cap_cents(state, target, balances, balance, data) or 0
        bar = found.board_bar if found is not None else None
        if bar is None:
            z = float(mna_draws(rng, state.turn, *key, md.BOARD_TAG).standard_normal())
            bar = mf.board_bar(z, mb)
        reservation = math.ceil(cap * (1 + bar))  # money-exact: the board's bar (28.3)
        aspiration = reservation + times(reservation, 2 * balance.negotiation.spread["acquisition"])
        who, role = f"the board of {company.name}", "board"
    else:
        reservation = md.reservation_cents(state, target, balances, balance, data)
        if found is not None and found.counter_exact is not None:
            aspiration = max(found.counter_exact, reservation)
        else:
            personality = company.personality or ""
            anchor = mb.counter_anchor.get(personality, max(mb.counter_anchor.values()))
            z = float(mna_draws(rng, state.turn, *key, md.COUNTER_TAG).standard_normal())
            aspiration = mf.first_counter_exact(reservation, anchor, z, mb)
        founder = state.founder_of(target)
        who = _person_name(state, founder.id) if founder is not None else f"{company.name}'s CEO"
        role = "founder and CEO" if founder is not None else "CEO"
    estimate = md.estimate_cents(state, player, target, balances, balance, data)
    staff = len(state.staff(target))
    ref = DealRef(
        kind="acquisition",
        key=(target,),
        subject=f"Acquire {company.name}",
        terms=(_cents("Price", "lower"),),
        medians=((aspiration + reservation) // 2,),
        counterpart=Counterpart(
            who,
            role,
            company.name,
            f"company:{target}",
            company_id=target,
            style=(company.personality or "").replace("_", " "),
        ),
        facts=(
            f"Our estimate of {company.name}'s value is {format_money(estimate)}",
            f"{company.name} has {staff} people",
            "We pay in cash at closing"
            if params.get("cash_share", 1.0) == 1.0
            else "Part in shares",
        ),
        zones=((aspiration, reservation),),
    )
    return Deal("acquisition", params, ref, target)


def _hire(state: GameState, params: Params, data: GameData) -> Deal:
    from tst.sim.hiring.models import Candidate

    pid = _int(params, "candidate_id")
    candidate = state.candidate(pid)
    if not isinstance(candidate, Candidate) or candidate.status != "open":
        raise NegotiationRuleError(f"candidate {pid} is not open")
    if candidate.interviewed_turn is None:
        raise NegotiationRuleError("interview the candidate before talking terms (ADR-0016)")
    if state.pending_offer_for(pid) is not None:
        raise NegotiationRuleError("the candidate already has a pending offer")
    person = state.person(pid)
    expectation = person.salary_expectation_cents
    if not expectation:
        raise NegotiationRuleError("the candidate has no salary expectation")
    role = data.role(person.role).label.lower() if person.role else "employee"
    name = _person_name(state, pid)
    company = state.player
    ref = DealRef(
        kind="hire",
        key=(pid,),
        subject=f"Hire {name}",
        terms=(_cents("Salary a year", "lower"),),
        medians=(expectation,),
        counterpart=Counterpart(
            name,
            f"candidate, {person.level or ''} {role}".strip(),
            "",
            f"person:{pid}",
            person_id=pid,
        ),
        facts=(
            f"{company.name} is a stage-{company.stage} company",
            f"The role is {person.level or ''} {role}".replace("  ", " "),
            f"The offer includes {_int(params, 'equity_bp') / 100:g}% in options"
            if params.get("equity_bp")
            else "The offer is salary only",
        ),
    )
    return Deal("hire", params, ref, pid)


OFFER_BAND = 0.20  # tunable-exempt: display only, a rival's offer is shown in a band this wide
BAND_NICE = (5, 2, 1)  # tunable-exempt: the band's edges are round figures


def offer_band(cents: int) -> tuple[int, int]:
    """A rival's approach offer as the company is told it (M57r-B, review 10 item 4, F22;
    ruling 2: 61.3 keeps the amount hidden): the band of round figures it falls in, a step of
    1, 2 or 5 x a power of ten at or below OFFER_BAND of it, so the band is 8-20% wide and the
    offer anywhere inside it. Both the retention talk's facts and the rivals API show this."""
    raw = int(cents * OFFER_BAND)  # money-exact: a band width, then integer arithmetic
    if raw < 1:
        return cents, cents + 1
    power = int("1" + "0" * (len(str(raw)) - 1))  # the power of ten at or below raw
    step = next(n * power for n in BAND_NICE if n * power <= raw)
    lo = cents // step * step
    return lo, lo + step


def _retention(state: GameState, params: Params) -> Deal:
    aid = _int(params, "approach_id")
    try:
        approach = pending_approach(state, aid)
    except SimError as exc:
        raise NegotiationRuleError(exc.message) from exc
    employment = state.employment_of(approach.person_id)
    assert employment is not None
    name = _person_name(state, approach.person_id)
    rival = state.company(approach.rival_id).name
    year, _ = turn_to_ym(employment.start_turn)
    lo, hi = offer_band(approach.offer_cents)
    ref = DealRef(
        kind="retention",
        key=(aid,),
        subject=f"Keep {name}",
        terms=(_cents("Salary a year", "lower"),),
        medians=(approach.offer_cents,),
        counterpart=Counterpart(
            name,
            employment.role.replace("_", " "),
            state.player.name,
            f"person:{approach.person_id}",
            person_id=approach.person_id,
        ),
        facts=(
            f"{rival} offered {format_money(lo)} to {format_money(hi)} a year",
            f"{name} earns {format_money(employment.salary_cents)} a year now",
            f"{name} has worked here since {year}",
        ),
    )
    return Deal("retention", params, ref, aid)


def _good_index(good: str, data: GameData) -> int:
    assert data.commodities is not None
    keys = [g.key for g in data.commodities.goods]
    if good not in keys:
        raise NegotiationRuleError(f"unknown commodity {good!r}")
    return keys.index(good)


def _supplier(state: GameState, params: Params, balance: Balance, data: GameData) -> Deal:
    from tst.sim.commodities import offtake

    good = _str(params, "good")
    months = _int(params, "months")
    volume = _float(params, "volume_year")
    q = offtake.contract_quote(state, good, months, volume, balance, data)
    assert data.commodities is not None
    g = data.commodities.good(good)
    ref = DealRef(
        kind="supplier",
        key=(_good_index(good, data),),
        subject=f"{g.label}: {months}-month contract",
        terms=(_bp("Price", "lower", q.price, g.unit),),
        medians=(BP,),
        counterpart=Counterpart(
            "The trading desk", "commodity traders", f"{g.label} traders", f"traders:{good}"
        ),
        facts=(
            f"The quoted price is {q.price:,.2f} {g.unit}",
            f"{volume:,.1f} {g.volume_unit} a year for {months} months",
            f"Take-or-pay {balance.commodity.contract_take_or_pay:.0%}",
        ),
    )
    return Deal("supplier", params, ref, 0)


def _offtake(state: GameState, params: Params, balance: Balance, data: GameData) -> Deal:
    from tst.sim.commodities import offtake

    good = _str(params, "good")
    supplier = _str(params, "supplier")
    years = _int(params, "years")
    volume = _float(params, "volume_year")
    prepay = _float(params, "prepay", 0.0)
    q = offtake.offtake_quote(state, good, supplier, years, volume, prepay, balance, data)
    assert data.commodities is not None and data.suppliers is not None
    g = data.commodities.good(good)
    s = data.suppliers.supplier(supplier)
    assert s is not None
    index = [x.key for x in data.suppliers.suppliers].index(supplier)
    ref = DealRef(
        kind="offtake",
        key=(_good_index(good, data), index),
        subject=f"{g.label} offtake with {s.name}",
        terms=(_bp("Price", "lower", q.price, g.unit),),
        medians=(BP,),
        counterpart=Counterpart("Head of sales", "sales", s.name, supplier),
        facts=(
            f"The quoted price is {q.price:,.2f} {g.unit}",
            f"{volume:,.1f} {g.volume_unit} a year for {years} years",
            f"A collar of {balance.offtake.collar:.0%} either side",
        ),
    )
    return Deal("offtake", params, ref, 0)


def foundry_ceiling(
    state: GameState, fab_id: int, customer: str, balance: Balance, data: GameData
) -> float:
    """The most a designer pays a start today (38.2's slot price x max_price / premium)."""
    from tst.sim.contracts import termination as ct
    from tst.sim.fabs import market as fm
    from tst.sim.fabs.foundry import slot_price_cents

    fab = fm.fab_of(state, fab_id)
    if fab is None:
        raise NegotiationRuleError(f"no fab {fab_id}")
    # money-exact: rate
    ceiling = slot_price_cents(state, fab, balance, data) * balance.contracts.foundry.max_price
    return ceiling / float(ct.premium(state, customer, balance))


def _foundry(state: GameState, params: Params, balance: Balance, data: GameData) -> Deal:
    from tst.sim.fabs.foundry import customers

    fab_id = _int(params, "fab_id")
    customer = _str(params, "customer")
    names = customers(data, state)
    if customer not in names:
        raise NegotiationRuleError(f"the designers are {', '.join(names)}")
    months = _int(params, "months")
    starts = _float(params, "monthly_starts")
    ceiling = foundry_ceiling(state, fab_id, customer, balance, data)
    ref = DealRef(
        kind="foundry",
        key=(fab_id, names.index(customer)),
        subject=f"Foundry contract with {customer}",
        terms=(_bp("Price a start", "higher", ceiling, "a start", cents=True),),
        medians=(BP,),
        counterpart=Counterpart(
            "Head of procurement", "procurement", customer, f"customer:{customer}"
        ),
        facts=(
            f"The node's slot price is {format_money(round(ceiling))} a start",
            f"{starts:,.0f} starts a month for {months} months",
            "Our fab's capacity is limited",
        ),
    )
    return Deal("foundry", params, ref, 0)


def _ppa(state: GameState, params: Params, balance: Balance, data: GameData) -> Deal:
    from tst.sim.power import ppa

    region = _str(params, "region")
    producer = _str(params, "producer")
    mwh = _float(params, "mwh_month")
    years = _int(params, "years")
    if region not in data.region_keys:
        raise NegotiationRuleError(f"unknown region {region!r}")
    sellers = [s.key for s in ppa.sellers(data, region)]
    if producer not in sellers:
        raise NegotiationRuleError(f"{producer!r} does not sell power in that region")
    q = ppa.quote(state, region, producer, mwh, years, balance, data)
    ref = DealRef(
        kind="ppa",
        key=(list(data.region_keys).index(region), sellers.index(producer)),
        subject=f"Power contract with {q.producer_name}",
        terms=(_bp("Price a MWh", "lower", q.price_cents, "a MWh", cents=True),),
        medians=(BP,),
        counterpart=Counterpart(
            "Commercial director", "sales", q.producer_name, f"power:{producer}"
        ),
        facts=(
            f"The forward price is {format_money(round(q.forward_cents))} a MWh",
            f"{mwh:,.0f} MWh a month for {years} years",
            f"Take-or-pay {balance.power.ppa.take_or_pay:.0%}",
        ),
    )
    return Deal("ppa", params, ref, 0)


def _government(state: GameState, params: Params) -> Deal:
    cid = _int(params, "contract_id")
    try:
        c = new_contract(state, cid)
    except SimError as exc:
        raise NegotiationRuleError(exc.message) from exc
    who = f"{c.government.upper()} {c.buyer}"
    months = c.end_turn - c.start_turn
    ref = DealRef(
        kind="government",
        key=(cid,),
        subject=f"Final terms: {c.area} contract for the {who} buyer",
        terms=(_cents("Contract value", "higher"),),
        medians=(c.value_cents,),
        counterpart=Counterpart(
            "Contracting officer",
            "contracting",
            f"{who} government",
            f"government:{c.government}:{c.buyer}",
        ),
        facts=(
            f"The award was {format_money(c.value_cents)} over {months} months",
            f"Delivery starts {format_turn(c.start_turn)}",
            f"The contract is {c.contract.replace('_', ' ')}",
        ),
    )
    return Deal("government", params, ref, cid)


def settlement_fine(
    state: GameState, event_id: int, balance: Balance, data: GameData
) -> tuple[int, str]:
    """(the fine a settlement pays today, the regulator's key) for an open case event (48.3)."""
    from tst.sim.regulation import data as rdata
    from tst.sim.regulation.answers import case_for
    from tst.sim.regulation.cases import MIDDLE, fine_cents

    event = state.event(event_id)
    if event is None or event.status != "open" or event.company_id != state.player.id:
        raise NegotiationRuleError(f"no open event {event_id}")
    case = case_for(state, event)
    if case is None or case.stage != "objections":
        raise NegotiationRuleError("only a case at the objections stage has a fine to settle")
    reg = rdata.file(data).regulator(case.regulator)
    lo, hi = balance.regulation.fine.share
    full = fine_cents(state, case, reg, MIDDLE, balance, data) if hi > lo else 0
    cents = times(full, balance.regulation.fine.settle_share)
    if cents <= 0:
        raise NegotiationRuleError("this settlement carries no fine to talk about")
    return cents, case.regulator


def _settlement(state: GameState, params: Params, balance: Balance, data: GameData) -> Deal:
    from tst.sim.negotiation.actions import SETTLE, choice_for

    eid = _int(params, "event_id")
    cents, regulator = settlement_fine(state, eid, balance, data)
    choice_for(state, eid, (SETTLE,))
    name = regulator.replace("_", " ")
    ref = DealRef(
        kind="settlement",
        key=(eid,),
        subject=f"Settlement with {name}",
        terms=(_cents("Fine", "lower"),),
        medians=(cents,),
        counterpart=Counterpart("Case officer", "case team", name, f"regulator:{regulator}"),
        facts=(
            f"The settlement on the table is {format_money(cents)}",
            "We will commit to the remedy",
            "A ruling would take months",
        ),
    )
    return Deal("settlement", params, ref, eid)


def _licence_in(state: GameState, params: Params, data: GameData) -> Deal:
    from tst.sim.pharma.licensing import BIOTECH, upfront_of

    aid = _int(params, "asset_id")
    acquire = bool(params.get("acquire", False))
    a = next((x for x in state.pharma_assets if x.id == aid), None)
    if a is None or a.taken_by is not None or state.turn >= a.until_turn:
        raise NegotiationRuleError(f"asset {aid} is not available")
    upfront = upfront_of(a, acquire, data)
    ref = DealRef(
        kind="licence_in",
        key=(aid,),
        subject=f"{'Acquire' if acquire else 'In-license'} {a.name}",
        terms=(_cents("Upfront", "lower"),),
        medians=(upfront,),
        counterpart=Counterpart(
            "Business development", "business development", BIOTECH, f"biotech:{aid}"
        ),
        facts=(
            f"The listed upfront is {format_money(upfront)}",
            f"{a.name} is at {a.stage.replace('_', ' ')}",
            f"Royalty {a.royalty:.0%}" if not acquire else "We take it outright",
        ),
    )
    return Deal("licence_in", params, ref, aid)


def _licence_out(state: GameState, params: Params, balance: Balance, data: GameData) -> Deal:
    from tst.sim.pharma import data as pd
    from tst.sim.pharma.licensing import out_terms

    pid = _int(params, "programme_id")
    rival_id = _int(params, "rival_id")
    co = bool(params.get("co_develop", False))
    p = next((x for x in state.pharma_programmes if x.id == pid), None)
    if p is None or p.company_id != state.player.id:
        raise NegotiationRuleError(f"no programme {pid} of yours")
    rival = state.company(rival_id)
    if rival.is_player or pd.file(data).rival(rival.name) is None:
        raise NegotiationRuleError("license to one of the pharmaceutical rivals")
    up, _, royalty, _ = out_terms(p, co, balance, data)
    if up <= 0:
        raise NegotiationRuleError("there is no upfront to talk about")
    ceo = state.founder_of(rival_id)
    ref = DealRef(
        kind="licence_out",
        key=(pid, rival_id),
        subject=f"{'Co-develop' if co else 'Out-license'} {p.name} with {rival.name}",
        terms=(_cents("Upfront", "higher"),),
        medians=(up,),
        counterpart=Counterpart(
            _person_name(state, ceo.id) if ceo is not None else "Head of business development",
            "business development",
            rival.name,
            f"company:{rival_id}",
            company_id=rival_id,
        ),
        facts=(
            f"The stage's typical upfront is {format_money(up)}",
            f"{p.name} is at {p.stage.replace('_', ' ')}",
            f"Royalty {royalty:.0%}" if not co else "We share the costs",
        ),
    )
    return Deal("licence_out", params, ref, 0)


def deal_for(
    state: GameState,
    kind: DealKind,
    params: Params,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Deal:
    """The deal as the engine prices it today. Raises NegotiationRuleError if it cannot be
    talked about now (the deal's own rules)."""
    try:
        match kind:
            case "acquisition":
                return _acquisition(state, params, rng, balances, balance, data)
            case "hire":
                return _hire(state, params, data)
            case "retention":
                return _retention(state, params)
            case "supplier":
                return _supplier(state, params, balance, data)
            case "offtake":
                return _offtake(state, params, balance, data)
            case "foundry":
                return _foundry(state, params, balance, data)
            case "ppa":
                return _ppa(state, params, balance, data)
            case "government":
                return _government(state, params)
            case "settlement":
                return _settlement(state, params, balance, data)
            case "licence_in":
                return _licence_in(state, params, data)
            case "licence_out":
                return _licence_out(state, params, balance, data)
    except NegotiationRuleError:
        raise
    except SimError as exc:  # the deal's own rule (a quote it refuses, a missing good)
        raise NegotiationRuleError(exc.message) from exc
    raise NegotiationRuleError(f"unknown deal kind {kind!r}")


# --- Outcomes (58.4) --------------------------------------------------------------------------


def agreement(deal: Deal, terms: tuple[int, ...], actor_id: int, base: float) -> Agreement:
    """The existing action that executes agreed terms. `base` is a bp term's quote (for the
    foundry, whose action takes a price)."""
    p = deal.params
    (v,) = terms
    match deal.kind:
        case "acquisition":
            return BidForCompany(
                actor_id,
                _int(p, "target_id"),
                v,
                cash_share=_float(p, "cash_share", 1.0),
                mode=str(p.get("mode", "integrate")),  # type: ignore[arg-type]
            )
        case "hire":
            return MakeOffer(
                actor_id, _int(p, "candidate_id"), v, int(p.get("equity_bp", 0)), agreed=True
            )
        case "retention":
            return AgreeRetention(actor_id, _int(p, "approach_id"), v)
        case "supplier":
            return SignCommodityContract(
                actor_id, _str(p, "good"), _int(p, "months"), _float(p, "volume_year"), price_bp=v
            )
        case "offtake":
            return SignOfftake(
                actor_id,
                _str(p, "good"),
                _str(p, "supplier"),
                _int(p, "years"),
                _float(p, "volume_year"),
                prepay=_float(p, "prepay", 0.0),
                price_bp=v,
            )
        case "foundry":
            return SignFoundryContract(
                actor_id,
                _int(p, "fab_id"),
                _str(p, "customer"),
                _float(p, "monthly_starts"),
                _int(p, "months"),
                base * v / BP,  # money-exact: rate (a start's price, as the action takes it)
                agreed=True,
            )
        case "ppa":
            return SignPpa(
                actor_id,
                _str(p, "region"),
                _str(p, "producer"),
                _float(p, "mwh_month"),
                _int(p, "years"),
                price_bp=v,
            )
        case "government":
            return AgreeContractValue(actor_id, _int(p, "contract_id"), v)
        case "settlement":
            return AgreeSettlement(actor_id, _int(p, "event_id"), v)
        case "licence_in":
            return LicenseAsset(
                actor_id, _int(p, "asset_id"), bool(p.get("acquire", False)), upfront_cents=v
            )
        case "licence_out":
            return OutLicense(
                actor_id,
                _int(p, "programme_id"),
                _int(p, "rival_id"),
                bool(p.get("co_develop", False)),
                upfront_cents=v,
            )
    raise NegotiationRuleError(f"unknown deal kind {deal.kind!r}")


def walk_away(deal: Deal, actor_id: int, balance: Balance) -> WalkAway:
    return WalkAway(actor_id, deal.kind, deal.deal_id, balance.negotiation.cooldown_months)


def negotiator(state: GameState, balance: Balance) -> tuple[dict[str, float], tuple[str, ...]]:
    """The player's negotiator (the founder): true skills (HIDDEN, the engine's only) and the
    persona traits that count (32.4, public)."""
    from tst.sim.founder.persona import strong

    founder = state.founder_of(state.player.id)
    if founder is None:
        return {}, ()
    skills = founder.skills.as_dict()
    traits = tuple(t for t in ("ruthless", "beloved") if strong(state, state.player.id, t, balance))
    return skills, traits
