# M7c: Known fixes and an agent playtest

**Goal:** fix the two link problems M7b found, then have the agent play a full 10-year game through the browser like a player would. It fixes the bugs it finds and writes up everything else for Reece, so his own playtest starts from a cleaner build and a checklist.

**Spec sections:** §13 (UI), §17 (M7) · **ADRs:** 0007, 0009 · **Depends on:** M8 (`m8-done`); Reece started M8 first (2026-10-31)

## Context

Reece is away for two days and can't play. M7b's follow-ups: links to people who have left open a "not found" profile; links to events open the inbox rather than the event. His own 10-year playtest (the v1 acceptance) comes after this. A later brief turns his findings and this report's design notes into fixes.

## Out of scope

Design or balance changes. If something looks like a design problem (too slow, too easy, confusing rules), write it in the report and leave it alone. v2 systems.

## Sub-tasks (commit after each)

1. **Former staff profiles.** A person who has left opens a read-only "Former employee" profile.
   - **What it shows:** name, last role and unit, hire and leaving months, the reason they left (resigned, poached by a named rival, fired, retired), tenure, their last shown ranges and tags as the player knew them, and their History entries.
   - **No actions.** The poach-back case is out of scope.
   - **If departed people are no longer in the save,** keep what the player knew at departure (a migration and a data dictionary entry).
   - **Tests:** the existing planted hidden-value test covers this route. Links from History, the hall of fame, the inbox and the org history all resolve.
2. **Event links.** Every link to an event (History, hall of fame, "While you were away", the COO briefing) opens that event's own message in the inbox with its card showing, including answered events with the choice taken.
   - **Add a deep link** such as `/game/:save/inbox/:item`.
   - **Playwright:** follow a History event link and see the event card.
3. **Agent playtest.** Play a new game on `ex_big_tech_founders`, standard difficulty, for 120 months through the browser with Playwright, as a reasonable player would:
   - hire through job posts, interviews and offers, and set up a recruiter plan;
   - build and launch a product, then a second one;
   - raise a seed and a Series A when they're offered;
   - answer events by reading them, not always taking the first choice;
   - use Holiday in quiet stretches;
   - open every screen at least once a year;
   - ask the COO a question each year (mock adapter);
   - try the saves manager once (duplicate, then restore a backup).

   Save a screenshot of each main screen once a game-year in `docs/playtests/agent-m7c/`: at most 40 PNGs, compressed, under 15 MB in total. Keep the script in `frontend/e2e/playtest/` but out of `make e2e`; it can be run on demand with `make playtest`.
4. **Fix what's broken.** Fix everything the playtest shows that is clearly a bug, each with a test:
   - crashes or 5xx responses;
   - wrong or inconsistent numbers, such as a tile that disagrees with its breakdown or a total that doesn't add up;
   - broken links or buttons;
   - layout that hides information at 1440×900;
   - missing tooltips;
   - stuck states.

   Golden snapshots change only if a bug fix requires it, with the reason in CHANGELOG.
5. **Quick-start saves** (a tool, not a game feature): `make quickstart-saves` plays the balance runner's steady strategy headless on seed 1 and saves two games for Reece's playtests: `quick-stage2` (turn 36) and `quick-stage3` (blitzscale with a second product, at the first month of stage 3, so M8's divisions and seats can be tried at once). Each appears in the Saves screen; the tool is in `tools/` and documented in the README.
6. **Report:** `docs/playtests/agent-m7c.md`:
   - **The game in numbers,** per year: cash, ARR, staff, morale, rounds, products and events.
   - **Bugs fixed,** each with its commit.
   - **Bugs not fixed,** and why.
   - **Design and balance notes,** ranked by how much they'd affect a player. Observations only, nothing built. Include whether time felt slow or fast, decisions that seemed meaningless, information that was hard to find, and anything that felt unfair.
   - **A checklist for Reece's playtest:** the 10 things most worth his judgment.

   Close out with CHANGELOG and durations.

## Acceptance criteria

- [ ] Former staff open a read-only profile from every link; no hidden value appears (planted-value test).
- [ ] Every event link opens that event's message with its card.
- [ ] The agent's 120-month game finishes through the browser with no 5xx, with screenshots saved.
- [ ] Every bug fixed has a test; the report lists bugs fixed and not fixed, design notes and Reece's checklist.
- [ ] `make quickstart-saves` writes both saves, and they open in the game.
- [ ] `make check` green; `make e2e` passes; merged per CLAUDE.md §6 with the trailer `Milestone-Tag: m7c-done`.

## Manual check (Reece, after merge)

Read `docs/playtests/agent-m7c.md`, then play your 10-year run with its checklist beside you. To try M8's divisions and executives without playing to stage 3, open `quick-stage3`.

## Decisions made

- **Sub-task 0 (Reece, 2026-10-31).** v1 T2 is its own nightly test, marked `xfail(strict=False)` ("recorded miss: steady wins 10/10 after M8; rebalance in M15"); every other balance target stays a hard check, so `make check` is green again.
- **Former staff.** Departed people's rows were never deleted, but a poached person's true skills keep moving at their rival, so ranges computed later would drift. `former_staff` (migration 0021) freezes what the player saw at departure: displayed ranges, noticed tags, interests and work style once known, last role, level and unit, the reason and the rival. `sync_state` writes it when one of the player's employments that was on staff ends, from the state before the departure. The migration backfills past departures from what is stored (best effort for anyone now at a rival). `GET /people/{id}` still answers 404 for someone who left; the person screen then asks `GET /people/{id}/former` and shows the read-only profile, so every existing link resolves.
- **Event links.** New routes `/game/:save/inbox/:item` (any message, even off the first page or archived) and `/game/:save/events/:id` (the event's own message, found with `GET /events/{id}/item`). History rows with an event get an "Open the event" link, storyline steps link to their event, the COO briefing's event issues link to the event, and "While you were away" lists the events decided for you as links (`inbox_event_link`, also in migration 0021). Clicking a message now changes the URL to `/inbox/:item` (the older `?item=` still works).
- **Playtest agent.** It plays through the screens; it reads the API only to decide (what a player would read on screen) and to record each year. Its strategy: one B2B SaaS product built by the whole company; hires toward 4 + 2 a half-year while runway is 12 months or more; seed at once and each later round when allowed, taking the best valuation; a bridge when offered and a $1.5M SAFE at the largest cap whose hint reads "likely" when runway falls under 9 months; marketing $10,000 or 15% of revenue; a recruiter plan in month 6; a second product (Developer tools, its own team) once ARR passes $1M with 12 staff; a 4-month Holiday each year from year 3; every screen, four screenshots and a COO question at each year end; the saves manager once. Events: critical ones read for cash wording; others rotate between their choices, skipping a costly one when runway is short. Events and the COO use the mock adapter.
- **Hall of fame links.** The hall of fame links only to people (every record row) and products, never to events, so the former-profile fallback covers it; nothing was added there.
- **Overview burn (bug fix, API only).** The tile now reads the month's fall in cash from the ledger, as its breakdown and the P&L do. The sim snapshot's `monthly_burn_cents` still starts after the month's actions (an event paid before Continue is outside it); changing the sim would regenerate every golden snapshot, so the snapshot (History's burn chart) keeps its definition and the difference is a follow-up.
- **Burn note.** The tile's note projected gross costs beside a net burn; `OverviewOut.month_net_burn_cents` (month total less this month's revenue, never below 0) replaces it in the note.
- **e2e ports.** `TST_E2E_API_PORT` and `TST_E2E_WEB_PORT` override 8765 and 5175 so `make e2e` can run while `make playtest` holds them; both still default to the old ports. Two Playwright runs must not share `frontend/test-results` (each clears it), so run them one after the other.
- **Living market scoped to v1 (Reece, 2026-10-31).** `test_1_living_market` (M5 target 1, nightly) had failed on main since M8: breaches on 10/10 seeds. Every breach was in fintech, on every seed: PayPal's consumer share fell below half between Jun 2011 and Feb 2016, and Fiserv's enterprise share in 2017 (ratios 0.49–0.50), as the scheduled entrants arrived. No v1 category breached, so the target now judges the four v1 categories (b2b_saas, dev_tools, consumer_apps, cybersecurity), with a note that new-market disruption is intended; it is not xfailed. Result: 0/10 breaches, share ratios 0.58–1.65, launches per v1 category 1.00 (exactly the floor; 1.53 over all six categories).
- **Inbox folder filter (regression from sub-task 2).** Opening a message now changes the path, and the screen's error boundary was keyed by the path, so the inbox remounted and lost its Archived filter (`e2e/m4c.spec.ts` (c) caught it). The boundary ignores the `/inbox/:id` suffix, and `inbox` and `inbox/:itemId` are one route.

## Follow-ups

- **History's burn chart** (the sim snapshot's `monthly_burn_cents`) starts after the month's actions, so it can differ from the Overview tile in a month with an event paid before Continue. Fixing it in `snapshot_and_month_end_report` regenerates every golden snapshot; do it with the next golden regeneration.
- **Design and balance notes** for Reece and M15, ranked in `docs/playtests/agent-m7c.md`: inbox volume (676 unread by 2019), Holiday stopped every month after year 5, early cash pressure, large late event costs, seed dilution, unexplained quality drift, slow second-product launch, nothing pointing to the stage-3 levers, flat orgs with no cost, repetitive small events.
- **Runway versus the burn note** in a month with a large one-off cost (Runway "Profitable", note "projected $73,248"): decide whether runway should count costs already paid this month (formulas.md 14.1, M1c).
- **SAFE panel wording** when the cap rule blocks a raise that the angels would "likely" take; the block message could give the claimed share.
- **Launches per v1 category sit at exactly 1.00**, M5 target 1's floor; M15 may want headroom.
- **The playtest agent** could also try divisions, executives and support staff at stage 3 once Reece decides how a player should find them.
