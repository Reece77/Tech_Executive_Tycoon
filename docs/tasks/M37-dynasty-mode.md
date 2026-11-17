# M37: Dynasty mode, the second 30 years (v5, lane E)

**Goal:** the game can continue to December 2069. A standard campaign ends in December 2039 with a summary, and the player can carry on. Every system's data continues past its last entry by seeded rules: new eras, slowing process nodes, maturing markets. Rival leaders age and hand over, new rivals keep arriving, and founders can die, which triggers M36's succession and estate tax. Nothing changes before 2040.

**Formulas:** `docs/formulas.md` §52 (all), with §9, §13, §21, §26.4, §32.6, §33, §38, §45, §46 · **ADRs:** 0002, 0013 (stream `dynasty` 65), 0019 · **Research:** `docs/v5-research/dynasty-dossier.md` · **Outline:** `docs/v5-outline.md` · **Depends on:** M35b (`m35b-done`), M36 · **Lane:** E, alongside M38 and M41

## Reece's decisions (2026-11-14)

- **An optional dynasty mode to 2069,** with seeded eras beyond history.
- **The player plays the heir** (M36).

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m37-dynasty` from `main`.
- **Merges after M38 and M41.** Then merge `main`, re-parent the migration, re-record the M30 fixture with `--update-state-cache` and the reason, and re-run every guard.
- **M37 owns:**
  - new `backend/tst/sim/dynasty/` (the mode, the standard end and its summary, continuation rules, rival leaders' ageing and succession, mortality);
  - the post-2039 sections of `eras.yaml`, `nodes.yaml` and `tech_frontier.yaml`;
  - `dynasty.*` in `balance.yaml`;
  - the campaign summary screen and the new-game setting;
  - `tst/balance/m37.py` (new).
- **M37 must not edit:** M38's `vehicles/` and M41's `medical/`. Their seeded post-2025 curves continue by their own rules; if one stops before 2069, note it for that milestone or M43.
- **Shared files:** `balance.yaml`, the data files above (append only), `docs/formulas.md` (notes in §52 only), CHANGELOG, data dictionary, ADR-0013. Keep both sides.
- **CLAUDE.md §9's decision rules apply.** §52.5 target 1 (nothing moves before 2040, with dynasty mode on or off) is the guard everything answers to.

## Out of scope

Sandbox play after 2069; a third generation of new industries (eras only); rewriting any system's rules for the long run beyond §52.2's continuations.

## Sub-tasks (commit after each)

1. **Data and the mode:**
   - the new-game setting and switching an existing save;
   - `dynasty.*` keys with comments;
   - the post-2039 eras with windows, and seeded node and frontier successors;
   - stream `dynasty`, migration and data dictionary.
   - **Test:** loader validation; a standard game is unchanged to December 2039.
2. **The standard end** (§52.1): the December 2039 summary (Hall of Fame, legacy and dynasty scores), and the choice to end or continue; December 2069's final summary and read-only browsing.
3. **Continuations** (§52.2) for every series that ends before 2069. First, audit every data series with an end date or a last seeded entry, as a table in Decisions made: series, last entry, continuation rule. Then implement each rule.
   - **Seeded test:** the same seed continues the same way.
4. **Rivals age** (§52.3): leaders with ages, retirement and successors (and personality changes), entrants after 2039, relaunching failed brands.
5. **The founder's lifetime** (§52.4): mortality from 75, M36's succession and estate tax at once, the family-head and no-family endings.
   - **Hidden-value test:** no mortality draw reaches the API or a prompt.
6. **Performance:** a 2069 turn on the `full_integrator` save under the 500 ms guard on the CI runner, and the save under 400 MB. Use M30's retention rules, extended to the longer game, with identical results to 2039.
7. **API, CLI, e2e, balance and close-out:**
   - `tst advance --until 2069-12`;
   - **Playwright:** (a) a standard game's December 2039 summary offers to continue, (b) a dynasty game shows a post-2039 era arriving;
   - **a practice save** `pt-dynasty`: a dynasty game in December 2039 with a founder aged 68, two adult heirs, and a group across chips, cloud and cars;
   - **§52.5 targets** printed and recorded, tuning only `dynasty.*` (rule 1);
   - long runs dispatched on GitHub (rule 7; a 720-turn run is about twice a 360-turn one);
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Every game state and guard to December 2039 is identical to `main` before M37, with dynasty mode on or off (state-cache and golden checks).
- [ ] Every data series with an end before 2069 has a continuation rule (the audit table) and runs to 2069 without error on seeds 1–10.
- [ ] No mortality, succession or seeded-date draw reaches the API or a prompt before it happens (hidden-value test).
- [ ] §52.5 targets 2–5 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m37-done`.

## Manual check (Reece, after merge)

Load `pt-dynasty`, read the 2039 summary, and continue. Play a decade: watch a new era arrive, a rival's founder hand over, and decide when to step back.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
