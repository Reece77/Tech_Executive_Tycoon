"""M14 sub-task 7 (formulas.md 28.7): the CEO and the CPO pitch acquisitions; the CPO only
startups under the auto-approve limit x 4; acquisitions never auto-approve."""

from __future__ import annotations

import inspect

from tests.helpers import fresh_game, rival_cash, with_product
from tst.loader import LoadedData
from tst.sim.ledger import CASH
from tst.sim.org import pitches

CASH_CENTS = 50_000_000_000_00


def _state(loaded: LoadedData):  # type: ignore[no-untyped-def]
    state = with_product(
        fresh_game(loaded), customers={"mid_market": 100.0}, prices={"mid_market": 4000}
    )
    balances = {**rival_cash(state, loaded), (1, CASH): CASH_CENTS}
    return state, balances


def test_the_ceo_pitches_any_target_in_its_markets(loaded: LoadedData) -> None:
    state, balances = _state(loaded)
    b, d = loaded.balance, loaded.game_data
    ranked = pitches.candidates(state, 1, ("acquisition",), CASH_CENTS, b, d, balances, seat="ceo")
    names = {state.company(int(dict(c.params)["company_id"])).name for c in ranked}
    assert names and names <= {"Salesforce", "Oracle", "Zoho", "SAP"}  # B2B SaaS sellers
    for c in ranked:
        params = dict(c.params)
        assert c.kind == "acquisition" and params["mode"] in ("integrate", "brand")
        assert c.capex_cents == params["price_cents"] > 0 and "antitrust" in c.risk
    assert [c.score for c in ranked] == sorted((c.score for c in ranked), reverse=True)


def test_the_cpo_pitches_only_startups(loaded: LoadedData) -> None:
    state, balances = _state(loaded)
    b, d = loaded.balance, loaded.game_data
    ranked = pitches.candidates(state, 1, ("acquisition",), CASH_CENTS, b, d, balances, seat="cpo")
    assert all(state.company(int(dict(c.params)["company_id"])).is_startup for c in ranked)


def test_acquisitions_never_auto_approve() -> None:
    source = inspect.getsource(pitches.pitch_month)
    assert 'pitch.kind != "acquisition" and auto_approves(' in source
