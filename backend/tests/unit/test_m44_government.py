"""M44 (formulas.md 57): data that cites every value, named tenders as history, seeded tenders,
bidding and awards with score bands, protests, contracts' books, clearances, sourcing rules,
controlled items, reputation, the open letter, and a company that never bids playing exactly as
before."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

import tst.sim.actions  # noqa: F401  (government.actions is imported through the actions package)
from tests.helpers import fresh_game, make_person, with_employee, with_product
from tst.balance.game import Game, start_game
from tst.loader import LoadedData
from tst.sim.actions import apply_action
from tst.sim.calendar import ym_to_turn
from tst.sim.errors import GovernmentRuleError
from tst.sim.events.models import GameEvent
from tst.sim.facilities.config import month_to_turn
from tst.sim.government import awards, clearances, delivery, phase, reputation, sourcing, tenders
from tst.sim.government.actions import PlaceBid, ProtestAward, RequestClearance, WithdrawBid
from tst.sim.government.config import GovernmentFile, tag_problems
from tst.sim.government.events import government_step
from tst.sim.government.models import (
    Bid,
    Clearance,
    Contract,
    ControlledProduct,
    FacilityClearance,
    Tender,
)
from tst.sim.ledger import (
    BIDS_CLEARANCES,
    CASH,
    CONTRACT_COSTS,
    GOVERNMENT_REVENUE,
    LedgerBalances,
)
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_facility

PLAYER = 1
RICH: LedgerBalances = {(PLAYER, CASH): 10**14}
DATA = Path(__file__).resolve().parents[2] / "data" / "government.yaml"


def _tender(state: GameState, **kw: object) -> Tender:
    base = {
        "id": 900,
        "government": "us",
        "area": "cloud",
        "buyer": "civil",
        "title": "Test cloud",
        "announce_turn": state.turn,
        "close_turn": state.turn + 3,
        "award_turn": state.turn + 5,
        "value_cents": 2_000_000_000,
        "term_months": 36,
        "base_months": 24,
        "contract": "fixed_price",
        "clearance": "none",
    }
    base.update(kw)
    return Tender(**base)  # type: ignore[arg-type]


def _setup(
    loaded: LoadedData, year: int = 2016, quality: float = 95.0
) -> tuple[GameState, int, int]:
    """A player at stage 4 with a live cloud product and a seller, in January `year`."""
    state = replace(fresh_game(loaded), turn=ym_to_turn(year, 1))
    state = with_product(state, category="cloud_hosting", quality=quality, name="GovCloud")
    pid = _last(state)
    seller = make_person(loaded, 7001, "account_executive", "senior")
    state = with_employee(loaded, state, seller, 15_000_000)
    return state, pid, seller.id


def _last(state: GameState) -> int:
    """The player's newest product."""
    return max(p.id for p in state.products if p.company_id == PLAYER)


def _founder(state: GameState) -> int:
    f = state.founder_of(PLAYER)
    assert f is not None
    return f.id


def _act(state: GameState, action: object, loaded: LoadedData) -> tuple[GameState, list]:
    out = apply_action(
        state,
        action,  # type: ignore[arg-type]
        RngFactory(state.save_meta.master_seed),
        loaded.balance,
        loaded.game_data,
        RICH,
        seq=1,
    )
    return out.new_state, list(out.ledger_entries)


# --- data (57; sub-task 1) -------------------------------------------------------------------


def test_every_value_is_cited() -> None:
    raw = yaml.load(DATA.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
    assert tag_problems(raw, set(raw["sources"])) == []
    raw["governments"][0]["defence_usd_bn"][2010] = 738.0  # an uncited value
    with pytest.raises(ValueError, match="uncited"):
        GovernmentFile.model_validate(raw)
    raw["governments"][0]["defence_usd_bn"][2010] = [738.0, "S:nowhere"]  # an unknown source
    with pytest.raises(ValueError, match="nowhere"):
        GovernmentFile.model_validate(raw)


def test_history_figures(loaded: LoadedData) -> None:
    g = loaded.game_data.government
    assert g is not None
    us = g.government("us")
    cpi = g.cpi
    # SIPRI: US $997.3B in 2024 (current dollars), in 2010 dollars at load
    assert us.defence_at(2024) == pytest.approx(997.3e11 * cpi[2010] / cpi[2024])
    jedi = next(t for t in g.tenders if t.key == "jedi")
    assert (jedi.awarded, jedi.cancelled, jedi.winners) == (
        "2019-10",
        "2021-07",
        ("Microsoft Azure",),
    )
    jwcc = next(t for t in g.tenders if t.key == "jwcc")
    assert jwcc.awards == 4 and set(jwcc.winners) == {
        "Amazon Web Services",
        "Google Cloud",
        "Microsoft Azure",
        "Oracle",
    }
    assert g.bans[0].start == "2019-08" and "china" in g.bans[0].countries
    steps = g.domestic_content[0]
    assert steps.share_at(ym_to_turn(2023, 1)) == pytest.approx(0.60)
    assert steps.share_at(ym_to_turn(2024, 6)) == pytest.approx(0.65)


# --- tenders (57.1) ---------------------------------------------------------------------------


def test_seeded_tenders_are_deterministic_and_hidden_until_announced(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2027, 1))
    rng = RngFactory(state.save_meta.master_seed)
    a = tenders.draw_year(state, rng, b, d)
    again = tenders.draw_year(state, rng, b, d)
    assert a.tenders == again.tenders
    assert len(a.tenders) == sum(b.government.tenders.per_year.values())
    assert any(t.announce_turn > state.turn for t in a.tenders)  # some not yet announced
    assert {g for g, y, _ in a.government_world.growth if y == 2027} == set(
        b.government.tenders.per_year
    )
    assert tenders.draw_year(a, rng, b, d) == a  # once a year


def test_named_tenders_follow_history(loaded: LoadedData) -> None:
    """Without a player bid JEDI is awarded to Microsoft in October 2019, held by AWS's protest
    and cancelled in July 2021; JWCC goes to the four in December 2022."""
    b, d = loaded.balance, loaded.game_data
    rng = RngFactory(3)
    state = replace(fresh_game(loaded), turn=ym_to_turn(2019, 10))
    state = tenders.add_history(state, b, d)
    jedi = next(t for t in state.tenders if t.key == "jedi")
    state = replace(
        state,
        tenders=tuple(
            replace(t, status="evaluating") if t.id == jedi.id else t for t in state.tenders
        ),
    )
    state, _, _ = phase.month(state, rng, b, d)
    now = state.tender(jedi.id)
    assert now is not None and now.status == "protested" and now.winners == ("Microsoft Azure",)
    state = replace(state, turn=month_to_turn("2021-07"))
    state, _, _ = phase.month(state, rng, b, d)
    assert state.tender(jedi.id).status == "cancelled"  # type: ignore[union-attr]
    jwcc = next(t for t in state.tenders if t.key == "jwcc")
    state = replace(state, turn=jwcc.award_turn)
    state = replace(
        state,
        tenders=tuple(
            replace(t, status="evaluating") if t.id == jwcc.id else t for t in state.tenders
        ),
    )
    state, _, _ = phase.month(state, rng, b, d)
    assert set(state.tender(jwcc.id).winners) == {  # type: ignore[union-attr]
        "Amazon Web Services",
        "Google Cloud",
        "Microsoft Azure",
        "Oracle",
    }


# --- bidding, awards, delivery (57.2) ---------------------------------------------------------


def test_bid_award_contract_and_books(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, pid, seller = _setup(loaded)
    t = _tender(state)
    state = replace(state, tenders=(t,))
    with pytest.raises(GovernmentRuleError, match="price"):
        _act(state, PlaceBid(_founder(state), t.id, pid, t.value_cents * 3, (seller,)), loaded)
    state, entries = _act(
        state, PlaceBid(_founder(state), t.id, pid, t.value_cents // 2, (seller,)), loaded
    )
    assert entries[0].lines[0].account == BIDS_CLEARANCES
    with pytest.raises(GovernmentRuleError, match="already"):
        _act(state, PlaceBid(_founder(state), t.id, pid, t.value_cents // 2, (seller,)), loaded)
    rng = RngFactory(state.save_meta.master_seed)
    state = replace(state, turn=t.close_turn)
    state, _, _ = phase.month(state, rng, b, d)
    assert state.tender(t.id).status == "evaluating"  # type: ignore[union-attr]
    state = replace(state, turn=t.award_turn)
    state, _, _ = phase.month(state, rng, b, d)
    bid = state.gov_bids[0]
    assert bid.status in ("won", "lost") and bid.terms is not None
    assert state.tender(t.id).winning_band is not None  # type: ignore[union-attr]
    if bid.status == "won" and state.tender(t.id).status == "awarded":  # type: ignore[union-attr]
        contract = state.gov_contracts[0]
        assert contract.value_cents == bid.price_cents and contract.start_turn == t.award_turn + 1
        state = replace(state, turn=contract.start_turn)
        state, entries, _ = delivery.month(state, rng, b)
        accounts = {line.account for e in entries for line in e.lines}
        assert {GOVERNMENT_REVENUE, CONTRACT_COSTS, CASH} <= accounts
        assert all(sum(x.amount for x in e.lines) == 0 for e in entries)


def test_award_is_seeded_and_never_stores_rival_bids(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, pid, seller = _setup(loaded)
    t = _tender(state, award_turn=state.turn)
    bid = Bid(1, t.id, PLAYER, pid, t.value_cents // 2, (seller,), state.turn - 1)
    state = replace(state, tenders=(t,), gov_bids=(bid,))
    rng = RngFactory(state.save_meta.master_seed)
    one = awards.award(state, t, rng, b, d)
    two = awards.award(state, t, rng, b, d)
    assert one.state == two.state
    # the state holds the published award and the player's own bid, nothing of rivals' bids
    assert len(one.state.gov_bids) == 1 and one.state.protests == ()
    assert one.state.tender(t.id).winners  # type: ignore[union-attr]


def test_withdraw_before_close(loaded: LoadedData) -> None:
    state, pid, _seller = _setup(loaded)
    t = _tender(state)
    state = replace(state, tenders=(t,))
    state, _ = _act(state, PlaceBid(_founder(state), t.id, pid, t.value_cents // 2, ()), loaded)
    state, _ = _act(state, WithdrawBid(_founder(state), t.id), loaded)
    assert state.gov_bids[0].status == "withdrawn"


def test_player_protest_holds_the_award(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, pid, seller = _setup(loaded, quality=5.0)
    t = _tender(state, award_turn=state.turn, status="awarded", winners=("Oracle",))
    bid = Bid(1, t.id, PLAYER, pid, t.value_cents, (seller,), state.turn - 2, status="lost")
    state = replace(state, tenders=(t,), gov_bids=(bid,))
    state, entries = _act(state, ProtestAward(_founder(state), t.id), loaded)
    assert state.tender(t.id).status == "protested"  # type: ignore[union-attr]
    assert entries[0].lines[0].amount == b.government.protests.cost_cents
    with pytest.raises(GovernmentRuleError):
        _act(state, ProtestAward(_founder(state), t.id), loaded)
    protest = state.protests[-1]
    lo, hi = b.government.protests.delay_months.lo, b.government.protests.delay_months.hi
    assert lo <= protest.until - state.turn <= hi
    state = replace(state, turn=protest.until)
    state, _, _ = phase.month(state, RngFactory(state.save_meta.master_seed), b, d)
    assert state.protests[-1].outcome in ("sustained", "denied")
    assert state.tender(t.id).status == "awarded"  # type: ignore[union-attr]


@pytest.mark.parametrize("kind", ["fixed_price", "cost_plus", "idiq"])
def test_delivery_books_and_performance(loaded: LoadedData, kind: str) -> None:
    b = loaded.balance
    state, pid, _ = _setup(loaded)
    c = Contract(
        id=1,
        tender_id=900,
        clearance="none",
        company_id=PLAYER,
        product_id=pid,
        government="us",
        area="cloud",
        buyer="civil",
        contract=kind,
        value_cents=360_000_000,
        start_turn=state.turn,  # type: ignore[arg-type]
        base_end_turn=state.turn + 24,
        end_turn=state.turn + 36,
    )
    state = replace(state, gov_contracts=(c,))
    rng = RngFactory(9)
    state, entries, _ = delivery.month(state, rng, b)
    rev = -sum(
        line.amount for e in entries for line in e.lines if line.account == GOVERNMENT_REVENUE
    )
    cost = sum(line.amount for e in entries for line in e.lines if line.account == CONTRACT_COSTS)
    cash = sum(line.amount for e in entries for line in e.lines if line.account == CASH)
    assert cash == rev - cost
    now = state.gov_contracts[0]
    assert now.months == 1 and 0 <= now.performance <= 100
    if kind == "cost_plus":
        assert rev == pytest.approx(cost * (1 + b.government.delivery.cost_plus_fee), abs=2)
    # the product gone: no revenue, and a default after lapse_months
    state = replace(
        state,
        products=tuple(replace(p, status="retired") if p.id == pid else p for p in state.products),
    )
    for _ in range(b.government.delivery.lapse_months):
        state = replace(state, turn=state.turn + 1)
        state, entries, _ = delivery.month(state, rng, b)
        assert entries == []
    assert state.gov_contracts[0].status == "defaulted"


def test_options_exercised_or_declined(loaded: LoadedData) -> None:
    b = loaded.balance
    state, pid, _ = _setup(loaded)
    base = Contract(
        id=1,
        tender_id=900,
        clearance="none",
        company_id=PLAYER,
        product_id=pid,
        government="us",
        area="cloud",
        buyer="civil",
        contract="fixed_price",
        value_cents=360_000_000,
        start_turn=state.turn - 24,
        base_end_turn=state.turn,
        end_turn=state.turn + 12,
        months=24,
    )
    for perf, status in ((90.0, "active"), (40.0, "completed")):
        s = replace(state, gov_contracts=(replace(base, performance=perf),))
        s, _, _ = delivery.month(s, RngFactory(1), b)
        assert s.gov_contracts[0].status == status


# --- clearances and sourcing (57.3) -----------------------------------------------------------


def test_clearances_seeded_hidden_and_decided(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _, seller = _setup(loaded, year=2027)
    state, _entries = _act(
        state, RequestClearance(_founder(state), (seller,), "top_secret"), loaded
    )
    c = state.clearances[0]
    assert c.status == "pending" and c.due_turn > state.turn
    again = clearances.draw_clearance(
        replace(state, clearances=()),
        seller,
        PLAYER,
        "top_secret",
        RngFactory(state.save_meta.master_seed),
        b,
        d,
    )
    assert (again.due_turn, again.outcome) == (c.due_turn, c.outcome)
    with pytest.raises(GovernmentRuleError, match="pending"):
        _act(state, RequestClearance(_founder(state), (seller,), "secret"), loaded)
    state = replace(state, turn=c.due_turn)
    state, logs = clearances.month(state)
    assert (
        state.clearances[0].status == c.outcome and state.clearances[0].decided_turn == c.due_turn
    )
    assert logs


def test_clearance_times_in_band(loaded: LoadedData) -> None:
    """57.6 target 3's shape on many draws: median 6-15 months, at least 5% never clear."""
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2027, 1))
    rng = RngFactory(state.save_meta.master_seed)
    months, never = [], 0
    people = state.people[:600]
    for p in people:
        c = clearances.draw_clearance(state, p.id, PLAYER, "top_secret", rng, b, d)
        if c.outcome == "denied":
            never += 1
        else:
            months.append(c.due_turn - c.requested_turn)
    months.sort()
    assert 6 <= months[len(months) // 2] <= 15
    assert never / len(people) >= 0.05


def test_requirements_name_what_is_missing(
    loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    b, d = loaded.balance, loaded.game_data
    state, pid, _seller = _setup(loaded, year=2021)
    t = _tender(state, clearance="top_secret", buyer="defence")
    reasons = sourcing.requirements(state, state.player, state.product(pid), t, b, d)
    assert any("Top Secret" in r for r in reasons) and any("cleared facility" in r for r in reasons)
    # a device made partly in China: Section 889 and domestic content refuse it
    state = with_product(state, category="devices", quality=80, name="Rugged", root=False)
    dev = _last(state)
    monkeypatch.setattr(sourcing, "_made_in", lambda *a: {"china": 0.6, "us": 0.4})
    t = _tender(state, area="devices", buyer="defence")
    reasons = sourcing.requirements(state, state.player, state.product(dev), t, b, d)
    assert any("Section 889" in r for r in reasons)
    assert any("domestic content" in r for r in reasons)
    monkeypatch.setattr(sourcing, "_made_in", lambda *a: {"us": 1.0})
    assert sourcing.requirements(state, state.player, state.product(dev), t, b, d) == ()
    # before Section 889's date the ban does not apply
    early = replace(state, turn=ym_to_turn(2018, 1))
    monkeypatch.setattr(sourcing, "_made_in", lambda *a: {"china": 0.3, "us": 0.7})
    reasons = sourcing.requirements(early, early.player, early.product(dev), t, b, d)
    assert not any("Section 889" in r for r in reasons)


def test_cleared_staff_and_facility_meet_a_classified_tender(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, pid, _ = _setup(loaded, year=2021)
    need = b.government.clearances.required["secret"]
    for i in range(need):
        p = make_person(loaded, 7100 + i)
        state = with_employee(loaded, state, p, 10_000_000)
    staff = [e.person_id for e in state.staff(PLAYER)][-need:]
    from tst.sim.facilities.models import Facility

    dc = Facility(
        id=8001,
        company_id=PLAYER,
        kind="data_centre_general",
        region="north_america",
        capacity=100,
        on_time=100,
        ordered_turn=0,
        ready_turn=0,
        late_turn=0,
        capex_cents=1,
        input_index=1.0,
        capex_paid_cents=1,
        status="live",
    )
    state = with_facility(state, dc)
    state = replace(
        state,
        clearances=tuple(
            Clearance(p, PLAYER, "secret", 0, 1, "cleared", "cleared", 1) for p in staff
        ),
        facility_clearances=(FacilityClearance(8001, PLAYER, 0, 1, "cleared"),),
    )
    t = _tender(state, clearance="secret", buyer="defence")
    assert sourcing.requirements(state, state.player, state.product(pid), t, b, d) == ()
    # a person who leaves takes the clearance with them
    assert sourcing.cleared_staff(state, PLAYER, "secret") == need
    assert sourcing.cleared_staff(state, PLAYER, "top_secret") == 0


def test_controlled_item_loses_proscribed_markets(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, pid, _ = _setup(loaded)
    p = state.product(pid)
    assert p is not None
    assert sourcing.itar_keep(state, p, "china", b, d) == 1.0  # not controlled
    state = replace(state, controlled_products=(ControlledProduct(pid, PLAYER, state.turn),))
    assert sourcing.itar_keep(state, p, "china", b, d) == 0.0
    assert sourcing.itar_keep(state, p, "us", b, d) == 1.0
    assert sourcing.itar_keep(state, p, "india", b, d) == b.government.itar_keep["non_aligned"]


# --- reputation (57.4) ------------------------------------------------------------------------


def _consumer(loaded: LoadedData) -> tuple[GameState, int, Contract]:
    state = replace(fresh_game(loaded), turn=ym_to_turn(2026, 1))
    state = with_product(state, category="consumer_apps", quality=70, brand=60, name="Snap")
    app = _last(state)
    for i in range(12):
        p = make_person(loaded, 7200 + i)
        p = replace(p, interests=("open_source", "design"))
        state = with_employee(loaded, state, p, 10_000_000)
    c = Contract(
        id=1,
        tender_id=900,
        clearance="none",
        company_id=PLAYER,
        product_id=app,
        government="us",
        area="devices",
        buyer="defence",
        contract="fixed_price",
        value_cents=10**9,
        start_turn=state.turn + 1,
        base_end_turn=state.turn + 25,
        end_turn=state.turn + 37,
    )
    return replace(state, gov_contracts=(c,)), app, c


def test_defence_award_costs_brand_moves_persona_and_influence(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, app, c = _consumer(loaded)
    out, _logs = reputation.on_defence_award(state, c, RngFactory(5), b, d)
    assert state.product(app).brand - out.product(app).brand == pytest.approx(
        b.government.reputation.brand_first
    )  # type: ignore[union-attr]
    record = out.defence_record(PLAYER)
    assert record is not None and record.awards == 1 and record.blocs == ("us_aligned",)
    from tst.sim.founder.influence import of

    assert of(out, PLAYER, "north_america") == pytest.approx(b.government.reputation.influence)
    objecting = reputation.objectors(state, PLAYER, b)
    assert len(objecting) >= 12
    assert sum(1 for m in out.modifiers if m.stat == "morale_target") >= 12
    # the same seed draws the same letter
    again, _ = reputation.on_defence_award(state, c, RngFactory(5), b, d)
    assert again.queued == out.queued
    # china now refuses the company
    t = _tender(out, government="china", buyer="defence", area="cloud")
    out = with_product(out, category="cloud_hosting", quality=90, name="C", root=False)
    cloud = _last(out)
    reasons = sourcing.requirements(out, out.player, out.product(cloud), t, b, d)
    assert any("rivals' militaries" in r or "does not take bids" in r for r in reasons)


def test_open_letter_answers(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _app, c = _consumer(loaded)
    for seed in range(1, 40):
        out, _ = reputation.on_defence_award(state, c, RngFactory(seed), b, d)
        rec = out.defence_record(PLAYER)
        if rec is not None and rec.letter_turn is not None:
            break
    else:
        pytest.fail("no seed drew an open letter")
    out = replace(out, turn=rec.letter_turn)
    ev = GameEvent(
        id=1,
        company_id=PLAYER,
        turn=out.turn,
        template_id="defence_open_letter",
        category="government",
        severity="critical",
        trigger="government",
        strength=1.0,
    )
    carried, _, _logs = government_step(out, ev, "carry_on", b, d)
    assert sum(1 for e in carried.employments if e.status == "notice") >= 1
    withdrawn, _, _ = government_step(out, ev, "withdraw", b, d)
    assert withdrawn.gov_contracts[0].status == "terminated"
    board, entries, _ = government_step(out, ev, "ethics_board", b, d)
    assert entries[0].lines[0].amount == b.government.reputation.board_cents
    assert board.defence_record(PLAYER).letter_turn is None  # type: ignore[union-attr]


# --- a company that never bids (57.6 target 1) ------------------------------------------------


def test_never_bidding_plays_exactly_as_before(loaded: LoadedData) -> None:
    without = replace(loaded, game_data=loaded.game_data.model_copy(update={"government": None}))
    a = start_game(loaded, 4, "funded_spinout")
    b_ = start_game(without, 4, "funded_spinout")
    assert isinstance(a, Game)
    for _ in range(14):
        a.turn()
        b_.turn()
    assert a.balances == b_.balances
    assert a.snapshots == b_.snapshots
    assert a.state.tenders and not b_.state.tenders
