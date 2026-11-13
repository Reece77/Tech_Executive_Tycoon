# M29: Onboarding, navigation and the launcher (v3.5, lane C)

**Goal:** the game is easy to start and easy to find your way around. Double-click to play, with no PowerShell. Systems appear as the company reaches them. A guided first year. A "What next" panel. An inbox that separates what needs you from what's for reading. A grouped side bar and a Ctrl+K command palette for about 40 screens.

**Formulas:** `docs/formulas.md` §42 (all), with §12, §17.3, §23.1 and §40.4's `digest` kind · **ADRs:** 0001, 0007 · **Roadmap:** `docs/roadmap.md` Phase 2 ("onboarding and the UI pulled together", "a one-click launcher") · **Depends on:** M23b (`m23b-done`) · **Lane:** C, alongside M27a (lane A) and M28 (lane B)

## Lane

- Its own session and branch (`m29-onboarding`). **Merges first** if it is ready, since it has no rule changes; golden snapshots must stay unchanged.
- **M29 owns:** the front end's shell, side navigation, command palette, Overview, inbox layout, Main menu and Saves screens, Settings' interruption options; new read-only `backend/tst/sim/unlocks.py` and a read-only "What next" builder beside `coo.py`; API read-only endpoints for them; `tools/launcher.py` and the Windows shortcut; README's "How to play" section.
- **M29 must not edit** simulation rules (`backend/tst/sim/` beyond the two read-only modules), M27a's Automation screen and digest, or M28's World news and company pages. The inbox's Digest tab reads kind `digest` and appears once M27a's items exist; the side bar's groups include "Automation" (M27a adds the screen) and "World".
- **No new dependencies** (ADR-0001). FastAPI's static files (Starlette, already present) serve the built front end.
- **CLAUDE.md §9's decision rules apply.**

## Out of scope

Rules for automation (M27a) and the world (M28); a macOS or Linux launcher (Windows only; others keep `make dev`); a packaged installer or auto-update (follow-up); performance (M30).

## Sub-tasks (commit after each)

1. **The launcher** (§42.5): `tools/launcher.py` (checks for `uv`, installs dependencies, builds the front end when missing or stale, starts the API serving it on one port, opens the browser, writes `saves/launcher.log`, shows a plain error page when a step fails); `Tech Startup Tycoon.cmd` and a "make a desktop shortcut" step; the Main menu's Continue and the Saves screen's last-played dates and Back up. **Test:** the launcher's steps with a fake `uv` and a fake browser; an e2e flow against the single-port server.
2. **Progressive unlocking** (§42.1): `tst.sim.unlocks` (pure, read-only), the hidden nav items, the `unlock` inbox item and toast, a guide page per system, "Show everything", and older saves unlocking what they use. **Test:** each condition on fixtures; a save from before M29 shows every screen it already uses.
3. **A guided first year** (§42.2): the Getting started checklist from state, the chief of staff's notes, dismiss.
4. **What next** (§42.3) on the Overview, and **one Overview** (§42.4): KPI tiles with Explain, runway, What next, the digest's attention lines once M27a lands, and alerts.
5. **The inbox and navigation** (§42.4): inbox tabs (Needs you, Digest, News, Everything) with filters; the grouped side bar; the Ctrl+K palette for screens, people, products, facilities and rivals; recent items; breadcrumbs.
6. **Interruptions** (§42.4): Settings for which severities stop Continue and Holiday (critical always).
7. **e2e and close-out:** Playwright flows for (a) a new game's first unlock and the checklist ticking, (b) the palette jumping to a person, (c) the inbox's Needs you tab, (d) the launcher's single-port server opening the Main menu; README's "How to play" rewritten around the shortcut; CHANGELOG; README index row.

## Acceptance criteria

- [ ] On Windows, double-clicking the shortcut on a fresh clone installs, builds and opens the game, with no other step (manual check by Reece, plus the launcher's tests).
- [x] A new game shows only stage-1 screens, and each later screen appears with an unlock item when its condition holds (tests and e2e).
- [x] Every screen, person, product, facility and rival can be reached from the palette (e2e).
- [x] Golden snapshots unchanged; no simulation rule changed.
- [x] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m29-done`.

## Manual check (Reece, after merge)

Pull `main` in GitHub Desktop, then double-click **Tech Startup Tycoon** in the repository folder. Start a new game and play its first year with the checklist, then press Ctrl+K and type a person's name.

## Decisions made

1. **Which stage opens which screen** (42.1 names the stage without a table). Always shown (the stage-1 set): Inbox, Overview, History, Saves, Settings, People, Recruitment, Org, Products, Markets, Competitors, Finance (and its tabs). Stage 2: Offices, Research, Rankings. Stage 3: Infrastructure, Hardware. Stage 4: Refineries, Fabs. Stage 5: Group. Facts open them earlier: Offices with a second open office; Research with a research project; Infrastructure with a facility; Hardware with a units-selling product; Exploration with a desk study or licence (or "Explore for minerals"); Mines with a mine or a project that has a feasibility study (any level) or a permit; Refineries with a refinery or a mine; Fabs with a fab or a chip product; Group with a subsidiary; World when the group's live products sell in countries of two blocs or the group uses a commodity a biting export rule restricts. Exploration, Mines and World have no stage of their own, as §42.1 lists only facts for them.
2. **The stages are constants in `tst/sim/unlocks.py`, not balance keys:** they are UI gates, not tunables (marked `tunable-exempt`), and `balance.yaml` belongs to lane B while M23b runs.
3. **What was announced is stored as the `unlock` inbox items themselves** (link `guide`, the system's stable id), so there is no migration (none can clash with lane B's). A screen shows when its condition holds now or it was ever announced, so it never hides again. Items are written for conditions that become true across a turn **or an action** (both transactions call `tst.db.unlocks.announce`); a save from before M29 already meeting a condition shows that screen without an item.
4. **Interruptions at critical only:** Continue answers each open major event with its first choice (the existing `ChooseEvent` action) just before the turn, the same choice phase 1 makes on a holiday (16.3); no simulation rule or turn code changed. The event is recorded as answered rather than `auto`. It is also a holiday's default stop. Continue until (M15b) is unchanged and still stops for a major event (follow-up 2).
5. **Settings live in `saves/ui_settings.json`** beside the table views (shared by every save, never in a save file): Show everything, Getting started, Interruptions, and the save ids whose checklist was dismissed.
6. **The inbox's company filter is not built:** inbox rows carry only the player company's id (the holding company's items are merged in, M16), so there is nothing to filter on without a new column and migration (follow-up 3). The area and kind filters are built.
7. **Digest:** the Digest tab appears once an item of kind `digest` exists; the Overview shows the latest digest's title and first lines as its attention lines until M27a defines the digest's structure. The Automation group stays hidden until M27a adds its screen; §40.2's `stop_for_approvals` is M27a's.
8. **Getting started's steps from state:** hire a first engineer = an active non-founder employee whose role is a builder; a product's team = the root or a unit assigned to a product; the launch bars = a product launched or one in development with no launch problem; a seed round = any closed priced round; delegation = a seat with authority on (automating an area joins once M27a exists). The notes' speaker is the COO the briefing uses (17.3), else "your own notes".
9. **What next's order:** a critical event set aside, else a covenant in breach (the most urgent risk; short runway arrives through the briefing's runway issue), then waiting proposals and pitches, the briefing's issues, and this month's unlocks; five at most.
10. **The launcher** listens on port 8770 (so `make dev`'s 8000 can run beside it), runs `uv sync` every launch (quick when current), installs front-end packages when `node_modules` is missing or older than the lockfile, rebuilds `frontend/dist` when any front-end source is newer than it, uses `corepack pnpm` when pnpm itself is missing, and needs Node.js 22 once (the error page says so). A second double-click while the game runs just opens the browser. The `.cmd` finds a missing uv itself (Python comes through uv) and opens `tools/launcher_missing_uv.html`. `.gitattributes` keeps `*.cmd` in CRLF.
11. **The palette's index:** open screens (with the Finance and History tabs), the player company's active and notice-period staff, the group's products, facilities and mines, and living rivals. Recent items are kept in the browser (`localStorage`), like a table's last view. Keys 1-9 and 0 are unchanged.
12. **M23c's e2e flow** clicked the side bar's "People" by text; a nav group is titled People now, so it clicks the People link by role (the same link; the test is not weakened).
13. **The system ids in `tst/sim/unlocks.py`** are stable inbox link ids, not tunables, so each line carries `# tunable-exempt: stable id`. `GET /api/settings/ui` and the tables `PUT` keep M7b's `{"tables": ...}` response (onboarding has its own endpoint), so M7b's test stands unchanged.
14. **Two local-only failures that also fail on a clean `main` (§9 rule 3, not M29's).** The full local run (`-m "not timing and not weekly"`, 2026-11-12) failed these two; the `check` shards on this branch passed. A worktree of `main` at `dc746ea` gave the same result:

    | Test | m29-onboarding | main `dc746ea` |
    | --- | --- | --- |
    | `tests/property/test_fab_invariants.py::test_a_fab_keeps_its_books` (`build_fab refused`, n16, east_asia, 2023) | fail | fail |
    | `tests/balance/test_m22_balance.py::test_39_4_targets` (target 7) | fail | fail |

    M29 touches neither geopolitics nor balance. The fix belongs to lane B's M23b (running), which owns balance; nothing was added to `known_misses.py`. Turn-time budgets alone (`-m timing`): 6 passed, 1 skipped.
15. **M9's e2e flow (c) and Continue's 409 (§9 rule 5).** PR #48's e2e run on `9c33218` refused flow (c)'s Continue with 409. The trace's body was `save_busy`: the advance went out 82 ms after the Bangalore search's POST started and while that 178 ms write still held the save (a second writer is refused at once, M6 sub-task 0). The flow pressed Continue without waiting for the search to save. It now waits for that POST's response, as M1c's flows already wait for the new search row. M29's unlock check adds about 0.4 ms to a write (measured on this save), so it did not cause the race. The `KeyError: 3` in the server log is a separate bug: `event_links` looks up a person who has left (M7c's former-employee flow). It appears 4 times in `main`'s green e2e run too, so it is listed under Follow-ups. `tests/integration/test_m9_continue.py` plays Continue on the M9 save after a Bangalore search under both Interruptions settings, and checks that a Continue during a write is refused as busy and retryable, then plays once the write finishes.

## Acceptance criteria (how each was verified)

- Double-click on a fresh clone: `tests/unit/test_launcher.py` (fake uv, pnpm, server and browser: a fresh clone installs, builds, serves and opens; no rebuild when current; missing uv or Node, a busy port and a silent server give the error page; a second launch reuses the server; the shortcut). The e2e suite starts the real launcher (`--skip-install --no-browser`) as a server, which built `frontend/dist`, and flow (d) opens the Main menu from it. Reece's manual check remains.
- New game shows only stage-1 screens; later screens unlock with an item: `tests/unit/test_m29_unlocks.py` (every condition on fixtures, monotone in stage as a Hypothesis property), `tests/integration/test_api_onboarding.py` (items once, by a turn and by an action, none for a pre-M29 save), e2e flow (a).
- Palette reaches every screen, person, product, facility and rival: e2e flow (b) (a person and a screen), the palette index test, and `src/lib/m29.test.ts`.
- Golden snapshots unchanged; no simulation rule changed: `uv run pytest tests/golden` passes untouched; `backend/tst/sim/` gains only `unlocks.py` and `whatnext.py`.
- `make check` and CI `e2e`: see the pull request.

## Follow-ups

- `tst/api/event_links.py:92` raises `KeyError` when an event names a person who has left (`state.person`): `GET /events` returns 500 on such a save (M7c's former-employee flow; on `main` too). Skip people no longer in the state, or link them to their former-employee profile.

1. Reece's manual check of the shortcut on a fresh clone (the brief's Manual check).
2. Continue until (M15b) could honour Interruptions too (it stops for a major event as before).
3. An inbox filter by company needs the originating company on `inbox_item` (a migration).
4. M27a: automation areas in What next, the Automation group's screen, digest attention lines from the digest's structure, and `stop_for_approvals` in Interruptions.
5. A packaged installer and auto-update (out of scope here); macOS and Linux launchers.
