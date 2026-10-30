"""The event director (docs/formulas.md 16.1-16.2, M6 sub-task 3): triggers follow the state
(a low-morale star, a price war, a short runway), cooldowns and critical spacing hold,
storylines and follow-ups are scheduled, and the same seed queues the same events."""

from __future__ import annotations

from dataclasses import replace

from tests.helpers import fresh_game, make_person, with_employee, with_product
from tests.unit.test_hiring_phases import Game
from tst.loader import LoadedData
from tst.sim.events.director import candidates, direct
from tst.sim.events.models import GameEvent, QueuedEvent
from tst.sim.events.triggers import triggers
from tst.sim.rivals.models import RivalMove
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_event, with_person_state, with_queued

STAR = 2


def _staffed(loaded: LoadedData, n: int = 4, turn: int = 14) -> GameState:
    state = replace(fresh_game(loaded), turn=0)
    for pid in range(2, 2 + n):
        level = "principal" if pid == STAR else "junior"
        state = with_employee(loaded, state, make_person(loaded, pid, level=level), 9_000_000)
    return replace(state, turn=turn)


def _hits(state: GameState, loaded: LoadedData, cash: int = 400_000_000, moves=()):  # type: ignore[no-untyped-def]
    return triggers(state, state, loaded.balance, loaded.game_data, cash, tuple(moves))


def test_a_low_morale_star_is_noticed(loaded: LoadedData) -> None:
    state = _staffed(loaded)
    state = with_person_state(state, replace(state.person_state(STAR), morale=22.0))
    hits = _hits(state, loaded)
    low = [h for h in hits if h.trigger == "low_morale"]
    assert [h.person_ids for h in low] == [(STAR,)] and low[0].strength == (35 - 22) / 20
    assert any(h.trigger == "star_performer" and h.person_ids == (STAR,) for h in hits)
    pool = candidates(state, hits, loaded.balance, loaded.game_data)
    assert {c.template.trigger for c in pool} >= {"low_morale", "star_performer"}
    severities = {c.template.id: c.severity for c in pool if c.template.trigger == "low_morale"}
    assert severities["low_morale_checkin"] == "major"  # strength 0.65 >= 0.5
    assert all(h.trigger != "quiet_month" for h in hits)


def test_a_price_war_is_noticed(loaded: LoadedData) -> None:
    state = with_product(_staffed(loaded), customers={"smb": 40.0})
    mine = state.company_products(1)[0]
    rival = next(c for c in state.companies if c.name == "Salesforce")
    theirs = next(p for p in state.company_products(rival.id) if p.category == mine.category)
    cut = RivalMove(1, rival.id, state.turn, "price_cut", theirs.id, "smb", "cut SMB prices 10%")
    hits = _hits(state, loaded, moves=[cut])
    war = [h for h in hits if h.trigger == "price_war"]
    assert len(war) == 1 and war[0].rival_id == rival.id and war[0].product_id == mine.id
    assert any(h.trigger == "rival_move" for h in hits)
    pool = candidates(state, hits, loaded.balance, loaded.game_data)
    assert {c.template.id for c in pool} >= {"rival_price_war", "price_war_customers_ask"}


def test_a_short_runway_is_noticed_and_critical_below_three_months(loaded: LoadedData) -> None:
    state = _staffed(loaded)
    short = [h for h in _hits(state, loaded, cash=12_000_000) if h.trigger == "runway_short"]
    assert len(short) == 1 and short[0].critical_ok and short[0].strength == 1.0
    pool = candidates(
        state, _hits(state, loaded, cash=12_000_000), loaded.balance, loaded.game_data
    )
    assert any(c.severity == "critical" and c.template.id == "runway_payroll_crunch" for c in pool)
    longer = [h for h in _hits(state, loaded, cash=25_000_000) if h.trigger == "runway_short"]
    assert longer and not longer[0].critical_ok and longer[0].strength == 0.6


def _past(state: GameState, **fields: object) -> GameState:
    event = GameEvent(
        id=900 + len(state.events),
        company_id=1,
        template_id="low_morale_checkin",
        category="personnel",
        severity="minor",
        trigger="low_morale",
        strength=0.5,
        status="answered",
        turn=state.turn,
    )
    return with_event(state, replace(event, **fields))  # type: ignore[arg-type]


def test_cooldowns(loaded: LoadedData) -> None:
    state = _staffed(loaded)
    state = with_person_state(state, replace(state.person_state(STAR), morale=22.0))
    hits = _hits(state, loaded)

    def ids(s: GameState) -> set[str]:
        return {c.template.id for c in candidates(s, hits, loaded.balance, loaded.game_data)}

    assert "low_morale_checkin" in ids(state)
    # The same template within its cooldown: out; once the cooldown has passed it may run
    # again (the event is queued for next month, so turn - (cooldown - 1) is the first back).
    cool = loaded.balance.events.template_cooldown_turns
    assert "low_morale_checkin" not in ids(_past(state, turn=state.turn - (cool - 2)))
    assert "low_morale_checkin" in ids(_past(state, turn=state.turn - (cool - 1)))
    # Anyone named within the person cooldown: none of their events.
    near = state.turn - (loaded.balance.events.person_cooldown_turns - 2)
    named = _past(state, template_id="anniversary_card", person_ids=(STAR,), turn=near)
    assert not any(
        STAR in c.hit.person_ids for c in candidates(named, hits, loaded.balance, loaded.game_data)
    )
    # Category used last month: half weight.
    base = {
        c.template.id: c.weight for c in candidates(state, hits, loaded.balance, loaded.game_data)
    }
    used = _past(state, template_id="anniversary_card", turn=state.turn)
    halved = {
        c.template.id: c.weight for c in candidates(used, hits, loaded.balance, loaded.game_data)
    }
    assert halved["low_morale_checkin"] == base["low_morale_checkin"] / 2
    # At most one critical event in any 6 months.
    crunch = _hits(state, loaded, cash=12_000_000)
    recent = _past(
        state, template_id="runway_payroll_crunch", severity="critical", turn=state.turn - 3
    )
    assert not any(
        c.severity == "critical"
        for c in candidates(recent, crunch, loaded.balance, loaded.game_data)
    )


def test_storylines_and_follow_ups_are_scheduled(loaded: LoadedData) -> None:
    state = _staffed(loaded)
    state = with_queued(
        state, QueuedEvent(1, 1, "runway_aftermath", state.turn + 1, source_event_id=5)
    )
    state, requests = direct(
        state, state, RngFactory(4), loaded.balance, loaded.game_data, 400_000_000, 0, ()
    )
    assert requests[0].template_id == "runway_aftermath"  # always arrives, first
    assert state.queued[0].done
    assert all(e.status == "pending" and e.turn == state.turn + 1 for e in state.events)


def test_events_are_seeded_and_follow_the_month(loaded: LoadedData) -> None:
    runs = []
    for _ in range(2):
        state = _staffed(loaded, n=6, turn=0)
        game = Game(loaded, state, 400_000_000)
        for _ in range(30):
            game.turn()
        runs.append(
            [(e.id, e.turn, e.template_id, e.person_ids, e.tone) for e in game.state.events]
        )
    assert runs[0] == runs[1] and runs[0]
    events = game.state.events
    stories = {s.key: s for s in game.state.storylines}
    for e in events:
        if e.storyline_id is not None:
            assert game.state.storyline(e.storyline_id) is not None
    assert len({e.id for e in events}) == len(events)
    assert all(e.company_id == 1 for e in events)
    assert (
        len([s for s in stories.values() if s.status == "active"])
        <= loaded.balance.events.max_storylines
    )


def test_quiet_month_templates_fill_when_every_candidate_is_in_cooldown(
    loaded: LoadedData,
) -> None:
    """16.1 (Reece, 2026-10-29): when the triggered candidates run out, quiet-month templates
    may fill the month's slots, at minor severity only; none when quiet_month holds anyway."""
    import numpy as np

    from tst.sim.events.director import fill_candidates, pick
    from tst.sim.events.triggers import TriggerHit

    state = _staffed(loaded)
    hits = [TriggerHit("star_performer", 0.4, (STAR,), None)]
    blocked = _past(state, template_id="anniversary_card", person_ids=(STAR,), turn=state.turn)
    assert candidates(blocked, hits, loaded.balance, loaded.game_data) == []
    fill = fill_candidates(blocked, hits, loaded.balance, loaded.game_data)
    assert fill and {c.template.trigger for c in fill} == {"quiet_month"}
    assert {c.severity for c in fill} == {"minor"}
    chosen = pick(np.random.default_rng(0), [], 2, fill)
    assert len(chosen) == 2 and chosen[0].template.id != chosen[1].template.id
    quiet = [TriggerHit("quiet_month", 0.2)]
    assert fill_candidates(blocked, quiet, loaded.balance, loaded.game_data) == []


def test_early_days_until_something_is_live(loaded: LoadedData) -> None:
    """M7a (docs/balance-targets.md E3): with nothing live to sell, early_days holds instead of
    quiet_month, and a solo founder draws founder templates; a template naming {product}
    needs a product in development. Once a product is live, early_days stops."""
    solo = replace(fresh_game(loaded), turn=3)
    hits = _hits(solo, loaded)
    assert [h.trigger for h in hits] == ["early_days"]
    pool = candidates(solo, hits, loaded.balance, loaded.game_data)
    ids = {c.template.id for c in pool}
    assert {c.template.category for c in pool} == {"founder"}
    assert len(ids) >= 10 and "early_prototype_bug" not in ids  # no product to name

    building = with_product(solo, status="in_development")
    hit = next(h for h in _hits(building, loaded) if h.trigger == "early_days")
    assert hit.product_id == building.company_products(1)[0].id
    pool = candidates(building, [hit], loaded.balance, loaded.game_data)
    assert "early_prototype_bug" in {c.template.id for c in pool}

    live = with_product(solo, customers={"smb": 10.0})
    assert "early_days" not in {h.trigger for h in _hits(live, loaded)}
