"""The campaign's length and dynasty years for the API (M37, formulas.md 52.6): the mode, the
end date, eras' public windows, rivals' successions and deaths as they happen. Never a drawn
date before its window is public, a mortality draw or a succession plan."""

from __future__ import annotations

from tst.api.schemas.campaign import CampaignOut, DeathOut, EraWindowOut, LeaderChangeOut
from tst.loader import LoadedData
from tst.sim.calendar import format_turn, ym_to_turn
from tst.sim.dynasty import mode
from tst.sim.state import GameState

DECEMBER = 12  # tunable-exempt: calendar month


def campaign_out(state: GameState, data: LoadedData) -> CampaignOut:
    b, g = data.balance, data.game_data
    dynasty = mode.length(state) == "dynasty"
    # ADR-0024: a standard campaign's last month is 359 turns after its start (December 2039,
    # or December 2037 for a 2008 start)
    end_turn = (
        ym_to_turn(b.dynasty.end_year, DECEMBER)
        if dynasty or not mode.is_campaign(state)
        else mode.standard_end_turn(state, b) - 1
    )
    founder = state.founder_of(state.player.id)
    late = mode.in_dynasty_years(state, b)
    eras = []
    if late:
        for era in g.eras.eras:
            if era.window is None or era.window[0][0] < b.dynasty.start_year:
                continue
            (y1, _), (y2, _) = era.window
            a = state.era_arrival(era.key)
            eras.append(
                EraWindowOut(
                    key=era.key,
                    label=era.label,
                    window_label=f"{y1}-{y2}",
                    arrived_label=format_turn(a.turn) if a is not None else None,
                )
            )
    d = state.dynasty
    changes = [
        LeaderChangeOut(
            company_id=c.company_id,
            company_name=state.company(c.company_id).name,
            date_label=format_turn(c.turn),
            old_name=c.old_name or None,
            new_name=c.new_name,
            how=c.how,
            personality_changed=c.personality_before != c.personality_after,
        )
        for c in (d.leader_changes if d else ())
    ]
    deaths = [
        DeathOut(
            person_id=x.person_id,
            name=x.name,
            date_label=format_turn(x.turn),
            age=x.age,
            role=x.role,
        )
        for x in (d.deaths if d else ())
    ]
    return CampaignOut(
        length=mode.length(state),
        end_label=format_turn(end_turn),
        at_end=mode.at_standard_end(state, b),
        can_switch=mode.is_campaign(state) and not dynasty and not state.ended,
        game_state=mode.outcome(state, b),
        founder_age=founder.age(state.turn) if founder is not None else None,
        dynasty_years=late,
        eras=eras,
        leader_changes=changes[-50:],  # tunable-exempt: the latest shown
        deaths=deaths,
    )
