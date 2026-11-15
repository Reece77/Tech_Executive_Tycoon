"""M34 (docs/formulas.md 48): regulation.yaml's history and sources; designations and the
year-ahead warning (48.1); duties changing a designated platform's rules on their dates (48.2);
investigations' causes, stages, settlements, fines and remedies (48.3); the hidden-value guarantee
(48.6); and the structural order's preconditions and warnings (48.4)."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from tests.platform_helpers import HISTORY_END, START
from tests.regulation_helpers import REGION, owner_state
from tst.api.regulation_views import regulation_out
from tst.loader import LoadedData
from tst.sim.events.models import GameEvent
from tst.sim.ledger import FINES
from tst.sim.platforms import data as pdata
from tst.sim.regulation import answers, cases, designate, duties, structural
from tst.sim.regulation import data as rdata
from tst.sim.regulation.measure import View
from tst.sim.regulation.models import Case, Watch
from tst.sim.regulation.month import regulation_month
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

DATA = Path(__file__).resolve().parents[2] / "data"
DECEMBER_2026 = START + 11
YEAR = 12
BIG = 10**13  # $100B a month: every money threshold met
KEYS = (
    r"\s+(users_share|turnover_b|value_b|comply_months|duties|in_force|first_designations|"
    r"max_fine_share|repeat_fine_share|periodic_share):"
)


def _view(state: GameState, users: float, region: str = REGION, month: int = BIG) -> View:
    me = state.player.id
    return View(
        home=region,
        category_shares={("devices", region): {me: users}},
        users={(me, region): users},
        region_month={(me, region): month},
        world_year={me: month * YEAR},
    )


# --- 48.5 target 1: the data, its sources, and history ----------------------------------------


def test_every_value_in_regulation_yaml_has_a_source() -> None:
    """Every designation, case stage and regulator carries a source; every regime value and
    every regulator's strictness a comment (a URL or A)."""
    text = (DATA / "regulation.yaml").read_text(encoding="utf-8")
    block = text.split("regimes:", 1)[1].split("designations:", 1)[0]
    for line in block.splitlines():
        key = re.match(
            r"\s+(users_share|turnover_b|value_b|comply_months|duties|in_force|"
            r"first_designations|max_fine_share|repeat_fine_share|periodic_share):",
            line,
        )
        if key and not line.strip().endswith("null"):
            assert "#" in line, f"no source for: {line.strip()}"
    for line in text.split("regulators:", 1)[1].split("regimes:", 1)[0].splitlines():
        if re.match(r"\s+(strictness|structural|part):", line):
            assert "#" in line, f"no source for: {line.strip()}"


def test_history_designations_follow_the_data(loaded: LoadedData) -> None:
    state, _, _ = owner_state(loaded)
    d = loaded.game_data
    apple = next(c.id for c in state.companies if c.name == "Apple")
    sept_2023 = 164  # (2023 - 2010) x 12 + 8
    assert rdata.designated_in_history(state, d, apple, "dma", sept_2023) is not None
    assert rdata.designated_in_history(state, d, apple, "dma", sept_2023 - 1) is None
    assert rdata.designated_in_history(state, d, apple, "jp_msca", 182) is not None  # Mar 2025
    labels = {h.label for h in rdata.history_designations(state, d, HISTORY_END)}
    assert {"Apple", "Microsoft", "Meta", "Alphabet", "Amazon", "ByteDance", "Booking"} <= labels


def test_history_cases_fines_and_rulings_follow_the_data(loaded: LoadedData) -> None:
    d, b = loaded.game_data, loaded.balance
    cases_by_key = {c.key: c for c in rdata.file(d).cases}
    shopping = cases_by_key["eu_google_shopping"]
    assert shopping.fine == 2_420_000_000 and shopping.currency == "EUR"
    assert [s.at for s in shopping.stages] == ["2010-11", "2015-04", "2017-06", "2024-09"]
    android = cases_by_key["eu_google_android"]
    assert (android.fine, android.final) == (4_340_000_000, 4_125_000_000)
    assert cases_by_key["eu_google_adsense"].final == 0  # annulled in 2024
    assert cases_by_key["eu_apple_dma"].fine == 500_000_000
    assert cases_by_key["eu_meta_dma"].fine == 200_000_000
    assert cases_by_key["us_ftc_meta"].outcome == "dismissed"
    # the screen shows a case's later steps only from their month (48.6)
    state, _, _ = owner_state(loaded)
    state = replace(state, turn=shopping.stages[1].turn)
    out = regulation_out(state, loaded)
    row = next(c for c in out.cases if c.key == "eu_google_shopping")
    assert [s.stage for s in row.steps] == ["inquiry", "objections"] and row.fine_cents == 0
    assert row.outcome == "open"
    state = replace(state, turn=HISTORY_END)
    row = next(c for c in regulation_out(state, loaded).cases if c.key == "eu_google_shopping")
    assert row.fine_cents == rdata.usd_cents(2_420_000_000, "EUR", b) and row.outcome == "fined"


def test_nothing_runs_before_the_start(loaded: LoadedData) -> None:
    state, balances, _ = owner_state(loaded, users=0.9, turn=HISTORY_END)
    after, entries, logs = regulation_month(
        state, RngFactory(1), balances, loaded.balance, loaded.game_data
    )
    assert after is state and entries == [] and logs == []


# --- 48.1 designations ----------------------------------------------------------------------


def test_a_designation_warning_arrives_a_year_ahead(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _, _ = owner_state(loaded, turn=DECEMBER_2026)
    me = state.player.id
    state, logs = designate.december(state, _view(state, 0.5), None, b, d)
    assert any(w.regime == "dma" and w.company_id == me for w in state.designation_warnings)
    assert not any(g.regime == "dma" for g in state.designations)
    assert any(x.template == "regulation_designation_warning" for x in logs)
    state = replace(state, turn=DECEMBER_2026 + YEAR)
    state, logs = designate.december(state, _view(state, 0.5), None, b, d)
    g = next(g for g in state.designations if g.regime == "dma" and g.company_id == me)
    assert g.from_turn == DECEMBER_2026 + YEAR and g.duties_from == g.from_turn + 6
    warned = min(w.turn for w in state.designation_warnings if w.regime == "dma")
    assert g.from_turn - warned >= YEAR


def test_near_thresholds_warn_and_far_ones_do_not(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _, _ = owner_state(loaded, turn=DECEMBER_2026)
    near, _ = designate.december(state, _view(state, 0.085), None, b, d)  # 85% of the DMA's 10%
    assert any(w.regime == "dma" for w in near.designation_warnings)
    far, logs = designate.december(state, _view(state, 0.05), None, b, d)
    assert not any(w.regime == "dma" for w in far.designation_warnings)
    assert not far.designations and not [x for x in logs if "dma" in x.message.lower()]


def test_the_test_runs_only_in_december(loaded: LoadedData) -> None:
    state, _, _ = owner_state(loaded, turn=START)
    after, logs = designate.december(
        state, _view(state, 0.9), None, loaded.balance, loaded.game_data
    )
    assert after is state and logs == []


# --- 48.2 duties ----------------------------------------------------------------------------


def test_a_designated_platforms_duties_change_its_rules_on_their_dates(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _, platform = owner_state(loaded, turn=DECEMBER_2026, self_pref="strong")
    me = state.player.id
    state, _ = designate.december(state, _view(state, 0.5), None, b, d)
    state = replace(state, turn=DECEMBER_2026 + YEAR)
    state, _ = designate.december(state, _view(state, 0.5), None, b, d)
    g = next(x for x in state.designations if x.regime == "dma")
    before = replace(state, turn=g.duties_from - 1)
    before, _ = duties.start_month(before, b, d)
    p = before.platform(platform.id)
    assert p is not None and p.self_pref == "strong" and not p.regulated
    assert pdata.allows_side_loading(d, p, REGION, before.turn) == 0.0
    on = replace(state, turn=g.duties_from)
    on, logs = duties.start_month(on, b, d)
    p = on.platform(platform.id)
    assert p is not None and p.self_pref == "off" and not p.anti_steering
    eu = d.platforms.part_share(REGION, "eu") if d.platforms else 0.0
    assert pdata.allows_side_loading(d, p, REGION, on.turn) == pytest.approx(eu)
    sched = pdata.schedule(p, REGION, on.turn, b, d)
    assert any(part == "eu" and rate == pytest.approx(0.26) for part, _, rate in sched.regulated)
    dma = {x.kind for x in on.duties if x.company_id == me and x.regime == "dma"}
    assert dma == set(rdata.file(d).regime("dma").duties)
    assert any(x.template == "regulation_duty" for x in logs)
    # compliance work: $20M a duty a year, monthly (the UK's regime designated it too)
    n = sum(1 for x in on.duties if x.company_id == me and x.from_turn <= on.turn)
    entry = next(e for e in duties.compliance_entries(on, b) if e.company_id == me)
    assert n >= len(dma) and entry.lines[0].amount == n * (b.regulation.compliance_cents // 12)


def test_turning_self_preferencing_back_on_is_non_compliance(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _, platform = owner_state(loaded, turn=START + 18)
    me = state.player.id
    eu = rdata.file(d).regulator("eu_commission")
    state = duties.add_duty(state, me, "eu_commission", "no_self_preferencing", state.turn,
                            "designation", d, b)  # fmt: skip
    assert not duties.noncompliant(state, me, eu)
    pref = replace(state.platform(platform.id), self_pref="strong")  # type: ignore[arg-type]
    state = replace(state, platforms=tuple(pref if p.id == pref.id else p for p in state.platforms))
    assert duties.breaches(state, me, eu) == ["no_self_preferencing"]
    found = cases.causes(state, me, eu, _view(state, 0.5), b, d)
    assert "noncompliance" in found and "self_preferencing" in found


# --- 48.3 investigations --------------------------------------------------------------------


def test_no_cause_means_no_chance_and_causes_raise_it(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _, platform = owner_state(loaded, turn=START + 6)
    me = state.player.id
    eu = rdata.file(d).regulator("eu_commission")
    assert cases.chance(state, me, eu, _view(state, 0.2), b, d) == 0.0  # under 40%
    dominant = cases.chance(state, me, eu, _view(state, 0.6), b, d)
    assert dominant > 0
    small = cases.chance(state, me, eu, _view(state, 0.6, month=10**8), b, d)  # $12M a year
    assert small == 0.0
    pref = replace(state.platform(platform.id), self_pref="strong")  # type: ignore[arg-type]
    worse = replace(state, platforms=tuple(pref if p.id == pref.id else p for p in state.platforms))
    assert cases.chance(worse, me, eu, _view(worse, 0.6), b, d) > dominant


def _opened(loaded: LoadedData, turn: int = START + 6) -> tuple[GameState, Case]:
    """A dominant player with an open EU inquiry (opened with a draw forced to succeed)."""
    b, d = loaded.balance, loaded.game_data
    state, _, _ = owner_state(loaded, turn=turn)
    v = _view(state, 0.9)
    for seed in range(1, 400):
        after, _ = cases.openings(state, RngFactory(seed), v, b, d)
        case = cases.open_case(after, state.player.id, "eu_commission")
        if case is not None:
            return after, case
    raise AssertionError("no inquiry opened in 400 seeds")


def test_an_inquiry_is_queued_to_the_player_with_its_stage_window(loaded: LoadedData) -> None:
    state, case = _opened(loaded)
    assert case.stage == "inquiry" and 6 <= case.due_turn - case.opened_turn <= 12
    assert case.asked_template == cases.INQUIRY and case.asked_turn == state.turn + 1
    assert any(q.template_id == cases.INQUIRY for q in state.queued)


def test_settling_at_the_objections_ends_it_with_a_commitment_and_a_smaller_fine(
    loaded: LoadedData,
) -> None:
    b, d = loaded.balance, loaded.game_data
    state, case = _opened(loaded)
    case = replace(case, stage="objections", asked_turn=None)
    state = cases.with_case(state, case)
    state = replace(state, reg_turnover=((state.player.id, (10**11,) * 12),))
    after, entries, _ = cases.settle(state, case, b, d)
    closed = next(c for c in after.reg_cases if c.id == case.id)
    assert closed.stage == "closed" and closed.outcome == "settled"
    assert any(x.source == "commitment" and x.case_id == case.id for x in after.duties)
    fine = sum(line.amount for e in entries for line in e.lines if line.account == FINES)
    turnover = 12 * 10**11
    lo, hi = b.regulation.fine.share
    assert fine == round(round(turnover * (lo + (hi - lo) * 0.5)) * b.regulation.fine.settle_share)


def test_a_ruling_against_posts_a_fine_within_the_cap_and_a_remedy(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, case = _opened(loaded)
    state = replace(state, reg_turnover=((state.player.id, (10**11,) * 12),))
    case = replace(case, stage="objections", contested=True, due_turn=state.turn, asked_turn=None)
    state = cases.with_case(state, case)
    for seed in range(1, 200):
        after, entries, _ = cases.rule(state, case, RngFactory(seed), b, d)
        ruled = next(c for c in after.reg_cases if c.id == case.id)
        if ruled.outcome == "fined":
            break
    else:
        raise AssertionError("no ruling against in 200 seeds")
    fine = sum(line.amount for e in entries for line in e.lines if line.account == FINES)
    assert fine == ruled.fine_cents > 0
    assert fine <= 0.10 * 12 * 10**11
    assert any(x.source == "remedy" and x.case_id == case.id for x in after.duties)
    assert ruled.asked_template == cases.RULING


def test_rivals_settle_or_contest_by_personality(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _, _ = owner_state(loaded, turn=START + 6)
    rival = next(c for c in state.rivals() if c.personality == "cost_leader")
    fighter = next(c for c in state.rivals() if c.personality == "aggressive")
    for company, settles in ((rival, True), (fighter, False)):
        case = Case(
            id=cases.next_case_id(state), regulator="eu_commission", company_id=company.id,
            conduct="dominance", market="consumer_apps", opened_turn=state.turn,
            stage="objections", stage_turn=state.turn, due_turn=state.turn + 6,
            remedy="interoperability",
        )  # fmt: skip
        after = cases.with_case(state, case)
        after, _, _ = cases.rival_answer(after, case, "objections", RngFactory(1), b, d)
        got = next(c for c in after.reg_cases if c.id == case.id)
        assert (got.outcome == "settled") is settles
        assert got.contested is not settles


# --- 48.6 the hidden-value guarantee ----------------------------------------------------------


def test_no_investigation_chance_or_draw_reaches_the_api_or_a_prompt(loaded: LoadedData) -> None:
    """The screen and the event's placeholders show stages, windows and ranges only: never a
    case's drawn end month, an opening's chance, an outcome's chance or a strictness index."""
    b, d = loaded.balance, loaded.game_data
    state, case = _opened(loaded)
    out = regulation_out(state, loaded).model_dump()
    text = json.dumps(out)
    for hidden in ("due_turn", "chance", "strictness", "draw"):
        assert hidden not in text
    row = next(c for c in out["cases"] if c["id"] == case.id)
    assert row["stage_window"] == "6-12 months"
    assert format_month(case.due_turn) not in json.dumps(row)
    shown = cases.chance(state, state.player.id, rdata.file(d).regulator("eu_commission"),
                         _view(state, 0.9), b, d)  # fmt: skip
    assert f"{shown:.4f}" not in text and f"{shown:.1%}" not in text
    event = GameEvent(
        id=1, company_id=state.player.id, turn=state.turn + 1, template_id=cases.OBJECTIONS,
        category="regulation", severity="critical", trigger="regulation", strength=1.0,
    )  # fmt: skip
    state = cases.with_case(state, replace(case, asked_template=cases.OBJECTIONS))
    state = replace(state, events=(*state.events, event))
    names = answers.event_names(state, d, b, event)
    lo, hi = b.regulation.odds.ruling_against
    assert names["odds"] == f"{lo:.0%}-{hi:.0%}"
    assert set(names) == {"regulator", "case", "market", "fine", "odds", "unit"}


def format_month(turn: int) -> str:
    from tst.sim.calendar import format_turn

    return format_turn(turn)


# --- 48.4 structural remedies ---------------------------------------------------------------


def _ruled_and_breached(loaded: LoadedData, turn: int) -> tuple[GameState, Case]:
    """A ruling against the player in devices, its no-self-preferencing remedy now breached."""
    b, d = loaded.balance, loaded.game_data
    state, _, platform = owner_state(loaded, turn=turn, self_pref="strong")
    me = state.player.id
    case = Case(
        id=1, regulator="eu_commission", company_id=me, conduct="self_preferencing",
        market="devices", opened_turn=turn - 20, stage="closed", stage_turn=turn - 2,
        due_turn=turn - 2, outcome="fined", remedy="no_self_preferencing", ruled_turn=turn - 2,
        closed_turn=turn - 2,
    )  # fmt: skip
    state = cases.with_case(state, case)
    state = replace(state, duties=())
    state = duties.add_duty(state, me, "eu_commission", "no_self_preferencing", turn - 2,
                            "remedy", d, b, case_id=1)  # fmt: skip
    pref = replace(state.platform(platform.id), self_pref="strong")  # type: ignore[arg-type]
    state = replace(state, platforms=tuple(pref if p.id == pref.id else p for p in state.platforms))
    return state, case


def test_warning_signs_begin_build_and_end_with_the_preconditions(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _ = _ruled_and_breached(loaded, START + 24)
    eu = rdata.file(d).regulator("eu_commission")
    assert structural.conditions(state, state.player.id, eu, "devices", b, d)
    state, logs = structural.watches_month(state, b, d)
    assert [s for s, _ in state.reg_watches[0].signs] == ["press"]
    assert logs[0].template == "regulation_warning_press"
    every = b.regulation.structural.warning_every
    for _ in range(3):
        state = replace(state, turn=state.turn + every)
        state, _ = structural.watches_month(state, b, d)
    assert [s for s, _ in state.reg_watches[0].signs] == ["press", "report", "political", "board"]
    fixed = replace(
        state,
        platforms=tuple(
            replace(p, self_pref="off") if not p.historical else p for p in state.platforms
        ),
    )
    fixed, _ = structural.watches_month(fixed, b, d)
    assert fixed.reg_watches == ()


def test_no_order_without_three_years_of_warnings(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _ = _ruled_and_breached(loaded, START + 24)
    me = state.player.id
    eu = rdata.file(d).regulator("eu_commission")
    new = Case(
        id=2, regulator="eu_commission", company_id=me, conduct="noncompliance", market="devices",
        opened_turn=state.turn, stage="objections", stage_turn=state.turn, due_turn=state.turn,
        remedy="no_self_preferencing",
    )  # fmt: skip
    state = cases.with_case(state, new)
    watched = replace(state, reg_watches=(Watch(me, "eu_commission", "devices", state.turn - 35,
                                                (("press", state.turn - 35),)),))  # fmt: skip
    assert not structural.may_order(watched, new, eu, b, d)
    old = replace(state, reg_watches=(Watch(me, "eu_commission", "devices", state.turn - 36,
                                            (("press", state.turn - 36),)),))  # fmt: skip
    assert structural.may_order(old, new, eu, b, d)
    order_state, _ = structural.order(old, new, eu, b, d)
    o = order_state.reg_orders[0]
    assert o.unit_kind == "platform" and o.deadline_turn == o.ordered_turn + 24
    assert o.ordered_turn - o.warned_from >= 36
    us = rdata.file(d).regulator("jftc")  # its law allows no structural remedy
    assert not structural.conditions(old, me, us, "devices", b, d)
