# M7b: History, saves manager, Holiday, tooltips, column views and "Ask my COO"

**Goal:** v1 is finished, so Reece can play a full 10-year run without a blocking bug. He can look back over his company's history, manage his saves, skip quiet months with Holiday, see why every important number is what it is, keep his own table layouts, and ask his COO what to worry about.

**Spec sections:** §4 (time-scale controls), §12 (other LLM uses), §13 (History screen, UX rules), §17 (M7) · **ADRs:** 0004, 0005, 0006, 0007, 0009, 0014, 0015, 0018 · **Formulas:** `docs/formulas.md` §17 (all) · **Wireframes:** `docs/wireframes.md` (M7b screens) and `docs/wireframes/source/History.dc.html`, `Saves.dc.html`, `Holiday.dc.html`, `Coo.dc.html` · **Depends on:** M7a (`m7a-done`)

## Context

M7 was split in two (Reece, D1a): M7a did speed and balance; M7b finishes v1. Reece's decisions (2026-10-30): Holiday, which the spec lists in §4 but no milestone scheduled, is in M7b; Sandbox mode and the company score wait for v2; "Ask my COO" is built last and cut first if the milestone runs long (D2a). The spec's v1 acceptance for M7 is a full 10-year run without a blocking bug, so this milestone ends with a scripted 120-month run through the API and a Playwright pass over every screen.

What already exists and is extended, not rebuilt: the main menu's saves table (`SavesTable`), periodic and pre-migration backups (`tst/db/backup.py`), the `ironman` difficulty, the Space/Enter hotkeys (`useGameHotkeys`), `turn_snapshot`, `decision_log` (with `source` and `actor_id`), inbox items (including `month_end`), events, storylines, and the LLM settings file next to the saves (`saves/llm_settings.json`).

## Out of scope

Sandbox mode and the company score (v2). Scenario goals. Anything from v2 or v3. New balance tuning beyond what a bug fix needs: if the 10-year run shows a balance problem, record it under Follow-ups. Importing and exporting save files (the saves are plain files in `saves/`).

## Sub-tasks (commit after each)

0. **Carried from M7a:** any open M7a follow-up that blocks play. Refresh `tests/durations.json` after each sub-task; add a third CI shard if any job passes 17 minutes (rule kept from M6).
1. **Holiday** (§17.1): keys `holiday.max_months`, `holiday.default_months`, `holiday.default_stop`, `holiday.stop_runway_months`. Behaviour:
   - Holiday runs as a job the front end can follow: months done, the current date, and a Stop button. Each month is its own transaction. A second write while it runs gets the existing 409 `save_busy`.
   - The `holiday_summary` inbox item.
   - CLI: `tst holiday --save NAME --months N --stop major`.
   - The determinism test: a 12-month holiday equals 12 Continues.
   - A test for each stop reason.
   - Front end: a Holiday button beside Continue (shortcut `H`) opening the dialog, and a progress strip in the top bar while it runs.
2. **Saves manager.** A Saves screen, reached from the main menu and from the left nav, that replaces the main menu's table:
   - **Columns:** company, scenario, difficulty, game date, turn, last played, file size, game state (active, bankrupt, founder removed).
   - **Actions:**
     - **Open** and **rename** (the company name stays; the save's display name changes).
     - **Duplicate** ("save as").
     - **Delete**, with a confirmation that names the save.
     - **Restore from backup:** lists the periodic and pre-upgrade backups with their dates, and restores one as a **new** save named "Company (restored, Mar 2013)", never over the original.
   - **Ironman saves:** no duplicate and no restore. Delete is allowed.
   - **Busy saves:** rename, duplicate, delete and restore each refuse with 409 `save_busy` while the save is busy.
   - **API, CLI and tests:** routes for each action; CLI `tst saves list|rename|duplicate|delete|restore`; tests for each action, including the Ironman refusals.
3. **History screen** (§17.2), in the left nav, with four tabs:
   - **Timeline:** search, the filters and month lines, as a TanStack table with paging.
   - **Charts:** the KPIs and product series, with 1-year, 3-year and all ranges.
   - **Storylines:** their time lines.
   - **Hall of fame:** the records table in §17.2.

   API routes return only what the player could see: shown ratings, never true values. Add a test that plants hidden values and asserts they don't appear in any History response.
4. **Tooltips** (spec §13: "every number has a tooltip explaining its drivers"), two kinds:
   - **Definitions:**
     - `backend/data/glossary.yaml` (term id → one or two sentences, plain words), validated at load and served by one API route.
     - Every KPI label and every table column header shows its definition on hover or focus.
     - A front-end test fails if a column or KPI id has no glossary entry.
   - **Drivers:** the API returns a `breakdown` (a list of `{label, amount}` and an optional note) next to these numbers, built by backend code. The front end only displays it.
     - **Top bar:** cash (last month's change by revenue, payroll, other costs, financing, event effects) and runway (cash ÷ burn, or "not burning").
     - **Overview:** MRR and ARR (by product), burn (by cost line), headcount (by unit), average morale (the company-wide average of the morale terms).
     - **Product:** quality and market share (the inputs §11 already exposes in words).
     - **Person:** morale reuses the existing breakdown; salary against market rate, if the player can see it.
     - **Finance:** each statement line gets its definition only.
5. **Saved column views** (spec §13: "every table supports saved column views"):
   - One shared hook gives every TanStack table: column visibility, order and sort; named views; a built-in "Default" view that can't be deleted; and the last view used.
   - **Storage:** per table id, in `saves/ui_settings.json` through an API route. That file sits beside the saves and is shared across them, like the LLM settings, and it is never written into a save file.
   - **Tables at minimum:** People, Recruitment candidates, Hiring plans, Products, Market, Competitors, Cap table, History timeline.
   - **Shortcuts:** add `H` for Holiday and `/` to focus search on the current table. Show the full shortcut list with `?`.
6. **Ask my COO** (§17.3): keys `coo.max_question_chars`, `coo.max_answer_words`, `coo.keep_answers`.
   - **Engine:** the briefing (pure, with a unit test for each issue).
   - **LLM:** the request through the existing adapter interface, extending `MockLLMAdapter` and `TemplateAdapter`; the offline reply; the budget meter.
   - **Storage:** a `coo_answer` table (migration and data dictionary).
   - **API:** routes for the briefing, asking, and the last answers.
   - **Screen:** a COO panel opened from the top bar.
   - **Test:** extend the hidden-value prompt test to COO prompts.
   - If the milestone is running long, cut this sub-task, record it under Follow-ups, and finish the rest.
7. **The 10-year run and close-out:**
   - **Scripted 10-year run (integration, nightly):** a new game played for 120 months through the API with Holiday and the M3a earn-and-burn decisions. It answers critical events with their first choice, opens every screen's routes each year, and asserts no 5xx response, a balanced ledger and an unchanged save after a reload.
   - **Playwright:**
     - (a) A 6-month Holiday stops on a major event, and the summary appears.
     - (b) Rename, duplicate and restore a save, and find the restored copy.
     - (c) Search History for a hired person and open their profile from the entry.
     - (d) Hover a top-bar number and see its breakdown.
     - (e) Save a People view, reload, and find it still selected.
     - (f) With the mock adapter, ask the COO a question and see an answer.
   - **Close-out:** CHANGELOG, data dictionary, durations and shard times; add the README index row for M7b (and M7a if it's missing).

## Acceptance criteria

- [ ] A Holiday of N months gives the same save as N Continues; it stops for every §17.1 reason (a test each); Stop finishes the current month and rolls nothing back.
- [ ] Saves can be renamed, duplicated, deleted and restored from a backup as a new save; Ironman refuses duplicate and restore; busy saves return 409.
- [ ] The History screen shows the timeline with search and filters, month lines, charts, storylines and the hall of fame; no History response contains a hidden value (planted-value test).
- [ ] Every KPI label and table column header has a glossary definition (front-end test); the listed numbers show a driver breakdown served by the API.
- [ ] Every listed table has saved views that persist across reloads and across saves.
- [ ] The COO briefing works offline; questions are answered within the budget, by the mock adapter in tests; no COO prompt contains a hidden value. (Or the sub-task is cut and recorded.)
- [ ] The scripted 120-month run passes: no 5xx, the ledger balances, and a reload changes nothing.
- [ ] `make check` green; `make e2e` passes every flow; merged per CLAUDE.md §6 with the trailer `Milestone-Tag: m7b-done`.

## Manual check (Reece, after merge)

This is the spec's v1 acceptance. Play a full 10-year run (120 months) on any scenario, using Holiday as you like. Note any blocking bug, any number whose tooltip doesn't explain it, and whether the History screen tells your company's story. Also note whether a two-person bootstrap team's launch (about month 21 after M7a) feels too slow.

## Decisions made

- **Branch.** Built on `m6-events-i6h2de`, the session's designated branch, reset onto `main` after `m7a-done` (its earlier history was all merged).
- **Sub-task 0.** No open M7a follow-up blocks play (they are balance and v2 notes), so nothing was carried.
- **Holiday (17.1).** `tst/holiday.py` runs months as ordinary `repository.run_turn` calls. The API runs it as a background job in the API process (`POST/GET /holiday`, `POST /holiday/stop`); `repository.reserve` holds the save for the whole holiday, so every other write gets 409 `save_busy` between months as well as during one, and Stop is checked after each month (the month in progress always commits). Stop reason 4 is the arrival of `term_sheets_arrived`, `safe_filled` or `bridge_offered` (v1 has no separate "SAFE offer": a SAFE's answer is the filled message). Reason 3: below `holiday.stop_runway_months` the first time in the holiday (a holiday that starts below 6 stops only if runway recovers and falls again), or below 3 months at any time; 3 is the spec's fixed floor, a module constant, since the brief lists four keys. The summary is written by `holiday.py` (kind `holiday_summary`, linked to History), from the inbox rows and auto-resolved events of the months played; it is not an inbox template. Continue and Holiday are disabled while a holiday runs; the strip shows month N of M, the date, the stop rules and "Stop after this month", then the reason and a link to the summary.
- **Determinism test.** A 12-month holiday and 12 Continues give equal state, ledger lines, snapshots and inbox items (the summary item aside).
- **Saves manager.** Rename changes `save_meta.display_name` (migration `0017`), never the file, slug or company name; the column is mapped `deferred`, because migration 0013 loads `save_meta` through the current models. Duplicate and restore copy with SQLite's backup API into a new slug made from the display name (`kestrel-restored-apr-2010`, then `-2`), upgrading an old backup to the latest migration. Delete removes the save, its WAL files, its backups and its index entry. Every action takes the save's write lock, so a turn, an action or a holiday in progress makes it 409. Ironman saves can be renamed and deleted. The main menu's table is replaced by the same Saves manager; Saves is key 0 in the left nav.
- **History "shown rating".** The spec does not define it, and no history of displayed ranges was stored, so: a person's shown rating is the mean midpoint of the displayed ranges of their role's primary skills (what the player sees), logged for every player employee at each month end in `person_rating_log` (migration `0018`). Best hires compare their first logged month with their last; notable departures use the last; saves from before M7b start logging at their next turn. The founder is left out of longest serving. "Poached by" names the rival whose employment starts when they left.
- **Timeline.** Entries: answered and auto-resolved events (by "You" or "Default (at Continue)"), player and delegate actions in words (choose_event is covered by the event row), and inbox items of hires, departures, launches, first customers, ARR milestones, rounds, the board and rival news (the `fired` message is left out: the Fire action shows). Inbox items have no actor; a source filter hides them. Month lines show when nothing filters, or for the months that still have an entry. Pages of 50, server side.
- **Tooltips.** `backend/data/glossary.yaml` (142 terms) is validated at load but not hashed into saves (UI text, not game data). A column header's term is its column id, or `meta.term` where an id is computed (skill and personality columns, statement periods) or means something else in another table; P&L lines use `line.*` and `account.*`. `frontend/src/lib/glossary.test.ts` reads the sources and fails on any KPI tile, column header, hand-built `<th>` or `Term` without a definition. The top bar's and Overview's breakdowns come from one lazy route (`GET /overview/breakdowns`), fetched when a tooltip first opens, so Continue does not pay for the average-morale terms; product quality and share and the salary breakdown ride inline. Burn's breakdown lists cost lines less revenue, financing and event gains, so it sums to the fall in cash. A person's morale keeps its existing breakdown panel.
- **Saved views.** `saves/ui_settings.json` via `GET /api/settings/ui` and `PUT /api/settings/ui/tables/{id}`. The built-in Default is never stored. Table ids: `people.overview`, `people.skills`, `recruitment.candidates`, `recruitment.plans`, `products`, `market` (one set for every segment's table), `competitors`, `captable`, `history.timeline`. The People screen's Columns menu moved into the views menu (show, hide, move left and right). `/` focuses the table search where a screen has one (People, History).
- **COO (17.3).** The thresholds are balance keys next to the brief's three (`coo.max_issues`, `runway_months`, `morale_below`, `role_open_months`, `board_below`) rather than literals in the sim. Issues come in 17.3's order, critical events before major ones; "a unit over its span limit" uses the Org tile's rule; a rival price cut counts in the last played month. The answer uses `llm.model_story`, counts toward the budget and `llm_call_log` (purpose `coo`); over budget the call is logged as `budget`. `MockLLMAdapter` answers "[mock] …" from the first briefing line; `TemplateAdapter` gives the offline reply. The e2e flow points `llm_settings.json` at the mock adapter for its duration and restores it.
- **The 10-year run** is `nightly` (about 40 s): seed 7, funded spinout, the earn-and-burn product and team hired through searches and offers, then 12-month holidays (stop: critical). It reached turn 120 with $5.3M ARR, 6 hires and 10 holidays (each ran its 12 months) and about 1,100 API calls; it sweeps every GET route in the OpenAPI spec each year.
- **Tests adjusted, not weakened.** `test_openapi_declares_response_models` also accepts 202 (a holiday starts as a job) and 204 (a deleted save); `test_create_list_get` checks the new save fields; schema-version assertions are 19.

## Follow-ups

- **Former staff from History.** People who left are not in the live state, so a History or hall-of-fame link to a former employee opens a "not found" profile. A read-only profile for former staff would fix it.
- **Event links.** History and the COO briefing link events to the inbox, not to the event's own message.
- **Table search.** `/` focuses a search box only where a screen has one (People, History); the other listed tables have none yet.
- **The 10-year script's staff dwindle** (6 hired, 3 left at month 120) because it never replaces leavers; with M7a's attrition a static team shrinks. Worth a look in Reece's manual check alongside the two-person launch timing.
- **Holiday status in memory.** The job registry lives in the API process: after a restart the last holiday's status is gone (its summary item stays).
- Carried from M7a: the two-person launch at about month 21; hard difficulty; the funded-company ARR plateau; refusal fallbacks for the Claude adapter.
