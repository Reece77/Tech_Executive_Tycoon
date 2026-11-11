# M23c: Playtest 5 fixes and the interface (lane C)

**Goal:** fix what Reece's v3 playtest found hard to use, and make the shell feel like Football Manager: bars that stay put, critical decisions you can research before making, and screens that say how to proceed rather than only what's missing. Make the practice saves realistic.

**Playtest:** `docs/playtests/reece-playtest-5.md` · **Formulas:** §18, §31–§37 (display only) · **Depends on:** M22 (`m22-done`) · **Lane:** C, alongside M23a and M23b

## Lane

- Its own session and branch (`m23c-interface`). Merges whenever ready, before M23b.
- **M23c owns:** the front end (`frontend/src/`), API view builders and read-only endpoints for display, the practice-save tools (`tools/e2e_*_save.py` and the helpers they call in `tst/balance/` for fixtures only), `fix-fixture-reveals`'s change (already merged into this docs branch), glossary entries.
- **M23c must not edit** simulation rules (`backend/tst/sim/`) except read-only helpers for display; anything that needs a rule change goes to M23a as a note. M23b's strategies and targets are off limits.
- **CLAUDE.md §9's decision rules apply.**

## Sub-tasks (commit after each)

1. **The shell:** the top bar (date, cash, energy, stress, Continue) and the side navigation stay visible while the working pane scrolls independently, at every screen width.
2. **Look before you decide:** a critical event can be **set aside** to browse any screen read-only (Continue stays blocked until it's answered), with a persistent banner linking back to it; the event card links to the screens that matter for it (a mine's panel for a mine crash, the product for a recall).
3. **Exploration:** clicking a block opens a **licence confirmation** (cost, term, what you get) instead of buying at once; every greyed-out stage says **how** to unlock it ("drill 18 more holes (40 in total), then re-estimate"); a **progress line** toward the next resource category; a **"Your blocks and projects"** view across all regions; desk-study results kept per region and commodity, so running one doesn't recolour the map you were looking at.
4. **The group:** **Found a subsidiary** on the Group screen (Finance → Group), linked from Mines; pitches and capital requests link to the screen where they're answered; a **capital-actions history** (stake sales, carve-outs, spin-offs, buyouts: date, proceeds, ownership before and after, NCI, value created); subsidiaries' **quarterly updates** in their CEO's voice, each ending with a question the player can answer (advice that sets a nudge on the mandate).
5. **Chips, wafers and foundries (wording):** "wafer contract" becomes **foundry contract**; the wafer plant makes **blank wafers**; a chip's cost shows **wafer material** and **foundry processing** separately; a chip used inside the group's devices shows "**used in** N phones" instead of no revenue; "used" figures on own-supply lines get units and a tooltip.
6. **Commodities planning:** a planning view per commodity: need over the next 12 months from current sales and plans, which products drive it, and how much offtakes and own supply cover.
7. **Explain and glossary:** NPV, IRR, reserves, grade and yield in the glossary; Explain on a mine's NPV and cost per unit, a fab's cost per good die, and the v3 screens (Infrastructure, Hardware, Research, Group, Mines, Refineries, Fabs, World), as M25's follow-up asked.
8. **Angel stakes:** show the last-round value and an **estimated value range** from the startup's public growth since its round, labelled as an estimate, beside the last-round mark.
9. **Realistic practice saves:** stage-3 and larger fixtures get a believable team (a CTO, product and sales staff, the specialists the scenario needs); a **chip company with its own fab** fixture; `mature` stops claiming chips it doesn't have; every fixture's People and Org screens open (a fixture test opens People, Org and the fixture's main screen for each mode).
10. **e2e and close-out:** Playwright flows for the sticky shell, setting aside a critical event, the licence confirmation and the planning view; CHANGELOG; README index row.

## Acceptance criteria

- [ ] The top and side bars stay visible on every screen while content scrolls (e2e).
- [ ] A critical event can be set aside to browse read-only and answered later (e2e).
- [ ] Every greyed-out action on the Exploration, Mines, Refineries and Fabs screens says how to unlock it (a scan test over the API's reasons).
- [ ] Every practice-save mode opens People and Org (fixture test).
- [ ] Golden snapshots unchanged (no rule changes).
- [ ] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m23c-done`.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
