"""M16 sub-task 5 (formulas.md 31.4): subsidiaries as companies. A mandate steers the brand's
decisions and how much cash it keeps; each December its board scores the CEO, and two misses
bring a replacement proposal; with minorities, cash moves up only as dividends, pro rata; a
subsidiary CEO's capital request is judged against the mandate and, approved, funded."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.unit.test_m16_group_membership import _assert_balanced, _two_brands
from tst.loader import LoadedData
from tst.sim.errors import GroupRuleError
from tst.sim.group.subsidiaries import (
    AnswerGroupPitch,
    ReplaceSubsidiaryCeo,
    SetMandate,
    board_seats,
    review,
)
from tst.sim.ledger import CASH, COMMON_EQUITY, INVESTMENT_SUBSIDIARIES
from tst.sim.mna.models import DIRECTIVE_PERSONALITY
from tst.sim.mna.style import style
from tst.sim.press.names import rival_ceo_id
from tst.sim.state import mandate_of, owner_at, with_mandate, with_ownership


def _energy(game) -> None:  # type: ignore[no-untyped-def]
    from tests.unit.test_mna_deals import _energy as fill

    fill(game)


def test_a_mandate_sets_the_brand_style_and_only_for_subsidiaries(loaded: LoadedData) -> None:
    game, a, b = _two_brands(loaded)
    _energy(game)
    game.act(SetMandate(1, a, "return_cash"))
    assert mandate_of(game.state, a).kind == "return_cash"  # type: ignore[union-attr]
    assert style(game.state, game.state.company(a)) == DIRECTIVE_PERSONALITY["harvest"]
    assert style(game.state, game.state.company(b)) == DIRECTIVE_PERSONALITY["grow"]  # directive
    with pytest.raises(GroupRuleError):
        game.act(SetMandate(1, 1, "grow"))  # the player runs its own company
    with pytest.raises(GroupRuleError):
        game.act(SetMandate(1, a, "dominate"))  # type: ignore[arg-type]
    assert board_seats(game.state, a, loaded.balance) == (3, 2, 0)


def test_two_missed_decembers_bring_a_replacement(loaded: LoadedData) -> None:
    game, a, _ = _two_brands(loaded)
    _energy(game)
    game.act(SetMandate(1, a, "grow"))
    m = mandate_of(game.state, a)
    assert m is not None
    # an impossible target: every December is a miss
    b = loaded.balance
    hard = b.model_copy(
        update={
            "group": b.group.model_copy(
                update={"mandate": b.group.mandate.model_copy(update={"grow_target": 100.0})}
            )
        }
    )
    first, met, _ = review(game.state, m, game.balances, hard, loaded.game_data)
    assert not met and first.misses == 1 and not first.proposal
    second, met, words = review(game.state, first, game.balances, hard, loaded.game_data)
    assert second.misses == 2 and second.proposal and "revenue growth" in words
    game.state = with_mandate(game.state, second)
    ceo = rival_ceo_id(game.state, a)
    assert ceo is not None
    game.act(ReplaceSubsidiaryCeo(1, a))
    assert ceo not in {e.person_id for e in game.state.staff(a)}
    after = mandate_of(game.state, a)
    assert after is not None and after.misses == 0 and not after.proposal
    with pytest.raises(GroupRuleError):  # no proposal now
        game.act(ReplaceSubsidiaryCeo(1, a))


def test_december_reviews_run_in_the_turn(loaded: LoadedData) -> None:
    game, a, _ = _two_brands(loaded)
    _energy(game)
    game.act(SetMandate(1, a, "margin"))
    while game.state.turn % 12 != 11:
        game.turn()
    result = game.turn()
    m = mandate_of(game.state, a)
    assert m is not None and m.last_review_turn == 11 and m.last_result
    kinds = {i.template for i in result.log_items}
    assert kinds & {"group_review_met", "group_review_missed"}


def test_with_minorities_cash_moves_up_as_dividends(loaded: LoadedData) -> None:
    game, a, _ = _two_brands(loaded)
    held = owner_at(game.state, a)
    assert held is not None
    # outsiders hold 30% from now (as a stake sale leaves it, 31.5)
    from tst.sim.group.ownership import carrying_cents, equity_cents

    carrying = carrying_cents(held, game.balances, loaded.game_data)
    rebase = (
        game.state.turn,
        7_000,
        round(carrying * 0.7),
        equity_cents(game.balances, a, loaded.game_data),
    )
    game.state = with_ownership(game.state, replace(held, rebases=(rebase,)))
    game.balances[(a, CASH)] = game.balances.get((a, CASH), 0) + 50_000_000_00
    game.balances[(a, COMMON_EQUITY)] = game.balances.get((a, COMMON_EQUITY), 0) - 50_000_000_00
    result = game.turn()
    paid = [e for e in result.ledger_entries if e.company_id == a and e.memo.startswith("Dividend")]
    got = [
        e for e in result.ledger_entries if e.company_id == 1 and e.memo.startswith("Dividend from")
    ]
    assert len(paid) == 1 and len(got) == 1
    whole = {x.account: x.amount for x in paid[0].lines}[CASH]
    mine = {x.account: x.amount for x in got[0].lines}[INVESTMENT_SUBSIDIARIES]
    assert -mine == round(-whole * 0.7)  # pro rata
    assert not any(
        e.memo.startswith("Cash swept") and e.company_id == a for e in result.ledger_entries
    )


def test_a_capital_request_is_judged_and_funded(loaded: LoadedData) -> None:
    game, a, _ = _two_brands(loaded)
    _energy(game)
    game.act(SetMandate(1, a, "grow"))
    b = loaded.balance
    sure = b.model_copy(
        update={
            "group": b.group.model_copy(
                update={"mandate": b.group.mandate.model_copy(update={"pitch_chance": 1.0})}
            )
        }
    )
    game.loaded = replace(game.loaded, balance=sure)
    while game.state.turn % 3 != 0:
        game.turn()
    game.turn()
    (pitch,) = [p for p in game.state.group_pitches if p.status == "pending"]
    assert pitch.company_id == a and pitch.fits_mandate and pitch.amount_cents > 0
    cash = game.balances[(a, CASH)]
    game.act(AnswerGroupPitch(1, pitch.id, True))
    assert game.balances[(a, CASH)] == cash + pitch.amount_cents
    assert game.state.group_pitches[0].status == "approved"
    _assert_balanced(game, 1)
