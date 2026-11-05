"""M14b press (docs/formulas.md 29): the 29.8 worked examples; moments' cap, stakes and tones;
each promise kind kept and broken, judged on displayed values only (a differential test);
credibility's drift and effects."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.conftest import DATA_DIR
from tests.helpers import fresh_game, make_person, with_employee, with_product
from tests.unit.test_m13_public import LISTED
from tst.loader import load_all
from tst.sim.events.models import GameEvent
from tst.sim.press import moments, promises
from tst.sim.press.models import Credibility, PressMoment, Promise
from tst.sim.press.shares import shown_quality
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    credibility_of,
    reach_stage,
    with_company,
    with_credibility,
    with_press_moment,
    with_promise,
)
from tst.sim.state import with_product as put_product

LOADED = load_all(DATA_DIR)
B, D = LOADED.balance, LOADED.game_data
CID = 1


def _brand_mods(state: GameState) -> list[float]:
    return [m.value_pct for m in state.modifiers if m.stat == "brand_target"]


def scaleup(staff: int = 10) -> GameState:
    state = fresh_game(LOADED)
    for pid in range(2, 2 + staff):
        state = with_employee(LOADED, state, make_person(LOADED, pid), 9_000_000)
    return with_company(state, reach_stage(state.player, 3, 0))


# --- 29.8 worked examples ----------------------------------------------------------------------


def test_kept_promise_listed_example() -> None:
    """a = 1.5, ambition 0.4, credibility 60: brand target +4 x 1.5 x 1.4 x 1.1 = +9.2 for 12
    months; credibility +7.5."""
    state = with_credibility(LISTED, Credibility(CID, 60.0))
    assert moments.audience(state, CID, B) == 1.5
    p = Promise(1, CID, "ship", state.turn, state.turn + 6, ambition=0.4, audience=1.5)
    state = with_promise(state, p)
    out, logs = promises.resolve(state, p, "kept", B, D)
    (mod,) = [m for m in out.modifiers if m.stat == "brand_target"]
    assert mod.value_pct == pytest.approx(9.24)
    assert mod.end_turn - mod.start_turn == 12
    assert credibility_of(out, CID).value == pytest.approx(67.5)  # type: ignore[union-attr]
    assert logs[0].template == "promise_kept"


def test_broken_no_layoffs_stage_3_example() -> None:
    """a = 1.0: brand target -8, credibility -10, every employee's morale -5."""
    state = scaleup()
    assert moments.audience(state, CID, B) == 1.0
    p = Promise(1, CID, "no_layoffs", state.turn, state.turn + 12, audience=1.0)
    state = with_promise(state, p)
    morale = {e.person_id: state.person_state(e.person_id).morale for e in state.staff(CID)}
    out, logs = promises.resolve(state, p, "broken", B, D, reminder_in=2)
    assert _brand_mods(out) == [-8]
    assert credibility_of(out, CID).value == pytest.approx(40)  # type: ignore[union-attr]
    founder = out.founder_of(CID)
    for pid, before in morale.items():
        if founder is not None and pid == founder.id:
            continue
        assert out.person_state(pid).morale == pytest.approx(before - 5)  # type: ignore[operator]
    reminder = [m for m in out.press_moments if m.trigger == "reminder"]
    assert reminder and dict(reminder[0].facts)["due_turn"] == state.turn + 2
    assert logs[0].template == "promise_broken"


# --- Moments (29.1) --------------------------------------------------------------------------


def test_queue_cap_and_stakes() -> None:
    state = scaleup()
    for trigger in ("launch", "jab", "breach", "earnings"):
        state = moments.queue_moment(state, CID, trigger)
    state = moments.schedule(state, B)
    queued = [m for m in state.press_moments if m.status == "queued"]
    skipped = [m for m in state.press_moments if m.status == "skipped"]
    assert [m.trigger for m in queued] == ["breach"]  # one a month, highest stakes
    assert {m.trigger for m in skipped} == {"launch", "jab", "earnings"}
    assert [q.template_id for q in state.queued if not q.done] == ["press_breach"]


def test_quarter_cap() -> None:
    state = replace(scaleup(), turn=11)  # next month (12) starts a quarter
    shown = []
    for t in (11, 12, 13):
        state = replace(state, turn=t)
        state = moments.queue_moment(state, CID, "launch")
        state = moments.schedule(state, B)
        shown += [
            m.event_turn
            for m in state.press_moments
            if m.status == "queued" and m.event_turn not in shown
        ]
    assert sorted(set(shown)) == [12, 13]  # the third month of the quarter gets none
    assert any(m.status == "skipped" for m in state.press_moments)


def _event(state: GameState, turn: int) -> GameEvent:
    return GameEvent(1, CID, turn, "press_launch", "press", "major", "press", 1.0)


def test_tones() -> None:
    state = scaleup()
    a = moments.audience(state, CID, B)
    for tone, mods, cred in (("bold", [3 * a], 50), ("measured", [1 * a], 50), ("deflect", [], 48)):
        s = moments.queue_moment(state, CID, "launch")
        s = moments.schedule(s, B)
        m = next(x for x in s.press_moments if x.status == "queued")
        out, _ = moments.apply_tone(s, _event(s, m.event_turn), tone, B, D)  # type: ignore[arg-type]
        assert _brand_mods(out) == pytest.approx(mods)
        assert moments.credibility(out, CID, B) == pytest.approx(cred)
        assert next(x for x in out.press_moments if x.id == m.id).tone == tone


def test_bold_backfire_when_share_falls() -> None:
    state = with_product(scaleup(), customers={"smb": 100.0})
    pid = state.company_products(CID)[0].id
    m = PressMoment(
        1, CID, "launch", 0, "answered", 1, pid, tone="bold", answered_turn=0, share_bp=9000
    )
    state = with_press_moment(state, m)
    out = moments.backfires(replace(state, turn=2), B)
    assert moments.credibility(out, CID, B) == pytest.approx(50 - 6)
    out2 = moments.backfires(replace(out, turn=3), B)  # once only
    assert moments.credibility(out2, CID, B) == pytest.approx(44)


def test_credibility_drift_and_hiring_appeal() -> None:
    state = with_credibility(scaleup(), Credibility(CID, 80.0))
    assert moments.hiring_appeal(state, CID, B) == pytest.approx(0.03)
    state = moments.drift_credibility(state, B)
    assert credibility_of(state, CID).value == 79  # type: ignore[union-attr]
    high = with_credibility(state, Credibility(CID, 100.0))
    assert moments.hiring_appeal(high, CID, B) == pytest.approx(0.05)
    assert moments.cred_factor(high, CID, B) == pytest.approx(1.5)


# --- Promises (29.2) -------------------------------------------------------------------------


def _answered(state: GameState) -> GameState:
    m = PressMoment(
        99,
        CID,
        "launch",
        state.turn,
        "answered",
        state.turn,
        tone="measured",
        answered_turn=state.turn,
    )
    return with_press_moment(state, m)


def test_promise_needs_a_press_moment_and_a_cap() -> None:
    state = with_product(scaleup(), status="in_development")
    pid = state.company_products(CID)[0].id
    with pytest.raises(Exception):  # noqa: B017 - no moment answered this month
        promises.make(state, CID, "ship", B, D, product_id=pid, months=6)
    state = _answered(state)
    state, p = promises.make(state, CID, "ship", B, D, product_id=pid, months=6)
    assert p.deadline_turn == state.turn + 6
    assert p.ambition == pytest.approx((18 - 6) / 15)
    with pytest.raises(Exception):  # noqa: B017 - one promise a moment
        promises.make(state, CID, "no_layoffs", B, D)


def _promise(state: GameState, kind: str, **kw: object) -> tuple[GameState, Promise]:
    return promises.make(_answered(state), CID, kind, B, D, **kw)  # type: ignore[arg-type]


def test_ship_kept_and_broken() -> None:
    state = with_product(scaleup(), status="in_development")
    pid = state.company_products(CID)[0].id
    state, p = _promise(state, "ship", product_id=pid, months=6)
    assert promises.verdict(state, p) is None
    live = put_product(state, replace(state.product(pid), status="live"))  # type: ignore[arg-type]
    assert promises.verdict(live, p) == "kept"
    late = replace(state, turn=p.deadline_turn)
    assert promises.verdict(late, p) == "broken"


def _rival_product(state: GameState) -> int:
    product = state.company_products(CID)[0]
    return next(
        p.id for p in state.products if p.company_id != CID and p.category == product.category
    )


def test_beat_judged_on_displayed_quality_only() -> None:
    """Differential: two saves with the same displayed quality (41) but different true
    quality (41.2 and 41.45) against a rival at 41.3 judge Beat the same way."""
    base = with_product(scaleup(), quality=41.2)
    pid = base.company_products(CID)[0].id
    rid = _rival_product(base)
    base = put_product(base, replace(base.product(rid), quality=41.3))  # type: ignore[arg-type]
    base, p = _promise(base, "beat", product_id=pid, rival_product_id=rid, months=6)
    other = put_product(base, replace(base.product(pid), quality=41.45))  # type: ignore[arg-type]
    assert shown_quality(base, pid) == shown_quality(other, pid) == 41
    due_a = replace(base, turn=p.deadline_turn)
    due_b = replace(other, turn=p.deadline_turn)
    assert promises.verdict(due_a, p) == promises.verdict(due_b, p) == "broken"
    ahead = put_product(due_a, replace(due_a.product(pid), quality=43.0))  # type: ignore[arg-type]
    assert promises.verdict(ahead, p) == "kept"


def test_research_kept_and_broken() -> None:
    from tst.sim.research.models import ResearchLead
    from tst.sim.state import with_research_lead

    state = with_research_lead(scaleup(), ResearchLead(CID, "ai", 10.0))
    state, p = _promise(state, "research", domain="ai", level=15, months=12)
    assert promises.verdict(state, p) is None
    reached = with_research_lead(state, ResearchLead(CID, "ai", 15.2))
    assert promises.verdict(reached, p) == "kept"
    assert promises.verdict(replace(state, turn=p.deadline_turn), p) == "broken"


def test_no_layoffs_kept_and_broken_by_a_firing() -> None:
    state = scaleup()
    state, p = _promise(state, "no_layoffs")
    assert promises.verdict(replace(state, turn=p.deadline_turn), p) == "kept"
    founder = state.founder_of(CID)
    assert founder is not None
    out = _fire(state, founder.id, 2)
    broken = next(x for x in out.new_state.promises if x.id == p.id)
    assert broken.status == "broken"
    assert any(i.template == "promise_broken" for i in out.log_items)


def test_no_price_rise_kept_and_broken() -> None:
    from tst.sim.state import with_product_segment

    state = with_product(scaleup(), prices={"smb": 4000})
    pid = state.company_products(CID)[0].id
    state, p = _promise(state, "no_price_rise", product_id=pid)
    seg = state.product_segment(pid, "smb")
    assert seg is not None
    cut = with_product_segment(state, replace(seg, price_cents=3500))
    assert promises.verdict(cut, p) is None
    rise = with_product_segment(state, replace(seg, price_cents=4500))
    assert promises.verdict(rise, p) == "broken"
    assert promises.verdict(replace(cut, turn=p.deadline_turn), p) == "kept"


def test_layoffs_moment_at_ten_percent() -> None:
    state = scaleup(staff=10)
    founder = state.founder_of(CID)
    assert founder is not None
    out = _fire(state, founder.id, 2)
    assert [m.trigger for m in out.new_state.press_moments] == []  # 1 of 11 is under 10%
    out = _fire(out.new_state, founder.id, 3)
    assert [m.trigger for m in out.new_state.press_moments] == ["layoffs"]


def _fire(state: GameState, actor: int, person: int):  # type: ignore[no-untyped-def]
    from tst.sim.actions import Fire, apply_action

    cash = {(CID, "1000_cash"): 10**10}
    return apply_action(state, Fire(actor, person), RngFactory(1), B, D, cash, seq=person)
