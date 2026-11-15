"""M36r (Codex review 7; docs/tasks/M36r-review-7-fixes.md): each finding's regression test,
written first and seen failing on m30-done."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select

from tst.balance import m22
from tst.balance.game import PLAYER, Game
from tst.balance.m27b import add_staff_at
from tst.loader import LoadedData
from tst.sim.actions import apply_action
from tst.sim.actions.authority import AnswerProposal
from tst.sim.automation import owners, scope
from tst.sim.automation.config import NEVER_ACTIONS
from tst.sim.automation.models import AreaOwner
from tst.sim.automation.run import AutoRun
from tst.sim.calendar import ym_to_turn
from tst.sim.commodities.models import CommodityDeal
from tst.sim.commodities.offtake import spot_price
from tst.sim.contracts.termination import TerminateContract
from tst.sim.data_models import Balance
from tst.sim.geopolitics.actions import SetGreyRoute
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerBalances, LedgerEntry, LedgerLine
from tst.sim.mining.actions import FoundSubsidiary
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_commodity_deal, with_company, with_person_state

SUB_CENTS = 50_000_000_000  # $500M: the subsidiary's capital
LIMIT = 100_000_000  # $1M


def _energy(game: Game) -> None:
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))


# --- Finding 1: never-actions stay the founder's ----------------------------------------------


def _subsidiary_group(seed: int = 1) -> tuple[Game, int, int, int, int]:
    """A stage-3 accelerator seller in October 2022 with a North American subsidiary, Minerals
    (inside the US rule's jurisdiction), that owns the accelerator (restricted in China) and a
    copper contract, under its own CEO:
    (game, subsidiary, CEO, product, deal)."""
    data = m22.loaded()
    game, pid = m22.accelerator_company(seed, data, ym_to_turn(2022, 10))
    game.state = with_company(game.state, replace(game.state.player, stage=3))
    game.balances[(PLAYER, CASH)] = game.balances.get((PLAYER, CASH), 0) + 2 * SUB_CENTS
    _energy(game)
    before = {c.id for c in game.state.companies}
    assert game.act(FoundSubsidiary(game.founder_id, "Minerals", "north_america", SUB_CENTS)), dict(
        game.refused
    )
    (sub,) = {c.id for c in game.state.companies} - before
    (ceo,) = add_staff_at(game, sub, "operations_manager", "exec", 1, skill=16.0)
    product = game.state.product(pid)
    assert product is not None
    game.state = replace(
        game.state,
        products=tuple(
            replace(p, company_id=sub) if p.id == pid else p for p in game.state.products
        ),
    )
    turn = game.state.turn
    price = spot_price(game.state, "copper", data.game_data, data.balance)
    deal_id = max((d.id for d in game.state.commodity_deals), default=0) + 1
    deal = CommodityDeal(
        deal_id, sub, "contract", "copper", turn - 2, turn + 21, 1_200.0, price, price, price
    )
    game.state = with_commodity_deal(game.state, deal)
    _energy(game)
    return game, sub, ceo, pid, deal_id


def _propose(game: Game, sub: int, ceo: int, action: TerminateContract | SetGreyRoute) -> int:
    """The subsidiary CEO's supply area meets a never-action: it becomes the player's proposal."""
    data = m22.loaded()
    owner = AreaOwner(sub, "supply", ceo, LIMIT, 0, game.state.turn)
    run = AutoRun(
        state=game.state,
        balances=dict(game.balances),
        rng=RngFactory(game.state.save_meta.master_seed),
        balance=data.balance,
        data=data.game_data,
        owner=owner,
        area_index=owners.area_index(data.balance, "supply"),
    )
    assert not run.attempt(sub, action)
    assert run.taken == []
    (proposal,) = [p for p in run.state.pending_proposals(PLAYER) if p.kind == "auto"]
    assert scope.acting_for(proposal) == sub
    game.state = run.state
    return proposal.id


def _never_action(kind: str, ceo: int, pid: int, deal_id: int) -> TerminateContract | SetGreyRoute:
    if kind == "terminate_contract":
        return TerminateContract(ceo, "commodity", deal_id)
    return SetGreyRoute(ceo, pid, "china")


def _write(path: Path, game: Game, start: dict[tuple[int, str], int]) -> None:
    """The game's state into a save, and its ledger as one netting entry per company."""
    from tst.db.mappers import entry_to_row
    from tst.db.repository import load_state, open_session
    from tst.db.state_io import read_meta, sync_state

    with open_session(path) as session, session.begin():
        sync_state(session, load_state(session), game.state)
        read_meta(session).current_turn = game.state.turn
        by_company: dict[int, list[LedgerLine]] = {}
        for key in sorted(set(game.balances) | set(start)):
            diff = game.balances.get(key, 0) - start.get(key, 0)
            if diff:
                by_company.setdefault(key[0], []).append(LedgerLine(key[1], diff))
        for cid, lines in sorted(by_company.items()):
            gap = sum(x.amount for x in lines)
            if gap:
                lines.append(LedgerLine(COMMON_EQUITY, -gap))
            if len(lines) >= 2:
                entry = LedgerEntry(game.state.turn - 1, cid, "M36r fixture", tuple(lines))
                session.add(entry_to_row(entry))


def _save(game: Game, data: LoadedData, tmp_path: Path, name: str) -> Path:
    from tst.db.repository import create_save, ledger_balances, open_session

    path = create_save(
        name, 1, "funded_spinout", company_name="Reload", data=data, save_dir=tmp_path
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    _write(path, game, start)
    return path


def _cold(path: Path) -> GameState:
    from tst.db.repository import load_state, open_session

    with open_session(path) as session:
        return load_state(session)


def _result(state: GameState, kind: str, sub: int, pid: int, deal_id: int) -> object:
    if kind == "terminate_contract":
        d = next(x for x in state.commodity_deals if x.id == deal_id)
        return (d.status, d.end_turn)
    return sorted(
        (x.company_id, x.country, x.status) for x in state.licences if x.product_id == pid
    )


@pytest.mark.parametrize("kind", sorted(NEVER_ACTIONS))
def test_an_approved_never_action_in_a_subsidiary_runs_as_the_founder(
    kind: str, tmp_path: Path
) -> None:
    from tst.db.models import DecisionLogRow
    from tst.db.repository import ledger_balances, open_session, run_action

    data = m22.loaded()
    game, sub, ceo, pid, deal_id = _subsidiary_group()
    pid_proposal = _propose(game, sub, ceo, _never_action(kind, ceo, pid, deal_id))
    proposal = next(p for p in game.state.proposals if p.id == pid_proposal)
    # the required actor is recorded on the proposal and enforced centrally
    assert scope.proposal_actor(game.state, proposal, game.founder_id) == game.founder_id
    assert dict(proposal.params).get(scope.ACTOR_PARAM) == scope.FOUNDER
    before = _result(game.state, kind, sub, pid, deal_id)

    # declining changes nothing but the proposal
    declined = apply_action(
        game.state,
        AnswerProposal(game.founder_id, pid_proposal, False),
        RngFactory(1),
        data.balance,
        data.game_data,
        game.balances,
        seq=1,
    )
    assert declined.ledger_entries == ()
    assert _result(declined.new_state, kind, sub, pid, deal_id) == before

    path = _save(game, data, tmp_path, kind)
    with open_session(path) as session:
        cash_before = dict(ledger_balances(session))
    out = run_action(path, data, AnswerProposal(game.founder_id, pid_proposal, True))
    after = _result(out.new_state, kind, sub, pid, deal_id)
    assert after != before
    if kind == "terminate_contract":
        assert after[0] == "ended"
        (entry,) = out.ledger_entries  # the subsidiary's books, once
        assert entry.company_id == sub
    else:
        assert after == [(sub, "china", "grey")]
        assert out.ledger_entries == ()
    cold = _cold(path)
    assert _result(cold, kind, sub, pid, deal_id) == after
    assert next(p for p in cold.proposals if p.id == pid_proposal).status == "approved"
    with open_session(path) as session:
        cash_after = dict(ledger_balances(session))
        rows = session.scalars(select(DecisionLogRow)).all()
    moved = {
        k[0]
        for k in set(cash_before) | set(cash_after)
        if cash_before.get(k, 0) != cash_after.get(k, 0)
    }
    assert moved <= {sub}
    for row in rows:
        if row.kind in NEVER_ACTIONS or row.kind == "answer_proposal":
            assert row.actor_id == game.founder_id, row.kind


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    kind=st.sampled_from(sorted(NEVER_ACTIONS)),
    in_sub=st.booleans(),
    proposer=st.sampled_from(["ceo", "staff", "gone", "nobody"]),
    recorded=st.booleans(),
)
def test_no_delegate_is_ever_the_actor_of_a_never_action(
    kind: str, in_sub: bool, proposer: str, recorded: bool
) -> None:
    """Acceptance: approved or not, a grey route or a termination is the founder's. Proposals
    filed before the fix (no recorded actor) are covered by their kind."""
    import json

    from tst.sim.actions import action_payload, auto_proposal_action
    from tst.sim.org.models import Proposal

    game, sub, ceo, pid, deal_id = _cached_group()
    state = game.state
    staff = next(
        e.person_id for e in state.employments if e.company_id == sub and e.status == "active"
    )
    person = {"ceo": ceo, "staff": staff, "gone": 999_999, "nobody": ceo}[proposer]
    if proposer == "nobody":
        state = replace(
            state,
            employments=tuple(
                replace(e, status="left") if e.company_id == sub else e for e in state.employments
            ),
        )
    company = sub if in_sub else PLAYER
    action = _never_action(kind, person, pid, deal_id)
    params: list[tuple[str, int | str]] = [
        ("action", json.dumps(action_payload(action), sort_keys=True, default=list))
    ]
    if in_sub:
        params.append((scope.COMPANY_PARAM, company))
    if recorded:
        params.append((scope.ACTOR_PARAM, scope.FOUNDER))
    proposal = Proposal(1, PLAYER, "lead", person, state.turn, "auto", tuple(sorted(params)), "x")
    actor = scope.proposal_actor(state, proposal, game.founder_id)
    assert actor == game.founder_id
    assert auto_proposal_action(proposal, actor).actor_id == game.founder_id


_GROUP: list[tuple[Game, int, int, int, int]] = []


def _cached_group() -> tuple[Game, int, int, int, int]:
    if not _GROUP:
        _GROUP.append(_subsidiary_group())
    return _GROUP[0]


def _reload(state: GameState, tmp_path: Path, name: str = "reload") -> GameState:
    """`state` written into a fresh save and read back cold (a new session)."""
    from tst.db.repository import create_save, load_state, open_session
    from tst.db.state_io import read_meta, sync_state

    path = create_save(
        name, 1, "funded_spinout", company_name="Reload", data=m22.loaded(), save_dir=tmp_path
    )
    with open_session(path) as session, session.begin():
        sync_state(session, load_state(session), state)
        read_meta(session).current_turn = state.turn
    return _cold(path)


# --- Finding 2: commitments from the deal's own integer-cent quote ---------------------------

JAN_2026 = ym_to_turn(2026, 1)
OBLIGATION_YEAR = 1_000_000_000_015  # Codex's annual value, in cents


def _supply_game() -> tuple[Game, int]:
    """January 2026, rich, with a procurement lead: (game, lead)."""
    from tst.balance.game import start_game

    data = m22.loaded()
    game = start_game(data, 1, "funded_spinout")
    game.state = replace(game.state, turn=JAN_2026)
    game.balances[(PLAYER, CASH)] = game.balances.get((PLAYER, CASH), 0) + 10**15
    (lead,) = add_staff_at(game, PLAYER, "procurement_manager", "senior", 1, skill=14.0)
    _energy(game)
    return game, lead


def _offtake_reference(year_cents: int, years: int, prepaid: int) -> int:
    """Independent: the offtake's fixed take-or-pay over its term, x the configured share as
    the decimal written in balance.yaml, rounded half-even once; plus the prepayment."""
    share = Fraction(str(m22.loaded().balance.offtake.take_or_pay))
    return round(Fraction(year_cents * years) * share) + prepaid


def _contract_reference(year_cents: int, months: int) -> int:
    share = Fraction(str(m22.loaded().balance.commodity.contract_take_or_pay))
    return round(Fraction(year_cents * months, 12) * share)


def _year_reference(volume: float, price: float, good: str) -> int:
    """Independent: a year's volume at the price, in cents, from the decimals as written."""
    data = m22.loaded().game_data
    assert data.commodities is not None
    usd = data.commodities.good(good).usd_per_unit
    return round(Fraction(repr(volume)) * Fraction(repr(price)) * Fraction(repr(usd)) * 100)


def _run_for(game: Game, lead: int, limit: int) -> AutoRun:
    data = m22.loaded()
    return AutoRun(
        state=game.state,
        balances=dict(game.balances),
        rng=RngFactory(game.state.save_meta.master_seed),
        balance=data.balance,
        data=data.game_data,
        owner=AreaOwner(PLAYER, "supply", lead, limit, 0, game.state.turn),
        area_index=owners.area_index(data.balance, "supply"),
    )


def test_an_offtake_commitment_is_its_quote_s_obligation_at_the_exact_limit() -> None:
    """Codex review 7 finding 2: the annual value 1,000,000,000,015 cents x 3 years x 7/10 is
    2,100,000,000,032 cents (half-even of ...031.5); the float path said ...031."""
    from tst.sim.actions.commodities import SignOfftake
    from tst.sim.automation import limits
    from tst.sim.commodities.offtake import offtake_quote, usd_per_unit
    from tst.sim.contracts import termination as ct

    data = m22.loaded()
    b, d = data.balance, data.game_data
    game, lead = _supply_game()
    price = ct.offered(game.state, "freeport", spot_price(game.state, "copper", d, b), b)
    volume = OBLIGATION_YEAR / (price * usd_per_unit("copper", d) * 100)
    q = offtake_quote(game.state, "copper", "freeport", 3, volume, 0.0, b, d)
    assert q.year_value_cents == _year_reference(volume, price, "copper")
    expected = _offtake_reference(q.year_value_cents, 3, 0)
    action = SignOfftake(lead, "copper", "freeport", 3, volume, 0.0)
    assert limits.commitment(game.state, action, b, d, game.balances) == expected
    if q.year_value_cents == OBLIGATION_YEAR:
        assert expected == 2_100_000_000_032
    run = _run_for(game, lead, expected)  # cost == limit: always a proposal
    assert not run.attempt(PLAYER, action)
    assert run.taken == []
    (proposal,) = [p for p in run.state.pending_proposals(PLAYER) if p.kind == "auto"]
    assert proposal.param("commitment_cents") == expected


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    offtake=st.booleans(),
    volume=st.floats(min_value=0.5, max_value=5e6, allow_nan=False),
    term=st.integers(min_value=0, max_value=30),
    prepay=st.sampled_from([0.0, 0.05, 0.1, 0.15, 0.2]),
    good=st.sampled_from(["copper", "lithium_carbonate", "nickel"]),
)
def test_commodity_commitments_match_a_rational_reference(
    offtake: bool, volume: float, term: int, prepay: float, good: str
) -> None:
    """Rational reference for contracts and offtakes, and cost == limit always proposes."""
    from tst.sim.actions.commodities import SignCommodityContract, SignOfftake
    from tst.sim.automation import limits
    from tst.sim.commodities.offtake import contract_quote, offtake_quote
    from tst.sim.errors import SimError

    data = m22.loaded()
    b, d = data.balance, data.game_data
    game, lead = _cached_supply()
    state = game.state
    action: SignOfftake | SignCommodityContract
    try:
        if offtake:
            years = 3 + term % 8
            q = offtake_quote(state, good, "freeport", years, volume, prepay, b, d)
            year = _year_reference(volume, q.price, good)
            expected = _offtake_reference(year, years, q.prepaid_cents)
            action = SignOfftake(lead, good, "freeport", years, volume, prepay)
        else:
            months = 6 + term
            q = contract_quote(state, good, months, volume, b, d)
            expected = _contract_reference(_year_reference(volume, q.price, good), months)
            action = SignCommodityContract(lead, good, months, volume)
    except SimError:
        return  # a supplier that does not sell this good, or a term out of range
    assert q.year_value_cents == _year_reference(volume, q.price, good)
    cost = limits.commitment(state, action, b, d, game.balances)
    assert cost == expected
    if cost > 0:
        run = _run_for(game, lead, cost)
        assert not run.attempt(PLAYER, action)
        assert run.taken == []


_SUPPLY: list[tuple[Game, int]] = []


def _cached_supply() -> tuple[Game, int]:
    if not _SUPPLY:
        _SUPPLY.append(_supply_game())
    return _SUPPLY[0]


# --- Finding 3: exact platform fees ------------------------------------------------------------

_PLATFORM: list[GameState] = []


def _platform_start() -> GameState:
    from tests.platform_helpers import START, platform_state
    from tst.sim.platforms.phase import platforms_month

    if not _PLATFORM:
        data = m22.loaded()
        state, _ = platform_state(data, turn=START)
        _PLATFORM.append(platforms_month(state, RngFactory(3), data.balance, data.game_data))
    return _PLATFORM[0]


def _one_app_market(
    customers: float, price: int, users: tuple[float, ...], paid_share: float
) -> tuple[GameState, Balance, int, list[int]]:
    """The platform state with every app market emptied but one product's home app segment
    (customers at price), and device platforms in the home region with the given users (the
    rest at zero): (state, balance with that paid_share, product id, platform ids)."""
    from tst.sim.platforms import fees
    from tst.sim.platforms.phase import home_of, live_in
    from tst.sim.products.models import SELLING

    data = m22.loaded()
    b, d = data.balance, data.game_data
    state = _platform_start()
    home = home_of(state, b, d)
    assert home is not None
    books = {c.id for c in state.ledger_companies()}
    apps = b.platforms.app_categories
    product, seg = next(
        (p, s)
        for p in state.products
        if p.status in SELLING and p.company_id in books and fees.app_category(p.category, b)
        for s in state.segments_of(p.id)
        if s.segment in apps[p.category].segments
    )
    platforms = [
        p.id
        for p in state.platforms
        if p.kind == "device"
        and p.owner_id != product.company_id
        and live_in(p, home, state.turn)
        and any(r.platform_id == p.id and r.region == home for r in state.platform_regions)
    ][: len(users)]
    assert len(platforms) == len(users)
    share = dict(zip(platforms, users, strict=True))
    state = replace(
        state,
        product_segments=tuple(
            replace(s, customers=customers, price_cents=price)
            if (s.product_id, s.segment) == (product.id, seg.segment)
            else replace(s, customers=0.0)
            for s in state.product_segments
        ),
        regional_segments=tuple(replace(r, customers=0.0) for r in state.regional_segments),
        platform_regions=tuple(
            replace(r, users=share.get(r.platform_id, 0.0) if r.region == home else 0.0)
            for r in state.platform_regions
        ),
    )
    cat = product.category
    new_apps = {**apps, cat: apps[cat].model_copy(update={"paid_share": paid_share})}
    platforms_b = b.platforms.model_copy(update={"app_categories": new_apps})
    return state, b.model_copy(update={"platforms": platforms_b}), product.id, platforms


def _seller_fees(entries: list[LedgerEntry], company: int) -> int:
    from tst.sim.ledger import INTERCOMPANY_PURCHASES, PLATFORM_FEES

    return sum(
        line.amount
        for e in entries
        if e.company_id == company
        for line in e.lines
        if line.account in (PLATFORM_FEES, INTERCOMPANY_PURCHASES)
    )


def _owner_fees(entries: list[LedgerEntry], company: int) -> int:
    from tst.sim.ledger import INTERCOMPANY_SALES, PLATFORM_FEE_REVENUE

    return -sum(
        line.amount
        for e in entries
        if e.company_id == company
        for line in e.lines
        if line.account in (PLATFORM_FEE_REVENUE, INTERCOMPANY_SALES)
    )


def test_a_half_cent_platform_fee_rounds_half_even_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Codex review 7 finding 3: 1,750 x 0.4 x 0.7 x 0.15 is 73.5 cents exactly: 74, not 73."""
    from tst.sim.platforms import fees

    d = m22.loaded().game_data
    monkeypatch.setattr(fees.pdata, "fee_for", lambda *a, **k: 0.15)
    state, balance, pid, (plat,) = _one_app_market(1.0, 1_750, (0.7,), 0.4)
    due = fees.fees_due(state, balance, d)
    assert list(due.values()) == [74]
    (key,) = due
    assert key[:2] == (pid, plat)
    entries = fees.fee_entries(state, balance, d)
    for e in entries:
        assert sum(line.amount for line in e.lines) == 0
    product = state.product(pid)
    assert product is not None
    assert _seller_fees(entries, product.company_id) == 74
    owner = key[2]
    if owner in {c.id for c in state.ledger_companies()}:
        assert _owner_fees(entries, owner) == 74
    cold = _reload(state, tmp_path)
    assert fees.fees_due(cold, balance, d) == {key: 74}


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    customers=st.floats(min_value=0.0, max_value=1e6, allow_nan=False),
    price=st.integers(min_value=1, max_value=100_000),
    users=st.tuples(st.floats(0.0, 1.0), st.floats(0.0, 1.0)),
    fee=st.sampled_from([0.0, 0.1, 0.15, 0.3, 0.27, 0.125]),
    paid_share=st.sampled_from([0.1, 0.4, 0.35, 1.0, 0.7]),
)
def test_platform_fees_match_a_rational_reference(
    customers: float, price: int, users: tuple[float, float], fee: float, paid_share: float
) -> None:
    """An independent rational reference: revenue = customers x price rounded once; each
    (seller, owner) pair pays the exact sum over platforms of revenue x paid_share x users x
    fee, rounded half-even once; the owner earns exactly what its sellers pay."""
    from collections import defaultdict

    from tst.sim.platforms import fees

    d = m22.loaded().game_data
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(fees.pdata, "fee_for", lambda *a, **k: fee)
        state, balance, pid, plats = _one_app_market(customers, price, users, paid_share)
        revenue = round(Fraction(repr(customers)) * price)
        exact_due: dict[int, Fraction] = defaultdict(Fraction)
        for plat, u in zip(plats, users, strict=True):
            p = state.platform(plat)
            assert p is not None
            owner = p.owner_id if p.owner_id is not None else -1
            if u > 0:
                exact_due[owner] += (
                    revenue * Fraction(str(paid_share)) * Fraction(repr(u)) * Fraction(str(fee))
                )
        expected = {o: round(v) for o, v in exact_due.items() if round(v) > 0}
        entries = fees.fee_entries(state, balance, d)
    for e in entries:
        assert sum(line.amount for line in e.lines) == 0
    product = state.product(pid)
    assert product is not None
    assert _seller_fees(entries, product.company_id) == sum(expected.values())
    books = {c.id for c in state.ledger_companies()}
    for owner, cents in expected.items():
        if owner in books:
            assert _owner_fees(entries, owner) == cents


# --- Finding 4: group OS licences eliminate ----------------------------------------------------


def _licence_case(case: str) -> tuple[GameState, int, int, int]:
    """A licensed own OS (100 cents a unit) and a device line on it: `subsidiary` (the player
    owns the OS, its subsidiary makes the device), `parent` (the subsidiary owns the OS, the
    player makes the device), `sister` (one subsidiary each), or `outside` (a rival OEM outside
    the group): (state, product id, licensee, OS owner)."""
    from tst.sim.group.models import Ownership
    from tst.sim.platforms.models import DeviceRun
    from tst.sim.state import with_ownership

    state = _platform_start()
    others = sorted(c.id for c in state.ledger_companies() if c.id != PLAYER)
    a, b_, rival = others[0], others[1], others[2]
    os_platform = next(p for p in state.platforms if p.kind == "device")
    subs: tuple[int, ...]
    if case == "subsidiary":
        licensee, owner, subs = a, PLAYER, (a,)
    elif case == "parent":
        licensee, owner, subs = PLAYER, a, (a,)
    elif case == "sister":
        licensee, owner, subs = a, b_, (a, b_)
    else:
        licensee, owner, subs = rival, PLAYER, ()
    for i, sub in enumerate(subs):
        state = with_ownership(state, Ownership(9_000 + i, sub, PLAYER, state.turn - 1))
    product = state.products[0]
    state = replace(
        state,
        products=tuple(
            replace(p, company_id=licensee) if p.id == product.id else p for p in state.products
        ),
        platforms=tuple(
            replace(p, historical=False, licence_cents=100, owner_id=owner)
            if p.id == os_platform.id
            else p
            for p in state.platforms
        ),
        device_runs=(DeviceRun(product.id, os_platform.id, state.turn),),
    )
    return state, product.id, licensee, owner


@pytest.mark.parametrize("case", ["subsidiary", "parent", "sister", "outside"])
def test_group_os_licences_are_intercompany_and_eliminate(case: str, tmp_path: Path) -> None:
    """Codex review 7 finding 4: inside the group an OS licence is 5900 / 4300, which
    consolidation removes; outside it, 5150 / 4150."""
    from tst.sim.finance.consolidation import consolidated_lines
    from tst.sim.geopolitics import world
    from tst.sim.ledger import (
        INTERCOMPANY_PURCHASES,
        INTERCOMPANY_SALES,
        PLATFORM_FEE_REVENUE,
        PLATFORM_FEES,
    )
    from tst.sim.platforms import fees

    data = m22.loaded()
    state, pid, licensee, owner = _licence_case(case)
    group = {c.id for c in world.group(state)}
    inside = case != "outside"
    assert (licensee in group and owner in group) == inside
    entries = fees.own_licence_entries(state, {pid: 1.0}, data.balance, data.game_data)
    for e in entries:
        assert sum(line.amount for line in e.lines) == 0

    def amount(company: int, account: str) -> int:
        return sum(
            line.amount
            for e in entries
            if e.company_id == company
            for line in e.lines
            if line.account == account
        )

    assert amount(licensee, CASH) == -100 and amount(owner, CASH) == 100
    if inside:
        assert amount(licensee, INTERCOMPANY_PURCHASES) == 100
        assert amount(owner, INTERCOMPANY_SALES) == -100
        assert amount(licensee, PLATFORM_FEES) == 0 and amount(owner, PLATFORM_FEE_REVENUE) == 0
        types = {a.code: a.type for a in data.game_data.accounts}
        by: dict[int, list[tuple[int, str, int]]] = {}
        for e in entries:
            by.setdefault(e.company_id, []).extend((e.turn, x.account, x.amount) for x in e.lines)
        members = [(by.get(c, []), state.turn - 1) for c in sorted(group - {PLAYER})]
        lines = consolidated_lines(by.get(PLAYER, []), members, types)
        for account in (
            PLATFORM_FEES,
            PLATFORM_FEE_REVENUE,
            INTERCOMPANY_PURCHASES,
            INTERCOMPANY_SALES,
            CASH,  # cash only moved inside the group
        ):
            assert sum(x[2] for x in lines if x[1] == account) == 0, account
    else:
        assert amount(licensee, PLATFORM_FEES) == 100
        assert amount(owner, PLATFORM_FEE_REVENUE) == -100
    cold = _reload(state, tmp_path)
    assert fees.own_licence_entries(cold, {pid: 1.0}, data.balance, data.game_data) == entries


# --- Finding 5: the estate pays what it owes ----------------------------------------------------

_ESTATE: list[Game] = []


def _estate_game() -> Game:
    from tests.m36_helpers import family_game, hire_child
    from tst.sim.family import rules

    if not _ESTATE:
        game = family_game(m22.loaded(), 3, age=60, child_ages=(30, 27))
        for k in rules.children(game.state):
            hire_child(game, k.person_id)
        _ESTATE.append(game)
    return _ESTATE[0]


def _estate_value(state: GameState, person: int, balances: LedgerBalances) -> int:
    """Independent: everything a person holds, at the estate's own valuations."""
    from tst.sim.family import estate
    from tst.sim.finance.captable import person_shares
    from tst.sim.founder.models import FAMILY_OFFICE, PERSONAL_CASH
    from tst.sim.founder.personal import book_balances
    from tst.sim.founder.wealth import stake_value_cents
    from tst.sim.state import listed_id

    data = m22.loaded()
    b, d = data.balance, data.game_data
    cid = listed_id(state)
    books = book_balances(state.personal_book, person)
    value = books.get(PERSONAL_CASH, 0) + books.get(FAMILY_OFFICE, 0)
    value += person_shares(state, cid, person) * estate.share_price(state, cid, balances, b, d)
    value += sum(
        h.shares * estate.share_price(state, h.company_id, balances, b, d)
        for h in state.public_holdings
        if h.person_id == person and h.shares > 0 and h.company_id != cid
    )
    value += sum(
        stake_value_cents(s)
        for s in state.angel_stakes
        if s.person_id == person and s.status == "open"
    )
    return value


def _estate_case(game: Game, case: str) -> GameState:
    """The head's estate, mostly in one kind of taxable asset ($10B)."""
    from tests.m36_helpers import with_cash
    from tst.sim.founder.investing_models import AngelStake, PublicHolding
    from tst.sim.founder.models import ANGEL, FAMILY_OFFICE, PERSONAL_CASH, PUBLIC_SHARES
    from tst.sim.founder.wealth import post
    from tst.sim.state import public_of, with_angel_stake, with_public_holding

    head = game.founder_id
    big = 1_000_000_000_000  # $10B
    state = with_cash(game.state, head, big)
    if case == "family_office":
        state = post(state, head, "Test", "fo", FAMILY_OFFICE, PERSONAL_CASH, big)
    elif case == "public":
        from tst.sim.markets_public.models import PublicCompany

        listed = next(c for c in state.companies if c.is_rival and c.alive)
        if public_of(state, listed.id) is None:  # a listed rival at $123.45 a share
            row = PublicCompany(listed.id, 0, "RVL", False, 12_345, 12_345, 0.0, 10**12)
            state = replace(state, public_companies=(*state.public_companies, row))
        public = public_of(state, listed.id)
        assert public is not None
        shares = big // max(1, public.price_cents)
        cost = shares * public.price_cents
        state = with_public_holding(state, PublicHolding(head, listed.id, shares, cost))
        state = post(state, head, "Test", "shares", PUBLIC_SHARES, PERSONAL_CASH, cost)
    elif case == "angel":
        startups = [c for c in state.companies if c.is_rival and c.alive][:4]
        for i, startup in enumerate(startups):
            cost = big // len(startups)
            stake = AngelStake(800 + i, head, startup.id, 100_000, cost, state.turn, cost * 10 + i)
            state = with_angel_stake(state, stake)
            state = post(state, head, "Test", "angel", ANGEL, PERSONAL_CASH, cost)
    return state


def _spent(state: GameState, person: int) -> int:
    """The estate tax actually posted (Dr 9300 "Estate tax") in the person's book."""
    from tst.sim.founder.models import PERSONAL_SPENDING

    return sum(
        line.amount
        for e in state.personal_book
        if e.person_id == person and e.memo == "Estate tax"
        for line in e.lines
        if line.account == PERSONAL_SPENDING
    )


@pytest.mark.parametrize("case", ["family_office", "public", "angel", "cash"])
def test_the_estate_pays_its_whole_tax_and_passes_the_rest(case: str, tmp_path: Path) -> None:
    """Codex review 7 finding 5: the tax paid equals the quote; the gross estate equals the tax
    plus the heir's inheritance; nothing disappears; the displayed tax equals the postings."""
    from tst.sim.family import estate, rules

    data = m22.loaded()
    b, d = data.balance, data.game_data
    game = _estate_game()
    head = game.founder_id
    heir = rules.children(game.state)[0].person_id
    state = _estate_case(game, case)
    q = estate.quote(state, head, game.balances, b, d)
    assert q.tax_cents > 0
    assert q.estate_cents == _estate_value(state, head, game.balances)
    heir_before = _estate_value(state, heir, game.balances)
    after, _ = estate.settle(state, head, heir, game.balances, b, d)
    for e in after.personal_book:
        assert sum(line.amount for line in e.lines) == 0
    paid = _spent(after, head) - _spent(state, head)
    assert paid == q.tax_cents
    inherited = _estate_value(after, heir, game.balances) - heir_before
    assert _estate_value(after, head, game.balances) == 0
    assert q.estate_cents == q.tax_cents + inherited  # no value disappears
    assert after.family is not None and state.family is not None
    assert after.family.estate_tax_cents - state.family.estate_tax_cents == paid
    cold = _reload(after, tmp_path)
    assert cold.family is not None
    assert cold.family.estate_tax_cents == after.family.estate_tax_cents
    assert _estate_value(cold, heir, game.balances) == _estate_value(after, heir, game.balances)
