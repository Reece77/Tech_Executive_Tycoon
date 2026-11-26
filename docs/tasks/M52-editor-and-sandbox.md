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

1. **A custom game is a scenario game.** `GameMode.kind` stays `scenario`, `scenario` is `custom/<slug>` (never a `scenarios.yaml` key) and the new `scenario_sha256` (the canonical text's SHA-256) marks it custom (`GameMode.custom`). Every engine branch that serves scenarios serves it unchanged, so an unedited scenario plays identically (target 2); the entry joins the game data beside `scenarios.yaml`'s (`custom.with_custom`; a save's own copy through `tst.db.custom_io.data_for_custom`, beside M25's mod seam in `data_for_save`).
2. **Target 2's "identical"** compares M30's full-state digest with the custom game's mode record read as the original's (its key, hash and empty growth changes: the only fields that name it custom), every month from the start to month 12.
3. **The file** is a historical entry plus `overrides`, `opened_from` and `format: 1`; `goal` and `deadline` may both be left out (open play, no verdict); `length` gains `endless`. Company name lives in `overrides.company.name` (an entry has none). Canonical text: `model_dump(exclude_defaults)` as block YAML, keys sorted, LF, `format` always written; the hash covers the name (`key`), so an imported copy under another name hashes differently but is otherwise equal.
4. **Validation is two-stage:** the schema (types, closed fields, `extra=forbid`, printable names) at parse; ranges and references (`editor.*`, categories, roles, incumbents, nodes in volume by the start year, lenders, cities, goal fields) in `custom.refusals`, every reason named. Hypothesis found that a control character in a name does not survive YAML: names and texts must be printable.
5. **Markets:** `market_mult` multiplies the category's national and regional addressable markets in the start month; `growth_delta` is kept in `GameMode.growth_delta` and added in `research.eras.annual_growth` every month (never below 0). Cars, robots and telecom services recompute their markets from their own data every month, so they are refused as not editable. M54's and M55's categories appear from the data; a new one that recomputes its market each month needs adding to `custom.computed_markets` (a follow-up for whichever merges last).
6. **World:** history is the same on every seed through 2025, so the macro start (confidence, base rate) and commodity price levels are editable only from `editor.macro_from_year` 2026, applied to the month the start reads; 20.1's and 33.1's AR(1) steps go on from there.
7. **Rivals** are incumbents.yaml's by name (rival key (0, index)); one gone by the start year (failed or bought) is left as it is. Removal is Sandbox's (`fail_rival`); cash x is against common equity in the brought-forward balances; quality + is clamped to 0-100.
8. **Added rivals** are 52.3's entrants: M37's entrant body moved into `tst.sim.dynasty.rivals.enter` (behaviour unchanged: M45's fixture) and drawn on stream `scenario` (no new stream, ADR-0026) at keys 1,000,000 + category index x 100 + k, through `scenarios.scenario_draw` (the stream's one call site); rival key (20, category index, k), clear of the tags in use and of M54's and M55's likely next ones.
9. **Facilities:** fabs only, the one start builder (M51's `_running_fab`); data centres, plants and mines have none (follow-up). Debt is the loans list; its range is on the summed principal.
10. **Start years** `editor.start_years` 2008-2030 (M50's 2008 world to M51's latest start), blanks offered for 2008 and 2010.
11. **Preview** runs synchronously (it plays the dormant world to the start, up to a minute for 2030); the **difficulty** estimate runs in a background thread: M51's sensible script for the scenario it was opened from, v1's steady otherwise, on `editor.preview_seeds` (1-3) for at most `editor.preview_months` (120), rated with M51's bands scaled from ten seeds; one job a canonical text.
12. **Results and comparisons:** custom results go to `<saves>/results/<profile>.custom.json` (with the file's hash); a custom or endless game earns no achievements (`why_none`) and the Saves list shows mode `custom` (or `sandbox`) with no score.
13. **Sandbox past 2069:** `ContinueSandbox` only from `dynasty_end` (it reopens the game, length `endless`); a Sandbox may begin endless (`sandbox.endless` on `POST /api/saves`); an endless game never closes. `dynasty.beyond` (start 2070, end 2120, 4 nodes): research baselines by decade and category maturity extended to 2120 at load (a later year reads the last rate: no bound below 9999), four more node successors (atomic5-8, windows 2076-2117), and eras.yaml's `beyond_2069` (five eras, windows 2070-2116) appended after every era and in play only from January 2070 (`levels.in_play`).
14. **The economy at 2100** is measured as every company's revenue in 2100 (credits on revenue accounts over the year); "every money value within its column" as the largest integer anywhere in the state or the ledger balances against int64. Every money column is an INTEGER (tested; the LLM logs' real API cost is a float and not game money).
15. **Rule 2 (script lacks behaviour):** M37's reference arm (M43r's guard) shifted `dynasty.start_year`/`end_year` only; it now shifts `dynasty.beyond`'s years too, so the arm stays valid. M37's unit tests that bounded dynasty-years data (eras to 2065, exactly `count` successors) are narrowed to the second wave and `count + beyond.nodes`: M52 extends both by design. M45's and M37's digests leave out `GameMode.scenario_sha256` and `growth_delta` (None/empty in their games), as M51 did for `challenges`.
16. **The API's name guard** forbids any field named `capacity` (products' hidden sales capacity), so a fab's wafer starts travel as `wafer_starts` (`FabSpec` aliases; the files keep `capacity`).
17. **E2E (c)** moves a new dynasty save to January 2070 directly (as M37's flows do): the flow is about continuing, not the world.

18. **Rule 6 (turn time at 2100):** profiling a 2101 month found telecom demand's growth factor recompounding every month since 2026 on every call (11% of the month, growing with each year played): now kept as running products (identical results, tested against the old loop): 736 -> 544 ms adjusted locally, 700 -> 610 ms on CI. What remains is spread over every phase (365 companies by 2100 against about 170 in 2069), the cause of M37's own 2069 known miss (535 ms, bound 550).

19. **Reece's ruling (2026-11-26)** on target 4's two misses: both are known misses (`tst/balance/known_misses.py`). `M52.2100_month` (owner v6 performance, as M37's 2069 month: the same cause) is known up to 650 ms adjusted, and the raw 1.0 s worst-month check is not applied at 2100; `M52.economy_2100` (owner M57, the v6 balance pass: mines' sales compounding after 2069, governed by no M52 key) is known while 2100 revenue stays at least 250x below int64. The hard guard stays: every value within int64.

### Readings (66.4, printed by `tools/m52_targets.py` and `tools/m52_save.py`)

| Target | Reading | |
| --- | --- | --- |
| 1. Nothing else moves | M30's state cache and golden snapshots unchanged (`make check`); M45's dynasty fixture identical for all 720 months on seeds 1-3 (locally on the way to 2100, and CI weekly-m45) | met |
| 2. Round trip | 33/33 (11 scenarios x seeds 1-3) identical every month to month 12 | met |
| 3. Determinism | the edited EV maker's 24 months identical on Linux and Windows (`determinism` job, every push) | met |
| 4. Long play: errors | seeds 1-3 reach December 2100, active, no error | met |
| 4. Long play: within the column | largest integer 1.17e17 / 1.38e17 / 1.55e17 (79x / 67x / 59x below int64) | met |
| 4. Long play: economy 1,000x below | 2100 revenue 2.09e16 / 2.46e16 / 2.57e16 cents (442x / 375x / 359x below); 2069: 2.4e15 (3,786x, seed 1). Commodity sales dominate (2.4e17 of the 2100 save's cumulative revenue against 4.5e16 of subscriptions) | **known miss** `M52.economy_2100` (M57, within 250x) |
| 4. Long play: turn time | a 2101 month 610 ms adjusted on CI (1,118 ms raw, worst 1,496 ms; runner x1.83), 544 ms locally | **known miss** `M52.2100_month` (v6 performance, within 650 ms) |

## Follow-ups

- Start builders for data centres, plants and mines, so the editor's facilities match 66.1's list.
- The Editor screen edits the numbers of existing staff, product and research lines; adding or removing lines, segments, loans and fabs is in the schema and API but not yet on screen.
- Market overrides for categories whose markets follow their own data (cars, robots, telecom, and any of M54's or M55's that do).
- The round-trip test with a new category from M54 or M55 (the brief: whichever of the three merges last).
- A cache of the dormant world by seed and start year would make the preview and custom starts much faster.
