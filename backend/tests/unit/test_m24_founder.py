"""M24 the founder's life (docs/formulas.md 32.2-32.6): the personal book (property tests: it
balances and never mixes with a company's books), the founder's share sale, dividends and
exits; the foundation's creation, gifts, grants and effects; the persona's sources, drift and
effects; lobbying, influence, antitrust and scandals (a seeded test of their timing); and the
legacy score."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import DATA_DIR
from tests.helpers import fresh_game, make_person, with_employee
from tests.unit.test_m13_public import LISTED
from tst.loader import load_all
from tst.sim.actions import (
    CreateFoundation,
    GiveToFoundation,
    SellFounderShares,
    SetLobbying,
    apply_action,
)
from tst.sim.errors import InsufficientEnergyError, InvalidActionError, UnbalancedEntryError
from tst.sim.finance.captable import person_shares
from tst.sim.founder import effects, foundation, influence, legacy, persona, personal, stress
from tst.sim.founder.config import SOURCES, TRAITS
from tst.sim.founder.models import (
    ENDOWMENT,
    PERSONAL_ACCOUNTS,
    PERSONAL_CASH,
    PERSONAL_INCOME,
    PERSONAL_SPENDING,
    Influence,
    PersonalEntry,
)
from tst.sim.founder.phase import founder_month
from tst.sim.ledger import CASH, LOBBYING, LedgerEntry, LedgerLine
from tst.sim.markets_public.public import public_float
from tst.sim.modes.models import CompanyScore
from tst.sim.press.models import PressMoment
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    credibility_of,
    foundation_of,
    influence_of,
    life_of,
    with_influence,
    with_life,
    with_press_moment,
)

LOADED = load_all(DATA_DIR)
B, D = LOADED.balance, LOADED.game_data
CID = 1
MILLION = 100_000_000  # cents
BIG = {(CID, CASH): 10**13}


def _fid(state: GameState) -> int:
    founder = state.founder_of(CID)
    assert founder is not None
    return founder.id


def _act(state: GameState, action: object) -> GameState:
    return apply_action(state, action, RngFactory(1), B, D, BIG, seq=1).new_state  # type: ignore[arg-type]


def _rich(state: GameState, cents: int = 20 * MILLION) -> GameState:
    return personal.credit(state, _fid(state), cents, "exit")


# --- 32.2 The personal book --------------------------------------------------------------------


def test_personal_entries_refuse_company_accounts_and_company_entries_refuse_9xxx() -> None:
    with pytest.raises(UnbalancedEntryError):
        PersonalEntry(0, 1, "x", "exit", (LedgerLine(CASH, 5), LedgerLine(PERSONAL_INCOME, -5)))
    with pytest.raises(UnbalancedEntryError):
        LedgerEntry.transfer(
            turn=0, company_id=1, memo="x", debit=PERSONAL_CASH, credit=CASH, amount=5
        )
    with pytest.raises(UnbalancedEntryError):  # unbalanced
        PersonalEntry(
            0, 1, "x", "exit", (LedgerLine(PERSONAL_CASH, 5), LedgerLine(PERSONAL_INCOME, -4))
        )


def test_data_keeps_the_charts_apart() -> None:
    company = {a.code for a in D.accounts}
    mine = {a.code for a in D.personal_accounts}
    assert mine == set(PERSONAL_ACCOUNTS)
    assert not company & mine
    assert not any(code.startswith("9") for code in company)


@settings(max_examples=150, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.sampled_from(("secondary", "dividend", "exit", "salary", "gift", "grant")),
            st.integers(min_value=1, max_value=10**12),
        ),
        max_size=40,
    )
)
def test_the_personal_book_balances(ops: list[tuple[str, int]]) -> None:
    """Every entry balances, the book sums to zero, cash and the endowment never go below
    zero, and no entry touches a company account."""
    state = fresh_game(LOADED)
    fid = _fid(state)
    for kind, cents in ops:
        if kind in ("gift", "grant"):
            have = (
                personal.cash_cents(state, fid)
                if kind == "gift"
                else personal.endowment_cents(state, fid)
            )
            cents = min(cents, have)
            if cents <= 0:
                continue
            state = (personal.gift if kind == "gift" else personal.grant)(state, fid, cents)
        else:
            state = personal.credit(state, fid, cents, kind)
    totals = personal.book_balances(state.personal_book, fid)
    assert sum(totals.values()) == 0
    assert totals.get(PERSONAL_CASH, 0) >= 0 and totals.get(ENDOWMENT, 0) >= 0
    income = sum(c for k, c in ops if k not in ("gift", "grant"))
    assert -totals.get(PERSONAL_INCOME, 0) == income
    assert (
        totals.get(PERSONAL_CASH, 0) + totals.get(ENDOWMENT, 0) + totals.get(PERSONAL_SPENDING, 0)
        == income
    )
    for entry in state.personal_book:
        assert sum(line.amount for line in entry.lines) == 0
        assert all(line.account in PERSONAL_ACCOUNTS for line in entry.lines)


@settings(max_examples=10, deadline=None)
@given(st.integers(min_value=0, max_value=3), st.integers(min_value=0, max_value=4_000_000))
def test_company_ledgers_never_touch_personal_accounts(months: int, lobbying: int) -> None:
    """A founder who lobbies, gives and is paid: the company entries of the months post to
    company accounts only, and personal entries only to personal ones."""
    from tst.sim.decisions import Decisions
    from tst.sim.ledger import apply_entries
    from tst.sim.turn import advance_turn

    state = _rich(fresh_game(LOADED))
    state = _act(state, SetLobbying(_fid(state), "north_america", lobbying))
    balances = dict(BIG)
    entries: list[LedgerEntry] = []
    for _ in range(months + 1):
        result = advance_turn(state, Decisions(), RngFactory(5), B, D, balances)
        entries += result.ledger_entries
        balances = apply_entries(balances, result.ledger_entries)
        state = result.new_state
    company_codes = {a.code for a in D.accounts}
    for entry in entries:
        assert all(line.account in company_codes for line in entry.lines)
    assert all(k[1] in company_codes for k in balances)
    for p in state.personal_book:
        assert all(line.account in PERSONAL_ACCOUNTS for line in p.lines)
    spent = sum(line.amount for e in entries for line in e.lines if line.account == LOBBYING)
    assert spent == (months + 1) * lobbying * 100


def test_founder_sells_shares_into_the_float() -> None:
    state = LISTED
    fid = _fid(state)
    held = person_shares(state, CID, fid)
    floated = public_float(state, CID)
    shares = held // 10
    state = replace(state, person_states=state.person_states)
    out = apply_action(state, SellFounderShares(fid, shares), RngFactory(1), B, D, BIG, seq=1)
    after = out.new_state
    assert out.ledger_entries == ()  # the company's books do not move
    assert person_shares(after, CID, fid) == held - shares
    assert public_float(after, CID) == floated + shares
    public = after.public_companies[0]
    gross = shares * round(public.price_cents * 0.95)
    net = gross - round(gross * 0.03)
    assert personal.cash_cents(after, fid) == net
    assert personal.income_by_source(after, fid)["secondary"] == net
    with pytest.raises(InvalidActionError):
        _act(after, SellFounderShares(fid, held * 2))


def test_sale_needs_a_listing() -> None:
    state = fresh_game(LOADED)
    with pytest.raises(InvalidActionError):
        _act(state, SellFounderShares(_fid(state), 10))


def test_dividend_share_reaches_the_book() -> None:
    state = LISTED
    fid = _fid(state)
    after = personal.dividend_share(state, CID, 7)
    assert personal.cash_cents(after, fid) == 7 * person_shares(state, CID, fid)


def test_salary_after_tax() -> None:
    state = fresh_game(LOADED)
    fid = _fid(state)
    job = state.employment_of(fid)
    assert job is not None
    assert personal.salary_month(state, B) == state  # a founder on 0 salary gets nothing
    from tst.sim.state import with_employment

    paid = with_employment(state, replace(job, salary_cents=1_000_000))
    out = personal.salary_month(paid, B)
    assert personal.cash_cents(out, fid) == 650_000


# --- 32.3 The foundation -------------------------------------------------------------------


def test_create_needs_a_million_and_energy() -> None:
    state = fresh_game(LOADED)
    fid = _fid(state)
    with pytest.raises(InvalidActionError):
        _act(state, CreateFoundation(fid, "education"))
    state = _rich(state, MILLION)
    with pytest.raises(InvalidActionError):
        _act(state, CreateFoundation(fid, "sports"))
    made = _act(state, CreateFoundation(fid, "education"))
    f = foundation_of(made, fid)
    assert f is not None and f.cause == "education" and f.region == "north_america"
    assert made.person_state(fid).energy == state.person_state(fid).energy - B.foundation.energy  # type: ignore[operator]
    with pytest.raises(InvalidActionError):
        _act(made, CreateFoundation(fid, "climate"))
    from tst.sim.state import with_person_state

    tired = with_person_state(state, replace(state.person_state(fid), energy=1))
    with pytest.raises(InsufficientEnergyError):
        _act(tired, CreateFoundation(fid, "health"))


def _with_foundation(cause: str, gift: int, turn: int = 11) -> GameState:
    state = _rich(fresh_game(LOADED), gift)
    fid = _fid(state)
    state = _act(state, CreateFoundation(fid, cause))
    state = _act(state, GiveToFoundation(fid, gift))
    state = with_life(state, stress.new_life(fid, B))
    return replace(state, turn=turn)


def test_gift_and_december_grants() -> None:
    state = _with_foundation("education", 200 * MILLION)
    fid = _fid(state)
    assert personal.cash_cents(state, fid) == 0
    assert personal.endowment_cents(state, fid) == 200 * MILLION
    with pytest.raises(InvalidActionError):
        _act(state, GiveToFoundation(fid, 1))
    out, logs = foundation.grants_month(state, B)
    f = foundation_of(out, fid)
    assert f is not None and f.last_grant_cents == 10 * MILLION  # 5% of $200M
    assert personal.endowment_cents(out, fid) == 190 * MILLION
    assert [log.template for log in logs] == ["foundation_grants"]
    life = life_of(out, fid)
    assert life is not None
    # 32.7 target 5: $10M a year raises Beloved by 5-10 (k x log10(100) = 2k).
    assert 5 <= life.beloved - B.persona.start <= 10
    assert any(q.template_id == "founder_first_grants" for q in out.queued)
    # Not in other months.
    assert foundation.grants_month(replace(state, turn=10), B)[0] == replace(state, turn=10)


def test_grant_effects_by_cause_and_their_twelve_months() -> None:
    out, _ = foundation.grants_month(_with_foundation("education", 200 * MILLION), B)
    # 32.7 target 5: at most 0.03 of hiring appeal from $10M a year.
    assert effects.education_points(out, CID, B) == pytest.approx(0.03)
    assert effects.hiring_points(out, CID, "software_engineer", B, D) == pytest.approx(0.03)
    later = replace(out, turn=out.turn + B.foundation.effect_months)
    assert effects.education_points(later, CID, B) == 0.0
    small, _ = foundation.grants_month(_with_foundation("education", 20 * MILLION), B)
    assert effects.education_points(small, CID, B) == pytest.approx(0.003)
    climate, _ = foundation.grants_month(_with_foundation("climate", 20 * MILLION), B)
    assert effects.consumer_brand(climate, CID, B) == B.foundation.brand
    health, _ = foundation.grants_month(_with_foundation("health", 20 * MILLION), B)
    assert effects.morale_points(health, CID, B) == B.foundation.morale
    local, _ = foundation.grants_month(_with_foundation("local", 20 * MILLION), B)
    assert effects.pool_bonus(local, CID, B) == B.foundation.pool


def test_beloved_from_grants() -> None:
    assert foundation.beloved_from(100_000 * 100, B) == 0.0
    assert foundation.beloved_from(10 * MILLION, B) == pytest.approx(2 * B.foundation.beloved_k)
    assert foundation.beloved_from(10**15, B) == B.foundation.beloved_cap


# --- 32.4 Persona ----------------------------------------------------------------------------


def test_every_source_raises_its_trait_and_traits_drift() -> None:
    life = stress.new_life(1, B)
    for source, trait in SOURCES.items():
        raised = persona.apply_source(life, source, 0, B)
        assert raised.trait(trait) == B.persona.start + B.persona.sources[source]
        assert raised.trait_causes[-1][1] == trait
    high = replace(life, visionary=30.0, reckless=19.0, ruthless=21.0)
    drifted = persona.drift(high, B)
    assert (drifted.visionary, drifted.reckless, drifted.ruthless) == (28.0, 20.0, 20.0)
    assert persona.top_trait(replace(life, beloved=40.0)) == "beloved"
    assert persona.top_trait(life) == TRAITS[0]


def _with_trait(state: GameState, trait: str, value: float = 70.0) -> GameState:
    life = stress.new_life(_fid(state), B)
    return with_life(state, replace(life, **{trait: value}))  # type: ignore[arg-type]


def test_persona_effects_apply_at_sixty() -> None:
    state = fresh_game(LOADED)
    plain = with_life(state, stress.new_life(_fid(state), B))
    assert effects.hiring_points(plain, CID, "software_engineer", B, D) == 0.0
    assert effects.morale_points(plain, CID, B) == 0.0
    assert effects.resign_factor(plain, CID, B) == 1.0
    assert effects.feud_factor(plain, CID, B) == 1.0
    assert effects.cred_target(plain, CID, B) == B.press.cred_start
    visionary = _with_trait(state, "visionary")
    assert effects.hiring_points(visionary, CID, "software_engineer", B, D) == 0.03
    assert effects.hiring_points(visionary, CID, "account_executive", B, D) == 0.0
    ruthless = _with_trait(state, "ruthless")
    assert effects.morale_points(ruthless, CID, B) == -2
    assert effects.feud_factor(ruthless, CID, B) == 1.3
    assert influence.antitrust_factor(ruthless, CID, "north_america", B) == pytest.approx(1.1)
    assert effects.resign_factor(_with_trait(state, "beloved"), CID, B) == 0.9
    assert effects.cred_target(_with_trait(state, "reckless"), CID, B) == 45
    assert effects.cred_target(_with_trait(state, "reckless", 59.9), CID, B) == 50


def test_month_sources_bold_answer_and_kept_promise() -> None:
    from tst.sim.press.models import Promise
    from tst.sim.state import with_promise

    state = fresh_game(LOADED)
    turn = state.turn
    moment = PressMoment(1, CID, "launch", turn, "answered", tone="bold", answered_turn=turn)
    state = with_press_moment(state, moment)
    state = with_promise(
        state,
        Promise(1, CID, "ship", turn - 3, turn, status="kept", resolved_turn=turn),
    )
    out, _, _ = founder_month(state, state, RngFactory(1), B, D, holiday=False)
    life = life_of(out, _fid(state))
    assert life is not None
    assert life.visionary == B.persona.start + 3
    assert life.beloved == B.persona.start + 4


def test_raises_across_the_company() -> None:
    from tst.sim.state import with_employment

    state = fresh_game(LOADED)
    for pid in range(2, 6):
        state = with_employee(LOADED, state, make_person(LOADED, pid), 9_000_000)
    staff = [e for e in state.staff(CID) if e.role != "founder"]
    for e in staff[:1]:  # 1 of 4: 25%
        state = with_employment(state, replace(e, last_raise_turn=state.turn))
    out, _, _ = founder_month(state, state, RngFactory(1), B, D, holiday=False)
    life = life_of(out, _fid(state))
    assert life is not None and life.beloved == B.persona.start + 2


# --- 32.5 Influence and scandals -------------------------------------------------------------


def test_lobbying_builds_influence_and_risk() -> None:
    state = _act(fresh_game(LOADED), SetLobbying(1, "north_america", 500_000))
    record = influence_of(state, CID, "north_america")
    assert record is not None and record.spend_cents == 50_000_000
    with pytest.raises(InvalidActionError):
        _act(state, SetLobbying(1, "atlantis", 1))
    with pytest.raises(InvalidActionError):
        _act(state, SetLobbying(1, "europe", B.influence.max_monthly_dollars + 1))
    out, entries, _ = influence.lobbying_month(state, RngFactory(1), B, D)
    after = influence_of(out, CID, "north_america")
    assert after is not None
    assert after.value == pytest.approx(3 * math.sqrt(5))
    assert after.risk == pytest.approx(500 * B.influence.risk_rate)
    (entry,) = entries
    assert {line.account: line.amount for line in entry.lines} == {
        LOBBYING: 50_000_000,
        CASH: -50_000_000,
    }
    # Influence approaches the cap; antitrust blocks fall by up to 40%.
    capped = with_influence(out, replace(after, value=100.0))
    assert influence.antitrust_factor(capped, CID, "north_america", B) == pytest.approx(0.6)
    assert influence.of(capped, CID, "europe") == 0.0


def test_exposure_band_only() -> None:
    assert influence.exposure(0.0, B) == "low"
    assert influence.exposure(15.0, B) == "medium"
    assert influence.exposure(45.0, B) == "high"


def _scandal_months(seed: int, months: int = 120) -> list[int]:
    state = fresh_game(LOADED)
    state = with_influence(
        state, Influence(CID, "north_america", spend_cents=50_000_000, started_turn=0)
    )
    broke = []
    for t in range(months):
        state = replace(state, turn=t)
        state, _, logs = influence.lobbying_month(state, RngFactory(seed), B, D)
        if any(log.template == "scandal_broke" for log in logs):
            broke.append(t)
    return broke


def test_scandal_timing_is_seeded() -> None:
    """Same seed, same months; another seed, other months (stream founder_life)."""
    first = _scandal_months(11)
    assert first == _scandal_months(11)
    assert any(_scandal_months(s) != first for s in (12, 13, 14))


def test_a_scandal_hits_and_queues_its_event() -> None:
    state = fresh_game(LOADED)
    fid = _fid(state)
    state = with_life(state, stress.new_life(fid, B))
    state = with_influence(state, Influence(CID, "north_america", value=50.0))
    out, _entries, logs = influence.break_scandal(state, CID, "north_america", True, B, D)
    cred = credibility_of(out, CID)
    assert cred is not None and cred.value == B.press.cred_start - 15
    record = influence_of(out, CID, "north_america")
    assert record is not None and record.value == 0 and record.scandal_turns == (state.turn,)
    life = life_of(out, fid)
    assert life is not None and (life.ruthless, life.reckless) == (30.0, 25.0)
    assert any(q.template_id == "founder_scandal" for q in out.queued)
    assert [log.template for log in logs] == ["scandal_broke"]
    # Fighting brings the drawn second story; apologizing costs credibility and stress.
    event_turn = state.turn + 1
    shown = replace(out, turn=event_turn)
    fought, more = influence.answer_scandal(shown, CID, event_turn, "fight", B)
    assert [log.template for log in more] == ["scandal_second_story"]
    assert credibility_of(fought, CID).value == B.press.cred_start - 30  # type: ignore[union-attr]
    sorry, _ = influence.answer_scandal(shown, CID, event_turn, "apologize", B)
    assert credibility_of(sorry, CID).value == B.press.cred_start - 20  # type: ignore[union-attr]
    assert life_of(sorry, fid).stress == B.stress.start + 10  # type: ignore[union-attr]


# --- 32.6 Legacy -----------------------------------------------------------------------------


def test_legacy_formula() -> None:
    state = fresh_game(LOADED)
    fid = _fid(state)
    life = replace(stress.new_life(fid, B), visionary=60.0, beloved=40.0, ruthless=30.0)
    state = with_life(state, life)
    score = CompanyScore(CID, 12, 500, 0, 0.0, 0.0, 0.0, 0.0, 0)
    state = replace(state, scores=(score, replace(score, turn=24, score=420)))
    from tst.sim.founder.models import Foundation
    from tst.sim.state import with_foundation

    state = with_foundation(state, Foundation(fid, "F", "health", 0, grants_cents=9 * MILLION))
    out = legacy.legacy_of(state, B)
    expected = 500 + 100 * math.log10(1 + 9) + 2 * (60 + 40) - (30 + 20)
    assert out.total == round(expected)
    assert out.best_score == 500 and out.giving == pytest.approx(100.0)
    assert out.persona == pytest.approx(150.0)


def test_persona_in_public_words_and_event_names() -> None:
    """32.4: press, staff and rival texts name the strongest trait once it is above 20."""
    from tst.events.drafts import event_names
    from tst.sim.events.models import GameEvent

    state = fresh_game(LOADED)
    assert persona.public_words(state, CID, B) == persona.UNKNOWN_WORDS
    state = _with_trait(state, "reckless", 35.0)
    assert persona.public_words(state, CID, B) == "reckless"
    event = GameEvent(1, CID, state.turn, "press_launch", "press", "major", "press", 1.0)
    assert event_names(state, event, D, B)["persona"] == "reckless"


# --- Reckless sources of the product manager's ruling (2026-11-07, 32.7 target 3) -----------


def _burning(state: GameState, burn: int = 1_000_000) -> GameState:
    from tst.sim.state import with_company

    return with_company(state, replace(state.player, burn_history=(burn,)))


def _month(state: GameState, cash: int) -> GameState:
    out, _, _ = founder_month(state, state, RngFactory(1), B, D, holiday=False, cash_cents=cash)
    return out


def test_runway_burn_raises_reckless_capped_each_year() -> None:
    state = _burning(fresh_game(LOADED))
    fid = _fid(state)
    size, cap = B.persona.sources["runway_burn"], B.persona.burn_year_cap
    assert life_of(_month(state, 7_000_000), fid).reckless == B.persona.start  # type: ignore[union-attr]
    raised = _month(state, 5_000_000)  # 5 months of runway
    assert life_of(raised, fid).reckless == B.persona.start + size  # type: ignore[union-attr]
    assert life_of(_month(_burning(state, 0), 0), fid).reckless == B.persona.start  # type: ignore[union-attr]
    # The cap: at most burn_year_cap points in a calendar year (drift aside).
    total = 0.0
    for t in range(12):
        state = _month(replace(state, turn=t), 1)
        total = life_of(state, fid).burn_points  # type: ignore[union-attr]
    assert total == cap
    state = _month(replace(state, turn=12), 1)  # a new year
    assert life_of(state, fid).burn_points == size  # type: ignore[union-attr]


def test_down_round_raises_reckless() -> None:
    from tst.sim.finance.models import FundingRound

    state = fresh_game(LOADED)
    fid = _fid(state)
    down = FundingRound(99, CID, "a", "closed", 1, 0, 1, closed_turn=state.turn, down_round=True)
    state = replace(state, rounds=(*state.rounds, down))
    life = life_of(_month(state, 10**10), fid)
    assert life is not None and life.reckless == B.persona.start + B.persona.sources["down_round"]
    flat = replace(state, rounds=(*state.rounds[:-1], replace(down, down_round=False)))
    assert life_of(_month(flat, 10**10), fid).reckless == B.persona.start  # type: ignore[union-attr]


def test_headcount_doubled_in_a_year() -> None:
    state = fresh_game(LOADED)
    fid = _fid(state)
    state = with_life(state, replace(stress.new_life(fid, B), headcount_mark=2))
    december = replace(state, turn=11)
    same = life_of(_month(december, 10**10), fid)
    assert same is not None and same.reckless == B.persona.start  # 1 (the founder) of 2
    for pid in range(2, 7):
        december = with_employee(LOADED, december, make_person(LOADED, pid), 9_000_000)
    grown = life_of(_month(december, 10**10), fid)  # 6 > 2 x 2
    assert grown is not None
    assert grown.reckless == B.persona.start + B.persona.sources["headcount_doubled"]
    assert grown.headcount_mark == 6
    # Not in other months, and not without last December's mark.
    assert life_of(_month(replace(december, turn=10), 10**10), fid).headcount_mark == 2  # type: ignore[union-attr]
