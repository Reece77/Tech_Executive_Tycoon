"""M47 sub-task 5 (docs/formulas.md 58.1, 58.4): each deal kind's median is today's price
(58.5 target 1: skip is fair), an agreement executes through the kind's existing action, and a
walk-away loses the deal as that deal is lost."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, make_person, with_candidates, with_employee
from tests.pharma_helpers import base, programme
from tst.loader import LoadedData
from tst.sim.actions import apply_action
from tst.sim.actions.commodities import SignCommodityContract
from tst.sim.calendar import ym_to_turn
from tst.sim.commodities import offtake
from tst.sim.government.models import Contract
from tst.sim.ledger import CASH
from tst.sim.negotiation import deals, engine
from tst.sim.negotiation.models import BP
from tst.sim.pharma import licensing
from tst.sim.power import ppa
from tst.sim.rivals.models import PoachApproach
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

RICH = {(1, CASH): 10**14}


def _apply(state: GameState, action: object, loaded: LoadedData) -> GameState:
    out = apply_action(
        state,
        action,  # type: ignore[arg-type]
        RngFactory(state.save_meta.master_seed),
        loaded.balance,
        loaded.game_data,
        RICH,
        seq=1,
    )
    return out.new_state


def _deal(state: GameState, kind: str, params: dict[str, object], loaded: LoadedData) -> deals.Deal:
    return deals.deal_for(
        state,
        kind,  # type: ignore[arg-type]
        params,
        RngFactory(state.save_meta.master_seed),
        RICH,
        loaded.balance,
        loaded.game_data,
    )


def _founder(state: GameState) -> int:
    founder = state.founder_of(state.player.id)
    assert founder is not None
    return founder.id


def test_a_hire_skips_at_the_expectation_and_is_accepted_when_agreed(loaded: LoadedData) -> None:
    state = with_candidates(loaded, fresh_game(loaded), 1, interviewed=True)
    pid = state.candidates[-1].person_id
    deal = _deal(state, "hire", {"candidate_id": pid, "equity_bp": 0}, loaded)
    expectation = state.person(pid).salary_expectation_cents
    assert deal.ref.medians == (expectation,)
    after = _apply(state, deals.agreement(deal, deal.ref.medians, _founder(state), 0.0), loaded)
    hired = after.employment_of(pid)
    assert hired is not None and hired.salary_cents == expectation
    assert after.candidate(pid).status == "hired"  # type: ignore[union-attr]
    walked = _apply(state, deals.walk_away(deal, _founder(state), loaded.balance), loaded)
    assert walked.candidate(pid).status == "declined"  # type: ignore[union-attr]


def _approached(loaded: LoadedData) -> tuple[GameState, PoachApproach]:
    state = fresh_game(loaded)
    pid, ids = state.next_ids.take("person")
    state = replace(state, next_ids=ids)
    state = with_employee(loaded, state, make_person(loaded, pid), 10_000_000)
    rival = next(c for c in state.rivals() if c.alive)
    approach = PoachApproach(1, rival.id, pid, 13_000_000, state.turn)
    return replace(state, approaches=(approach,)), approach


def test_a_retention_matches_the_rivals_offer_and_keeps_the_person(loaded: LoadedData) -> None:
    state, approach = _approached(loaded)
    deal = _deal(state, "retention", {"approach_id": approach.id}, loaded)
    assert deal.ref.medians == (approach.offer_cents,)
    after = _apply(state, deals.agreement(deal, (12_500_000,), _founder(state), 0.0), loaded)
    emp = after.employment_of(approach.person_id)
    assert emp is not None and emp.salary_cents == 12_500_000
    assert after.approaches[0].status == "declined"
    lost = _apply(state, deals.walk_away(deal, _founder(state), loaded.balance), loaded)
    assert lost.approaches[0].status == "accepted"
    assert lost.employment_of(approach.person_id).status == "notice"  # type: ignore[union-attr]


def test_a_supplier_contract_at_the_median_is_the_quote(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    params = {"good": "lithium_carbonate", "months": 12, "volume_year": 100.0}
    deal = _deal(state, "supplier", params, loaded)
    assert deal.ref.medians == (BP,)
    founder = _founder(state)
    plain = _apply(state, SignCommodityContract(founder, "lithium_carbonate", 12, 100.0), loaded)
    skipped = _apply(state, deals.agreement(deal, (BP,), founder, deal.ref.terms[0].base), loaded)
    assert plain.commodity_deals == skipped.commodity_deals
    cheaper = _apply(state, deals.agreement(deal, (9_500,), founder, 0.0), loaded)
    assert cheaper.commodity_deals[-1].signing_price == pytest.approx(
        plain.commodity_deals[-1].signing_price * 0.95
    )


def test_quotes_at_the_median_are_unchanged(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    q = offtake.contract_quote(state, "cobalt", 12, 10.0, loaded.balance, loaded.game_data)
    assert offtake.at_bp(q, BP, loaded.game_data) == q
    region = loaded.game_data.region_keys[0]
    seller = ppa.sellers(loaded.game_data, region)[0].key
    pq = ppa.quote(state, region, seller, 100.0, 10, loaded.balance, loaded.game_data)
    assert ppa.at_bp(pq, BP, loaded.balance) == pq


def test_a_foundry_agreement_passes_the_ceiling_only_when_agreed(loaded: LoadedData) -> None:
    ref = deals.Deal(
        "foundry",
        {"fab_id": 3, "customer": "Apple", "monthly_starts": 100.0, "months": 12},
        None,  # type: ignore[arg-type]
        0,
    )
    action = deals.agreement(ref, (10_400,), 9, 1_000_000.0)
    assert action.agreed and action.price_cents == pytest.approx(1_040_000.0)  # type: ignore[union-attr]


def test_a_government_contract_starts_at_the_agreed_value(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    c = Contract(
        id=1, tender_id=0, company_id=state.player.id, product_id=1, government="us",
        area="cloud", buyer="civil", contract="fixed_price", value_cents=4_000_000_000,
        start_turn=state.turn + 1, base_end_turn=state.turn + 37, end_turn=state.turn + 61,
    )  # fmt: skip
    state = replace(state, gov_contracts=(c,))
    deal = _deal(state, "government", {"contract_id": 1}, loaded)
    assert deal.ref.medians == (c.value_cents,)
    assert deal.ref.terms[0].wants == "higher"
    up = _apply(state, deals.agreement(deal, (4_100_000_000,), _founder(state), 0.0), loaded)
    assert up.gov_contracts[0].value_cents == 4_100_000_000
    lost = _apply(state, deals.walk_away(deal, _founder(state), loaded.balance), loaded)
    assert lost.gov_contracts[0].status == "terminated"
    started = replace(state, gov_contracts=(replace(c, start_turn=state.turn),))
    with pytest.raises(Exception, match="settled when delivery began"):
        _deal(started, "government", {"contract_id": 1}, loaded)


def test_licences_skip_at_the_listed_upfront(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    rng = RngFactory(4)
    from tst.sim.pharma import pipeline

    state = base(loaded, turn=ym_to_turn(2022, 1))
    state, _ = pipeline.start_programme(
        state, state.player.id, "PX", "obesity", "small_molecule", False, rng, b, d
    )
    state = licensing.january(state, rng, b, d)
    asset = state.pharma_assets[0]
    deal = _deal(state, "licence_in", {"asset_id": asset.id}, loaded)
    assert deal.ref.medians == (asset.upfront_cents,)
    after = _apply(
        state, deals.agreement(deal, (asset.upfront_cents - 1000,), _founder(state), 0.0), loaded
    )
    assert after.pharma_deals[-1].upfront_cents == asset.upfront_cents - 1000
    lapsed = _apply(state, deals.walk_away(deal, _founder(state), b), loaded)
    assert next(a for a in lapsed.pharma_assets if a.id == asset.id).until_turn == state.turn

    state = base(loaded, turn=ym_to_turn(2022, 1))
    p = programme(state, stage="phase2", status="ready", obs_n=1, obs_eff=0.6)
    state = replace(state, pharma_programmes=(p,))
    lilly = next(c for c in state.rivals() if c.name == "Eli Lilly")
    deal = _deal(state, "licence_out", {"programme_id": p.id, "rival_id": lilly.id}, loaded)
    up, _, _, _ = licensing.out_terms(p, False, b, d)
    assert deal.ref.medians == (up,) and deal.ref.terms[0].wants == "higher"


def test_an_acquisitions_zone_is_its_first_counter_and_reservation(loaded: LoadedData) -> None:
    from tst.sim.mna import deals as md
    from tst.sim.mna import valuation

    state = fresh_game(loaded)
    balances = {**RICH}
    target = next(
        c
        for c in state.rivals()
        if c.alive
        and c.parent_id is None
        and not valuation.is_listed(state, c.id, loaded.game_data)
    )
    deal = _deal(state, "acquisition", {"target_id": target.id, "mode": "brand"}, loaded)
    ((aspiration, reservation),) = deal.ref.zones or ((0, 0),)
    assert reservation == md.reservation_cents(
        state, target.id, balances, loaded.balance, loaded.game_data
    )
    assert aspiration >= reservation
    neg = engine.open_negotiation(deal.ref, RngFactory(1), state.turn, 1.0, (), 0, loaded.balance)
    median = engine.skip(neg).final
    assert median == ((aspiration + reservation) // 2,)
    assert median is not None
    after = _apply(state, deals.agreement(deal, median, _founder(state), 0.0), loaded)
    assert any(x.target_id == target.id for x in after.deals)
