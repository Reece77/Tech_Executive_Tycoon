"""M57 sub-task 4: the v6 scripts (tst.balance.strategies_v6) take their system's first actions on
short runs; the targets themselves are weekly (tests/balance/test_v6_balance.py). Each run starts
from a new game moved to the system's first month (stage 3, cash to cover it), so it is quick."""

from __future__ import annotations

from dataclasses import replace

from tst.balance import strategies_v6 as s6
from tst.balance import v6
from tst.balance.game import PLAYER, Game, start_game
from tst.balance.report import SCENARIO
from tst.balance.strategies import Strategy
from tst.balance.v3 import loaded
from tst.sim.calendar import ym_to_turn
from tst.sim.ledger import CASH
from tst.sim.media.models import LeadOffer
from tst.sim.state import with_company, with_product
from tst.sim.telecom.models import Auction

RICH = 10**12  # $10B of cash


def _at(turn: int, seed: int = 1) -> Game:
    game = start_game(loaded(), seed, SCENARIO)
    game.state = replace(game.state, turn=turn)
    game.state = with_company(game.state, replace(game.state.player, stage=3))
    game.balances[(PLAYER, CASH)] = RICH
    return game


def _play(game: Game, script: Strategy, months: int) -> None:
    for _ in range(months):
        script(game)
        game.turn()
    assert not game.state.ended


def test_v6_keys_are_registered() -> None:
    assert set(s6.V6) == {"telecom_operator", "bank_group", "media_studio"}
    assert set(s6.V6) <= set(v6.ALL) and set(s6.V6) <= set(v6.FIELD)
    assert set(v6.PLAYED) == set(v6.FIELD)


def test_the_scripts_start_in_their_systems_first_months() -> None:
    b = loaded().balance
    assert b.telecom.start_turn == s6.TELECOM_FROM
    assert b.media.start_turn == s6.MEDIA_FROM
    assert ym_to_turn(b.finserv.unlock_year, 1) == s6.BANK_FROM
    assert b.finserv.start_turn == s6.CHARTER_FROM
    r = b.finserv.bank.beta_range
    assert r.lo < s6._beta(_at(s6.BANK_FROM)) < r.hi


def test_telecom_operator_bids_then_builds_its_network() -> None:
    game = _at(s6.TELECOM_FROM)
    auction = Auction(
        id=1,
        key="seeded_test",
        label="United States low-band auction",
        region="north_america",
        area="united_states",
        band="low",
        mhz=40.0,
        blocks=10,
        reserve_cents=10**9,
        turn=game.state.turn + 3,
        term_years=15,
        obligation=0.7,
        obligation_years=6,
        history=False,
    )
    game.state = replace(game.state, telecom=replace(game.state.telecom, auctions=(auction,)))
    _play(game, s6.telecom_operator, 1)
    bid = game.state.telecom.auctions[0]
    assert bid.bid_company_id == PLAYER and bid.bid_blocks == 6  # the cap, 60% of 10
    assert bid.bid_limit_cents == round(auction.reserve_cents * s6.BID_MULT)
    _play(game, s6.telecom_operator, 4)
    assert any(x.company_id == PLAYER for x in game.state.telecom.licences)
    assert s6._product(game, s6.MOBILE[1]) is not None
    towers = [f for f in game.state.facilities if f.company_id == PLAYER and f.kind == "tower"]
    assert [f.capacity for f in towers] == [s6.TOWER_ORDER]


def test_telecom_operator_waits_for_telecoms_first_month() -> None:
    game = _at(s6.TELECOM_FROM - 1)
    _play(game, s6.telecom_operator, 1)
    assert "rung:bid" not in game.notes and s6._product(game, s6.MOBILE[1]) is None


def test_bank_group_partners_then_applies_for_a_charter() -> None:
    game = _at(s6.BANK_FROM)
    _play(game, s6.bank_group, 2)
    pid = s6._product(game, s6.BANK_LINE[1])
    assert pid is not None
    bank = game.state.finserv.bank_in(PLAYER, "north_america")
    assert bank is not None and bank.status == "partner"
    product = game.state.product(pid)
    assert product is not None
    game.state = with_product(game.state, replace(product, status="live", launched_turn=0))
    game.notes["partner_turn"] -= s6.PARTNER_MONTHS
    _play(game, s6.bank_group, 1)
    assert not any(b.status == "applying" for b in game.state.finserv.banks)  # not before 2026
    game.state = replace(game.state, turn=s6.CHARTER_FROM)
    _play(game, s6.bank_group, 2)
    own = [b for b in game.state.finserv.banks if b.status == "applying"]
    assert len(own) == 1
    assert (own[0].beta, own[0].loan_to_deposit, own[0].securities_share, own[0].duration) == (
        s6._beta(game),
        s6.LOAN_TO_DEPOSIT,
        s6.SECURITIES_SHARE,
        s6.DURATION,
    )


def test_media_studio_greenlights_a_title_with_the_best_shown_lead() -> None:
    game = _at(s6.MEDIA_FROM)
    offers = tuple(LeadOffer(year=2026, n=n, turn=game.state.turn) for n in range(3))
    game.state = replace(game.state, media=replace(game.state.media, offers=offers))
    best = max(s6._shown(game), key=lambda x: x[0])
    _play(game, s6.media_studio, 1)
    titles = [t for t in game.state.media.titles if t.company_id == PLAYER]
    assert len(titles) == 1 and titles[0].kind == s6.SLATE[0] and titles[0].window == "licensed"
    lead = game.state.media.lead(titles[0].lead_person_id or 0)
    assert lead is not None and lead.company_id == PLAYER
    signed = next(o for o in game.state.media.offers if o.status != "open")
    assert (signed.year, signed.n) == best[1:3]
    _play(game, s6.media_studio, s6.TITLE_GAP)
    titles = [t for t in game.state.media.titles if t.company_id == PLAYER]
    assert [t.kind for t in titles] == list(s6.SLATE[:2])
