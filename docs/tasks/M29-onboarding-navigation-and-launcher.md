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
- [ ] A new game shows only stage-1 screens, and each later screen appears with an unlock item when its condition holds (tests and e2e).
- [ ] Every screen, person, product, facility and rival can be reached from the palette (e2e).
- [ ] Golden snapshots unchanged; no simulation rule changed.
- [ ] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m29-done`.

## Manual check (Reece, after merge)

Pull `main` in GitHub Desktop, then double-click **Tech Startup Tycoon** in the repository folder. Start a new game and play its first year with the checklist, then press Ctrl+K and type a person's name.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
