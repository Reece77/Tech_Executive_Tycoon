"""M41 (docs/formulas.md 50): medical.yaml's sources and history; the category family and
markets sized to the game (50.1); classes, routes and review times (50.2); studies (50.3);
coverage and adoption (50.4); quality, inspections and recalls (50.5); the market gate; and
the hidden-value guarantee (50.7)."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest

from tests.medical_helpers import PID, medical_state
from tst.loader import LoadedData
from tst.sim.facilities.config import month_to_turn
from tst.sim.ledger import MEDICAL_RECURRING, RECALLS
from tst.sim.medical import coverage, gate, quality, recurring, routes, studies
from tst.sim.medical import data as md
from tst.sim.medical.models import Clearance, Design, Study
from tst.sim.medical.month import medical_month
from tst.sim.rng import RngFactory

DATA = Path(__file__).resolve().parents[2] / "data"
VALUE = re.compile(r"^\s+-?\s*[a-z_0-9]+:\s*(\[|\{|-?\d)")


# --- 50.6 target 1: the data and its sources --------------------------------------------------


def test_every_value_in_medical_yaml_has_a_source() -> None:
    """Every line of medical.yaml holding a number (a figure, a range or a dated map) carries a
    comment with its source or A; each route, regulator and precedent names a source."""
    text = (DATA / "medical.yaml").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.lstrip().startswith(("#", "note:", "label:")) or not VALUE.match(line):
            continue
        assert "#" in line, f"no source for: {line.strip()}"
    reg = (DATA / "regulation.yaml").read_text(encoding="utf-8").split("health_regulators:", 1)[1]
    for line in reg.splitlines():
        if re.match(r"\s+(strictness|part):", line):
            assert "#" in line, f"no source for: {line.strip()}"


def test_the_medical_sub_categories_are_categories_and_sized_to_the_game(
    loaded: LoadedData,
) -> None:
    """Each sub-category is a family medical category whose 2024 potential, served at the
    incumbents' two-thirds, is the real market x economy_scale.money within 25% (50.1)."""
    d, b = loaded.game_data, loaded.balance
    mf = md.file(d)
    keys = [c.key for c in d.categories if c.medical]
    assert keys == [s.key for s in mf.subcategories]
    regions = sum(m.size * m.price_index for m in d.region_markets)
    for sub in mf.subcategories:
        cat = d.category(sub.key)
        growth = 1.0
        for year in range(2010, 2024):
            growth *= 1 + cat.growth_in(year)
        for real_b, factor in ((sub.market.real_2010_b, 1.0), (sub.market.real_2024_b, growth)):
            yearly = 0.0
            for m in cat.markets:
                upc = m.units_per_customer
                if cat.sells_units:
                    spend = upc * m.reference_price_cents * 12 / (m.replacement_months or 12)
                else:
                    spend = m.reference_price_cents * 12
                spend += upc * sub.consumables_cents * 12
                yearly += m.addressable * factor * spend
            game = yearly * regions * 0.65 / 100
            want = real_b * 1e9 * b.economy_scale.money
            assert 0.75 < game / want < 1.25, (sub.key, real_b, game, want)


def test_the_health_regulators_are_m34_records_apart_from_competition(loaded: LoadedData) -> None:
    rf = loaded.game_data.regulation
    assert rf is not None
    assert [r.key for r in rf.health_regulators] == ["fda", "eu_notified_bodies", "pmda", "nmpa"]
    assert not {r.key for r in rf.health_regulators} & {r.key for r in rf.regulators}
    assert all(r.kind == "health" for r in rf.health_regulators)


# --- 50.2 classes, routes and review times to 2025 -------------------------------------------


@pytest.mark.parametrize(
    ("category", "use", "month", "route"),
    [
        ("surgical_robotics", "robotic_surgery", "2010-01", "k510"),  # da Vinci from 2000
        ("wearables_diagnostics", "glucose_monitoring", "2012-01", "pma"),  # class III then
        ("wearables_diagnostics", "glucose_monitoring", "2018-06", "k510"),  # iCGM after G6
        ("wearables_diagnostics", "arrhythmia_detection", "2015-01", "de_novo"),
        ("wearables_diagnostics", "arrhythmia_detection", "2019-01", "k510"),  # Apple's predicate
        ("wearables_diagnostics", "wellness_tracking", "2015-01", "exempt"),
        ("implantables", "cardiac_rhythm", "2015-01", "pma"),
        ("samd", "radiology_triage", "2017-01", "de_novo"),
        ("samd", "radiology_triage", "2019-01", "k510"),  # Viz.ai's De Novo of Feb 2018
    ],
)
def test_us_routes_follow_the_data(
    loaded: LoadedData, category: str, use: str, month: str, route: str
) -> None:
    d = loaded.game_data
    state = medical_state(loaded, category=category, use=use, turn=month_to_turn(month))
    u = md.subcategory(d, category).use(use)  # type: ignore[union-attr]
    assert md.route_for(state, u, md.FDA, state.turn, d).key == route


def test_eu_routes_change_with_the_mdr_on_its_date(loaded: LoadedData) -> None:
    d = loaded.game_data
    u = md.subcategory(d, "implantables").use("cardiac_rhythm")  # type: ignore[union-attr]
    before = medical_state(loaded, category="implantables", turn=month_to_turn("2021-04"))
    after = medical_state(loaded, category="implantables", turn=month_to_turn("2021-05"))
    assert md.route_for(before, u, md.EU, before.turn, d).key == "ce_mdd"
    assert md.route_for(after, u, md.EU, after.turn, d).key == "ce_mdr"
    samd = md.subcategory(d, "samd").use("radiology_triage")  # type: ignore[union-attr]
    assert md.eu_class(samd, before.turn, d) == "I" and md.eu_class(samd, after.turn, d) == "IIa"


def test_review_times_are_drawn_inside_the_datas_window(loaded: LoadedData) -> None:
    """Every drawn review lies in the route's window by date, plus a request's months when one
    is asked (50.2); 510(k)s ask for more information about as often as the data says."""
    b, d = loaded.balance, loaded.game_data
    asked = 0
    for seed in range(1, 41):
        state = medical_state(loaded, turn=month_to_turn("2019-01"))
        product = state.product(PID)
        assert product is not None
        state, _, _ = routes.submit(state, product, md.FDA, RngFactory(seed), b, d)
        s = state.med_submissions[-1]
        route = md.file(d).route(s.route)
        lo, hi = route.window(state.turn)
        extra = route.more_info.months if s.more_info else (0, 0)
        assert lo + extra[0] <= s.due_turn - s.filed_turn <= hi + extra[1]
        asked += s.more_info
    assert 0.45 < asked / 40 < 0.85


def test_a_pma_needs_a_successful_pivotal_study(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = medical_state(loaded, category="implantables", use="cardiac_rhythm")
    product = state.product(PID)
    assert product is not None
    assert (
        routes.why_not(state, product, md.FDA, b, d)
        == "this route needs a successful pivotal study"
    )
    won = Study(1, 1, PID, "pivotal", 241, 0, 24, 100, 100, "succeeded", 24)
    state = replace(state, med_studies=(won,))
    assert routes.why_not(state, product, md.FDA, b, d) is None


def test_a_clearance_starts_the_regions_that_rely_on_it(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = medical_state(loaded)
    product = state.product(PID)
    assert product is not None
    state, _, _ = routes.submit(state, product, md.FDA, RngFactory(1), b, d)
    s = state.med_submissions[-1]
    for t in range(state.turn + 1, s.due_turn + 1):
        state, _ = routes.decisions_month(replace(state, turn=t), RngFactory(1), b, d)
    s = state.med_submissions[-1]
    if s.status == "cleared":
        relying = {c.region for c in state.med_clearances if c.authority.startswith(md.RELY)}
        assert {"latin_america", "oceania", "north_america"} <= relying


def test_a_samd_update_needs_a_new_filing_unless_a_pccp_was_approved(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = medical_state(loaded, category="samd", use="radiology_triage", cleared=("fda",))
    product = state.product(PID)
    assert product is not None
    grown = replace(product, feature_points=b.medical.review.update_features + 1)
    assert routes.update_needed(state, grown, b, d)
    with_plan = replace(state, med_designs=(replace(state.med_designs[0], pccp=True),))
    assert not routes.update_needed(with_plan, grown, b, d)


# --- 50.3 studies -----------------------------------------------------------------------------


def test_a_study_spends_its_cost_evenly_and_reads_out_at_its_month(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = medical_state(loaded, category="implantables", use="cardiac_rhythm")
    product = state.product(PID)
    assert product is not None
    state, _ = studies.start(state, product, "pivotal", 241, d)
    study = state.med_studies[-1]
    assert study.cost_cents == 241 * md.file(d).studies.cost_per_patient_cents["implantables"]
    spent = 0
    for t in range(state.turn, study.due_turn + 1):
        state, entries, _ = studies.month(replace(state, turn=t), RngFactory(3), b, d)
        spent += sum(line.amount for e in entries for line in e.lines if line.amount > 0)
    done = state.med_studies[-1]
    assert done.status in ("succeeded", "failed") and done.read_turn == study.due_turn
    redesign = 0 if done.status == "succeeded" else round(study.cost_cents * 0.2)
    assert abs(spent - study.cost_cents - redesign) <= 1
    design = md.design_of(state, PID)
    assert design is not None
    if done.status == "succeeded":
        assert design.evidence == pytest.approx(0.6)
    else:
        assert design.redesign_until == study.due_turn + b.medical.study.redesign_months


def test_study_success_rate_follows_its_chance(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    wins = 0
    for seed in range(1, 201):
        state = medical_state(loaded, category="implantables", use="cardiac_rhythm")
        product = state.product(PID)
        assert product is not None
        study = Study(seed, 1, PID, "pivotal", 200, state.turn - 24, state.turn, 1000, 1000)
        state = replace(state, med_studies=(study,))
        state, _, _ = studies.month(state, RngFactory(seed), b, d)
        wins += state.med_studies[0].status == "succeeded"
    p = studies.chance(state, product, "pivotal", b, d)
    assert abs(wins / 200 - p) < 0.1


# --- 50.4 coverage and adoption; the gate -----------------------------------------------------


def test_an_uncleared_device_cannot_win_customers_and_coverage_lifts_the_gate(
    loaded: LoadedData,
) -> None:
    b, d = loaded.balance, loaded.game_data
    state = medical_state(loaded)
    product = state.product(PID)
    assert product is not None
    assert gate.share(state, product, "north_america", b, d) == 0.0
    state = medical_state(loaded, cleared=("fda",))
    product = state.product(PID)
    assert product is not None
    us = md.part_share(d, md.regulator(d, md.FDA))
    floor = b.medical.adoption.floor
    no_cov = b.medical.coverage.no_coverage_share
    assert gate.share(state, product, "north_america", b, d) == pytest.approx(us * no_cov * floor)
    covered = replace(
        state, med_coverage=(coverage.Coverage(PID, "north_america", 0, "covered", 0, 0),)
    )
    assert gate.share(covered, product, "north_america", b, d) == pytest.approx(us * floor)
    access = gate.merge({}, state, b, d)
    assert access[(PID, "europe")].blocked == 1.0


def test_evidence_and_training_speed_adoption(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data

    def months_to(share: float, evidence: float, training: int) -> int:
        state = medical_state(loaded, cleared=("fda",))
        design = replace(state.med_designs[0], evidence=evidence, training_cents=training)
        state = replace(state, med_designs=(design,))
        for m in range(1, 400):
            state, _, _ = coverage.month(replace(state, turn=state.turn + 1), RngFactory(1), b, d)
            if coverage.adoption(state, PID, "north_america") >= share:
                return m
        return 400

    base = months_to(0.3, 0.0, 0)
    assert months_to(0.3, 0.6, 0) < base - 24
    assert months_to(0.3, 0.0, b.medical.adoption.training_full_cents) < base


# --- 50.5 quality, inspections and recalls ----------------------------------------------------


def test_high_quality_plants_recall_less(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = medical_state(loaded, cleared=("fda",), customers=50.0)
    product = state.product(PID)
    assert product is not None
    low = quality.recall_chance(state, product, b, d)
    plantless = md.file(d).quality.levels[md.file(d).quality.contract_level].defect
    assert low > 0
    for level in ("low", "high"):
        mult = md.file(d).quality.levels[level].defect
        assert mult != plantless
    assert md.file(d).quality.levels["high"].defect <= 0.4 * md.file(d).quality.levels["low"].defect


def test_a_class_i_recall_costs_stops_sales_and_queues_a_critical_event(
    loaded: LoadedData,
) -> None:
    b, d = loaded.balance, loaded.game_data
    state = medical_state(loaded, cleared=("fda",), customers=40.0)
    product = state.product(PID)
    assert product is not None
    state, entries, _, rec = quality.recall(state, product, "I", False, b, d)
    assert rec.klass == "I" and rec.units == 40
    assert sum(line.amount for e in entries for line in e.lines if line.account == RECALLS) > 0
    assert gate.share(state, product, "north_america", b, d) == 0.0
    state = quality.queue_class_i(state, product)
    assert state.queued[-1].template_id == quality.CLASS_I_RECALL
    caught = medical_state(loaded, cleared=("fda",), customers=40.0)
    _, _, _, early = quality.recall(caught, product, "I", True, b, d)
    assert early.klass == "II"


def test_a_consent_decree_stops_sales_in_its_part(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = medical_state(loaded, cleared=("fda",), customers=10.0)
    product = state.product(PID)
    assert product is not None
    state, entries, _ = quality.inspect(state, 1, md.FDA, 0.0, b, d)
    assert state.med_inspections[-1].finding == "consent_decree"
    assert gate.share(state, product, "north_america", b, d) == 0.0
    assert entries and entries[0].lines[0].amount > 0


def test_consumables_book_recurring_revenue_for_installed_units(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = medical_state(loaded, cleared=("fda",), customers=10.0)
    entries = [e for e in recurring.recurring_month(state, b, d) if e.company_id == 1]
    revenue = -sum(
        line.amount for e in entries for line in e.lines if line.account == MEDICAL_RECURRING
    )
    assert revenue == 10 * md.file(d).subcategory("surgical_robotics").consumables_cents  # type: ignore[union-attr]


# --- 50.6 target 1: a company without medical devices draws nothing ---------------------------


def test_no_design_means_no_medical_month(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = medical_state(loaded)
    bare = replace(state, med_designs=())

    class Exploding(RngFactory):
        def stream(self, turn: int, name: str, *key: int):  # type: ignore[no-untyped-def,override]
            assert name != "medical", "a medical draw without a medical device"
            return super().stream(turn, name, *key)

    out, entries, logs = medical_month(bare, Exploding(1), b, d)
    assert out is bare and entries == [] and logs == []


# --- 50.7 the hidden-value guarantee ----------------------------------------------------------


def test_no_draw_reaches_the_api_or_a_prompt_before_it_happens(loaded: LoadedData) -> None:
    """The Medical screen shows routes' ranges, studies' designs and chance ranges: never a
    submission's drawn month or request, a coverage decision's month, a study's chance, or any
    future inspection or recall."""
    from tst.api.medical_views import medical_out

    b, d = loaded.balance, loaded.game_data
    state = medical_state(loaded, category="implantables", use="cardiac_rhythm")
    product = state.product(PID)
    assert product is not None
    won = Study(1, 1, PID, "pivotal", 241, 0, 24, 100, 100, "succeeded", 24)
    state = replace(state, med_studies=(won,))
    state, _, _ = routes.submit(state, product, md.FDA, RngFactory(1), b, d)
    state, _ = studies.start(state, product, "post_market", 500, d)
    out = medical_out(state, loaded).model_dump_json()
    for hidden in ("due_turn", 'more_info"', 'chance"', "draw", "strictness"):
        assert hidden not in out, hidden
    p = studies.chance(state, product, "post_market", b, d)
    assert f"{p:.4f}" not in out
    sub = state.med_submissions[-1]
    from tst.sim.calendar import format_turn

    assert format_turn(sub.due_turn) not in out
    lo, hi = routes.shown_range(state, md.subcategory(d, "implantables").use("cardiac_rhythm"),  # type: ignore[union-attr]
                                md.file(d).route(sub.route), False, b, d)  # fmt: skip
    assert f"{lo}-{hi} months" in out


def test_designs_persist_through_their_dataclasses(loaded: LoadedData) -> None:
    from tst.db.mna_io import from_data, to_data

    d = Design(PID, "robotic_surgery", True, 500, True, 0.6, 12.0, 30)
    assert from_data(Design, to_data(d)) == d
    c = Clearance(PID, "rely:oceania", "oceania", 12, "reliance", 3)
    assert from_data(Clearance, to_data(c)) == c
