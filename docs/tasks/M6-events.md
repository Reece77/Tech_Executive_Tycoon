# M6: Events, storylines and relationships

**Goal:** the company has a story. Each month the engine picks one to three events from what is actually happening (an unhappy star, a price war, a short runway, two people who can't stand each other), writes them with the LLM inside strict limits or from templates offline, and lets the player choose; some grow into multi-month storylines; people have relationships that move morale; and the month reads like a company, with headlines and board minutes. One milestone: rules, LLM pipeline, API, CLI and screens.

**Spec sections:** §5, §12, §20 · **ADRs:** 0002, 0005 (budget §6), 0006 (amended: no weekly sub-turns), 0011 (tone), 0012, 0014 · **Formulas:** `docs/formulas.md` §16 (all) and its §9 and §12 rows · **Wireframes:** `docs/wireframes.md` (M6 screens) and `docs/wireframes/source/Event.dc.html`, `Settings.dc.html` · **Depends on:** M5 (`m5-done`)

## Context

ADR-0005 is the contract: the director decides when, about whom, how severe and which effects are allowed; the LLM only writes the words and attaches allowed effects; the validator clamps everything; templates are the offline mode and the fallback. LLM calls happen outside the sim after the turn commits, and every event is stored, so replay never calls the LLM. Reece set the budget at $10 a calendar month.

## Out of scope

Weekly crisis sub-turns (v2, ADR-0006 amended), "Ask my COO" (M7), the History screen (M7), events about v2 or v3 systems, voice or images.

## Sub-tasks (commit after each)

0. **Carried from M5 (do first):**
   - **Suite speed:** save rival people, employments and ledger lines in bulk (as M5 did for loads), and anything else profiling shows, until the GitHub `check` run is back under 20 minutes; then restore the workflow's `timeout-minutes` to 25. Record before and after.
   - **Busy save:** a second write to a save while one is in progress returns HTTP 409 with code `save_busy` and a clear message, not a 500.
   - **Old saves on game routes:** opening a save from before the latest migration upgrades it (as the save index does) or refuses with a clear "upgrade needed" message; never a 500.
   - **Free agents:** people from a failed rival join a pool of free agents for 6 months and appear in the player's later searches for their roles (not only searches open when the rival fails); `rivals.free_agent_months` (6).
1. **Data and formula tests:** every §12 M6 key; the trigger table (§16.2) and effect caps (§16.3) as data; every §16.11 worked example as a unit test.
2. **Relationships** (§16.7): pairs, starting values, drift, tag pushes, `W_rel` in morale, the §13.6 change; property tests (relationships stay in [−100, 100]; pairs exist only for unit-mates and manager links). Migration; data dictionary.
3. **Director** (§16.1, §16.2): triggers from state, candidate weights, cooldowns, severity, critical spacing, stream `events` (id 6), `EventRequest`s from phase 12.
4. **Templates** (§16.4): about 60 in `backend/data/events/*.yaml`, validated at load (every trigger covered, every critical trigger has a critical template, placeholders resolvable, effects within caps); the 5 storylines (§16.6).
5. **Event service and validator** (§16.3, §16.5): the post-commit service, `TemplateAdapter`, `MockLLMAdapter` (deterministic, used by every test), `AnthropicAdapter` (structured output, models and prices from settings, budget meter and fallback, `llm_call_log`), the context builder with its allowlist, the validator with clamps and one retry; the hidden-value prompt test.
6. **Choices and critical events:** the `choose_event` action (energy 0) applying effects, auto-resolution of minor and major events at Continue, Continue blocked by an open critical event (the API returns the blocking event), follow-ups.
7. **Other LLM text** (§16.8): headlines in Market news, board minutes, exit-interview lines, each with templates.
8. **API, CLI and screens:** events with choices and effect words (§16.9), storylines, relationship labels on profiles and in the org unit panel, the LLM meter and settings; `tst events`, `tst choose --event --choice`, `tst storylines`; the event card in the inbox, the critical event modal, the profile's relationships panel, the Settings screen per the wireframes, and an **Event** inbox kind badge.
9. **Golden, balance and e2e:** golden snapshots with `MockLLMAdapter` (CHANGELOG note); the §16.10 balance table, tuning only `events.*` and `relationships.*` keys; Playwright: (a) answer an event and see its effect; (b) a scripted critical event blocks Continue until answered; (c) switch to offline mode in Settings and receive a template event.

## Acceptance criteria

- [ ] Every §16.11 worked example passes as a test.
- [ ] The director's events follow the state (a scripted low-morale star, price war and short runway each produce their events) and respect every cooldown.
- [ ] No LLM draft can apply an effect outside the catalog, a target outside the eligible list, or a value beyond its cap (property test over random drafts).
- [ ] No prompt contains a hidden value (planted-value test).
- [ ] With the budget at $0 or no API key, the game plays fully on templates; the meter and fallback work at the limit.
- [ ] Critical events block Continue until answered; follow-ups arrive the next month.
- [ ] Relationships move morale through `W_rel`; a credit-taker's unit-mates settle near the §16.11 value.
- [ ] Replay reproduces a save with events, choices and a storyline without calling any adapter.
- [ ] §16.10 balance targets met (printed, values recorded).
- [ ] `make check` green; `make e2e` passes all flows; merged and tagged `m6-done` per CLAUDE.md §6.

## Manual check (Reece, after merge)

Put your `ANTHROPIC_API_KEY` in `backend/.env`, play 24 months, and note: do events feel like they come from your company's situation, are choices interesting, does any event feel unfair, and how much of the $10 did it use (the meter shows it).

## Decisions made

- **Sub-task 0.** A turn writes changed rows as one bulk `UPDATE` per table (a merge per row cost a `SELECT`); a new save bulk-inserts people's child rows; `_upsert` inserts by binary search. A per-save, non-blocking write lock makes a second write a 409 `save_busy` (SQLite's own lock maps to the same); `existing_save_path` upgrades an old save (or 409 `upgrade_needed`). Free agents live in `free_agent` (migration 0014). Tables added after 0013 are read only when present with all their columns (`has_table`), because migration 0013 loads state through the current models.
- **Where things live.** The director, triggers, effects and template rendering run inside the turn, so they are pure code in `tst/sim/events/` (ADR-0005 names `tst/events/` for the director; placement only). `tst/events/` holds the context builder, validator, drafts and the service; `tst/llm/` the adapters, settings and spend meter; `tst/db/events.py` runs the service against a save.
- **Event lifecycle.** Phase 12 queues next month's events as `pending` rows (the `EventRequest`s of ADR-0012); after the turn commits, `write_pending` writes their words and validated choices (`open`) and an inbox item (kind `event` or `critical_event`). Continue first writes anything left pending, then plays; phase 1 answers open minor and major events with their first choice; an open critical event makes `advance_turn` raise `CriticalEventOpenError` (409 `critical_event_open` with `event_id`). An unwritten event (only in in-memory tests) closes with nothing applied and never blocks.
- **Ids.** Event, storyline and queue ids continue from `max(id) + 1` of their tables, not `save_meta` (an old save's migration 0013 reads `save_meta` through the current model).
- **Template effects** are `share`s of the severity's cap, so every template is within its caps at every severity; the template's first choice is the reasonable default. Target words map to the eligible list (`unit` falls back to the company for the root; `pair` is the founder and the person for one-person triggers).
- **Relationships** are the player's company only (rivals' people are not in events); `W_rel` shows in the morale breakdown as "Relationships with teammates" (a morale term, never a pair's number).
- **Effects.** Costs post to 6900 General and administrative, gains to the new `4900_other_income`; `energy_delta` applies when next month's energy resets (from events answered this month); `growth_boost` raises the role's first primary skill; `reveal_tag` reveals the first hidden tag in the person's tag order; `customers_pct` applies to the event's segment (all segments if none).
- **LLM.** Claude through `output_config.format` with the spec 12 schema (cash in dollars), effort low; defaults `claude-haiku-5-5` for events, headlines and minutes and `claude-sonnet-5-5` for storyline steps, priced at 10/50 and 200/1000 cents per million tokens (settings, editable). Settings and the monthly spend live next to the saves (`saves/llm_settings.json`, `saves/llm_spend.json`): the budget is real money across saves. A refusal or `max_tokens` stop is a failed draft (retry, then the template); server-side refusal fallbacks are not enabled. Tests force `MockLLMAdapter` (`TST_LLM_ADAPTER=mock` in `tests/conftest.py`); the e2e API runs with no key.
- **Read-only text** (16.8): headlines every month (from the month's rival moves offline), minutes after a quarterly board meeting, an exit line per resignation; stored in `llm_text` and shown on Market news, the board's last meeting and the resignation message.
- **Balance (sub-task 9), Reece 2026-10-29:** the §16.1 rules alone with `events.*` keys gave about 0.7–0.85 events a month in the calm earn-and-burn script. Reece chose a quiet-month fill (minor only, when every triggered candidate is in cooldown) plus key tuning aimed at about 1.2 a month (formulas.md §16.1). Tuned: count weights [0.08, 0.40, 0.38, 0.14], template cooldown 12, person cooldown 4, `underpaid` 0.95, `star_performer` top 30%, `team_clash` −25, `team_bond` 30, `board_unhappy` 50, minor morale cap 3. `low_morale` stays at 35 (the §16.11 director example). Result (`uv run pytest tests/integration/test_event_balance.py -s`): **1.23 events a month**; no critical event (none in 6 months twice); event cash −1.44% of revenue (worst seed −2.24%); morale +1.32 on average (worst seed +3.22, seed 4, mostly from who stays and who leaves differing between the runs); **41 distinct templates**; M5 targets unchanged and passing.
- **Golden snapshots** are regenerated with `MockLLMAdapter`: events now apply their first choice at Continue, and the script answers critical events with their first choice (`answer_critical`).
- **Read routes share one load (sub-task 0, found by `make e2e`).** A screen sends about seven GETs at once and each did a full `load_state`; together they took about 6 s each (GIL contention), past Playwright's 5 s waits. `read_session` makes reads of one save take turns in the process and reuse the remembered state; the file stamp is taken only while no reader holds a connection (a reader creates the WAL and its close removes it), and a loaded state is remembered only if no commit landed meanwhile. Seven parallel reads: 0.35 s cold, 0.03 s warm.
- **CI as two matrix jobs (Reece, 2026-10-30).** The runner has 2 cores and the suite already ran under `pytest -n auto`, so one job could not get under 20 minutes. `check (shard 1/2)` runs backend lint, types and test shard 1; `check (shard 2/2)` the API sync, the frontend and shard 2; 25 minutes each. `--shard K/N` (tests/conftest.py) assigns tests longest first to the least-loaded shard from `tests/durations.json` (`make test-durations` refreshes it; a new test counts as the mean). `make check` stays the local command. Each test also weighs 1.3 s when sharding (`SHARD_OVERHEAD_S`, fitted on CI: a test costs about 0.93x its local time plus 1.2 s), because a split by local time alone gave 8m15s against 13m53s. **Before and after:** one job of 26m40s at the start of M6 (19m51s after the speed work in sub-tasks 0 and 9); now `check (shard 1/2)` 14m09s and `check (shard 2/2)` 12m35s, so the check takes 14m09s wall clock for about 27 runner-minutes (15 + 13 billed, the same as the single job's 27).

## Follow-ups

- About 20 more personnel, operations and market templates (M7, Reece): quiet-month fills are a large share of events in a calm company.
- The morale effect of events is close to the ±3 target on one seed (+3.22 on seed 4); worth a look after the new templates.
- Events need staff or a product to be varied: a solo founder with no product sees mostly finance and quiet-month events.
- Server-side refusal fallbacks for the Claude adapter (a refusal now falls back to the template).
- **Turn speed (M7):** profile a turn first, then optimize: RNG stream construction (`RngFactory.stream` per person and decision) and the incumbents' key-people loops (rivals' people grow, age and resign every month). The slowest tests are turn-heavy (balance runs, goldens, time budgets) and would gain most.
- Consider a slow/nightly marker for the longest tests (see the 20 slowest in the M6 summary); refresh `tests/durations.json` when the suite changes shape.

## Follow-ups

_(Agent fills in.)_
