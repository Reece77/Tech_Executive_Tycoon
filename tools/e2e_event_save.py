"""Create a save with an open event for the e2e tests (M6, an e2e fixture tool). A funded
spinout hires three engineers through the normal actions and plays a month; then, standing
in for the director, one event is queued for this month and written by the event service with
the template adapter, as after a real turn. Events the director queued itself are answered
first, so the scripted one is the only one open. `--critical` queues the critical payroll
event instead (formulas.md 16.3); `--queued` opens no event but queues the payroll event's
follow-up for next month, so the next Continue brings a known event; `--modifier` opens the
minor award event whose first choice starts a morale-target modifier (M10b, 23.2). It runs
before the API
opens the file. Never used by the game itself.

Usage: uv run --project backend python tools/e2e_event_save.py <dir> <name>
       [--critical|--queued|--modifier]
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.config import Settings
from tst.db.events import write_pending
from tst.db.repository import (
    create_save,
    load_state,
    open_session,
    run_action,
    run_turn,
    write_session,
)
from tst.db.state_io import sync_state
from tst.llm.offline import TemplateAdapter
from tst.loader import load_all
from tst.sim.actions import ChooseEvent, Interview, MakeOffer, OpenSearch
from tst.sim.events.formulas import cash_base_cents
from tst.sim.events.models import GameEvent, QueuedEvent
from tst.sim.state import with_event, with_queued

SEED = 16
FOUNDER = 1
HIRES = 3


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print(__doc__)
        return 2
    save_dir, name = Path(argv[0]), argv[1]
    critical, queued = argv[2:] == ["--critical"], argv[2:] == ["--queued"]
    modifier = argv[2:] == ["--modifier"]
    data = load_all(Settings().data_dir)
    offline = TemplateAdapter()
    path = create_save(
        name,
        SEED,
        "funded_spinout",
        company_name="Kestrel",
        data=data,
        save_dir=save_dir,
        mission=("ai", "enterprise"),
    )
    run_action(path, data, OpenSearch(FOUNDER, "software_engineer", "job_post"))
    run_turn(path, data, adapter=offline)
    with open_session(path) as session:
        state = load_state(session)
    for candidate in [c for c in state.candidates if c.company_id == 1][:HIRES]:
        ask = state.person(candidate.person_id).salary_expectation_cents or 0
        run_action(path, data, Interview(FOUNDER, candidate.person_id))
        run_action(path, data, MakeOffer(FOUNDER, candidate.person_id, 2 * ask, 0))
    run_turn(path, data, adapter=offline)
    with open_session(path) as session:
        state = load_state(session)
    for event in state.open_events(1):
        if event.status == "open":
            run_action(path, data, ChooseEvent(FOUNDER, event.id, event.choices[0].key))
    with write_session(path) as session:
        state = load_state(session)
        staff = sorted(e.person_id for e in state.staff(1) if e.person_id != FOUNDER)
        event_id, ids = state.next_ids.take("event")
        event = GameEvent(
            id=event_id,
            company_id=1,
            turn=state.turn,
            template_id="runway_payroll_crunch" if critical else "low_morale_checkin",
            category="finance" if critical else "personnel",
            severity="critical" if critical else "major",
            trigger="runway_short" if critical else "low_morale",
            strength=1.0 if critical else 0.6,
            person_ids=() if critical else (staff[0],),
            months=2 if critical else None,
            cash_base_cents=cash_base_cents(150_000_000, 0, data.balance.events),
        )
        if modifier:  # M10b: a minor event whose choice A starts a modifier (23.2)
            event = replace(
                event,
                template_id="quiet_award",
                category="market",
                severity="minor",
                trigger="quiet_month",
                person_ids=(),
                strength=0.3,
            )
        new = with_event(replace(state, next_ids=ids), event)
        if queued:  # the event is answered already; its follow-up comes next month
            event = replace(
                event,
                template_id="runway_payroll_crunch",
                category="finance",
                severity="critical",
                trigger="runway_short",
                person_ids=(),
                status="answered",
                title="Payroll is at risk",
                chosen="A",
                resolved_turn=state.turn,
            )
            queued_id, ids = ids.take("queued")
            new = with_event(replace(state, next_ids=ids), event)
            new = with_queued(
                new,
                QueuedEvent(queued_id, 1, "runway_aftermath", state.turn + 1, event.id),
            )
        sync_state(session, state, new)
    write_pending(path, data, adapter=offline)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
