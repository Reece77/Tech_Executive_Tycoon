"""M42 (docs/formulas.md 55): pharma.yaml's sources; history holds for a company without pharma
(55.6 target 1); the pipeline and readouts (55.1); AI discovery (55.2); approval and exclusivity
(55.3); demand, prices, the IRA and the cliff (55.4); supply and licensing (55.5); and the
hidden-value guarantee in the engine's shown values (55.7)."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest

from tests.pharma_helpers import base, marketed, programme
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.data_models import Balance
from tst.sim.ledger import CASH, DRUG_SALES
from tst.sim.pharma import approval, demand, licensing, pipeline, rivals, rules, value
from tst.sim.pharma import data as pd
from tst.sim.pharma.models import Drug
from tst.sim.pharma.month import events_month, sales_month
from tst.sim.rng import RngFactory

DATA = Path(__file__).resolve().parents[2] / "data"
VALUE = re.compile(r"^\s+-?\s*[a-z_0-9]+:\s*(\[|\{|-?\d)")


# --- the data and its sources (55.6 target 1) --------------------------------------------------


def test_every_value_in_pharma_yaml_has_a_source() -> None:
    """Every line of pharma.yaml holding a number carries a comment with its source, est. or A,
    or sits under a block comment that cites it (areas, stages, modalities, rules)."""
    text = (DATA / "pharma.yaml").read_text(encoding="utf-8")
    blocks = 0
    for line in text.splitlines():
        if line.startswith("# ---"):
            blocks += 1
        if line.lstrip().startswith(("#", "label:", "text:", "source:")) or not VALUE.match(line):
            continue
        inline = "#" in line or "source:" in line
        assert inline or blocks, f"no source for: {line.strip()}"
    for key in ("BIO", "Paul et al.", "Moore", "Martin", "IRA", "RAND", "PDUFA", "Jayatunga"):
        assert key in text, key


def test_the_areas_are_bio_2021s_rates(loaded: LoadedData) -> None:
    pf = pd.file(loaded.game_data)
    onc = pf.area("oncology").transitions
    assert round(onc.loa, 3) == 0.053  # BIO 2021 oncology
    assert round(pf.area("rare_disease").transitions.loa, 3) == 0.170
    assert min(a.transitions.loa for a in pf.areas) == pf.area("cardiovascular").transitions.loa


def test_the_pharma_categories_are_pseudo_and_out_of_the_markets(loaded: LoadedData) -> None:
    d = loaded.game_data
    assert not any(c.pharma for c in d.categories)
    keys = {c.key for c in d.pseudo_categories if c.pharma}
    assert keys == {a.category for a in pd.file(d).areas}


def test_rivals_follow_their_reported_revenue_to_2025(loaded: LoadedData) -> None:
    """With no modelled drugs, a rival's month is its data at the game's scale (55.5)."""
    b, d = loaded.balance, loaded.game_data
    state = base(loaded, turn=ym_to_turn(2024, 7))
    pfizer = next(c for c in state.rivals() if c.name == "Pfizer")
    r = pd.file(d).rival("Pfizer")
    assert r is not None
    cents = rivals.monthly_cents(state, pfizer.id, r, {}, 0.0, b, d)
    expected = 63.6 * pd.BILLION * pd.CENTS * b.pharma.scale / pd.MONTHS
    assert cents == pytest.approx(expected, rel=0.01)


def test_rivals_make_no_product_decisions(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = base(loaded)
    pfizer = next(c for c in state.rivals() if c.name == "Pfizer")
    apple = next(c for c in state.rivals() if c.name == "Apple")
    assert rivals.holds(state, pfizer, b, d)
    assert not rivals.holds(state, apple, b, d)
    assert not state.company_products(pfizer.id)


def test_a_company_without_pharma_draws_and_posts_nothing_of_its_own(loaded: LoadedData) -> None:
    """55.6 target 1: no programme, drug, deal or asset for the player; sales and events post
    only rivals' lines (a rival's revenue joins its MRR)."""
    b, d = loaded.balance, loaded.game_data
    rng = RngFactory(1)
    state = base(loaded, turn=ym_to_turn(2015, 1))
    player = state.player.id
    for _ in range(13):
        state, entries, revenue = sales_month(state, b, d)
        assert all(e.company_id != player for e in entries)
        assert player not in revenue
        state, entries, logs = events_month(state, rng, b, d)
        assert not entries and not logs
        state = replace(state, turn=state.turn + 1)
    assert not state.pharma_programmes and not state.pharma_assets and not state.pharma_months


def test_assets_are_listed_only_once_the_player_comes_to_pharma(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    rng = RngFactory(1)
    state = base(loaded, turn=ym_to_turn(2022, 1))
    assert licensing.january(state, rng, b, d).pharma_assets == ()
    state, _ = pipeline.start_programme(
        state, state.player.id, "PX", "obesity", "small_molecule", False, rng, b, d
    )
    listed = licensing.january(state, rng, b, d).pharma_assets
    assert len(listed) == b.pharma.rivals.assets_a_year


# --- the pipeline (55.1) -----------------------------------------------------------------------


def test_a_programme_starts_in_discovery_and_reads_out_on_its_planned_month(
    loaded: LoadedData,
) -> None:
    b, d = loaded.balance, loaded.game_data
    rng = RngFactory(3)
    state = base(loaded, turn=ym_to_turn(2015, 1))
    state, logs = pipeline.start_programme(
        state, state.player.id, "PX", "lung_cancer", "biologic", False, rng, b, d
    )
    p = state.pharma_programmes[0]
    assert p.stage == "discovery" and logs[0].template == "pharma_programme_started"
    months = pipeline.stage_months(p, "discovery", "standard", b, d)
    assert p.due_turn == state.turn + months
    spent = 0
    for _ in range(months + 1):
        state, entries, _ = pipeline.month(state, rng, b, d)
        spent += sum(e.lines[0].amount for e in entries)
        state = replace(state, turn=state.turn + 1)
    p = state.pharma_programmes[0]
    assert p.stage == "preclinical" and p.patent_turn is not None
    assert spent == pipeline.stage_cost_cents(p, "discovery", 0, months, b, d)


def test_discovery_capacity_counts_research_staff(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = base(loaded, turn=ym_to_turn(2015, 1))
    assert pipeline.discovery_slots(state, state.player.id, b, d) == b.pharma.discovery.slots_base
    rng = RngFactory(1)
    state, _ = pipeline.start_programme(
        state, state.player.id, "A", "obesity", "small_molecule", False, rng, b, d
    )
    from tst.sim.errors import PharmaRuleError

    with pytest.raises(PharmaRuleError, match="capacity"):
        pipeline.start_programme(
            state, state.player.id, "B", "obesity", "small_molecule", False, rng, b, d
        )


def test_readouts_are_seeded_and_follow_the_hidden_values(loaded: LoadedData) -> None:
    """Same seed, same readouts; a better molecule's true chance is higher (55.1)."""
    b, d = loaded.balance, loaded.game_data
    state = base(loaded, turn=ym_to_turn(2018, 1))
    p = programme(state, stage="phase2", status="active", due_turn=state.turn)
    state = replace(state, pharma_programmes=(p,))
    first = pipeline.read_out(state, p, RngFactory(9), b, d)[0].pharma_readouts
    again = pipeline.read_out(state, p, RngFactory(9), b, d)[0].pharma_readouts
    assert first == again
    good, bad = replace(p, efficacy=0.9), replace(p, efficacy=0.2)
    assert pipeline.chance(good, "phase2", "standard", b, d) > pipeline.chance(
        bad, "phase2", "standard", b, d
    )


def test_a_failed_readout_can_be_redesigned_or_stopped(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = base(loaded, turn=ym_to_turn(2018, 1))
    p = programme(state, stage="phase2", status="failed", obs_n=1, obs_eff=0.5)
    state = replace(state, pharma_programmes=(p,))
    redo = pipeline.begin_stage(state, p, "phase2", "large", b, d, redo=True)
    plain = pipeline.begin_stage(state, p, "phase2", "large", b, d)
    assert redo.status == "active" and redo.attempt == 1
    assert redo.cost_cents == round(plain.cost_cents * (1 + b.pharma.redesign_cost_share))


# --- 55.7: what is shown never reads the hidden values -------------------------------------------


@pytest.mark.parametrize("stage", ["phase1", "phase2", "phase3"])
def test_shown_chances_ranges_and_value_ignore_hidden_values(
    loaded: LoadedData, stage: str
) -> None:
    b, d = loaded.balance, loaded.game_data
    state = base(loaded, turn=ym_to_turn(2018, 1))
    p = programme(state, stage=stage, status="active", obs_n=1, obs_eff=0.55, obs_safety=0.7)
    q = replace(p, efficacy=0.05, safety=0.95)
    assert pipeline.shown_chance(p, stage, "standard", b, d) == pipeline.shown_chance(
        q, stage, "standard", b, d
    )
    assert pipeline.estimate_range(p, b) == pipeline.estimate_range(q, b)
    assert value.explain(p, b, d) == value.explain(q, b, d)


# --- AI discovery (55.2) -----------------------------------------------------------------------


def test_ai_discovery_needs_a_strong_model_and_shortens_preclinical(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = base(loaded, turn=ym_to_turn(2022, 1))
    assert not pipeline.ai_ready(state, state.player.id, b, d)
    early = base(loaded, turn=ym_to_turn(2019, 1))
    assert not pipeline.ai_ready(early, early.player.id, b, d)
    p = programme(state, stage="preclinical")
    ai = replace(p, ai=True)
    plain_months = pipeline.stage_months(p, "preclinical", "standard", b, d)
    ai_months = pipeline.stage_months(ai, "preclinical", "standard", b, d)
    assert ai_months == round(plain_months * (1 - b.pharma.ai.preclinical_cut))
    assert pipeline.chance(ai, "phase1", "standard", b, d) > pipeline.chance(
        p, "phase1", "standard", b, d
    )


# --- approval and exclusivity (55.3) -------------------------------------------------------------


def test_us_exclusivity_takes_the_latest_of_patent_and_data(loaded: LoadedData) -> None:
    d = loaded.game_data
    state = marketed(loaded, turn=ym_to_turn(2026, 1))
    p = state.pharma_programmes[0]
    approved = p.approved_turn
    assert approved is not None
    loe = pd.loe_turn(state, p, pd.US_REGION, d)
    assert loe is not None
    assert loe >= approved + 5 * pd.MONTHS  # NCE data exclusivity
    assert loe <= approved + 14 * pd.MONTHS  # Hatch-Waxman's cap
    bio = replace(p, modality="biologic")
    loe_bio = pd.loe_turn(state, bio, pd.US_REGION, d)
    assert loe_bio is not None and loe_bio >= approved + 12 * pd.MONTHS  # BPCIA
    eu = pd.loe_turn(state, p, pd.EU_REGION, d)
    assert eu is not None and eu >= approved + 10 * pd.MONTHS  # 8 + 2


def test_a_filing_is_reviewed_and_approved_or_refused_on_its_drawn_month(
    loaded: LoadedData,
) -> None:
    b, d = loaded.balance, loaded.game_data
    rng = RngFactory(2)
    state = base(loaded, turn=ym_to_turn(2018, 1))
    p = programme(state, stage="phase3", status="ready", obs_n=3, obs_eff=0.75, obs_safety=0.7)
    state = replace(state, pharma_programmes=(p,))
    state, _ = approval.file(state, p, "fda_drugs", rng, b, d)
    review = state.pharma_reviews[0]
    lo, hi = approval.review_range(d, "fda_drugs", review.priority)
    assert lo <= review.due_turn - review.filed_turn <= hi
    while state.turn <= review.due_turn:
        state, _, _ = approval.month(state, rng, b, d)
        state = replace(state, turn=state.turn + 1)
    assert state.pharma_reviews[0].status in ("approved", "crl")
    if state.pharma_reviews[0].status == "approved":
        assert state.pharma_programmes[0].status == "marketed"
        assert pd.access(state, p.id, pd.US_REGION, d) > 0


# --- demand, prices and the cliff (55.4) ---------------------------------------------------------


def test_a_marketed_drug_sells_and_books_balanced_entries(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = marketed(loaded, turn=ym_to_turn(2026, 1))
    state, entries, out = demand.month(state, b, d)
    sales = sum(e.lines[1].amount for e in entries if e.lines[1].account == DRUG_SALES)
    assert -sales == out.revenue[state.player.id] > 0
    assert all(sum(line.amount for line in e.lines) == 0 for e in entries)
    assert any(line.account == CASH for e in entries for line in e.lines)


def test_better_drugs_take_more_patients_and_a_higher_price_fewer(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    good = marketed(loaded, turn=ym_to_turn(2026, 1), efficacy=0.8)
    poor = marketed(loaded, turn=ym_to_turn(2026, 1), efficacy=0.4)
    assert demand.month(good, b, d)[2].patients[1] > demand.month(poor, b, d)[2].patients[1]
    drug = good.pharma_drugs[0]
    dear = replace(good, pharma_drugs=(replace(drug, list_cents=drug.list_cents * 2),))
    assert demand.month(dear, b, d)[2].patients[1] < demand.month(good, b, d)[2].patients[1]


def test_the_cliff_cuts_a_small_molecules_revenue(loaded: LoadedData) -> None:
    """55.6 target 4: 24 months after exclusivity ends everywhere, most revenue is gone."""
    b, d = loaded.balance, loaded.game_data
    state = marketed(loaded, turn=ym_to_turn(2026, 1))
    p = state.pharma_programmes[0]
    ends = [pd.loe_turn(state, p, r, d) for r in d.region_keys]
    first = min(e for e in ends if e is not None)
    last = max(e for e in ends if e is not None)
    before = demand.month(replace(state, turn=first - 1), b, d)[2].revenue[state.player.id]
    after = demand.month(replace(state, turn=last + 24), b, d)[2].revenue[state.player.id]
    assert after < 0.3 * before
    assert pd.retained(pd.modality(d, "biologic"), 24) > pd.retained(
        pd.modality(d, "small_molecule"), 24
    )


def test_the_ira_selects_an_old_large_drug_and_cuts_its_medicare_price(
    loaded: LoadedData,
) -> None:
    b, d = loaded.balance, loaded.game_data
    turn = ym_to_turn(2028, 1)
    state = marketed(loaded, turn=turn, approved=turn - 10 * pd.MONTHS)
    pid = state.pharma_programmes[0].id
    big = round(5 * pd.BILLION * pd.CENTS * b.pharma.scale / pd.MONTHS)
    from tst.sim.pharma.models import DrugMonth

    months = tuple(
        DrugMonth(t, pid, state.player.id, 1.0, big, big) for t in range(turn - 12, turn)
    )
    state = replace(state, pharma_months=months)
    picked, logs = rules.january(state, RngFactory(1), b, d)
    assert [i.programme_id for i in picked.pharma_ira] == [pid]
    assert logs[0].template == "pharma_ira_selected"
    drug = picked.pharma_drugs[0]
    p = picked.pharma_programmes[0]
    assert demand.net_cents_year(picked, p, drug, pd.US_REGION, d) < demand.net_cents_year(
        state, p, drug, pd.US_REGION, d
    )
    young = marketed(loaded, turn=turn, approved=turn - 3 * pd.MONTHS)
    young = replace(young, pharma_months=months)
    assert rules.january(young, RngFactory(1), b, d)[0].pharma_ira == ()


def test_hta_refuses_a_price_above_the_value_cap(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = marketed(loaded, turn=ym_to_turn(2026, 1), efficacy=0.5)
    p = state.pharma_programmes[0]
    cap = approval.value_cap_cents(p, "europe", b, d)
    drug = state.pharma_drugs[0]
    assert drug.list_cents <= cap
    assert replace(drug, list_cents=round(cap * 2)).list_cents > cap


# --- licensing (55.5) --------------------------------------------------------------------------


def test_an_in_licensed_asset_pays_upfront_and_keeps_its_hidden_values(
    loaded: LoadedData,
) -> None:
    b, d = loaded.balance, loaded.game_data
    rng = RngFactory(4)
    state = base(loaded, turn=ym_to_turn(2022, 1))
    state, _ = pipeline.start_programme(
        state, state.player.id, "PX", "obesity", "small_molecule", False, rng, b, d
    )
    state = licensing.january(state, rng, b, d)
    asset = state.pharma_assets[0]
    state, entries, _ = licensing.take_asset(state, state.player.id, asset.id, False, b, d)
    p = state.pharma_programmes[-1]
    assert (p.efficacy, p.safety) == (asset.efficacy, asset.safety)
    assert entries[0].lines[0].amount == asset.upfront_cents
    assert state.pharma_deals[-1].royalty == asset.royalty


def test_out_licensing_moves_the_programme_and_pays_the_player(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = base(loaded, turn=ym_to_turn(2022, 1))
    p = programme(state, stage="phase2", status="ready", obs_n=1, obs_eff=0.6)
    state = replace(state, pharma_programmes=(p,))
    lilly = next(c for c in state.rivals() if c.name == "Eli Lilly")
    state, entries, _ = licensing.out_license(state, p, lilly.id, False, b, d)
    assert state.pharma_programmes[0].company_id == lilly.id
    received = [e for e in entries if e.company_id == p.company_id]
    assert received and received[0].lines[0].account == CASH


def test_a_drug_needs_supply_and_a_recall_stops_it(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = marketed(loaded, turn=ym_to_turn(2026, 1))
    drug = state.pharma_drugs[0]
    blocked = replace(state, pharma_drugs=(replace(drug, blocked_until=state.turn + 1),))
    assert demand.month(blocked, b, d)[2].revenue.get(state.player.id, 0) == 0
    assert isinstance(drug, Drug)


# --- M43a's ceilings (54.1) on pharma's markets --------------------------------------------------


def _tight(loaded: LoadedData, share: float) -> Balance:
    b = loaded.balance
    shares = {**b.markets.ceiling_share, "pharma_metabolic": share}
    return b.model_copy(update={"markets": b.markets.model_copy(update={"ceiling_share": shares})})


def test_pharma_markets_follow_their_data_before_the_ceilings(loaded: LoadedData) -> None:
    from tst.sim.pharma import ceilings

    b, d = loaded.balance, loaded.game_data
    state = base(loaded, turn=ym_to_turn(2025, 6))
    assert ceilings.month(state, b, d).pharma_markets == ()
    assert ceilings.world_factor(state, b, d) == 1.0


def test_a_pharma_market_at_its_ceiling_is_held_not_cut(loaded: LoadedData) -> None:
    from tst.sim.pharma import ceilings

    d = loaded.game_data
    tight = _tight(loaded, 1e-6)
    state = base(loaded, turn=ym_to_turn(2030, 1))
    metabolic = pd.area(d, "metabolic")
    for region in ("north_america", "europe"):
        before = ceilings.value_cents(state, d, tight, metabolic, region)
        after_state = replace(ceilings.month(state, tight, d), turn=state.turn)
        held = ceilings.value_cents(after_state, d, tight, metabolic, region)
        grown = ceilings.value_cents(
            replace(after_state, pharma_markets=()), d, tight, metabolic, region
        )
        assert held == pytest.approx(
            ceilings._uncapped_cents(d, tight, metabolic, region, state.turn - 1)
        )
        assert held < grown and before > 0


@pytest.mark.parametrize("year", [2027, 2040, 2060])
def test_no_pharma_market_grows_past_its_ceiling(loaded: LoadedData, year: int) -> None:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    from tst.sim.markets import saturation
    from tst.sim.pharma import ceilings

    d = loaded.game_data

    @settings(max_examples=15, deadline=None)
    @given(share=st.floats(1e-5, 0.02), months=st.integers(1, 24))
    def check(share: float, months: int) -> None:
        b = _tight(loaded, share)
        state = base(loaded, turn=ym_to_turn(year, 1))
        area = pd.area(d, "metabolic")
        for _ in range(months):
            prev = ceilings.value_cents(state, d, b, area, "north_america")
            state = replace(ceilings.month(state, b, d), turn=state.turn + 1)
            state = replace(state, turn=state.turn - 1)
            now = ceilings.value_cents(state, d, b, area, "north_america")
            cap = saturation.ceiling_cents(state, b, d, area.category, "north_america")
            assert now <= max(cap, prev) * (1 + 1e-9)
            state = replace(state, turn=state.turn + 1)

    check()
