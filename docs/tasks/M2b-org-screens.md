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

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
