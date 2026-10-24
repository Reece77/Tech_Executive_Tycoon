# M1c: Screens and new-game setup

**Goal:** M1 is playable in the browser: create a company with your own founder and mission, then hire, pay, and manage a team through the Inbox, People, Person profile, Recruitment, and Overview screens.

**Spec sections:** §5.3, §13 · **ADRs:** 0001, 0007, 0009, 0014 · **Wireframes:** `docs/wireframes.md` (all six screens) · **Depends on:** M1b (`m1b-done`)

## Context

M1b provides every rule and endpoint, including previews for the offer hint and the founder build. This milestone is front end only. The one backend change it needed was made ahead of time, in the `m1b-followups` branch: firing a culture carrier reveals that tag to the player's company and adds an inbox item ("The team took {name}'s departure hard; they held the team together"), with a test. A hidden tag otherwise never shows, so the fire dialog must not state the exact penalty. The front end displays, sorts, filters, and formats what the API returns; it never computes a game value (`CLAUDE.md` §7). If a screen needs a number the API does not return, add it to the backend schema, regenerate the client, and note it under Decisions made.

## Out of scope

Any new game rule. Org chart, Products, Finance, Competitors, and History screens (later milestones; keep them as dimmed nav items). Animations.

## Screens (layout, colors, and content per `docs/wireframes.md`)

1. **New-game setup** (replaces M0's create form): a stepped form on one page.
   - Company: name, scenario (v1 only), difficulty.
   - Founder: name (optional; blank draws one), age, background cards showing bonuses, skill allocation with the background's default pre-filled, and a reset button. Points remaining, final skill values, and errors come from `POST /api/meta/founder-preview` as the player types (debounced).
   - Personality: four preset cards or "Surprise me" (random).
   - Mission: choose exactly 2 interests.
   - Start: disabled until the preview reports no errors.
2. **Inbox:** becomes the home screen after a game loads.
3. **Overview:** KPI tiles (cash, monthly burn, runway, headcount, monthly payroll, average morale), 12-month cash line chart, this month's cost breakdown, and the five latest inbox items.
4. **People:** roster with Overview and Skills views, filter, summary tiles.
5. **Person profile:** as wireframed, with Fire behind a confirm dialog that states the severance and says "everyone else's morale will drop by at least 3 points". Never show the exact penalty: −6 instead of −3 would reveal a hidden culture-carrier tag.
6. **Recruitment:** open a search, your searches, candidates table, and the offer panel. The hint, floor, ratio, and rule errors come from the offer-preview endpoint as the player edits salary or equity.
7. **Top bar:** founder energy meter, which updates after each action; Continue (Space or Enter); keys 1–9 for nav.

## Sub-tasks (commit after each)

1. Regenerate the client; shared shell (top bar with energy, nav with unread count); `AttributeRange`, `MoraleBar`, `KindBadge`, and `StatusChip` components with Vitest tests.
2. New-game setup.
3. Inbox (home) and Overview.
4. People and Person profile.
5. Recruitment and the offer panel.
6. Playwright: (a) set up a game with a custom founder and mission; (b) open a job post, Continue, interview, preview and send an offer at the ask, Continue, see the hire on People and payroll in Overview; (c) fire someone and see severance and the morale dip.

## Acceptance criteria

- [ ] From a fresh game, the player can hire 10 people through the UI within 6 turns using all three channels.
- [ ] Every screen matches its wireframe in layout, tokens, and content; hidden values never appear.
- [ ] No game value is computed in the front end: hints, points remaining, and costs all come from the API.
- [ ] Each screen has loading and error states, and works at a narrow window width (nav stacks, tables scroll).
- [ ] `make check` green; `make e2e` passes the three Playwright flows.

## Manual check (Reece)

1. `make dev`; create a game with the setup screen (funded spinout, your own name, mission AI and Enterprise).
2. Hire a team of about 10 over a few months, mixing channels; deliberately underpay two people.
3. Play 24 months. Expect cash to fall by payroll, the underpaid pair's morale to drift down, and some traits noticed in the inbox.
4. Fire someone; check severance on Overview and the morale dip on People.
5. Write down anything that feels off: these notes drive the first balance pass and the M2 brief.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
