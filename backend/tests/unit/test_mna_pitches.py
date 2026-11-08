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


def test_acquisition_pitches_use_public_numbers_only(loaded: LoadedData) -> None:
    """M15r (Codex review 4 finding 5): before diligence a target's private salaries are
    hidden, so two worlds differing only in one of them give identical candidates, pitches
    and pitch words (ranking, cases and report facts alike)."""
    from dataclasses import replace

    from tst.sim.state import with_employment

    state, balances = _state(loaded)
    b, d = loaded.balance, loaded.game_data
    zoho = next(c.id for c in state.companies if c.name == "Zoho")
    job = next(e for e in state.staff(zoho) if not state.person(e.person_id).is_founder)
    richer = with_employment(state, replace(job, salary_cents=job.salary_cents + 12_000_000))
    holder = 1  # the founder holds the CEO seat in this fixture

    def out(s):  # type: ignore[no-untyped-def]
        ranked = pitches.candidates(s, 1, ("acquisition",), CASH_CENTS, b, d, balances, seat="ceo")
        made = [pitches.make_pitch(s, 1, "ceo", holder, c, b) for c in ranked]
        return ranked, made, [pitches.pitch_text(s, p) for p in made]

    plain, rich = out(state), out(richer)
    assert any(int(dict(c.params)["company_id"]) == zoho for c in plain[0])
    assert plain == rich
