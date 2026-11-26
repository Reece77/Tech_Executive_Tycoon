# M52: The editor and sandbox (v6, lane C)

**Goal:** the player can edit a starting company, rivals, markets and rules into a custom scenario, save and share it as a file, and play it. A dynasty or sandbox game can continue past December 2069 with no end and no score.

**Formulas:** `docs/formulas.md` §66 (all), with §30.2, §30.3, §52, §60, §63 · **ADRs:** 0002, 0008, 0013, 0024, **0026** (custom scenarios) · **Depends on:** `m51-done` and `m50-done` (both on `main`) · **Lane:** C, alongside M54 (lane A) and M55 (lane B)

## Reece's decisions (2026-11-21, 2026-11-22)

- **The editor and sandbox** in v6's second direction: edit a starting company, rivals, markets and rules into a custom scenario; sandbox play past 2069 with no score.
- Defaults for everything else.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m52-editor` from `main`.
- **Must not edit** M54's or M55's files. Merge `main` often.
- **CLAUDE.md §9's decision rules apply.**
- **M52 owns:**
  - new `backend/tst/sim/modes/custom.py` (applying a validated custom spec at the start) and the continuation past 2069 in `tst/sim/dynasty/`;
  - new `backend/tst/scenario_files.py` (outside `tst.sim`: reading, validating, canonicalising, hashing and writing scenario files in `<saves>/scenarios/`);
  - the editor's Pydantic schema and `editor.*` keys;
  - `eras.yaml`'s new `beyond_2069` list;
  - the scenario routes (list, read, create, update, delete, import, export, preview) and the Editor screen, and the Custom section of M51's Scenarios screen;
  - `tst/balance/m52.py` (new).
- **Categories are data:** the editor lists every category and incumbent from the loaded data, so M54's and M55's additions appear without editing M52's code. Whichever of the three merges last adds one custom-scenario round-trip test that uses a new category from the others.
- **No fixed merge order** with M54 and M55: the first ready merges first; the others then merge `main`, re-parent their migrations on the new head, and re-run every guard.
- §66.4 target 1 (nothing else moves) is the guard.

## Out of scope

Editing hidden values (ADR-0026, point 3); editing data files under `backend/data/` from the game; mods with code; an online scenario library; the 2000 and 1995 starts (their own milestone).

## Sub-tasks (commit after each)

1. **The schema and files** (ADR-0026, §66.2): the custom-scenario schema (a `scenarios.yaml` entry plus `overrides`, a closed list with ranges from `editor.*`), canonical YAML and its SHA-256, the files in `<saves>/scenarios/`, import and export with clear refusals; migration for the mode record's scenario hash; data dictionary. **Property test (Hypothesis):** any valid spec round-trips (write, read, canonicalise) to the same hash; any field outside its range is refused.
2. **Applying a custom start** (§66.1) through §63's start code: the company, rivals present or removed, rival quality, markets, macro start, rules and a goal. **Test:** every `scenarios.yaml` entry opened as a custom spec with no overrides starts an identical game (§66.4 target 2).
3. **Preview and difficulty:** the start month's summary and, on request, the sensible script on 3 seeds in the background (no turn is saved).
4. **The Editor screen:** sections for company, rivals, markets, world and rules; every field shows its range; refusals show the reason; save, save as, export, import; start a game from the editor. The Scenarios screen's **Custom** section with each scenario's best result (kept apart from M51's results).
5. **Sandbox past 2069** (§66.3): "continue in sandbox" at December 2069 and a sandbox with no end; continuation series year after year; the `beyond_2069` eras; overflow guards (every money column 64-bit; the 2100 economy at least 1,000× below the limit). **Test:** a 2069 save continued to December 2100 on seeds 1–3 with no error and every money value within its column.
6. **API, e2e, balance and close-out:**
   - **Playwright:** (a) open "The EV maker", double its cash, save as a custom scenario, start it, see the cash; (b) export a scenario and import it back; (c) continue a 2069 save in sandbox and advance a year;
   - the `determinism` job's digests include one custom scenario (§66.4 target 3);
   - **§66.4 targets** printed; the 2100 turn time measured with `make check-timing`'s method (runner-adjusted);
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] A normal game, every scenario in `scenarios.yaml` and a dynasty game to 2069 play exactly as before (state cache, golden snapshots).
- [ ] Every `scenarios.yaml` entry round-trips through the editor to an identical game (state hash at month 12, seeds 1–3).
- [ ] A custom scenario gives the same state hash at month 24 on Windows and Linux (the `determinism` job).
- [ ] The editor never shows or sets a hidden value (a test over the editor's schema and routes).
- [ ] A sandbox game runs to December 2100 on seeds 1–3 with no error and within 550 ms a late month (runner-adjusted).
- [ ] Custom and sandbox games stay out of the Hall of Fame, achievements and M51's results.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m52-done`.

## Decisions made

(filled in by the session)

## Follow-ups

(filled in by the session)
