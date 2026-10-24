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

Engineering decisions made by the agent. No game rule changed and the golden snapshots are unchanged.

**API additions** (screens needed numbers the API did not return; all display values, built in `tst/api`, with integration tests in `tests/integration/test_api_screens.py`):

- **Overview:** `team` (headcount, on notice, people cost, payroll and average morale *now*, not at the last month end), `month_costs` (this month's projection from `phases.monthly_costs`, the same function phase 6 posts, so a test checks the projection equals what Continue posts), `month_paid` (expenses already posted this month, labelled by ledger memo, so a firing shows "Severance"), `month_total_cents`, `stage_label` (spec §3 names) and `runway_low` (runway below `morale.runway_warn_months`).
- **People:** employment gains `market_rate_cents` (role band mid × region), `monthly_cost_cents`, `tenure_months` and start/end date labels; every person gains `knowledge` (search channel, interview and reference-check counts from `decision_log`, first interview month) and `interests` (moved from the profile to the summary, still null until revealed, so the candidates table needs no extra requests); the profile gains `work_style_matches_role`; tags and pending offers gain date labels ("answer in Mar 2010").
- **Recruitment:** `GET /api/meta/hiring` (channel energy, cost, fee, batch size, repeat, level mix; role key skills; energy costs; offer limits; the minimum firing morale penalty, 3). Searches list closed searches whose candidates are still available (the "Closed after one batch" row) and carry batch dates. The offer preview returns `reasons`: plain sentences built only from what the company knows (pay vs ask, equity, revealed mission matches, the displayed risk-appetite range, stage appeal).
- **Inbox:** `POST /inbox/{id}/unread` for Mark unread. **Setup:** preset descriptions in `backgrounds.yaml`; scenarios carry starting cash for every difficulty.
- `phases.payroll` now builds its lines from `monthly_costs`; `employment_monthly_cost_cents` reproduces the §8 worked example ($12,100.00), with a unit test.

**Front end:**

- **Runway** stays "whole months at last month's burn" (the existing API value), noted as such on the tile. The wireframe's "At June costs" would be a different number; see follow-ups.
- **Fire dialog** states the severance and "at least 3 points" (from the hiring meta), never the exact penalty. The profile note says only that morale drops.
- **Inbox:** clicking a message marks it read; the default selection (newest) does not. Template keys map to the wireframe's kind labels and People/Hiring filters in `src/lib/inbox.ts` (display only; unknown kinds show as Month).
- **Candidates table** shows the role's primary skills plus its first secondary skill; People "Top skills" sorts by range midpoint. Both are display ordering only.
- **Hotkeys:** digits now work while a button or link has focus (only Space/Enter defer to the focused control). Continue no longer waits for the other screens to refetch, so a second press is not swallowed.
- **Seed** stays available on the setup screen behind "Set a seed (optional)" (needed for the seeded e2e flows; not in the wireframe).
- **Fonts:** IBM Plex from Google Fonts in `index.html`, falling back to system fonts offline (no new dependency).
- **Component tests** render to static markup with `react-dom/server`: no DOM library (jsdom) is in ADR-0001, so interaction is covered by Playwright.
- A per-screen error boundary shows a render error instead of a blank page.
- **E2E:** `e2e/m1c.spec.ts` has flows (a), (b), (c) and a fourth test for the first acceptance criterion (ten hires within six turns via network, recruiter and job post, all through the UI). The M0 smoke tests now go through the setup screen. Locally, `PLAYWRIGHT_CHANNEL=msedge make e2e` uses the installed Edge.

## Follow-ups

- **Runway at this month's costs:** the wireframe's Overview note ("At June costs") implies runway from the projected month, not last month's burn. That is a definition change (it also feeds the top-bar warning), so it needs Reece's call.
- **Month-closed inbox items:** the wireframe shows a "May 2010 closed" (Month) message; the engine emits none. A month-end summary template would fill it.
- **jsdom or happy-dom** as a dev dependency would allow Vitest interaction tests (setup stepper, offer panel); needs an ADR-0001 addition.
- **Self-hosted fonts** (for example `@fontsource/ibm-plex-*`) if the game should look right offline; also a dependency question.
- **Short skill labels** ("Software eng") in `skills.yaml` would keep the People "Top skills" column narrower; it currently scrolls at 1440 px with long names.
- The network channel card shows 2–4 candidates; the +1 for founder sociability ≥ 15 is not mentioned.
- Candidates expire in phase 12 of their last month, after an offer made that month resolves in phase 1 of the next; worth confirming an offer made in the expiry month still resolves (the UI allows it).
