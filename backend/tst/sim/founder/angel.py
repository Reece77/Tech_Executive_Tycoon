"""Angel and venture investing with the founder's own money (docs/formulas.md 37.2, M26).

- Rounds: every startup's founding money, later rounds (15.4), corporate venture investments
  (31.5) and the founder's cheques are recorded as `StartupRound`s. A round sells
  `angel.round_dilution` of the startup: post-money = raised / round_dilution, unless M16's
  venture set the price (pre-money + cheque).
- Joining a round (energy angel.energy): within angel.round_window_months of a startup's
  latest round, the founder's cheque extends it at its price: the post-money grows by the
  cheque, earlier holders dilute pro rata, and the founder's stake is the cheque over the
  new post-money (so a stake never exceeds 100%). At most the round's own size.
- Backing a new startup (energy angel.back_energy, at least angel.min_cheque_cents): a
  network founder starts a rival startup in a category, the cheque its founding cash, the
  stake `angel.seed_stake` by cheque size.
- Information rights: its key people are learned by the scouting rules (28.2's diligence
  action), its cash band and funding history are shown.
- Outcomes (monthly, `stakes_month`): later rounds dilute; an acquisition pays stake x price
  (the player's own group buying it is a related-party deal and raises a conflict of
  interest); a listing turns the stake into public shares; a failure writes it off.

Personal postings: a cheque Dr 9110 Cr 9100; proceeds Dr 9100, Cr 9110 at cost, the rest to
9410 gains or 9420 losses; a write-off Dr 9420 Cr 9110. The startup's own book takes the
cheque Dr cash Cr common equity: each book balances on its own (ADR-0003)."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from statistics import fmean
from typing import Final

import numpy as np

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.founder import draws
from tst.sim.founder.draws import personal_draws
from tst.sim.founder.events import queue
from tst.sim.founder.investing_models import STAKE_FULL, AngelStake, NetworkEntry, StartupRound
from tst.sim.founder.models import ANGEL, GAINS, LOSSES, PERSONAL_CASH, PUBLIC_SHARES
from tst.sim.founder.personal import cash_cents
from tst.sim.founder.wealth import post, shares_outstanding
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerBalances, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.people.models import Employment, Person
from tst.sim.rivals.setup import key_people_split
from tst.sim.rng import RngFactory
from tst.sim.state import (
    CompanyState,
    GameState,
    angel_stake_of,
    group_companies,
    holding_in,
    listed_id,
    next_record_id,
    rounds_of,
    with_angel_stake,
    with_candidate,
    with_employment,
    with_network,
    with_public_holding,
    with_startup_round,
)

CONFLICT_TEMPLATE = "personal_conflict"
ROUND_SOURCES = ("founded", "funded", "venture", "backed")  # rounds the founder may join
FOUNDING_MEMO = "Founders' and angels' money"  # rivals/startups.found_company's entry (15.4)
ROUND_MEMO = "Funding round"  # rivals/startups.startup_funding's entry (15.4)
SKILL_MID = 10.0  # tunable-exempt: the middle of the 1-20 attribute scale
LINK: Final = "rival"


# --- Rounds -----------------------------------------------------------------------------------


def post_money(raised_cents: int, balance: Balance) -> int:
    """37.2: a round's post-money, raised / angel.round_dilution."""
    return round(Fraction(raised_cents) / Fraction(str(balance.angel.round_dilution)))


def latest_round(state: GameState, company_id: int) -> StartupRound | None:
    rounds = rounds_of(state, company_id)
    return max(rounds, key=lambda r: (r.turn, r.id)) if rounds else None


def open_round(state: GameState, company_id: int, balance: Balance) -> StartupRound | None:
    """The startup's latest round, while it is open to the founder (within
    angel.round_window_months of closing)."""
    rounds = [r for r in rounds_of(state, company_id) if r.source in ROUND_SOURCES]
    if not rounds:
        return None
    last = max(rounds, key=lambda r: (r.turn, r.id))
    if state.turn - last.turn > balance.angel.round_window_months:
        return None
    return last


def record_round(
    state: GameState,
    company_id: int,
    raised_cents: int,
    post_cents: int,
    source: str,
) -> tuple[GameState, StartupRound]:
    record = StartupRound(
        id=next_record_id(state.startup_rounds),
        company_id=company_id,
        turn=state.turn,
        raised_cents=raised_cents,
        post_cents=post_cents,
        source=source,  # type: ignore[arg-type]
    )
    return with_startup_round(state, record), record


def record_month_rounds(
    state: GameState, entries: tuple[LedgerEntry, ...], balance: Balance
) -> tuple[GameState, list[StartupRound]]:
    """The month's startup rounds from the phase's entries (15.4): a founding's money and a
    later round, both Dr cash Cr common equity in the startup's book."""
    new: list[StartupRound] = []
    for e in entries:
        if e.memo not in (FOUNDING_MEMO, ROUND_MEMO):
            continue
        company = state.company(e.company_id)
        if not company.is_startup or company.is_player:
            continue
        raised = sum(line.amount for line in e.lines if line.account == CASH)
        if raised <= 0:
            continue
        source = "founded" if e.memo == FOUNDING_MEMO else "funded"
        state, record = record_round(state, company.id, raised, post_money(raised, balance), source)
        new.append(record)
    return state, new


# --- Joining a round ------------------------------------------------------------------------


def _check_startup(state: GameState, company_id: int, data: GameData) -> CompanyState:
    from tst.sim.mna.valuation import is_listed

    company = state.company(company_id)
    if (
        not company.is_startup
        or company.is_player
        or not company.alive
        or company.parent_id is not None
        or is_listed(state, company_id, data)
    ):
        raise InvalidActionError("the founder invests only in a private startup")
    return company


def _check_cash(state: GameState, person_id: int, cents: int) -> None:
    if cents > cash_cents(state, person_id):
        raise InvalidActionError("not enough personal cash for that")


def join_round(
    state: GameState,
    person_id: int,
    company_id: int,
    cents: int,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """37.2: the founder's cheque into a startup's open round."""
    ab = balance.angel
    company = _check_startup(state, company_id, data)
    rnd = open_round(state, company_id, balance)
    if rnd is None:
        raise InvalidActionError(f"{company.name} has no round open to you")
    if cents < ab.round_min_cents:
        raise InvalidActionError(
            f"a cheque into a round is at least ${ab.round_min_cents // 100:,}"
        )
    if cents > rnd.raised_cents:
        raise InvalidActionError(
            f"the round raised ${rnd.raised_cents // 100:,}; your cheque can be at most that"
        )
    _check_cash(state, person_id, cents)
    last = latest_round(state, company_id)
    price = last.post_cents if last is not None else rnd.post_cents
    new_post = price + cents
    old = angel_stake_of(state, person_id, company_id)
    kept = int(Fraction(old.stake_ppm * price, new_post)) if old is not None else 0
    stake = min(STAKE_FULL, kept + int(Fraction(cents * STAKE_FULL, new_post)))
    state, _ = record_round(state, company_id, cents, new_post, "angel")
    record = AngelStake(
        id=old.id if old is not None else next_record_id(state.angel_stakes),
        person_id=person_id,
        company_id=company_id,
        stake_ppm=stake,
        cost_cents=(old.cost_cents if old is not None else 0) + cents,
        from_turn=old.from_turn if old is not None else state.turn,
        last_post_cents=new_post,
        backed=old.backed if old is not None else False,
        founder_known=old.founder_known if old is not None else False,
        coi_turn=old.coi_turn if old is not None else None,
        coi_answer=old.coi_answer if old is not None else None,
        coi_found_turn=old.coi_found_turn if old is not None else None,
    )
    state = with_angel_stake(state, record)
    state = post(
        state,
        person_id,
        f"Angel investment in {company.name}",
        "angel",
        ANGEL,
        PERSONAL_CASH,
        cents,
    )
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=company_id,
        memo="Funding round: the founder of a rival, personally",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=cents,
    )
    state = information_rights(state, company_id, rng, balance, data)
    state = _competing_conflict(state, record, data)
    log = inbox_item(
        state.turn,
        state.player.id,
        "angel_invested",
        link_kind=LINK,
        link_id=company_id,
        company=company.name,
        amount_cents=cents,
        pct=f"{stake / STAKE_FULL:.1%}",
    )
    return state, (entry,), (log,)


def information_rights(
    state: GameState, company_id: int, rng: RngFactory, balance: Balance, data: GameData
) -> GameState:
    """37.2: the startup's key people, learned by the scouting rules (as 31.5's venture)."""
    from tst.sim.rivals.ceo_knowledge import learn_of_ceo

    for e in state.staff(company_id):
        state = learn_of_ceo(state, e.person_id, "rival_diligence", rng, balance, data)
    return state


# --- The network and backing a new startup ---------------------------------------------------


def group_ids(state: GameState) -> set[int]:
    """The player's companies and every company their group owns (31.1)."""
    ids = {c.id for c in group_companies(state, listed_id(state))}
    return ids | {state.player.id}


def network(state: GameState) -> list[Person]:
    """37.2: people the founder could back: those who left the player's companies (the last
    angel.network_size, `state.network`) and work for no company in the group, and
    candidates in the player's own searches. (The Hall of Fame holds past games' founders,
    not colleagues: M26 decision.) By person id."""
    mine = group_ids(state)
    founder = state.founder_of(state.player.id)
    seen = {e.person_id for e in state.network}
    seen |= {c.person_id for c in state.open_candidates(state.player.id)}
    out: list[Person] = []
    for pid in sorted(seen):
        job = state.employment_of(pid)
        if job is not None and job.company_id in mine:
            continue
        try:
            person = state.person(pid)
        except KeyError:
            continue
        if person.is_founder or (founder is not None and pid == founder.id):
            continue
        if job is not None:
            company = state.company(job.company_id)
            if company.is_startup and job.level == "exec":  # already founding one
                continue
        out.append(person)
    return out


def network_month(state: GameState, balance: Balance) -> GameState:
    """Phase 12: people whose employment at the player's group ended this month join the
    founder's network (37.2)."""
    mine = group_ids(state)
    founder = state.founder_of(state.player.id)
    left = [
        NetworkEntry(e.person_id, state.turn)
        for e in state.employments
        if e.company_id in mine
        and e.status == "ended"
        and e.end_turn == state.turn
        and e.end_reason != "retired"
        and (founder is None or e.person_id != founder.id)
    ]
    return with_network(state, left, balance.angel.network_size)


def known_well(state: GameState, person_id: int, data: GameData, balance: Balance) -> bool:
    """37.2: the player knows a person well when the mean half-width of their skills'
    revealed ranges is at most angel.known_hw."""
    reveal = state.reveal(state.player.id, person_id)
    if reveal is None:
        return False
    skills = set(data.skill_keys)
    widths = [rec.hw for key, rec in reveal.attributes if key in skills]
    return bool(widths) and fmean(widths) <= balance.angel.known_hw


def seed_stake(cents: int, balance: Balance) -> float:
    """37.2: the founder's stake when backing a new startup, from the bottom of
    angel.seed_stake at the smallest cheque to its top at angel.seed_full_cents."""
    ab = balance.angel
    lo, hi = ab.seed_stake
    f = (cents - ab.min_cheque_cents) / (ab.seed_full_cents - ab.min_cheque_cents)
    return lo + (hi - lo) * min(1.0, max(0.0, f))


def mean_true_skill(person: Person, data: GameData) -> float:
    skills = set(data.skill_keys)
    values = [v for k, v in person.skills.items if k in skills]
    return fmean(values) if values else SKILL_MID


def back_startup(
    state: GameState,
    person_id: int,
    founder_id: int,
    category_key: str,
    cents: int,
    gen: np.random.Generator,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """37.2: a new rival startup with a network founder, the cheque its founding cash. Its
    name, personality, team size and segments come from the action's generator in that order;
    its team from people_gen (15.4)."""
    from tst.sim.rivals import startups as su

    ab = balance.angel
    sb = balance.rivals.startup
    if cents < ab.min_cheque_cents:
        raise InvalidActionError(
            f"backing a new startup takes at least ${ab.min_cheque_cents // 100:,}"
        )
    _check_cash(state, person_id, cents)
    if founder_id not in {p.id for p in network(state)}:
        raise InvalidActionError("that person is not in your network")
    keys = [c.key for c in data.categories]
    if category_key not in keys:
        raise InvalidActionError(f"unknown category {category_key!r}")
    category = data.category(category_key)
    if category.capacity_market or category.sells_units or category.assembly_market:
        raise InvalidActionError(f"a new startup cannot start in {category.label}")
    taken = {c.name for c in state.companies}
    names = [n for n in data.startup_names if n not in taken]
    if not names:
        raise InvalidActionError("no startup names are left")
    known = known_well(state, founder_id, data, balance)
    name = names[int(gen.integers(0, len(names)))]
    personality = sb.personalities[int(gen.integers(0, len(sb.personalities)))]
    team = int(gen.integers(ab.team[0], ab.team[1], endpoint=True))
    segments_all = list(category.segment_keys)
    count = min(len(segments_all), 1 + int(gen.integers(0, 2)))
    picks = sorted(int(i) for i in gen.choice(len(segments_all), size=count, replace=False))
    founder = state.person(founder_id)
    extra = round(cents * ab.skill_runway * max(0.0, mean_true_skill(founder, data) - SKILL_MID))
    index = keys.index(category_key)
    state, company, entry = su.found_company(
        state,
        name,
        personality,
        category,
        [segments_all[i] for i in picks],
        cents,
        key_people_split(team, su._mix(category.key, balance)),
        [su.TEAM_LEVEL] * team,
        rng,
        balance,
        data,
        rival_key=su.startup_key(state, index),
    )
    state = _employ_founder(state, company, founder, balance, data)
    product_id = state.company_products(company.id)[0].id
    region = su.founding_region(state, rng, company, category, balance, data)
    state = su.sell_first_in(state, company, product_id, region, balance, data)
    state, _ = su._record(
        state, company, "founded", f"was founded in {category.label}, backed by an angel"
    )
    entries = [entry]
    if extra > 0:  # angel.skill_runway: a strong founder's network brings more money
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=company.id,
                memo=FOUNDING_MEMO,
                debit=CASH,
                credit=COMMON_EQUITY,
                amount=extra,
            )
        )
    share = seed_stake(cents, balance)
    stake_ppm = round(share * STAKE_FULL)
    post_cents = round(Fraction(cents * STAKE_FULL, stake_ppm))
    state, _ = record_round(state, company.id, cents, post_cents, "backed")
    record = AngelStake(
        id=next_record_id(state.angel_stakes),
        person_id=person_id,
        company_id=company.id,
        stake_ppm=stake_ppm,
        cost_cents=cents,
        from_turn=state.turn,
        last_post_cents=post_cents,
        backed=True,
        founder_known=known,
    )
    state = with_angel_stake(state, record)
    state = post(state, person_id, f"Backed {company.name}", "angel", ANGEL, PERSONAL_CASH, cents)
    state = information_rights(state, company.id, rng, balance, data)
    state = _competing_conflict(state, record, data)
    log = inbox_item(
        state.turn,
        state.player.id,
        "angel_backed",
        link_kind=LINK,
        link_id=company.id,
        company=company.name,
        founder=f"{founder.first_name} {founder.last_name}",
        amount_cents=cents,
        pct=f"{share:.0%}",
    )
    return state, tuple(entries), (log,)


def _employ_founder(
    state: GameState, company: CompanyState, person: Person, balance: Balance, data: GameData
) -> GameState:
    """The network founder leaves any job and leads the new startup (an exec builder)."""
    from tst.sim.rivals.setup import market_salary_cents

    job = state.employment_of(person.id)
    if job is not None:
        state = with_employment(
            state,
            replace(job, status="ended", end_turn=state.turn, end_reason="resigned"),
        )
    candidate = state.candidate(person.id)
    if candidate is not None and candidate.status == "open":
        state = with_candidate(
            state, replace(candidate, status="withdrawn", resolved_turn=state.turn)
        )
    role = data.role(balance.rivals.function_roles["builder"])
    level = "exec"  # tunable-exempt: 15.4's founder is the startup's top person
    salary = round(
        market_salary_cents(role.key, level, balance, data) * balance.rivals.startup.salary_mult
    )
    emp_id, ids = state.next_ids.take("rival_employment")
    state = replace(state, next_ids=ids)
    return with_employment(
        state,
        Employment(
            id=emp_id,
            person_id=person.id,
            company_id=company.id,
            role=role.key,
            level=level,
            salary_cents=salary,
            equity_bp=0,
            start_turn=state.turn,
            end_turn=None,
            status="active",
        ),
    )


# --- Conflicts of interest ------------------------------------------------------------------


def _competing_conflict(state: GameState, stake: AngelStake, data: GameData) -> GameState:
    """37.2: an angel-backed startup competing with the player's company (a category the
    player sells in) raises a conflict of interest, once per stake."""
    if stake.coi_turn is not None:
        return state
    from tst.sim.products.models import SELLING

    mine = {p.category for p in state.company_products(state.player.id) if p.status in SELLING}
    theirs = {p.category for p in state.company_products(stake.company_id)}
    if not mine & theirs:
        return state
    return raise_conflict(state, stake)


def raise_conflict(state: GameState, stake: AngelStake) -> GameState:
    state = with_angel_stake(state, replace(stake, coi_turn=state.turn))
    return queue(state, state.player.id, CONFLICT_TEMPLATE, state.turn + 1)


def answer_conflict(state: GameState, step: str, rng: RngFactory, balance: Balance) -> GameState:
    """The conflict event's answer: disclose and recuse (no effect), or conceal, when a draw
    (stream personal, key (1, stake id)) decides whether and when it comes out."""
    pb = balance.personal
    for stake in state.angel_stakes:
        if stake.coi_turn is None or stake.coi_answer is not None:
            continue
        found: int | None = None
        if step == "conceal":
            gen = personal_draws(rng, stake.coi_turn, draws.CONFLICT, stake.id)
            if float(gen.random()) < pb.coi_found_p:
                found = state.turn + 1 + int(float(gen.random()) * pb.coi_found_months)
        state = with_angel_stake(state, replace(stake, coi_answer=step, coi_found_turn=found))
    return state


# --- The month ------------------------------------------------------------------------------


def stakes_month(
    state: GameState,
    new_rounds: list[StartupRound],
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LogItem]]:
    """Phase 12 (37.2): rounds dilute open stakes; acquisitions pay out, listings become
    public shares, failures are written off; the player's group agreeing to buy a held
    startup raises a conflict of interest; a concealed conflict may come out."""
    logs: list[LogItem] = []
    turn = state.turn
    venture = [r for r in state.startup_rounds if r.turn == turn and r.source == "venture"]
    for rnd in (*new_rounds, *venture):
        for stake in state.angel_stakes:
            if stake.company_id != rnd.company_id or stake.status != "open":
                continue
            if stake.from_turn == turn and rnd.source == "founded":
                continue
            kept = int(
                Fraction(stake.stake_ppm * (rnd.post_cents - rnd.raised_cents), rnd.post_cents)
            )
            state = with_angel_stake(
                state, replace(stake, stake_ppm=kept, last_post_cents=rnd.post_cents)
            )
    mine = group_ids(state)
    for stake in state.angel_stakes:
        if stake.status != "open":
            continue
        company = state.company(stake.company_id)
        agreed = [
            d
            for d in state.deals
            if d.target_id == company.id and d.made_turn == turn and d.acquirer_id in mine
        ]
        if agreed and stake.coi_turn is None:
            state = raise_conflict(state, stake)
            stake = next(s for s in state.angel_stakes if s.id == stake.id)
        closed = next(
            (
                d
                for d in state.deals
                if d.target_id == company.id and d.status == "closed" and d.resolved_turn == turn
            ),
            None,
        )
        if closed is not None:
            state, log = _payout(state, stake, closed.price_cents, closed.acquirer_id in mine)
            logs.append(log)
            continue
        from tst.sim.mna.valuation import is_listed

        if is_listed(state, company.id, data):
            state, log = _to_public(state, stake, balance)
            logs.append(log)
            continue
        if not company.alive:
            state = post(
                state,
                stake.person_id,
                f"{company.name} failed: written off",
                "angel",
                LOSSES,
                ANGEL,
                stake.cost_cents,
            )
            state = with_angel_stake(state, replace(stake, status="failed", closed_turn=turn))
            logs.append(
                inbox_item(
                    turn,
                    state.player.id,
                    "angel_written_off",
                    link_kind=LINK,
                    link_id=company.id,
                    company=company.name,
                    amount_cents=stake.cost_cents,
                )
            )
    return state, logs


def _payout(
    state: GameState, stake: AngelStake, price_cents: int, related: bool
) -> tuple[GameState, LogItem]:
    company = state.company(stake.company_id)
    proceeds = int(Fraction(stake.stake_ppm, STAKE_FULL) * price_cents)
    state = post(
        state,
        stake.person_id,
        f"{company.name} acquired: your stake",
        "angel",
        PERSONAL_CASH,
        ANGEL,
        stake.cost_cents,
    )
    gain = proceeds - stake.cost_cents
    if gain > 0:
        state = post(
            state, stake.person_id, f"Gain on {company.name}", "angel", PERSONAL_CASH, GAINS, gain
        )
    elif gain < 0:
        state = post(
            state, stake.person_id, f"Loss on {company.name}", "angel", LOSSES, PERSONAL_CASH, -gain
        )
    state = with_angel_stake(
        state,
        replace(stake, status="acquired", closed_turn=state.turn, proceeds_cents=proceeds),
    )
    log = inbox_item(
        state.turn,
        state.player.id,
        "angel_exit",
        link_kind=LINK,
        link_id=company.id,
        company=company.name,
        amount_cents=proceeds,
        related="yes" if related else "no",
    )
    return state, log


def _to_public(state: GameState, stake: AngelStake, balance: Balance) -> tuple[GameState, LogItem]:
    company = state.company(stake.company_id)
    shares = int(
        Fraction(stake.stake_ppm, STAKE_FULL) * shares_outstanding(state, company.id, balance)
    )
    held = holding_in(state, stake.person_id, company.id)
    from tst.sim.founder.investing_models import PublicHolding

    state = with_public_holding(
        state,
        PublicHolding(
            stake.person_id,
            company.id,
            (held.shares if held else 0) + shares,
            (held.cost_cents if held else 0) + stake.cost_cents,
        ),
    )
    state = post(
        state,
        stake.person_id,
        f"{company.name} listed",
        "angel",
        PUBLIC_SHARES,
        ANGEL,
        stake.cost_cents,
    )
    state = with_angel_stake(state, replace(stake, status="listed", closed_turn=state.turn))
    log = inbox_item(
        state.turn,
        state.player.id,
        "angel_listed",
        link_kind=LINK,
        link_id=company.id,
        company=company.name,
        shares=f"{shares:,}",
    )
    return state, log
