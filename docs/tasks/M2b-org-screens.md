# M2b: Org screens

**Goal:** manage the organization from the browser: see and edit the org chart, appoint leaders, set policies, run hiring plans, and give raises and promotions.

**Spec sections:** §6, §13 · **ADRs:** 0007, 0009, 0014, 0015, 0016 · **Wireframes:** `docs/wireframes.md` (M2b screens) and `docs/wireframes/source/Org.dc.html`, `ProfileOrg.dc.html`, `RecruitmentPlans.dc.html` · **Depends on:** M2a (`m2a-done`)

## Context

M2a provides every rule, endpoint and preview, except one backend slice listed below (a plan focus for spotting potential, Reece's call after M2a). Apart from that slice, this milestone is front end only: display, sort, filter and format what the API returns; never compute a game value (`CLAUDE.md` §7). If a screen needs a value the API lacks, add it to the backend schema, regenerate the client, and record it under Decisions made.

## Out of scope

Any new rule beyond the backend slice. Products, Finance, Competitors and History screens.

## Backend slice (sub-task 0, before the screens)

Per `docs/formulas.md` §4 (PA scout factor) and §13.10 (plan focus, potential target):

1. `hiring_plan.focus` (`current` default, `potential`), migration `0007_plan_focus`, data dictionary; `create_plan` / `update_plan`, API and `tst plan create|update --focus`.
2. Delegate ranking for `potential` (junior and mid only, by displayed PA midpoint).
3. The PA scout factor and `reveal.pa_scout_divisor`, `reveal.pa_strength.*` in `balance.yaml`, with unit tests and the §4 worked example extended with a PA row.
4. The comparative test: 400 seeds, judgment 16 vs 6, mean true PA gap ≥ 3. Tune only the keys §13.10 names (now including `reveal.initial_hw.pa`, 60–120, and the founder's own PA kept at `reveal.founder_pa_hw` = 40); record the values and the typical phrase §13.10 asks for under Decisions made. If no values in range reach the target, stop and report the best gap.
5. Golden snapshots regenerated if the PA change moves them, with a CHANGELOG note.

## Screens

1. **Org** (nav key 5, now live): the tree from company to departments to teams, each node showing its leader, headcount, policy and the leader's span (with an over-span warning). Create, rename and dissolve units; set leaders; move people by drag-and-drop or a "Move to" menu. Every change shows the reorganization preview (one-off morale changes) before it is confirmed. Departments appear only when unlocked, with the reason shown otherwise.
2. **Person profile additions:** unit and manager (linked), a morale breakdown panel (§13.11 terms), and Raise and Promote dialogs that show the preview (new salary against the market rate, one-off morale) before confirming.
3. **People additions:** Unit and Manager columns, a unit filter, and a "Leads" chip on leaders.
4. **Recruitment additions:** a Hiring plans panel (owner, unit, role, focus, progress toward target, channel, ratio, equity, last turn's activity), with create, edit and close; the plan dialog offers Focus: "Best now" (current) or "Spot potential" (potential, juniors and mids only); the network channel card mentions the +1 candidate for a sociable founder.
5. **Inbox:** delegate summaries get their own kind badge; add paging (50 per page), since a long game fills the inbox.
6. **Overview additions:** an Org tile (units, people over span, average manager quality shown as a label: strong, fine, stretched).

## Sub-tasks (commit after each)

0. Backend slice (above).
1. Regenerate the client; shared `OrgNode`, `SpanBadge` and `PreviewDialog` components with tests.
2. Org screen.
3. Profile and People additions.
4. Recruitment hiring plans; inbox paging and the delegate badge; Overview tile.
5. Playwright: (a) build company → department → team and appoint leads; (b) create a hiring plan, Continue three times, see hires join the plan's unit while founder energy stays full; (c) give a raise and a promotion and see the preview match the result.

## Acceptance criteria

- [ ] The potential target in `docs/formulas.md` §13.10 holds (printed gap ≥ 3 PA over 400 runs), with the tuned values recorded.
- [ ] Every M2a action is reachable from the screens, with its preview shown before it is applied.
- [ ] The Org screen matches its wireframe and stays usable with 40 people and 8 units.
- [ ] No game value is computed in the front end.
- [ ] `make check` green; `make e2e` passes all flows.

## Manual check (Reece)

1. Play a `funded_spinout` game to about 15 people, then build two teams and a department in the Org screen.
2. Hand engineering hiring to a recruiter's plan and play 12 months without hiring yourself. Run a second plan set to "Spot potential" and compare its hires' potential phrases after six months.
3. Note whether morale and growth respond the way the org suggests, and whether the founder's energy now feels like a resource, given that every hire needs an interview. These notes feed the balance pass and M3.

## Decisions made

1. **Tuned PA values** (formulas.md §4, §13.10): stranger PA `hw` (`reveal.initial_hw.pa`) **67**, founder's own PA `hw` (`reveal.founder_pa_hw`) **40**, `reveal.pa_scout_divisor` **16**, `reveal.pa_strength`: job-post screen **0.05**, interview **0.10**, scouting month **0.60**; network intro 0.30, reference check 0.30, employed month 0.08 unchanged. Result: **+3.09 PA** over 400 seeds (judgment 16: 132.66, judgment 6: 129.57).
   - 67 is the smallest whole value that reaches +3: 66 gives +2.93 and 65 at most +2.94 with any strengths tried. At 40 the named keys topped out at +1.27; 70 gives +3.33 and 75 gives +3.41 with the same strengths. The margin at 67 is thin (0.09 PA), so a later change to candidate generation or delegate ranking could tip the test under 3.
   - Tuning runs (400 seeds each): at hw 60–70 the strengths and divisor moved the gap by at most about 0.3; divisor 16 beat 14, 17, 18, 20 and 24; scouting 0.6 beat 0.4 and 0.8.
2. **What the player's own reading costs:** a judgment-10 founder, after a job-post screen and one interview, typically sees **"limited to outstanding"** (45 of 100 seeded candidates) or **"decent to outstanding"** (30); then "limited to excellent" (19), "good to outstanding" (3) and "limited to good" (3). The displayed PA range averages 119 points wide. A 6-month employee read by a judgment-12 scout narrows to about "decent to outstanding" (§4 PA worked example).
3. **`reveal.pa_scout_clamp`** ([0.1, 1.0]) holds the bounds of the PA scout factor in `balance.yaml` rather than as literals (not tuned).
4. **Old decision logs:** `CreatePlan` and `UpdatePlan` default `focus` to `current`, so M2a saves replay unchanged.
5. **Potential focus** affects steps 2, 3 and 5 only; scouting (step 4) still covers every open candidate for the role, and step 1 is unchanged.
6. **Tests pinning the old PA value** (`test_section_4_initial_half_widths`, the founder knowledge test) now check 67 for strangers and `founder_pa_hw` for the founder, as formulas.md now says.
7. **Golden snapshots** are unchanged by the slice: the scripted games use current-focus plans and nothing they decide depends on PA knowledge.
8. **Values added to the API for the screens** (the brief allows this; none is a new rule): `rename_unit` (see 9); `UnitOut.headcount` (the unit and every unit below it); `ManagerOut.label` and `OrgOut.managers_over_span`; `PersonSummaryOut.org` (unit, parent unit, manager, led unit) and `.energy`; `PayPreviewOut.salary_change_bp`, `.market_ratio`, `.new_market_ratio`, `.monthly_cost_change_cents`, `.below_market`; `OverviewOut.org` (the Org tile), `.option_pool_left_bp`, `.network_bonus_candidates`; `InboxOut.total` and `.offset` with an `offset` query parameter; `HiringPlanOut.owner_on_staff` and `.owner_role_label`.
9. **Renaming a unit** is a new action, `rename_unit` (API `POST /org/units/{id}/rename`, `tst unit rename`, previewable): free, with no morale change, as the wireframe shows Rename without an energy cost. Names follow the create rules (1–64 characters, unique among active units).
10. **Manager label** (strong, fine, stretched) comes from the manager's W_mgr (§13.4): at or above +2 strong, at or below −2 stretched, between fine (`org.manager_label_bands`, morale points). The Overview's average label is the label of the mean W_mgr over everyone who manages anyone (founder included). This display rule was not in the spec; the bands mean "about a quarter of the cap either way".
11. **"Well below the market rate"** in the Promote dialog is shown whenever the salary would be below the new level's market rate (`below_market`), so no extra threshold was invented.
12. **Inbox:** the filters (Unread, People, Hiring) apply to the 50 messages on the current page. Plan messages (`plan_activity`, `plan_filled`, `plan_paused`) get the Delegate badge and the Hiring group; `unit_leader_left` is a Notice.
13. **Org screen:** a new team is created under the selected department when one is selected, otherwise under the company; the root has no "inherit" policy option; a leader's Move to… is disabled until they are replaced (the API refuses it anyway). Drag-and-drop uses HTML5 drag events; people and teams also have menus for keyboard use.
14. **Promote and raise…** promotes first, then opens the raise dialog at the new level's market rate.
15. **Plan dialog:** an owner who has never owned a plan shows `delegates.energy_per_month` from `GET /meta/org`; the owner defaults to the first staff member until the player picks.
16. **Smoke e2e:** key 5 now opens Org, so the placeholder check moved to key 6 (Products, M3).

## Follow-ups

1. **The potential target has a thin margin** (+3.09 against +3 at stranger PA `hw` 67). A change to candidate generation, batch sizes or delegate ranking could tip the comparative test under 3; 70 would give +3.33 if more headroom is wanted.
2. **Potential is now hard to read for the player.** After a job-post screen and one interview a judgment-10 founder usually sees "limited to outstanding" (45 of 100 candidates). The balance pass may want the founder's own interviews to read potential better, or a cheaper way to learn it than hiring a scout.
3. **No player-initiated scouting.** Scouting is the main source of PA knowledge but only delegates can do it; a founder "scout this candidate" action would let the player buy knowledge with energy.
4. **Inbox filters are per page.** With many messages, People or Hiring filters show only matches from the current 50; server-side filters would fix it if long games make it awkward.
5. **Manager label bands** (±2 W_mgr) are a first guess for the playtest.
