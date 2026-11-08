"""M14 sub-task 7 (formulas.md 28.7): the CEO and the CPO pitch acquisitions; the CPO only
startups under the auto-approve limit x 4; acquisitions never auto-approve."""

from __future__ import annotations

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


CPO_CASH = 1_000_000_000_00  # $1B: the default limit is 5% ($50M), the CPO's x4 $200M


def _startups(loaded: LoadedData):  # type: ignore[no-untyped-def]
    """Zoho (about $125M) an eligible startup, SAP (about $315M) a startup over the CPO's
    limit, Salesforce (about $945M) an incumbent the CEO can afford, Oracle beyond the cash
    (M15r, Codex review 4 finding 11)."""
    from dataclasses import replace

    from tst.sim.state import with_company

    state, balances = _state(loaded)
    for name in ("Zoho", "SAP"):
        company = next(c for c in state.companies if c.name == name)
        state = with_company(state, replace(company, is_startup=True))
    return state, {**balances, (1, CASH): CPO_CASH}


def _targets(state, ranked) -> set[str]:  # type: ignore[no-untyped-def]
    return {state.company(int(dict(c.params)["company_id"])).name for c in ranked}


def test_the_cpo_pitches_only_affordable_startups(loaded: LoadedData) -> None:
    state, balances = _startups(loaded)
    b, d = loaded.balance, loaded.game_data
    for name, low, high in (("Zoho", 0, 200), ("SAP", 200, 1_000), ("Salesforce", 0, 1_000)):
        target = next(c.id for c in state.companies if c.name == name)
        estimate = pitches_estimate(state, target, balances, loaded) // 100_000_000  # $M
        assert low <= estimate < high, name  # the fixture is what the test says it is
    cpo = pitches.candidates(state, 1, ("acquisition",), CPO_CASH, b, d, balances, seat="cpo")
    assert _targets(state, cpo) == {"Zoho"}
    ceo = pitches.candidates(state, 1, ("acquisition",), CPO_CASH, b, d, balances, seat="ceo")
    assert _targets(state, ceo) == {"Zoho", "SAP", "Salesforce"}


def pitches_estimate(state, target: int, balances, loaded: LoadedData) -> int:  # type: ignore[no-untyped-def]
    from tst.sim.mna import deals

    return deals.estimate_cents(state, 1, target, balances, loaded.balance, loaded.game_data)


def test_acquisitions_never_auto_approve(loaded: LoadedData) -> None:
    """On Holiday, with a spend limit far above the price, an acquisition pitch still waits
    for the founder: no deal, no posting (28.7)."""
    from tests.helpers import with_product
    from tests.unit.test_m10c_executives import EXEC, _company, _give
    from tst.sim.org.delegates import DelegateRun
    from tst.sim.org.formulas import pitch_chance
    from tst.sim.org.models import PitchPolicy
    from tst.sim.rng import RngFactory
    from tst.sim.state import with_pitch_policy

    b, d = loaded.balance, loaded.game_data
    state = _company(loaded, "cpo", "product_manager", staff=3)
    state = with_product(state, customers={"mid_market": 100.0}, prices={"mid_market": 4000})
    state = _give(state, "cpo", b)
    state = with_pitch_policy(state, PitchPolicy(1, auto_approve_cents=10**15))
    balances = {**rival_cash(state, loaded), (1, CASH): CASH_CENTS}
    assert pitches.candidates(state, 1, ("acquisition",), CASH_CENTS, b, d, balances, seat="ceo")
    chance = pitch_chance(state.person(EXEC).personality["ambition"], b.pitch)
    seed = next(
        s
        for s in range(1, 500)
        if float(RngFactory(s).stream(state.turn, "pitch", EXEC).random(2)[0]) < chance
    )
    run = DelegateRun(state=state, balances=dict(balances), rng=RngFactory(seed), balance=b, data=d)
    pitches.pitch_month(run, 1, "ceo", EXEC, ("acquisition",), 20.0, at_controls=False)
    (pitch,) = run.state.pitches
    assert pitch.kind == "acquisition" and pitch.status == "pending"
    assert pitch.cost_cents < 10**15  # under the limit: any other pitch would go ahead
    assert run.state.deals == state.deals and run.entries == [] and run.taken == []


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
