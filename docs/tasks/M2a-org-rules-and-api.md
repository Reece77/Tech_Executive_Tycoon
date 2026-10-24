# M2a: Organization, delegation, raises (rules, API, CLI)

**Goal:** the player can build a company → department → team structure, appoint leaders, set policies, give raises and promotions, and hand hiring to delegates, and those choices change morale, growth and hiring results, all through the API and the command line, fully tested. Screens come in M2b.

**Spec sections:** §5.2, §5.3, §5.4, §6 · **ADRs:** 0002, 0007, 0011, 0013, 0014, 0015, 0016 · **Formulas:** `docs/formulas.md` §13, plus the M2 terms in §3, §6, §7, §9 · **Depends on:** M1 (`m1c-done`)

## Context

M1 gave the company people, hiring and a payroll. As the team grows, everyone reports to the founder, whose energy and attention run out. M2 adds the answer: an org chart whose managers affect morale and growth, and delegates who hire on the founder's behalf. Every effect works through systems M1 already has (morale, growth, offers, energy); productivity and coordination cost arrive with products in M3.

`docs/formulas.md` §13 is authoritative for every rule and number. ADR-0015 says where delegates act and how their randomness and replay work.

## Out of scope

Products, projects, productivity, coordination cost, decision latency, and the `politician`, `maverick`, `perfectionist` and `quiet_genius` effects (M3). Divisions and subsidiaries (v2/v3). Pairwise relationships and chemistry (with events, M6). Equity refreshes and the cap table (M4). Any change to the offer rules beyond the pitch term and the interview requirement (ADR-0016).

## Rules (summary of `docs/formulas.md` §13)

1. **Units:** company root (implicit, led by the founder), departments under the root (from 10 staff, or stage 2), teams under the root or a department. Every staff member belongs to one unit; the founder always belongs to the root. Leaders are members of the unit they lead and lead at most one unit.
2. **Managers:** a person's manager is their unit's leader; leaders and members of leaderless units look one level up; the root's leader is the founder.
3. **Span and quality:** `L = 5 + floor(leadership / 4)`; `S = 1` up to `L` reports, else `L / n`; `Q = (2·leadership + communication + mentoring) / 4 × S`.
4. **Morale target** gains `W_mgr = clamp(0.8 (Q − 10), −8, +8)`, the teammate-tag term (culture carrier +2, credit-taker −2, toxic high performer −3, each capped), and the remote term.
5. **Growth** is multiplied by `M_growth = clamp(1 + (mentoring·S + bonus − 5) / 20, 0.75, 1.5)` from the person's manager, with +3 bonus for a mentor teammate.
6. **Reorganizing** costs one-off morale: move −2, new leader −1 to other members and −5 to a replaced leader, dissolve −2.
7. **Raises and promotions:** a raise of at least 5% gives +3 once per 12 turns; a pay cut −10; a promotion +5 and the new level's market rate.
8. **Remote policy:** no office fee; −3 morale if sociability ≥ 14, +2 if ≤ 7.
9. **Delegated hiring:** plans owned by a staff delegate with 100 energy a month, run in phase 2: open a search, rank candidates by the company's displayed ranges, interview, scout with leftover energy, offer at the plan's ratio (ADR-0015).
10. **Offer pitch:** every offer's score gains `0.3 × (recruiting − 10) / 10` from whoever made it.
11. **Morale breakdown** in the API shows only what the company can know (§13.11).

## Changes from Reece's M1 playtest (ADR-0016)

1. **Offers require an interview.** `make_offer` fails with `InterviewRequired` (HTTP 409) unless the offering company has interviewed the candidate. Candidates in API responses gain `offer_blocked_reason` (`null` or `"interview_required"`). Tests: an offer without an interview is refused for the player and for a delegate; an interview by a delegate unlocks a player offer.
2. **Screens (small, in this milestone):** regenerate the client; disable the Offer button for a candidate with `offer_blocked_reason` and show "Interview first". Update the M1c Playwright hiring flow to interview before offering.

## Fixes carried from M1

1. **Candidate expiry vs. pending offer:** a candidate with a pending offer must not expire before it resolves (M1c follow-up; `docs/formulas.md` §7). Add a test that an offer made in a candidate's last month still resolves.
2. **CLI runway:** `tst inspect` reports runway at this month's projected costs, matching the screens (M1c decision).

## Sub-tasks (commit after each)

1. **Formula tests and data:** every §13.12 worked example and the pitch examples as unit tests (noise off); all new keys from §12 in `balance.yaml`.
2. **State and persistence:** `org_unit` (company, kind, name, parent, leader person, work-location policy or inherit), `employment.unit_id` and `last_raise_turn`, `hiring_plan` (owner, unit, role, target, channel, ratio bp, equity bp, status), `decision_log.source` and actor, delegate energy, `next_ids` for units and plans. Migration `0005_org`; existing saves put everyone in the root. Data dictionary.
3. **Org rules:** pure functions for manager resolution, span, quality, morale terms, growth multiplier, remote cost; wire them into phases 6 and 8. Property tests: every non-founder has exactly one manager; no cycles; the founder has none; leaders belong to their units.
4. **Actions** (ADR-0014): `create_unit`, `dissolve_unit`, `set_leader`, `move_person`, `set_policy`, `give_raise`, `promote`, `create_plan`, `update_plan`, `close_plan`, with founder energy per §6 and validation errors for every rule in §13.1.
5. **Delegates** (ADR-0015): phase 2 behavior, stream `delegate` (id 14) added to `STREAM_IDS` and ADR-0013's table, inbox summaries, plans pausing when their owner leaves, and the replay check that recomputed delegate actions equal the logged ones.
6. **Playtest changes and M1 fixes** above, and the offer pitch term.
7. **API** (save-scoped): org tree (units, leaders, members, each manager's reports, `L`, `S` and an over-span flag); the org actions; previews for reorganizations (the one-off morale changes, by person) and for raises and promotions (new salary versus market rate, one-off morale); hiring plans (list, create, update, close, last turn's activity); the person morale breakdown per §13.11; org metadata (energy costs, unlock rule, policy options). Extend the hidden-field test to the new responses, and add a test that a hidden toxic teammate shows only as "other" in the breakdown.
8. **CLI:** `tst org`, `tst unit create|dissolve|lead|move|policy`, `tst raise`, `tst promote`, `tst plan create|list|update|close`, `tst morale --person`.
9. **Golden snapshots:** the scripted plan interviews before every offer, and adds two teams with leads around turn 6, a department at 10 staff, and one recruiter-led hiring plan; regenerate with a CHANGELOG note.

## Acceptance criteria

- [ ] A scripted test builds a three-level org (company → department → team), with leaders, from the API.
- [ ] A founder managing 12 directly shows the §13.12 manager penalty in the morale breakdown; adding two leads removes it.
- [ ] Each reorganization's one-off morale change matches §13.7, and the preview reports it before the action.
- [ ] A recruiter-led plan fills 4 hires within 4 turns without spending founder energy.
- [ ] An offer to a candidate nobody at the company has interviewed is refused with `InterviewRequired`, from the API, the CLI and a delegate; the Offer button is disabled with "Interview first".
- [ ] Over 200 seeded runs, plans run by a judgment-16 recruiter hire people with a higher mean true CA than plans run by a judgment-6 recruiter (comparative test).
- [ ] An offer made in a candidate's last month still resolves.
- [ ] Replay reproduces a save with reorganizations, raises and delegates, and recomputed delegate actions match the log.
- [ ] No API response leaks a hidden field or an unnoticed tag (exact-name test and breakdown test).
- [ ] 120 turns with 25 staff, 4 units and 3 plans average under 1 second per turn (printed).
- [ ] `make check` green; golden snapshots regenerated with a CHANGELOG note.

## Manual check (Reece, command line)

1. Start a `funded_spinout` game and hire about 12 people (as in M1).
2. `uv run tst morale --save <save> --person <id>` for an employee: the manager term should be negative with everyone reporting to you.
3. Create two teams, appoint leads with good leadership, move people in, and check the same person's morale breakdown again.
4. Create a hiring plan owned by a recruiter for 3 engineers; advance 3 turns; read the inbox summaries; confirm the hires joined the plan's unit and your energy stayed at 100.
5. Give someone a raise and a promotion and watch their morale over the next months.
6. Try `tst offer` on a candidate you have not interviewed: it should refuse and tell you to interview first.

## Decisions made

Engineering and rule details that formulas.md §13, ADR-0015 and ADR-0016 left open:

1. **Interview record:** `candidate.interviewed_turn` (not in the column list above) records the company's first interview; `0005_org` backfills it from `decision_log`, so upgraded saves can still offer to candidates they interviewed.
2. **No FK constraints on columns added to existing tables** (`employment.unit_id`, `offer.plan_id`/`unit_id`, `decision_log.actor_id`): SQLite cannot add one by `ALTER TABLE`, and a referencing column could not be dropped on downgrade. The new tables have full FKs.
3. **The root's policy** lives on `company.work_policy` (default `office`); units store their own policy or null to inherit.
4. **Department unlock:** headcount includes the founder (`len(staff) >= 10`), or stage ≥ 2 (a spec constant in code).
5. **Leadership changes:** set, replace and remove all count as a change: −1 for each other member, −5 for the leader who loses the post. Removing a leader is allowed (`person_id: null`).
6. **Leaders must already be members:** `set_leader` refuses a non-member (no automatic move), and moving a leader out is refused until they are replaced or removed, so "leads at most one unit" holds by construction.
7. **Raise bonus cooldown:** `last_raise_turn` is set only by a raise that earned the +3; smaller raises do not restart the 12 turns. Every pay cut gives −10.
8. **Promotion** changes the employment's level only (the ladder ends at principal); salary is unchanged until a raise.
9. **Plan energy:** create and update cost 2 (`hiring_plan`); closing is free, like closing a search. `UpdatePlan` carries every field; the API's PATCH merges omitted fields.
10. **Plan statuses:** `active`, `paused` (owner left), `filled` (hired = target), `closed`. Raising the target or giving a paused plan a new owner on staff reactivates it.
11. **Delegate reading of §13.10:** "no open search for its role" means any open company search for that role; the plan's candidates are all open candidates for the role. Steps 2–4 run whenever the plan is active; offers go only up to the number still needed (target − hired − pending). Interviews continue while energy − 6 > `delegates.scout_cost`; scouting needs ≥ `scout_cost`. Offer salary = ask × ratio_bp / 10,000, rounded half to even.
12. **Scouting** is an action (`scout`) for any actor at `delegates.scout_cost`; it is not exposed in the API or CLI in M2a.
13. **Delegate energy** starts at `delegates.energy_per_month` when a person first owns a plan, and resets with the founder's after phase 12.
14. **People who leave:** in phase 1 (after notices end) and immediately on firing, a departed leader's post clears and their plans pause, each with an inbox item (`unit_leader_left`, `plan_paused`).
15. **Where hires join:** the offer stores the plan's unit at the time it is made; dissolving a unit moves its plans' and pending offers' unit to the parent.
16. **Live state** also loads whoever made a pending offer and every live plan's owner, so the pitch uses the maker's recruiting even after they leave and paused plans can still name their owner.
17. **Delegate log rows** take `seq` values after the player's actions for that turn; replay raises `ReplayMismatchError` when recomputed delegate actions differ from the logged ones.
18. **The founder's offer hint** includes the pitch term (the company knows the founder exactly).
19. **Morale breakdown:** a projection for this month with runway at this month's projected costs (as on the Overview); fit appears once the profile is known; each teammate tag shows the capped term of the holders the company has noticed; the rest is "other". It is also used by `tst morale`.
20. **Previews** apply the action to the loaded state without saving and report the differences.
21. **Plan activity wording** ("interviewed 4 software engineers and made 2 offers") is built in the sim and passed to the `plan_activity` template.
22. **M1 tests that offered without interviewing** now interview first through the API/CLI/DB, or set the interview precondition directly (`mark_interviewed`, `with_candidates(..., interviewed=True)`) where the test is about offers, so their numbers are unchanged.
23. **Performance:** `summarize()` (run after every committed turn for the save index) reads the player's company row instead of loading the whole state.

## Follow-ups

1. **Delegate searches stay open after a plan fills or closes.** A plan's job post keeps costing $500 a month and producing batches until the player closes it (the 120-turn check ends with 76 open candidates). §13.10 has no rule for it; suggest the delegate closes a job post it opened once its plan is filled or closed.
2. **Judgment barely matters yet:** over 200 seeds, judgment-16 hires average CA 115.45 against 115.36 for judgment 6. The criterion holds, but the effect is small for the balance pass (ranking by role-skill midpoints is already close to the truth after a job-post screen and an interview).
3. **No action reparents a team** under a department; the player must dissolve and recreate it. Worth a `move_unit` action in M2b if the screens need it.
4. **Attrition:** the performance check starts at 25 staff and ends near 16 after 120 turns, even with three plans refilling; base resignation (about 0.5% a month) may be high for a 30-year campaign.
5. **People screens (M2b):** person responses do not yet carry unit and manager; the screens can read them from `GET /org`.
